from __future__ import annotations

import json
from pathlib import Path

import pytest

from build_label_packet import _constrained_shuffle, _make_rows, _read_cells


def _write_cells(run_dir: Path, cells: list[dict]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "cells.jsonl").write_text(
        "".join(json.dumps(cell, ensure_ascii=False) + "\n" for cell in cells),
        encoding="utf-8",
    )


def _cell(cq_id: str, variant: str, cell_id: str) -> dict:
    return {
        "cell_id": cell_id,
        "cq_id": cq_id,
        "cluster_id": cq_id,
        "category": "concept_definition",
        "variant": variant,
        "question": f"What is {cq_id}?",
        "judge_response": {"score": 2, "evidence": "some span"},
    }


def test_legacy_shared_schema_view_still_resolves(tmp_path: Path) -> None:
    # Old single-variant smoke/dryrun layout: run_dir/schema_view.txt, no
    # sibling variants/ directory with per-variant material.
    run_dir = tmp_path / "harness" / "dryrun"
    _write_cells(run_dir, [_cell("CQB01", "BRICK_SOURCE", "cell-1")])
    view_path = run_dir / "schema_view.txt"
    view_path.write_text("shared schema view content\n", encoding="utf-8")

    cells, variants_dir, shared_view_path = _read_cells(run_dir)
    assert variants_dir is None
    assert shared_view_path == view_path

    rows = _make_rows(cells, variants_dir, shared_view_path, bank_path=None)
    assert rows[0]["rendered_view_path"] == str(view_path.resolve())


def test_real_multivariant_run_resolves_per_variant_rendered_view(tmp_path: Path) -> None:
    # Real holdout layout: harness/real_run/cells.jsonl next to a sibling
    # harness/variants/{A,B}/rendered_view.txt -- the material actually
    # supplied to the judge differs by variant, so every row must point at
    # its own variant's file, never a single shared one.
    harness = tmp_path / "harness"
    run_dir = harness / "real_run"
    _write_cells(
        run_dir,
        [_cell("CQB01", "A", "cell-a"), _cell("CQB01", "B", "cell-b")],
    )
    for variant in ("A", "B"):
        variant_dir = harness / "variants" / variant
        variant_dir.mkdir(parents=True)
        (variant_dir / "rendered_view.txt").write_text(f"material for variant {variant}\n", encoding="utf-8")
    # No run_dir/schema_view.txt at all -- this is the real_run situation
    # this fix targets.
    assert not (run_dir / "schema_view.txt").exists()

    cells, variants_dir, shared_view_path = _read_cells(run_dir)
    assert variants_dir == harness / "variants"
    assert shared_view_path is None

    rows = _make_rows(cells, variants_dir, shared_view_path, bank_path=None)
    by_id = {row["cell_id"]: row for row in rows}
    assert by_id["cell-a"]["rendered_view_path"] == str((harness / "variants" / "A" / "rendered_view.txt").resolve())
    assert by_id["cell-b"]["rendered_view_path"] == str((harness / "variants" / "B" / "rendered_view.txt").resolve())
    # The two variants' material must not collapse onto the same file.
    assert by_id["cell-a"]["rendered_view_path"] != by_id["cell-b"]["rendered_view_path"]


def test_missing_schema_view_and_incomplete_variants_refuses(tmp_path: Path) -> None:
    harness = tmp_path / "harness"
    run_dir = harness / "real_run"
    _write_cells(run_dir, [_cell("CQB01", "A", "cell-a")])
    # variants/ exists but has no rendered_view.txt for variant A, and there
    # is no shared schema_view.txt either -- no material is resolvable.
    (harness / "variants" / "A").mkdir(parents=True)

    with pytest.raises(SystemExit):
        _read_cells(run_dir)


def test_constrained_shuffle_meets_min_gap_when_feasible() -> None:
    # 224 cells across 33 CQ-clusters, largest group size 9 (mirrors the real
    # holdout run's shape): (9-1)*(20+1)+3 = 171 <= 224, so min_gap=20 is
    # feasible and must be achieved exactly, not merely attempted.
    rows = []
    sizes = [9, 9, 9, 8, 8, 8, 8, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 5, 5, 5]
    assert sum(sizes) == 224
    for i, size in enumerate(sizes):
        cq_id = f"CQ{i:02d}"
        for j in range(size):
            rows.append({"cq_id": cq_id, "n": j})

    shuffled = _constrained_shuffle(rows, seed=20260913, min_gap=20)
    assert len(shuffled) == len(rows)
    assert sorted((r["cq_id"], r["n"]) for r in shuffled) == sorted((r["cq_id"], r["n"]) for r in rows)

    positions: dict[str, list[int]] = {}
    for index, row in enumerate(shuffled):
        positions.setdefault(row["cq_id"], []).append(index)
    gaps = [b - a for idxs in positions.values() for a, b in zip(idxs, idxs[1:])]
    assert min(gaps) >= 20


def test_constrained_shuffle_degrades_gracefully_when_infeasible(capsys: pytest.CaptureFixture[str]) -> None:
    # 72 cells with a group of 5 repeats: (5-1)*(20+1)+1 = 85 > 72, so
    # min_gap=20 is mathematically infeasible. The function must still
    # return every row (no data loss) and warn rather than silently
    # producing an unconstrained shuffle.
    rows = [{"cq_id": "CQB01", "n": i} for i in range(5)] + [
        {"cq_id": f"CQ{i:02d}", "n": 0} for i in range(67)
    ]
    shuffled = _constrained_shuffle(rows, seed=20260914, min_gap=20)
    assert len(shuffled) == len(rows)
    assert sorted((r["cq_id"], r["n"]) for r in shuffled) == sorted((r["cq_id"], r["n"]) for r in rows)
    captured = capsys.readouterr()
    assert "infeasible" in captured.err

    positions = [i for i, r in enumerate(shuffled) if r["cq_id"] == "CQB01"]
    gaps = [b - a for a, b in zip(positions, positions[1:])]
    # The greedy is not globally optimal once resources run low near the end
    # of the row set, but it must still land far from the pathological
    # gap-of-1 that plain random shuffling (or the old 500-retry heuristic)
    # produced on this exact shape. 10 is a safe floor for the observed,
    # deterministic (seeded) outcome.
    assert min(gaps) >= 10


def test_constrained_shuffle_is_deterministic_for_a_fixed_seed() -> None:
    rows = [{"cq_id": f"CQ{i % 5:02d}", "n": i} for i in range(20)]
    first = _constrained_shuffle(rows, seed=42, min_gap=3)
    second = _constrained_shuffle(rows, seed=42, min_gap=3)
    assert first == second
