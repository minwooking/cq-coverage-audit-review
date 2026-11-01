#!/usr/bin/env python3
"""Reproduction gate: the loaders and the vectorised BCa must reproduce numbers already
registered/recorded (BRIEF.md T1, T3, T4, T5c; results_v3.json) before any new number is used.

Writes selfcheck.json; exits non-zero on any mismatch beyond tolerance."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa: F401,F403
import common as C

d = C.load_188()
res: dict = {"checks": []}
fail = 0


def check(name, got, want, tol=1e-6):
    global fail
    ok = abs(got - want) <= tol
    fail += (not ok)
    res["checks"].append({"name": name, "got": got, "recorded": want, "ok": bool(ok)})
    print(("OK  " if ok else "FAIL"), name, got, want)


U = json.load(open(C.H / "real_run/results_human_pass/unsealed_2026-10-09/holdout_results_human.rerun_0dbe6e9.json"))

# 2x2 counts (BRIEF T5c): J>=2 / J<=1 x A=1 / A=0
t = {(j, a): int(((d.J >= 2) == bool(j)) .__and__(d.S_AH == a).sum()) for j in (1, 0) for a in (1, 0)}
check("2x2 J>=2,A=1", t[(1, 1)], 118)
check("2x2 J>=2,A=0 (pi events)", t[(1, 0)], 14)
check("2x2 J<=1,A=1 (under)", t[(0, 1)], 20)
check("2x2 J<=1,A=0", t[(0, 0)], 36)

# pi-hat BCa vs recorded (analyzer, python-loop implementation)
d["_pi"] = ((d.J >= 2) & (d.S_AH == 0)).astype(float)
d["_n"] = 1.0
M, _ = C.cluster_matrix(d, ["_pi", "_n"])
r = C.fast_bca(M, lambda s: s[:, 0] / s[:, 1])
pi = U["pi_hat"]
check("pi_hat est", r["est"], pi["pi_hat"])
check("pi_hat ci_lo", r["lo"], pi["ci_lo"], 1e-9)
check("pi_hat ci_hi", r["hi"], pi["ci_hi"], 1e-9)

# A->B L1* delta (23 pairs)
x = d[d.variant == "A"].set_index("cq_id").L1star_AH
y = d[d.variant == "B"].set_index("cq_id").L1star_AH
r = C.paired_delta(x, y)
ab = U["contrasts"]["A->B"]
check("A->B L1* delta", r["est"], ab["delta"], 1e-9)
check("A->B L1* ci_lo", r["lo"], ab["ci_lo"], 1e-9)
check("A->B L1* ci_hi", r["hi"], ab["ci_hi"], 1e-9)
check("A->B L1* ci90_lo", r["lo90"], ab["equivalence_interval"]["ci_lo"], 1e-9)
check("A->B L1* ci90_hi", r["hi90"], ab["equivalence_interval"]["ci_hi"], 1e-9)

# G4 QWK / G5 MAE (J vs R_AH)
g4 = U["gates"]["G4_human_judge_qwk"]
g5 = U["gates"]["G5_mae_judge_human"]
d["_cf"] = 0
rows = np.zeros((len(d), 16))
for i, (j, rr) in enumerate(zip(d.J, d.R_AH)):
    rows[i, j * 4 + rr] = 1
dd = d.copy()
for k in range(16):
    dd[f"c{k}"] = rows[:, k]
M, _ = C.cluster_matrix(dd, [f"c{k}" for k in range(16)])
q = C.fast_bca(M, lambda s: C.qwk_from_flat(s, 4))
m = C.fast_bca(M, lambda s: C.mae_from_flat(s, 4))
check("G4 QWK est", q["est"], g4["qwk"], 1e-6)
check("G4 QWK ci_lo", q["lo"], g4["ci_lo"], 1e-9)
check("G4 QWK ci_hi", q["hi"], g4["ci_hi"], 1e-9)
check("G5 MAE est", m["est"], g5["value"], 1e-9)
check("G5 MAE ci_lo", m["lo"], g5["ci_lo"], 1e-9)
check("G5 MAE ci_hi", m["hi"], g5["ci_hi"], 1e-9)

# second rater (results_v3.json): pi-hat, A->B, G4, G5
V3 = json.load(open(C.PAPER / "annotation/second_pass_2026-10-13/v3/results_v3.json"))
d["_pi2"] = ((d.J >= 2) & (d.S_2 == 0)).astype(float)
M, _ = C.cluster_matrix(d, ["_pi2", "_n"])
r = C.fast_bca(M, lambda s: s[:, 0] / s[:, 1])
check("2nd rater pi_hat est", r["est"], V3["pi_hat"]["pi_hat"])
check("2nd rater pi_hat ci_lo", r["lo"], V3["pi_hat"]["ci_lo"], 1e-9)
check("2nd rater pi_hat ci_hi", r["hi"], V3["pi_hat"]["ci_hi"], 1e-9)
x = d[d.variant == "A"].set_index("cq_id").L1star_2
y = d[d.variant == "B"].set_index("cq_id").L1star_2
r = C.paired_delta(x, y)
ab3 = V3["contrasts"]["A->B"]
check("2nd rater A->B delta", r["est"], ab3["delta"], 1e-9)
check("2nd rater A->B ci_lo", r["lo"], ab3["ci_lo"], 1e-9)
check("2nd rater A->B ci_hi", r["hi"], ab3["ci_hi"], 1e-9)

# judge-only J A->B (judge_only_J.json)
JO = json.load(open(C.H / "real_run/results_human_pass/judge_only_J.json"))["A_to_B_J"]
x = d[d.variant == "A"].set_index("cq_id").J
y = d[d.variant == "B"].set_index("cq_id").J
r = C.paired_delta(x, y)
check("J A->B delta (3dp)", round(r["est"], 3), JO["delta"], 5e-4)
check("J A->B ci_lo (3dp)", round(r["lo"], 3), JO["ci_lo"], 5e-4)
check("J A->B ci_hi (3dp)", round(r["hi"], 3), JO["ci_hi"], 5e-4)


# ---- cross-checks against the round-31 script outputs (results_r31.json): QWK(AH R, second R), sigma and MDE
R31 = json.load(open(C.H / "r31_analyses/results_r31.json"))
q31 = R31["4_gate_feasibility_numbers"]["G2_reference_inter_rater_QWK_AH_vs_independent_R"]
rows = np.zeros((len(d), 16))
for i, (a_, b_) in enumerate(zip(d.R_AH, d.R_2)):
    rows[i, a_ * 4 + b_] = 1
dd2 = d.copy()
for k in range(16):
    dd2[f"h{k}"] = rows[:, k]
M, _ = C.cluster_matrix(dd2, [f"h{k}" for k in range(16)])
hh = C.fast_bca(M, lambda s: C.qwk_from_flat(s, 4))
check("HH QWK est vs r31", hh["est"], q31["qwk"], 1e-9)
check("HH QWK lo vs r31", hh["lo"], q31["bca"]["lo"], 1e-9)
check("HH QWK hi vs r31", hh["hi"], q31["bca"]["hi"], 1e-9)
for lab, col in (("J", "J"), ("L1star_AH", "L1star_AH")):
    x_ = d[d.variant == "A"].set_index("cq_id")[col]
    y_ = d[d.variant == "B"].set_index("cq_id")[col]
    sh_ = sorted(set(x_.index) & set(y_.index))
    sd_ = float((y_.loc[sh_] - x_.loc[sh_]).std(ddof=1))
    check(f"sigma {lab} vs r31", sd_, R31["5_holdout_MDE"][lab]["A_to_B"]["sigma_holdout"], 1e-9)
    check(f"MDE23 {lab} vs r31", C.Z_MDE * sd_ / np.sqrt(len(sh_)), R31["5_holdout_MDE"][lab]["A_to_B"]["MDE"], 1e-9)

# ---- exact sign-flip permutation p: unit test against brute force and the binomial sign test
import itertools
from scipy.stats import binomtest
dif = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, -1, -1, -1, -1, -1, -1, 0, 0]
sf = C.signflip_exact_p(dif)
check("signflip == binomial sign test (all |d|=1)", sf["p_two_sided"], binomtest(6, 16, 0.5).pvalue, 1e-12)
dif2 = [3, -2, 1, 1, -1, 2, 0, -3, 1, 2, 1, -1]
brute = 0
obs = abs(sum(dif2))
nz2 = [abs(x) for x in dif2 if x != 0]
for signs in itertools.product((1, -1), repeat=len(nz2)):
    brute += abs(sum(s_ * a_ for s_, a_ in zip(signs, nz2))) >= obs
check("signflip == brute-force enumeration", C.signflip_exact_p(dif2)["p_two_sided"], brute / 2 ** len(nz2), 1e-12)

res["n_fail"] = fail
json.dump(res, open(Path(__file__).resolve().parent / "selfcheck.json", "w"), indent=1)
print("FAILURES:", fail)
sys.exit(1 if fail else 0)
