#!/usr/bin/env python3
"""Addendum 35: run one `chunktograph` CLI command unchanged, with token-usage logging only.

AI-generated; review before reuse.  Usage:  run_pipeline.py <cli args...>   (same args as `uv run chunktograph`)

It imports chunktograph.cli.app and wraps `chat.completions.create` of the OpenAI client that
`chunktograph.llm.LLMClient` builds, so every pipeline LLM call is counted (calls, failures, prompt and
completion tokens from the response `usage`).  Request bodies are NOT changed, nothing is retried here.
One summary line per command is appended to $S4_USAGE_LOG (default build_usage.jsonl next to this file).
Endpoint/model/key come from the CHUNKTOGRAPH_LLM_* environment (the key is never printed or logged).
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = Path(os.environ.get("S4_USAGE_LOG", HERE / "build_usage.jsonl"))
lock = threading.Lock()
tot = {"calls": 0, "failures": 0, "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
       "calls_without_usage": 0, "max_prompt_tokens": 0}

from chunktograph import llm  # noqa: E402

_orig_init = llm.LLMClient.__init__


def _init(self, *a, **k):
    _orig_init(self, *a, **k)
    create = self._client.chat.completions.create

    def wrapped(*aa, **kk):
        try:
            resp = create(*aa, **kk)
        except Exception:
            with lock:
                tot["calls"] += 1
                tot["failures"] += 1
            raise
        u = getattr(resp, "usage", None)
        with lock:
            tot["calls"] += 1
            if u is None:
                tot["calls_without_usage"] += 1
            else:
                p, c = int(getattr(u, "prompt_tokens", 0) or 0), int(getattr(u, "completion_tokens", 0) or 0)
                tot["prompt_tokens"] += p
                tot["completion_tokens"] += c
                tot["total_tokens"] += int(getattr(u, "total_tokens", p + c) or (p + c))
                tot["max_prompt_tokens"] = max(tot["max_prompt_tokens"], p)
        return resp

    self._client.chat.completions.create = wrapped


llm.LLMClient.__init__ = _init

# Concurrency is fixed at 8 in PipelineConfig; the shared server gets fewer workers (PLAN 35.5).  Only the worker count changes.
if os.environ.get("S4_CONCURRENCY"):
    from chunktograph import config as _cfg
    for _n in dir(_cfg):
        _c = getattr(_cfg, _n)
        if isinstance(_c, type) and hasattr(_c, "llm_concurrency") and hasattr(_c, "__post_init__"):
            def _wrap(orig):
                def post(self):
                    orig(self)
                    self.llm_concurrency = int(os.environ["S4_CONCURRENCY"])
                return post
            _c.__post_init__ = _wrap(_c.__post_init__)


def main() -> int:
    from chunktograph.cli import app
    t0 = time.monotonic()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rc = 0
    try:
        app(args=sys.argv[1:], standalone_mode=False)
    except SystemExit as exc:
        rc = int(exc.code or 0)
    except Exception as exc:  # noqa: BLE001
        rc = 1
        print(f"command failed: {exc!r}", file=sys.stderr)
    rec = {"command": " ".join(sys.argv[1:2]), "args": [a for a in sys.argv[1:]], "started_utc": started,
           "elapsed_s": round(time.monotonic() - t0, 1), "exit_code": rc, **tot,
           "model": os.environ.get("CHUNKTOGRAPH_LLM_MODEL"), "concurrency": os.environ.get("S4_CONCURRENCY", "default")}
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    print(json.dumps(rec))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
