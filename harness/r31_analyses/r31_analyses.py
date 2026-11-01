#!/usr/bin/env python3
"""Round-31 post hoc analyses on EXISTING per-cell data.  No judge/LLM calls.

Registered estimators reused from harness/analyze_holdout.py:
  question(CQ)-clustered BCa bootstrap, seed 20260913, B = 10,000
  (cluster_bootstrap_stat / cluster_bootstrap_delta), Clopper-Pearson (scipy beta).

Usage:  python3 r31_analyses.py   ->  results_r31.json  (+ prints a text digest)
Every analysis here is POST HOC and exploratory; none enters a registered gate.
"""
from __future__ import annotations
import csv, itertools, json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import beta, binomtest
from sklearn.metrics import cohen_kappa_score

HERE = Path(__file__).resolve().parent
H = HERE.parent
R = H.parent
sys.path.insert(0, str(H))
import analyze_holdout as ah  # noqa: E402

SEED, B = ah.REGISTERED_SEED, ah.BOOTSTRAP_RESAMPLES
OUT: dict = {"seed": SEED, "B": B, "note": "post hoc; no LLM/judge calls"}


# ------------------------------------------------------------------ loaders
def load_d() -> pd.DataFrame:
    """188 primary cells with J, AH label (S_AH), independent label (S_v3, R_score), AH R."""
    pc = pd.DataFrame(json.load(open(H / "real_run/results_human_pass/unsealed_2026-10-09/per_cell.json"))["primary_cells"])
    v3 = pd.read_csv(R / "annotation/second_pass_2026-10-13/v3/labels_v3.csv")
    key = pd.read_csv(R / "annotation/labeling_sheet_key_2026-10-13.csv")
    d = pc.merge(v3[["cell_id", "S_label", "R_score"]], on="cell_id")
    d["S_AH"] = d.A
    d["S_v3"] = d.S_label
    # integrity: AH label and J equal the sealed key
    k = key.set_index("cell_id")
    assert (k.loc[d.cell_id, "S_AH"].values == d.S_AH.values).all()
    assert (k.loc[d.cell_id, "J"].values == d.J.values).all()
    for n in ["S_AH", "S_v3"]:
        d["L1_" + n] = np.where(d[n] == 1, d.J, np.minimum(d.J, 1))
    d["cluster_id"] = d.cq_id
    assert len(d) == 188 and d.cq_id.nunique() == 33
    return d


def cov(s):  # coverage in percent for a vector of 0..3 scores
    return float(np.sum(s) / (len(s) * 3) * 100)


def ci_fmt(x, lo, hi, nd=3):
    return f"{x:.{nd}f} [{lo:.{nd}f}, {hi:.{nd}f}]"


def bca(records, fn):
    r = ah.cluster_bootstrap_stat(records, fn, seed=SEED, B=B)
    return {"est": r["estimate"], "lo": r["ci_lo"], "hi": r["ci_hi"], "lo90": r["ci90_lo"], "hi90": r["ci90_hi"],
            "n_clusters": r["n_clusters"]}


d = load_d()
recs = d.to_dict("records")

# ================================================================== 1. D vs B
a1 = {}
for lab, col in [("J", "J"), ("L1star_AH", "L1_S_AH"), ("L1star_independent", "L1_S_v3")]:
    b = d[d.variant == "B"].set_index("cq_id")[col]
    dd = d[d.variant == "D"].set_index("cq_id")[col]
    sh = sorted(b.index.intersection(dd.index))
    diff = (dd[sh] - b[sh])
    res = ah.cluster_bootstrap_delta({q: [float(diff[q])] for q in sh}, seed=SEED, resamples=B)
    nz = diff[diff != 0]
    w = ah.wilcoxon_zeros_dropped([float(x) for x in diff])
    a1[lab] = {
        "n_shared_questions": len(sh), "delta_D_minus_B_rubric_pts": res["delta"],
        "ci95": [res["ci_lo"], res["ci_hi"]], "ci90": [res["ci90_lo"], res["ci90_hi"]],
        "delta_coverage_pp": res["delta"] / 3 * 100, "ci95_coverage_pp": [res["ci_lo"] / 3 * 100, res["ci_hi"] / 3 * 100],
        "n_pos": int((diff > 0).sum()), "n_neg": int((diff < 0).sum()), "n_zero": int((diff == 0).sum()),
        "wilcoxon_p": w["p"], "sign_test_p": (binomtest(int((diff > 0).sum()), int((diff != 0).sum()), .5).pvalue if len(nz) else None),
        "coverage_B_pct": cov(b[sh]), "coverage_D_pct": cov(dd[sh]),
    }
a1["note"] = ("one of 15 variant pairs, post hoc; unadjusted. Holm over 15 pairs would multiply p by up to 15 "
              "(smallest p x15). MDE for n=33 at sigma=1.155 is 0.563 rubric pts.")
OUT["1_D_vs_B"] = a1

# ================================================================== 2. label-source comparison
a2 = {}
b_ = int(((d.S_AH == 1) & (d.S_v3 == 0)).sum())  # AH supported, independent unsupported
c_ = int(((d.S_AH == 0) & (d.S_v3 == 1)).sum())
a2["discordant_AH1_ind0"] = b_
a2["discordant_AH0_ind1"] = c_
a2["mcnemar_exact_p_two_sided"] = binomtest(min(b_, c_), b_ + c_, .5).pvalue
a2["n_cells"] = 188
a2["note_mcnemar"] = "cell-level, ignores question clustering (33 clusters); a clustered CI on the share difference follows"
# clustered CI on supported-share difference (AH - independent)
a2["supported_share_diff_AH_minus_ind_pp"] = bca(recs, lambda c: 100 * (np.mean([x["S_AH"] for x in c]) - np.mean([x["S_v3"] for x in c])))


def pi_cells(c, col):
    return np.mean([1.0 if (x["J"] >= 2 and x[col] == 0) else 0.0 for x in c]) * 100


a2["pi_AH_pct"] = bca(recs, lambda c: pi_cells(c, "S_AH"))
a2["pi_ind_pct"] = bca(recs, lambda c: pi_cells(c, "S_v3"))
a2["pi_events_AH"] = int(((d.J >= 2) & (d.S_AH == 0)).sum())
a2["pi_events_ind"] = int(((d.J >= 2) & (d.S_v3 == 0)).sum())
a2["pi_diff_ind_minus_AH_pp"] = bca(recs, lambda c: pi_cells(c, "S_v3") - pi_cells(c, "S_AH"))
# clustered discordance: per-question net flip counts (sign test across questions as a sensitivity)
net = d.assign(f=(d.S_AH - d.S_v3)).groupby("cq_id").f.sum()
a2["questions_net_AH_more_supportive"] = int((net > 0).sum())
a2["questions_net_ind_more_supportive"] = int((net < 0).sum())
a2["question_level_sign_test_p"] = binomtest(int((net > 0).sum()), int((net != 0).sum()), .5).pvalue
a2["questions_with_any_discordance"] = int(d.assign(x=(d.S_AH != d.S_v3)).groupby("cq_id").x.any().sum())

# Kendall tau of six-variant coverage order (eligible cells, as in the paper's Coverage)
V = list("ABCDEF")
covs = {"J": [cov(d[d.variant == v].J) for v in V],
        "AH": [cov(d[d.variant == v].L1_S_AH) for v in V],
        "independent": [cov(d[d.variant == v].L1_S_v3) for v in V]}


def tau_exact(x, y):
    t0 = stats.kendalltau(x, y).statistic  # tau-b
    cnt = tot = 0
    for p in itertools.permutations(range(6)):
        t = stats.kendalltau(x, [y[i] for i in p]).statistic
        tot += 1
        cnt += abs(t) >= abs(t0) - 1e-12
    return float(t0), cnt / tot


a2["coverage_pct_by_variant"] = {k: dict(zip(V, [round(x, 2) for x in v])) for k, v in covs.items()}
a2["kendall_tau_b"] = {}
for (n1, x), (n2, y) in itertools.combinations(covs.items(), 2):
    t, p = tau_exact(x, y)
    a2["kendall_tau_b"][f"{n1}~{n2}"] = {"tau_b": t, "exact_perm_p_two_sided_720": p}
a2["order_desc"] = {k: ["".join(sorted(V, key=lambda v: -covs[k][V.index(v)]))] for k in covs}
a2["note_tau"] = "n=6 variants with ties; tau-b; coverage point estimates only (no per-variant CI propagated)"
OUT["2_label_source"] = a2

# ================================================================== 3. G5 decomposition
a3 = {}
for lab, col in [("AH_rater_L1", "rater_L1"), ("independent_R", "R_score")]:
    e = (d.J - d[col]).abs()
    tot = float(e.sum())
    n0 = int((d.J == 0).sum())
    n0_R1 = int(((d.J == 0) & (d[col] == 1)).sum())
    f1 = n0  # reviewers' accounting: every J=0 cell carries >=1 point forced by R>=1
    f2 = n0_R1  # strict: only J=0 & R=1 cells (error exactly 1) could drop to 0 if R=0 were allowed
    mae = lambda c, col=col, sub=0: float(np.mean([abs(x["J"] - x[col]) - sub * (x["J"] == 0) for x in c]))
    mae_f2 = lambda c, col=col: float(np.mean([abs(x["J"] - x[col]) - (1 if (x["J"] == 0 and x[col] == 1) else 0) for x in c]))
    a3[lab] = {
        "R_min_observed": int(d[col].min()), "R_counts": {int(k): int(v) for k, v in d[col].value_counts().sort_index().items()},
        "total_error_points": tot, "MAE_registered": tot / 188, "MAE_registered_ci": bca(recs, lambda c: mae(c)),
        "n_J0_cells": n0, "n_J0_R1_cells": n0_R1, "n_J0_R_ge2_cells": n0 - n0_R1,
        "floor_points_reviewer_accounting_47": f1,
        "share_reviewer": f1 / tot, "MAE_without_floor_reviewer": (tot - f1) / 188,
        "MAE_without_floor_reviewer_ci": bca(recs, lambda c: mae(c, sub=1)),
        "floor_points_strict": f2, "share_strict": f2 / tot, "MAE_without_floor_strict": (tot - f2) / 188,
        "MAE_without_floor_strict_ci": bca(recs, mae_f2),
        "G5_threshold_upper_bound_le": 0.50,
    }
# best case MAE given floor: rater agrees with judge except J=0 -> R=1
best = lambda c: float(np.mean([1.0 if x["J"] == 0 else 0.0 for x in c]))
a3["best_case_MAE_given_floor_and_observed_J"] = {"point": 47 / 188, "bca_ci": bca(recs, best)}
a3["note"] = ("'registered R>=1 floor' = the labeling rule R=1 whenever S=0 / no R=0 was ever entered (R in {1,2,3} on all 188 "
              "cells, both raters). Reviewer accounting subtracts 1 point from each of the 47 J=0 cells; the strict reading counts only "
              "J=0 cells whose R is exactly 1, because 17 of the 47 J=0 cells have R>=2 (rater found support) and are not floor-bound.")

# 3b. where the G5 error sits: cells where J and the binary label S disagree (the labeling-rule channel) vs. the rest
for lab, col, sc in [("AH_rater_L1", "rater_L1", "S_AH"), ("independent_R", "R_score", "S_v3")]:
    e = (d.J - d[col]).abs()
    disc = ((d.J >= 2).astype(int) != d[sc])
    a3[lab]["error_points_in_J_S_discordant_cells"] = {"n_cells": int(disc.sum()), "points": float(e[disc].sum()),
        "share_of_total": float(e[disc].sum() / e.sum()), "MAE_if_discordant_cells_zeroed": float(e[~disc].sum() / 188)}
    a3[lab]["error_points_J0_cells_by_R"] = {int(r): int(e[(d.J == 0) & (d[col] == r)].sum()) for r in (1, 2, 3)}
OUT["3_G5_decomposition"] = a3

# ================================================================== 5. holdout MDE
z = stats.norm.ppf(.975) + stats.norm.ppf(.80)
a5 = {"registered_sigma": 1.155, "registered_MDE_n36": z * 1.155 / 6, "registered_MDE_n23": z * 1.155 / math.sqrt(23)}
for lab, col in [("J", "J"), ("L1star_AH", "L1_S_AH"), ("L1star_independent", "L1_S_v3")]:
    out = {}
    for (v1, v2, nm) in [("A", "B", "A_to_B"), ("B", "D", "B_to_D")]:
        x = d[d.variant == v1].set_index("cq_id")[col]
        y = d[d.variant == v2].set_index("cq_id")[col]
        sh = sorted(x.index.intersection(y.index))
        diff = (y[sh] - x[sh]).values.astype(float)
        n = len(diff)
        sd = float(diff.std(ddof=1))
        lo = sd * math.sqrt((n - 1) / stats.chi2.ppf(.975, n - 1))
        hi = sd * math.sqrt((n - 1) / stats.chi2.ppf(.025, n - 1))
        rng = np.random.default_rng(SEED)
        bs = np.array([diff[rng.integers(0, n, n)].std(ddof=1) for _ in range(B)])
        out[nm] = {"n_questions": n, "sigma_holdout": sd, "sigma_ci95_chi2": [lo, hi],
                   "sigma_ci95_boot_pct": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                   "MDE": z * sd / math.sqrt(n), "MDE_at_sigma_ci": [z * lo / math.sqrt(n), z * hi / math.sqrt(n)],
                   "mean_delta": float(diff.mean())}
    a5[lab] = out
a5["note"] = "same normal-approximation formula as main.tex Sec. V-B: (z_.975+z_.8) sigma / sqrt(n), no Holm; sigma = SD of per-question differences"
OUT["5_holdout_MDE"] = a5

# ================================================================== 6. controls
c = pd.read_json(H / "real_run/cells.jsonl", lines=True)
ab = c[c.cell_kind == "ablated_control"]
pr = c[c.cell_kind == "preserved_control"]


def cp(k, n, lvl=.95):
    a = 1 - lvl
    lo = 0.0 if k == 0 else beta.ppf(a / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - a / 2, k + 1, n - k)
    return [float(lo), float(hi)]


k = int((ab.J >= 2).sum())
a6 = {"source": "harness/real_run/cells.jsonl cell_kind=ablated_control (24) / preserved_control (12)",
      "ablated_n": len(ab), "ablated_questions": int(ab.cq_id.nunique()),
      "ablated_J_ge2": k, "ablated_J_ge2_rate_cp95": cp(k, len(ab)),
      "judge_side_specificity_J_le1": len(ab) - k, "specificity_cp95": cp(len(ab) - k, len(ab)),
      "ablated_J_counts": {int(a): int(b) for a, b in ab.J.value_counts().sort_index().items()},
      "preserved_n": len(pr), "preserved_J_ge2": int((pr.J >= 2).sum()),
      "preserved_sensitivity_cp95": cp(int((pr.J >= 2).sum()), len(pr)),
      "preserved_J_counts": {int(a): int(b) for a, b in pr.J.value_counts().sort_index().items()},
      "caveat": "CP assumes independent cells; 24 ablated cells cover 20 questions. Registered G3 uses the evaluator's A, not J (0 of 24 usable)."}
# deterministic replay (no LLM): does the cited evidence survive in the ablated view for the J>=2 ablated cells?
try:
    import run_holdout as rh
    bank = {r["cq_id"]: r for r in csv.DictReader(open(R / "bank/cq_bank_brick_v1.csv", encoding="utf-8"))}
    rep = []
    for r in ab[ab.J >= 2].itertuples():
        view = (H / f"variants/{r.variant}/rendered_view.txt").read_text(encoding="utf-8")
        av = rh.ablate_rendered_view(view, bank[r.cq_id])
        ev = r.judge_response.get("evidence", "")
        toks = [t.strip() for t in str(ev).split("|") if t.strip()]
        rep.append({"cell_id": r.cell_id, "J": int(r.J), "evidence_in_ablated_view": bool(ev) and str(ev) in av,
                    "evidence_in_original_view": bool(ev) and str(ev) in view,
                    "evidence_tokens_in_ablated": sum(t in av for t in toks), "n_tokens": len(toks)})
    a6["replay_J_ge2_ablated_cells"] = rep
except Exception as e:  # pragma: no cover
    a6["replay_J_ge2_ablated_cells"] = f"replay not run: {type(e).__name__}: {e}"
OUT["6_ablated_controls"] = a6

# ================================================================== 7. judge noise vs dev adjacent gaps
dv = json.load(open(R.parent / "output/abcdef_evaluation.json")) if (R.parent / "output/abcdef_evaluation.json").exists() \
    else json.load(open("<repo>/output/abcdef_evaluation.json"))
ov = {v: dv["aggregate"][v]["overall_pct"] for v in V}
order = sorted(V, key=lambda v: ov[v])  # ascending: A B C E D F (D=F tie)
order = ["A", "B", "C", "E", "D", "F"]
gaps = [(order[i], order[i + 1], ov[order[i + 1]] - ov[order[i]]) for i in range(5)]
# per-sample Overall: coverage from judge_scores[k], quality from layer2 judge_scores[k]
l1 = dv["layer1"]["detail"]
l2 = dv["layer2"]["detail"]
per = {}
for v in V:
    row = []
    for s in (0, 1):
        cq = sum(l1[v][q]["judge_scores"][s] for q in l1[v]) / (len(l1[v]) * 3) * 100
        ql = sum(l2[v]["judge_scores"][s].values()) / 35 * 100
        row.append((cq + ql) / 2)
    per[v] = row
dif = np.array([per[v][0] - per[v][1] for v in V])
sd_diff = float(dif.std(ddof=1))
rmsd = float(np.sqrt(np.mean(dif ** 2)))
EF = abs(ov["E"] - ov["F"])
a7 = {"overall_pct": {v: round(ov[v], 3) for v in V},
      "adjacent_gaps": [{"pair": f"{a}->{b}", "gap": round(g, 3)} for a, b, g in gaps],
      "noise_EF_same_graph_gap": EF,
      "noise_floor_note_EF": "E and F are the same graph; their whole difference is one question (CQ15, 2 vs 3) = 1/(16*3)*100/2 = 1.042 Overall; n=1 pair, no variance estimate",
      "one_cq_point_in_Overall": 100 / 48 / 2,
      "self_consistency_two_sample_per_variant_Overall": {v: [round(x, 3) for x in per[v]] for v in V},
      "two_sample_abs_diff_by_variant": {v: round(abs(per[v][0] - per[v][1]), 3) for v in V},
      "two_sample_diff_sd_n6": sd_diff, "two_sample_rms_diff_n6": rmsd,
      "implied_sd_of_one_sample_Overall(rms/sqrt2)": rmsd / math.sqrt(2),
      "exceeds_EF_noise": {f"{a}->{b}": bool(g > EF + 1e-9) for a, b, g in gaps},
      "exceeds_2x_rms_two_sample_diff": {f"{a}->{b}": bool(g > 2 * rmsd) for a, b, g in gaps},
      "note": "dev Overall = mean(coverage, quality); per-sample Overall uses each of the two judge samples for L1 and L2 (published Overall uses consensus values). Single judge, 16 questions, one run of each graph."}
OUT["7_dev_noise"] = a7

# ================================================================== 8. length analysis
Ls = {v: len((H / f"variants/{v}/rendered_view.txt").read_text(encoding="utf-8")) for v in V}
a8 = {"view_chars": Ls}
for lab, col in [("J_coverage", "J"), ("L1star_AH_coverage", "L1_S_AH"), ("L1star_independent_coverage", "L1_S_v3")]:
    y = [cov(d[d.variant == v][col]) for v in V]
    x = [Ls[v] for v in V]
    rho = stats.spearmanr(x, y)
    pr_ = stats.pearsonr(np.log(x), y)
    # exact permutation p for Spearman over 720 perms
    obs = abs(rho.statistic)
    cnt = sum(abs(stats.spearmanr(x, [y[i] for i in p]).statistic) >= obs - 1e-12 for p in itertools.permutations(range(6)))
    # question-clustered bootstrap CI for the variant-level Spearman (resample questions, recompute 6 variant coverages)
    qs = sorted(d.cq_id.unique())
    piv = {v: d[d.variant == v].set_index("cq_id")[col] for v in V}
    rng = np.random.default_rng(SEED)
    bs = []
    for _ in range(B):
        samp = rng.integers(0, len(qs), len(qs))
        yy = []
        for v in V:
            s = [piv[v][qs[i]] for i in samp if qs[i] in piv[v].index]
            yy.append(np.sum(s) / (3 * len(s)) * 100)
        r_ = stats.spearmanr(x, yy).statistic
        if not np.isnan(r_):
            bs.append(r_)
    kt = stats.kendalltau(x, y)
    a8[lab] = {"n_variants": 6, "coverage_pct": dict(zip(V, [round(t, 2) for t in y])),
               "spearman": float(rho.statistic), "spearman_exact_perm_p": cnt / 720,
               "spearman_question_bootstrap_pct_ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
               "kendall_tau_b": float(kt.statistic), "pearson_r_log_length": float(pr_.statistic), "pearson_p_log_length": float(pr_.pvalue)}
# cell level for reference (the paper's rho=0.02, p=0.63)
rc = stats.spearmanr(d.variant.map(Ls), d.J)
a8["cell_level_reference"] = {"spearman_J_cell": float(rc.statistic), "asymptotic_p": float(rc.pvalue), "n_cells": 188,
                              "note": "cells share 33 questions and 6 variants: effective n is not 188"}
# full -> subgraph from raw cells (not only results_length.json)
cl = [json.loads(l) for l in open(H / "length_experiment/cells_length.jsonl") if l.strip()]
import run_holdout as rh2  # noqa: E402
by = {"full": {}, "subgraph": {}}
inv = {"full": 0, "subgraph": 0}
for r in cl:
    if r["condition"] in by:
        if rh2._valid_score(r):
            by[r["condition"]][r["pair_id"]] = r["J"]
        else:
            inv[r["condition"]] += 1
ids = sorted(set(by["full"]) & set(by["subgraph"]))
f = np.array([by["full"][i] for i in ids]); s_ = np.array([by["subgraph"][i] for i in ids])
diff = f - s_
res = ah.cluster_bootstrap_delta({i: [float(x)] for i, x in zip(ids, diff)}, seed=SEED, resamples=B)
res_json = next(c_ for c_ in json.load(open(H / "length_experiment/results_length.json"))["contrasts"] if c_["contrast"] == "full-subgraph")
k_ex = int((diff == 0).sum())
a8["full_minus_subgraph"] = {"n_pairs": len(ids), "n_distinct_questions": len(ids), "mean_diff": float(diff.mean()),
                             "bca_ci95": [res["ci_lo"], res["ci_hi"]], "exact_agreement": k_ex / len(ids), "exact_k": k_ex,
                             "exact_agreement_cp95": cp(k_ex, len(ids)),
                             "n_up_full": int((diff > 0).sum()), "n_down_full": int((diff < 0).sum()),
                             "invalid_records": inv,
                             "matches_results_length_json": bool(abs(res_json["mean_diff"] - diff.mean()) < 1e-12 and len(ids) == res_json["n_pairs"]
                                                                  and abs(res_json["interval"]["ci95"][0] - res["ci_lo"]) < 1e-9
                                                                  and abs(res_json["interval"]["ci95"][1] - res["ci_hi"]) < 1e-9),
                             "pairs_cover_variant_A_only": True,
                             "note": "22 questions in one variant (A); clustering is trivial (1 pair per question); 23rd pair lost to an invalid subgraph score"}
# limited - subgraph: point estimate pooled (-1.212) vs interval centre (cluster mean -1.162)
rl = next(c_ for c_ in json.load(open(H / "length_experiment/results_length.json"))["contrasts"] if c_["contrast"] == "limited-subgraph")
a8["limited_minus_subgraph_check"] = {"pooled_mean_diff": rl["mean_diff"], "interval_centre_cluster_mean": rl["interval"]["cluster_mean_diff"],
                                      "ci95": rl["interval"]["ci95"], "n_pairs": rl["n_pairs"], "n_clusters": rl["n_clusters"]}
OUT["8_length"] = a8

# ================================================================== 4. gate feasibility (numbers only; prose in report)
a4 = {}
def cp_up(k, n, lvl):  # one-sided upper
    return float(1.0 if k == n else beta.ppf(lvl, k + 1, n - k))
a4["G1_CP_upper_zero_events"] = {f"n{n}_{lvl}": cp_up(0, n, lvl) for n in (33, 36) for lvl in (.95, .975)}
a4["G1_CP_upper_one_event"] = {f"n{n}_{lvl}": cp_up(1, n, lvl) for n in (33, 36) for lvl in (.95, .975)}
a4["G1_min_clusters_zero_event_pass_975"] = next(n for n in range(10, 200) if cp_up(0, n, .975) <= .10)
a4["G1_min_clusters_zero_event_pass_95"] = next(n for n in range(10, 200) if cp_up(0, n, .95) <= .10)
a4["G5_best_case"] = a3["best_case_MAE_given_floor_and_observed_J"]
q = lambda x, y: cohen_kappa_score(x, y, weights="quadratic")
qa = q(d.rater_L1, d.R_score)
a4["G2_reference_inter_rater_QWK_AH_vs_independent_R"] = {"qwk": float(qa), "bca": bca([{**r} for r in recs], lambda c: float(q([x["rater_L1"] for x in c], [x["R_score"] for x in c]))),
                                                          "note": "different raters, not the registered same-rater statistic; shows how far a different human is from the 0.70 lower-bound bar"}
a4["G3_judge_side_analog"] = {"ablated_J_le1": a6["judge_side_specificity_J_le1"], "of": 24, "threshold": 22, "note": "J-based analog, not the registered A-based gate"}
a4["G6_MDE_A_to_B_n23_registered"] = a5["registered_MDE_n23"]
OUT["4_gate_feasibility_numbers"] = a4

json.dump(OUT, open(HERE / "results_r31.json", "w"), indent=1, default=float)
print(json.dumps(OUT, indent=1, default=float))
