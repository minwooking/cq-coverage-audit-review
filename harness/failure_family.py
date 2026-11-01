#!/usr/bin/env python3
"""Decompose holdout cells into fixed, observable failure families.

This module deliberately does not call a model.  It consumes the JSONL records
written by ``run_holdout.py`` (or the compatible simulated record format),
assigns exactly one precedence-ordered bucket to each row, and writes both a
machine-readable JSON summary and a plain-text table.

The decomposition is an analysis of recorded fields, not a new judgment.  A
formal holdout's ``A=0`` in an unannotated ``run_holdout.py`` output is only a
placeholder (``label_source == 'pending human evidence'``), so such rows are
kept in ``other`` rather than being falsely called unsupported evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "access.failure_family.v1"
BUCKETS = (
    "success",
    "judge_parse_failure",
    "missing_evidence_citation",
    "unsupported_evidence",
    "other",
)
FAILURE_BUCKETS = tuple(bucket for bucket in BUCKETS if bucket != "success")


def _truth(value: Any) -> bool | None:
    """Interpret a recorded boolean without treating an absent field as false."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def _parse_failure(row: dict[str, Any]) -> bool:
    """Return whether the judge response is unusable or failed to parse.

    ``run_holdout.py`` records ``judge_response_parsed`` and stores errors such
    as ``content is null`` inside ``judge_response``.  Simulated records also
    expose ``judge_response_unusable``.  All are observable, so no inference is
    needed.
    """
    if _truth(row.get("judge_response_unusable")) is True:
        return True
    if _truth(row.get("judge_response_parsed")) is False:
        return True
    response = row.get("judge_response")
    return isinstance(response, dict) and any(
        key in response for key in ("_error", "_unparsed")
    )


def cited_evidence(row: dict[str, Any]) -> str:
    """Return the recorded judge citation, or an empty string.

    Formal records put it in ``judge_response.evidence``.  The simulated runner
    writes the same judge output as ``claimed_evidence`` instead.  The
    adjudicator's ``adjudicator_span`` is intentionally not used: it is a
    separate adjudication field, not the judge's citation.
    """
    response = row.get("judge_response")
    if isinstance(response, dict):
        evidence = response.get("evidence")
        return evidence.strip() if isinstance(evidence, str) else ""
    evidence = row.get("claimed_evidence")
    return evidence.strip() if isinstance(evidence, str) else ""


def _a_value(row: dict[str, Any]) -> int | None:
    """Return an adjudicated A value, or None when it is unavailable."""
    # run_holdout.py deliberately emits A=0 before the human evidence pass.
    # Simulated records may contain a synthetic A; they are classified for
    # harness verification but the summary is explicitly marked SIMULATED.
    if str(row.get("label_source", "")).strip().lower() == "pending human evidence":
        return None
    value = row.get("A")
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int) and value in (0, 1):
        return value
    if isinstance(value, str) and value.strip() in {"0", "1"}:
        return int(value.strip())
    return None


def classify_cell(row: dict[str, Any]) -> tuple[str, str]:
    """Assign one bucket using the frozen precedence order.

    Precedence is: parse failure, no citation, unsupported citation, success,
    residual ``other``.  The first matching rule wins; this makes the labels
    mutually exclusive even when a malformed row has several problems.
    """
    if _parse_failure(row):
        return "judge_parse_failure", "judge response unusable or not parsed"

    evidence = cited_evidence(row)
    if not evidence:
        return "missing_evidence_citation", "judge citation is absent or empty"

    a_value = _a_value(row)
    if a_value is None:
        return "other", "adjudicated A is unavailable or still a placeholder"
    if a_value == 0:
        return "unsupported_evidence", "citation present but A=0"
    if a_value == 1:
        return "success", "citation present and A=1"
    # Defensive fallback; _a_value currently prevents reaching this branch.
    return "other", "A is outside the recorded 0/1 domain"


def load_cells(run_dir: Path) -> list[dict[str, Any]]:
    """Load non-empty JSONL records from a run directory."""
    cells_path = run_dir / "cells.jsonl"
    if not cells_path.is_file():
        raise ValueError(f"missing cells.jsonl: {cells_path}")
    cells: list[dict[str, Any]] = []
    for line_number, line in enumerate(cells_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON at {cells_path}:{line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"record at {cells_path}:{line_number} is not an object")
        cells.append(row)
    if not cells:
        raise ValueError(f"no cell records in {cells_path}")
    return cells


def _simulated_flag(run_dir: Path, cells: list[dict[str, Any]]) -> bool:
    manifest_path = run_dir / "MANIFEST.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if _truth(manifest.get("SIMULATED")) is True:
                return True
        except (OSError, json.JSONDecodeError):
            pass
    return any(_truth(row.get("SIMULATED")) is True for row in cells)


def summarize(run_dir: Path) -> dict[str, Any]:
    """Return counts, all-cell proportions, and traceable row assignments."""
    cells = load_cells(run_dir)
    assignments: list[dict[str, Any]] = []
    counts = {bucket: 0 for bucket in BUCKETS}
    for index, row in enumerate(cells, 1):
        bucket, reason = classify_cell(row)
        counts[bucket] += 1
        assignments.append({
            "row_index": index,
            "cq_id": row.get("cq_id"),
            "cluster_id": row.get("cluster_id"),
            "variant": row.get("variant"),
            "bucket": bucket,
            "reason": reason,
        })

    n = len(cells)
    bucket_rows = [
        {
            "bucket": bucket,
            "count": counts[bucket],
            "proportion": counts[bucket] / n,
            "percentage": counts[bucket] / n * 100.0,
        }
        for bucket in BUCKETS
    ]
    simulated = _simulated_flag(run_dir, cells)
    result: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "source_run_dir": str(run_dir.resolve()),
        "SIMULATED": simulated,
        "warning": (
            "SIMULATED output; do not report as a study result."
            if simulated
            else None
        ),
        "denominator": {
            "definition": "all cell records in cells.jsonl, including successes",
            "n_cells": n,
        },
        "failure_numerator_definition": (
            "success is excluded from failure numerators; each non-success row "
            "is assigned to exactly one precedence-ordered failure bucket"
        ),
        "buckets": bucket_rows,
        "counts": counts,
        "assignments": assignments,
        "checks": {
            "all_cells_assigned_once": len(assignments) == n,
            "bucket_sum_equals_denominator": sum(counts.values()) == n,
            "failure_sum_plus_success_equals_denominator": (
                sum(counts[bucket] for bucket in FAILURE_BUCKETS) + counts["success"] == n
            ),
        },
    }
    return result


def render_table(result: dict[str, Any]) -> str:
    """Render a stable, human-readable summary table."""
    denominator = result["denominator"]["n_cells"]
    lines = [
        "Failure-family decomposition",
        f"Denominator: all cell records (n={denominator}); success is excluded from failure numerators.",
    ]
    if result.get("SIMULATED"):
        lines.append("WARNING: SIMULATED output; do not report as a study result.")
    lines.extend([
        "",
        f"{'bucket':<28} {'count':>7} {'proportion':>12} {'percent':>10}",
        f"{'-' * 28} {'-' * 7} {'-' * 12} {'-' * 10}",
    ])
    by_bucket = {row["bucket"]: row for row in result["buckets"]}
    for bucket in BUCKETS:
        row = by_bucket[bucket]
        lines.append(
            f"{bucket:<28} {row['count']:>7} {row['proportion']:>12.6f} "
            f"{row['percentage']:>9.3f}%"
        )
    failure_sum = sum(by_bucket[bucket]["count"] for bucket in FAILURE_BUCKETS)
    lines.extend([
        "",
        f"failure buckets (excluding success): {failure_sum}",
        f"bucket sum: {sum(row['count'] for row in result['buckets'])} / {denominator}",
        "Assignments are retained in the JSON output by row_index and cq_id.",
    ])
    return "\n".join(lines) + "\n"


def write_outputs(result: dict[str, Any], json_path: Path, table_path: Path) -> None:
    """Persist JSON and table outputs, creating parent directories as needed."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    table_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    table_path.write_text(render_table(result), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="directory containing cells.jsonl")
    parser.add_argument("--json-out", type=Path, default=None,
                        help="JSON output path (default: RUN_DIR/failure_family.json)")
    parser.add_argument("--table-out", type=Path, default=None,
                        help="text table path (default: RUN_DIR/failure_family.txt)")
    args = parser.parse_args(argv)
    try:
        result = summarize(args.run_dir)
    except ValueError as exc:
        parser.error(str(exc))
    json_path = args.json_out or args.run_dir / "failure_family.json"
    table_path = args.table_out or args.run_dir / "failure_family.txt"
    write_outputs(result, json_path, table_path)
    table = render_table(result)
    sys.stdout.write(table)
    sys.stdout.write(f"JSON: {json_path}\nTABLE: {table_path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
