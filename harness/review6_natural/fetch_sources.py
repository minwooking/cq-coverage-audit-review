#!/usr/bin/env python3
"""Addendum 27 step 2a: fetch the natural-language Brick documentation named in PLAN.md 27.3.

AI-generated; review before reuse.  Network only to api.github.com (file trees at pinned commits),
raw.githubusercontent.com, and the four open-access paper PDFs listed in PAPERS.  Plain urllib
requests with the library's default User-Agent: no e-mail, no personal identifier, no credential in any
header or URL.  Never downloads TTL/OWL/SHACL/CSV schema files (extension filter below).

Writes corpus/raw/<group>/<path> and corpus/fetch_log.json (url, repo, pin, path, license text evidence,
retrieval time UTC, sha256 of the fetched bytes, byte count).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "corpus" / "raw"

# (group, repo, pin, include predicate on path, license note resolved from the LICENSE file below)
REPOS = [
    ("brick-docs", "BrickSchema/docs", "3f92114a643078432c50bc7f9de3ffb8f5980fe1",
     lambda p: p.endswith(".md") and (p == "intro.md" or p.split("/")[0] in
                                      {"brick", "extra", "lifecycle", "metadata", "modeling", "software"})),
    ("brick-website", "BrickSchema/brick-website", "b9506a909d4ccc1abe3234147ce13377f17a6bf9",
     lambda p: p.endswith(".md") and p.split("/")[0] in
               {"webpages", "blog", "tools", "ontologyPages", "usageDetails"}),
    ("py-brickschema", "BrickSchema/py-brickschema", "50c7670acce806baa4a1d2c47101bff9bf37162e",
     lambda p: p == "README.md" or (p.startswith("docs/") and p.endswith(".rst") and not p.startswith("docs/source/"))),
    ("brick-v1.4.4", "BrickSchema/Brick", "4b5be60d27f9b4d96fe477f45513fa71afebe684",
     lambda p: p in {"README.md", "CONTRIBUTING.md", "extensions/README.md", "alignments/README.md",
                     "examples/simple_apartment/README.md"}
     or (p.startswith("alignments/") and p.endswith("/README.md") and p.count("/") == 2)),
]
FORBIDDEN_EXT = (".ttl", ".owl", ".rdf", ".nt", ".csv", ".shacl", ".jsonld")

# Open-access papers: plan 27.3 admits a paper only with an explicit CC-BY (no NC, no ND) statement
# in its text.  The list below is the CC-BY (no NC/ND) set among the top results of the web search
# "Brick schema building metadata paper open access CC BY license" (2026-10-17); others in the same
# results (CC BY-NC-ND / CC BY-NC) are excluded by the rule.
PAPERS = [
    ("paper-fierro2020", "https://gtf.fyi/papers/house2020fierro.pdf",
     "Fierro et al. 2020, Formalizing Tag-Based Metadata With the Brick Ontology (Frontiers in Big Data)"),
    ("paper-vizbrick2022", "https://osti.gov/servlets/purl/1997805",
     "VizBrick: A GUI-based Interactive Tool for Authoring Semantic Metadata for Building Datasets (CEUR-WS)"),
    ("paper-buildsys2024-llm", "https://eta-publications.lbl.gov/sites/default/files/2025-04/large_language_models.pdf",
     "Large Language Models for the Creation and Use of Semantic Ontologies in Buildings (BuildSys 2024)"),
    ("paper-brickllm2025", "https://moderate-project.eu/wp-content/uploads/2025/07/BRICKLLM-SoftwareX.pdf",
     "BrickLLM: A Python library for generating Brick-compliant RDF graphs using LLMs (SoftwareX)"),
]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def http_get(url: str, tries: int = 3) -> bytes:
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url)  # default User-Agent only
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"fetch failed {url}: {last!r}")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    log: list[dict] = []
    licenses: dict[str, dict] = {}
    for group, repo, pin, pred in REPOS:
        tree = json.loads(http_get(f"https://api.github.com/repos/{repo}/git/trees/{pin}?recursive=1"))
        if tree.get("truncated"):
            raise SystemExit(f"tree truncated for {repo}")
        blobs = [x["path"] for x in tree["tree"] if x["type"] == "blob"]
        # license file text (record, do not include in the corpus)
        lic_path = next((p for p in blobs if p == "LICENSE"), None)
        lic_info = {"file": None}
        if lic_path:
            lb = http_get(f"https://raw.githubusercontent.com/{repo}/{pin}/{lic_path}")
            txt = lb.decode("utf-8", errors="replace")
            lic_info = {"file": f"{repo}@{pin[:10]}:LICENSE", "sha256": sha256_bytes(lb),
                        "first_line": txt.strip().splitlines()[0][:120],
                        "has_neither_the_name": "Neither the name" in txt,
                        "is_mit": "Permission is hereby granted, free of charge" in txt}
        licenses[group] = lic_info
        chosen = sorted(p for p in blobs if pred(p) and not p.lower().endswith(FORBIDDEN_EXT))
        for path in chosen:
            url = f"https://raw.githubusercontent.com/{repo}/{pin}/{path}"
            data = http_get(url)
            dest = RAW / group / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            log.append({"group": group, "kind": "repo-file", "repo": repo, "pin": pin, "path": path,
                        "url": url, "retrieved_utc": now_utc(), "sha256": sha256_bytes(data),
                        "bytes": len(data)})
            print(f"{group}: {path} ({len(data)} B)")
    failed_papers: list[dict] = []
    for group, url, title in PAPERS:
        try:
            data = http_get(url, tries=2)
        except Exception as exc:  # noqa: BLE001  (plan 27.3: a paper that is not fetchable without login is skipped and logged)
            failed_papers.append({"group": group, "url": url, "title": title, "error": repr(exc)[:200]})
            print(f"{group}: NOT FETCHED ({repr(exc)[:120]})")
            continue
        if not data.lstrip().startswith(b"%PDF"):
            failed_papers.append({"group": group, "url": url, "title": title,
                                  "error": "response is not a PDF (blocked or interstitial page); not retried with altered headers"})
            print(f"{group}: NOT A PDF; skipped")
            continue
        dest = RAW / group / "paper.pdf"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        text = subprocess.run(["pdftotext", str(dest), "-"], capture_output=True, text=True, check=True).stdout
        (RAW / group / "paper.txt").write_text(text, encoding="utf-8")
        lic_lines = [ln.strip() for ln in text.splitlines()
                     if re.search(r"creative\s*commons|CC[ -]BY", ln, re.I)][:3]
        log.append({"group": group, "kind": "paper-pdf", "title": title, "path": "paper.pdf", "url": url,
                    "retrieved_utc": now_utc(), "sha256": sha256_bytes(data), "bytes": len(data),
                    "license_evidence_lines": lic_lines, "pdftotext_chars": len(text)})
        print(f"{group}: {len(data)} B pdf, {len(text)} chars text; license lines: {lic_lines[:2]}")
    (HERE / "corpus" / "fetch_log.json").write_text(
        json.dumps({"fetched_utc": now_utc(), "licenses": licenses, "files": log,
                    "papers_not_fetched": failed_papers}, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(f"fetched {len(log)} items")
    return 0


if __name__ == "__main__":
    sys.exit(main())
