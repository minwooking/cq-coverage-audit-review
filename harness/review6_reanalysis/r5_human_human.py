#!/usr/bin/env python3
"""R5  Human-human reference for the gate thresholds, on the SAME 188 primary cells.

Pairs (rows = first rater):
  JH_AH  judge J        vs AH rater score R_AH         (G4 QWK 0.500, G5 MAE 0.793 as registered)
  JH_2   judge J        vs second rater score R_2      (post hoc; second rater saw the judge's span)
  HH     AH R_AH        vs second rater R_2            (human-human; R is a function of S for the second rater)
Statistics, each CQ-clustered BCa 95% (seed 20260913, B = 10,000): MAE, exact agreement, quadratic-weighted kappa
(rubric levels 0..3), and on the binary support call  [J>=2] / S_AH / S_2: Cohen kappa, Gwet AC1, PABAK,
raw agreement.  Paired differences between the pairs (same resamples) show whether the judge-human gap
exceeds the human-human gap.  Registered bars quoted for orientation only (not re-adjudicated here):
  G4: not falsified unless the QWK CI upper limit < 0.60;  G5: needs MAE CI upper limit <= 0.50.
Caveats carried into the report: the AH rater consulted an LLM on about half the cells and saw an AI draft;
the second rater saw the judge's quoted span; neither R has a 0 (floor R >= 1); the second rater's R is
a function of S (R = 1 or 2 only when S = 0, 2 or 3 only when S = 1) so R-based statistics repeat S.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

d = C.load_188()
K = 4
OUT: dict = {"seed": C.SEED, "B": C.B, "post_hoc": True, "n_cells": 188, "n_clusters": 33}


def add_flat(df, a, b, prefix, k):
    flat = np.zeros((len(df), k * k))
    for i, (x, y) in enumerate(zip(df[a].to_numpy(), df[b].to_numpy())):
        flat[i, int(x) * k + int(y)] = 1
    for j in range(k * k):
        df[f"{prefix}{j}"] = flat[:, j]
    return [f"{prefix}{j}" for j in range(k * k)]


d["Jbin"] = (d.J >= 2).astype(int)
cols = {}
cols["JH_AH"] = add_flat(d, "J", "R_AH", "a", K)
cols["JH_2"] = add_flat(d, "J", "R_2", "b", K)
cols["HH"] = add_flat(d, "R_AH", "R_2", "c", K)
cols["bin_J_AH"] = add_flat(d, "Jbin", "S_AH", "e", 2)
cols["bin_J_2"] = add_flat(d, "Jbin", "S_2", "f", 2)
cols["bin_AH_2"] = add_flat(d, "S_AH", "S_2", "g", 2)
allcols = sum(cols.values(), [])
M, _ = C.cluster_matrix(d, allcols)
pos = {}
o = 0
for k, v in cols.items():
    pos[k] = slice(o, o + len(v))
    o += len(v)


def stat(key, what, k=K):
    sl = pos[key]
    if what == "mae":
        return lambda s: C.mae_from_flat(s[:, sl], k)
    if what == "exact":
        return lambda s: C.exact_from_flat(s[:, sl], k)
    if what == "qwk":
        return lambda s: C.qwk_from_flat(s[:, sl], k)
    return lambda s: C.bin_stats_from_flat(s[:, sl])[what]


ord_pairs = {"JH_AH": "judge vs AH rater score", "JH_2": "judge vs second rater score", "HH": "AH vs second rater (human-human)"}
OUT["ordinal_0_3"] = {}
for key, lab in ord_pairs.items():
    OUT["ordinal_0_3"][key] = {"label": lab, **{w: C.fast_bca(M, stat(key, w)) for w in ("mae", "exact", "qwk")}}
OUT["binary_support"] = {}
for key, lab in {"bin_J_AH": "[J>=2] vs S_AH (judge-AH)", "bin_J_2": "[J>=2] vs S_2 (judge-second rater)",
                 "bin_AH_2": "S_AH vs S_2 (human-human)"}.items():
    OUT["binary_support"][key] = {"label": lab,
                                  **{w: C.fast_bca(M, stat(key, w)) for w in ("agreement", "kappa", "ac1", "pabak")}}
    tab = M[:, pos[key]].sum(0).astype(int).tolist()
    OUT["binary_support"][key]["table_n00_n01_n10_n11"] = tab

# paired differences between pairs (same resamples): judge-human minus human-human
def diff_stat(k1, k2, w):
    f1, f2 = stat(k1, w), stat(k2, w)
    return lambda s: f1(s) - f2(s)


OUT["paired_differences"] = {}
for w in ("mae", "exact", "qwk"):
    OUT["paired_differences"][f"{w}: judge-AH minus human-human"] = C.fast_bca(M, diff_stat("JH_AH", "HH", w))
    OUT["paired_differences"][f"{w}: judge-second rater minus human-human"] = C.fast_bca(M, diff_stat("JH_2", "HH", w))
for w in ("kappa", "ac1", "pabak"):
    OUT["paired_differences"][f"binary {w}: judge-AH minus human-human"] = C.fast_bca(M, diff_stat("bin_J_AH", "bin_AH_2", w))
    OUT["paired_differences"][f"binary {w}: judge-second rater minus human-human"] = C.fast_bca(M, diff_stat("bin_J_2", "bin_AH_2", w))

# threshold orientation (registered bars; observation only)
hh = OUT["ordinal_0_3"]["HH"]
OUT["threshold_orientation"] = {
    "G5_bar_MAE_upper_limit_le": 0.50,
    "human_human_MAE": hh["mae"], "human_human_MAE_upper_limit": hh["mae"]["hi"],
    "human_human_MAE_would_pass_G5_bar": bool(hh["mae"]["hi"] <= 0.50),
    "G4_bar_QWK_upper_limit_lt": 0.60,
    "human_human_QWK": hh["qwk"], "human_human_QWK_upper_limit": hh["qwk"]["hi"],
    "human_human_QWK_not_falsified_by_G4_rule": bool(hh["qwk"]["hi"] >= 0.60),
    "judge_AH_MAE_upper_limit": OUT["ordinal_0_3"]["JH_AH"]["mae"]["hi"],
    "judge_AH_QWK_upper_limit": OUT["ordinal_0_3"]["JH_AH"]["qwk"]["hi"],
    "note": "the bars are those of PREREG sec.2 (G4 falsification-only, G5); this block only places the "
            "human-human values beside them and does not change any gate status"}

# descriptive: signed gap and the R floor
OUT["descriptives"] = {
    "mean_J": float(d.J.mean()), "mean_R_AH": float(d.R_AH.mean()), "mean_R_2": float(d.R_2.mean()),
    "R_AH_counts": {int(k): int(v) for k, v in d.R_AH.value_counts().sort_index().items()},
    "R_2_counts": {int(k): int(v) for k, v in d.R_2.value_counts().sort_index().items()},
    "J_counts": {int(k): int(v) for k, v in d.J.value_counts().sort_index().items()},
    "HH_signed_mean_R2_minus_RAH": float((d.R_2 - d.R_AH).mean()),
    "HH_n_exact": int((d.R_AH == d.R_2).sum()),
    "HH_abs_diff_counts": {int(k): int(v) for k, v in (d.R_AH - d.R_2).abs().value_counts().sort_index().items()},
    "R2_is_function_of_S2": bool(((d.S_2 == 1) & (d.R_2 >= 2)).sum() + ((d.S_2 == 0) & (d.R_2 <= 2)).sum() == len(d)),
}

json.dump(OUT, open(Path(__file__).resolve().parent / "parts/r5.json", "w"), indent=1, default=float)


def f(r, nd=3):
    return C.ci_str(r, nd)


for k, v in OUT["ordinal_0_3"].items():
    print(f"{k:6s} MAE {f(v['mae'])}  exact {f(v['exact'])}  QWK {f(v['qwk'])}")
for k, v in OUT["binary_support"].items():
    print(f"{k:9s} agree {f(v['agreement'])} kappa {f(v['kappa'])} AC1 {f(v['ac1'])} PABAK {f(v['pabak'])} table {v['table_n00_n01_n10_n11']}")
for k, v in OUT["paired_differences"].items():
    print(f"  {k:60s} {f(v)}")
print(OUT["threshold_orientation"]["human_human_MAE_would_pass_G5_bar"], OUT["threshold_orientation"]["human_human_QWK_upper_limit"])
print(OUT["descriptives"])
