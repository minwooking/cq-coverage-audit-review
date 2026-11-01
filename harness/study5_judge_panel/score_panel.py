#!/usr/bin/env python3
"""Addendum 36: score a job file with one open-weights judge using addendum 26's scorer, imported unchanged except for (i) two extra judge
entries (q38, q80) and (ii) an Authorization header for the Qwen endpoints.  AI-generated; review before reuse.

  P5_ENDPOINT=<base URL ending in /v1> score_panel.py <judge: glm|gptoss|q38|q80> <jobs.jsonl> <out.jsonl> [--workers N]

Request-only.  Resumable ((cell, repeat) pairs with a terminal record are skipped).  The endpoint comes from the environment only (never written to a
file); the key for q38/q80 comes from P5_KEY or CHUNKTOGRAPH_LLM_API_KEY, read in-process and never printed.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import urllib.request

import p5_common as C

spec = importlib.util.spec_from_file_location("sj", C.HARNESS / "review6_judges" / "score_judges.py")
sj = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sj)
sj.JUDGES["q38"] = {"model": "Qwen/Qwen3.8-Flash-Next", "extra": {"chat_template_kwargs": {"enable_thinking": False}}}
sj.JUDGES["q80"] = {"model": "Qwen/Qwen3-Next-80B-A3B-Instruct-FP8", "extra": {"chat_template_kwargs": {"enable_thinking": False}}}


def _auth() -> str:
    if os.environ.get("P5_KEY"):
        return os.environ["P5_KEY"]
    k = os.environ.get("CHUNKTOGRAPH_LLM_API_KEY")
    if not k:
        raise SystemExit("set P5_KEY or CHUNKTOGRAPH_LLM_API_KEY (the judge key is environment-only)")
    return k


def main(argv=None) -> int:
    a = list(argv or sys.argv[1:])
    judge, jobs, out = a[0], a[1], a[2]
    rest = a[3:]
    ep = os.environ.get("P5_ENDPOINT")
    if not ep:
        raise SystemExit("set P5_ENDPOINT")
    w = int(rest[rest.index("--workers") + 1]) if "--workers" in rest else 3
    sj.MAX_WORKERS = max(sj.MAX_WORKERS, w)
    key = _auth() if judge in ("q38", "q80") else "none"

    def post(url, body, timeout=900.0):
        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    sj.post = post
    args = ["--jobs", jobs, "--judge", judge, "--endpoint", ep, "--out", out, "--repeats", "3", "--workers", str(w),
            "--confirm-addendum26-frozen"]
    if "--studies" in rest:
        args += ["--studies", rest[rest.index("--studies") + 1]]
    return sj.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
