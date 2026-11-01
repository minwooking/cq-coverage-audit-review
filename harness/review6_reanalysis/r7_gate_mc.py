#!/usr/bin/env python3
"""R7  Monte Carlo pass probability of each registered gate at the REALISED design (33 question clusters,
188 primary cells, observed rates).  Post hoc, no LLM call.

Question answered: 'was the gate passable at this design, and with what probability if the truth were what we
observed (plug-in) or better?'  A gate whose pass probability is ~0 at the observed truth AND stays low for
plausible improvements was not an informative test at n = 33.

Gate rules (PREREG sec.2; the analyzer's definitions):
  G1  one-sided Clopper-Pearson upper limit on the share of clusters with an event (J>=2 and A=0) <= 10%.
      Decision level 97.5% (95% reported alongside).  Exact + MC.
  G2  same-rater washout QWK, n = 72 cells, CI lower limit >= 0.70.  NOT RUN in the study; analogue: a 72-cell
      random sample of the realised cells with the human-human pair (AH R vs second-rater R) as the 'two passes'.
  G3  >= 22 of 24 ablated cells judged unsupported by the evaluator.  Judge-side analogue (J<=1): 21/24 observed.
  G4  falsification-only: FAILS if the QWK(J, R) 95% CI upper limit < 0.60; it can never pass.
  G5  MAE(J, R) 95% CI upper limit <= 0.50.
  G6  A->B consistent (L1* CI excludes 0 is the necessary component; the full rule also needs a second-judge
      direction and fragility K >= 6, so P(resolved) is an UPPER bound on P(G6 pass)).
  G7  < 3% of cells with dwell < 20 s (process metric; binomial at the observed 171/188).
  G8  falsification-only external spot-check, not run: no simulation.
Plug-in world: draw 33 clusters with replacement from the 33 observed clusters (all of a cluster's cells travel
together), compute the registered CI on the draw (BCa over clusters, inner B = 1000), repeat S times.
Improvement worlds ('agreement mixtures'): each cell of the second score is replaced, independently with
probability q, by the best value attainable (for J vs R: R' = max(J, 1) because no rater ever scored 0; for the
human-human pair: R2' = R_AH).  The expected confusion matrix of the mixture gives the TRUE QWK/MAE of that world.
Seed 20260913 for every random draw.  S = 2000 plug-in/mixture simulations per cell of the table.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats
from scipy.stats import binom

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

RNG = np.random.default_rng(C.SEED)
S_SIM = 2000
B_IN = 1000
d = C.load_188().sort_values(["cq_id", "variant"]).reset_index(drop=True)
clusters = sorted(d.cq_id.unique(), key=str)
cells = {c: d[d.cq_id == c] for c in clusters}
NC = len(clusters)
assert NC == 33
OUT: dict = {"post_hoc": True, "seed": C.SEED, "S_sim": S_SIM, "B_inner": B_IN, "n_clusters": NC,
             "plug_in_definition": "33 clusters drawn with replacement from the 33 observed; registered CI computed on the draw"}


# ---------------------------------------------------------------- G1
def cp_ok(k, n, alpha):
    return C.ah.clopper_pearson_upper(k, n, alpha) <= 0.10


def g1_block():
    out = {}
    for n in (33, 36):
        for alpha, lab in ((0.025, "97.5"), (0.05, "95")):
            kmax = max([k for k in range(0, n) if cp_ok(k, n, alpha)], default=-1)
            out[f"n{n}_level{lab}"] = {"max_events_allowed": kmax,
                                       "cp_upper_at_zero_events": float(C.ah.clopper_pearson_upper(0, n, alpha)),
                                       "passable": kmax >= 0}
    # P(pass) for a per-cluster event probability p (binomial: exact)
    probs = {"observed_AH_4_of_33": 4 / 33, "observed_second_rater_8_of_33": 8 / 33,
             "p_0.005": 0.005, "p_0.01": 0.01, "p_0.02": 0.02, "p_0.05": 0.05}
    out["exact_pass_probability"] = {}
    for n in (33, 36):
        for alpha, lab in ((0.025, "97.5"), (0.05, "95")):
            kmax = out[f"n{n}_level{lab}"]["max_events_allowed"]
            out["exact_pass_probability"][f"n{n}_level{lab}"] = {
                k: (float(binom.cdf(kmax, n, p)) if kmax >= 0 else 0.0) for k, p in probs.items()}
    # plug-in MC at 33 clusters with the observed event clusters (AH labels and second rater)
    for src, S in (("AH", "S_AH"), ("second_rater", "S_2")):
        ev = np.array([int(((cells[c].J >= 2) & (cells[c][S] == 0)).any()) for c in clusters])
        draws = RNG.integers(0, NC, (100000, NC))
        k = ev[draws].sum(1)
        res = {}
        for alpha, lab in ((0.025, "97.5"), (0.05, "95")):
            kmax = out[f"n33_level{lab}"]["max_events_allowed"]
            res[f"mc_P_pass_level{lab}"] = float((k <= kmax).mean()) if kmax >= 0 else 0.0
        res["mc_mean_event_clusters"] = float(k.mean())
        res["observed_event_clusters"] = int(ev.sum())
        res["exact_P_zero_events_in_33_draws"] = float(((NC - ev.sum()) / NC) ** NC)
        out[f"plug_in_mc_{src}"] = res
    return out


OUT["G1"] = g1_block()
print("G1 done", OUT["G1"]["plug_in_mc_AH"], OUT["G1"]["n33_level97.5"], OUT["G1"]["n36_level97.5"])


# ---------------------------------------------------------------- generic cluster sim machinery
def conf_vec(a, b, k):
    v = np.zeros(k * k)
    np.add.at(v, np.asarray(a) * k + np.asarray(b), 1)
    return v


def sim_ordinal(first, second, perfect, q, what, S=S_SIM, subsample=None, k=4):
    """simulate the registered interval for MAE / QWK of (first, second) in the world where each `second` value is
    replaced by perfect(first, second) w.p. q.  Returns arrays of (est, lo, hi).
    subsample: random number of cells (washout analogue) taken from the resampled pool."""
    res = []
    for _ in range(S):
        idx = RNG.integers(0, NC, NC)
        rows = []
        for c in idx:
            cc = cells[clusters[c]]
            a = cc[first].to_numpy()
            b = cc[second].to_numpy()
            if q > 0:
                u = RNG.random(len(a))
                b = np.where(u < q, perfect(a, b), b)
            rows.append((a, b))
        if subsample:
            tot = sum(len(a) for a, _ in rows)
            keep = np.zeros(tot, bool)
            keep[RNG.choice(tot, subsample, replace=False)] = True
            o = 0
            new = []
            for a, b in rows:
                m = keep[o:o + len(a)]
                o += len(a)
                if m.any():
                    new.append((a[m], b[m]))
            rows = new
            if len(rows) < 3:
                continue
        M = np.stack([conf_vec(a, b, k) for a, b in rows])
        f = (lambda s: C.mae_from_flat(s, k)) if what == "mae" else (lambda s: C.qwk_from_flat(s, k))
        try:
            r = C.fast_bca(M, f, B_=B_IN)
        except Exception:
            continue
        if not np.isfinite(r["hi"]) or not np.isfinite(r["lo"]):
            continue
        res.append((r["est"], r["lo"], r["hi"]))
    return np.array(res)


def true_world(first, second, perfect, q, k=4):
    """expected (population) confusion in the mixture world -> true MAE and QWK."""
    a = d[first].to_numpy()
    b = d[second].to_numpy()
    C0 = conf_vec(a, b, k)
    C1 = conf_vec(a, perfect(a, b), k)
    Cm = ((1 - q) * C0 + q * C1)[None]
    return float(C.mae_from_flat(Cm, k)[0]), float(C.qwk_from_flat(Cm, k)[0])


perf_JR = lambda a, b: np.maximum(a, 1)      # best attainable R given J (R >= 1 on every cell)
perf_HH = lambda a, b: a                      # second pass equals the first

QS = [0.0, 0.25, 0.5, 0.75, 0.85, 0.9, 1.0]

# ---------------------------------------------------------------- G5 and G4 (J vs AH rater score)
OUT["G5"] = {"rule": "MAE CI upper limit <= 0.50", "worlds": []}
OUT["G4"] = {"rule": "falsified if QWK CI upper limit < 0.60; cannot pass", "worlds": []}
for q in QS:
    mae_t, qwk_t = true_world("J", "R_AH", perf_JR, q)
    s5 = sim_ordinal("J", "R_AH", perf_JR, q, "mae")
    s4 = sim_ordinal("J", "R_AH", perf_JR, q, "qwk")
    OUT["G5"]["worlds"].append({"q": q, "true_MAE": mae_t, "n_valid_sims": len(s5),
                                "P_pass": float((s5[:, 2] <= 0.50).mean()), "mean_upper": float(s5[:, 2].mean()),
                                "mean_est": float(s5[:, 0].mean())})
    OUT["G4"]["worlds"].append({"q": q, "true_QWK": qwk_t, "n_valid_sims": len(s4),
                                "P_falsified": float((s4[:, 2] < 0.60).mean()), "mean_upper": float(s4[:, 2].mean()),
                                "mean_est": float(s4[:, 0].mean()), "P_pass": 0.0})
    print("G5/G4 q", q, OUT["G5"]["worlds"][-1], OUT["G4"]["worlds"][-1])

# ---------------------------------------------------------------- G2 analogue (72 random cells; human-human pair)
OUT["G2_analogue"] = {"rule": "QWK CI lower limit >= 0.70 on a random 72-cell sample", "worlds": [],
                      "assumption": "washout cells = a random 72 of the 188 primary cells; the two passes = AH R and the "
                                    "second rater's R (different raters; the registered G2 is same-rater and was NOT run)"}
for q in QS:
    mae_t, qwk_t = true_world("R_AH", "R_2", perf_HH, q)
    s2 = sim_ordinal("R_AH", "R_2", perf_HH, q, "qwk", subsample=72)
    OUT["G2_analogue"]["worlds"].append({"q": q, "true_QWK": qwk_t, "true_MAE": mae_t, "n_valid_sims": len(s2),
                                         "P_pass": float((s2[:, 1] >= 0.70).mean()), "mean_lower": float(s2[:, 1].mean()),
                                         "mean_est": float(s2[:, 0].mean())})
    print("G2 q", q, OUT["G2_analogue"]["worlds"][-1])

# ---------------------------------------------------------------- G6: A->B resolved at n = 23 (necessary component)
x = d[d.variant == "A"].set_index("cq_id").L1star_AH
y = d[d.variant == "B"].set_index("cq_id").L1star_AH
sh = sorted(set(x.index) & set(y.index), key=str)
dif = (y.loc[sh] - x.loc[sh]).to_numpy(float)
xj = d[d.variant == "A"].set_index("cq_id").J
yj = d[d.variant == "B"].set_index("cq_id").J
difJ = (yj.loc[sh] - xj.loc[sh]).to_numpy(float)
OUT["G6_A_to_B_resolved"] = {"rule": "L1* A->B 95% BCa CI excludes 0 (necessary part of G6; K>=6 and a second-judge direction are further requirements)",
                             "n_pairs": len(sh), "observed_delta": float(dif.mean()), "observed_sd": float(dif.std(ddof=1)),
                             "worlds": []}
for tgt in (0.0, 0.25, 0.478, 0.675, 0.784, 1.0):
    shifted = dif - dif.mean() + tgt
    hits = 0
    ok = 0
    for _ in range(S_SIM):
        samp = shifted[RNG.integers(0, len(shifted), len(shifted))]
        r = C.fast_bca(samp[:, None], lambda s: s[:, 0] / len(shifted), B_=B_IN)
        if np.isfinite(r["lo"]):
            ok += 1
            hits += (r["lo"] > 0 or r["hi"] < 0)
    OUT["G6_A_to_B_resolved"]["worlds"].append({"true_delta": tgt, "P_ci_excludes_0": hits / ok, "n_valid_sims": ok})
    print("G6 delta", tgt, hits / ok)

# ---------------------------------------------------------------- G3 judge-side analogue (binomial) and G7
c = C.load_registered_J()
ab = c[c.cell_kind == "ablated_control"]
k_spec = int((ab.J <= 1).sum())
OUT["G3_judge_side_analogue"] = {
    "rule": ">= 22 of 24 ablated cells judged unsupported", "observed_J_le1": k_spec, "n": len(ab),
    "exact_P_pass_at_observed_rate": float(binom.sf(21, 24, k_spec / 24)),
    "exact_P_pass_at_p": {f"p_{p}": float(binom.sf(21, 24, p)) for p in (0.80, 0.875, 0.90, 0.95, 0.98)},
    "p_needed_for_80pct_pass": float(next(p for p in np.linspace(0.5, 1, 5001) if binom.sf(21, 24, p) >= 0.80)),
    "note": "judge-side analogue (J<=1); the registered G3 uses the evaluator's A, not computable (8 of 24 ablated cells labelled). "
            "Cells treated as independent although the 24 cover 20 questions."}
under20 = 171
OUT["G7"] = {"rule": "< 3% of 188 primary cells with dwell < 20 s", "observed": f"{under20}/188",
             "observed_share": under20 / 188, "cells_allowed": int(math.ceil(0.03 * 188) - 1),
             "exact_P_pass_at_observed_rate": float(binom.cdf(math.ceil(0.03 * 188) - 1, 188, under20 / 188)),
             "note": "process metric of the labelling sitting, not a property of the judge; binomial is a formality"}
OUT["G8"] = {"rule": "falsification-only external spot check; not run", "simulated": False}

# ---------------------------------------------------------------- summary
OUT["summary"] = {
    "G1": "cannot pass at 33 clusters at the 97.5% decision level (0-event upper limit 10.58%); at 95% only with zero events",
    "G2": "not run; analogue shows the pass probability for a human-human-like second pass (see G2_analogue.worlds)",
    "G3": "judge-side analogue only (see G3_judge_side_analogue)",
    "G4": "cannot pass by rule; P_falsified given in G4.worlds",
    "G5": "see G5.worlds (P_pass at the observed truth and under agreement mixtures)",
    "G6": "see G6_A_to_B_resolved.worlds (upper bound)",
    "G7": "see G7", "G8": "not run"}
json.dump(OUT, open(Path(__file__).resolve().parent / "parts/r7.json", "w"), indent=1, default=float)
print("done")
