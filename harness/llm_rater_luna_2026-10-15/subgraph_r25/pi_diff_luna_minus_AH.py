"""Paired unsupported-credit-rate difference, LLM-rater (luna, subgraph) minus AH labels.

Exploratory, post hoc, computed for supplement S21 after addendum 25 (not in its frozen plan).
Same resampling routine as the analyzer: analyze_holdout.cluster_bootstrap_stat
(CQ clusters, BCa 95%, B = 10000, seed 20260913). Sanity check: the independent-rater minus
AH difference must reproduce +6.4 [-2.2, +18.3] (main text, Section VI-D).
Run from harness/:  python3 llm_rater_luna_2026-10-15/subgraph_r25/pi_diff_luna_minus_AH.py
Review before reuse (generated tooling).
"""
import csv, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1])); sys.path.insert(0, str(HERE.parent))
import analyze_holdout as ah  # noqa: E402
import rater_luna as rl  # noqa: E402

cells = [json.loads(l) for l in open(HERE.parents[1] / "real_run" / "cells.jsonl") if l.strip()]
prim = [c for c in cells if c["cell_id"].startswith("primary:")]
ahl = rl.read_labels(rl.AH_LABELS)
ind = rl.read_labels(rl.INDEP_LABELS)
lu = {r["cell_id"]: int(r["A"]) for r in csv.DictReader(open(HERE / "labels_for_analysis_luna_subgraph.csv"))}
recs = [{"cluster_id": c["cluster_id"], "J": c["J"], "ah": ahl[c["cell_id"]]["S"],
         "lu": lu[c["cell_id"]], "in": ind[c["cell_id"]]["S"]} for c in prim]
rate = lambda cs, k: sum(r["J"] >= 2 and r[k] == 0 for r in cs) / len(cs)
out = {"n_cells": len(recs), "pi_AH": rate(recs, "ah"), "pi_luna": rate(recs, "lu")}
for name, k in (("luna_minus_AH", "lu"), ("independent_minus_AH_check", "in")):
    r = ah.cluster_bootstrap_stat(recs, lambda cs, k=k: rate(cs, k) - rate(cs, "ah"), B=10000, seed=20260913)
    out[name] = {x: r[x] for x in ("estimate", "ci_lo", "ci_hi", "n_clusters", "B", "seed", "method")}
(HERE / "pi_diff_luna_minus_AH.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))
