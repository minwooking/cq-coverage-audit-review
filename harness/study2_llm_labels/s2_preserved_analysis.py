#!/usr/bin/env python3
"""Analysis of addendum 33 (preserved-control labels on the Study 2 labeler).  AI-generated; a person must review and test it
before reuse.  Reads raw/<model>_preserved.jsonl(.gz) and manifests/preserved.json; reads NO human label.  Uses analyze.py's
slot matrices and cell-label rule unchanged (majority of >= 15 valid slots; consistent = >= 23 of 25 agree).
Writes results_preserved.json and REPORT_preserved.md.   LLM-labeled; post hoc; not human-validated.
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

MODELS = ["glm", "gptoss"]


def read(model: str, raw: Path) -> list[dict]:
    for p in (raw / f"{model}_preserved.jsonl", raw / f"{model}_preserved.jsonl.gz"):
        if p.exists():
            op = gzip.open if p.suffix == ".gz" else open
            with op(p, "rt", encoding="utf-8") as fh:
                return [json.loads(l) for l in fh if l.strip()]
    return []


def read_stage1(model: str, raw: Path) -> list[dict]:
    for p in (raw / f"{model}_stage1.jsonl", raw / f"{model}_stage1.jsonl.gz"):
        if p.exists():
            op = gzip.open if p.suffix == ".gz" else open
            with op(p, "rt", encoding="utf-8") as fh:
                return [json.loads(l) for l in fh if l.strip()]
    return []


def summarize(L, cons, nv) -> dict:
    s1 = (L == 1.0)
    return {"cells": int(len(L)), "undefined": int(np.isnan(L).sum()), "a_majority_S1": int(s1.sum()),
            "b_consistent": int(cons.sum()), "c_consistent_and_S1": int((cons & s1).sum()),
            "valid_slots_min": int(nv.min()), "valid_slots_total": int(nv.sum())}


def run(raw: Path, manifest: Path) -> dict:
    rows = json.loads(manifest.read_text(encoding="utf-8"))["rows"]
    ids = [r["cell_id"] for r in rows]
    per, flags = {}, {}
    for m in MODELS:
        recs = read(m, raw)
        mats = A.slot_matrices(recs, ids)
        lab = A.cell_labels(mats["S"], mats["R"])
        per[m] = summarize(lab["L"], lab["consistent"], lab["n_valid"])
        per[m]["context_skip"] = len(mats["context_skip"])
        flags[m] = (lab["L"] == 1.0, lab["consistent"], lab["L"])
    both = {"a_majority_S1": int((flags["glm"][0] & flags["gptoss"][0]).sum()),
            "b_consistent": int((flags["glm"][1] & flags["gptoss"][1]).sum()),
            "c_consistent_and_S1": int((flags["glm"][0] & flags["gptoss"][0] & flags["glm"][1] & flags["gptoss"][1]).sum())}
    # context only: registered judge J of the preserved cells marked S=0 by a model
    J = {}
    for line in (HERE.parent / "real_run" / "cells.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r["cell_kind"] == "preserved_control":
                J[r["cell_id"]] = r["J"]
    s0 = {m: sorted(J[c] for c, l in zip(ids, flags[m][2]) if l == 0.0) for m in MODELS}
    # context: the 24 ablated controls of Study 2 (existing Stage 1 records, same rule) -- majority S=0, consistent, consistent and S=0
    man1 = json.loads((HERE / "manifests" / "stage1.json").read_text(encoding="utf-8"))["rows"]
    aids = sorted(r["cell_id"] for r in man1 if r["cell_kind"] == "ablated_control")
    abl, af = {}, {}
    for m in MODELS:
        mats = A.slot_matrices(read_stage1(m, raw), aids)
        lab = A.cell_labels(mats["S"], mats["R"])
        z0, cons = (lab["L"] == 0.0), lab["consistent"]
        af[m] = (z0, cons)
        abl[m] = {"cells": len(aids), "a_majority_S0": int(z0.sum()), "b_consistent": int(cons.sum()),
                  "c_consistent_and_S0": int((z0 & cons).sum()), "undefined": int(np.isnan(lab["L"]).sum())}
    abl["both_models"] = {"a_majority_S0": int((af["glm"][0] & af["gptoss"][0]).sum()),
                          "b_consistent": int((af["glm"][1] & af["gptoss"][1]).sum()),
                          "c_consistent_and_S0": int((af["glm"][0] & af["gptoss"][0] & af["glm"][1] & af["gptoss"][1]).sum())}
    return {"addendum": 33, "ablated_controls_study2": abl, "n_cells": len(ids), "per_model": per, "both_models": both,
            "view_holds_terms": int(sum(bool(r["view_holds_terms"]) for r in rows)),
            "registered_J_of_cells_marked_S0": s0, "comparison_ablated_S0": "22 of 24 (both models, Study 2)",
            "banner": "LLM-labeled; post hoc; not human-validated"}


def report(res: dict) -> str:
    pm, b = res["per_model"], res["both_models"]
    n = res["n_cells"]
    L = ["# Addendum 33 -- preserved-control labels (auto-generated; LLM-labeled; post hoc)", "",
         f"{n} preserved controls, 25 labels per cell and model, Study 2 view builder, personas, seeds and consistency rule.", "",
         "| | GLM-4.7-Flash | gpt-oss-20b | both models |", "|---|---|---|---|"]
    for k, t in (("a_majority_S1", "(a) majority S=1"), ("b_consistent", "(b) consistent (>= 23/25)"),
                 ("c_consistent_and_S1", "(c) consistent and S=1")):
        L.append(f"| {t} | {pm['glm'][k]} of {n} | {pm['gptoss'][k]} of {n} | {b[k]} of {n} |")
    ab = res["ablated_controls_study2"]
    L += ["", "Context, the 24 ablated controls of Study 2 (same rule): ",
          f"| ablated (a) majority S=0 | {ab['glm']['a_majority_S0']} of 24 | {ab['gptoss']['a_majority_S0']} of 24 | {ab['both_models']['a_majority_S0']} of 24 |",
          f"| ablated (b) consistent | {ab['glm']['b_consistent']} of 24 | {ab['gptoss']['b_consistent']} of 24 | {ab['both_models']['b_consistent']} of 24 |",
          f"| ablated (c) consistent and S=0 | {ab['glm']['c_consistent_and_S0']} of 24 | {ab['gptoss']['c_consistent_and_S0']} of 24 | {ab['both_models']['c_consistent_and_S0']} of 24 |"]
    L += ["", f"Undefined cells: GLM {pm['glm']['undefined']}, gpt-oss {pm['gptoss']['undefined']}. Valid slots (min per cell): "
          f"GLM {pm['glm']['valid_slots_min']}, gpt-oss {pm['gptoss']['valid_slots_min']}. Views holding the expected-answer terms: "
          f"{res['view_holds_terms']} of {n}. Registered judge J of cells labeled S=0: {res['registered_J_of_cells_marked_S0']}.",
          "Comparison: 22 of 24 ablated controls labeled S=0 by both models (Study 2)."]
    return "\n".join(L) + "\n"


def main() -> int:
    res = run(HERE / "raw", HERE / "manifests" / "preserved.json")
    (HERE / "results_preserved.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (HERE / "REPORT_preserved.md").write_text(report(res), encoding="utf-8")
    print(report(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
