"""Tests of analyze.py (synthetic data, no model).  AI-generated; review before reuse."""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze as A  # noqa: E402


def cells(scope, n, variants="AB"):
    return [{"panel_id": f"{scope}|primary:{v}:{i}", "scope": scope, "domain": scope, "variant": v, "cq_id": str(i), "cluster": f"{scope}:{i}"}
            for i in range(n) for v in variants]


def means(cs, f):
    return {c["panel_id"]: f(c) for c in cs}


def test_d_by_cluster_needs_both_cells():
    cs = cells("dcat", 3)
    m = means(cs, lambda c: 2.0 if c["variant"] == "B" else 1.0)
    del m["dcat|primary:B:2"]
    assert A.d_by_cluster(cs, m, "A", "B") == {"dcat:0": 1.0, "dcat:1": 1.0}


def test_resolved_direction_and_verdict_labels():
    cs = cells("dcat", 14)
    pos = A.contrasts_for(cs, means(cs, lambda c: (2.0 if c["variant"] == "B" else 1.0) + (0.2 if int(c["cq_id"]) % 2 else 0)), [("A", "B")])
    assert pos["A->B|dcat"]["verdict"] == "resolved_B_gt_A"
    neg = A.contrasts_for(cs, means(cs, lambda c: 1.0 if c["variant"] == "B" else 2.0 + (0.2 if int(c["cq_id"]) % 2 else 0)), [("A", "B")])
    assert neg["A->B|dcat"]["verdict"] == "resolved_A_gt_B"


def test_small_n_is_underpowered_and_absent_scope_is_none():
    cs = cells("dcat", 4)
    r = A.contrasts_for(cs, means(cs, lambda c: 1.0 + (c["variant"] == "B")), [("A", "B")])
    assert r["A->B|dcat"]["verdict"] == "underpowered"
    assert r["A->B|ssn"]["verdict"] == "none"


def test_brick_pool_averages_banks_per_source_question():
    cs = cells("holdout", 2) + cells("paraphrases", 2)
    m = means(cs, lambda c: {"holdout": 2.0, "paraphrases": 1.0}[c["scope"]] if c["variant"] == "B" else 0.0)
    for c in cs:
        c["cluster"] = c["cq_id"]                      # brick banks cluster on the source question id
    d = A.scope_d(cs, m, "brick_pool", "A", "B")
    assert d == {"0": 1.5, "1": 1.5}


def test_pooled_domains_qualified_clusters():
    cs = cells("dcat", 2) + cells("ssn", 2)
    d = A.scope_d(cs, means(cs, lambda c: float(c["variant"] == "B")), "new_domains_pooled", "A", "B")
    assert set(d) == {"dcat:0", "dcat:1", "ssn:0", "ssn:1"}


def test_qwk_perfect_chance_and_constant():
    assert A.qwk([0, 1, 2, 3], [0, 1, 2, 3]) == pytest.approx(1.0)
    assert A.qwk([0, 3, 0, 3], [3, 0, 3, 0]) < 0
    assert A.qwk([1, 1], [1, 1]) is None
    assert A.qwk([], []) is None


def test_agreement_uses_median_low_and_shared_cells():
    s = {"glm": {"a": [3, 3, 0], "b": [1], "c": [2]}, "gptoss": {"a": [3], "b": [1], "d": [0]}}
    out = A.agreement(s, {"a", "b", "c", "d"})
    assert out["glm~gptoss"]["n_cells"] == 2 and out["glm~gptoss"]["exact_agreement"] == 1.0


def test_panel_counts_labels():
    pj = {"x": {"contrasts": {"A->B|brick_pool": {"verdict": "resolved_B_gt_A"}}}, "y": {"contrasts": {"A->B|brick_pool": {"verdict": "equivalent"}}},
          "z": {"contrasts": {}}}
    c = A.panel_counts(pj, "A->B|brick_pool", ["x", "y", "z"])
    assert (c["resolved_second_gt_first"], c["equivalent"], c["none"]) == (1, 1, 1)
