#!/usr/bin/env python3
"""Fetch the documentation pages and ontology files of one domain (addendum 35 PLAN 35.2).  AI-generated; review before reuse.

  fetch_sources.py <domain>      -> <domain>/raw/<file>, <domain>/fetch_log.json (url, sha256, bytes, retrieved UTC, license text found)

Plain urllib GET, generic User-Agent, no e-mail or personal identifier in any request.  Raw files are git-ignored.
"""
from __future__ import annotations

import html
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone

import s4_common as C


def get(url: str, accept: str | None = None, tries: int = 3) -> bytes:
    last = None
    for _ in range(tries):
        try:
            h = {"User-Agent": C.UA}
            if accept:
                h["Accept"] = accept
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=90) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
    raise SystemExit(f"fetch failed: {url}: {last!r}")


def license_sentence(t: str) -> str:
    m = re.search(r'class="copyright"', t)
    if not m:
        return ""
    seg = re.sub(r"<[^>]+>", " ", t[m.start():m.start() + 1500])
    return re.sub(r"\s+", " ", html.unescape(seg))[:260]


def main(argv=None) -> int:
    d = (argv or sys.argv[1:])[0]
    cfg = C.DOMAINS[d]
    raw = C.ddir(d) / "raw"
    raw.mkdir(exist_ok=True)
    log = {"domain": d, "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "files": []}
    for name, url in cfg["docs"]:
        b = get(url)
        (raw / f"{name}.html").write_bytes(b)
        lic = license_sentence(b.decode("utf-8", "replace"))
        log["files"].append({"kind": "doc", "name": name, "url": url, "file": f"{name}.html", "bytes": len(b),
                             "sha256": __import__("hashlib").sha256(b).hexdigest(), "license_statement_on_page": lic})
    for fn, url, acc in cfg["ontology"]:
        b = get(url, acc)
        (raw / fn).write_bytes(b)
        log["files"].append({"kind": "ontology", "name": fn, "url": url, "file": fn, "bytes": len(b),
                             "sha256": __import__("hashlib").sha256(b).hexdigest()})
    log["license_docs"], log["license_ontology"], log["redistribute"] = cfg["license_docs"], cfg["license_ontology"], cfg["redistribute"]
    (C.ddir(d) / "fetch_log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    for f in log["files"]:
        print(f["name"], f["bytes"], f["sha256"][:12], f.get("license_statement_on_page", "")[:100])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
