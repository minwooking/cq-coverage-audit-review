"""Tests for build_label_packet --domain (IOF packet, PREREG addendum 15 §15.7-4).

ALL run data here is synthetic scaffolding under tmp_path. The committed IOF
bank and packaged variants_iof views are read as frozen INPUTS and never
written. The failure this pins: without --domain, the brick path-walk from
harness/real_run_iof silently resolves the BRICK bank and the BRICK variants
directory, producing an IOF packet with the wrong CQ text and views.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ACCESS = HERE.parent
sys.path.insert(0, str(ACCESS / "annotation" / "packet"))
import build_label_packet as blp  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]

BANK = ACCESS / "bank" / "iof" / "cq_bank_iof_v1.csv"
VIEWS_IOF = ACCESS / "harness" / "variants_iof"


def _cell(cid: str, kind: str, cq_id: str, variant: str) -> dict:
    return {"cell_id": cid, "cell_kind": kind, "cq_id": cq_id, "cluster_id": cq_id,
            "category": "taxonomy", "variant": variant, "J": 2,
            "judge_response": {"score": 2, "evidence": "span-x"}}


def _run_dir(tmp_path: Path, cells: list[dict]) -> Path:
    run_dir = tmp_path / "real_run_fake"
    run_dir.mkdir()
    (run_dir / "cells.jsonl").write_text(
        "\n".join(json.dumps(c) for c in cells), encoding="utf-8")
    return run_dir


@pytest.fixture()
def iof_argv(tmp_path, monkeypatch):
    def make(run_dir: Path, out: Path) -> None:
        monkeypatch.setattr(sys, "argv", ["build_label_packet", str(run_dir),
                                          "--domain", "iof", "--out-dir", str(out)])
    return make


def test_iof_sheet_rows_and_domain_resolution(tmp_path, iof_argv):
    # Given: a synthetic IOF run (2 primary + 1 ablated control) and the frozen IOF material
    cells = [_cell("primary:A:CQI01", "primary", "CQI01", "A"),
             _cell("primary:B:CQI02", "primary", "CQI02", "B"),
             _cell("ablated_control:A:CQI03", "ablated_control", "CQI03", "A")]
    run_dir = _run_dir(tmp_path, cells)
    out = tmp_path / "out"
    # When: the packet is built for the iof domain
    iof_argv(run_dir, out)
    assert blp.main() == 0
    with (out / "labels_primary_pass_blank.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    by_id = {r["cell_id"]: r for r in rows}
    # Then: every scored cell (primary AND controls) is present, views resolve to
    # variants_iof (not the brick variants dir), and CQ text comes from the IOF bank
    assert len(rows) == len(cells)
    for r in rows:
        assert "variants_iof" in r["rendered_view_path"]
        assert Path(r["rendered_view_path"]).is_file()
    bank = {r["cq_id"]: r for r in csv.DictReader(BANK.open(newline="", encoding="utf-8"))}
    assert by_id["primary:A:CQI01"]["cq_text"] == bank["CQI01"]["question"]
    assert by_id["primary:A:CQI01"]["judge_evidence_span"] == "span-x"
    assert by_id["primary:A:CQI01"]["evidence_span_verbatim"] == ""


def test_iof_no_washout_sheet(tmp_path, iof_argv, capsys):
    run_dir = _run_dir(tmp_path, [_cell("primary:A:CQI01", "primary", "CQI01", "A")])
    out = tmp_path / "out"
    iof_argv(run_dir, out)
    blp.main()
    assert not (out / "labels_washout_reassessment_pass_blank.csv").exists()
    assert "no IOF washout" in capsys.readouterr().out


def test_iof_refuses_wrong_variant_material(tmp_path, iof_argv):
    run_dir = _run_dir(tmp_path, [_cell("primary:Z:CQI01", "primary", "CQI01", "Z")])
    iof_argv(run_dir, tmp_path / "out")
    with pytest.raises(SystemExit):
        blp.main()


def test_brick_default_path_unchanged(tmp_path):
    """Brick without --domain still builds 224+72 rows from the real run (read-only)."""
    monkeypatch_argv = ["build_label_packet", str(ACCESS / "harness" / "real_run"),
                        "--out-dir", str(tmp_path / "out")]
    sys.argv[:] = monkeypatch_argv
    try:
        assert blp.main() == 0
    finally:
        sys.argv[:] = ["pytest"]
    with (tmp_path / "out" / "labels_primary_pass_blank.csv").open(newline="", encoding="utf-8") as fh:
        assert len(list(csv.DictReader(fh))) == 224
    with (tmp_path / "out" / "labels_washout_reassessment_pass_blank.csv").open(newline="", encoding="utf-8") as fh:
        assert len(list(csv.DictReader(fh))) == 72
