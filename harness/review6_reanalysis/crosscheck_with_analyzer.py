#!/usr/bin/env python3
"""Independent spot-check: four NEW quantities recomputed with the analyzer's own python-loop bootstrap
(analyze_holdout.cluster_bootstrap_stat / cluster_bootstrap_delta) instead of the vectorised implementation.
Must match parts/*.json exactly (tolerance 1e-9).  Run after r1, r2, r3, r5."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

ah = C.ah
HERE = Path(__file__).resolve().parent
d = C.load_188()
recs = d.to_dict("records")
P = {k: json.load(open(HERE / f"parts/{k}.json")) for k in ("r1", "r2", "r3", "r5")}
out = {"checks": []}
bad = 0


def chk(name, got, want):
    global bad
    ok = all(abs(g - w) < 1e-9 for g, w in zip(got, want))
    bad += (not ok)
    out["checks"].append({"name": name, "analyzer": list(map(float, got)), "vectorised": list(map(float, want)), "ok": bool(ok)})
    print("OK  " if ok else "FAIL", name, got, want)


f = lambda cs: np.mean([(1.0 if (c["J"] >= 2 and c["S_AH"] == 0) else 0.0) - (1.0 if (c["J"] <= 1 and c["S_AH"] == 1) else 0.0) for c in cs])
r = ah.cluster_bootstrap_stat(recs, f, seed=C.SEED, B=C.B)
x = P["r1"]["AH"]["overall"]["binary_support"]["net_rate_over_minus_under"]
chk("R1 net over-under rate (AH)", (r["estimate"], r["ci_lo"], r["ci_hi"]), (x["est"], x["lo"], x["hi"]))

A = d[d.variant == "A"].set_index("cq_id").R_AH
B = d[d.variant == "B"].set_index("cq_id").R_AH
sh = sorted(set(A.index) & set(B.index))
res = ah.cluster_bootstrap_delta({q: [float(B[q] - A[q])] for q in sh}, seed=C.SEED, resamples=C.B)
m = P["r2"]["AH"]["contrast_A_to_B_23_questions"]["L_R (rater score)"]
chk("R2 A->B under L_R (AH)", (res["delta"], res["ci_lo"], res["ci_hi"]), (m["est"], m["lo"], m["hi"]))

BANK, EXC = list(ah.REGISTERED_BANK_CQ_IDS), ah.REGISTERED_EXCLUDED_CQS
idx = d.set_index(["variant", "cq_id"]).J
dd = {q: [(0.0 if q in EXC["B"] else float(idx.loc[("B", q)])) - (0.0 if q in EXC["A"] else float(idx.loc[("A", q)]))] for q in BANK}
res = ah.cluster_bootstrap_delta(dd, seed=C.SEED, resamples=C.B)
m = P["r3"]["J"]["A_to_B"]["full_bank_36_ineligible_0"]
chk("R3 full-bank A->B on J (ineligible=0)", (res["delta"], res["ci_lo"], res["ci_hi"]), (m["est"], m["lo"], m["hi"]))


def ac1(cs):
    a = np.array([c["J"] >= 2 for c in cs], float)
    b = np.array([c["S_AH"] == 1 for c in cs], float)
    po = np.mean(a == b)
    pi = (a.mean() + b.mean()) / 2
    pe = 2 * pi * (1 - pi)
    return (po - pe) / (1 - pe)


r = ah.cluster_bootstrap_stat(recs, ac1, seed=C.SEED, B=C.B)
m = P["r5"]["binary_support"]["bin_J_AH"]["ac1"]
chk("R5 Gwet AC1 judge-AH", (r["estimate"], r["ci_lo"], r["ci_hi"]), (m["est"], m["lo"], m["hi"]))
out["n_fail"] = bad
json.dump(out, open(HERE / "crosscheck.json", "w"), indent=1)
sys.exit(1 if bad else 0)
