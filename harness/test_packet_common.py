"""Tests for the helpers shared by the sec.12 packet builders. Synthetic data only."""
from __future__ import annotations

import collections
import io
import json
import os
import stat
import sys
from contextlib import redirect_stderr
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import packet_common as pc  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]


def mode_of(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def rows_for(sizes: list[int]) -> list[dict]:
    """One row per (group, member); input order = ascending row id (what the builders pass)."""
    rows = []
    for g, n in enumerate(sizes):
        for m in range(n):
            rows.append({"row": f"g{g:02d}-m{m}", "cq_id": f"CQ{g:02d}"})
    return sorted(rows, key=lambda r: r["row"])


# --- length bound ----------------------------------------------------------------
def test_gap_feasible_bound() -> None:
    assert pc.gap_feasible([], 20)
    assert pc.gap_feasible([1] * 30, 20)                       # nothing repeats
    assert pc.gap_feasible([2] * 10, 10)                       # a?b..a: (2-1)*10 + 10 = 20 <= 20
    assert not pc.gap_feasible([2] * 10, 11)
    assert pc.gap_feasible([4, 4] + [2] * 20, 15)              # (4-1)*15 + 2 = 47 <= 48
    assert not pc.gap_feasible([4, 4] + [2] * 20, 16)          # 3*16 + 2 = 50 > 48
    assert not pc.gap_feasible([4, 4] + [2] * 20, 20)


def test_min_same_key_gap() -> None:
    order = [{"cq_id": c} for c in "abcab"]
    assert pc.min_same_key_gap(order) == 3
    assert pc.min_same_key_gap([{"cq_id": c} for c in "abc"]) is None
    assert pc.min_same_key_gap([{"cq_id": c} for c in "aab"]) == 1


# --- the registered constrained shuffle --------------------------------------------
def test_constrained_order_meets_20_when_feasible() -> None:
    rows = rows_for([3] * 10 + [2] * 15 + [1] * 10)             # 70 rows, largest group 3: 2*20+10 <= 70
    order, report = pc.constrained_order(rows, 20260913, 20)
    assert sorted(r["row"] for r in order) == sorted(r["row"] for r in rows)   # a permutation
    assert pc.min_same_key_gap(order) >= 20
    assert report["target_met"] is True and report["applied_min_gap"] == 20
    assert report["achieved_min_gap"] >= 20 and report["target_feasible_by_length_bound"] is True
    assert report["seed"] == 20260913 and report["n_rows"] == 70
    assert report["shuffle_module_sha256"] == pc.sha256_file(pc.SHUFFLE_SOURCE)


def test_constrained_order_reports_the_best_gap_when_20_is_infeasible() -> None:
    sizes = [4, 4] + [2] * 20            # the shape of the 48-cell second-annotator list
    rows = rows_for(sizes)
    assert len(rows) == 48
    order, report = pc.constrained_order(rows, 20260913, 20)
    assert report["target_met"] is False and report["target_feasible_by_length_bound"] is False
    assert report["achieved_min_gap"] == 15 == report["applied_min_gap"]       # the optimum: 3*15 + 2 <= 48
    assert not pc.gap_feasible(collections.Counter(r["cq_id"] for r in rows).values(), 16)
    assert report["largest_same_cq_group"] == 4
    # the registered function alone, asked for 20, falls back to a much worse arrangement
    module = pc.registered_shuffle_module()
    with redirect_stderr(io.StringIO()):
        direct = module._constrained_shuffle(list(rows), 20260913, min_gap=20)
    assert pc.min_same_key_gap(direct) < 15


def test_constrained_order_is_deterministic_and_seed_dependent() -> None:
    rows = rows_for([3] * 10 + [2] * 15)
    a, _ = pc.constrained_order(rows, 20260913)
    b, _ = pc.constrained_order(rows, 20260913)
    c, _ = pc.constrained_order(rows, 20260914)
    assert [r["row"] for r in a] == [r["row"] for r in b]
    assert [r["row"] for r in a] != [r["row"] for r in c]


def test_constrained_order_without_repeats_is_a_plain_seeded_shuffle() -> None:
    rows = rows_for([1] * 25)
    order, report = pc.constrained_order(rows, 20260913)
    assert report["achieved_min_gap"] is None and report["target_met"] is True
    assert report["same_cq_repeats"] is False
    assert sorted(r["row"] for r in order) == sorted(r["row"] for r in rows)


def test_constrained_order_rejects_another_group_key() -> None:
    with pytest.raises(ValueError):
        pc.constrained_order(rows_for([2]), key="row")


def test_constrained_order_reports_the_best_gap_the_length_bound_allows() -> None:
    _, report = pc.constrained_order(rows_for([4, 4] + [2] * 20), 20260913, 20)
    assert report["best_gap_by_length_bound"] == 15 == report["achieved_min_gap"]
    _, report = pc.constrained_order(rows_for([3] * 10 + [2] * 15 + [1] * 10), 20260913, 20)
    assert report["best_gap_by_length_bound"] == 20 and report["achieved_min_gap"] >= 20
    _, report = pc.constrained_order(rows_for([1] * 25))
    assert report["best_gap_by_length_bound"] == 20               # nothing repeats: the target itself


def test_constrained_order_stops_when_the_shuffle_misses_a_gap_the_length_bound_allows(
        monkeypatch: pytest.MonkeyPatch) -> None:
    rows = rows_for([3] * 10 + [2] * 15 + [1] * 10)               # a 20-position separation is feasible here
    module = pc.registered_shuffle_module()
    monkeypatch.setattr(module, "_constrained_shuffle",
                        lambda rows, seed, min_gap=20: list(rows))   # same-CQ rows left side by side
    with pytest.raises(RuntimeError, match="feasible"):
        pc.constrained_order(rows, 20260913, 20)


# --- bytes helpers -----------------------------------------------------------------
def test_canonical_json_is_deterministic_and_sorted() -> None:
    a = pc.canonical_json({"b": 1, "a": {"y": [1, 2], "x": "한글"}})
    b = pc.canonical_json({"a": {"x": "한글", "y": [1, 2]}, "b": 1})
    assert a == b and a.endswith(b"\n") and "한글" in a.decode("utf-8")
    assert list(json.loads(a)) == ["a", "b"]


def test_write_checked_creates_keeps_and_refuses(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "f.bin"
    assert pc.write_checked(target, b"one") == "created"
    assert pc.write_checked(target, b"one") == "unchanged"
    with pytest.raises(FileExistsError):
        pc.write_checked(target, b"two")
    assert target.read_bytes() == b"one"
    assert pc.write_checked(target, b"two", force=True) == "overwritten"
    assert target.read_bytes() == b"two"
    assert not list(target.parent.glob("*.tmp*"))     # the atomic temp file is gone


def test_sha256_helpers_agree(tmp_path: Path) -> None:
    f = tmp_path / "x.bin"
    data = b"abc" * 1_000_000                          # larger than the read block
    f.write_bytes(data)
    assert pc.sha256_file(f) == pc.sha256_bytes(data)


def test_provenance_has_hashes_and_versions_but_no_path_or_time(tmp_path: Path) -> None:
    script = tmp_path / "tool.py"
    script.write_text("print(1)\n", encoding="utf-8")
    other = tmp_path / "other.py"
    other.write_text("x = 1\n", encoding="utf-8")
    p = pc.provenance(script, {"other.py": other})
    assert p["script"] == "tool.py" and p["script_sha256"] == pc.sha256_file(script)
    assert p["packet_common_sha256"] == pc.sha256_file(Path(pc.__file__))
    assert p["imported_sources_sha256"] == {"other.py": pc.sha256_file(other)}
    assert p["python"].count(".") == 2 and p["numpy"] != "" and p["scipy"] != ""
    assert str(tmp_path) not in json.dumps(p)           # no absolute path in a manifest
    assert pc.provenance(script) == {k: v for k, v in p.items() if k != "imported_sources_sha256"}


def test_repo_relative_never_leaks_a_foreign_absolute_path(tmp_path: Path) -> None:
    inside = pc.HERE / "real_run" / "cells.jsonl"
    assert pc.repo_relative(inside) == "paper/access2026/harness/real_run/cells.jsonl"
    assert pc.repo_relative(tmp_path / "somewhere" / "x.csv") == "x.csv"


# --- durable and private writes -------------------------------------------------------
def test_write_checked_mode_is_exact_and_an_unchanged_file_is_tightened(tmp_path: Path) -> None:
    target = tmp_path / "private" / "f.bin"
    old = os.umask(0o022)
    try:
        assert pc.write_checked(target, b"one", mode=0o600) == "created"
        assert mode_of(target) == 0o600
        os.chmod(target, 0o644)
        assert pc.write_checked(target, b"one", mode=0o600) == "unchanged" and mode_of(target) == 0o600
        assert pc.write_checked(target, b"two", force=True, mode=0o640) == "overwritten"
        assert mode_of(target) == 0o640
        plain = tmp_path / "plain.bin"                              # no mode asked for: the process default
        pc.write_checked(plain, b"x")
        assert mode_of(plain) == 0o644
    finally:
        os.umask(old)


@pytest.mark.skipif(not Path("/proc/self/fd").exists(), reason="needs /proc to name the synced file")
def test_atomic_write_fsyncs_the_temp_file_before_the_rename_and_the_directory_after(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, str]] = []
    real_fsync, real_replace = os.fsync, os.replace

    def spy_fsync(fd: int) -> None:
        try:
            events.append(("fsync", Path(os.readlink(f"/proc/self/fd/{fd}")).name))
        except OSError:
            events.append(("fsync", "?"))
        real_fsync(fd)

    def spy_replace(src, dst) -> None:
        events.append(("replace", Path(dst).name))
        real_replace(src, dst)

    monkeypatch.setattr(os, "fsync", spy_fsync)
    monkeypatch.setattr(os, "replace", spy_replace)
    pc.write_bytes_atomic(tmp_path / "out" / "f.bin", b"data", mode=0o600)
    temp = next(i for i, e in enumerate(events) if e[0] == "fsync" and ".tmp" in e[1])
    rename = next(i for i, e in enumerate(events) if e == ("replace", "f.bin"))
    folder = next(i for i, e in enumerate(events) if e == ("fsync", "out"))
    assert temp < rename < folder
    assert mode_of(tmp_path / "out" / "f.bin") == 0o600


def test_a_failed_atomic_write_keeps_the_old_file_and_leaves_no_temp_file(tmp_path: Path,
                                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "f.bin"
    target.write_bytes(b"old")
    monkeypatch.setattr(os, "replace", lambda src, dst: (_ for _ in ()).throw(OSError("rename failed")))
    with pytest.raises(OSError):
        pc.write_bytes_atomic(target, b"new", mode=0o600)
    monkeypatch.undo()
    assert target.read_bytes() == b"old" and [p.name for p in tmp_path.iterdir()] == ["f.bin"]


def test_ensure_private_dir_sets_the_mode_exactly_even_on_an_existing_looser_directory(tmp_path: Path) -> None:
    made = pc.ensure_private_dir(tmp_path / "a" / "b")
    assert made == tmp_path / "a" / "b" and mode_of(made) == 0o700
    os.chmod(made, 0o755)
    pc.ensure_private_dir(made)
    assert mode_of(made) == 0o700
    assert mode_of(pc.ensure_private_dir(tmp_path / "c", mode=0o750)) == 0o750


def test_fsync_dir_is_best_effort(tmp_path: Path) -> None:
    pc.fsync_dir(tmp_path)
    pc.fsync_dir(tmp_path / "does_not_exist")                     # a missing directory is not an error
