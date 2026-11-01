"""Tests for build_second_annotator_packet (PREREG sec.12.4).

The pinned-hash behaviour is exercised on SYNTHETIC fixtures by overriding the pins; the one
test that touches the committed real artifacts only reads the three allowed cells.jsonl fields
and compares hashes (it is skipped when the artifacts are not present).
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_second_annotator_packet as sap  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
import label_assist as la  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
import packet_common as pc  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]

HEADER = list(la.SHEET_COLUMNS)
CATEGORIES = {"cat_a": 9, "cat_b": 10, "cat_c": 12}      # primary cells per category
PER = 4                                                  # cells drawn per category in the fixtures


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def make_views(root: Path) -> Path:
    views = root / "views"
    views.mkdir(parents=True, exist_ok=True)
    lines = []
    for v in "ABCDEF":
        name = f"rendered_view_{v}.txt"
        (views / name).write_bytes(f"VIEW {v}\nbrick:Zone anchor {v}\n".encode("utf-8"))
        lines.append(f"{sha((views / name).read_bytes())}  {name}")
    (views / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return views


def make_world(root: Path, filled_label: bool = False) -> dict[str, Path]:
    """cells.jsonl (primary + controls, with judge fields that must never be read) and the
    matching AH blank sheet."""
    root.mkdir(parents=True, exist_ok=True)
    cells, sheet_rows = [], [HEADER]
    n = 0
    for category, count in CATEGORIES.items():
        for _ in range(count):
            n += 1
            variant = "ABCDEF"[n % 6]
            cq = f"CQB{(n * 7) % 31 + 1:02d}"          # CQs repeat across variants: same-CQ groups
            cell_id = f"primary:{variant}:{cq}:{n}"
            cells.append({"cell_id": cell_id, "cell_kind": "primary", "category": category,
                          "J": 3, "A": 1, "variant": variant, "cq_id": cq,
                          "judge_response": {"score": 3, "evidence": f"quoted span {n}"}})
            sheet_rows.append([cell_id, cq, cq, category, variant, f"What is thing {n}?",
                               f"quoted span {n}", "/abs/stale/rendered_view.txt",
                               "stray label" if (filled_label and n == 5) else "", "", "", ""])
    for kind in ("ablated_control", "preserved_control"):
        for i in range(3):
            cell_id = f"{kind}:{'ABC'[i]}:CQB0{i + 1}"
            cells.append({"cell_id": cell_id, "cell_kind": kind, "category": "cat_a", "J": 0})
            sheet_rows.append([cell_id, f"CQB0{i + 1}", f"CQB0{i + 1}", "cat_a", "ABC"[i],
                               "control text", "", "/abs/stale/rendered_view.txt", "", "", "", ""])
    cells_path = root / "cells.jsonl"
    cells_path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cells),
                          encoding="utf-8")
    sheet = root / "ah_sheet.csv"
    with open(sheet, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(sheet_rows)
    return {"cells": cells_path, "sheet": sheet, "views": make_views(root)}


def registered_recipe(cells_path: Path, per: int) -> bytes:
    """The sec.12.4 recipe, written out independently of the builder."""
    ids: dict[str, list[str]] = collections.defaultdict(list)
    for line in cells_path.read_text(encoding="utf-8").split("\n"):
        if line.strip():
            rec = json.loads(line)
            if rec["cell_kind"] == "primary":
                ids[rec["category"]].append(rec["cell_id"])
    rng = random.Random(20260913)
    picked: list[str] = []
    for cat in sorted(ids):
        picked += rng.sample(sorted(ids[cat]), per)
    return ("\n".join(sorted(picked)) + "\n").encode("utf-8")


def run_build(world: dict[str, Path], out: Path, **kw):
    list_data = registered_recipe(world["cells"], PER)
    return sap.build(world["cells"], world["sheet"], world["views"], out / "cell_list_48.txt",
                     out / "packet", expected_cells_sha=sha(world["cells"].read_bytes()),
                     expected_list_sha=kw.pop("expected_list_sha", sha(list_data)),
                     expected_sheet_sha=sha(world["sheet"].read_bytes()), per_category=PER, **kw)


# --------------------------------------------------------------------------
def test_pins_are_the_registered_values() -> None:
    assert sap.PINNED_LIST_SHA256 == "bd2333d427971fb182add2e3735e1d81fd3fe343640d736eea2b612819854b7e"
    assert sap.PINNED_CELLS_SHA256 == "bfd5b3c83981c8a6ec970b93f460bab7409daf047a2e048bfaa90b5adfd0d4af"
    assert sap.SEED == 20260913 and sap.PER_CATEGORY == 8 and sap.CELLS_FIELDS == (
        "cell_id", "cell_kind", "category")


def test_selection_follows_the_registered_recipe(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    ids = sap.select_second_annotator_cells(sap.read_cell_fields(world["cells"]), 20260913, PER)
    data = sap.serialize_cell_list(ids)
    assert data == registered_recipe(world["cells"], PER)
    assert len(ids) == PER * len(CATEGORIES) and ids == sorted(ids)
    assert data.endswith(b"\n") and data.count(b"\n") == len(ids)
    assert not any(i.startswith(("ablated", "preserved")) for i in ids)       # controls are not drawn
    per_cat = collections.Counter(c.split(":")[0] for c in ids)
    assert per_cat == {"primary": len(ids)}
    # a different seed gives a different list: the seed is not decorative
    other = sap.select_second_annotator_cells(sap.read_cell_fields(world["cells"]), 20260914, PER)
    assert other != ids


def test_only_the_three_allowed_fields_are_read(tmp_path: Path) -> None:
    path = tmp_path / "cells.jsonl"
    lines = [json.dumps({"cell_id": "primary:A:CQB01", "cell_kind": "primary", "category": "c"}),
             json.dumps({"cell_id": "primary:A:CQB02", "cell_kind": "primary", "category": "c",
                         "J": "not-an-int", "A": None, "judge_response": 12345, "x": ["y"]})]
    path.write_text("\n".join(lines) + "\n\n", encoding="utf-8")
    rows = sap.read_cell_fields(path)
    assert all(set(r) == {"cell_id", "cell_kind", "category"} for r in rows)
    assert [r["cell_id"] for r in rows] == ["primary:A:CQB01", "primary:A:CQB02"]
    path.write_text(json.dumps({"cell_id": "x", "cell_kind": "primary"}) + "\n", encoding="utf-8")
    with pytest.raises(sap.PacketError, match="category"):
        sap.read_cell_fields(path)
    path.write_text(json.dumps({"cell_id": "x", "cell_kind": "primary", "category": 3}) + "\n",
                    encoding="utf-8")
    with pytest.raises(sap.PacketError):
        sap.read_cell_fields(path)
    path.write_text("[1, 2]\n", encoding="utf-8")
    with pytest.raises(sap.PacketError):
        sap.read_cell_fields(path)
    path.write_text("\n\n", encoding="utf-8")
    with pytest.raises(sap.PacketError, match="no cell rows"):
        sap.read_cell_fields(path)


def test_a_line_separator_inside_a_json_string_does_not_split_the_record(tmp_path: Path) -> None:
    path = tmp_path / "cells.jsonl"
    record = {"cell_id": "primary:A:CQB01", "cell_kind": "primary", "category": "c",
              "note": "a" + chr(0x2028) + "b"}
    path.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    assert len(sap.read_cell_fields(path)) == 1


def test_selection_refuses_a_small_category_and_duplicates() -> None:
    rows = [{"cell_id": f"primary:A:{i}", "cell_kind": "primary", "category": "c"} for i in range(3)]
    with pytest.raises(sap.PacketError, match="fewer than"):
        sap.select_second_annotator_cells(rows, 20260913, 4)
    with pytest.raises(sap.PacketError, match="duplicate"):
        sap.select_second_annotator_cells(rows + rows[:1], 20260913, 2)
    with pytest.raises(sap.PacketError, match="no primary"):
        sap.select_second_annotator_cells([{"cell_id": "a", "cell_kind": "ablated_control",
                                            "category": "c"}], 20260913, 1)


def test_build_writes_the_list_the_sheet_and_the_manifest(tmp_path: Path) -> None:
    world = make_world(tmp_path / "in")
    out = tmp_path / "out"
    result = run_build(world, out)
    list_data = (out / "cell_list_48.txt").read_bytes()
    assert list_data == registered_recipe(world["cells"], PER)
    assert result["list_sha256"] == sha(list_data) and result["n_cells"] == PER * 3
    rows = list(csv.reader(open(out / "packet" / sap.SHEET_NAME, newline="", encoding="utf-8")))
    assert rows[0] == HEADER and len(rows) - 1 == PER * 3
    assert sorted(r[0] for r in rows[1:]) == list_data.decode("utf-8").split()      # exactly the list
    assert all(not any(c.strip() for c in r[8:]) for r in rows[1:])                  # labels empty
    source = {r[0]: r for r in list(csv.reader(open(world["sheet"], newline="", encoding="utf-8")))[1:]}
    for r in rows[1:]:
        assert r[:7] == source[r[0]][:7]                                              # AH columns as they were
        assert r[7] == f"rendered_view_{r[4]}.txt"                                    # relative view name
    # the sheet round-trips through label_assist's packet loader (view names sha256-checked)
    views = la.verify_packet_views(world["views"], la.sheet_view_refs(out / "packet" / sap.SHEET_NAME))
    assert set(views) <= {f"rendered_view_{v}.txt" for v in "ABCDEF"}
    # same-CQ spacing is the best the registered shuffle reaches, and it is what the manifest says
    pos: dict[str, list[int]] = collections.defaultdict(list)
    for i, r in enumerate(rows[1:]):
        pos[r[1]].append(i)
    gaps = [b - a for v in pos.values() for a, b in zip(v, v[1:])]
    manifest = json.loads((out / "packet" / sap.MANIFEST_NAME).read_text(encoding="utf-8"))
    assert manifest["order"]["achieved_min_gap"] == (min(gaps) if gaps else None)
    assert result["order"]["achieved_min_gap"] == manifest["order"]["achieved_min_gap"]


def test_manifest_states_no_J_no_labels_no_drafts_and_carries_the_hashes(tmp_path: Path) -> None:
    world = make_world(tmp_path / "in")
    out = tmp_path / "out"
    run_build(world, out)
    manifest_bytes = (out / "packet" / sap.MANIFEST_NAME).read_bytes()
    manifest = json.loads(manifest_bytes)
    text = manifest["contents_statement"]
    assert "no judge score (J)" in text and "no label" in text and "no AI draft" in text
    assert manifest["contains"] == {"judge_score_J": False, "labels": False, "ai_drafts": False,
                                    "translation": False, "judge_evidence_span": True}
    sheet_bytes = (out / "packet" / sap.SHEET_NAME).read_bytes()
    assert manifest["files"][sap.SHEET_NAME]["sha256"] == sha(sheet_bytes)
    assert manifest["files"][sap.SHEET_NAME]["rows"] == PER * 3
    assert manifest["files"][f"../{sap.LIST_NAME}"]["sha256"] == sha((out / sap.LIST_NAME).read_bytes())
    assert manifest["inputs"]["cells_jsonl"]["sha256"] == sha(world["cells"].read_bytes())
    assert manifest["inputs"]["cells_jsonl"]["fields_read"] == ["cell_id", "cell_kind", "category"]
    assert manifest["inputs"]["ah_sheet"]["sha256"] == sha(world["sheet"].read_bytes())
    assert manifest["inputs"]["views"]["SHA256SUMS.txt"] == sha((world["views"] / "SHA256SUMS.txt").read_bytes())
    tool = manifest["tool"]
    assert tool["script"] == "build_second_annotator_packet.py"
    assert tool["script_sha256"] == pc.sha256_file(Path(sap.__file__))
    assert tool["python"] and tool["numpy"] and tool["scipy"]
    assert manifest["selection"]["list_sha256"] == manifest["files"][f"../{sap.LIST_NAME}"]["sha256"]
    assert manifest["selection"]["picked_per_category"] == {c: PER for c in CATEGORIES}
    assert str(tmp_path) not in manifest_bytes.decode("utf-8")                       # no absolute paths
    sums = (out / "packet" / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    assert sums == [f"{sha(sheet_bytes)}  {sap.SHEET_NAME}",
                    f"{sha((out / sap.LIST_NAME).read_bytes())}  ../{sap.LIST_NAME}"]
    for word in ("verified", "reference"):                                           # wording rule
        assert word not in manifest_bytes.decode("utf-8").lower()


def test_the_serve_command_carries_require_note_in_the_docstring_and_the_manifest(tmp_path: Path) -> None:
    """The second annotator fills all four columns (DN-9): the documented serve command and the one in the
    manifest both pass --require-note to label_assist --packet (PREREG sec.13.1 item 8)."""
    world = make_world(tmp_path / "in")
    run_build(world, tmp_path / "out")
    manifest = json.loads((tmp_path / "out" / "packet" / sap.MANIFEST_NAME).read_text(encoding="utf-8"))
    serve = manifest["serve_with"]
    assert serve.startswith("label_assist.py --packet --require-note --sheet ") and "--views" in serve
    flat = " ".join(sap.__doc__.split())
    assert "label_assist.py --packet --require-note --sheet <packet>/second_annotator_sheet_48.csv" in flat
    # the flag the manifest names exists on the server's command line and is accepted with --packet
    args = la.build_parser().parse_args(["--packet", "--require-note", "--sheet", "s.csv", "--views", "v"])
    assert args.packet is True and args.require_note is True


def test_two_builds_give_identical_bytes(tmp_path: Path) -> None:
    world = make_world(tmp_path / "in")
    run_build(world, tmp_path / "one")
    run_build(world, tmp_path / "two")
    for rel in ("cell_list_48.txt", f"packet/{sap.SHEET_NAME}", f"packet/{sap.MANIFEST_NAME}",
                "packet/SHA256SUMS.txt"):
        assert (tmp_path / "one" / rel).read_bytes() == (tmp_path / "two" / rel).read_bytes(), rel
    again = run_build(world, tmp_path / "one")           # a rerun over its own output changes nothing
    assert set(again["write_status"].values()) == {"unchanged"}


def test_pins_refuse_a_wrong_cells_file_list_or_sheet(tmp_path: Path) -> None:
    world = make_world(tmp_path / "in")
    out = tmp_path / "out"
    with pytest.raises(sap.PacketError, match="cells.jsonl sha256"):
        sap.build(world["cells"], world["sheet"], world["views"], out / "l.txt", out / "p",
                  per_category=PER)                      # the real pins on a fixture
    with pytest.raises(sap.PacketError, match="48-cell list hashes to"):
        run_build(world, out, expected_list_sha="0" * 64)
    with pytest.raises(sap.PacketError, match="AH sheet sha256"):
        sap.build(world["cells"], world["sheet"], world["views"], out / "l.txt", out / "p",
                  expected_cells_sha=sha(world["cells"].read_bytes()), per_category=PER)
    assert not (out / "l.txt").exists() and not (out / "p").exists()                 # nothing written


def test_independent_copy_must_be_byte_equal(tmp_path: Path) -> None:
    world = make_world(tmp_path / "in")
    good = tmp_path / "independent.txt"
    good.write_bytes(registered_recipe(world["cells"], PER))
    run_build(world, tmp_path / "ok", verify_list=good)
    bad = tmp_path / "independent_bad.txt"
    bad.write_bytes(good.read_bytes().replace(b"\n", b"\r\n"))
    with pytest.raises(sap.PacketError, match="byte-equal"):
        run_build(world, tmp_path / "bad", verify_list=bad)
    assert not (tmp_path / "bad" / "cell_list_48.txt").exists()


def test_a_source_sheet_with_a_label_is_refused(tmp_path: Path) -> None:
    world = make_world(tmp_path / "in", filled_label=True)
    ids = registered_recipe(world["cells"], PER).decode("utf-8").split()
    # the stray label sits on one specific cell; make sure it is among the drawn ones
    labeled = [r[0] for r in list(csv.reader(open(world["sheet"], newline="", encoding="utf-8")))[1:] if r[8]]
    if labeled[0] not in ids:
        pytest.skip("fixture draw does not include the labeled cell")
    with pytest.raises(sap.PacketError, match="label text"):
        run_build(world, tmp_path / "out")


def test_missing_or_repeated_source_rows_and_unknown_variant_are_refused(tmp_path: Path) -> None:
    header, rows = sap.read_sheet(make_world(tmp_path / "in")["sheet"])
    names = {v: f"rendered_view_{v}.txt" for v in "ABCDEF"}
    with pytest.raises(sap.PacketError, match="0 rows"):
        sap.build_packet_rows(rows, ["primary:Z:CQB99"], names)
    with pytest.raises(sap.PacketError, match="2 rows"):
        sap.build_packet_rows(rows + rows[:1], [rows[0][0]], names)
    bad = [list(rows[0])]
    bad[0][4] = "Z"
    with pytest.raises(sap.PacketError, match="no view for variant"):
        sap.build_packet_rows(bad, [bad[0][0]], names)
    with pytest.raises(sap.PacketError, match="width"):
        sap.build_packet_rows([["x"]], ["x"], names)


def test_a_header_that_is_not_the_ah_sheet_header_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "s.csv"
    path.write_text("cell_id,cq_text\nx,y\n", encoding="utf-8")
    with pytest.raises(sap.PacketError, match="12-column"):
        sap.read_sheet(path)
    blank = [""] * 12
    sap.assert_contents_statement_holds(HEADER, [blank])                 # the honest case passes
    with pytest.raises(sap.PacketError, match="header changed"):
        sap.assert_contents_statement_holds(HEADER[:-1], [])
    with pytest.raises(sap.PacketError, match="header changed"):
        sap.assert_contents_statement_holds(HEADER + ["A_draft"], [])   # a draft column is refused
    for column in (8, 9, 10, 11):                                       # any non-empty label cell
        row = list(blank)
        row[column] = "x"
        with pytest.raises(sap.PacketError, match="label column"):
            sap.assert_contents_statement_holds(HEADER, [row])
    with pytest.raises(sap.PacketError, match="width"):
        sap.assert_contents_statement_holds(HEADER, [["x"]])


def test_existing_different_output_is_not_overwritten_without_force(tmp_path: Path) -> None:
    world = make_world(tmp_path / "in")
    out = tmp_path / "out"
    run_build(world, out)
    (out / "packet" / sap.SHEET_NAME).write_bytes(b"tampered")
    with pytest.raises(FileExistsError):
        run_build(world, out)
    result = run_build(world, out, force=True)
    assert result["write_status"]["sheet"] == "overwritten"


def cli_argv(world: dict[str, Path], out: Path, per: int | None = PER) -> list[str]:
    argv = ["--cells", str(world["cells"]), "--ah-sheet", str(world["sheet"]),
            "--views", str(world["views"]), "--list-out", str(out / "l.txt"),
            "--packet-dir", str(out / "p"),
            "--expected-cells-sha256", sha(world["cells"].read_bytes()),
            "--expected-list-sha256", sha(registered_recipe(world["cells"], PER)),
            "--expected-sheet-sha256", sha(world["sheet"].read_bytes())]
    return argv + (["--per-category", str(per)] if per is not None else [])


def test_cli_refuses_with_the_real_pins_and_with_the_registered_size(
        tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    world = make_world(tmp_path / "in")
    out = tmp_path / "out"
    assert sap.main(["--cells", str(world["cells"]), "--list-out", str(out / "l.txt"),
                     "--packet-dir", str(out / "p")]) == 1           # the real pins on a fixture
    assert "refused" in capsys.readouterr().err
    assert sap.main(cli_argv(world, out, per=None)) == 1             # 8 per category is not the fixture's list
    assert "hashes to" in capsys.readouterr().err                    # the pinned list hash catches it
    assert not (out / "l.txt").exists()


def test_cli_success_prints_counts_and_hashes_only(tmp_path: Path,
                                                   capsys: pytest.CaptureFixture[str]) -> None:
    world = make_world(tmp_path / "in")
    out = tmp_path / "out"
    assert sap.main(cli_argv(world, out)) == 0
    shown = capsys.readouterr().out
    assert f"cells={PER * 3}" in shown and sha(registered_recipe(world["cells"], PER)) in shown
    assert "achieved_min_gap=" in shown and "target_min_gap=20" in shown
    assert "primary:" not in shown and "cat_" not in shown            # no cell id or category on stdout
    assert sap.main(cli_argv(world, out)) == 0                        # an identical rerun is fine
    assert "unchanged" in capsys.readouterr().out


# --------------------------------------------------------------------------
# the committed real artifacts (skipped when absent): only hashes and the three fields are used
# --------------------------------------------------------------------------
REAL = sap.REAL_RUN / "second_annotator"


@pytest.mark.skipif(not (REAL / sap.LIST_NAME).exists(), reason="second-annotator artifacts not built")
def test_committed_artifacts_match_the_registered_hashes() -> None:
    data = (REAL / sap.LIST_NAME).read_bytes()
    assert sha(data) == sap.PINNED_LIST_SHA256 and len(data) == 768 and data.count(b"\n") == 48
    cells = sap.REAL_RUN / "cells.jsonl"
    assert sha(cells.read_bytes()) == sap.PINNED_CELLS_SHA256
    assert sap.serialize_cell_list(sap.select_second_annotator_cells(sap.read_cell_fields(cells))) == data
    packet = REAL / "packet"
    manifest = json.loads((packet / sap.MANIFEST_NAME).read_text(encoding="utf-8"))
    sheet = (packet / sap.SHEET_NAME).read_bytes()
    assert manifest["files"][sap.SHEET_NAME]["sha256"] == sha(sheet)
    assert manifest["files"][f"../{sap.LIST_NAME}"]["sha256"] == sha(data)
    assert manifest["contains"]["judge_score_J"] is False and manifest["contains"]["labels"] is False
    assert manifest["contains"]["ai_drafts"] is False
    assert "--packet --require-note" in manifest["serve_with"]      # DN-9: the second annotator fills all four columns
    rows = list(csv.reader(open(packet / sap.SHEET_NAME, newline="", encoding="utf-8")))
    assert rows[0] == HEADER and sorted(r[0] for r in rows[1:]) == data.decode("utf-8").split()
    assert all(not any(c.strip() for c in r[8:]) for r in rows[1:])
    assert all(r[7] == f"rendered_view_{r[4]}.txt" for r in rows[1:])
