"""Tests of analyze.py (synthetic data, no model).  AI-generated; review before reuse."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze as A  # noqa: E402


def cells(scope, n, variants="ABCDEF"):
    return [{"panel_id": f"{scope}|primary:{v}:{i}", "scope": scope, "domain": scope, "variant": v, "cq_id": str(i), "cluster": f"{scope}:{i}"}
            for i in range(n) for v in variants]


def means(cs, f):
    return {c["panel_id"]: f(c) for c in cs}


LEVEL = {v: k * 0.5 for k, v in enumerate("ABCDEF")}


def test_monotone_ladder_is_resolved_adjacent_and_flagged_monotone():
    cs = cells("dcat", 14)
    m = means(cs, lambda c: 0.5 + LEVEL[c["variant"]] + (0.1 if int(c["cq_id"]) % 2 else 0))
    r = A.contrasts_for(cs, m)
    assert r["B->C|dcat"]["verdict"] == "resolved_C_gt_B" and r["A->F|dcat"]["verdict"] == "resolved_F_gt_A"
    lad = A.ladder_means(cs, m)
    com = A.common_clusters_means(cs, m)
    assert A.monotone([lad["dcat"][v]["mean_J"] for v in A.CHAIN])["monotone_nondecreasing"] is True
    assert com["dcat"]["n_clusters"] == 14


def test_non_monotone_and_missing_cells():
    cs = cells("dcat", 12)
    m = means(cs, lambda c: 2.0 - (0.4 if c["variant"] == "D" else 0.0))
    for i in range(3):
        del m[f"dcat|primary:E:{i}"]
    r = A.contrasts_for(cs, m)
    assert r["C->D|dcat"]["verdict"] == "resolved_C_gt_D"
    assert r["D->E|dcat"]["n_clusters"] == 9
    assert A.monotone([2.0, 1.6, 2.0])["monotone_nondecreasing"] is False
    assert A.common_clusters_means(cs, m)["dcat"]["n_clusters"] == 9


def test_pooled_scope_qualifies_clusters_and_small_n_underpowered():
    cs = cells("dcat", 6) + cells("ssn", 6)
    m = means(cs, lambda c: 1.0 + (c["variant"] == "B"))
    r = A.contrasts_for(cs, m)
    assert r["A->B|dcat"]["verdict"] == "underpowered"
    assert r["A->B|new_domains_pooled"]["n_clusters"] == 12
    assert r["A->B|prov"]["verdict"] == "none"


def test_equivalence_at_two_margins():
    cs = cells("dcat", 14)
    m = means(cs, lambda c: 2.0 + (0.4 if (c["variant"] == "C" and int(c["cq_id"]) % 2) else 0) - (0.4 if (c["variant"] == "C" and int(c["cq_id"]) % 2 == 0) else 0))
    r = A.contrasts_for(cs, m)["B->C|dcat"]
    assert r["verdict"] in ("equivalent", "unresolved") and r["verdict_030"] in ("equivalent", "unresolved")
