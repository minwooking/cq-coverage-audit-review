#!/usr/bin/env python3
"""Run one rater condition of addendum 28 (review6_raters): LLM-rater labels S/R/span per primary cell.

AI-generated code: review and test before use.  Python stdlib + the repository's rater_luna / run_holdout modules.
It never opens site_key*, labeling_sheet_key*, human_labels_export*, views_for_raters.zip, .env or sealed files:
the material comes from cells_manifest.json (build_inputs.py), the prompt text from prompts.py.

One request per cell, no conversation history.  Resumable (a cell with a valid record is not re-sent).  Workers <= 3
per endpoint.  Token budget: a call is refused before it is sent if (actual prompt tokens already used by the budget
group + reserved for in-flight calls + 1.07 x its estimate) would exceed the cap.  HTTP 402/403, an HTTP 429 whose
Retry-After exceeds 300 s, the budget cap or 5 consecutive failed calls stop the whole run (no retry loop).

Amended plan: no OpenAI/luna call is made.  Open-weight raters are reached through a local port-forward to the shared server
(request-only); the Anthropic route is used only if the <internal-proxy> proxy is logged in to it.

Record fields: cell_id, run, model, prompt_id, prompt_sha256, view_sha256, view_kind, temperature_sent, seed_sent,
est_input_tokens, usage, S_raw, R_raw, span, note, span_verbatim, S_final, R_floor, valid, status, attempts.
  span check: whitespace-normalised, the cited span must be a substring of the rendering the rater saw; if not,
  S_final = 0 (span_verbatim is logged for every S_raw = 1).  R_floor = max(R_raw, 1) when S_final = 1, else R_raw.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
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

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HARNESS / "llm_rater_luna_2026-10-15"))
sys.path.insert(0, str(HARNESS))
import prompts as P  # noqa: E402
import rater_luna as rl  # noqa: E402  (parse_content / collapse / user_message only)
import run_holdout as rh  # noqa: E402  (pacing + retry constants, as in S21)

SEED = 20260913
INTERNAL_PROXY = "http://localhost:PORT/v1"
MAX_WORKERS = 3
MAX_TOKENS_FIRST = 2048
MAX_TOKENS_RETRY = 4096
MAX_INVALID_RETRIES = 2
HTTP_TIMEOUT_S = 900
EST_TO_ACTUAL = 1.07          # S21: 5,177,144 actual / 4,853,188 estimated
CONSECUTIVE_FAIL_STOP = 5
CONTEXT_RE = re.compile(r"(maximum context length|context length|context window|too long|exceeds the model)", re.I)
TEMP_REJECT_RE = re.compile(r"temperature", re.I)
RAW = HERE / "raw"

MODELS = {
    "haiku": {"id": "anthropic/claude-haiku-5-5", "family": "anthropic", "route": "<internal-proxy>", "response_format": None,
              "send_seed": False, "temperature": "send_if_accepted", "extra": {}, "budget_group": "haiku"},
    "opus": {"id": "anthropic/claude-opus-5-5", "family": "anthropic", "route": "<internal-proxy>", "response_format": None,
             "send_seed": False, "temperature": "send_if_accepted", "extra": {}, "budget_group": "opus"},
    "glm": {"id": "zai-org/GLM-4.7-Flash", "family": "zhipu", "route": "vllm", "response_format": None,
            "send_seed": True, "temperature": "send", "extra": {"chat_template_kwargs": {"enable_thinking": False}},
            "budget_group": None},
    "gptoss": {"id": "openai/gpt-oss-20b", "family": "openai-open", "route": "vllm", "response_format": None,
               "send_seed": True, "temperature": "send", "extra": {"reasoning_effort": "low"},
               "budget_group": None},
    # same-family contrast rater (Qwen = the extractor's family): Qwen3.8-Flash-Next NVFP4, vLLM 0.30.0 container
    # `<container>` on the shared server, reached ONLY through the <internal-proxy> gateway (provider <internal-proxy>); thinking cannot be
    # switched off through the gateway (probed), so the model reasons before answering and gets a larger output budget.
    "qwen": {"id": "<internal-proxy>/Qwen/Qwen3.8-Flash-Next", "family": "qwen", "route": "<internal-proxy>", "response_format": None,
             "send_seed": False, "temperature": "send", "extra": {}, "budget_group": "qwen", "max_tokens": (6144, 12288)},
    "fakeproxy": {"id": "fake-luna", "family": "test", "route": "<internal-proxy>", "response_format": {"type": "text"}, "send_seed": True,
                "temperature": "send", "extra": {}, "budget_group": "fakeproxy"},
    "fake": {"id": "fake-rater", "family": "test", "route": "vllm", "response_format": None, "send_seed": False,
             "temperature": "send", "extra": {}, "budget_group": None},
}

# cells: sub182 (the 182 cells with a subgraph view) | all188 (used only by the offline test double)
# Experiment 1 rater = GLM-4.7-Flash (amended plan): (a) T=0 twice, (b) T=0.7 three times, (c) two paraphrases at T=0.
RUNS = {
    "a1": dict(model="glm", prompt="base", temperature=0.0, seed=SEED, order=("sorted",), cells="sub182"),
    "a2": dict(model="glm", prompt="base", temperature=0.0, seed=SEED, order=("sorted",), cells="sub182"),
    "b1": dict(model="glm", prompt="base", temperature=0.7, seed=SEED + 1, order=("shuffle", SEED + 101), cells="sub182"),
    "b2": dict(model="glm", prompt="base", temperature=0.7, seed=SEED + 2, order=("shuffle", SEED + 102), cells="sub182"),
    "b3": dict(model="glm", prompt="base", temperature=0.7, seed=SEED + 3, order=("shuffle", SEED + 103), cells="sub182"),
    "c1": dict(model="glm", prompt="p1", temperature=0.0, seed=SEED, order=("sorted",), cells="sub182"),
    "c2": dict(model="glm", prompt="p2", temperature=0.0, seed=SEED, order=("sorted",), cells="sub182"),
    "gptoss": dict(model="gptoss", prompt="base", temperature=0.0, seed=SEED, order=("sorted",), cells="sub182"),
    "qwen": dict(model="qwen", prompt="base", temperature=0.0, seed=None, order=("sorted",), cells="all188", max_ctx=262144),
    "haiku": dict(model="haiku", prompt="base", temperature=0.0, seed=None, order=("sorted",), cells="sub182"),
    "opus": dict(model="opus", prompt="base", temperature=0.0, seed=None, order=("sorted",), cells="sub182"),
    "fake": dict(model="fake", prompt="base", temperature=0.0, seed=None, order=("sorted",), cells="all188"),
}

STOP = threading.Event()
STOP_REASON: list[str] = []
_write_lock = threading.Lock()
_ledger_lock = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def finalize(parsed: dict, material: str) -> dict:
    s, r, span = parsed["S"], parsed["R"], parsed["span"]
    verb = None
    if s == 1:
        verb = bool(collapse(span)) and collapse(span) in collapse(material)
    s_final = 1 if (s == 1 and verb) else 0
    r_floor = max(r, 1) if s_final == 1 else r
    return {"S_raw": s, "R_raw": r, "span": span, "note": parsed["note"], "span_verbatim": verb,
            "S_final": s_final, "R_floor": r_floor}


def load_manifest():
    m = json.loads((HERE / "cells_manifest.json").read_text(encoding="utf-8"))
    return m, {c["cell_id"]: c for c in m["cells"]}


def select_cells(m, cmap, spec: dict, subset: str | None) -> list[str]:
    ids = sorted(cmap)
    kind = spec["cells"]
    if kind == "sub182":
        ids = [i for i in ids if cmap[i]["view_kind"] == "subgraph"]
    elif kind == "aux48":
        ids = list(m["aux_sample"])
    if subset == "sub182":
        ids = [i for i in ids if cmap[i]["view_kind"] == "subgraph"]
    elif subset == "fb6":
        ids = [i for i in ids if cmap[i]["view_kind"] != "subgraph"]
    elif subset not in (None, "all"):
        raise SystemExit(f"unknown subset {subset}")
    o = spec["order"]
    if o[0] == "shuffle":
        random.Random(o[1]).shuffle(ids)
    return ids


def material_for(cmap_row: dict, spec: dict) -> tuple[str, str, str]:
    """(text, sha256, kind) of the rendering the rater sees."""
    if spec.get("material") == "full":
        path, sha, kind = cmap_row["full_path"], cmap_row["full_sha256"], "full_view"
    else:
        path, sha, kind = cmap_row["view_path"], cmap_row["view_sha256"], cmap_row["view_kind"]
    text = (ACCESS / path).read_text(encoding="utf-8")
    if hashlib.sha256(text.encode()).hexdigest() != sha:
        raise SystemExit(f"{cmap_row['cell_id']}: material sha256 mismatch")
    return text, sha, kind


def est_for(cmap_row: dict, spec: dict, prompt: str) -> int:
    if spec.get("material") == "full":
        return cmap_row["est_input_tokens_full"] + (len(prompt) - len(rl.RATER_PROMPT)) // 4
    return cmap_row["est_input_tokens"] + (len(prompt) - len(rl.RATER_PROMPT)) // 4


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def group_used(group: str | None) -> int:
    """Actual prompt tokens already spent by a budget group (every raw file, every record tagged with the group)."""
    if group is None or not RAW.exists():
        return 0
    tot = 0
    for p in RAW.glob("*.jsonl"):
        if p.name.endswith(".meta.jsonl"):
            continue
        for r in read_jsonl(p):
            if r.get("budget_group") == group:
                tot += sum((a.get("prompt_tokens") or 0) for a in r.get("attempts", []))
    return tot


def http_post(url: str, body: dict, key: str, timeout: float):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def build_body(mcfg: dict, spec: dict, system: str, user: str, max_tokens: int, send_temp: bool) -> dict:
    body = {"model": mcfg["id"],
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if send_temp:
        body["temperature"] = spec["temperature"]
    if mcfg["send_seed"] and spec["seed"] is not None:
        body["seed"] = spec["seed"]
    body["max_tokens"] = max_tokens
    if mcfg["response_format"] is not None:
        body["response_format"] = mcfg["response_format"]
    body.update(mcfg["extra"])
    return body


METRIC_RE = re.compile(r"^vllm:num_requests_(running|waiting)\{[^}]*\}\s+([0-9.eE+-]+)", re.M)


class Gate:
    """Courtesy gate for shared vLLM endpoints (operational only; changes no request, prompt or cell).

    Before each call, read the server's /metrics (a plain GET on the same base URL): requests running + waiting that
    are NOT this runner's own in-flight calls belong to somebody else.  While there are any, send nothing (poll every
    10 s), so the endpoint never carries more than 3 concurrent requests in total.  An unreadable /metrics does not block."""

    def __init__(self, base: str, enabled: bool):
        self.root = base[:-3] if base.endswith("/v1") else base
        self.enabled = enabled
        self.inflight = 0
        self.last = 0.0
        self.others = 0
        self.waited_s = 0.0
        self.lock = threading.Lock()

    def refresh(self):
        try:
            with urllib.request.urlopen(f"{self.root}/metrics", timeout=10) as r:
                txt = r.read().decode("utf-8", "replace")
            tot = sum(float(v) for _, v in METRIC_RE.findall(txt))
            self.others = max(0, int(round(tot)) - self.inflight)
        except Exception:
            self.others = 0
        self.last = time.time()

    def enter(self):
        if not self.enabled:
            return
        while not STOP.is_set():
            with self.lock:
                if time.time() - self.last > 8:
                    self.refresh()
                if self.others == 0:
                    self.inflight += 1
                    return
            time.sleep(10)
            self.waited_s += 10
        with self.lock:
            self.inflight += 1

    def leave(self):
        if self.enabled:
            with self.lock:
                self.inflight -= 1


class Runner:
    def __init__(self, a, m, cmap, spec, mcfg):
        self.a, self.m, self.cmap, self.spec, self.mcfg = a, m, cmap, spec, mcfg
        self.prompt = P.PROMPTS[spec["prompt"]]
        self.prompt_sha = P.SHA[spec["prompt"]]
        self.key = os.environ.get(rh.API_KEY_ENV) or ("<internal-proxy>-local" if mcfg["route"] == "<internal-proxy>" else "none")
        self.base = a.endpoint or (INTERNAL_PROXY if mcfg["route"] == "<internal-proxy>" else None)
        if not self.base:
            raise SystemExit("--endpoint is required for a vLLM route")
        self.base = self.base.rstrip("/")
        self.send_temp = mcfg["temperature"] in ("send", "send_if_accepted")
        self.temp_note = None
        self.reserved = 0
        self.group = spec.get("budget_group") or mcfg["budget_group"]
        self.used = group_used(self.group) if self.group else 0
        self.cap = a.token_budget
        self.gate = Gate(self.base, bool(a.gate))
        self.fail_streak = 0
        self.calls_done = 0
        self.planned = 0
        self.t0 = time.time()
        self.marks = set()
        self.tok_in = 0
        self.tok_out = 0

    # ---- one HTTP attempt with transport-level retry
    def post_once(self, system, user, max_tokens):
        mcfg, spec = self.mcfg, self.spec
        retry_delays = (5, 15, 45)
        attempt_meta = {"max_tokens": max_tokens}
        k = 0
        r429 = 0
        while True:
            if STOP.is_set():
                return None, {"kind": "stopped"}, attempt_meta
            body = build_body(mcfg, spec, system, user, max_tokens, self.send_temp)
            attempt_meta["temperature_sent"] = self.send_temp
            if mcfg["route"] == "<internal-proxy>":
                rh._pace_judge_request()
            self.gate.enter()
            try:
                payload = http_post(f"{self.base}/chat/completions", body, self.key, HTTP_TIMEOUT_S)
                return payload, None, attempt_meta
            except urllib.error.HTTPError as exc:
                try:
                    text = exc.read().decode("utf-8", "replace")[:600]
                except Exception:
                    text = ""
                if exc.code in (402, 403):
                    STOP.set(); STOP_REASON.append(f"HTTP {exc.code}")
                    return None, {"kind": "http", "code": exc.code, "body": text}, attempt_meta
                if exc.code == 400:
                    if CONTEXT_RE.search(text):
                        return None, {"kind": "context", "code": 400, "body": text}, attempt_meta
                    if (self.send_temp and mcfg["temperature"] == "send_if_accepted" and TEMP_REJECT_RE.search(text)):
                        self.send_temp = False
                        self.temp_note = "temperature rejected by the API (HTTP 400); omitted for the rest of the run"
                        continue
                    return None, {"kind": "http", "code": 400, "body": text}, attempt_meta
                if exc.code == 429:
                    ra = exc.headers.get("Retry-After") if exc.headers is not None else None
                    try:
                        wait = float(ra) if ra is not None else min(rh.JUDGE_BACKOFF_BASE_S * 2 ** r429, rh.JUDGE_BACKOFF_CAP_S)
                    except ValueError:
                        wait = min(rh.JUDGE_BACKOFF_BASE_S * 2 ** r429, rh.JUDGE_BACKOFF_CAP_S)
                    if wait > rh.JUDGE_RETRY_AFTER_CAP_S or r429 >= rh.JUDGE_MAX_RETRIES:
                        STOP.set(); STOP_REASON.append(f"HTTP 429 Retry-After {wait:.0f}s")
                        return None, {"kind": "http", "code": 429, "body": text, "retry_after_s": wait}, attempt_meta
                    r429 += 1
                    print(f"429, retry in {wait:.0f}s", file=sys.stderr, flush=True)
                    time.sleep(wait)
                    continue
                if exc.code in (500, 502, 503, 504) and k < len(retry_delays):
                    time.sleep(retry_delays[k]); k += 1
                    continue
                return None, {"kind": "http", "code": exc.code, "body": text}, attempt_meta
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                if k < len(retry_delays):
                    time.sleep(retry_delays[k]); k += 1
                    continue
                return None, {"kind": "net", "body": repr(exc)}, attempt_meta
            finally:
                self.gate.leave()

    def job(self, cid: str):
        if STOP.is_set():
            return None
        row = self.cmap[cid]
        text, sha, kind = material_for(row, self.spec)
        cell = {"catKo": row["catKo"], "q": row["q"], "qko": row["qko"]}
        user = rl.user_message(text, cell)
        est = est_for(row, self.spec, self.prompt)
        need = int(est * EST_TO_ACTUAL)
        if self.group:
            with _ledger_lock:
                if self.used + self.reserved + need > self.cap:
                    STOP.set(); STOP_REASON.append(
                        f"token budget cap {self.cap} (used {self.used}, reserved {self.reserved}, need {need})")
                    return None
                self.reserved += need
        t0 = time.time()
        rec = {"cell_id": cid, "run": self.a.run, "model_key": self.a.model_key, "model": self.mcfg["id"],
               "family": self.mcfg["family"], "prompt_id": self.spec["prompt"], "prompt_sha256": self.prompt_sha,
               "view_sha256": sha, "view_kind": kind, "est_input_tokens": est,
               "seed_sent": self.spec["seed"] if self.mcfg["send_seed"] else None, "budget_group": self.group,
               "started_at_utc": now(), "attempts": []}
        try:
            final = None
            for k in range(MAX_INVALID_RETRIES + 1):
                first, retry = self.mcfg.get("max_tokens", (MAX_TOKENS_FIRST, MAX_TOKENS_RETRY))
                mt = first if k == 0 else retry
                payload, err, meta = self.post_once(self.prompt, user, mt)
                if err is not None:
                    meta.update(error=err["kind"], code=err.get("code"), body=(err.get("body") or "")[:300])
                    rec["attempts"].append(meta)
                    if err["kind"] == "context":
                        rec.update(valid=False, status="context_skip")
                        return self.write(rec, t0, ok_call=True)
                    rec.update(valid=False, status="error", error=err["kind"], error_body=(err.get("body") or "")[:300],
                               retry_after_s=err.get("retry_after_s"))
                    return self.write(rec, t0, ok_call=False)
                choice = payload.get("choices", [{}])[0]
                msg = choice.get("message", {})
                usage = payload.get("usage") or {}
                meta.update(finish_reason=choice.get("finish_reason"), prompt_tokens=usage.get("prompt_tokens"),
                            completion_tokens=usage.get("completion_tokens"))
                parsed, perr = rl.parse_content(msg.get("content") or "")
                meta["parse_ok"] = parsed is not None
                rec["attempts"].append(meta)
                rec.update(usage=usage, model_returned=payload.get("model"), raw_content=msg.get("content"))
                if parsed is not None:
                    rec.update(valid=True, status="ok", temperature_sent=self.send_temp, **finalize(parsed, text))
                    return self.write(rec, t0, ok_call=True)
                final = perr
            rec.update(valid=False, status="invalid", error=f"unparsed: {final}", temperature_sent=self.send_temp)
            return self.write(rec, t0, ok_call=True)
        finally:
            if self.group:
                with _ledger_lock:
                    self.reserved -= need
                    self.used += sum((a.get("prompt_tokens") or 0) for a in rec["attempts"])

    def write(self, rec, t0, ok_call):
        rec["elapsed_s"] = round(time.time() - t0, 1)
        with _write_lock:
            with Path(self.a.out).open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            self.calls_done += 1
            self.fail_streak = 0 if ok_call else self.fail_streak + 1
            u = rec.get("usage") or {}
            self.tok_in += sum((x.get("prompt_tokens") or 0) for x in rec["attempts"])
            self.tok_out += sum((x.get("completion_tokens") or 0) for x in rec["attempts"])
            if self.fail_streak >= CONSECUTIVE_FAIL_STOP and not STOP.is_set():
                STOP.set(); STOP_REASON.append(f"{CONSECUTIVE_FAIL_STOP} consecutive failed calls")
            self.checkpoint()
        print(f"{rec['cell_id']} {rec['view_kind']} status={rec['status']} S_raw={rec.get('S_raw')} "
              f"S={rec.get('S_final')} R={rec.get('R_raw')} in={u.get('prompt_tokens')} out={u.get('completion_tokens')} "
              f"{rec['elapsed_s']}s {rec.get('error', '')}", file=sys.stderr, flush=True)
        return rec

    def checkpoint(self):
        if not self.planned or not self.a.progress:
            return
        frac = self.calls_done / self.planned
        for mark in (0.5, 1.0):
            if frac >= mark and mark not in self.marks:
                self.marks.add(mark)
                line = (f"[raters] {now()} run={self.a.run} {self.calls_done}/{self.planned} calls "
                        f"({int(mark * 100)}%), prompt_tok={self.tok_in}, elapsed={int(time.time() - self.t0)}s, "
                        f"stop={'; '.join(STOP_REASON) or '-'}")
                with Path(self.a.progress).open("a", encoding="utf-8") as pf:
                    pf.write(line + "\n")


def preflight_vllm(base, mcfg, items, prompt, max_model_len):
    """Exact prompt-token counts through the server's /tokenize (no generation).  Over-context cells are skipped."""
    root = base[:-3] if base.endswith("/v1") else base
    counts = {}
    for cid, user in items:
        body = {"model": mcfg["id"], "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": user}],
                "add_generation_prompt": True}
        resp = http_post(f"{root}/tokenize", body, "none", 300)
        counts[cid] = int(resp["count"])
    over = sorted(c for c, n in counts.items() if n + MAX_TOKENS_RETRY > max_model_len)
    return {"max_model_len": max_model_len, "retry_max_tokens": MAX_TOKENS_RETRY, "prompt_tokens": counts,
            "n_cells": len(counts), "cells_over_context": over, "max_prompt_tokens": max(counts.values()) if counts else 0,
            "sum_prompt_tokens": sum(counts.values())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", required=True, choices=sorted(RUNS))
    ap.add_argument("--out", required=True, help="raw jsonl (appended; resumable)")
    ap.add_argument("--endpoint", default=None, help="OpenAI-compatible base URL ending in /v1 (vLLM route; <internal-proxy> default)")
    ap.add_argument("--subset", default=None, choices=("all", "sub182", "fb6"))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--token-budget", type=int, default=0, help="hard cap on actual prompt tokens of the budget group (<internal-proxy> models)")
    ap.add_argument("--limit-positions", default="", help="dry run: comma list of positions in the sorted subgraph cell list")
    ap.add_argument("--max-model-len", type=int, default=65536)
    ap.add_argument("--progress", default=None)
    ap.add_argument("--gate", action="store_true", help="courtesy gate: send only while nobody else is using the vLLM endpoint (/metrics)")
    ap.add_argument("--model-override", default=None, choices=sorted(MODELS), help="run the same condition on another model key (e.g. opus instead of haiku)")
    ap.add_argument("--confirm-addendum28-frozen", action="store_true")
    a = ap.parse_args(argv)
    spec = dict(RUNS[a.run])
    a.model_key = a.model_override or spec["model"]
    spec["model"] = a.model_key
    mcfg = MODELS[a.model_key]
    dry = a.limit_positions != ""
    if not 1 <= a.workers <= MAX_WORKERS:
        raise SystemExit(f"REFUSING: --workers must be 1..{MAX_WORKERS}")
    if not dry and a.model_key != "fake" and not a.confirm_addendum28_frozen:
        raise SystemExit("REFUSING: pass --confirm-addendum28-frozen only after the PLAN.md freeze commit")
    if (spec.get("budget_group") or mcfg["budget_group"]) and not a.token_budget:
        raise SystemExit("REFUSING: --token-budget is required for an <internal-proxy> model")
    m, cmap = load_manifest()
    ids = select_cells(m, cmap, spec, a.subset)
    if dry:
        sub = [i for i in sorted(cmap) if cmap[i]["view_kind"] == "subgraph"]
        ids = [sub[int(p)] for p in a.limit_positions.split(",")]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {r["cell_id"] for r in read_jsonl(out) if r.get("valid") or r.get("status") == "context_skip"}
    pending = [c for c in ids if c not in done]
    rn = Runner(a, m, cmap, spec, mcfg)
    est_planned = sum(est_for(cmap[c], spec, rn.prompt) for c in pending)
    print(f"run {a.run} model {mcfg['id']} cells {len(ids)} done {len(done)} pending {len(pending)} "
          f"est_planned {est_planned} (x{EST_TO_ACTUAL}={int(est_planned * EST_TO_ACTUAL)}) used {rn.used} cap {a.token_budget}",
          file=sys.stderr, flush=True)
    if rn.group and rn.used + int(est_planned * EST_TO_ACTUAL) > a.token_budget:
        print("NOTE: the planned estimate exceeds the remaining cap; the run will stop at the cap", file=sys.stderr, flush=True)
    meta_path = out.with_name(out.stem + ".meta.jsonl")
    started = now()
    t_start = time.time()
    if mcfg["route"] == "vllm" and a.model_key != "fake" or (a.model_key == "fake" and a.endpoint):
        items = []
        for c in pending:
            text, _, _ = material_for(cmap[c], spec)
            items.append((c, rl.user_message(text, {"catKo": cmap[c]["catKo"], "q": cmap[c]["q"], "qko": cmap[c]["qko"]})))
        pre = preflight_vllm(rn.base, mcfg, items, rn.prompt, a.max_model_len) if items else None
        if pre:
            out.with_name(out.stem + "_preflight.json").write_text(json.dumps(pre, indent=1), encoding="utf-8")
            over = set(pre["cells_over_context"])
            with out.open("a", encoding="utf-8") as fh:
                for c in sorted(over):
                    fh.write(json.dumps({"cell_id": c, "run": a.run, "model_key": a.model_key, "model": mcfg["id"],
                                         "status": "context_skip", "valid": False, "view_kind": cmap[c]["view_kind"],
                                         "attempts": [{"prompt_tokens": pre["prompt_tokens"][c]}],
                                         "note": "prompt + retry budget exceeds max_model_len (preflight)"}) + "\n")
            pending = [c for c in pending if c not in over]
    if spec.get("max_ctx"):
        retry_tokens = mcfg.get("max_tokens", (MAX_TOKENS_FIRST, MAX_TOKENS_RETRY))[1]
        too_big = [c for c in pending if est_for(cmap[c], spec, rn.prompt) + retry_tokens > spec["max_ctx"]]
        with out.open("a", encoding="utf-8") as fh:
            for c in too_big:
                fh.write(json.dumps({"cell_id": c, "run": a.run, "model_key": a.model_key, "model": mcfg["id"],
                                     "status": "context_skip", "valid": False, "view_kind": cmap[c]["view_kind"],
                                     "est_input_tokens": est_for(cmap[c], spec, rn.prompt), "attempts": [],
                                     "note": "estimated prompt (characters/4) + retry budget exceeds the model window; not sent"}) + "\n")
        pending = [c for c in pending if c not in set(too_big)]
    rn.planned = len(pending)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = [ex.submit(rn.job, c) for c in pending]
        for f in as_completed(futs):
            f.result()
    finished = now()
    meta = {"run": a.run, "model": mcfg["id"], "prompt_id": spec["prompt"], "prompt_sha256": rn.prompt_sha,
            "temperature_requested": spec["temperature"], "temperature_sent": rn.send_temp,
            "temperature_note": rn.temp_note, "seed": spec["seed"] if mcfg["send_seed"] else None,
            "workers": a.workers, "subset": a.subset, "pending_at_start": len(pending), "calls": rn.calls_done,
            "prompt_tokens": rn.tok_in, "completion_tokens": rn.tok_out, "started_utc": started, "finished_utc": finished,
            "wall_s": round(time.time() - t_start, 1), "stop_reasons": list(STOP_REASON), "gate": bool(a.gate), "gate_waited_s": rn.gate.waited_s,
            "budget_group": rn.group, "token_budget": a.token_budget or None}
    with meta_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(meta) + "\n")
    print(json.dumps(meta), file=sys.stderr, flush=True)
    return 1 if STOP_REASON else 0


if __name__ == "__main__":
    sys.exit(main())
