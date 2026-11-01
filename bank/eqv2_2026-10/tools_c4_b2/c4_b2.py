#!/usr/bin/env python3
# AI-generated draft: a person must review and test it before use.  (Addendum 47, C4 for bank b2.)
"""C4 for the frozen b2 bank: same procedure as tools/eligibility.py + tools/views.py (b1), b2 arguments.

New file; the b1 tools are imported and reused unchanged (rule, builder, hash checks, pair_sets, aggregates).
No model call, no network.  Writes eligibility_b2.json, view_manifest_b2.jsonl, pairs_b2.json,
inputs/b2/<V>/<id>/subgraph.txt (git-ignored).  Usage: python c4_b2.py
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BANK_DIR = HERE.parent
sys.path.insert(0, str(BANK_DIR / "tools"))
import eligibility as el   # noqa: E402
import views as vw         # noqa: E402

BANK_B2 = BANK_DIR / "cq_bank_brick_eqv2_b2.csv"
BANK_B2_SHA = "ff32b2fbc518e696d285b2bc6cfccac7648efe6bf80a566f1293ac883c8225d4"


def main():
    rh = el.import_rule()   # asserts run_holdout file sha and RUBRIC (module value) sha
    rows = el.load_bank(BANK_B2, el.BANK_COLUMNS, BANK_B2_SHA)
    views = {}
    for v in el.VARIANTS:
        raw = el.RENDER[v].read_bytes()
        assert el.sha256_bytes(raw) == el.RENDER_SHA256[v], f"rendering {v} sha mismatch"
        views[v] = raw.decode("utf-8")
    cells = el.compute(rows, views, rh._grounding_match_info)
    doc = {"study": "addendum 47 (plan-based, exploratory), C4 eligibility, bank b2",
           "rule": "run_holdout._grounding_match_info(R_V, row)['can_ablate'] on the full rendering; no allowlist",
           "inputs": {"bank_sha256": BANK_B2_SHA, "rendering_sha256": el.RENDER_SHA256,
                      "run_holdout_sha256": el.RUN_HOLDOUT_SHA256, "rubric_sha256": el.RUBRIC_SHA256},
           "n_rows": len(rows), "summary": el.summarize(cells), "cells": cells}
    (BANK_DIR / "eligibility_b2.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    vw.check_graphs()
    bv = vw.import_builder()
    qs = vw.load_questions(BANK_B2, BANK_B2_SHA)
    # b1 builder call parameterised: set name "b2" (output inputs/b2/...), prefix "eqv2b2"
    vw.SET_NAME = "b2"
    vw.el.BANK_CSV = BANK_B2
    manifest = vw.build_cells(qs, doc["cells"], bv, vw.INPUTS_DIR, lambda v: vw.GRAPH[v])
    for m in manifest:
        if m["view_path"] and Path(m["view_path"]).is_absolute():
            m["view_path"] = str(Path(m["view_path"]).relative_to(vw.ACCESS))
    ids = [q["cq_id"] for q in qs]
    cat = {q["cq_id"]: q["category"] for q in qs}
    ps = vw.pair_sets(manifest, ids, cat)
    agg = vw.aggregates(manifest, ps, len(ids))
    # aggregate keys are named K1/y1 by the b1 code; rename for b2
    agg = {("K2" if k == "K1" else "y2" if k == "y1" else "K2_ge_210" if k == "K1_ge_210" else k): v for k, v in agg.items()}
    with (BANK_DIR / "view_manifest_b2.jsonl").open("w", encoding="utf-8") as fh:
        for m in manifest:
            fh.write(json.dumps(m, ensure_ascii=False, sort_keys=True) + "\n")
    (BANK_DIR / "pairs_b2.json").write_text(json.dumps({"aggregates": agg, **ps}, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"K2={agg['K2']} floor={agg['floor_size']} A={agg['A_eligible']} B={agg['B_eligible']}")


if __name__ == "__main__":
    main()
