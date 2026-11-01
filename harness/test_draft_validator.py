"""Tests for the standalone AI-draft CSV validator.

ALL DATA HERE IS SYNTHETIC scaffolding material; none of it is a study label.
Fixtures are built minimal and self-contained (same shape as
test_label_assist.make_views/make_sheet so the contract is exercised against
the real 12-column sheet + rendered_view_{V}.txt layout).
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
# harness test convention (sibling-module import via sys.path, see
# test_label_assist.py); pyright cannot model the path hack.
import validate_draft as vd  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]

SHEET_HEADER = ["cell_id", "cq_id", "cluster_id", "category", "variant", "cq_text",
                "judge_evidence_span", "rendered_view_path", "evidence_span_verbatim",
                "A", "rater_L1", "note"]
DRAFT_HEADER = ["cell_id", "A_draft", "rater_L1_draft", "span_draft",
                "note_draft", "model", "generated_at"]


def make_views(tmp_path: Path) -> Path:
    views = tmp_path / "views"
    views.mkdir(parents=True, exist_ok=True)
    lines = []
    for v in "ABCDEF":
        name = f"rendered_view_{v}.txt"
        (views / name).write_bytes(
            f"VIEW {v}\nbrick:Zone — definition anchor for variant {v}\nline3\n".encode("utf-8"))
        digest = hashlib.sha256((views / name).read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}")
    (views / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return views


def make_sheet(tmp_path: Path, n: int = 3) -> Path:
    rows = [SHEET_HEADER]
    for i in range(1, n + 1):
        variant = "ABCDEF"[(i - 1) % 6]
        rows.append([f"cat:{variant}:CQB{i:02d}", f"CQB{i:02d}", f"CQB{i:02d}",
                     "concept_definition", variant, f"What is thing {i}?", "",
                     "/abs/stale/rendered_view.txt", "", "", "", ""])
    path = tmp_path / "sheet.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    return path


def good_row(i: int, a: str = "1", span: str | None = "anchor for variant A",
             note: str = "", model: str = "draftmodel-v1",
             ts: str = "2026-10-01T09:00:00+09:00") -> list[str]:
    variant = "ABCDEF"[(i - 1) % 6]
    if span is not None:
        span = span.replace("variant A", f"variant {variant}")
    if a == "0":
        span, note = "", (note or "뷰에 핵심 관계 미진술")
    return [f"cat:{variant}:CQB{i:02d}", a, "2" if a == "1" else "1",
            span, note, model, ts]


def make_draft(tmp_path: Path, rows: list[list[str]], name: str = "draft_224.csv",
               header: list[str] | None = None) -> Path:
    path = tmp_path / name
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header if header is not None else DRAFT_HEADER)
        w.writerows(rows)
    return path


def validate(tmp_path: Path, draft: Path) -> list[str]:
    return vd.validate_draft(draft, make_sheet(tmp_path), make_views(tmp_path))


# 1. happy path: a fully valid draft (any row order) -> zero errors
def test_valid_draft_returns_no_errors_in_any_order(tmp_path: Path) -> None:
    rows = [good_row(2), good_row(3, a="0"), good_row(1)]  # order shuffled on purpose
    errs = validate(tmp_path, make_draft(tmp_path, rows))
    assert errs == [], errs


# 2. header contract ---------------------------------------------------------
def test_bad_header_rejected(tmp_path: Path) -> None:
    bad = list(DRAFT_HEADER)
    bad[1] = "A"
    errs = validate(tmp_path, make_draft(tmp_path, [good_row(1)], header=bad))
    assert len(errs) == 1 and "헤더" in errs[0]


# 3. cell_id coverage: missing, duplicate, extra ------------------------------
def test_missing_cell_id_reported(tmp_path: Path) -> None:
    errs = validate(tmp_path, make_draft(tmp_path, [good_row(1), good_row(2)]))
    assert len(errs) == 1 and "cat:C:CQB03" in errs[0]


def test_duplicate_cell_id_reported(tmp_path: Path) -> None:
    rows = [good_row(1), good_row(1), good_row(2), good_row(3)]
    errs = validate(tmp_path, make_draft(tmp_path, rows))
    assert any("중복" in e and "cat:A:CQB01" in e for e in errs), errs


def test_extra_cell_id_not_in_sheet_reported(tmp_path: Path) -> None:
    row = good_row(1)
    row[0] = "ghost:Z:CQB99"
    errs = validate(tmp_path, make_draft(tmp_path, [row, good_row(2), good_row(3)]))
    assert any("ghost:Z:CQB99" in e for e in errs), errs


# 4. span must be an exact substring of the cell's variant view ---------------
def test_span_not_in_view_rejected(tmp_path: Path) -> None:
    row = good_row(1, span="this sentence is nowhere in the rendered view")
    errs = validate(tmp_path, make_draft(tmp_path, [row, good_row(2), good_row(3)]))
    assert any("cat:A:CQB01" in e and "view" in e.lower() or "뷰" in e for e in errs), errs


def test_span_from_wrong_variant_view_rejected(tmp_path: Path) -> None:
    # row 2's variant is B but the span quotes variant A's view text
    row = good_row(2)
    row[3] = "anchor for variant A"
    errs = validate(tmp_path, make_draft(tmp_path, [good_row(1), row, good_row(3)]))
    assert any("cat:B:CQB02" in e for e in errs), errs


# 5/6. decision-dependent field rules ------------------------------------------
def test_a1_requires_nonempty_span(tmp_path: Path) -> None:
    row = good_row(1, a="1", span="")
    errs = validate(tmp_path, make_draft(tmp_path, [row, good_row(2), good_row(3)]))
    assert any("cat:A:CQB01" in e and "span" in e for e in errs), errs


def test_a0_requires_note_and_empty_span(tmp_path: Path) -> None:
    row = good_row(3, a="0")
    row[3], row[4] = "anchor for variant C", ""  # span present + note missing
    errs = validate(tmp_path, make_draft(tmp_path, [good_row(1), good_row(2), row]))
    assert any("cat:C:CQB03" in e and "note" in e for e in errs), errs
    assert any("cat:C:CQB03" in e and "span" in e for e in errs), errs


# 7. value domains + provenance fields ------------------------------------------
def test_bad_domain_and_empty_provenance_reported(tmp_path: Path) -> None:
    row = good_row(1)
    row[1], row[2], row[5], row[6] = "2", "9", "", ""
    errs = validate(tmp_path, make_draft(tmp_path, [row, good_row(2), good_row(3)]))
    assert any("cat:A:CQB01" in e and "A_draft" in e for e in errs), errs
    assert any("cat:A:CQB01" in e and "rater_L1_draft" in e for e in errs), errs
    assert any("cat:A:CQB01" in e and "model" in e for e in errs), errs
    assert any("cat:A:CQB01" in e and "generated_at" in e for e in errs), errs


# 8. CLI contract: 0 on valid, 1 + error lines on invalid -----------------------
def test_cli_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sheet, views = make_sheet(tmp_path), make_views(tmp_path)
    good = make_draft(tmp_path, [good_row(1), good_row(2), good_row(3)])
    assert vd.main(["--draft", str(good), "--sheet", str(sheet), "--views", str(views)]) == 0
    bad = make_draft(tmp_path, [good_row(1), good_row(2)])  # row 3 missing
    assert vd.main(["--draft", str(bad), "--sheet", str(sheet), "--views", str(views)]) == 1
    printed = capsys.readouterr().out
    assert "cat:C:CQB03" in printed


def test_cli_missing_draft_file_exits_1(tmp_path: Path) -> None:
    sheet, views = make_sheet(tmp_path), make_views(tmp_path)
    missing = tmp_path / "nope.csv"
    assert vd.main(["--draft", str(missing), "--sheet", str(sheet), "--views", str(views)]) == 1
