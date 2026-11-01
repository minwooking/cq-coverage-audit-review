from __future__ import annotations

import csv
from pathlib import Path

import pytest

from compute_agreement import agreement, load_labels, qwk


def test_binary_kappa_and_disagreement_list():
    result = agreement({"a": 0, "b": 1, "c": 1, "d": 0}, {"a": 0, "b": 1, "c": 0, "d": 1})
    assert result["n"] == 4
    assert result["raw_agreement"] == pytest.approx(0.5)
    assert result["cohen_kappa_binary"] == pytest.approx(0.0)
    assert result["disagreement_cell_ids"] == ["c", "d"]


def test_perfect_binary_kappa():
    result = agreement({"a": 0, "b": 1}, {"a": 0, "b": 1})
    assert result["cohen_kappa_binary"] == 1.0
    assert result["raw_agreement"] == 1.0


def test_g2_intra_rater_qwk_for_ordered_layer1_scores():
    # Non-perfect ordinal agreement; a one-step error is weighted less than a
    # three-step error by the quadratic distance matrix.
    result = qwk({"a": 0, "b": 1, "c": 2, "d": 3}, {"a": 0, "b": 1, "c": 3, "d": 2})
    assert result == pytest.approx(0.8)


def test_qwk_rejects_out_of_range_scores():
    with pytest.raises(ValueError, match="0..3"):
        qwk({"a": 4}, {"a": 3})


def test_rejects_unfilled_or_mismatched_cells(tmp_path: Path):
    left = tmp_path / "left.csv"
    with left.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["cell_id", "A"])
        writer.writeheader()
        writer.writerow({"cell_id": "a", "A": ""})
    with pytest.raises(ValueError, match="A must be an integer"):
        load_labels(left)
