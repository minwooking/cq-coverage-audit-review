#!/usr/bin/env python3
"""Run one judge over one domain's jobs with the unchanged scorer of addendum 26 (PLAN 35.6).  AI-generated; review before reuse.

  S4_ENDPOINT=<judge base URL ending in /v1> run_judges.py <domain> glm|gptoss [--workers N]

Request-only.  Resumable (scorer skips valid (cell, repeat) pairs).  At most 3 workers per endpoint (the scorer's cap).  Hosts are never written to a file.
"""
from __future__ import annotations

import importlib.util
import os
import sys

import s4_common as C


def main(argv=None) -> int:
    a = list(argv or sys.argv[1:])
    d, judge = a[0], a[1]
    ep = os.environ.get("S4_ENDPOINT")
    if not ep:
        raise SystemExit("set S4_ENDPOINT to the judge endpoint (OpenAI-compatible base URL)")
    spec = importlib.util.spec_from_file_location("sj", C.HARNESS / "review6_judges" / "score_judges.py")
    sj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sj)
    out = C.ddir(d) / "judge_raw" / f"{judge}.jsonl"
    out.parent.mkdir(exist_ok=True)
    args = ["--jobs", str(C.ddir(d) / "jobs.jsonl"), "--judge", judge, "--endpoint", ep, "--out", str(out), "--repeats", "3",
            "--confirm-addendum26-frozen", "--progress", str(out.with_name(f"{judge}_progress.log"))]
    args += a[2:] if len(a) > 2 else ["--workers", "3"]
    return sj.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
