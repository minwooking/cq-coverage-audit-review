"""Tests of analyze.py (synthetic data, no model).  AI-generated; review before reuse."""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze as A  # noqa: E402
import s4_common as C  # noqa: E402


def test_mde_reproduces_paper_value():
    assert abs(A.mde(1.155, 23) - 0.675) < 0.001


def test_contrast_known_values():
    d = {f"c{i}": x for i, x in enumerate([1.0, 1.0, 0.0, 2.0, 1.0, 0.0, 1.0, 1.0, 2.0, 1.0, 1.0, 0.0])}
    r = A.contrast_from_d(d)
    assert r["n_clusters"] == 12 and abs(r["delta"] - np.mean(list(d.values()))) < 1e-12
    assert r["ci95"][0] > 0 and r["decision"] == "resolved"
    assert r["sign_test"] == {"n_pos": 9, "n_neg": 0, "n_zero": 3, "p": pytest.approx(2 * 0.5 ** 9)}
    assert r["underpowered_flag"] is False


def test_contrast_null_is_not_resolved_and_small_n_flagged():
    r = A.contrast_from_d({f"c{i}": x for i, x in enumerate([1, -1, 0, 1, -1, 0, 0, 1])})
    assert r["decision"] != "resolved" and r["underpowered_flag"] is True
    assert A.contrast_from_d({"c": 1.0})["decision"] == "underpowered"


def test_cell_scores_mean_median_and_invalid_skipped():
    rows = [{"cell_id": "x", "valid": 1, "J": j} for j in (0, 3, 3)] + [{"cell_id": "x", "valid": 0, "J": None}]
    assert A.cell_scores(rows)["x"] == pytest.approx(2.0)
    assert A.cell_scores(rows, "median")["x"] == 3.0


def test_verbatim_summary_counts_credits_only():
    rows = [{"variant": "A", "valid": 1, "J": 3, "verbatim": 1, "verbatim_elided": 1},
            {"variant": "A", "valid": 1, "J": 2, "verbatim": 0, "verbatim_elided": 1},
            {"variant": "A", "valid": 1, "J": 1, "verbatim": 0, "verbatim_elided": 0},
            {"variant": "B", "valid": 1, "J": 0, "verbatim": 1, "verbatim_elided": 1}]
    s = A.verbatim_summary(rows)
    assert s["A"]["credits_J_ge_2"] == 2 and s["A"]["verbatim_strict"] == 1 and s["A"]["verbatim_elided"] == 2
    assert s["B"]["credits_J_ge_2"] == 0 and s["B"]["share_strict"] is None


def test_matcher_is_the_review9_one():
    view = A.an.norm("The  height of a tree is the observed property.")
    assert A.an.verbatim(["The height of a tree"], view)
    assert not A.an.verbatim(["the height of a tree"], view)            # case sensitive
    assert A.r9.verbatim_elided("The height of a tree ... the observed property.", view)


def test_domain_result_and_pooling(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "ddir", lambda d: (tmp_path / d).mkdir(exist_ok=True) or tmp_path / d)
    rng = np.random.default_rng(1)
    for d in ("x1", "x2"):
        ids = [f"{d}{i:02d}" for i in range(12)]
        cells = {}
        for c in ids:
            for v in "AB":
                cells[f"primary:{v}:{c}"] = {"variant": v, "cq_id": c, "eligible": True}
        (tmp_path / d).mkdir(exist_ok=True)
        (tmp_path / d / "eligibility.json").write_text(json.dumps({"bank_sha256": "0", "n_questions": 12, "eligible_cells": {"A": 12, "B": 12},
                                                              "eligible_clusters_A_or_B": 12, "eligible_in_both": ids, "cells": cells}))
        with (tmp_path / d / "scores_glm.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=A.FIELDS)
            w.writeheader()
            for c in ids:
                for v, base in (("A", 1), ("B", 2)):
                    for r in (1, 2, 3):
                        w.writerow({"cell_id": f"primary:{v}:{c}", "variant": v, "cq_id": c, "repeat": r, "valid": 1, "J": base + (r == 1 and v == "B" and 0),
                                    "verbatim": 1, "verbatim_elided": 1})
    per = {d: {"glm": A.domain_result(d, "glm")} for d in ("x1", "x2")}
    r = per["x1"]["glm"]["mean_of_repeats"]
    assert r["delta"] == pytest.approx(1.0) and r["mean_J_A"] == 1.0 and r["mean_J_B"] == 2.0
    assert r["coverage_both_set"]["A"]["coverage_pct"] == pytest.approx(100 * 12 / 36)
    p = A.pooled(per, "glm")
    assert p["mean_of_repeats"]["n_clusters"] == 24 and p["mean_of_repeats"]["delta"] == pytest.approx(1.0)
    assert p["verbatim"]["A"]["credits_J_ge_2"] == 0 and p["verbatim"]["B"]["credits_J_ge_2"] == 72
