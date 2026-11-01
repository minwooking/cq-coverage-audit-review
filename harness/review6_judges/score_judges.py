#!/usr/bin/env python3
"""Score the frozen job list with ONE non-Qwen judge endpoint (addendum 26, exploratory).

AI-generated draft; the author must review and test it before the output is used.  Python stdlib only,
so it can run on the GPU host inside tmux/nohup (an SSH drop does not stop it).

For every job in ``jobs.jsonl`` and every repeat 1..R it sends ONE chat/completions request (no
conversation history) with the job's own system and user messages, ``temperature`` 0.0,
``response_format`` json_object, ``max_tokens`` 1024 and the judge's thinking-minimal switch
(see JUDGES).  A malformed / empty / truncated reply is retried with ``max_tokens`` 4096 (the
development harness rule: retry with a larger budget), at most 2 retries.  Nothing is imputed:
a cell that stays invalid is recorded with ``valid=false``.

Repeats are separate passes (all cells of repeat 1, then repeat 2, ...), each pass in a seeded shuffle
(seed + 1000 * repeat) so batch composition differs between repeats.  Concurrency is capped at 3.
Resume: ``(cell_id, repeat)`` pairs with a valid or context-skipped record are not sent again.
The scorer only talks to the endpoint it is given; it never stops or reconfigures a server.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

MAX_WORKERS = 3
SEED = 20260913
TEMPERATURE = 0.0
FIRST_MAX_TOKENS = 1024
RETRY_MAX_TOKENS = 4096
MAX_RETRIES = 2
MAX_MODEL_LEN_DEFAULT = 65536

# thinking-minimal switches, the analogue of the registered judge's `thinking_level=minimal` and of
# the substitute judges' `enable_thinking=false`; they are the only deviation from the registered request.
JUDGES = {
    "gptoss": {"model": "openai/gpt-oss-20b", "extra": {"reasoning_effort": "low"}},
    "glm": {"model": "zai-org/GLM-4.7-Flash", "extra": {"chat_template_kwargs": {"enable_thinking": False}}},
    # test double only
    "fake": {"model": "fake-judge", "extra": {}},
}
CONTEXT_RE = re.compile(r"(maximum context length|context length|context window|too long)", re.I)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def loads_lenient(content: str):
    """strict json.loads first; then the development harness's lenient parser (code fence / prose)."""
    text = (content or "").strip()
    try:
        return json.loads(text), False
    except json.JSONDecodeError:
        pass
    if text.startswith("```"):
        t = text.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
        text = t.strip()
        try:
            return json.loads(text), True
        except json.JSONDecodeError:
            pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start:end + 1]), True
    raise json.JSONDecodeError("no JSON object", text, 0)


def parse_reply(content):
    """-> (J or None, evidence, ok, note, lenient).  J in {0,1,2,3}; anything else is invalid."""
    if content is None or not str(content).strip():
        return None, None, False, "empty content", False
    try:
        obj, lenient = loads_lenient(str(content))
    except Exception:
        return None, None, False, "malformed JSON", False
    if not isinstance(obj, dict) or "score" not in obj:
        return None, None, False, "no score field", lenient
    raw = obj["score"]
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None, obj.get("evidence"), False, "score not numeric", lenient
    j = int(round(float(raw)))
    if j not in (0, 1, 2, 3):
        return None, obj.get("evidence"), False, "score out of range", lenient
    note = "" if float(raw).is_integer() else "non-integer score rounded"
    return j, obj.get("evidence"), True, note, lenient


def post(url: str, body: dict, timeout: float = 900.0):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer none"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def http_error_text(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")[:600]
    except Exception:
        return ""


def one_request(base: str, model: str, extra: dict, job: dict, max_tokens: int):
    body = {"model": model,
            "messages": [{"role": "system", "content": job["system"]}, {"role": "user", "content": job["user"]}],
            "temperature": TEMPERATURE, "max_tokens": max_tokens, "response_format": {"type": "json_object"}}
    body.update(extra)
    delays = (5, 15, 45)
    for k in range(len(delays) + 1):
        try:
            return post(f"{base}/chat/completions", body), None
        except urllib.error.HTTPError as exc:
            text = http_error_text(exc)
            if exc.code == 400 and CONTEXT_RE.search(text):
                return None, {"kind": "context", "code": 400, "body": text}
            if exc.code in (429, 500, 502, 503, 504) and k < len(delays):
                time.sleep(delays[k])
                continue
            return None, {"kind": "http", "code": exc.code, "body": text}
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            if k < len(delays):
                time.sleep(delays[k])
                continue
            return None, {"kind": "net", "body": repr(exc)}
    return None, {"kind": "net", "body": "retries exhausted"}


def score_cell(base: str, judge_id: str, job: dict, repeat: int) -> dict:
    cfg = JUDGES[judge_id]
    t0 = time.monotonic()
    rec = {"judge": judge_id, "model": cfg["model"], "study": job["study"], "cell_id": job["cell_id"],
           "cell_kind": job["cell_kind"], "variant": job["variant"], "cq_id": job["cq_id"],
           "cluster_id": job["cluster_id"], "repeat": repeat, "prompt_sha256": job["prompt_sha256"],
           "started_utc": now(), "attempts": []}
    final = None
    for attempt in range(MAX_RETRIES + 1):
        mt = FIRST_MAX_TOKENS if attempt == 0 else RETRY_MAX_TOKENS
        payload, err = one_request(base, cfg["model"], cfg["extra"], job, mt)
        if err is not None:
            rec["attempts"].append({"max_tokens": mt, "error": err["kind"], "code": err.get("code"),
                                    "body": (err.get("body") or "")[:300]})
            if err["kind"] == "context":
                rec.update(status="context_skip", valid=False, J=None)
                rec["latency_s"] = round(time.monotonic() - t0, 3)
                return rec
            final = err
            continue
        choice = payload["choices"][0]
        msg = choice.get("message", {})
        content = msg.get("content")
        reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
        usage = payload.get("usage") or {}
        j, evidence, ok, note, lenient = parse_reply(content)
        finish = choice.get("finish_reason")
        att = {"max_tokens": mt, "finish_reason": finish, "completion_tokens": usage.get("completion_tokens"),
               "parse_ok": ok, "note": note}
        rec["attempts"].append(att)
        if ok and finish == "length":  # complete JSON but cut off the reply budget: still usable only if parsed
            att["note"] = (note + "; finish=length but JSON parsed").strip("; ")
        rec.update(raw_content=content, finish_reason=finish, reasoning_chars=len(reasoning),
                   reasoning_head=reasoning[:300], prompt_tokens=usage.get("prompt_tokens"),
                   completion_tokens=usage.get("completion_tokens"), evidence=evidence,
                   lenient_parse=lenient, parse_note=note)
        if ok:
            rec.update(status="ok", valid=True, J=j)
            rec["latency_s"] = round(time.monotonic() - t0, 3)
            return rec
        final = {"kind": "invalid", "body": note}
    rec.update(status="invalid", valid=False, J=None, final_error=final)
    rec["latency_s"] = round(time.monotonic() - t0, 3)
    return rec


def load_jobs(path: Path, studies: list[str] | None) -> list[dict]:
    jobs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for j in jobs:
        if sha256_text(j["system"] + "\n\x00\n" + j["user"]) != j["prompt_sha256"]:
            raise SystemExit(f"prompt sha256 mismatch for {j['cell_id']}")
    if studies:
        jobs = [j for j in jobs if j["study"] in studies]
    return jobs


def done_keys(path: Path) -> set[tuple[str, int]]:
    out: set[tuple[str, int]] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("valid") or r.get("status") == "context_skip":
                    out.add((r["cell_id"], r["repeat"]))
    return out


def preflight(base: str, model: str, jobs: list[dict], max_model_len: int) -> dict:
    """Exact prompt token counts from the server tokenizer (/tokenize); no generation is requested."""
    root = base[:-3] if base.endswith("/v1") else base
    counts = {}
    for job in jobs:
        body = {"model": model, "messages": [{"role": "system", "content": job["system"]},
                                             {"role": "user", "content": job["user"]}],
                "add_generation_prompt": True}
        resp = post(f"{root}/tokenize", body, timeout=300)
        counts[job["cell_id"]] = int(resp["count"])
    fits = {c: (n + RETRY_MAX_TOKENS <= max_model_len) for c, n in counts.items()}
    return {"max_model_len": max_model_len, "retry_max_tokens": RETRY_MAX_TOKENS, "prompt_tokens": counts,
            "n_cells": len(counts), "n_over_context": sum(1 for v in fits.values() if not v),
            "cells_over_context": sorted(c for c, v in fits.items() if not v),
            "max_prompt_tokens": max(counts.values()), "sum_prompt_tokens": sum(counts.values())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jobs", type=Path, required=True)
    ap.add_argument("--judge", choices=sorted(JUDGES), required=True)
    ap.add_argument("--endpoint", required=True, help="OpenAI-compatible base URL ending in /v1")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--studies", default="", help="comma list: holdout_subgraph,holdout_control,dev")
    ap.add_argument("--max-model-len", type=int, default=MAX_MODEL_LEN_DEFAULT)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--preflight-only", action="store_true")
    ap.add_argument("--confirm-addendum26-frozen", action="store_true")
    ap.add_argument("--progress", type=Path, default=None)
    a = ap.parse_args(argv)
    if not 1 <= a.workers <= MAX_WORKERS:
        raise SystemExit(f"REFUSING: --workers must be 1..{MAX_WORKERS}")
    if a.seed != SEED:
        raise SystemExit(f"REFUSING: seed must be {SEED}")
    studies = [s for s in a.studies.split(",") if s]
    jobs = load_jobs(a.jobs, studies or None)
    cfg = JUDGES[a.judge]
    base = a.endpoint.rstrip("/")
    pre_path = a.out.with_name(a.out.stem + "_preflight.json")

    if a.preflight_only:
        pre = preflight(base, cfg["model"], jobs, a.max_model_len)
        pre_path.write_text(json.dumps(pre, indent=1), encoding="utf-8")
        print(json.dumps({k: v for k, v in pre.items() if k != "prompt_tokens"}))
        return 0
    if not a.confirm_addendum26_frozen and a.judge != "fake":
        raise SystemExit("REFUSING: pass --confirm-addendum26-frozen only after the PLAN.md freeze commit")

    pre = preflight(base, cfg["model"], jobs, a.max_model_len)
    pre_path.write_text(json.dumps(pre, indent=1), encoding="utf-8")
    over = set(pre["cells_over_context"])
    todo_jobs = [j for j in jobs if j["cell_id"] not in over]
    lock = threading.Lock()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    progress = a.progress or a.out.with_name(a.out.stem + "_progress.log")
    done = done_keys(a.out)
    total = len(todo_jobs) * a.repeats
    state = {"calls": len([k for k in done if k[0] not in over]), "t0": time.monotonic(), "marks": set(),
             "invalid": 0, "ctx": 0, "tokens_in": 0, "tokens_out": 0}

    def log(msg: str):
        line = f"{now()} {a.judge} {msg}"
        with progress.open("a", encoding="utf-8") as pf:
            pf.write(line + "\n")
        print(line, flush=True)

    # cells that do not fit: one skip record per (cell, repeat 0), so the analysis can list them
    with a.out.open("a", encoding="utf-8") as fh:
        for cid in sorted(over):
            if (cid, 0) not in done:
                job = next(j for j in jobs if j["cell_id"] == cid)
                fh.write(json.dumps({"judge": a.judge, "model": cfg["model"], "study": job["study"],
                                     "cell_id": cid, "cell_kind": job["cell_kind"], "variant": job["variant"],
                                     "cq_id": job["cq_id"], "cluster_id": job["cluster_id"], "repeat": 0,
                                     "status": "context_skip", "valid": False, "J": None,
                                     "prompt_tokens": pre["prompt_tokens"][cid],
                                     "note": "prompt + retry budget exceeds max_model_len (preflight)"}) + "\n")
    log(f"start cells={len(todo_jobs)} (over-context skipped {len(over)}) repeats={a.repeats} planned_calls={total} "
        f"already_done={state['calls']} workers={a.workers}")

    def after(rec: dict, fh):
        with lock:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            state["calls"] += 1
            state["tokens_in"] += rec.get("prompt_tokens") or 0
            state["tokens_out"] += rec.get("completion_tokens") or 0
            if rec["status"] == "invalid":
                state["invalid"] += 1
            if rec["status"] == "context_skip":
                state["ctx"] += 1
            for pct in (25, 50, 75, 100):
                if state["calls"] * 100 >= total * pct and pct not in state["marks"]:
                    state["marks"].add(pct)
                    log(f"CHECKPOINT {pct}% calls={state['calls']}/{total} invalid={state['invalid']} "
                        f"context_skip={state['ctx']} prompt_tokens_this_run={state['tokens_in']} "
                        f"completion_tokens_this_run={state['tokens_out']} "
                        f"elapsed_s={round(time.monotonic() - state['t0'])}")

    with a.out.open("a", encoding="utf-8") as fh:
        for r in range(1, a.repeats + 1):
            pending = [j for j in todo_jobs if (j["cell_id"], r) not in done]
            random.Random(a.seed + 1000 * r).shuffle(pending)
            if not pending:
                continue
            log(f"repeat {r}: {len(pending)} cells")
            with ThreadPoolExecutor(max_workers=a.workers) as pool:
                futs = [pool.submit(score_cell, base, a.judge, j, r) for j in pending]
                for f in as_completed(futs):
                    after(f.result(), fh)
            log(f"repeat {r} done")
    log(f"DONE calls={state['calls']} invalid={state['invalid']} context_skip={state['ctx']} "
        f"prompt_tokens_this_run={state['tokens_in']} completion_tokens_this_run={state['tokens_out']} "
        f"elapsed_s={round(time.monotonic() - state['t0'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
