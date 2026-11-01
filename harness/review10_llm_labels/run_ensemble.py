#!/usr/bin/env python3
"""Runner of addendum 30 (review10_llm_labels): persona x seed evidence labels per cell.  AI-generated; review and
test before use.  Python stdlib + the repository's run_rater / rater_luna / run_holdout modules (imported, not edited).

Per cell and model: 5 personas x 5 seeds = 25 requests (temperature 0.7, seed parameter 1..5), one request each, no
history.  The system prompt is PREAMBLE[persona] + BASE (personas.py); the user message is the one of addendum 28.
Resumable: a slot with a terminal record (ok / invalid / context_skip) is not sent again; HTTP / network failures are not
terminal.  Cells are processed in the seeded order of cells.order(); one worker takes a whole cell (so the five seeds of a
(cell, persona) pair follow each other and the server prefix cache helps); at most 3 workers per endpoint.

It never opens site_key*, labeling_sheet_key*, human_labels_export*, views_for_raters.zip, .env or sealed files, and it
never reads a human label.  Endpoint addresses and keys come from the command line / environment and are written to no
file.  A record holds: cell_id, persona, seed, model alias, S_raw, R_raw, span, note (400 chars), span_verbatim, S_final,
R_floor, status, finish_reason, token counts, latency -- no view text, no address, no key.

Amendment A1: --tiers runs several cell sets from one shared queue in priority order (1, 2a, 2b, 3a-3e); each tier has its
own raw file (raw/<model>_t<tier>.jsonl; the internal second-domain tier 3d goes to raw_internal/, which is git-ignored).
Stop rules (as addendum 28): HTTP 402 / 403, HTTP 429 with Retry-After > 300 s, or 5 consecutive failed calls stop the run;
a wall-clock cap (--max-wall-s) or a token budget (--token-budget) stops the start of new cells.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty, Queue

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HARNESS / "review6_raters"))
sys.path.insert(0, str(HARNESS / "llm_rater_luna_2026-10-15"))
sys.path.insert(0, str(HARNESS))
import cells as C  # noqa: E402
import personas as PS  # noqa: E402
import rater_luna as rl  # noqa: E402
import run_holdout as rh  # noqa: E402
import run_rater as RR  # noqa: E402  (Gate, http_post, build_body, finalize, material_for, est_for, MODELS)

SEEDS = (1, 2, 3, 4, 5)
TEMPERATURE = 0.7
MAX_WORKERS = 32               # amendment A1 (PLAN 30.12): up to 32 per endpoint, chosen by a throughput probe
MAX_INVALID_RETRIES = 2
HTTP_TIMEOUT_S = 900
EST_TO_ACTUAL = 1.15            # chars/4 -> tokens, as seen for Qwen in addendum 28
CONSECUTIVE_FAIL_STOP = 5
TERMINAL = ("ok", "invalid", "context_skip")
SLOTS = [(p, s) for p in PS.PERSONAS for s in SEEDS]      # 25, fixed order
CONTEXT_RE = RR.CONTEXT_RE
SEED_REJECT_RE = re.compile(r"\bseed\b", re.I)

# alias -> (run_rater model key, window, role)
MODEL_KEYS = {"glm": "glm", "gptoss": "gptoss", "qwen": "qwen", "fake": "fake"}
WINDOW = {"glm": 65536, "gptoss": 65536, "qwen": 262144, "fake": 65536}

_write_lock = threading.Lock()
STOP = RR.STOP
STOP_REASON = RR.STOP_REASON
DEADLINE = threading.Event()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path: Path) -> list[dict]:
    return RR.read_jsonl(path)


class Gate2(RR.Gate):
    """Courtesy gate of addendum 28 with a slack of 2 requests for the jitter between this runner's own in-flight count and the
    server's running+waiting count (needed at high concurrency; others = running + waiting - own in-flight - slack)."""
    SLACK = 2

    def refresh(self):
        import urllib.request
        try:
            with urllib.request.urlopen(f"{self.root}/metrics", timeout=10) as r:
                txt = r.read().decode("utf-8", "replace")
            tot = sum(float(v) for _, v in RR.METRIC_RE.findall(txt))
            self.others = max(0, int(round(tot)) - self.inflight - self.SLACK)
        except Exception:
            self.others = 0
        self.last = time.time()


class State:
    def __init__(self, a, mcfg, alias):
        self.a, self.mcfg, self.alias = a, mcfg, alias
        base = a.endpoint or os.environ.get(f"R10_ENDPOINT_{alias.upper()}")
        if not base:
            raise SystemExit("--endpoint (or R10_ENDPOINT_<ALIAS>) is required")
        self.base = base.rstrip("/")
        self.key = os.environ.get(rh.API_KEY_ENV) or ("<internal-proxy>-local" if mcfg["route"] == "<internal-proxy>" else "none")
        self.send_seed = bool(mcfg["send_seed"])
        self.seed_note = None
        self.gate = Gate2(self.base, bool(a.gate))
        self.fail_streak = 0
        self.calls_done = 0
        self.valid = 0
        self.planned = 0
        self.t0 = time.time()
        self.marks: set[float] = set()
        self.tok_in = 0
        self.tok_out = 0
        self.tok_prior = 0
        self.reserved = 0
        self.lock = threading.Lock()


def post_once(st: State, system: str, user: str, max_tokens: int, seed: int):
    mcfg = st.mcfg
    spec = {"temperature": TEMPERATURE, "seed": seed}
    delays = (5, 15, 45)
    k = r429 = 0
    meta = {"max_tokens": max_tokens}
    while True:
        if STOP.is_set():
            return None, {"kind": "stopped"}, meta
        local = dict(mcfg)
        local["send_seed"] = st.send_seed
        body = RR.build_body(local, spec, system, user, max_tokens, True)
        if mcfg["route"] == "<internal-proxy>":
            rh._pace_judge_request()
        st.gate.enter()
        try:
            return RR.http_post(f"{st.base}/chat/completions", body, st.key, HTTP_TIMEOUT_S), None, meta
        except urllib.error.HTTPError as exc:
            try:
                text = exc.read().decode("utf-8", "replace")[:600]
            except Exception:
                text = ""
            if exc.code in (402, 403):
                STOP.set(); STOP_REASON.append(f"HTTP {exc.code}")
                return None, {"kind": "http", "code": exc.code, "body": text}, meta
            if exc.code == 400:
                if CONTEXT_RE.search(text):
                    return None, {"kind": "context", "code": 400, "body": text}, meta
                if st.send_seed and SEED_REJECT_RE.search(text):
                    st.send_seed = False
                    st.seed_note = "seed parameter rejected by the endpoint (HTTP 400); omitted for the rest of the run"
                    continue
                return None, {"kind": "http", "code": 400, "body": text}, meta
            if exc.code == 429:
                ra = exc.headers.get("Retry-After") if exc.headers is not None else None
                try:
                    wait = float(ra) if ra is not None else min(rh.JUDGE_BACKOFF_BASE_S * 2 ** r429, rh.JUDGE_BACKOFF_CAP_S)
                except ValueError:
                    wait = min(rh.JUDGE_BACKOFF_BASE_S * 2 ** r429, rh.JUDGE_BACKOFF_CAP_S)
                if wait > rh.JUDGE_RETRY_AFTER_CAP_S or r429 >= rh.JUDGE_MAX_RETRIES:
                    STOP.set(); STOP_REASON.append(f"HTTP 429 Retry-After {wait:.0f}s")
                    return None, {"kind": "http", "code": 429, "body": text}, meta
                r429 += 1
                time.sleep(wait)
                continue
            if exc.code in (500, 502, 503, 504) and k < len(delays):
                time.sleep(delays[k]); k += 1
                continue
            return None, {"kind": "http", "code": exc.code, "body": text}, meta
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            if k < len(delays):
                time.sleep(delays[k]); k += 1
                continue
            return None, {"kind": "net", "body": type(exc).__name__}, meta
        finally:
            st.gate.leave()


def slot_record(st: State, cid: str, persona: str, seed: int, row: dict, text: str, tier: str) -> dict:
    """Send one slot (with up to MAX_INVALID_RETRIES re-sends of an unparsable reply) and return its record."""
    system = PS.SYSTEM[persona]
    user = rl.user_message(text, {"catKo": row["catKo"], "q": row["q"], "qko": row["qko"]})
    first, retry = st.mcfg.get("max_tokens", (RR.MAX_TOKENS_FIRST, RR.MAX_TOKENS_RETRY))
    t0 = time.time()
    rec = {"cell_id": cid, "tier": tier, "persona": persona, "seed": seed, "model": st.alias,
           "view_kind": row["view_kind"], "started_at_utc": now()}
    tok_in = tok_out = 0
    last_err = None
    for k in range(MAX_INVALID_RETRIES + 1):
        payload, err, meta = post_once(st, system, user, first if k == 0 else retry, seed)
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
        msg = choice.get("message") or {}
        usage = payload.get("usage") or {}
        tok_in += usage.get("prompt_tokens") or 0
        tok_out += usage.get("completion_tokens") or 0
        content = msg.get("content") or ""
        parsed, perr = rl.parse_content(content)
        rec.update(finish_reason=choice.get("finish_reason"), attempts=k + 1)
        if parsed is not None:
            fin = RR.finalize(parsed, text)
            rec.update(valid=True, status="ok", S_raw=fin["S_raw"], R_raw=fin["R_raw"], span=fin["span"],
                       note=(fin["note"] or "")[:400], span_verbatim=fin["span_verbatim"], S_final=fin["S_final"],
                       R_floor=fin["R_floor"], seed_sent=st.send_seed)
            break
        last_err = perr
        rec.update(valid=False, status="invalid", error=f"unparsed: {perr}", raw_head=content[:200], seed_sent=st.send_seed)
    rec.update(prompt_tokens=tok_in, completion_tokens=tok_out, latency_s=round(time.time() - t0, 1))
    return rec



def tier_out(model: str, tier: str) -> Path:
    base = HERE / ("raw_internal" if tier in C.INTERNAL_TIERS else "raw")
    if os.environ.get("R10_RAW_DIR"):                      # tests only
        base = Path(os.environ["R10_RAW_DIR"]) / base.name
    return base / f"{model}_t{tier}.jsonl"


def write_rec(st: State, out: Path, rec: dict) -> None:
    with _write_lock:
        with out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        st.calls_done += 1
        ok_call = rec["status"] in TERMINAL
        st.fail_streak = 0 if ok_call else st.fail_streak + 1
        st.valid += 1 if rec.get("valid") else 0
        st.tok_in += rec.get("prompt_tokens") or 0
        st.tok_out += rec.get("completion_tokens") or 0
        st.recent.append(time.time())
        if st.fail_streak >= CONSECUTIVE_FAIL_STOP and not STOP.is_set():
            STOP.set(); STOP_REASON.append(f"{CONSECUTIVE_FAIL_STOP} consecutive failed calls")
    print(f"{rec['cell_id']} {rec['persona']} s{rec['seed']} {rec['status']} S_raw={rec.get('S_raw')} "
          f"S={rec.get('S_final')} in={rec.get('prompt_tokens')} out={rec.get('completion_tokens')} "
          f"{rec['latency_s']}s {rec.get('error', '')}", file=sys.stderr, flush=True)


def progress_line(st: State, tiers_state: dict, final=False) -> str:
    now_t = time.time()
    with _write_lock:
        recent = [t for t in st.recent if now_t - t <= 600]
        st.recent = recent
        done, planned = st.calls_done, st.planned
    window = min(600.0, now_t - st.t0) or 1.0
    rate = len(recent) / window * 60            # calls per minute over the last <= 10 min
    left = max(0, planned - done)
    eta = (left / rate * 60) if rate > 0 else float("inf")
    ts = " ".join(f"{t}:{v['done']}/{v['total']}" for t, v in tiers_state.items())
    return (f"[review10] {now()} model={st.alias} {'FINAL ' if final else ''}calls {done}/{planned} "
            f"parse_ok={st.valid / max(1, done):.1%} rate={rate:.0f}/min ETA={'n/a' if eta == float('inf') else f'{eta / 3600:.1f}h'} "
            f"workers={st.a.workers} cells_done[{ts}] stop={'; '.join(STOP_REASON) or '-'}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, choices=sorted(MODEL_KEYS))
    ap.add_argument("--tiers", default="1", help="comma list in priority order, e.g. 1,2a,2b,3a,3b,3c,3d,3e")
    ap.add_argument("--out", default=None, help="test only: raw jsonl for a single tier (default raw/<model>_t<tier>.jsonl)")
    ap.add_argument("--endpoint", default=None, help="OpenAI-compatible base URL ending in /v1 (never written to a file)")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--gate", action="store_true", help="courtesy gate: send only while nobody else uses the endpoint")
    ap.add_argument("--pilot", action="store_true", help="10 calls: first 2 cells of the order x 5 personas x seed 1")
    ap.add_argument("--limit-cells", type=int, default=0, help="test: only the first N cells of each tier's order")
    ap.add_argument("--max-wall-s", type=float, default=0, help="no new cell starts after this many seconds")
    ap.add_argument("--token-budget", type=int, default=0, help="cap on prompt+completion tokens (the files' records included)")
    ap.add_argument("--progress", default=None)
    ap.add_argument("--report-every-s", type=float, default=900)
    ap.add_argument("--confirm-addendum30-frozen", action="store_true")
    a = ap.parse_args(argv)
    alias = a.model
    tiers = [t for t in a.tiers.split(",") if t]
    for t in tiers:
        if t not in C.TIERS:
            raise SystemExit(f"unknown tier {t}")
    mcfg = dict(RR.MODELS[MODEL_KEYS[alias]])
    if alias in ("qwen", "fake"):
        mcfg["send_seed"] = True          # tried; falls back to unseeded draws if the endpoint rejects it (recorded)
    if not 1 <= a.workers <= MAX_WORKERS:
        raise SystemExit(f"REFUSING: --workers must be 1..{MAX_WORKERS}")
    if alias != "fake" and not a.confirm_addendum30_frozen and not a.pilot:
        raise SystemExit("REFUSING: pass --confirm-addendum30-frozen only after the PLAN.md freeze commit and SCHEDULE.md")
    if mcfg["route"] == "<internal-proxy>" and not a.token_budget:
        raise SystemExit("REFUSING: --token-budget is required for the <internal-proxy> route")
    st = State(a, mcfg, alias)
    st.recent = []
    window = WINDOW[alias]
    first_tok, retry_tok = mcfg.get("max_tokens", (RR.MAX_TOKENS_FIRST, RR.MAX_TOKENS_RETRY))
    jobs: list[tuple[str, str, list]] = []
    cmaps: dict[str, dict] = {}
    outs: dict[str, Path] = {}
    tiers_state: dict[str, dict] = {}
    prior_tokens = 0
    n_skipped = 0
    for tier in tiers:
        rows = C.load_tier(tier)
        cmap = {r["cell_id"]: r for r in rows}
        cmaps[tier] = cmap
        ids = C.order(rows)
        if a.pilot:
            ids = ids[:2]
        elif a.limit_cells:
            ids = ids[:a.limit_cells]
        out = Path(a.out) if (a.out and len(tiers) == 1) else tier_out(alias, tier)
        out.parent.mkdir(parents=True, exist_ok=True)
        outs[tier] = out
        prior = read_jsonl(out)
        prior_tokens += sum((r.get("prompt_tokens") or 0) + (r.get("completion_tokens") or 0) for r in prior)
        done = {(r["cell_id"], r.get("persona"), r.get("seed")) for r in prior if r.get("status") in TERMINAL}
        todo, skipped = [], []
        for cid in ids:
            est = int(RR.est_for(cmap[cid], {}, PS.SYSTEM["domain"]) * EST_TO_ACTUAL)
            (skipped if est + retry_tok > window else todo).append(cid)
        with out.open("a", encoding="utf-8") as fh:
            for cid in skipped:
                if (cid, None, None) not in done:
                    fh.write(json.dumps({"cell_id": cid, "tier": tier, "persona": None, "seed": None, "model": alias,
                                         "status": "context_skip", "valid": False, "view_kind": cmap[cid]["view_kind"],
                                         "note": "estimated prompt (characters/4 x 1.15) + retry budget exceeds the model window; not sent"}) + "\n")
        n_skipped += len(skipped)
        slots = [(p, s) for p, s in SLOTS if not a.pilot or s == 1]
        n_cells = 0
        for cid in todo:
            left = [(p, s) for p, s in slots if (cid, p, s) not in done]
            if left:
                jobs.append((tier, cid, left))
                n_cells += 1
        tiers_state[tier] = {"done": len(todo) - n_cells, "total": len(todo)}
    st.tok_prior = prior_tokens
    st.planned = sum(len(l) for _, _, l in jobs)
    print(f"model {alias} tiers {tiers} pending_cells {len(jobs)} pending_calls {st.planned} skipped_context {n_skipped}", file=sys.stderr, flush=True)
    q: Queue = Queue()
    for item in jobs:
        q.put(item)
    progress = Path(a.progress) if a.progress else None
    t_start = time.time()
    started = now()
    stop_report = threading.Event()

    def append_progress(line: str):
        if progress is not None:
            with _write_lock:
                with progress.open("a", encoding="utf-8") as pf:
                    pf.write(line + "\n")

    def reporter():
        while not stop_report.wait(a.report_every_s):
            append_progress(progress_line(st, tiers_state))

    def worker():
        while not STOP.is_set():
            if a.max_wall_s and time.time() - t_start > a.max_wall_s:
                DEADLINE.set()
                return
            try:
                tier, cid, left = q.get_nowait()
            except Empty:
                return
            row = cmaps[tier][cid]
            need = 0
            if a.token_budget:
                per_call = int(RR.est_for(row, {}, PS.SYSTEM["domain"]) * EST_TO_ACTUAL) + first_tok // 2
                need = per_call * len(left)
                with st.lock:
                    if st.tok_prior + st.tok_in + st.tok_out + st.reserved + need > a.token_budget:
                        STOP.set(); STOP_REASON.append(f"token budget cap {a.token_budget}")
                        return
                    st.reserved += need
            finished_cell = False
            try:
                text, _, _ = RR.material_for(row, {})
                for persona, seed in left:
                    if STOP.is_set():
                        return
                    rec = slot_record(st, cid, persona, seed, row, text, tier)
                    if rec["status"] == "stopped":
                        return
                    write_rec(st, outs[tier], rec)
                    if rec["status"] == "context_skip":
                        break
                else:
                    finished_cell = True
            finally:
                if need:
                    with st.lock:
                        st.reserved -= need
            if finished_cell:
                with st.lock:
                    tiers_state[tier]["done"] += 1
                    if tiers_state[tier]["done"] == tiers_state[tier]["total"]:
                        append_progress(f"[review10] {now()} model={alias} tier={tier} finished ({tiers_state[tier]['total']} cells x 25 slots; "
                                        + progress_line(st, tiers_state)[len('[review10] '):].split(' ', 1)[1] + ")")

    append_progress(f"[review10] {now()} model={alias} start: tiers {','.join(tiers)}, {len(jobs)} cells / {st.planned} calls pending, workers={a.workers}")
    threads = [threading.Thread(target=worker, daemon=True) for _ in range(a.workers)]
    rt = threading.Thread(target=reporter, daemon=True)
    for t in threads:
        t.start()
    rt.start()
    for t in threads:
        t.join()
    stop_report.set()
    append_progress(progress_line(st, tiers_state, final=True))
    meta = {"model": alias, "tiers": tiers, "pilot": bool(a.pilot), "temperature": TEMPERATURE, "seed_sent": st.send_seed,
            "seed_note": st.seed_note, "workers": a.workers, "gate": bool(a.gate), "gate_waited_s": st.gate.waited_s,
            "cells_skipped_context": n_skipped, "pending_calls_at_start": st.planned,
            "calls": st.calls_done, "valid_calls": st.valid, "prompt_tokens": st.tok_in, "completion_tokens": st.tok_out,
            "started_utc": started, "finished_utc": now(), "wall_s": round(time.time() - t_start, 1),
            "deadline_hit": DEADLINE.is_set(), "stop_reasons": list(STOP_REASON),
            "persona_sha256": PS.PREAMBLE_SHA256, "base_sha256": PS.BASE_SHA256}
    meta_path = tier_out(alias, tiers[0]).with_name(f"{alias}_run.meta.jsonl")
    if a.out and len(tiers) == 1:
        meta_path = Path(a.out).with_name(Path(a.out).stem + ".meta.jsonl")
    with meta_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(meta) + "\n")
    print(json.dumps({k: v for k, v in meta.items() if k != "persona_sha256"}), file=sys.stderr, flush=True)
    return 1 if STOP_REASON else 0


if __name__ == "__main__":
    sys.exit(main())
