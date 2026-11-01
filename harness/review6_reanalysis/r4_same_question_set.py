#!/usr/bin/env python3
"""R4  A->B on the SAME question set for the registered judge (Gemini J) and the substitute judge
(gpt-5.6-luna) under three input conditions: full view, truncated 60k-character view ('limited'),
question-relevant subgraph.  Post hoc, no new label, no LLM call (existing cells only).

Contrast: mean over shared questions of (score_B - score_A), one cell per (variant, question);
CQ-clustered BCa 95% (and 90%), seed 20260913, B = 10,000.  Two question sets are reported:
  per-judge set  : questions with a valid A cell and a valid B cell for THAT judge (23 for all but the subgraph view)
  strict common  : questions valid for ALL conditions simultaneously (identical 22 or fewer questions)
Valid = parsed score in 0..3 (the length-experiment convention, load_scores); the last valid record per cell wins.
Sources: harness/real_run/cells.jsonl (Gemini), harness/length_experiment/cells_length.jsonl (luna full-A,
limited, subgraph), harness/length_experiment/luna_full_r35/cells_luna_full_r35.jsonl (luna full B-F).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

OUT: dict = {"seed": C.SEED, "B": C.B, "post_hoc": True}

# ---- registered judge (Gemini), primary cells only
g = C.load_registered_J()
g = g[g.cell_kind == "primary"]
gem = {f"{r.variant}:{r.cq_id}": int(r.J) for r in g.itertuples() if C.valid_score(r._asdict() | {"J": r.J, "judge_response_parsed": r.judge_response_parsed})}
assert len(gem) == 188

# ---- substitute judge (luna)
len_rows = C.jsonl(C.P_LEN)
luna = {"limited": {}, "subgraph": {}, "full": {}}
n_invalid = {"limited": 0, "subgraph": 0, "full": 0}
for r in sorted(len_rows, key=lambda r: r["started_at_utc"]):
    if C.valid_score(r):
        luna[r["condition"]][r["pair_id"]] = int(r["J"])
    else:
        n_invalid[r["condition"]] += 1
for r in sorted(C.jsonl(C.P_LUNA_FULL), key=lambda r: r["started_at_utc"]):
    if C.valid_score(r):
        luna["full"][r["pair_id"]] = int(r["J"])
    else:
        n_invalid["full"] += 1
OUT["valid_counts"] = {"gemini_primary": len(gem), **{f"luna_{k}": len(v) for k, v in luna.items()},
                       "luna_invalid_records_skipped": n_invalid}

SOURCES = {"Gemini J (registered)": gem, "luna full": luna["full"], "luna limited (60k chars)": luna["limited"],
           "luna subgraph": luna["subgraph"]}


def series(src, v):
    return pd.Series({k.split(":")[1]: x for k, x in src.items() if k.startswith(v + ":")})


def contrast(src, restrict=None, v1="A", v2="B"):
    x, y = series(src, v1), series(src, v2)
    if restrict is not None:
        x, y = x.loc[[q for q in x.index if q in restrict]], y.loc[[q for q in y.index if q in restrict]]
    r = C.paired_delta(x, y)
    dif = np.array(r["diffs"])
    r["wilcoxon_p"] = C.wilcoxon_p(dif)
    r["signflip"] = C.signflip_exact_p(dif)
    sh = r["cqs"]
    r["mean_A_on_set"] = float(x.loc[sh].mean())
    r["mean_B_on_set"] = float(y.loc[sh].mean())
    r["share_Jge2_A"] = float((x.loc[sh] >= 2).mean())
    r["share_Jge2_B"] = float((y.loc[sh] >= 2).mean())
    r["direction"] = "B>A" if r["est"] > 0 else ("B<A" if r["est"] < 0 else "tie")
    r["ci95_excludes_0"] = bool(r["lo"] > 0 or r["hi"] < 0)
    r["n_questions"] = len(sh)
    cqs = list(sh)
    r.pop("diffs"), r.pop("cqs")
    r["_cqs"] = cqs
    return r


per_judge, sets = {}, {}
for name, src in SOURCES.items():
    r = contrast(src)
    sets[name] = set(r.pop("_cqs"))
    per_judge[name] = r
common = set.intersection(*sets.values())
OUT["per_judge_question_set"] = per_judge
OUT["strict_common_set"] = {"n_questions": len(common),
                            "questions_not_common": {n: sorted(sets[n] - common) for n in sets if sets[n] - common}}
OUT["strict_common_set"]["contrasts"] = {}
for name, src in SOURCES.items():
    r = contrast(src, restrict=common)
    r.pop("_cqs")
    OUT["strict_common_set"]["contrasts"][name] = r

# direction agreement across judges (per-judge set and strict common set)
for key, blk in (("per_judge_question_set", per_judge), ("strict_common_contrasts", OUT["strict_common_set"]["contrasts"])):
    dirs = {n: b["direction"] for n, b in blk.items()}
    OUT[f"direction_agreement_{key}"] = {"directions": dirs,
                                         "all_same_direction": len(set(dirs.values())) == 1,
                                         "n_judge_conditions_B_gt_A": sum(v == "B>A" for v in dirs.values()),
                                         "n_judge_conditions_ci95_excludes_0": sum(b["ci95_excludes_0"] for b in blk.values())}

# cell-level agreement of the A and B scores between Gemini and each luna condition (same cells), descriptive
agr = {}
for name in list(SOURCES)[1:]:
    src = SOURCES[name]
    ks = sorted(set(src) & set(gem))
    a = np.array([gem[k] for k in ks]); b = np.array([src[k] for k in ks])
    agr[name] = {"n_cells": len(ks), "mean_gemini": float(a.mean()), "mean_luna": float(b.mean()),
                 "mean_luna_minus_gemini": float((b - a).mean()), "exact_agreement": float((a == b).mean()),
                 "QWK": float(C.qwk_from_flat(C.conf_flat(a, b, 4)[None], 4)[0])}
OUT["cell_level_vs_gemini_descriptive"] = agr

json.dump(OUT, open(Path(__file__).resolve().parent / "parts/r4.json", "w"), indent=1, default=float)
for name, r in per_judge.items():
    print(f"{name:26s} n={r['n_questions']} delta {C.ci_str(r)} 90%[{r['lo90']:.3f},{r['hi90']:.3f}] up/down/tie {r['n_up']}/{r['n_down']}/{r['n_tie']} "
          f"meanA {r['mean_A_on_set']:.2f} meanB {r['mean_B_on_set']:.2f} wilcoxon {r['wilcoxon_p']:.3f} signflip {r['signflip']['p_two_sided']:.4f}")
print("strict common n =", len(common), OUT["strict_common_set"]["questions_not_common"])
for name, r in OUT["strict_common_set"]["contrasts"].items():
    print(f"  common {name:26s} delta {C.ci_str(r)} up/down/tie {r['n_up']}/{r['n_down']}/{r['n_tie']} signflip {r['signflip']['p_two_sided']:.4f}")
print(OUT["direction_agreement_per_judge_question_set"])
print(OUT["cell_level_vs_gemini_descriptive"])
