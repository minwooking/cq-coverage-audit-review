#!/usr/bin/env python3
"""R6  Per-judge A->B on the cross-family panel (the 48 registered cells scored by Gemini J, gpt-5.6-luna and
claude-sonnet-5-5) and contrast-direction agreement across judges.  Post hoc, no LLM call.

Feasibility is computed first: the frozen 48-cell list (A3 B9 C13 D7 E10 F6, 28 questions) holds NO question
for which both A and B have a cell, so the registered paired A->B contrast has n = 0 pairs on this panel.
Reported instead (all descriptive, all 'underpowered by construction'):
  (1) the pair-count matrix for every variant pair on the panel;
  (2) per-judge A vs the SAME-question graph cell (C or E) on the questions that exist (2 questions);
  (3) per-judge pooled contrast mean J(B-F cells) - mean J(A cells), unpaired across the panel's 28 question
      clusters (question-clustered BCa; A has only 3 cells in 3 clusters, so resamples that drop every A
      cluster are undefined and are excluded and counted);
  (4) per-judge variant means;
  (5) a pointer to R4, where the two judge FAMILIES that scored all 23 A-B question pairs (Gemini, luna in three
      input conditions) are compared; sonnet scored only the 48 cells.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

ids = [l.strip() for l in open(C.P_LIST48) if l.strip()]
assert len(ids) == 48
OUT: dict = {"seed": C.SEED, "B": C.B, "post_hoc": True, "n_cells": 48}

g = C.load_registered_J()
gem = {r.cell_id: int(r.J) for r in g.itertuples() if r.cell_kind == "primary"}
judges = {"Gemini J (registered)": {i: gem[i] for i in ids}}
for name, folder in (("gpt-5.6-luna", "gpt-5.6-luna"), ("claude-sonnet-5-5", "anthropic__claude-sonnet-5-5")):
    rows = C.jsonl(C.P_PANEL / folder / "cells.jsonl")
    m = {}
    for r in rows:
        if C.valid_score(r):
            m[r["cell_id"]] = int(r["J"])
    assert set(ids) <= set(m), f"{name} missing cells"
    judges[name] = {i: m[i] for i in ids}

df = pd.DataFrame([{"cell_id": i, "variant": i.split(":")[1], "cq_id": i.split(":")[2], "cluster_id": i.split(":")[2],
                    **{n: judges[n][i] for n in judges}} for i in ids])
OUT["n_clusters"] = int(df.cq_id.nunique())
OUT["cells_by_variant"] = df.variant.value_counts().sort_index().to_dict()

# (1) pair-count matrix
cq = {v: set(df[df.variant == v].cq_id) for v in C.VARIANTS}
OUT["paired_questions_matrix"] = {f"{a}-{b}": len(cq[a] & cq[b]) for a, b in itertools.combinations(C.VARIANTS, 2)}
OUT["A_B_paired_questions"] = len(cq["A"] & cq["B"])
OUT["A_cqs"], OUT["B_cqs"] = sorted(cq["A"]), sorted(cq["B"])

# (2) A vs same-question graph cells
OUT["A_vs_same_question_graph_cells"] = {}
for jn in judges:
    rows = []
    for v in "BCDEF":
        for q in sorted(cq["A"] & cq[v]):
            a = int(df[(df.variant == "A") & (df.cq_id == q)][jn].iloc[0])
            b = int(df[(df.variant == v) & (df.cq_id == q)][jn].iloc[0])
            rows.append({"question": q, "graph_variant": v, "J_A": a, "J_graph": b, "diff_graph_minus_A": b - a})
    OUT["A_vs_same_question_graph_cells"][jn] = {
        "pairs": rows, "n_pairs": len(rows), "n_distinct_questions": len({r["question"] for r in rows}),
        "mean_diff": float(np.mean([r["diff_graph_minus_A"] for r in rows])) if rows else None,
        "direction": ("graph>A" if rows and np.mean([r["diff_graph_minus_A"] for r in rows]) > 0 else
                      "graph<A" if rows and np.mean([r["diff_graph_minus_A"] for r in rows]) < 0 else "tie")}

# (3) pooled, unpaired
OUT["pooled_graph_minus_A_unpaired"] = {}
for jn in judges:
    t = df.copy()
    t["_a"] = np.where(t.variant == "A", t[jn], 0).astype(float)
    t["_na"] = (t.variant == "A").astype(float)
    t["_g"] = np.where(t.variant != "A", t[jn], 0).astype(float)
    t["_ng"] = (t.variant != "A").astype(float)
    M, _ = C.cluster_matrix(t, ["_a", "_na", "_g", "_ng"])
    with np.errstate(invalid="ignore", divide="ignore"):
        r = C.fast_bca(M, lambda s: s[:, 2] / s[:, 3] - s[:, 0] / s[:, 1])
    r["mean_J_A_cells"] = float(t[t.variant == "A"][jn].mean())
    r["mean_J_graph_cells_B_to_F"] = float(t[t.variant != "A"][jn].mean())
    r["n_A_cells"], r["n_graph_cells"] = 3, 45
    r["direction"] = "graph>A" if r["est"] > 0 else "graph<A" if r["est"] < 0 else "tie"
    r["ci95_excludes_0"] = bool(r["lo"] > 0 or r["hi"] < 0)
    OUT["pooled_graph_minus_A_unpaired"][jn] = r
dirs = {jn: OUT["pooled_graph_minus_A_unpaired"][jn]["direction"] for jn in judges}
OUT["direction_agreement_pooled"] = {"directions": dirs, "all_same": len(set(dirs.values())) == 1}

# (4) variant means per judge
OUT["variant_means_J"] = {jn: {v: float(df[df.variant == v][jn].mean()) for v in C.VARIANTS} for jn in judges}
OUT["panel_J_marginals"] = {jn: [int((df[jn] == k).sum()) for k in range(4)] for jn in judges}
OUT["pointer"] = ("The A->B contrast across judge families is in parts/r4.json (Gemini and luna, three input conditions, "
                  "23 question pairs); sonnet scored the 48-cell panel only.")

json.dump(OUT, open(Path(__file__).resolve().parent / "parts/r6.json", "w"), indent=1, default=float)
print("paired A-B questions on panel:", OUT["A_B_paired_questions"], OUT["paired_questions_matrix"])
for jn in judges:
    v = OUT["A_vs_same_question_graph_cells"][jn]
    p = OUT["pooled_graph_minus_A_unpaired"][jn]
    print(jn, "A vs same-q graph:", v["n_pairs"], v["mean_diff"], v["direction"], "| pooled graph-A", C.ci_str(p),
          p.get("n_undefined_resamples"), "| means", {k: round(x, 2) for k, x in OUT["variant_means_J"][jn].items()})
print(OUT["direction_agreement_pooled"])
