"""Tests of the ladder analysis on synthetic data (no model, no network).  AI-generated; review before reuse."""
import csv
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze as A  # noqa: E402


def rec(cell, rep, J, valid=True):
    return {"cell_id": cell, "repeat": rep, "valid": valid, "J": J if valid else None, "prompt_tokens": 10, "completion_tokens": 2, "model": "m"}


def test_lists_from_raw_prefers_valid_and_skips_context(tmp_path):
    p = tmp_path / "a.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in [rec("c1", 1, None, False), rec("c1", 1, 2), rec("c1", 2, 3), rec("c2", 0, None, False), rec("c3", 1, None, False)]))
    lists, calls = A.lists_from_files(tmp_path, ("a.jsonl", "missing.jsonl"))
    assert sorted(lists["c1"]) == [(1, 2), (2, 3)] and "c3" not in lists
    assert calls["valid"] == 2 and calls["invalid"] == 1 and calls["context_skip"] == 1


def test_lists_from_csv_reads_valid_rows_only(tmp_path):
    p = tmp_path / "s.csv"
    with p.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["cell_id", "repeat", "J", "valid"])
        w.writerow(["x", 1, 3, "True"])
        w.writerow(["x", 2, "", "False"])
    lists, _ = A.lists_from_files(tmp_path, ("s.csv",))
    assert lists == {"x": [(1, 3)]}


def test_pair_agreement_only_pairs_with_ladder_judge():
    sc = {"glm": {"a": [3], "b": [1]}, "gptoss": {"a": [3], "b": [1]}, "q35_4b": {"a": [3], "b": [0]}}
    out = A.pair_agreement(sc, {"a", "b"})
    assert set(out) == {"glm~q35_4b", "gptoss~q35_4b"} and out["glm~q35_4b"]["n_cells"] == 2
    assert A.s5.JUDGE_ORDER == A.OTHERS          # restored


def test_contrasts_reuse_study5_rule_and_ladder_counts():
    cs = [{"panel_id": f"dcat|primary:{v}:{i}", "scope": "dcat", "domain": "dcat", "variant": v, "cq_id": str(i), "cluster": f"dcat:{i}"} for i in range(14) for v in "AB"]
    m = {c["panel_id"]: (2.0 if c["variant"] == "B" else 1.0) + (0.2 if int(c["cq_id"]) % 2 else 0) for c in cs}
    r = A.s5.contrasts_for(cs, m, [("A", "B")])
    pj = {"q35_4b": {"contrasts": r}}
    c = A.s5.panel_counts(pj, "A->B|dcat", ["q35_4b"])
    assert c["resolved_second_gt_first"] == 1


def test_report_and_tables_render_on_minimal_results():
    res = {"banner": "b", "judges_present": ["q35_4b"], "per_judge": {"q35_4b": {"label": "Qwen3.5-4B", "contrasts": {"A->B|dcat": {"n_clusters": 12, "delta": 0.5, "ci95": [0.1, 0.9], "verdict": "resolved_B_gt_A"}}, "calls": {}}},
           "ladder_counts": {"A->B|dcat": {"resolved_second_gt_first": 1, "resolved_first_gt_second": 0, "equivalent": 0, "unresolved": 0, "underpowered": 0, "judges": ["q35_4b"]}},
           "agreement_qwk": {"A_B_cells": {"glm~q35_4b": {"n_cells": 5, "qwk": 0.5, "exact_agreement": 0.6}}}}
    assert "Qwen3.5-4B" in A.report(res) and "resolved B gt A" in A.tables(res)
