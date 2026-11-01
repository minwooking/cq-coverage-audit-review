#!/usr/bin/env python3
"""Calls, latency and estimated tokens for the LLM-judge runs (round 25, S13).

Reads only logged files; computes nothing about money.  Tokens are ESTIMATED as
ceil(characters / 4) unless a run logged response `usage` fields (the 48-cell paired audit).
Run:  python3 harness/cost_latency/cost_latency.py   (writes cost_latency.json next to it)
"""
from __future__ import annotations
import csv, json, statistics as st, sys
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
H = HERE.parent                       # harness/
ACC = H.parent                        # paper/access2026
sys.path.insert(0, str(H))
import run_holdout as rh              # RUBRIC constant (judge system prompt)

def P(s): return datetime.fromisoformat(s)
def jl(p): return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines() if l.strip()]
def est(chars): return -(-chars // 4)
def lat(xs):
    xs = sorted(xs)
    return {"n": len(xs), "sum_s": round(sum(xs), 1), "mean_s": round(sum(xs) / len(xs), 2),
            "median_s": round(st.median(xs), 2), "max_s": round(xs[-1], 1)}

out = {}

# ---- 1. holdout (gemini-3.6-flash), 224 cells -------------------------------------------------
cells = jl(H / "real_run/cells.jsonl")
man = json.loads((H / "real_run/MANIFEST.json").read_text(encoding="utf-8"))
qs = {r["cq_id"]: r["question"] for r in csv.DictReader((ACC / "bank/cq_bank_brick_v1.csv").open(encoding="utf-8", newline=""))}
view_chars = {v: len((H / f"variants/{v}/rendered_view.txt").read_text(encoding="utf-8")) for v in "ABCDEF"}
overhead = lambda q: len(rh.RUBRIC) + len("ARTIFACT:\n") + len("\n\nQUESTION: ") + len(q)
chars_one = sum(view_chars[c["variant"]] + overhead(qs[c["cq_id"]]) for c in cells)          # one request per cell
chars_att = sum(c["attempt"] * (view_chars[c["variant"]] + overhead(qs[c["cq_id"]])) for c in cells)
starts = [P(c["started_at_utc"]) for c in cells]
end = P(man["generated_utc"])
wall = (end - min(starts)).total_seconds()
out["holdout"] = {
    "judge": man["judge_model"], "cells": len(cells), "attempt_hist": dict(sorted(Counter(c["attempt"] for c in cells).items())),
    "calls_logged_attempts": sum(c["attempt"] for c in cells), "cells_with_retry": sum(c["attempt"] > 1 for c in cells),
    "all_parsed": all(c["judge_response_parsed"] for c in cells),
    "latency": lat([c["elapsed_s"] for c in cells]),
    "start_utc": min(starts).isoformat(), "end_utc_manifest": man["generated_utc"], "wall_s": round(wall, 1),
    "concurrency": "4 (code default JUDGE_CONCURRENCY; not recorded in the manifest)",
    "est_input_chars_one_request_per_cell": chars_one, "est_input_tokens_one_request_per_cell": est(chars_one),
    "est_input_tokens_attempt_weighted": est(chars_att),
    "view_chars": view_chars, "rubric_chars": len(rh.RUBRIC),
    "note": "elapsed_s is the logged per-cell value; transport-level retries (HTTP 429 backoff) are not counted in `attempt`; view size used for ablated controls (24 cells) is the unablated view (upper bound)",
    "usage_logged": False,
}

# ---- 2. length experiment (gpt-5.6-luna), 393 calls --------------------------------------------
L = H / "length_experiment"
lm = json.loads((L / "MANIFEST_length.json").read_text(encoding="utf-8"))
lc = jl(L / "cells_length.jsonl")
by = {}
for c in lc: by.setdefault(c["condition"], []).append(c)
out["length"] = {
    "judge": lm["judge_model"], "calls_manifest": lm["calls_this_run"], "rows": len(lc),
    "invalid_unparsed": sum(not c["judge_response_parsed"] for c in lc),
    "latency": lat([c["elapsed_s"] for c in lc]),
    "wall_s": lm["elapsed_s"], "workers": lm["workers"], "start_utc": lm["started_utc"], "end_utc": lm["ended_utc"],
    "est_input_tokens_manifest": lm["est_input_tokens_this_run"], "est_input_tokens_rows": sum(c["est_input_tokens"] for c in lc),
    "attempt_hist": dict(Counter(c["attempt"] for c in lc)),
    "by_condition": {k: {"calls": len(v), "latency": lat([c["elapsed_s"] for c in v]),
                         "est_input_tokens": sum(c["est_input_tokens"] for c in v)} for k, v in sorted(by.items())},
    "usage_logged": False,
}

# ---- 3. paired 48-cell audit (luna + sonnet), usage logged -------------------------------------
A = H / "real_run/paired_ai_audit_48"
out["paired48"] = {}
for d in ("gpt-5.6-luna", "anthropic__claude-sonnet-5-5"):
    m = json.loads((A / d / "run_manifest.json").read_text(encoding="utf-8"))
    cs = jl(A / d / "cells.jsonl"); fs = jl(A / d / "failures.jsonl")
    inv = m["invocations"]
    wall = sum((P(i["finished_utc"]) - P(i["started_utc"])).total_seconds() for i in inv)
    tok = m["tokens_all_invocations"]
    sj = [c["second_judge"]["usage"] for c in cs]
    out["paired48"][d] = {
        "judge": m["model_requested"], "cells_scored": len(cs), "failed_attempts": len(fs),
        "failed_by_class": dict(Counter(f["error_class"] for f in fs)),
        "calls": len(cs) + len(fs), "invocations": len(inv),
        "workers_per_invocation": [i["workers"] for i in inv],
        "latency_scored": lat([c["elapsed_s"] for c in cs]),
        "wall_s_sum_of_invocations": round(wall, 1),
        "usage_all_invocations": tok,
        "usage_scored_cells_prompt": sum(u["prompt_tokens"] for u in sj),
        "usage_scored_cells_completion": sum(u["completion_tokens"] for u in sj),
        "usage_logged": True,
    }

# estimate-vs-usage check on the 48 paired cells (the only cells where both exist)
lu = jl(A / "gpt-5.6-luna/cells.jsonl")
e48 = est(sum(view_chars[c["variant"]] + overhead(qs[c["cq_id"]]) for c in lu))
out["paired48_estimate_check"] = {
    "est_input_tokens_48_cells_chars_over_4": e48,
    "actual_prompt_tokens_luna_scored_cells": out["paired48"]["gpt-5.6-luna"]["usage_scored_cells_prompt"],
    "actual_prompt_tokens_sonnet_scored_cells": out["paired48"]["anthropic__claude-sonnet-5-5"]["usage_scored_cells_prompt"],
    "ratio_luna": round(out["paired48"]["gpt-5.6-luna"]["usage_scored_cells_prompt"] / e48, 3),
    "ratio_sonnet": round(out["paired48"]["anthropic__claude-sonnet-5-5"]["usage_scored_cells_prompt"] / e48, 3),
}
out["length"]["est_input_tokens_valid_calls_only"] = lm["est_input_tokens_this_run"]
out["length"]["est_input_tokens_all_calls"] = sum(c["est_input_tokens"] for c in lc)

(HERE / "cost_latency.json").write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(out, indent=1, ensure_ascii=False))
