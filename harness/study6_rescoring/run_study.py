#!/usr/bin/env python3
"""Addendum 37 scorer wrapper: addendum 26's score_judges.py imported unchanged, plus judge entries qwen35 and q38.  AI-generated; review before reuse.

  S6_ENDPOINT=<base URL ending in /v1> run_study.py <judge: glm|gptoss|qwen35|q38> <jobs.jsonl> <out.jsonl> [--studies a,b] [--workers N]

Request-only, resumable.  The endpoint comes from the environment only.  q38 needs CHUNKTOGRAPH_LLM_API_KEY (never printed); the other judges need none.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("sj", HERE.parent / "review6_judges" / "score_judges.py")
sj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sj)
OFF = {"chat_template_kwargs": {"enable_thinking": False}}
sj.JUDGES["qwen35"] = {"model": "Qwen/Qwen3.5-4B", "extra": OFF}
sj.JUDGES["q38"] = {"model": "Qwen/Qwen3.8-Flash-Next", "extra": OFF}


def main(argv=None) -> int:
    a = list(argv if argv is not None else sys.argv[1:])
    judge, jobs, out, rest = a[0], a[1], a[2], a[3:]
    ep = os.environ.get("S6_ENDPOINT")
    if not ep:
        raise SystemExit("set S6_ENDPOINT")
    w = int(rest[rest.index("--workers") + 1]) if "--workers" in rest else 3
    key = "none"
    if judge == "q38":
        key = os.environ.get("CHUNKTOGRAPH_LLM_API_KEY") or ""
        if not key:
            raise SystemExit("q38 needs CHUNKTOGRAPH_LLM_API_KEY")

    def post(url, body, timeout=900.0):
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    sj.post = post
    args = ["--jobs", jobs, "--judge", judge, "--endpoint", ep, "--out", out, "--repeats", "3", "--workers", str(w),
            "--max-model-len", "32768" if judge == "qwen35" else "65536", "--confirm-addendum26-frozen"]
    if "--studies" in rest:
        args += ["--studies", rest[rest.index("--studies") + 1]]
    return sj.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
