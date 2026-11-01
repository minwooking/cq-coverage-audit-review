#!/usr/bin/env python3
"""Second-annotator (n = 48) cell list and annotation packet -- PREREG sec.12.4.

1. Reproduces the registered 48-cell list exactly as sec.12.4 pins it: the primary
   cells of ``harness/real_run/cells.jsonl``, using only the ``cell_id``,
   ``cell_kind`` and ``category`` fields (no judge score and no other field is kept),
   categories in name order, ``cell_id`` sorted inside a category, one
   ``random.Random(20260913)`` and ``rng.sample(sorted_ids, 8)`` per category. The
   serialized list (sorted ids, one per line, trailing newline, UTF-8) must hash to the
   registered sha256; the run is refused otherwise. Optionally the bytes are compared
   with a separately computed copy (``--verify-list``).
2. Builds the annotator's sheet in the AH-pass sheet format
   (``annotation_pending/primary_pass_224_ready_to_fill.csv``, 12 columns), restricted
   to those 48 cells: no draft column, no translation, no label, no judge score. Only
   ``rendered_view_path`` differs from the AH rows (see below). Row order is the
   registered constrained shuffle (seed 20260913); the achieved same-CQ spacing is
   reported. The 20-position separation is not reachable for this row set (two CQs
   contribute four cells), so the report says what was reached.
3. Writes ``MANIFEST.json`` (sha256 of every file and input) whose
   ``contents_statement`` says the sheet holds no J, no labels and no drafts. Every part
   of that statement is checked before the file is written.

``rendered_view_path``: the AH sheet stores an absolute path into a worktree that no
longer exists; label_assist ignored it and picked the view by variant. In a packet the
column is the view's file name relative to ``--views`` (``rendered_view_<V>.txt``), the
name ``label_assist.py --packet`` resolves and sha256-checks. Nothing else in a
row is changed.

Serve it with::

    label_assist.py --packet --require-note --sheet <packet>/second_annotator_sheet_48.csv \\
        --views harness/real_run/annotation_pending/views --out <outside the repo>/working.csv

``--require-note`` makes the note a required field of every save, so the second annotator fills
all four columns (PREREG sec.12.4 DN-9, sec.13.1 item 8); without it ``--packet`` takes the note as
optional, which is the washout's rule.
"""
from __future__ import annotations

import argparse
import collections
import csv
import io
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import label_assist as la  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
import packet_common as pc  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]

REAL_RUN = pc.HERE / "real_run"
SEED = pc.REGISTERED_SEED
PER_CATEGORY = 8
CELLS_FIELDS = ("cell_id", "cell_kind", "category")
PINNED_CELLS_SHA256 = "bfd5b3c83981c8a6ec970b93f460bab7409daf047a2e048bfaa90b5adfd0d4af"
PINNED_LIST_SHA256 = "bd2333d427971fb182add2e3735e1d81fd3fe343640d736eea2b612819854b7e"
PINNED_AH_SHEET_SHA256 = "c2601549b0fc9d97c16ab04b87a61769dcc8783d3b00031c81a9ac23f61f787d"
SHEET_NAME = "second_annotator_sheet_48.csv"
MANIFEST_NAME = "MANIFEST.json"
LIST_NAME = "cell_list_48.txt"
CONTENTS_STATEMENT = (
    "This sheet holds no judge score (J), no label and no AI draft. The label columns "
    "(evidence_span_verbatim, A, rater_L1, note) are empty on every row, the sheet has no "
    "draft column, and no translation is attached. The only judge-derived text is "
    "judge_evidence_span, the span the judge quoted, shown as in the AH pass (PREREG "
    "sec.12.4); it is not a score (PREREG D16 records that an empty span coincides with "
    "J=0 in this run).")


class PacketError(Exception):
    """A refusal: the registered inputs or outputs do not hold."""


# --------------------------------------------------------------------------
# the registered 48-cell list
# --------------------------------------------------------------------------
def read_cell_fields(path: Path) -> list[dict[str, str]]:
    """The three fields sec.12.4 allows (cell_id, cell_kind, category) of every row.
    Everything else on the line (J, A, the judge response, ...) is dropped at once."""
    rows: list[dict[str, str]] = []
    # split on "\n" only: str.splitlines() also breaks at U+2028/U+2029/U+0085, which may
    # sit unescaped inside a JSON string (same rule as analyze_holdout.load_cells)
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").split("\n"), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        if not isinstance(record, dict):
            raise PacketError(f"{path} line {number}: not a JSON object")
        picked: dict[str, str] = {}
        for field in CELLS_FIELDS:
            value = record.get(field)
            if not isinstance(value, str) or not value:
                raise PacketError(f"{path} line {number}: field {field!r} missing or not text")
            picked[field] = value
        rows.append(picked)
    if not rows:
        raise PacketError(f"no cell rows in {path}")
    return rows


def select_second_annotator_cells(rows: list[dict[str, str]], seed: int = SEED,
                                  per_category: int = PER_CATEGORY) -> list[str]:
    """PREREG sec.12.4 procedure; returns the picked ``cell_id``s sorted."""
    ids: dict[str, list[str]] = collections.defaultdict(list)
    seen: set[str] = set()
    for row in rows:
        if row["cell_kind"] != "primary":
            continue
        if row["cell_id"] in seen:
            raise PacketError(f"duplicate primary cell_id {row['cell_id']!r}")
        seen.add(row["cell_id"])
        ids[row["category"]].append(row["cell_id"])
    if not ids:
        raise PacketError("no primary cells")
    for category in sorted(ids):
        if len(ids[category]) < per_category:
            raise PacketError(
                f"category {category!r} has {len(ids[category])} primary cells, "
                f"fewer than the {per_category} to draw")
    rng = random.Random(seed)
    picked: list[str] = []
    for category in sorted(ids):                             # category name order
        picked += rng.sample(sorted(ids[category]), per_category)
    return sorted(picked)


def serialize_cell_list(ids: list[str]) -> bytes:
    return ("\n".join(sorted(ids)) + "\n").encode("utf-8")


# --------------------------------------------------------------------------
# the sheet
# --------------------------------------------------------------------------
def read_sheet(path: Path) -> tuple[list[str], list[list[str]]]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    if not rows:
        raise PacketError(f"{path} is empty")
    header = [c.strip() for c in rows[0]]
    if header != list(la.SHEET_COLUMNS):
        raise PacketError(f"{path}: header is not the 12-column AH sheet header: {header}")
    return header, rows[1:]


def build_packet_rows(source_rows: list[list[str]], ids: list[str],
                      view_names: dict[str, str]) -> list[list[str]]:
    """The AH-sheet rows of ``ids`` (source order), label columns required blank and kept
    blank, ``rendered_view_path`` replaced by the relative view name. Raises when an id is
    absent or repeated in the source sheet or a source row already carries a label."""
    by_id: dict[str, list[list[str]]] = collections.defaultdict(list)
    for row in source_rows:
        if len(row) != len(la.SHEET_COLUMNS):
            raise PacketError(f"sheet row of width {len(row)}; expected {len(la.SHEET_COLUMNS)}")
        by_id[row[0]].append(row)
    out: list[list[str]] = []
    for cell_id in ids:
        found = by_id.get(cell_id, [])
        if len(found) != 1:
            raise PacketError(f"{len(found)} rows for cell_id {cell_id!r} in the source sheet; need 1")
        row = list(found[0])
        if any(c.strip() for c in row[8:]):
            raise PacketError(f"source sheet row for {cell_id!r} already holds label text")
        variant = row[4]
        if variant not in view_names:
            raise PacketError(f"no view for variant {variant!r} (cell {cell_id!r})")
        row[7] = view_names[variant]
        row[8:] = ["", "", "", ""]
        out.append(row)
    return out


def assert_contents_statement_holds(header: list[str], rows: list[list[str]]) -> None:
    """Check what ``CONTENTS_STATEMENT`` claims, on the rows about to be written."""
    if header != list(la.SHEET_COLUMNS):
        raise PacketError("sheet header changed")
    names = {c.lower() for c in header}
    for banned in ("j", "judge_score", "score", "a_draft", "rater_l1_draft", "span_draft",
                   "note_draft", "draft", "cq_ko", "translation"):
        if banned in names:
            raise PacketError(f"sheet carries a {banned!r} column")
    for row in rows:
        if len(row) != len(header):
            raise PacketError("row width differs from the header")
        if any(cell.strip() for cell in row[8:]):
            raise PacketError("a label column is not empty")


def sheet_bytes(header: list[str], rows: list[list[str]]) -> bytes:
    """Default csv dialect (CRLF, QUOTE_MINIMAL): the dialect of the AH sheet."""
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def build_manifest(*, cells_path: Path, cells_sha: str, list_data: bytes, ah_sheet: Path,
                   ah_sheet_sha: str, views_dir: Path, sheet_data: bytes, order_report: dict,
                   ids: list[str], rows: list[list[str]], per_category: int = PER_CATEGORY) -> dict:
    category_counts = collections.Counter(r[3] for r in rows)
    sums = (Path(views_dir) / "SHA256SUMS.txt")
    return {
        "kind": "second_annotator_packet",
        "spec": "PREREG.md sec.12.4 (DN-8, DN-9, DN-10); built by harness/build_second_annotator_packet.py",
        "contents_statement": CONTENTS_STATEMENT,
        "contains": {"judge_score_J": False, "labels": False, "ai_drafts": False,
                     "translation": False, "judge_evidence_span": True},
        "seed": SEED,
        "tool": pc.provenance(Path(__file__), {"label_assist.py": Path(la.__file__)}),
        "files": {
            SHEET_NAME: {"sha256": pc.sha256_bytes(sheet_data), "bytes": len(sheet_data),
                         "rows": len(rows), "columns": list(la.SHEET_COLUMNS)},
            f"../{LIST_NAME}": {"sha256": pc.sha256_bytes(list_data), "bytes": len(list_data),
                                "rows": len(ids)},
        },
        "inputs": {
            "cells_jsonl": {"path": pc.repo_relative(cells_path), "sha256": cells_sha,
                            "fields_read": list(CELLS_FIELDS)},
            "ah_sheet": {"path": pc.repo_relative(ah_sheet), "sha256": ah_sheet_sha},
            "views": {"dir": pc.repo_relative(views_dir),
                      "SHA256SUMS.txt": pc.sha256_file(sums)},
        },
        "selection": {
            "procedure": "primary cells; categories in name order; cell_id sorted inside a "
                         "category; one random.Random(20260913); "
                         f"rng.sample(sorted_ids, {per_category}) per category; list = picked ids "
                         "re-sorted, UTF-8, one per line, trailing LF",
            "per_category": per_category,
            "picked_per_category": dict(sorted(category_counts.items())),
            "list_sha256": pc.sha256_bytes(list_data),
            "registered_list_sha256": PINNED_LIST_SHA256,
        },
        "order": {**order_report,
                  "shuffle_input_order": "cell_id ascending"},
        "rendered_view_path": "rewritten to the file name relative to --views (the AH sheet "
                              "held an absolute path to a deleted worktree); no other column "
                              "differs from the AH-sheet row",
        "serve_with": "label_assist.py --packet --require-note --sheet <this sheet> --views "
                      f"{pc.repo_relative(views_dir)} --out <path outside the repository>",
    }


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------
def build(cells_path: Path, ah_sheet: Path, views_dir: Path, list_out: Path, packet_dir: Path, *,
          expected_cells_sha: str = PINNED_CELLS_SHA256,
          expected_list_sha: str = PINNED_LIST_SHA256,
          expected_sheet_sha: str = PINNED_AH_SHEET_SHA256,
          verify_list: Path | None = None, force: bool = False,
          per_category: int = PER_CATEGORY) -> dict:
    cells_path, ah_sheet, views_dir = Path(cells_path), Path(ah_sheet), Path(views_dir)
    cells_sha = pc.sha256_file(cells_path)
    if cells_sha != expected_cells_sha:
        raise PacketError(f"cells.jsonl sha256 {cells_sha} is not the registered {expected_cells_sha}")
    ah_sha = pc.sha256_file(ah_sheet)
    if ah_sha != expected_sheet_sha:
        raise PacketError(f"AH sheet sha256 {ah_sha} is not the recorded {expected_sheet_sha}")

    ids = select_second_annotator_cells(read_cell_fields(cells_path), SEED, per_category)
    list_data = serialize_cell_list(ids)
    if pc.sha256_bytes(list_data) != expected_list_sha:
        raise PacketError(f"the 48-cell list hashes to {pc.sha256_bytes(list_data)}, "
                          f"not the registered {expected_list_sha}")
    if verify_list is not None:
        separate = Path(verify_list).read_bytes()
        if separate != list_data:
            raise PacketError(f"the list is not byte-equal to the separately computed copy {verify_list}")

    views = la.verify_views(views_dir)                      # all six views, sha256-checked
    view_names = {variant: path.name for variant, path in views.items()}
    header, source_rows = read_sheet(ah_sheet)
    packet_rows = build_packet_rows(source_rows, ids, view_names)
    keyed = [{"cell_id": r[0], "cq_id": r[1], "row": r} for r in sorted(packet_rows, key=lambda r: r[0])]
    order, order_report = pc.constrained_order(keyed, SEED, pc.REGISTERED_MIN_GAP)
    ordered_rows = [item["row"] for item in order]
    assert_contents_statement_holds(header, ordered_rows)
    sheet_data = sheet_bytes(header, ordered_rows)
    manifest = build_manifest(cells_path=cells_path, cells_sha=cells_sha, list_data=list_data,
                              ah_sheet=ah_sheet, ah_sheet_sha=ah_sha, views_dir=views_dir,
                              sheet_data=sheet_data, order_report=order_report, ids=ids,
                              rows=ordered_rows, per_category=per_category)
    manifest_data = pc.canonical_json(manifest)

    list_out, packet_dir = Path(list_out), Path(packet_dir)
    for target in (list_out, packet_dir / SHEET_NAME, packet_dir / MANIFEST_NAME):
        for source in (cells_path, ah_sheet):
            if target.resolve() == source.resolve():
                raise PacketError(f"output {target} is an input")
    sums = (f"{pc.sha256_bytes(sheet_data)}  {SHEET_NAME}\n"
            f"{pc.sha256_bytes(list_data)}  ../{LIST_NAME}\n").encode("utf-8")
    status = {
        "list": pc.write_checked(list_out, list_data, force=force),
        "sheet": pc.write_checked(packet_dir / SHEET_NAME, sheet_data, force=force),
        "manifest": pc.write_checked(packet_dir / MANIFEST_NAME, manifest_data, force=force),
        "sha256sums": pc.write_checked(packet_dir / "SHA256SUMS.txt", sums, force=force),
    }
    return {"n_cells": len(ids), "list_sha256": pc.sha256_bytes(list_data),
            "sheet_sha256": pc.sha256_bytes(sheet_data),
            "manifest_sha256": pc.sha256_bytes(manifest_data),
            "order": order_report, "write_status": status,
            "picked_per_category": manifest["selection"]["picked_per_category"]}


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cells", type=Path, default=REAL_RUN / "cells.jsonl")
    ap.add_argument("--ah-sheet", type=Path,
                    default=REAL_RUN / "annotation_pending" / "primary_pass_224_ready_to_fill.csv")
    ap.add_argument("--views", type=Path, default=REAL_RUN / "annotation_pending" / "views")
    ap.add_argument("--list-out", type=Path, default=REAL_RUN / "second_annotator" / LIST_NAME)
    ap.add_argument("--packet-dir", type=Path, default=REAL_RUN / "second_annotator" / "packet")
    ap.add_argument("--verify-list", type=Path, default=None,
                    help="separately computed list; the built list must be byte-equal to it")
    ap.add_argument("--expected-cells-sha256", default=PINNED_CELLS_SHA256,
                    help="registered sha256 of cells.jsonl (override only for a synthetic fixture)")
    ap.add_argument("--expected-list-sha256", default=PINNED_LIST_SHA256,
                    help="registered sha256 of the 48-cell list (override only for a fixture)")
    ap.add_argument("--expected-sheet-sha256", default=PINNED_AH_SHEET_SHA256,
                    help="recorded sha256 of the AH blank sheet (override only for a fixture)")
    ap.add_argument("--per-category", type=int, default=PER_CATEGORY,
                    help="cells drawn per category. The registered list is 8 per category; the pinned "
                         "list hash refuses any other value on the real cells.jsonl (fixtures only)")
    ap.add_argument("--force", action="store_true", help="overwrite differing existing outputs")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = build(args.cells, args.ah_sheet, args.views, args.list_out, args.packet_dir,
                       expected_cells_sha=args.expected_cells_sha256,
                       expected_list_sha=args.expected_list_sha256,
                       expected_sheet_sha=args.expected_sheet_sha256,
                       verify_list=args.verify_list, force=args.force,
                       per_category=args.per_category)
    except (PacketError, la.SafetyError, FileExistsError, OSError, ValueError) as exc:
        print(f"[build_second_annotator_packet] refused: {exc}", file=sys.stderr)
        return 1
    order = result["order"]
    print(f"cells={result['n_cells']} list_sha256={result['list_sha256']}")
    print(f"sheet_sha256={result['sheet_sha256']} manifest_sha256={result['manifest_sha256']}")
    print(f"order: target_min_gap={order['target_min_gap']} achieved_min_gap={order['achieved_min_gap']} "
          f"target_met={order['target_met']} largest_same_cq_group={order['largest_same_cq_group']}")
    print("written: " + ", ".join(f"{k}={v}" for k, v in result["write_status"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
