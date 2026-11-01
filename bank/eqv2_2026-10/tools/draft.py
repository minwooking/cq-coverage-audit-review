#!/usr/bin/env python3
# AI-generated draft: a person must review and test it before use.  (Addendum 47, C2.)
"""Blind question drafting for bank eqv2 (addendum 47, 47.3).

The MODEL writes ONLY the question sentence; grounding, expected_answer and the ASK query
are built by this script from the frozen snapshot via common.build_facts (the expansion
builder's grammar, re-implemented; that builder is not imported -- its module-level code
runs on import).  Requests carry no tools (asserted in code); temperature 0, max_tokens
256, thinking off, JSON output {"question": "..."}.

Endpoint and model id come ONLY from the environment or the command line
(EQV2_DRAFT_ENDPOINT / --endpoint, EQV2_DRAFT_MODEL / --model); nothing that identifies a
host, address or port is ever written to disk.  Requests go to one OpenAI-compatible
chat/completions route through a bounded in-flight window (default 8, hard cap 16); the
fallback route (a separate engine, in-flight 4) is selected with --route fallback and is
tried only when the primary is unhealthy.  If neither is available the run stops and
reports.

A sys.audit hook records every open/listdir/scandir to logs/blind_open_log_b{k}.jsonl and
raises on any forbidden path (blind_patterns.json) -- the drafting process never sees the
renderings, graphs, judge records, manifests, eligibility or annotation outputs.  Call
logs (prompt, response, latency, model id -- never host or port) go to
logs/draft_calls_b{k}.jsonl.  Resume: completed cq_ids already present in the output
draft file are skipped; failed calls retry with capped exponential backoff.

THIS FILE PERFORMS NO NETWORK CALL WHEN TESTED: the client is injectable and the real
client is constructed only when --execute is passed together with an endpoint.

Usage (execution happens in P3, after C2, not here):
    EQV2_DRAFT_ENDPOINT=... EQV2_DRAFT_MODEL=... python3 draft.py --batch b1 --execute

Batch 2 (BATCH2_PROCEDURE.md): the same pinned prompt hash is asserted, the items come
from batch2_plan.json, output is draft_b2.jsonl, and the logs go to the directory in
EQV2_LOG_DIR (bank/eqv2_2026-10/logs_b2).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import common
from common import (ACCESS, BANK, CATEGORIES, FRAME_SUMMARY, LOG_DIR, SEED, Snapshot,
                    build_facts, build_prompt, install_blind_hooks, now_iso)

HERE = common.TOOLS
MAX_INFLIGHT_DEFAULT = 8
MAX_INFLIGHT_HARD = 16
MAX_TOKENS = 256
RETRIES = 4
BACKOFF_BASE_S = 2.0
BACKOFF_CAP_S = 16.0

_draft_lock = threading.Lock()


class DraftRefused(RuntimeError):
    pass


class DraftCallError(RuntimeError):
    def __init__(self, cause: str, retry_after: float | None = None):
        super().__init__(cause)
        self.retry_after = retry_after


# ---------------------------------------------------------------- clients
def make_request_body(prompt: list[dict], model: str) -> dict:
    body = {"model": model, "messages": prompt, "temperature": 0, "max_tokens": MAX_TOKENS,
            "response_format": {"type": "json_object"}, "enable_thinking": False}
    assert "tools" not in body and "functions" not in body  # 47.3: no tools in the request
    return body


class MockClient:
    """Test-only: returns a deterministic question built from the prompt's term line."""

    def __init__(self, answers: dict[str, str] | None = None):
        self.answers = answers or {}
        self.calls = 0

    def complete(self, body: dict) -> tuple[str, float]:
        self.calls += 1
        user = body["messages"][1]["content"]
        q = self.answers.get(user, "")
        if not q:
            term = user.split("Term: ", 1)[1].split()[0] if "Term: " in user else "brick:Unknown"
            q = f"What is {term}?"
        return json.dumps({"question": q}), 0.0


class HttpChatClient:
    """One route: base URL + model id live only in this object (env/CLI), never on disk."""

    def __init__(self, endpoint: str, model: str, in_flight: int, label: str = "primary"):
        if in_flight > MAX_INFLIGHT_HARD:
            raise DraftRefused(f"in-flight {in_flight} exceeds hard cap {MAX_INFLIGHT_HARD}")
        self._url = endpoint.rstrip("/") + "/chat/completions"
        self.model = model
        self.label = label
        self._sem = threading.BoundedSemaphore(in_flight)

    def complete(self, body: dict) -> tuple[str, float]:
        payload = json.dumps(body).encode()
        t0 = time.monotonic()
        with self._sem:
            req = urllib.request.Request(self._url, data=payload,
                                         headers={"Content-Type": "application/json"},
                                         method="POST")
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    data = json.loads(resp.read().decode())
            except urllib.error.HTTPError as exc:
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                raise DraftCallError(f"http {exc.code}", retry_after=float(retry_after) if retry_after else None) from exc
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                raise DraftCallError(f"{type(exc).__name__}") from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise DraftCallError("malformed response envelope") from exc
        return content, time.monotonic() - t0


# ---------------------------------------------------------------- planning
def plan_items(frame_summary: dict, batch: str) -> list[dict]:
    """Deterministic draft order: the shared cq_id mapping in common.frame_items
    (canonical category order, frame order within a category).  b2 is read from
    batch2_plan.json (written by plan_b2.py, cross-checked against the frame tail);
    this tool never reads the batch-size file nor any b1 outcome file."""
    if batch not in ("b1", "b2"):
        raise DraftRefused(f"unknown batch {batch!r}")
    return common.frame_items(frame_summary, batch)


# ---------------------------------------------------------------- core loop
def log_call(log_path: Path, item: dict, prompt: list[dict], response: str,
             latency: float, model: str, ok: bool, attempt: int, error: str = "") -> None:
    """Call log: prompt, response, latency, model id. NEVER host, address or port."""
    rec = {"ts": now_iso(), "cq_id": item["cq_id"], "category": item["category"],
           "term": item["term"], "frame_rank": item["frame_rank"], "prompt": prompt,
           "response": response, "latency_s": round(latency, 3), "model_id": model,
           "ok": ok, "attempt": attempt, "error": error or None}
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with _draft_lock, log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def draft_one(client, item: dict, snap: Snapshot) -> dict:
    """One item -> draft row. Model text goes through a shape check before the row is
    built so a bad generation retries instead of polluting the batch."""
    facts = build_facts(snap, item["term"], item["category"], item["frame_rank"])
    # Same `kind` for the ASK body and the prompt frame (common.build_facts derives it
    # from the rank and the snapshot children); a caller-supplied kind is ignored.
    prompt = build_prompt(item["category"], item["frame_rank"], facts, item["term"],
                          facts.get("kind", 0))
    last_err = ""
    for attempt in range(1, RETRIES + 1):
        body = make_request_body(prompt, getattr(client, "model", "mock"))
        try:
            content, latency = client.complete(body)
            q = parse_question(content)
            if common.word_count(q) > 30 or q.count("?") != 1:
                last_err = f"shape fail: {q!r}"
                continue
            row = {"cq_id": item["cq_id"], "category": item["category"],
                   "question": q, "grounding": facts["grounding"],
                   "expected_answer": facts["expected_answer"], "ask": facts["ask"],
                   "ask_expressible": facts["ask_expressible"], "cluster_id": item["cq_id"],
                   "batch": item["batch"], "frame_rank": item["frame_rank"],
                   "draft_model": getattr(client, "model", "mock"),
                   "prompt_sha256": common.prompt_sha256(),
                   "status": "draft"}
            log_call(_CALL_LOG, item, prompt, content, latency,
                     getattr(client, "model", "mock"), True, attempt)
            return row
        except DraftCallError as exc:
            wait = min(BACKOFF_CAP_S, BACKOFF_BASE_S * (2 ** (attempt - 1)))
            if exc.retry_after:
                wait = max(wait, min(300.0, exc.retry_after))
            time.sleep(wait)
            last_err = str(exc)
            log_call(_CALL_LOG, item, prompt, "", wait, getattr(client, "model", "mock"),
                     False, attempt, last_err)
    raise DraftCallError(f"draft failed for {item['cq_id']}: {last_err}")


def parse_question(content: str) -> str:
    try:
        obj = json.loads(content)
    except json.JSONDecodeError as exc:
        raise DraftCallError(f"not JSON: {exc}") from exc
    q = obj.get("question") if isinstance(obj, dict) else None
    if not isinstance(q, str) or not q.strip():
        raise DraftCallError("question key missing or empty")
    return q.strip()


_CALL_LOG = LOG_DIR / "draft_calls_b1.jsonl"


def run_draft(items: list[dict], snap: Snapshot, client, out_path: Path,
              call_log: Path, workers: int = 4, progress_every: int = 25) -> dict:
    global _CALL_LOG
    _CALL_LOG = call_log
    done = set()
    if out_path.exists():
        with out_path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    done.add(json.loads(line)["cq_id"])
                except (KeyError, json.JSONDecodeError):
                    continue
    todo = [it for it in items if it["cq_id"] not in done]
    summary = {"requested": len(todo), "resumed_skipped": len(done), "failed": []}
    lock = threading.Lock()
    with out_path.open("a", encoding="utf-8") as out, ThreadPoolExecutor(max_workers=workers) as pool:

        def work(item):
            try:
                row = draft_one(client, item, snap)
                with lock:  # `out` stays open by the outer context -- threads must not close it
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
                return row["cq_id"], None
            except DraftCallError as exc:
                return item["cq_id"], str(exc)

        for n, (cid, err) in enumerate(pool.map(work, todo), 1):
            if err:
                summary["failed"].append({"cq_id": cid, "error": err})
            if n % progress_every == 0:
                print(f"[draft] {n}/{len(todo)} done, failed={len(summary['failed'])}",
                      file=sys.stderr)
    return summary


# ---------------------------------------------------------------- cli
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--batch", default="b1", choices=["b1", "b2"])
    ap.add_argument("--execute", action="store_true", help="make real model calls (P3 only)")
    ap.add_argument("--endpoint", default=None, help="base URL; env EQV2_DRAFT_ENDPOINT")
    ap.add_argument("--model", default=None, help="model id; env EQV2_DRAFT_MODEL")
    ap.add_argument("--route", default="primary", choices=["primary", "fallback"],
                    help="fallback route = the other engine, in-flight 4")
    ap.add_argument("--in-flight", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--frame", default=str(FRAME_SUMMARY))
    ap.add_argument("--out", default=None, help="draft rows jsonl (default bank/draft_b{k}.jsonl)")
    ap.add_argument("--no-hook", action="store_true")
    args = ap.parse_args(argv)

    if not args.no_hook:
        install_blind_hooks(f"blind_open_log_{args.batch}.jsonl")
    summary_path = Path(args.frame)
    frame = json.loads(summary_path.read_text(encoding="utf-8"))
    # 47.A1: frame_summary.json is committed and never rewritten, so after the single
    # prompt revision the pinned hash lives in prompt_sha256_r2.json (common.expected_
    # prompt_sha256 reads the r2 file first, then the frame file -- round-1 runs).
    assert common.prompt_sha256() == common.expected_prompt_sha256(), \
        "prompt hash drifted from the pinned template (prompt_sha256_r2.json / frame_summary)"
    items = plan_items(frame, args.batch)

    if args.execute:
        endpoint = args.endpoint or os.environ.get("EQV2_DRAFT_ENDPOINT", "")
        model = args.model or os.environ.get("EQV2_DRAFT_MODEL", "")
        if not endpoint or not model:
            raise DraftRefused("no endpoint/model configured -- both routes unavailable: stop and report (47.3)")
        if "://" not in endpoint:
            raise DraftRefused("endpoint must be an absolute http(s) base URL")
        inflight = args.in_flight or (4 if args.route == "fallback" else MAX_INFLIGHT_DEFAULT)
        client = HttpChatClient(endpoint, model, inflight, args.route)
    else:
        client = MockClient()

    out_path = Path(args.out or str(BANK / f"draft_{args.batch}.jsonl"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    snap = Snapshot()
    result = run_draft(items, snap, client, out_path,
                       LOG_DIR / f"draft_calls_{args.batch}.jsonl", workers=args.workers)
    print(json.dumps({"batch": args.batch, "executed": args.execute, **{k: v for k, v in result.items() if k != "failed"},
                      "failed": len(result["failed"])}, ensure_ascii=False))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
