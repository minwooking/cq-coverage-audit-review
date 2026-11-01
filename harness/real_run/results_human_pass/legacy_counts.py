"""Counts behind older manuscript figures: judge J and the LLM auxiliary check only.

Reads the judge run (``cells.jsonl``) and the LLM auxiliary labels
(``llm_auxiliary_labels.jsonl``) and writes ``legacy_counts.json`` next to this
script. No human (AH) label is read, and no cell or CQ identifier is written:
the output holds counts, sums and means only.

Usage (from the worktree root; both paths default to ../ of this script)::

    python paper/access2026/harness/real_run/results_human_pass/legacy_counts.py \
        [paper/access2026/harness/real_run/cells.jsonl \
         paper/access2026/harness/real_run/llm_auxiliary_labels.jsonl]

Means are stored at full precision next to their numerator and denominator,
so BRIEF.md rounds once (half-up) from the stored value.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
KINDS = ("primary", "ablated_control", "preserved_control")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _span_empty(evidence) -> bool:
    if evidence is None:
        return True
    if isinstance(evidence, str):
        return evidence.strip() == ""
    if isinstance(evidence, list):
        return all(_span_empty(e) for e in evidence)
    raise TypeError(f"unexpected evidence type {type(evidence).__name__}")


def _mean_block(js: list) -> dict:
    n = len(js)
    return {"n": n, "sum_J": sum(js), "mean_J": (sum(js) / n) if n else None}


def _aux_block(rows: list) -> dict:
    a1 = [r["J"] for r in rows if r["A_aux"] == 1]
    a0 = [r["J"] for r in rows if r["A_aux"] == 0]
    return {
        "n_cells": len(rows),
        "n_A_aux_1": len(a1),
        "n_A_aux_0": len(a0),
        "J_given_A_aux_1": _mean_block(a1),
        "J_given_A_aux_0": _mean_block(a0),
        "n_empty_span": sum(r["empty"] for r in rows),
        "n_empty_span_with_A_aux_0": sum(r["empty"] and r["A_aux"] == 0 for r in rows),
        "n_J0": sum(r["J"] == 0 for r in rows),
    }


def main(argv: list) -> int:
    cells_path = Path(argv[1]) if len(argv) > 1 else HERE.parent / "cells.jsonl"
    aux_path = Path(argv[2]) if len(argv) > 2 else HERE.parent / "llm_auxiliary_labels.jsonl"
    out_path = HERE / "legacy_counts.json"

    cells = _rows(cells_path)
    aux = _rows(aux_path)
    by_id = {c["cell_id"]: c for c in cells}
    if len(by_id) != len(cells):
        raise SystemExit("duplicate cell_id in cells.jsonl")
    aux_by_id = {a["cell_id"]: a for a in aux}
    if len(aux_by_id) != len(aux):
        raise SystemExit("duplicate cell_id in llm_auxiliary_labels.jsonl")
    if set(aux_by_id) != set(by_id):
        raise SystemExit("cell_id sets of the two inputs differ")
    unknown = {c["cell_kind"] for c in cells} - set(KINDS)
    if unknown:
        raise SystemExit(f"unexpected cell_kind values: {sorted(unknown)}")

    joined = []
    for cid, c in by_id.items():
        a = aux_by_id[cid]
        joined.append({
            "kind": c["cell_kind"],
            "J": int(c["J"]),
            "A_aux": int(a["A_auxiliary"]),
            "empty": _span_empty(c["judge_response"]["evidence"]),
            "aux_J": int(a["J"]),
            "aux_empty_flag": bool(a["evidence_empty"]),
        })

    primary = [r for r in joined if r["kind"] == "primary"]
    controls = [r for r in joined if r["kind"] != "primary"]
    out = {
        "source": {
            "cells_jsonl_sha256": _sha256(cells_path),
            "llm_auxiliary_labels_jsonl_sha256": _sha256(aux_path),
            "reads": "judge J (cells.jsonl) and A_aux (LLM auxiliary check, label_source LLM); no human label",
            "writes": "aggregates only; no cell or CQ identifier",
        },
        "n_cells_by_kind": {k: sum(r["kind"] == k for r in joined) for k in KINDS},
        "judge_only_J_by_control_kind": {
            k: _mean_block([r["J"] for r in joined if r["kind"] == k])
            for k in ("ablated_control", "preserved_control")
        },
        "A_aux": {
            "all_224_cells": _aux_block(joined),
            "primary_cells": _aux_block(primary),
            "control_cells": _aux_block(controls),
        },
        "checks": {
            "aux_J_equals_judge_J_all_cells": all(r["J"] == r["aux_J"] for r in joined),
            "aux_evidence_empty_flag_equals_judge_span_empty_all_cells":
                all(r["empty"] == r["aux_empty_flag"] for r in joined),
            "judge_span_empty_iff_J0_all_cells": all(r["empty"] == (r["J"] == 0) for r in joined),
            "every_empty_span_has_A_aux_0": all(r["A_aux"] == 0 for r in joined if r["empty"]),
            "J_values_seen": sorted({r["J"] for r in joined}),
            "A_aux_values_seen": sorted({r["A_aux"] for r in joined}),
        },
    }
    out_path.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
