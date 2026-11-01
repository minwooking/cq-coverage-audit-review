#!/usr/bin/env python3
"""Addendum 36 amendment D: variance decomposition of the Study 5 judge panel.  AI-generated; review and test before use.

  analyze.py run        committed score CSVs + cells_ab.json + paper results.json -> results.json, REPORT_auto.md, tables.tex
  test_analyze.py       tests on synthetic data

No model call, no network.  Every constant is the PLAN's (D.4/D.5): seed 20260913, B = 2000, permutations 2000, reading rule p < 0.05 or share >= 10%.
Judge scores, not human labels; exploratory, post hoc.
"""
from __future__ import annotations

import csv
import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
SEED, B_BOOT, B_PERM = 20260913, 2000, 2000
ALPHA, SHARE_MIN = 0.05, 0.10
BRICK_BANKS = ("holdout", "paraphrases", "v2_extras", "expansion")
DOMAINS = ("dcat", "ssn", "prov")
SCORE_FILES = {
    "glm": "study5_judge_panel/scores_glm.csv", "gptoss": "study5_judge_panel/scores_gptoss.csv", "q38": "study5_judge_panel/scores_q38.csv",
    "q80": "study5_judge_panel/scores_q80.csv", "gw": "study5_judge_panel/scores_gw.csv",
    "q38_27b": "study5b_small_judges/scores_q38_27b.csv", "q35_9b": "study5b_small_judges/scores_q35_9b.csv", "q35_4b": "study5b_small_judges/scores_q35_4b.csv",
}
LABEL = {"glm": "GLM-4.7-Flash", "gptoss": "gpt-oss-20b", "q38": "Qwen3.8-Flash-Next", "q80": "Qwen3-Next-80B", "gw": "luna",
         "q38_27b": "Qwen3.8-27B", "q35_9b": "Qwen3.5-9B", "q35_4b": "Qwen3.5-4B"}
SETS = {"INDEP": ["glm", "gptoss", "q38", "gw"], "INDEP+SF": ["glm", "gptoss", "q38", "gw", "q80"],
        "LADDER": ["q38_27b", "q35_9b", "q35_4b"], "ALL": list(SCORE_FILES)}
SCOPES = ("brick_pool", "new_domains_pooled")


# ------------------------------------------------------------------------------------------------------------------ loading
def read_scores(p: Path) -> dict[str, dict[int, int]]:
    out: dict[str, dict[int, int]] = {}
    for r in csv.DictReader(Path(p).open(encoding="utf-8", newline="")):
        out.setdefault(r["panel_id"], {})[int(r["repeat"])] = int(r["J"])
    return out


def load_all(root: Path = HARNESS):
    cells = json.loads((root / "study5_judge_panel/cells_ab.json").read_text(encoding="utf-8"))["cells"]
    scores = {j: read_scores(root / f) for j, f in SCORE_FILES.items()}
    return cells, scores


def scope_cells(cells: list[dict], scope: str) -> list[dict]:
    banks = BRICK_BANKS if scope == "brick_pool" else DOMAINS
    return [c for c in cells if c["scope"] in banks]


def build_units(cells: list[dict], scores: dict, judges: list[str], scope: str):
    """Complete-case unit table.  Returns Y (Q,2,J) of unit means (variant order A,B), question keys, and replicate lists.
    A (bank, cluster) pair is eligible if both A and B cells exist and every judge scored both; unit = mean over eligible banks of the cell mean
    (the paper's per-question mean of per-bank differences, addendum 34 A1)."""
    by: dict[tuple, dict[str, str]] = {}
    for c in scope_cells(cells, scope):
        by.setdefault((c["scope"], c["cluster"]), {})[c["variant"]] = c["panel_id"]
    per_q: dict[str, list[dict]] = {}
    for (bank, cl), vv in by.items():
        if "A" in vv and "B" in vv and all(scores[j].get(vv[v]) for j in judges for v in ("A", "B")):
            q = cl if scope == "brick_pool" else f"{bank}|{cl}"
            per_q.setdefault(q, []).append(vv)
    qs = sorted(per_q)
    Y = np.zeros((len(qs), 2, len(judges)))
    reps = {}
    for i, q in enumerate(qs):
        for k, v in enumerate(("A", "B")):
            for jj, j in enumerate(judges):
                cellvals = [list(scores[j][vv[v]].values()) for vv in per_q[q]]
                Y[i, k, jj] = float(np.mean([np.mean(x) for x in cellvals]))
                reps[(i, k, jj)] = cellvals
    return Y, qs, reps


def rep_noise(reps: dict, J: int) -> tuple[np.ndarray, float]:
    """per-judge within-cell repeat variance (unbiased, mean over cells with >=2 repeats) and the mean variance of a unit mean due to repeats"""
    s2 = np.zeros(J)
    for jj in range(J):
        v = [np.var(c, ddof=1) for (i, k, j), cs in reps.items() if j == jj for c in cs if len(c) >= 2]
        s2[jj] = float(np.mean(v)) if v else 0.0
    noise = []
    for (i, k, jj), cs in reps.items():
        n = sum(len(c) for c in cs)
        noise.append(s2[jj] / n * 1.0 if n else 0.0)   # banks average cell means: variance of the mean of n draws, upper-bound-ish
    return s2, float(np.mean(noise))


# ------------------------------------------------------------------------------------------------------------------ variance components
def components(Y: np.ndarray, s2_rep: float = 0.0, noise_unit: float = 0.0) -> dict:
    """expected-mean-squares decomposition for Y[q, v, j] (question random; variant and judge fixed), one value per cell; negatives truncated at 0"""
    Q, V, J = Y.shape
    g = Y.mean()
    mq, mv, mj = Y.mean((1, 2)), Y.mean((0, 2)), Y.mean((0, 1))
    mqv, mqj, mvj = Y.mean(2), Y.mean(1), Y.mean(0)
    SSq = V * J * ((mq - g) ** 2).sum()
    SSv = Q * J * ((mv - g) ** 2).sum()
    SSj = Q * V * ((mj - g) ** 2).sum()
    SSqv = J * ((mqv - mq[:, None] - mv[None, :] + g) ** 2).sum()
    SSqj = V * ((mqj - mq[:, None] - mj[None, :] + g) ** 2).sum()
    SSvj = Q * ((mvj - mv[:, None] - mj[None, :] + g) ** 2).sum()
    SSqvj = ((Y - mqv[:, :, None] - mqj[:, None, :] - mvj[None] + mq[:, None, None] + mv[None, :, None] + mj[None, None, :] - g) ** 2).sum()
    MS = {"q": SSq / (Q - 1), "v": SSv / (V - 1), "j": SSj / (J - 1), "qv": SSqv / ((Q - 1) * (V - 1)), "qj": SSqj / ((Q - 1) * (J - 1)),
          "vj": SSvj / ((V - 1) * (J - 1)), "qvj": SSqvj / ((Q - 1) * (V - 1) * (J - 1))}
    pos = lambda x: float(max(0.0, x))
    c = {"question": pos((MS["q"] - MS["qv"] - MS["qj"] + MS["qvj"]) / (V * J)),
         "question_x_variant": pos((MS["qv"] - MS["qvj"]) / J),
         "question_x_judge": pos((MS["qj"] - MS["qvj"]) / V),
         "variant": pos((MS["v"] - MS["qv"]) / (Q * J) * (V - 1) / V),
         "judge": pos((MS["j"] - MS["qj"]) / (Q * V) * (J - 1) / J),
         "variant_x_judge": pos((MS["vj"] - MS["qvj"]) / Q * (V - 1) * (J - 1) / (V * J)),
         "question_x_variant_x_judge_net": pos(MS["qvj"] - noise_unit),
         "repeat": float(s2_rep)}
    tot = sum(c.values())
    shares = {k: (v / tot if tot > 0 else 0.0) for k, v in c.items()}
    vr = c["variant"] + c["variant_x_judge"] + c["question_x_variant"]
    return {"components": c, "total": tot, "shares": shares, "interaction_share": shares["variant_x_judge"],
            "interaction_share_of_variant_variance": (c["variant_x_judge"] / vr if vr > 0 else 0.0),
            "F_vj": float(MS["vj"] / MS["qvj"]) if MS["qvj"] > 0 else None, "MS": {k: float(v) for k, v in MS.items()},
            "df_vj": [(V - 1) * (J - 1), (Q - 1) * (V - 1) * (J - 1)]}


def T_stat(Y: np.ndarray) -> float:
    """interaction variance estimate (raw, truncated at 0); the test statistic"""
    return components(Y)["components"]["variant_x_judge"]


def remove_interaction(Y: np.ndarray) -> np.ndarray:
    mv, mj, g, mvj = Y.mean((0, 2)), Y.mean((0, 1)), Y.mean(), Y.mean(0)
    return Y - (mvj - mv[:, None] - mj[None, :] + g)[None]


def boot_test(Y: np.ndarray, B: int = B_BOOT, seed: int = SEED) -> dict:
    """question-clustered bootstrap test of H0 (no judge x variant interaction), null imposed by removing the estimated interaction"""
    rng = np.random.default_rng(seed)
    Q = Y.shape[0]
    obs = T_stat(Y)
    Y0 = remove_interaction(Y)
    ts = np.empty(B)
    for b in range(B):
        ts[b] = T_stat(Y0[rng.integers(0, Q, Q)])
    return {"T_obs": obs, "p": float((1 + (ts >= obs).sum()) / (B + 1)), "B": B, "seed": seed, "null_T_mean": float(ts.mean())}


def boot_share_ci(Y: np.ndarray, s2_rep: float, noise_unit: float, B: int = B_BOOT, seed: int = SEED) -> list[float]:
    rng = np.random.default_rng(seed + 1)
    Q = Y.shape[0]
    sh = [components(Y[rng.integers(0, Q, Q)], s2_rep, noise_unit)["interaction_share"] for _ in range(B)]
    return [float(np.percentile(sh, 2.5)), float(np.percentile(sh, 97.5))]


def perm_test(Y: np.ndarray, B: int = B_PERM, seed: int = SEED) -> dict:
    """judge main effects removed, then judge labels permuted within each question x variant cell"""
    rng = np.random.default_rng(seed + 2)
    Yc = Y - Y.mean((0, 1))[None, None, :] + Y.mean()
    obs = T_stat(Y)
    Q, V, J = Y.shape
    ts = np.empty(B)
    for b in range(B):
        P = np.empty_like(Yc)
        for q in range(Q):
            for v in range(V):
                P[q, v] = Yc[q, v, rng.permutation(J)]
        ts[b] = T_stat(P)
    return {"T_obs": obs, "p": float((1 + (ts >= obs).sum()) / (B + 1)), "B": B, "seed": seed + 2}


def f_test(comp: dict) -> dict:
    from scipy import stats
    if comp["F_vj"] is None:
        return {"F": None, "p": None}
    d1, d2 = comp["df_vj"]
    return {"F": comp["F_vj"], "df": [d1, d2], "p": float(stats.f.sf(comp["F_vj"], d1, d2))}


# ------------------------------------------------------------------------------------------------------------------ contrasts
def contrasts(Y: np.ndarray) -> np.ndarray:
    """per-judge mean over questions of B - A"""
    return (Y[:, 1, :] - Y[:, 0, :]).mean(0)


def contrast_block(Y: np.ndarray, judges: list[str], B: int = B_BOOT, seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed + 3)
    Q, _, J = Y.shape
    d = Y[:, 1, :] - Y[:, 0, :]
    est = d.mean(0)
    boots = np.empty((B, J))
    for b in range(B):
        boots[b] = d[rng.integers(0, Q, Q)].mean(0)
    se = boots.std(0, ddof=1)
    sd_obs = float(est.std(ddof=1)) if J > 1 else 0.0
    sds = boots.std(1, ddof=1)
    tau2 = max(0.0, float(est.var(ddof=1) - (se ** 2).mean()))
    lam = tau2 / (tau2 + se ** 2) if tau2 > 0 else np.zeros(J)
    shrunk = est.mean() + lam * (est - est.mean())
    return {"n_questions": int(Q),
            "per_judge": {j: {"delta_mixed": float(est[i]), "ci95": [float(np.percentile(boots[:, i], 2.5)), float(np.percentile(boots[:, i], 97.5))],
                              "se": float(se[i]), "delta_eb_shrunk": float(shrunk[i])} for i, j in enumerate(judges)},
            "between_judge_sd": {"sd": sd_obs, "ci95": [float(np.percentile(sds, 2.5)), float(np.percentile(sds, 97.5))],
                                 "noise_corrected_sd": float(np.sqrt(tau2)), "mean_delta": float(est.mean())}}


# ------------------------------------------------------------------------------------------------------------------ agreement
def qwk(x, y, k: int = 4) -> float | None:
    if len(x) == 0:
        return None
    O = np.zeros((k, k))
    for a, b in zip(x, y):
        O[a, b] += 1
    hx, hy = O.sum(1), O.sum(0)
    E = np.outer(hx, hy) / O.sum()
    W = np.array([[(i - j) ** 2 for j in range(k)] for i in range(k)], float) / (k - 1) ** 2
    den = (W * E).sum()
    return None if den == 0 else float(1 - (W * O).sum() / den)


def icc2_1(M: np.ndarray) -> float | None:
    """ICC(2,1): two-way random, absolute agreement; M is cells x repeats"""
    n, k = M.shape
    if n < 2 or k < 2:
        return None
    g = M.mean()
    msr = k * ((M.mean(1) - g) ** 2).sum() / (n - 1)
    msc = n * ((M.mean(0) - g) ** 2).sum() / (k - 1)
    mse = ((M - M.mean(1, keepdims=True) - M.mean(0, keepdims=True) + g) ** 2).sum() / ((n - 1) * (k - 1))
    den = msr + (k - 1) * mse + k * (msc - mse) / n
    return float((msr - mse) / den) if den > 0 else None


def within_judge(s: dict[str, dict[int, int]], cell_ids: list[str]) -> dict:
    pair_q = {}
    for a, b in combinations((1, 2, 3), 2):
        sh = [c for c in cell_ids if a in s.get(c, {}) and b in s.get(c, {})]
        if sh:
            pair_q[f"{a}-{b}"] = {"n": len(sh), "qwk": qwk([s[c][a] for c in sh], [s[c][b] for c in sh])}
    vals = [v["qwk"] for v in pair_q.values() if v["qwk"] is not None]
    nrep = {}
    for c in cell_ids:
        nrep[len(s.get(c, {}))] = nrep.get(len(s.get(c, {})), 0) + 1
    kmod = max((k for k in nrep if k >= 2), key=lambda k: nrep[k], default=None)
    icc = None
    if kmod:
        full = [c for c in cell_ids if len(s.get(c, {})) == kmod]
        M = np.array([[s[c][r] for r in sorted(s[c])] for c in full], float)
        icc = icc2_1(M)
    return {"pairs": pair_q, "mean_pair_qwk": float(np.mean(vals)) if vals else None, "icc2_1": icc, "icc_repeats_k": kmod,
            "repeat_count_hist": {str(k): v for k, v in sorted(nrep.items())}}


def median_low(v: list[int]) -> int:
    v = sorted(v)
    return v[(len(v) - 1) // 2]


def between_judge(scores: dict, judges: list[str], cell_ids: list[str]) -> dict:
    out = {}
    for j in judges:
        pair, pair1 = {}, {}
        for o in judges:
            if o == j:
                continue
            sh = [c for c in cell_ids if scores[j].get(c) and scores[o].get(c)]
            pair[o] = qwk([median_low(list(scores[j][c].values())) for c in sh], [median_low(list(scores[o][c].values())) for c in sh])
            sh1 = [c for c in sh if 1 in scores[j][c] and 1 in scores[o][c]]
            pair1[o] = qwk([scores[j][c][1] for c in sh1], [scores[o][c][1] for c in sh1])
        v = [x for x in pair.values() if x is not None]
        v1 = [x for x in pair1.values() if x is not None]
        out[j] = {"mean_qwk_median": float(np.mean(v)), "range": [float(min(v)), float(max(v))], "mean_qwk_repeat1": float(np.mean(v1)),
                  "pairs": pair}
    return out


# ------------------------------------------------------------------------------------------------------------------ run
def reading(p: float, share: float) -> str:
    return "judge-dependent contrast supported" if (p < ALPHA or share >= SHARE_MIN) else "common effect plus judge level offsets"


def run(root: Path = HARNESS) -> dict:
    cells, scores = load_all(root)
    paper = {}
    for f in ("study5_judge_panel", "study5b_small_judges"):
        r = json.loads((root / f / "results.json").read_text(encoding="utf-8"))
        for j, v in r["per_judge"].items():
            paper[j] = v["contrasts"]
    res = {"banner": "variance decomposition of judge-panel scores; not human-labelled; exploratory, post hoc (addendum 36 amendment D)",
           "seed": SEED, "B_boot": B_BOOT, "B_perm": B_PERM, "rule": {"p": ALPHA, "share": SHARE_MIN}, "interaction": {}, "agreement": {}, "contrasts": {}}
    for scope in SCOPES:
        for sname, js in SETS.items():
            Y, qs, reps = build_units(cells, scores, js, scope)
            s2, noise = rep_noise(reps, len(js))
            comp = components(Y, float(s2.mean()), noise)
            bt, pt = boot_test(Y), perm_test(Y)
            comp.update({"n_questions": len(qs), "judges": js, "boot_test": bt, "perm_test": pt, "F_test": f_test(comp),
                         "interaction_share_ci95": boot_share_ci(Y, float(s2.mean()), noise), "repeat_var_per_judge": {j: float(s2[i]) for i, j in enumerate(js)},
                         "reading": reading(bt["p"], comp["interaction_share"])})
            res["interaction"][f"{scope}|{sname}"] = comp
            res["contrasts"][f"{scope}|{sname}"] = contrast_block(Y, js)
        ids = [c["panel_id"] for c in scope_cells(cells, scope)]
        res["agreement"][scope] = {"n_cells": len(ids), "within": {j: within_judge(scores[j], ids) for j in SCORE_FILES},
                                   "between": between_judge(scores, list(SCORE_FILES), ids)}
    res["paper_bca"] = {j: {s: {"delta": paper[j][f"A->B|{s}"]["delta"], "ci95": paper[j][f"A->B|{s}"]["ci95"], "n_clusters": paper[j][f"A->B|{s}"]["n_clusters"]}
                            for s in SCOPES} for j in SCORE_FILES}
    return res


def fp(p):
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def pf(p):
    return "<0.001" if p < 0.001 else "=%.3f" % p


def fmt(x, d=2):
    return "--" if x is None else f"{x:.{d}f}"


def write_outputs(res: dict, out: Path = HERE) -> None:
    (out / "results.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    L = [f"# Addendum 36 amendment D -- {res['banner']}", "", "AI-generated; review before relying on it. Rule fixed in PLAN.md D.5: supported if bootstrap p < 0.05 or interaction share >= 10%.", "",
         "## Judge x variant interaction (variance components, mixed ANOVA on unit means)", "",
         "| scope | judges | Q | interaction share [95% CI] | share of variant variance | boot p | perm p | F p | reading |", "|---|---|---|---|---|---|---|---|---|"]
    for k, v in res["interaction"].items():
        sc, sn = k.split("|")
        L.append(f"| {sc} | {sn} | {v['n_questions']} | {fmt(v['interaction_share'], 3)} [{fmt(v['interaction_share_ci95'][0], 3)}, {fmt(v['interaction_share_ci95'][1], 3)}] | "
                 f"{fmt(v['interaction_share_of_variant_variance'], 2)} | {fp(v['boot_test']['p'])} | {fp(v['perm_test']['p'])} | {fp(v['F_test']['p'])} | {v['reading']} |")
    L += ["", "## Variance components (share of total, single-repeat scale)", "", "| scope | judges | " + " | ".join(next(iter(res["interaction"].values()))["shares"]) + " |",
          "|---|---|" + "---|" * len(next(iter(res["interaction"].values()))["shares"])]
    for k, v in res["interaction"].items():
        L.append("| " + k.replace("|", " | ") + " | " + " | ".join(fmt(x, 3) for x in v["shares"].values()) + " |")
    L += ["", "## Between-judge SD of the A->B contrast", "", "| scope | judges | Q | mean delta | SD [95% CI] | noise-corrected SD |", "|---|---|---|---|---|---|"]
    for k, v in res["contrasts"].items():
        b = v["between_judge_sd"]
        L.append(f"| {k.replace('|', ' | ')} | {v['n_questions']} | {fmt(b['mean_delta'])} | {fmt(b['sd'])} [{fmt(b['ci95'][0])}, {fmt(b['ci95'][1])}] | {fmt(b['noise_corrected_sd'])} |")
    L += ["", "## Per judge: repeat agreement and contrasts", "", "| scope | judge | within QWK | ICC(2,1) | between QWK (median) [range] | between QWK (repeat 1) | delta mixed (ALL complete cases) [CI] | delta BCa [CI] |", "|---|---|---|---|---|---|---|---|"]
    for sc in SCOPES:
        for j in SCORE_FILES:
            w, b = res["agreement"][sc]["within"][j], res["agreement"][sc]["between"][j]
            m = res["contrasts"][f"{sc}|ALL"]["per_judge"][j]
            p = res["paper_bca"][j][sc]
            L.append(f"| {sc} | {LABEL[j]} | {fmt(w['mean_pair_qwk'])} | {fmt(w['icc2_1'])} | {fmt(b['mean_qwk_median'])} [{fmt(b['range'][0])}, {fmt(b['range'][1])}] | {fmt(b['mean_qwk_repeat1'])} | "
                     f"{fmt(m['delta_mixed'])} [{fmt(m['ci95'][0])}, {fmt(m['ci95'][1])}] | {fmt(p['delta'])} [{fmt(p['ci95'][0])}, {fmt(p['ci95'][1])}] (n={p['n_clusters']}) |")
    L += ["", "Caveats: judge scores, not human labels; unit means over repeats and banks; complete-case questions only (Q column); method-of-moments components, negatives truncated at 0; judges treated as fixed, so shares describe this panel; delta mixed equals the paper's delta where the question sets coincide (it is the same mean of per-question B-A), differing only through complete-case restriction; the rule of PLAN D.5 is an OR of significance and share, so a significant but tiny share (see the share column) is read 'supported' mechanically.", ""]
    (out / "REPORT_auto.md").write_text("\n".join(L), encoding="utf-8")
    T = [r"% AI-generated; review before use. Addendum 36 amendment D.", r"\begin{tabular}{@{}llrrrrr@{}}", r"\toprule",
         r"Scope & Judge & Repeat QWK & Between QWK & $\Delta$ mixed & $\Delta$ BCa & ICC \\", r"\midrule"]
    for sc in SCOPES:
        for j in SCORE_FILES:
            w, b = res["agreement"][sc]["within"][j], res["agreement"][sc]["between"][j]
            m = res["contrasts"][f"{sc}|ALL"]["per_judge"][j]
            T.append(f"{'Brick pool' if sc == 'brick_pool' else 'New domains'} & {LABEL[j]} & {fmt(w['mean_pair_qwk'])} & {fmt(b['mean_qwk_median'])} & "
                     f"{m['delta_mixed']:+.2f} & {res['paper_bca'][j][sc]['delta']:+.2f} & {fmt(w['icc2_1'])} \\\\")
        T.append(r"\midrule")
    for sc in SCOPES:
        for sn in ("INDEP", "ALL"):
            v = res["interaction"][f"{sc}|{sn}"]
            lab = ("Brick pool" if sc == "brick_pool" else "New domains") + ", " + sn
            body = (lab + ": judge$\\times$variant share %.3f, cluster-bootstrap $p%s$ (permutation $p%s$), $Q=%d$"
                    % (v["interaction_share"], pf(v["boot_test"]["p"]), pf(v["perm_test"]["p"]), v["n_questions"]))
            T.append("\\multicolumn{7}{l}{" + body + "} \\\\")
    T += [r"\bottomrule", r"\end{tabular}", ""]
    (out / "tables.tex").write_text("\n".join(T), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        r = run()
        write_outputs(r)
        for k, v in r["interaction"].items():
            print(k, v["n_questions"], round(v["interaction_share"], 4), v["boot_test"]["p"], v["perm_test"]["p"], v["reading"])
    else:
        print(__doc__)
