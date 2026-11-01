#!/usr/bin/env python3
"""R9  Sensitivity of pi-hat to its event clusters (leave-one-cluster-out).  Post hoc, no new label.

pi-hat = 14/188 on the AH labels (events: J>=2 and S=0) falls in 4 of the 33 question clusters; the second
rater's labels give 26/188 in 8 clusters.  For every question cluster k the script drops ALL its cells and
recomputes (a) cell-level pi-hat, (b) the cluster-level G1 quantity (clusters with >= 1 event out of the
remaining clusters) with its one-sided Clopper-Pearson upper limit at the 97.5% decision level and 95%.
Then it drops the four event clusters one at a time, in pairs, and all together.  Also reported:
the cluster jackknife standard error of pi-hat, the largest single-cluster share of the events, and (bonus,
same logic) the leave-one-question-out range of the A->B L1* delta.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

d = C.load_188()
OUT: dict = {"post_hoc": True}
cp = C.ah.clopper_pearson_upper


def analyse(S, tag):
    e = ((d.J >= 2) & (d[S] == 0)).astype(int)
    t = d.assign(_e=e)
    per = t.groupby("cq_id").agg(events=("_e", "sum"), cells=("_e", "size"))
    n, ev = int(per.cells.sum()), int(per.events.sum())
    ev_cl = per[per.events > 0]
    out = {"events": ev, "cells": n, "pi_hat": ev / n, "n_clusters": len(per), "event_clusters": len(ev_cl),
           "events_by_event_cluster": {k: int(v) for k, v in ev_cl.events.items()},
           "cells_by_event_cluster": {k: int(v) for k, v in ev_cl.cells.items()},
           "largest_single_cluster_share_of_events": float(ev_cl.events.max() / ev) if ev else None}
    # leave one cluster out (all 33)
    loo = []
    for q, r in per.iterrows():
        e2, n2 = ev - int(r.events), n - int(r.cells)
        k2 = int((per.drop(q).events > 0).sum())
        loo.append({"dropped": q, "events": e2, "cells": n2, "pi_hat": e2 / n2, "event_clusters": k2, "of_clusters": 32})
    pis = np.array([x["pi_hat"] for x in loo])
    out["leave_one_cluster_out_all_33"] = {"pi_hat_min": float(pis.min()), "pi_hat_max": float(pis.max()),
                                          "pi_hat_range_pp": [float(pis.min() * 100), float(pis.max() * 100)]}
    # leave one EVENT cluster out
    drop1 = [x for x in loo if x["dropped"] in ev_cl.index]
    for x in drop1:
        x["G1_cp_upper_97_5"] = float(cp(x["event_clusters"], 32, 0.025))
        x["G1_cp_upper_95"] = float(cp(x["event_clusters"], 32, 0.05))
    out["leave_one_event_cluster_out"] = drop1
    # pairs and all event clusters
    combos = []
    ids = list(ev_cl.index)
    for r_ in range(2, len(ids) + 1):
        for c in itertools.combinations(ids, r_):
            e2 = ev - int(per.loc[list(c)].events.sum())
            n2 = n - int(per.loc[list(c)].cells.sum())
            k2 = int((per.drop(list(c)).events > 0).sum())
            ncl = len(per) - len(c)
            combos.append({"dropped": list(c), "events": e2, "cells": n2, "pi_hat": e2 / n2,
                           "event_clusters": k2, "of_clusters": ncl,
                           "G1_cp_upper_97_5": float(cp(k2, ncl, 0.025)), "G1_cp_upper_95": float(cp(k2, ncl, 0.05))})
    out["drop_two_or_more_event_clusters"] = combos
    # registered G1 for reference
    out["G1_registered_cluster_level"] = {"event_clusters": len(ev_cl), "of": len(per),
                                         "cp_upper_97_5": float(cp(len(ev_cl), len(per), 0.025)),
                                         "cp_upper_95": float(cp(len(ev_cl), len(per), 0.05))}
    # jackknife SE of the cell-level pi-hat
    jk = np.array([x["pi_hat"] for x in loo])
    nn = len(jk)
    out["cluster_jackknife_se_pi_hat"] = float(np.sqrt((nn - 1) / nn * np.sum((jk - jk.mean()) ** 2)))
    # BCa interval with the 4 (or 8) event clusters removed one at a time is not defined for zero events; report
    # the interval at each leave-one-event-cluster-out state where events > 0
    sub_ci = []
    for x in drop1:
        if x["events"] > 0:
            t2 = t[t.cq_id != x["dropped"]].assign(_n=1.0)
            M, _ = C.cluster_matrix(t2, ["_e", "_n"])
            r = C.fast_bca(M, lambda s: s[:, 0] / s[:, 1])
            sub_ci.append({"dropped": x["dropped"], "pi_hat": r["est"], "ci95": [r["lo"], r["hi"]]})
    out["bca_after_dropping_one_event_cluster"] = sub_ci
    return out


for src, S in (("AH", "S_AH"), ("second_rater", "S_2")):
    OUT[src] = analyse(S, src)

# bonus: leave-one-question-out A->B (L1* AH, J)
for col, nm in (("L1star_AH", "L1star_AH"), ("J", "J"), ("L1star_2", "L1star_second_rater")):
    x = d[d.variant == "A"].set_index("cq_id")[col]
    y = d[d.variant == "B"].set_index("cq_id")[col]
    sh = sorted(set(x.index) & set(y.index))
    dif = (y.loc[sh] - x.loc[sh]).to_numpy(float)
    loo = np.array([np.delete(dif, i).mean() for i in range(len(dif))])
    OUT.setdefault("A_to_B_leave_one_question_out", {})[nm] = {
        "delta": float(dif.mean()), "min": float(loo.min()), "max": float(loo.max()),
        "dropped_at_min": sh[int(loo.argmin())], "dropped_at_max": sh[int(loo.argmax())], "n_pairs": len(dif)}

json.dump(OUT, open(Path(__file__).resolve().parent / "parts/r9.json", "w"), indent=1, default=float)
for src in ("AH", "second_rater"):
    o = OUT[src]
    print(src, o["events"], "/", o["cells"], "event clusters", o["events_by_event_cluster"], "max share", o["largest_single_cluster_share_of_events"])
    print("  LOO all 33 pi range pp", [round(x, 2) for x in o["leave_one_cluster_out_all_33"]["pi_hat_range_pp"]])
    for x in o["leave_one_event_cluster_out"]:
        print("   drop", x["dropped"], f"{x['events']}/{x['cells']} = {x['pi_hat']*100:.2f}%  clusters {x['event_clusters']}/32  G1 CP97.5 {x['G1_cp_upper_97_5']*100:.1f}%")
    for x in o["drop_two_or_more_event_clusters"][-3:]:
        print("   drop", x["dropped"], f"{x['events']}/{x['cells']} = {x['pi_hat']*100:.2f}%  clusters {x['event_clusters']}/{x['of_clusters']}  G1 CP97.5 {x['G1_cp_upper_97_5']*100:.1f}%")
    print("  jackknife SE", round(o["cluster_jackknife_se_pi_hat"], 4), "BCa after drop", [(c["dropped"], round(c["pi_hat"], 3), [round(y, 3) for y in c["ci95"]]) for c in o["bca_after_dropping_one_event_cluster"]])
print(OUT["A_to_B_leave_one_question_out"])
