#!/usr/bin/env python3
"""R2  Two-sided (symmetric) correction alternatives to the withdraw-only L1*, and A->B under each;
sign-flip permutation p for A->B under J, L1*, and the symmetric versions.  Post hoc, no new label.

Estimators on the 0-3 rubric scale (coverage % = mean/3 * 100), per label source (AH; second rater):
  J        judge score, uncorrected
  L1*      registered, withdraw-only:  J if S=1 else min(J,1)
  L_flip   two-sided support correction:  S=1 -> max(J,2);  S=0 -> min(J,1)
           (adds credit when the label source finds support and the judge gave <2; removes it as L1* does)
  L_R      label replaces judge:  the rater's 0-3 score R where a label exists (here: all 188 cells)
Binary support scale (share of cells whose answer evidence is supported):
  Rogan-Gladen correction of the judge's [J>=2] rate:  p_RG = (p_J + Sp - 1) / (Se + Sp - 1)
  with Se = P(J>=2 | S=1), Sp = P(J<=1 | S=0) estimated (a) in sample on all 188 cells and (b) on C-F only
  (variants not entering the contrast), re-estimated inside every bootstrap resample.
PPI-style label-budget scenario: PPI estimate of mean(R_B - R_A) using J_B - J_A as the prediction,
  labelled on m of the 23 paired questions, vs the labelled-only mean; Monte Carlo over random label subsets.
Contrast: A->B over the 23 questions both variants share (one cell per question), CQ-clustered BCa 95% and
90% (TOST, margin +-0.30), Wilcoxon (zeros dropped) and EXACT two-sided sign-flip permutation p.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

d = C.load_188()
OUT: dict = {"seed": C.SEED, "B": C.B, "post_hoc": True,
             "unit_of_resampling": "question (CQ) cluster; one cell per question per variant"}

SRC = {"AH": ("S_AH", "R_AH"), "second_rater": ("S_2", "R_2")}


def add_estimators(df, S, R):
    df = df.copy()
    df["e_J"] = df.J
    df["e_L1star"] = np.where(df[S] == 1, df.J, np.minimum(df.J, 1))
    df["e_Lflip"] = np.where(df[S] == 1, np.maximum(df.J, 2), np.minimum(df.J, 1))
    df["e_LR"] = df[R]
    return df


EST = ["e_J", "e_L1star", "e_Lflip", "e_LR"]
EST_NAME = {"e_J": "J", "e_L1star": "L1* (withdraw-only)", "e_Lflip": "L_flip (two-sided support)", "e_LR": "L_R (rater score)"}


def contrast(df, col, v1="A", v2="B"):
    x = df[df.variant == v1].set_index("cq_id")[col]
    y = df[df.variant == v2].set_index("cq_id")[col]
    r = C.paired_delta(x, y)
    dif = np.array(r["diffs"])
    r["wilcoxon_p"] = C.wilcoxon_p(dif)
    r["signflip"] = C.signflip_exact_p(dif)
    r["tost_90ci_within_pm0.30"] = bool(r["lo90"] >= -0.30 and r["hi90"] <= 0.30)
    r["ci95_excludes_0"] = bool(r["lo"] > 0 or r["hi"] < 0)
    r["delta_coverage_pp"] = r["est"] / 3 * 100
    r["coverage_A_pct_on_23"] = float(x.loc[r["cqs"]].sum() / (3 * len(r["cqs"])) * 100)
    r["coverage_B_pct_on_23"] = float(y.loc[r["cqs"]].sum() / (3 * len(r["cqs"])) * 100)
    r.pop("diffs"), r.pop("cqs")
    return r


for src, (S, R) in SRC.items():
    df = add_estimators(d, S, R)
    blk = {"contrast_A_to_B_23_questions": {}, "coverage_by_variant_pct": {}}
    for e in EST:
        blk["contrast_A_to_B_23_questions"][EST_NAME[e]] = contrast(df, e)
    for e in EST:
        blk["coverage_by_variant_pct"][EST_NAME[e]] = {}
        for v in C.VARIANTS:
            sub = df[df.variant == v].assign(_n=1.0, _x=lambda t, e=e: t[e].astype(float))
            M, _ = C.cluster_matrix(sub, ["_x", "_n"])
            r = C.fast_bca(M, lambda s: s[:, 0] / s[:, 1] / 3 * 100)
            r["n_cells"] = len(sub)
            blk["coverage_by_variant_pct"][EST_NAME[e]][v] = r
    # paired difference between estimators on A->B: (symmetric) - (withdraw-only); same resamples
    xA = df[df.variant == "A"].set_index("cq_id")
    xB = df[df.variant == "B"].set_index("cq_id")
    sh = sorted(set(xA.index) & set(xB.index))
    blk["A_to_B_shift_vs_L1star"] = {}
    for e in ("e_J", "e_Lflip", "e_LR"):
        dd = ((xB.loc[sh, e] - xA.loc[sh, e]) - (xB.loc[sh, "e_L1star"] - xA.loc[sh, "e_L1star"]))
        r = C.paired_delta(xA.loc[sh, "e_L1star"] * 0, dd)   # mean of dd via the paired helper (x = 0)
        r.pop("diffs"), r.pop("cqs")
        blk["A_to_B_shift_vs_L1star"][EST_NAME[e]] = r
    OUT[src] = blk

# ------------------------------------------------------------------ Rogan-Gladen on the binary support scale
def rg_contrast(df, S, calib_variants):
    """RG-corrected contrast B - A of the supported share over the 23 shared questions.
    Per-cluster additive vector: [A_Jpos, B_Jpos, n_pairs, TP, FN, FP, TN] (calibration cells from
    `calib_variants`; pair cells from A and B on the shared questions).  Se, Sp re-estimated per resample."""
    A = d[d.variant == "A"].set_index("cq_id")
    Bv = d[d.variant == "B"].set_index("cq_id")
    sh = sorted(set(A.index) & set(Bv.index))
    cal = d[d.variant.isin(calib_variants)]
    rows = []
    for q in sorted(d.cq_id.unique(), key=str):
        r = np.zeros(7)
        if q in sh:
            r[0] = float(A.loc[q, "J"] >= 2)
            r[1] = float(Bv.loc[q, "J"] >= 2)
            r[2] = 1.0
        c = cal[cal.cq_id == q]
        jpos = (c.J >= 2)
        sp = (c[S] == 1)
        r[3] = float((jpos & sp).sum())
        r[4] = float((~jpos & sp).sum())
        r[5] = float((jpos & ~sp).sum())
        r[6] = float((~jpos & ~sp).sum())
        rows.append(r)
    M = np.array(rows)

    def f_rg(s):
        pa = s[:, 0] / s[:, 2]
        pb = s[:, 1] / s[:, 2]
        se = s[:, 3] / (s[:, 3] + s[:, 4])
        sp = s[:, 6] / (s[:, 5] + s[:, 6])
        with np.errstate(invalid="ignore", divide="ignore"):
            den = se + sp - 1
            return (pb - pa) / den

    def f_obs(s):
        return (s[:, 1] - s[:, 0]) / s[:, 2]

    r = C.fast_bca(M, f_rg)
    ro = C.fast_bca(M, f_obs)
    tot = M.sum(0)
    se, sp = tot[3] / (tot[3] + tot[4]), tot[6] / (tot[5] + tot[6])
    # direct labelled contrast of the support share on the same 23 questions
    direct = C.paired_delta(A.loc[sh, S], Bv.loc[sh, S])
    direct.pop("diffs"), direct.pop("cqs")
    return {"RG_corrected_contrast_support_share": r, "uncorrected_judge_contrast_Jge2_share": ro,
            "direct_label_contrast_support_share": direct,
            "Se_P(J>=2|S=1)": float(se), "Sp_P(J<=1|S=0)": float(sp), "Se_plus_Sp_minus_1": float(se + sp - 1),
            "calibration_variants": list(calib_variants), "n_calibration_cells": int(tot[3:].sum())}


OUT["rogan_gladen"] = {}
for src, (S, R) in SRC.items():
    OUT["rogan_gladen"][src] = {
        "in_sample_all_188_cells": rg_contrast(d, S, C.VARIANTS),
        "calibrated_on_C_to_F_only": rg_contrast(d, S, list("CDEF")),
    }
    # per-variant operating characteristics of the binary judge call against the label (heterogeneity)
    het = {}
    for v in C.VARIANTS:
        c = d[d.variant == v]
        tp = int(((c.J >= 2) & (c[S] == 1)).sum()); fn = int(((c.J < 2) & (c[S] == 1)).sum())
        fp = int(((c.J >= 2) & (c[S] == 0)).sum()); tn = int(((c.J < 2) & (c[S] == 0)).sum())
        het[v] = {"Se": tp / (tp + fn) if tp + fn else None, "Sp": tn / (tn + fp) if tn + fp else None,
                  "TP": tp, "FN": fn, "FP": fp, "TN": tn}
    OUT["rogan_gladen"][src]["per_variant_operating_characteristics"] = het
    # same on the 23 questions A and B share (the A->B pair set): shows the judge's operating point moves between A and B
    Ash = d[d.variant == "A"].set_index("cq_id")
    Bsh = d[d.variant == "B"].set_index("cq_id")
    shared = sorted(set(Ash.index) & set(Bsh.index))
    oc23 = {}
    for v, t in (("A", Ash), ("B", Bsh)):
        c = t.loc[shared]
        tp = int(((c.J >= 2) & (c[S] == 1)).sum()); fn = int(((c.J < 2) & (c[S] == 1)).sum())
        fp = int(((c.J >= 2) & (c[S] == 0)).sum()); tn = int(((c.J < 2) & (c[S] == 0)).sum())
        oc23[v] = {"Se": tp / (tp + fn), "Sp": tn / (tn + fp), "TP": tp, "FN": fn, "FP": fp, "TN": tn,
                   "share_S1": float((c[S] == 1).mean()), "share_Jge2": float((c.J >= 2).mean())}
    OUT["rogan_gladen"][src]["operating_characteristics_on_23_shared_questions"] = oc23

# ------------------------------------------------------------------ PPI-style label-budget scenario
rng = np.random.default_rng(C.SEED)
dfa = add_estimators(d, "S_AH", "R_AH")
xA = dfa[dfa.variant == "A"].set_index("cq_id")
xB = dfa[dfa.variant == "B"].set_index("cq_id")
sh = sorted(set(xA.index) & set(xB.index))
dJ = (xB.loc[sh, "J"] - xA.loc[sh, "J"]).to_numpy(float)
dR = (xB.loc[sh, "R_AH"] - xA.loc[sh, "R_AH"]).to_numpy(float)
theta_full = dR.mean()
ppi: dict = {"target": "mean over 23 paired questions of (R_B - R_A), AH rater score",
             "full_label_value": float(theta_full), "prediction": "J_B - J_A", "n_pairs": len(sh),
             "corr_dJ_dR": float(np.corrcoef(dJ, dR)[0, 1]), "scenarios": []}
for m in (6, 9, 12, 16):
    est_ppi, est_lab, est_pp = [], [], []
    beta_star = float(np.cov(dR, dJ, ddof=1)[0, 1] / np.var(dJ, ddof=1))   # oracle power-tuning slope (PPI++)
    for _ in range(20000):
        lab = rng.choice(len(sh), m, replace=False)
        est_lab.append(dR[lab].mean())
        est_ppi.append(dJ.mean() + (dR[lab] - dJ[lab]).mean())
        est_pp.append(dR[lab].mean() + beta_star * (dJ.mean() - dJ[lab].mean()))
    est_ppi, est_lab, est_pp = np.array(est_ppi), np.array(est_lab), np.array(est_pp)
    ppi["scenarios"].append({
        "m_labelled_questions": m, "labelled_only_mean": float(est_lab.mean()), "labelled_only_sd": float(est_lab.std()),
        "ppi_mean": float(est_ppi.mean()), "ppi_sd": float(est_ppi.std()),
        "sd_ratio_ppi_over_labelled_only": float(est_ppi.std() / est_lab.std()),
        "rmse_vs_full_label_labelled_only": float(np.sqrt(np.mean((est_lab - theta_full) ** 2))),
        "rmse_vs_full_label_ppi": float(np.sqrt(np.mean((est_ppi - theta_full) ** 2))),
        "ppi_plus_plus_oracle_lambda": float(beta_star), "ppi_pp_sd": float(est_pp.std()),
        "sd_ratio_ppi_pp_over_labelled_only": float(est_pp.std() / est_lab.std())})
ppi["note"] = ("With every cell labelled (the realised audit) PPI collapses to the labelled mean, so it adds no "
               "information here; the scenario shows only whether J is informative enough about R to cut label cost. "
               "Finite-population sampling without replacement of questions; 20,000 draws, seed 20260913.")
OUT["ppi_label_budget_scenario"] = ppi

json.dump(OUT, open(Path(__file__).resolve().parent / "parts/r2.json", "w"), indent=1, default=float)


def f(r, nd=3):
    return C.ci_str(r, nd)


for src in SRC:
    print("==", src)
    for e, r in OUT[src]["contrast_A_to_B_23_questions"].items():
        print(f"  {e:30s} delta {f(r)}  90% [{r['lo90']:.3f},{r['hi90']:.3f}] up/down/tie {r['n_up']}/{r['n_down']}/{r['n_tie']} "
              f"wilcoxon {r['wilcoxon_p']:.3f} signflip {r['signflip']['p_two_sided']:.4f} covA {r['coverage_A_pct_on_23']:.1f} covB {r['coverage_B_pct_on_23']:.1f}")
    for e, r in OUT[src]["A_to_B_shift_vs_L1star"].items():
        print("  shift vs L1*", e, f(r))
for src in SRC:
    for k, v in OUT["rogan_gladen"][src].items():
        if k.startswith(("per_variant", "operating_characteristics")):
            continue
        print(src, k, "RG", f(v["RG_corrected_contrast_support_share"]), "obs", f(v["uncorrected_judge_contrast_Jge2_share"]),
              "direct", f(v["direct_label_contrast_support_share"]), "Se+Sp-1", round(v["Se_plus_Sp_minus_1"], 3))
print(json.dumps(OUT["ppi_label_budget_scenario"], indent=0, default=float)[:1500])
