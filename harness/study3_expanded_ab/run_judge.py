#!/usr/bin/env python3
"""Runner for addendum 34 A1: addendum 26's scorer (imported, unchanged) with a raised worker cap.  AI-generated; review before use.
  run_judge.py --judge glm|gptoss --endpoint URL --workers N [--jobs F] [--out F] [--repeats 3]
Endpoint comes from the command line only (never written to a committed file); no key is used.  Resumable: (cell, repeat) pairs with a terminal record are skipped."""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("sj", HERE.parent / "review6_judges" / "score_judges.py")
sj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sj)


def main(argv):
    w = int(argv[argv.index("--workers") + 1]) if "--workers" in argv else 8
    sj.MAX_WORKERS = max(sj.MAX_WORKERS, w)
    a = list(argv)
    judge = a[a.index("--judge") + 1]
    if "--jobs" not in a:
        a += ["--jobs", str(HERE / "jobs_new.jsonl")]
    if "--out" not in a:
        a += ["--out", str(HERE / "raw" / f"judge_{judge}_s3.jsonl")]
    return sj.main(a + ["--confirm-addendum26-frozen"])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
