#!/usr/bin/env python3
"""Compute annotation consistency statistics.

Default mode compares binary A evidence verdicts and reports raw agreement,
Cohen's kappa, and disagreement IDs.  G2 mode uses ``--score-column`` to
compare the same annotator's two 0--3 Layer-1 score exports and reports the
quadratic-weighted kappa point estimate.  G2 confidence intervals require the
preregistered clustered CI procedure and are not fabricated here.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def load_labels(path: Path, column: str = "A") -> dict[str, int]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError(f"empty label file: {path}")
    if "cell_id" not in rows[0] or column not in rows[0]:
        raise ValueError(f"{path} must contain cell_id and {column} columns")
    out: dict[str, int] = {}
    for row in rows:
        cell_id = row.get("cell_id", "")
        if not cell_id or cell_id in out:
            raise ValueError(f"missing or duplicate cell_id in {path}: {cell_id!r}")
        try:
            out[cell_id] = int(row[column])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{column} must be an integer in {path}, cell {cell_id!r}") from exc
    return out


def agreement(left: dict[str, int], right: dict[str, int]) -> dict:
    """Binary A raw agreement and Cohen's kappa."""
    if any(v not in {0, 1} for v in (*left.values(), *right.values())):
        raise ValueError("binary A labels must be 0 or 1")
    if set(left) != set(right):
        raise ValueError(
            f"cell_id sets differ: only-left={sorted(set(left) - set(right))}, "
            f"only-right={sorted(set(right) - set(left))}"
        )
    ids = sorted(left)
    if not ids:
        raise ValueError("no common cells")
    n = len(ids)
    raw = sum(left[cell] == right[cell] for cell in ids) / n
    p_left = sum(left.values()) / n
    p_right = sum(right.values()) / n
    expected = p_left * p_right + (1 - p_left) * (1 - p_right)
    kappa = 1.0 if raw == 1.0 and expected == 1.0 else (raw - expected) / (1 - expected) if expected != 1 else 0.0
    return {
        "n": n,
        "raw_agreement": raw,
        "cohen_kappa_binary": kappa,
        "disagreement_cell_ids": [cell for cell in ids if left[cell] != right[cell]],
        "metric": "binary A calibration/reassessment consistency diagnostic (not preregistered G2)",
    }


def qwk(left: dict[str, int], right: dict[str, int], maximum: int = 3) -> float:
    """Quadratic-weighted kappa for matched ordinal scores 0..maximum."""
    if set(left) != set(right):
        raise ValueError("cell_id sets differ; QWK requires matched cells")
    ids = sorted(left)
    if not ids:
        raise ValueError("no common cells")
    if any(v < 0 or v > maximum for v in (*left.values(), *right.values())):
        raise ValueError(f"ordinal scores must be in 0..{maximum}")
    n = len(ids)
    observed = sum((left[cell] - right[cell]) ** 2 for cell in ids) / n
    left_counts = [sum(value == score for value in left.values()) for score in range(maximum + 1)]
    right_counts = [sum(value == score for value in right.values()) for score in range(maximum + 1)]
    expected = sum(
        left_counts[i] * right_counts[j] * (i - j) ** 2
        for i in range(maximum + 1)
        for j in range(maximum + 1)
    ) / (n * n)
    if expected == 0:
        return 1.0 if observed == 0 else 0.0
    return 1.0 - observed / expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path, help="primary-pass CSV")
    parser.add_argument("right", type=Path, help="washout-reassessment CSV")
    parser.add_argument(
        "--score-column",
        default="A",
        help="A for binary evidence agreement; use rater_L1 for G2 QWK (0--3)",
    )
    args = parser.parse_args()
    left = load_labels(args.left, args.score_column)
    right = load_labels(args.right, args.score_column)
    if args.score_column == "A":
        result = agreement(left, right)
    else:
        result = {
            "n": len(left),
            "intra_rater_qwk": qwk(left, right),
            "score_column": args.score_column,
            "metric": "G2 preregistered intra-rater quadratic-weighted kappa",
            "ci_note": "Report the preregistered clustered CI separately; this utility reports the point estimate only.",
        }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
