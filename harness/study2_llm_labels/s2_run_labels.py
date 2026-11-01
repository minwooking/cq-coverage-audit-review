#!/usr/bin/env python3
"""Runner of addendum 32 (Study 2): persona x seed evidence labels on the retrieval views.  AI-generated; review and test
before use.  Python stdlib + the repository's run_ensemble / run_rater / rater_luna modules (imported, not edited).

Per cell and model: 5 personas x 5 seeds = 25 requests (temperature 0.7, seed parameter 1..5), a fresh request each.  System
prompt = persona preamble + NEW_BASE (s2_personas); user message = rater_luna.user_message(view, cell) with the retrieval
view of s2_views (PLAN.md 32.4-32.5).  The rating is R_raw (no floor).  One record per call, appended to
raw/<model>_<stage>.jsonl with started_at_utc and latency_s (the timing record); no view text, address or key in a record.
Resumable: a slot with a terminal record (ok / invalid / context_skip) is not sent again.  Stop rules as addendum 28/30.

  --preflight  : tokenizer preflight (POST /tokenize, no generation) of every cell's prompt -> raw/preflight_<model>_<stage>.json
Endpoints come from --endpoint (never written to a file); keys from the environment (never printed).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path
from queue import Empty, Queue

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
sys.path.insert(0, str(HERE))

_spec = importlib.util.spec_from_file_location("r10_run_ensemble", HARNESS / "review10_llm_labels" / "run_ensemble.py")
RE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(RE)
RR, rl, rh = RE.RR, RE.rl, RE.rh
import s2_cells as C  # noqa: E402
import s2_personas as PS  # noqa: E402

RAW = HERE / "raw"
SLOTS = RE.SLOTS
TERMINAL = RE.TERMINAL
STOP, STOP_REASON, DEADLINE = RE.STOP, RE.STOP_REASON, RE.DEADLINE
WINDOW = RE.WINDOW
RETRY_BUDGET = 4096
PERSONA_MARGIN = 400            # tokens: the longest persona preamble over the preflight's persona


def raw_path(model: str, stage: str) -> Path:
    base = Path(os.environ.get("S2_RAW_DIR", str(RAW)))       # tests only
    return base / f"{model}_{stage}.jsonl"


def preflight_path(model: str, stage: str) -> Path:
    return raw_path(model, stage).with_name(f"preflight_{model}_{stage}.json")


def user_for(row: dict, text: str) -> str:
    return rl.user_message(text, {"catKo": row["catKo"], "q": row["q"], "qko": row.get("qko", "")})


def slot_record(st, row: dict, text: str, persona: str, seed: int, stage: str) -> dict:
    system = PS.SYSTEM[persona]
    user = user_for(row, text)
    first, retry = st.mcfg.get("max_tokens", (RR.MAX_TOKENS_FIRST, RR.MAX_TOKENS_RETRY))
    t0 = time.time()
    rec = {"cell_id": row["cell_id"], "stage": stage, "persona": persona, "seed": seed, "model": st.alias,
           "cell_kind": row["cell_kind"], "view_sha256": row["view_sha256"], "started_at_utc": RE.now()}
    tok_in = tok_out = 0
    for k in range(RE.MAX_INVALID_RETRIES + 1):
        payload, err, _ = RE.post_once(st, system, user, first if k == 0 else retry, seed)
        if err is not None:
            if err["kind"] == "context":
                rec.update(status="context_skip", valid=False, attempts=k + 1)
            elif err["kind"] == "stopped":
                rec.update(status="stopped", valid=False, attempts=k + 1)
            else:
                rec.update(status="error", valid=False, attempts=k + 1, error=err["kind"], code=err.get("code"),
                           error_body=(err.get("body") or "")[:200])
            break
        choice = (payload.get("choices") or [{}])[0]
        usage = payload.get("usage") or {}
        tok_in += usage.get("prompt_tokens") or 0
        tok_out += usage.get("completion_tokens") or 0
        content = (choice.get("message") or {}).get("content") or ""
        parsed, perr = rl.parse_content(content)
        rec.update(finish_reason=choice.get("finish_reason"), attempts=k + 1)
        if parsed is not None:
            fin = RR.finalize(parsed, text)
            rec.update(valid=True, status="ok", S_raw=fin["S_raw"], R_raw=fin["R_raw"], span=fin["span"],
                       note=(fin["note"] or "")[:400], span_verbatim=fin["span_verbatim"], S_final=fin["S_final"],
                       seed_sent=st.send_seed)
            break
        rec.update(valid=False, status="invalid", error=f"unparsed: {perr}", raw_head=content[:200], seed_sent=st.send_seed)
    rec.update(prompt_tokens=tok_in, completion_tokens=tok_out, latency_s=round(time.time() - t0, 3))
    return rec


def cells_for(stage: str) -> tuple[list[dict], list[str]]:
    rows = C.load_manifest(stage)
    prim = [r["cell_id"] for r in rows if r["cell_kind"] == "primary"]
    ctrl = [r["cell_id"] for r in rows if r["cell_kind"] != "primary"]
    if stage == "stage2":
        ids = C.order(prim, first_variants="AB") + C.order(ctrl)
    else:
        ids = C.order(prim) + C.order(ctrl)
    return rows, ids


def tokenize_count(base: str, model_id: str, system: str, user: str, key: str) -> int:
    root = base[:-3] if base.endswith("/v1") else base
    body = {"model": model_id, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    req = urllib.request.Request(f"{root}/tokenize", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        d = json.loads(r.read())
    return int(d["count"])


def do_preflight(a, st, rows: list[dict]) -> int:
    out = {}
    for r in rows:
        text = C.material_for(r)
        out[r["cell_id"]] = tokenize_count(st.base, st.mcfg["id"], PS.SYSTEM["domain"], user_for(r, text), st.key)
    path = preflight_path(st.alias, a.stage)
    path.parent.mkdir(parents=True, exist_ok=True)
    over = [c for c, n in out.items() if n + PERSONA_MARGIN + RETRY_BUDGET > WINDOW[st.alias]]
    path.write_text(json.dumps({"model": st.alias, "stage": a.stage, "window": WINDOW[st.alias], "prompt_tokens": out,
                                "max_prompt_tokens": max(out.values()), "over_context": over}, indent=1), encoding="utf-8")
    print(json.dumps({"cells": len(out), "max_prompt_tokens": max(out.values()), "over_context": len(over)}))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, choices=["glm", "gptoss", "qwen", "fake"])
    ap.add_argument("--stage", required=True, choices=["stage1", "stage2", "preserved"])
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--preflight", action="store_true")
    ap.add_argument("--pilot", action="store_true", help="test only: first 2 cells x 5 personas x seed 1")
    ap.add_argument("--limit-cells", type=int, default=0)
    ap.add_argument("--max-wall-s", type=float, default=0)
    ap.add_argument("--token-budget", type=int, default=0)
    ap.add_argument("--progress", default=None)
    ap.add_argument("--report-every-s", type=float, default=900)
    ap.add_argument("--confirm-addendum32-frozen", action="store_true")
    a = ap.parse_args(argv)
    alias = a.model
    mcfg = dict(RR.MODELS[RE.MODEL_KEYS[alias]])
    if alias in ("qwen", "fake"):
        mcfg["send_seed"] = True
    if not 1 <= a.workers <= RE.MAX_WORKERS:
        raise SystemExit(f"REFUSING: --workers must be 1..{RE.MAX_WORKERS}")
    if alias != "fake" and not a.confirm_addendum32_frozen and not a.preflight:
        raise SystemExit("REFUSING: pass --confirm-addendum32-frozen only after the PLAN.md freeze commit")
    if mcfg["route"] == "<internal-proxy>" and not a.token_budget and not a.preflight:
        raise SystemExit("REFUSING: --token-budget is required for the <internal-proxy> route")
    os.environ.setdefault(f"R10_ENDPOINT_{alias.upper()}", a.endpoint)
    ns = argparse.Namespace(endpoint=a.endpoint, gate=a.gate, workers=a.workers)
    st = RE.State(ns, mcfg, alias)
    st.recent = []
    rows, ids = cells_for(a.stage)
    cmap = {r["cell_id"]: r for r in rows}
    if a.preflight:
        if alias == "qwen":
            raise SystemExit("no tokenizer endpoint for the <internal-proxy> route; estimate is used")
        return do_preflight(a, st, rows)
    pre = {}
    pp = preflight_path(alias, a.stage)
    if alias in ("glm", "gptoss"):
        if not pp.exists():
            raise SystemExit("run --preflight first (PLAN.md 32.4 rule F)")
        pre = json.loads(pp.read_text(encoding="utf-8"))["prompt_tokens"]
    if a.pilot:
        ids = ids[:2]
    elif a.limit_cells:
        ids = ids[:a.limit_cells]
    out = raw_path(alias, a.stage)
    out.parent.mkdir(parents=True, exist_ok=True)
    prior = RE.read_jsonl(out)
    st.tok_prior = sum((r.get("prompt_tokens") or 0) + (r.get("completion_tokens") or 0) for r in prior)
    done = {(r["cell_id"], r.get("persona"), r.get("seed")) for r in prior if r.get("status") in TERMINAL}
    window = WINDOW[alias]
    first_tok, retry_tok = mcfg.get("max_tokens", (RR.MAX_TOKENS_FIRST, RR.MAX_TOKENS_RETRY))
    slots = [(p, s) for p, s in SLOTS if not a.pilot or s == 1]
    jobs, skipped = [], []
    for cid in ids:
        r = cmap[cid]
        n_tok = pre.get(cid) if pre else int(r["est_input_tokens"] * RE.EST_TO_ACTUAL) + 1200
        if n_tok + PERSONA_MARGIN + retry_tok > window if pre else n_tok + retry_tok > window:
            skipped.append(cid)
            continue
        left = [(p, s) for p, s in slots if (cid, p, s) not in done]
        if left:
            jobs.append((cid, left))
    with out.open("a", encoding="utf-8") as fh:
        for cid in skipped:
            if (cid, None, None) not in done:
                fh.write(json.dumps({"cell_id": cid, "stage": a.stage, "persona": None, "seed": None, "model": alias,
                                     "status": "context_skip", "valid": False,
                                     "note": "prompt tokens (preflight) + persona margin + retry budget exceed the model window; not sent"}) + "\n")
    tiers_state = {a.stage: {"done": len([i for i in ids if i not in skipped]) - len(jobs), "total": len(ids) - len(skipped)}}
    st.planned = sum(len(l) for _, l in jobs)
    print(f"model {alias} {a.stage} pending_cells {len(jobs)} pending_calls {st.planned} skipped_context {len(skipped)}",
          file=sys.stderr, flush=True)
    q: Queue = Queue()
    for item in jobs:
        q.put(item)
    progress = Path(a.progress) if a.progress else None
    t_start, started = time.time(), RE.now()
    stop_report = threading.Event()
    wl = RE._write_lock

    def append_progress(line: str):
        if progress is not None:
            with wl:
                with progress.open("a", encoding="utf-8") as pf:
                    pf.write(line + "\n")

    marks: set[int] = set()

    def checkpoint():
        pct = int(100 * st.calls_done / max(1, st.planned))
        for m in (25, 50, 75, 100):
            if pct >= m and m not in marks:
                marks.add(m)
                append_progress(RE.progress_line(st, tiers_state).replace("[review10]", f"[study2 {a.stage} {m}%]"))

    def reporter():
        while not stop_report.wait(a.report_every_s):
            append_progress(RE.progress_line(st, tiers_state).replace("[review10]", f"[study2 {a.stage}]"))

    def worker():
        while not STOP.is_set():
            if a.max_wall_s and time.time() - t_start > a.max_wall_s:
                DEADLINE.set()
                return
            try:
                cid, left = q.get_nowait()
            except Empty:
                return
            row = cmap[cid]
            need = 0
            if a.token_budget:
                per_call = int(row["est_input_tokens"] * RE.EST_TO_ACTUAL) + 1200 + first_tok // 2
                need = per_call * len(left)
                with st.lock:
                    if st.tok_prior + st.tok_in + st.tok_out + st.reserved + need > a.token_budget:
                        STOP.set()
                        STOP_REASON.append(f"token budget cap {a.token_budget}")
                        return
                    st.reserved += need
            finished = False
            try:
                text = C.material_for(row)
                for persona, seed in left:
                    if STOP.is_set():
                        return
                    rec = slot_record(st, row, text, persona, seed, a.stage)
                    if rec["status"] == "stopped":
                        return
                    RE.write_rec(st, out, rec)
                    checkpoint()
                    if rec["status"] == "context_skip":
                        break
                else:
                    finished = True
            finally:
                if need:
                    with st.lock:
                        st.reserved -= need
            if finished:
                with st.lock:
                    tiers_state[a.stage]["done"] += 1

    append_progress(f"[study2 {a.stage}] {RE.now()} model={alias} start: {len(jobs)} cells / {st.planned} calls pending, workers={a.workers}")
    threads = [threading.Thread(target=worker, daemon=True) for _ in range(a.workers)]
    rt = threading.Thread(target=reporter, daemon=True)
    for t in threads:
        t.start()
    rt.start()
    for t in threads:
        t.join()
    stop_report.set()
    append_progress(RE.progress_line(st, tiers_state, final=True).replace("[review10]", f"[study2 {a.stage}]"))
    meta = {"model": alias, "stage": a.stage, "pilot": bool(a.pilot), "temperature": RE.TEMPERATURE, "seed_sent": st.send_seed,
            "seed_note": st.seed_note, "workers": a.workers, "gate": bool(a.gate), "cells_skipped_context": len(skipped),
            "calls": st.calls_done, "valid_calls": st.valid, "prompt_tokens": st.tok_in, "completion_tokens": st.tok_out,
            "started_utc": started, "finished_utc": RE.now(), "wall_s": round(time.time() - t_start, 1),
            "deadline_hit": DEADLINE.is_set(), "stop_reasons": list(STOP_REASON),
            "new_base_sha256": PS.NEW_BASE_SHA256, "system_sha256": PS.SYSTEM_SHA256}
    with out.with_name(f"{alias}_{a.stage}.meta.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(meta) + "\n")
    print(json.dumps({k: v for k, v in meta.items() if k not in ("system_sha256",)}), file=sys.stderr, flush=True)
    return 1 if STOP_REASON else 0


if __name__ == "__main__":
    sys.exit(main())
