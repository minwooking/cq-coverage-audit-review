#!/usr/bin/env python3
"""Corpus of one domain: HTML -> text -> the chunker of addendum 27 -> nested chunking_result JSON (PLAN 35.3).  AI-generated; review before reuse.

  build_corpus.py <domain>  -> <domain>/corpus/cleaned/<doc>.txt, <domain>/corpus/corpus.json, <domain>/corpus_stats.json
Offline, no model.  The bank is never read here.  chunk rules are imported unchanged from review6_natural/build_natural_corpus.py.
"""
from __future__ import annotations

import json
import statistics
import sys

import s4_common as C

sys.path.insert(0, str(C.HARNESS / "review6_natural"))
import build_natural_corpus as bn  # noqa: E402
import html_to_text as h2t  # noqa: E402


def main(argv=None) -> int:
    d = (argv or sys.argv[1:])[0]
    cfg = C.DOMAINS[d]
    dd = C.ddir(d)
    log = json.loads((dd / "fetch_log.json").read_text(encoding="utf-8"))
    (dd / "corpus" / "cleaned").mkdir(parents=True, exist_ok=True)
    top, toc, rows, lengths = [], [], [], []
    n_atomic = 0
    for rec in [f for f in log["files"] if f["kind"] == "doc"]:
        cleaned = bn._tidy(h2t.convert((dd / "raw" / rec["file"]).read_text(encoding="utf-8", errors="replace")))
        (dd / "corpus" / "cleaned" / f"{rec['name']}.txt").write_text(cleaned, encoding="utf-8")
        title = bn.file_title(cleaned, rec["name"])
        adv, n_doc = [], 0
        for st, lines in bn.to_sections(cleaned, title):
            chunks = bn.chunk_section(lines)
            if not chunks:
                continue
            adv.append({"title": st, "status": "ok", "chunk_text": " ".join(chunks)[:4000],
                        "atomic_chunks": [{"content": {"text": c}} for c in chunks]})
            lengths.extend(len(c) for c in chunks)
            n_doc += len(chunks)
        top.append({"toc_hierarchy": [cfg["title"], title], "toc_index": f"{len(top) + 1}",
                    "child_chunks": {"advanced_chunking_result": adv}})
        toc.append({"title": f"{cfg['title']} / {title}", "level": 2})
        n_atomic += n_doc
        rows.append({"doc": rec["name"], "raw_sha256": rec["sha256"], "cleaned_chars": len(cleaned), "sections": len(adv), "atomic_chunks": n_doc})
    corpus = {"toc": toc, "chunks": top,
              "_provenance": {"generated_from": f"natural-language documentation of {cfg['title']} (see fetch_log.json)",
                              "n_top_level_chunks": len(top), "n_atomic_chunks": n_atomic,
                              "note": "addendum 35 corpus; the bank is never read by the builder"}}
    out = dd / "corpus" / "corpus.json"
    out.write_text(json.dumps(corpus, ensure_ascii=False, indent=1), encoding="utf-8")
    L = sorted(lengths)
    stats = {"domain": d, "corpus_sha256": C.sha256_file(out), "docs": rows, "top_level_chunks": len(top), "atomic_chunks": n_atomic,
             "atomic_chars_total": sum(L), "atomic_len": {"mean": round(statistics.mean(L), 1), "median": statistics.median(L),
                                                          "p90": L[int(0.9 * len(L))], "min": L[0], "max": L[-1]},
             "rules": {"merge_under": bn.MERGE_UNDER, "split_over": bn.SPLIT_OVER, "drop_under": bn.DROP_UNDER},
             "license_docs": cfg["license_docs"], "redistributable": cfg["redistribute"]}
    (dd / "corpus_stats.json").write_text(json.dumps(stats, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in stats.items() if k != "docs"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
