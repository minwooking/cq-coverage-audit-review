#!/usr/bin/env python3
"""Profile of the self-consistent cells of Study 2 (addendum 32; supplement Section S29).  AI-generated; a person must review and
test it before reuse.  No model call.  LLM-labeled; not human-validated beyond Stage 1.

A cell is self-consistent for a model if >= 23 of its 25 S labels agree (analyze.cell_labels).  For each primary model the
consistent cells are compared with the remaining cells of the 188 primary cells on: variant (A-F), question category, the
human support label under AH and under R2 (share S = 1), the human-human agreement on the cell (S_AH == S_2), the registered
judge score J (mean and share J >= 2), and the term-coverage flag of the retrieval view (manifest field view_holds_terms).
The human labels come from the de-identified analysis files through review6_reanalysis/common.load_188 only (the files of
review9/review10); only aggregates are written (no per-cell human label, no per-cell disagreement).
Intervals for a difference in shares: question-cluster bootstrap, 95% percentile, B = 10,000, seed 20260913 (descriptive).
Output: results_consistent_profile.json, tables_consistent_profile.tex.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze as A  # noqa: E402

RC, MODELS = A.RC, ["gptoss", "glm"]
B, SEED = 10_000, 20260913


def read(path: Path) -> list[dict]:
    for p in (path, path.with_name(path.name + ".gz")):
        if p.exists():
            op = gzip.open if p.suffix == ".gz" else open
            with op(p, "rt", encoding="utf-8") as fh:
                return [json.loads(l) for l in fh if l.strip()]
    raise SystemExit(f"missing {path}")


def diff_ci(cluster: np.ndarray, x: np.ndarray, cons: np.ndarray) -> list:
    """share(x | consistent) - share(x | rest) with a question-cluster percentile bootstrap."""
    u = sorted(set(cluster))
    pos = {c: i for i, c in enumerate(u)}
    ci = np.array([pos[c] for c in cluster])
    M = np.zeros((len(u), 4))
    np.add.at(M, ci, np.stack([x * cons, cons, x * ~cons, ~cons], 1).astype(float))

    def f(S):
        with np.errstate(invalid="ignore", divide="ignore"):
            return S[..., 0] / S[..., 1] - S[..., 2] / S[..., 3]
    rng = np.random.default_rng(SEED)
    draws = rng.integers(0, len(u), size=(B, len(u)))
    boot = f(M[draws].sum(1))
    boot = boot[np.isfinite(boot)]
    est = float(f(M.sum(0)))
    return [round(est, 3), round(float(np.percentile(boot, 2.5)), 3), round(float(np.percentile(boot, 97.5)), 3)]


def fmt_ci(d) -> str:
    return f"{d[0]:+.3f} [{d[1]:+.3f}, {d[2]:+.3f}]"


def latex(res: dict) -> str:
    g, o = res["models"]["gptoss"], res["models"]["glm"]
    L = [r"\begin{tabular}{@{}lcccccc@{}}", r"\toprule",
         r" & \multicolumn{3}{c}{\texttt{gpt-oss-20b}} & \multicolumn{3}{c}{\texttt{GLM-4.7-Flash}} \\",
         r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
         f"Share of cells & Consistent ({g['n_consistent']}) & Rest ({g['n_rest']}) & Difference & Consistent ({o['n_consistent']}) & Rest ({o['n_rest']}) & Difference \\\\",
         r"\midrule"]
    for k in g["features"]:
        a, b = g["features"][k], o["features"][k]
        name = k.replace("S=1", "$S=1$").replace("J>=2", "$J\\ge2$").replace("S_AH = S_R2", "$S_{\\mathrm{AH}}=S_{\\mathrm{R2}}$")
        L.append(f"{name} & {a['consistent']:.3f} & {a['rest']:.3f} & {fmt_ci(a['diff_ci'])} & {b['consistent']:.3f} & {b['rest']:.3f} & {fmt_ci(b['diff_ci'])} \\\\")
    L.append(f"Mean $J$ & {g['J_mean']['consistent']:.2f} & {g['J_mean']['rest']:.2f} & -- & {o['J_mean']['consistent']:.2f} & {o['J_mean']['rest']:.2f} & -- \\\\")
    L += [r"\midrule", r"\multicolumn{7}{@{}l}{Cells consistent / cells in the group, by variant} \\"]
    for v in g["variant"]:
        a, b = g["variant"][v], o["variant"][v]
        L.append(f"$\\mathrm{{{v}}}$ & \\multicolumn{{3}}{{c}}{{{a[0]} / {a[0]+a[1]}}} & \\multicolumn{{3}}{{c}}{{{b[0]} / {b[0]+b[1]}}} \\\\")
    L.append(r"\midrule")
    L.append(r"\multicolumn{7}{@{}l}{Cells consistent / cells in the group, by question category} \\")
    for c in g["category"]:
        a, b = g["category"][c], o["category"][c]
        L.append(f"{c.replace('_', ' ')} & \\multicolumn{{3}}{{c}}{{{a[0]} / {a[0]+a[1]}}} & \\multicolumn{{3}}{{c}}{{{b[0]} / {b[0]+b[1]}}} \\\\")
    L += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(L) + "\n"


def main() -> int:
    df = RC.load_188().sort_values("cell_id").reset_index(drop=True)
    man = json.loads((HERE / "manifests" / "stage1.json").read_text(encoding="utf-8"))
    hold = {r["cell_id"]: bool(r["view_holds_terms"]) for r in man["rows"] if r["cell_kind"] == "primary"}
    ids = list(df.cell_id)
    assert set(ids) == set(hold)
    cluster = df.cq_id.to_numpy()
    feats = {"human S=1, AH": df.S_AH.to_numpy(int), "human S=1, R2": df.S_2.to_numpy(int),
             "humans agree (S_AH = S_R2)": (df.S_AH == df.S_2).to_numpy(int),
             "registered judge J>=2": (df.J >= 2).to_numpy(int),
             "view holds the answer terms": np.array([hold[i] for i in ids], int)}
    res = {"banner": A.BANNER, "n_cells": len(ids), "rule": ">= 23 of 25 S labels agree (analyze.cell_labels)", "models": {}}
    for m in MODELS:
        recs = read(HERE / "raw" / f"{m}_stage1.jsonl")
        mats = A.slot_matrices(recs, ids)
        lab = A.cell_labels(mats["S"], mats["R"])
        cons = lab["consistent"] & ~np.isnan(lab["L"])
        out = {"n_consistent": int(cons.sum()), "n_rest": int((~cons).sum()),
               "n_clusters_consistent": int(len(set(cluster[cons]))),
               "share_consistent_labeled_S1": round(float((lab["L"][cons] == 1).mean()), 3)}
        out["variant"] = {v: [int(((df.variant == v).to_numpy() & cons).sum()), int(((df.variant == v).to_numpy() & ~cons).sum())]
                          for v in sorted(df.variant.unique())}
        out["category"] = {c: [int(((df.category == c).to_numpy() & cons).sum()), int(((df.category == c).to_numpy() & ~cons).sum())]
                           for c in sorted(df.category.unique())}
        out["features"] = {k: {"consistent": round(float(x[cons].mean()), 3), "rest": round(float(x[~cons].mean()), 3),
                               "diff_ci": diff_ci(cluster, x, cons)} for k, x in feats.items()}
        out["J_mean"] = {"consistent": round(float(df.J[cons].mean()), 2), "rest": round(float(df.J[~cons].mean()), 2)}
        res["models"][m] = out
    (HERE / "tables_consistent_profile.tex").write_text(latex(res), encoding="utf-8")
    (HERE / "results_consistent_profile.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
