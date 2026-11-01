#!/usr/bin/env python3
"""Addendum 36 amendment B: score the Study 5 job files with a Qwen size-ladder judge.  AI-generated; review and test before use.

  P5_ENDPOINT=<base URL ending in /v1> P5_KEY_FILE=<file outside the repo> score_ladder.py <q38_27b|q35_9b|q35_4b> <jobs.jsonl> <out.jsonl> [--workers N] [--max-model-len N]

Study 5's scorer (addendum 26 `score_judges.py`) imported unchanged; only three judge entries are added.  Request-only, resumable.  The endpoint and the
key come from the environment / a local file and are never written anywhere.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

S5 = Path(__file__).resolve().parent.parent / "study5_judge_panel"
sys.path.insert(0, str(S5))
import score_panel as sp  # noqa: E402  (study 5; defines sj, the addendum-26 scorer module)

sj = sp.sj
NOTHINK = {"chat_template_kwargs": {"enable_thinking": False}}
LADDER = {"q38_27b": "Qwen/Qwen3.8-27B", "q35_9b": "Qwen/Qwen3.5-9B", "q35_4b": "Qwen/Qwen3.5-4B"}
for _k, _m in LADDER.items():
    sj.JUDGES[_k] = {"model": _m, "extra": NOTHINK}


def main(argv=None) -> int:
    a = list(argv or sys.argv[1:])
    judge, jobs, out, rest = a[0], a[1], a[2], a[3:]
    ep = os.environ.get("P5_ENDPOINT")
    kf = os.environ.get("P5_KEY_FILE")
    if not ep or not kf:
        raise SystemExit("set P5_ENDPOINT and P5_KEY_FILE")
    key = Path(kf).read_text().strip()
    w = int(rest[rest.index("--workers") + 1]) if "--workers" in rest else 3
    sj.MAX_WORKERS = max(sj.MAX_WORKERS, w)

    def post(url, body, timeout=900.0):
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    sj.post = post
    args = ["--jobs", jobs, "--judge", judge, "--endpoint", ep, "--out", out, "--repeats", "3", "--workers", str(w), "--confirm-addendum26-frozen"]
    if "--max-model-len" in rest:
        args += ["--max-model-len", rest[rest.index("--max-model-len") + 1]]
    return sj.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
