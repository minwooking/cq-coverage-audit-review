"""Synthetic tests for the fixed failure-family decomposition.

These tests do not use study labels.  They verify only precedence, exclusivity,
residual handling, and denominator arithmetic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import failure_family as ff  # noqa: E402


def row(**updates):
    value = {
        "cq_id": "CQ1",
        "cluster_id": "CQ1",
        "variant": "BRICK_SOURCE",
        "J": 3,
        "A": 1,
        "claimed_evidence": "supporting span",
        "span_found_verbatim_in_artifact": True,
        "judge_response_unusable": False,
        "SIMULATED": True,
        "label_source": "LLM, not human",
    }
    value.update(updates)
    return value


def test_precedence_parse_failure_beats_missing_and_unsupported():
    record = row(
        claimed_evidence="",
        A=0,
        judge_response_unusable=True,
    )
    assert ff.classify_cell(record)[0] == "judge_parse_failure"


def test_precedence_missing_citation_beats_unsupported():
    record = row(claimed_evidence="", A=0)
    assert ff.classify_cell(record)[0] == "missing_evidence_citation"


def test_formal_run_holdout_evidence_field_is_used():
    record = row(
        claimed_evidence="stale simulated field",
        judge_response={"score": 3, "evidence": ""},
        A=0,
    )
    assert ff.classify_cell(record)[0] == "missing_evidence_citation"


def test_unsupported_citation_is_a_zero_a_record():
    assert ff.classify_cell(row(A=0))[0] == "unsupported_evidence"


def test_supported_citation_is_success():
    assert ff.classify_cell(row(A=1))[0] == "success"


def test_unavailable_formal_placeholder_goes_to_other():
    record = row(A=0, label_source="pending human evidence")
    assert ff.classify_cell(record)[0] == "other"


def test_unrecognized_record_goes_to_other():
    record = row(A="not-a-label", label_source="human annotation")
    assert ff.classify_cell(record)[0] == "other"


def test_every_record_gets_exactly_one_bucket():
    records = [
        row(cq_id="Q1", A=1),
        row(cq_id="Q2", A=0),
        row(cq_id="Q3", claimed_evidence="", A=0),
        row(cq_id="Q4", judge_response_unusable=True),
        row(cq_id="Q5", A=0, label_source="pending human evidence"),
    ]
    assignments = [ff.classify_cell(record) for record in records]
    buckets = [bucket for bucket, _reason in assignments]
    assert len(assignments) == len(records)
    assert all(bucket in ff.BUCKETS for bucket in buckets)
    assert set(buckets) == {
        "success", "unsupported_evidence", "missing_evidence_citation",
        "judge_parse_failure", "other",
    }


def test_denominator_and_failure_sum_are_consistent(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    records = [
        row(cq_id="Q1", A=1),
        row(cq_id="Q2", A=0),
        row(cq_id="Q3", claimed_evidence="", A=0),
        row(cq_id="Q4", judge_response_unusable=True),
        row(cq_id="Q5", A=0, label_source="pending human evidence"),
    ]
    (run_dir / "cells.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    result = ff.summarize(run_dir)
    assert result["denominator"]["n_cells"] == 5
    assert sum(result["counts"].values()) == 5
    assert result["counts"]["success"] + sum(
        result["counts"][bucket] for bucket in ff.FAILURE_BUCKETS
    ) == 5
    assert all(result["checks"].values())


def test_other_is_residual_for_unclassifiable_row(tmp_path: Path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "cells.jsonl").write_text(json.dumps(row(
        A=0, label_source="pending human evidence"
    )) + "\n", encoding="utf-8")
    result = ff.summarize(run_dir)
    assert result["counts"] == {
        "success": 0,
        "judge_parse_failure": 0,
        "missing_evidence_citation": 0,
        "unsupported_evidence": 0,
        "other": 1,
    }


def test_formal_parse_failure_is_detected_from_run_holdout_shape():
    record = {
        "cq_id": "Q1",
        "J": 0,
        "A": 0,
        "judge_response": {"_error": "content is null"},
        "judge_response_parsed": False,
        "SIMULATED": False,
        "label_source": "pending human evidence",
    }
    assert ff.classify_cell(record)[0] == "judge_parse_failure"
