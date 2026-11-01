"""Judge-only (J) coverage per variant and A->B on J, same resampling as the registered analyzer."""
import json, sys, collections
sys.path.insert(0, sys.argv[1])
import analyze_holdout as ah
cells = [json.loads(l) for l in open(sys.argv[2])]
prim = [c for c in cells if c["cell_kind"] == "primary"]
out = {"source": "cells.jsonl primary cells; J only (no labels)", "coverage_J": {}}
for v in sorted({c["variant"] for c in prim}):
    rec = [{"cluster_id": c["cluster_id"], "J": int(c["J"])} for c in prim if c["variant"] == v]
    res = ah.cluster_bootstrap_stat(rec, lambda rs: 100.0 * sum(r["J"] for r in rs) / (3 * len(rs)),
                                    None, "cluster_id", 10000, 20260913, "midrank")
    out["coverage_J"][v] = {"pct": round(res["estimate"], 2), "ci_lo": round(res["ci_lo"], 2),
                            "ci_hi": round(res["ci_hi"], 2), "n_cells": len(rec)}
byq = collections.defaultdict(dict)
for c in prim:
    byq[c["cq_id"]][c["variant"]] = int(c["J"])
inter = sorted(q for q, d in byq.items() if "A" in d and "B" in d)
deltas = {q: [byq[q]["B"] - byq[q]["A"]] for q in inter}
d = ah.cluster_bootstrap_delta(deltas, 10000, 20260913)
w = ah.wilcoxon_zeros_dropped([v[0] for v in deltas.values()])
out["A_to_B_J"] = {"n_cq": len(inter), "delta": round(d["delta"], 3), "ci_lo": round(d["ci_lo"], 3),
                   "ci_hi": round(d["ci_hi"], 3), "ci90": [round(d["ci90_lo"], 3), round(d["ci90_hi"], 3)],
                   "wilcoxon_p": w["p"], "n_nonzero": w["n_nonzero"]}
# Sensitivity: the former (strict) tie rule, and the lattice step of a mean over 23 integer deltas.
ds = ah.cluster_bootstrap_delta(deltas, 10000, 20260913, ties="strict")
out["A_to_B_J"]["strict_ties_ci"] = [round(ds["ci_lo"], 3), round(ds["ci_hi"], 3)]
out["A_to_B_J"]["lattice_step"] = round(1 / len(inter), 4)
# Comparability (PREREG L801-803): variant A has 23 scored CQs, B-F have 33, so
# B-F coverage is also given on A's 23-CQ set.
out["coverage_J_on_A_cq_set"] = {}
for v in sorted({c["variant"] for c in prim}):
    rec = [{"cluster_id": c["cluster_id"], "J": int(c["J"])} for c in prim
           if c["variant"] == v and c["cq_id"] in set(inter)]
    res = ah.cluster_bootstrap_stat(rec, lambda rs: 100.0 * sum(r["J"] for r in rs) / (3 * len(rs)),
                                    None, "cluster_id", 10000, 20260913, "midrank")
    out["coverage_J_on_A_cq_set"][v] = {"pct": round(res["estimate"], 2), "ci_lo": round(res["ci_lo"], 2),
                                        "ci_hi": round(res["ci_hi"], 2), "n_cells": len(rec)}
print(json.dumps(out, indent=1))
