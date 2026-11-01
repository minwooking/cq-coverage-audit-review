#!/usr/bin/env python3
"""R1  Over- vs under-credit per variant and overall (post hoc, no new label, no LLM call).

Definitions (fixed before looking at any new quantity; PREREG sec.1.1 estimand unchanged):
  S = binary support label (AH label A, or the second rater's S);  R = rater 0-3 score (rater_L1 / R_2).
  Ordinal: over = [J > R], under = [J < R], equal = [J == R]; mean(J - R).  R >= 1 on every cell
           (no rater ever scored 0), so each J = 0 cell is mechanically 'under' (floor).
  Binary : over  = [J >= 2 and S = 0]   (= the registered pi events, 14 on the AH labels)
           under = [J <= 1 and S = 1]   (20 on the AH labels); split by J = 0 / J = 1.
  Denominator: every cell of the stratum (variant, or all 188 primary cells).
Interval: CQ-clustered BCa 95%, B = 10,000, seed 20260913 (as the analyzer).
Net = over - under rate; negative = the judge is stingier than the label source on net.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

d = C.load_188()
OUT: dict = {"seed": C.SEED, "B": C.B, "population": "188 primary cells, 33 CQ clusters (A 23, B-F 33)",
             "post_hoc": True, "denominator": "all cells in the stratum"}


def ratio(sub, num, den="_n"):
    M, _ = C.cluster_matrix(sub, [num, den])
    return C.fast_bca(M, lambda s: s[:, 0] / s[:, 1])


def block(sub, S, R, tag):
    s = sub.copy()
    s["_n"] = 1.0
    J = s.J
    s["_over_ord"] = (J > s[R]).astype(float)
    s["_under_ord"] = (J < s[R]).astype(float)
    s["_eq_ord"] = (J == s[R]).astype(float)
    s["_jmr"] = (J - s[R]).astype(float)
    s["_J"] = J.astype(float)
    s["_R"] = s[R].astype(float)
    s["_abs"] = (J - s[R]).abs().astype(float)
    s["_over_bin"] = ((J >= 2) & (s[S] == 0)).astype(float)
    s["_under_bin"] = ((J <= 1) & (s[S] == 1)).astype(float)
    s["_under_bin_J0"] = ((J == 0) & (s[S] == 1)).astype(float)
    s["_under_bin_J1"] = ((J == 1) & (s[S] == 1)).astype(float)
    s["_net_bin"] = s["_over_bin"] - s["_under_bin"]
    n = len(s)
    out = {"n_cells": n, "n_clusters": int(s.cq_id.nunique())}
    out["ordinal"] = {
        "mean_J": ratio(s, "_J"), "mean_R": ratio(s, "_R"),
        "mean_J_minus_R": ratio(s, "_jmr"),
        "n_over_J_gt_R": int(s._over_ord.sum()), "n_under_J_lt_R": int(s._under_ord.sum()),
        "n_equal": int(s._eq_ord.sum()),
        "rate_over": ratio(s, "_over_ord"), "rate_under": ratio(s, "_under_ord"),
        "MAE": ratio(s, "_abs"),
        "n_under_at_J0": int(((J == 0) & (s[R] > J)).sum()),
        "n_under_J_ge1": int(((J >= 1) & (s[R] > J)).sum()),
    }
    ob, ub = int(s._over_bin.sum()), int(s._under_bin.sum())
    # exact sign (binomial) test on the discordant cells; cell level, ignores clustering (flagged)
    p_cell = binomtest(min(ob, ub), ob + ub, 0.5).pvalue if ob + ub else None
    # cluster-level sign test: per CQ net count (over - under)
    net = s.groupby("cq_id")._net_bin.sum()
    n_pos, n_neg = int((net > 0).sum()), int((net < 0).sum())
    p_cl = binomtest(min(n_pos, n_neg), n_pos + n_neg, 0.5).pvalue if n_pos + n_neg else None
    out["binary_support"] = {
        "n_over_J_ge2_S0": ob, "n_under_J_le1_S1": ub,
        "n_under_J0_S1": int(s._under_bin_J0.sum()), "n_under_J1_S1": int(s._under_bin_J1.sum()),
        "rate_over": ratio(s, "_over_bin"), "rate_under": ratio(s, "_under_bin"),
        "net_rate_over_minus_under": ratio(s, "_net_bin"),
        "under_to_over_ratio": (ub / ob) if ob else None,
        "exact_sign_p_cell_level_two_sided": p_cell,
        "cluster_level_sign_test": {"questions_net_over": n_pos, "questions_net_under": n_neg,
                                    "p_two_sided": p_cl},
        "share_S1": float((s[S] == 1).mean()), "share_J_ge2": float((J >= 2).mean()),
    }
    # counts of the four binary cells (J>=2 x S)
    out["binary_support"]["table"] = {"Jge2_S1": int(((J >= 2) & (s[S] == 1)).sum()), "Jge2_S0": ob,
                                      "Jle1_S1": ub, "Jle1_S0": int(((J <= 1) & (s[S] == 0)).sum())}
    return out


for src, S, R in (("AH", "S_AH", "R_AH"), ("second_rater", "S_2", "R_2")):
    OUT[src] = {"overall": block(d, S, R, src)}
    OUT[src]["by_variant"] = {v: block(d[d.variant == v], S, R, src) for v in C.VARIANTS}
    # variant-level sign pattern of the net binary rate
    nets = {v: OUT[src]["by_variant"][v]["binary_support"]["net_rate_over_minus_under"]["est"] for v in C.VARIANTS}
    OUT[src]["variants_with_net_under"] = [v for v, x in nets.items() if x < 0]
    OUT[src]["variants_with_net_over"] = [v for v, x in nets.items() if x > 0]
    OUT[src]["variants_net_zero"] = [v for v, x in nets.items() if x == 0]

# J vs S-based coverage: the registered L1* withdraws only; 'mean J vs mean L1*' is the withdrawn mass
d["_n"] = 1.0
d["_withdrawn"] = (d.J - d.L1star_AH).astype(float)
d["_withdrawn2"] = (d.J - d.L1star_2).astype(float)
OUT["withdrawn_mass_J_minus_L1star"] = {
    "AH": ratio(d, "_withdrawn"), "second_rater": ratio(d, "_withdrawn2"),
    "note": "mean(J - L1*) is the average credit the withdraw-only correction removes per cell (rubric points); "
            "it is non-negative by construction, so L1* can never move toward a more generous rater."}

json.dump(OUT, open(Path(__file__).resolve().parent / "parts/r1.json", "w"), indent=1, default=float)


def f(r, nd=3, sc=1.0):
    return C.ci_str(r, nd, sc)


o = OUT["AH"]["overall"]
print("AH overall ordinal: meanJ", f(o["ordinal"]["mean_J"]), "meanR", f(o["ordinal"]["mean_R"]), "J-R", f(o["ordinal"]["mean_J_minus_R"]))
print("  over/under/equal", o["ordinal"]["n_over_J_gt_R"], o["ordinal"]["n_under_J_lt_R"], o["ordinal"]["n_equal"])
b = o["binary_support"]
print("AH binary over", b["n_over_J_ge2_S0"], f(b["rate_over"], 4), "under", b["n_under_J_le1_S1"], f(b["rate_under"], 4),
      "net", f(b["net_rate_over_minus_under"], 4), "p_cell", b["exact_sign_p_cell_level_two_sided"], b["cluster_level_sign_test"])
for v in C.VARIANTS:
    x = OUT["AH"]["by_variant"][v]
    print(v, "ord J-R", f(x["ordinal"]["mean_J_minus_R"], 3), "bin over/under", x["binary_support"]["n_over_J_ge2_S0"],
          x["binary_support"]["n_under_J_le1_S1"], "net", f(x["binary_support"]["net_rate_over_minus_under"], 3))
o = OUT["second_rater"]["overall"]
b = o["binary_support"]
print("2nd overall J-R", f(o["ordinal"]["mean_J_minus_R"]), "bin over/under", b["n_over_J_ge2_S0"], b["n_under_J_le1_S1"],
      "net", f(b["net_rate_over_minus_under"], 4), "p", b["exact_sign_p_cell_level_two_sided"])
for v in C.VARIANTS:
    x = OUT["second_rater"]["by_variant"][v]
    print(" 2nd", v, x["binary_support"]["n_over_J_ge2_S0"], x["binary_support"]["n_under_J_le1_S1"], f(x["ordinal"]["mean_J_minus_R"], 3))
print("withdrawn", f(OUT["withdrawn_mass_J_minus_L1star"]["AH"]), f(OUT["withdrawn_mass_J_minus_L1star"]["second_rater"]))
