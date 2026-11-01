#!/usr/bin/env python3
"""Addendum 27 amendments 1-2: score the natural-corpus (and template-corpus) A/B subgraph views with
gpt-oss-20b, GLM-4.7-Flash (non-Qwen, primary) and Qwen3.8-Flash-Next (same-family contrast).

AI-generated; review and test before reuse.  Imports harness/review6_judges/score_judges.py UNCHANGED (sha256
pinned below) and reuses its cell scorer: same prompt, T=0, json_object, max_tokens 1024, retry 4096 x2, thinking-off
switch, nothing imputed.  Only additions: (a) the judge table gets a `qwenflash` entry at run time, (b) the scorer's
HTTP helper is wrapped so a bearer key can be sent to a server that requires one (the key is read from
R6_QWEN_API_KEY or, if unset, CHUNKTOGRAPH_LLM_API_KEY; it is never printed or written),
(c) pass loop with a prompt-token budget, a consecutive-failure stop rule, resume, and reuse of addendum-26 records.

  run_natural_judges.py --judge gptoss|glm|qwenflash --endpoint http://127.0.0.1:PORT/v1 --corpus natural|template|both
                        [--reuse-raw FILE] [--preflight-only] [--budget N] [--workers 1..3] [--repeats 3]

Request-only: it never starts, stops or reconfigures a server.  At most 3 workers per endpoint.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCESS = HERE.parents[1]
REPO = ACCESS.parents[1]
sys.path.insert(0, str(ACCESS / "harness" / "review6_judges"))

import score_judges as sj  # noqa: E402

EXPECTED_SCORER_SHA = "3788576cd22eb73d7568d032a4db869de3a195c76c5cbeb6e6f42f5e6239a753"
EXPECTED_PLAN_SHA = "12caf2e02a195bdaaa33920b101130bfc9ea14476f704eeae37ea136bcbdb159"  # PLAN.md after amendment 2
MAX_WORKERS = 3
SEED = 20260913
CONSEC_FAIL_STOP = 10
JOBS = {"natural": HERE / "jobs_natural.jsonl", "template": HERE / "jobs_template_AB.jsonl"}
MAXLEN = {"gptoss": 65536, "glm": 65536, "qwenflash": 262144, "fake": 65536}
BUDGET = {"gptoss": 6_000_000, "glm": 6_000_000, "qwenflash": 3_000_000, "fake": 10**9}
JUDGE_LABEL = {"gptoss": "primary non-Qwen", "glm": "primary non-Qwen", "qwenflash": "same-family judge (contrast)", "fake": "test double"}

sj.JUDGES["qwenflash"] = {"model": "Qwen/Qwen3.8-Flash-Next", "extra": {"chat_template_kwargs": {"enable_thinking": False}}}


def _key() -> str:
    k = os.environ.get("R6_QWEN_API_KEY")
    if k:
        return k
    k = os.environ.get("CHUNKTOGRAPH_LLM_API_KEY")
    if not k:
        raise SystemExit("set R6_QWEN_API_KEY or CHUNKTOGRAPH_LLM_API_KEY (the judge key is environment-only)")
    return k


_BEARER = {"v": "none"}
_orig_post = sj.post


def _post(url: str, body: dict, timeout: float = 900.0):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {_BEARER['v']}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


sj.post = _post  # one_request / preflight look the name up in the module at call time


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def plan_guard() -> dict:
    rel = str((HERE / "PLAN.md").relative_to(REPO))
    subprocess.run(["git", "-C", str(REPO), "ls-files", "--error-unmatch", rel], check=True, capture_output=True)
    if subprocess.run(["git", "-C", str(REPO), "diff", "--quiet", "HEAD", "--", rel]).returncode != 0:
        raise SystemExit("REFUSING TO RUN: PLAN.md differs from the committed version")
    got = sha_file(HERE / "PLAN.md")
    text = (HERE / "PLAN.md").read_text(encoding="utf-8")
    if got != EXPECTED_PLAN_SHA or "27.A1 Amendment 1" not in text or "27.A2 Amendment 2" not in text:
        raise SystemExit(f"REFUSING TO RUN: PLAN.md sha256 {got} is not the amended plan this runner is pinned to")
    commit = subprocess.run(["git", "-C", str(REPO), "log", "-1", "--format=%H", "--", rel], capture_output=True, text=True).stdout.strip()
    return {"plan_sha256": got, "plan_commit": commit}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--judge", choices=("gptoss", "glm", "qwenflash", "fake"), required=True)
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--corpus", choices=("natural", "template", "both"), default="both")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--budget", type=int, default=None)
    ap.add_argument("--reuse-raw", type=Path, default=None, help="addendum-26 raw jsonl of THIS judge (template cells only)")
    ap.add_argument("--out-dir", type=Path, default=HERE / "raw")
    ap.add_argument("--preflight-only", action="store_true")
    ap.add_argument("--test", action="store_true", help="test double: skips the plan and scorer pins")
    a = ap.parse_args(argv)
    if not 1 <= a.workers <= MAX_WORKERS:
        raise SystemExit(f"REFUSING: --workers must be 1..{MAX_WORKERS}")
    if (a.judge == "fake") != a.test:
        raise SystemExit("REFUSING: the fake judge is for --test only")
    if not a.test:
        if sha_file(ACCESS / "harness" / "review6_judges" / "score_judges.py") != EXPECTED_SCORER_SHA:
            raise SystemExit("REFUSING: score_judges.py differs from the pinned sha256")
        guard = plan_guard()
    else:
        guard = {"plan_sha256": None, "plan_commit": None}
    _BEARER["v"] = _key() if a.judge == "qwenflash" else "none"
    cfg = sj.JUDGES[a.judge]
    base = a.endpoint.rstrip("/")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    budget = a.budget if a.budget is not None else BUDGET[a.judge]
    corpora = ["natural", "template"] if a.corpus == "both" else [a.corpus]
    reuse: dict[tuple[str, int], dict] = {}
    if a.reuse_raw is not None:
        for line in a.reuse_raw.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if r.get("judge") == a.judge and r.get("valid") and r.get("study") == "holdout_subgraph":
                    reuse[(r["cell_id"], r["repeat"])] = r
    summary = {"judge": a.judge, "label": JUDGE_LABEL[a.judge], "model": cfg["model"], "endpoint_host": "tunnel (local port)",
               **guard, "scorer_sha256": sha_file(ACCESS / "harness" / "review6_judges" / "score_judges.py"),
               "repeats": a.repeats, "workers": a.workers, "budget_prompt_tokens": budget, "corpora": {}, "started_utc": now()}
    t_all = time.monotonic()
    state = {"tokens": 0, "abort": None, "consec": 0}
    lock = threading.Lock()
    for corpus in corpora:
        jobs = sj.load_jobs(JOBS[corpus], None)  # re-verifies every prompt_sha256
        out = a.out_dir / f"raw_{a.judge}_{corpus}.jsonl"
        pre = sj.preflight(base, cfg["model"], jobs, MAXLEN[a.judge])
        (a.out_dir / f"raw_{a.judge}_{corpus}_preflight.json").write_text(json.dumps(pre, indent=1), encoding="utf-8")
        info = {"n_cells": len(jobs), "max_prompt_tokens": pre["max_prompt_tokens"], "sum_prompt_tokens_one_pass": pre["sum_prompt_tokens"],
                "over_context": pre["cells_over_context"]}
        summary["corpora"][corpus] = info
        print(json.dumps({corpus: info}), flush=True)
        if a.preflight_only:
            continue
        over = set(pre["cells_over_context"])
        todo_jobs = [j for j in jobs if j["cell_id"] not in over]
        done = sj.done_keys(out)
        progress = a.out_dir / f"raw_{a.judge}_{corpus}_progress.log"

        def log(msg):
            with progress.open("a", encoding="utf-8") as pf:
                pf.write(f"{now()} {a.judge} {corpus} {msg}\n")
            print(f"{now()} {a.judge} {corpus} {msg}", flush=True)

        n_reused = 0
        with out.open("a", encoding="utf-8") as fh:
            for j in todo_jobs:
                if corpus != "template":
                    continue
                for r in range(1, a.repeats + 1):
                    src = reuse.get((j["cell_id"], r))
                    if src and src.get("prompt_sha256") == j["prompt_sha256"] and (j["cell_id"], r) not in done:
                        rec = dict(src)
                        rec["reused_from_addendum26"] = True
                        rec["study"] = "template_subgraph"
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        done.add((j["cell_id"], r))
                        n_reused += 1
            for cid in sorted(over):
                if (cid, 0) not in done:
                    fh.write(json.dumps({"judge": a.judge, "study": jobs[0]["study"], "cell_id": cid, "repeat": 0, "status": "context_skip",
                                         "valid": False, "J": None, "note": "prompt + retry budget exceeds max_model_len"}) + "\n")
        info["reused_records"] = n_reused
        total = len(todo_jobs) * a.repeats
        calls = {"n": 0, "invalid": 0, "ctx": 0, "tin": 0, "tout": 0, "marks": set()}
        log(f"start cells={len(todo_jobs)} repeats={a.repeats} planned={total} already_done={len(done)} reused={n_reused} workers={a.workers}")

        def run(job, rep):
            with lock:
                if state["abort"]:
                    return None
                if state["tokens"] >= budget:
                    state["abort"] = "token_budget"
                    return None
            rec = sj.score_cell(base, a.judge, job, rep)
            rec["study"] = job["study"]
            rec["label"] = JUDGE_LABEL[a.judge]
            with lock:
                state["tokens"] += rec.get("prompt_tokens") or 0
                fe = rec.get("final_error") or {}
                endpoint_fail = rec["status"] == "context_skip" or (rec["status"] == "invalid" and fe.get("kind") in ("net", "http"))
                state["consec"] = state["consec"] + 1 if endpoint_fail else 0
                if state["consec"] >= CONSEC_FAIL_STOP:
                    state["abort"] = "consecutive_endpoint_failures"
            return rec

        with out.open("a", encoding="utf-8") as fh:
            for rep in range(1, a.repeats + 1):
                pending = [j for j in todo_jobs if (j["cell_id"], rep) not in done]
                random.Random(SEED + 1000 * rep).shuffle(pending)
                if not pending or state["abort"]:
                    continue
                log(f"repeat {rep}: {len(pending)} cells")
                with ThreadPoolExecutor(max_workers=a.workers) as pool:
                    for f in as_completed([pool.submit(run, j, rep) for j in pending]):
                        rec = f.result()
                        if rec is None:
                            continue
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        fh.flush()
                        calls["n"] += 1
                        calls["tin"] += rec.get("prompt_tokens") or 0
                        calls["tout"] += rec.get("completion_tokens") or 0
                        calls["invalid"] += rec["status"] == "invalid"
                        calls["ctx"] += rec["status"] == "context_skip"
                        for pct in (25, 50, 75, 100):
                            if calls["n"] * 100 >= total * pct and pct not in calls["marks"]:
                                calls["marks"].add(pct)
                                log(f"CHECKPOINT {pct}% calls={calls['n']}/{total} invalid={calls['invalid']} context_skip={calls['ctx']} "
                                    f"prompt_tokens={calls['tin']} completion_tokens={calls['tout']} elapsed_s={round(time.monotonic() - t_all)}")
        info.update({"calls": calls["n"], "invalid_records": calls["invalid"], "context_skip": calls["ctx"],
                     "prompt_tokens": calls["tin"], "completion_tokens": calls["tout"], "abort": state["abort"]})
        log(f"DONE calls={calls['n']} invalid={calls['invalid']} context_skip={calls['ctx']} abort={state['abort']} "
            f"prompt_tokens={calls['tin']} completion_tokens={calls['tout']}")
        if state["abort"]:
            break
    summary.update({"ended_utc": now(), "elapsed_s": round(time.monotonic() - t_all, 1), "abort_reason": state["abort"],
                    "prompt_tokens_total": state["tokens"]})
    (a.out_dir / f"MANIFEST_run_{a.judge}_{summary['started_utc'].replace(':', '')}.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
