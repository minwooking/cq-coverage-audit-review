#!/usr/bin/env python3
"""R3  Full-bank (36 questions; ineligible cells counted as NOT covered, score 0) versus the registered
eligible-only coverage, and the A->B contrast under each.  Post hoc, no new label.

Eligibility is the registered one (analyze_holdout.REGISTERED_EXCLUDED_CQS; PREREG sec.6-2):
  variant A: 23 of 36 questions eligible (13 corpus-rare questions excluded);
  variants B-F: 33 of 36 (3 excluded: CQB15, CQB22, CQB23).
Scores: J (judge), L1* on the AH labels, L1* on the second rater's labels.
Full-bank-0 : coverage = sum(L) / (36 * 3), ineligible cells = 0   (the requested reading; a LOWER bound)
Full-bank-3 : ineligible cells = 3 (fully covered)                 (the matching UPPER bound, sensitivity only)
Eligible-only: the registered reading (A over 23, B-F over 33).
Interval: BCa over question clusters (36 for full-bank; 33 / 23 for eligible-only), seed 20260913, B = 10,000.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

d = C.load_188()
BANK = list(C.ah.REGISTERED_BANK_CQ_IDS)
EXC = C.ah.REGISTERED_EXCLUDED_CQS
assert len(BANK) == 36
OUT: dict = {"seed": C.SEED, "B": C.B, "post_hoc": True,
             "excluded_cqs": {"A": sorted(EXC["A"]), "B-F": sorted(EXC["B"])},
             "n_eligible": {"A": 23, "B-F": 33}, "n_bank": 36}

SC = {"J": "J", "L1star_AH": "L1star_AH", "L1star_second_rater": "L1star_2"}


def full_frame(col, fill):
    rows = []
    idx = d.set_index(["variant", "cq_id"])[col]
    for v in C.VARIANTS:
        for q in BANK:
            elig = q not in EXC[v]
            if elig:
                val = float(idx.loc[(v, q)])
            else:
                val = float(fill)
            rows.append({"variant": v, "cq_id": q, "cluster_id": q, "val": val, "eligible": elig})
    return pd.DataFrame(rows)


def cov_ci(sub):
    s = sub.assign(_n=1.0)
    M, _ = C.cluster_matrix(s, ["val", "_n"])
    r = C.fast_bca(M, lambda t: t[:, 0] / t[:, 1] / 3 * 100)
    r["n_cells"] = len(sub)
    return r


def contrast(fr, which):
    x = fr[fr.variant == "A"].set_index("cq_id").val
    y = fr[fr.variant == "B"].set_index("cq_id").val
    if which == "eligible":
        keep = [q for q in BANK if q not in EXC["A"] and q not in EXC["B"]]
        x, y = x.loc[keep], y.loc[keep]
    r = C.paired_delta(x, y)
    dif = np.array(r["diffs"])
    r["wilcoxon_p"] = C.wilcoxon_p(dif)
    r["signflip"] = C.signflip_exact_p(dif)
    r["delta_coverage_pp"] = r["est"] / 3 * 100
    r["ci95_excludes_0"] = bool(r["lo"] > 0 or r["hi"] < 0)
    r["tost_90ci_within_pm0.30"] = bool(r["lo90"] >= -0.30 and r["hi90"] <= 0.30)
    r.pop("diffs"), r.pop("cqs")
    return r


for name, col in SC.items():
    f0 = full_frame(col, 0)
    f3 = full_frame(col, 3)
    blk = {"coverage_pct_by_variant": {}, "A_to_B": {}}
    for v in C.VARIANTS:
        elig = f0[(f0.variant == v) & f0.eligible]
        blk["coverage_pct_by_variant"][v] = {
            "eligible_only": cov_ci(elig),
            "full_bank_0": cov_ci(f0[f0.variant == v]),
            "full_bank_3_upper_bound": cov_ci(f3[f3.variant == v]),
        }
    blk["A_to_B"]["eligible_only_23_registered"] = contrast(f0, "eligible")
    blk["A_to_B"]["full_bank_36_ineligible_0"] = contrast(f0, "full")
    blk["A_to_B"]["full_bank_36_ineligible_3_upper_bound"] = contrast(f3, "full")
    # decomposition of the full-bank-0 A->B delta: shared eligible (23) part and the 10 A-only-ineligible questions
    a_only = [q for q in BANK if q in EXC["A"] and q not in EXC["B"]]
    both = [q for q in BANK if q in EXC["A"] and q in EXC["B"]]
    x = f0[f0.variant == "A"].set_index("cq_id").val
    y = f0[f0.variant == "B"].set_index("cq_id").val
    blk["decomposition_full_bank_0_sum_of_differences"] = {
        "questions_ineligible_in_A_only": len(a_only), "questions_ineligible_in_all_variants": len(both),
        "sum_diff_on_23_shared": float((y - x).loc[[q for q in BANK if q not in EXC["A"] and q not in EXC["B"]]].sum()),
        "sum_diff_on_A_only_ineligible": float((y - x).loc[a_only].sum()),
        "mean_B_score_on_A_only_ineligible_questions": float(y.loc[a_only].mean()),
        "note": "A-only-ineligible questions contribute B's whole score as 'gain' because A is set to 0 there."}
    OUT[name] = blk
    for k, r in blk["A_to_B"].items():
        print(f"{name:22s} {k:42s} delta {C.ci_str(r)}  up/down/tie {r['n_up']}/{r['n_down']}/{r['n_tie']} n={r['n_pairs']} "
              f"cov {r['delta_coverage_pp']:.1f}pp wilcoxon {r['wilcoxon_p']:.3f} signflip {r['signflip']['p_two_sided']:.4f}")
    print("   coverage", {v: (round(blk['coverage_pct_by_variant'][v]['eligible_only']['est'], 1),
                              round(blk['coverage_pct_by_variant'][v]['full_bank_0']['est'], 1),
                              round(blk['coverage_pct_by_variant'][v]['full_bank_3_upper_bound']['est'], 1)) for v in C.VARIANTS})

json.dump(OUT, open(Path(__file__).resolve().parent / "parts/r3.json", "w"), indent=1, default=float)
