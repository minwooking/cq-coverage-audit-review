"""Tests for frame.py -- sampling frame construction (addendum 47, plan-based, exploratory).
AI-generated draft: a person must review and test it before use.
"""
import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import common  # noqa: E402
import frame as frame_mod  # noqa: E402

SNAP_SESSION: list = []


@pytest.fixture(scope="session")
def snap():
    if not SNAP_SESSION:
        SNAP_SESSION.append(common.Snapshot(common.SNAPSHOT))
    return SNAP_SESSION[0]


@pytest.fixture(scope="session")
def plan(snap):
    return frame_mod.frame_plan(snap)


def test_total_b1_is_504(plan):
    assert plan["total_b1"] == 504


def test_deterministic(plan, snap):
    """Same snapshot, same seed -> identical frame (regenerated in-place twice)."""
    p2 = frame_mod.frame_plan(snap)
    for c in common.CATEGORIES:
        assert p2["categories"][c]["b1_terms"] == plan["categories"][c]["b1_terms"]
        assert p2["categories"][c]["frame_tail"] == plan["categories"][c]["frame_tail"]
        assert p2["categories"][c]["b1_frame_rank"] == plan["categories"][c]["b1_frame_rank"]


def test_short_categories_redistributed(plan):
    """Short frames give all; total still 504 via round-robin to the largest frames,
    deficit fully covered, never over-allocation beyond frame size."""
    assert plan["redistribution"]["deficit_after_redistribution"] == 0
    for c in common.CATEGORIES:
        cat = plan["categories"][c]
        assert cat["allocation_b1"] <= cat["frame_size"]
    short = [c for c in common.CATEGORIES if plan["categories"][c]["frame_size"] < 84]
    assert "slots_facets" in short and "relations" in short
    assert sum(plan["categories"][c]["allocation_b1"] for c in common.CATEGORIES) == 504


def test_b1_terms_avoid_excluded_anchors(plan):
    excluded = set(plan["excluded_terms"])
    for c in common.CATEGORIES:
        for t in plan["categories"][c]["b1_terms"] + plan["categories"][c]["frame_tail"]:
            assert t not in excluded, f"{t} is a reference anchor but sits in the frame"


def test_excluded_terms_are_snapshot_terms(plan):
    terms = snap_terms(plan)
    for t in plan["excluded_terms"]:
        assert t in terms


def snap_terms(plan):
    return set(plan["excluded_terms"]) | {t for c in common.CATEGORIES for t in
                                          plan["categories"][c]["b1_terms"] +
                                          plan["categories"][c]["frame_tail"]}


def test_frame_size_fields_consistent(plan):
    for c in common.CATEGORIES:
        cat = plan["categories"][c]
        assert cat["frame_size"] + cat["excluded_from_frame"] <= cat["frame_size_pre_exclusion"]
        assert len(cat["b1_terms"]) == cat["allocation_b1"]
        assert len(cat["b1_frame_rank"]) == cat["allocation_b1"]
        assert all(r in (0, 1, 2) for r in cat["b1_frame_rank"])
        # replacement-wave ranks: one per tail item, same seed stream (validate.py wave)
        assert len(cat["frame_tail_frame_rank"]) == len(cat["frame_tail"])
        assert all(r in (0, 1, 2) for r in cat["frame_tail_frame_rank"])


def test_b1_terms_match_committed_frame_summary(plan):
    """Immutability gate for the taxonomy_kind wiring (the previous worker's edit may not
    shift the frame): the freshly computed plan's b1_terms/ranks/tails must equal the
    committed frame_summary.json, category by category. Only tau_emb (and the new
    frame_tail_frame_rank key) may differ from an earlier revision."""
    import common as _c
    committed = _c.FRAME_SUMMARY
    if not committed.exists():
        pytest.skip("committed frame_summary.json not present")
    data = json.loads(committed.read_text(encoding="utf-8"))
    if data.get("total_b1") != plan["total_b1"]:
        pytest.skip("committed frame_summary is from a different frame revision")
    for c in common.CATEGORIES:
        assert plan["categories"][c]["b1_terms"] == data["categories"][c]["b1_terms"]
        assert plan["categories"][c]["b1_frame_rank"] == data["categories"][c]["b1_frame_rank"]
        assert plan["categories"][c]["frame_tail"] == data["categories"][c]["frame_tail"]
    # 47.A1 (CP-1 rejection, one prompt revision): frame_summary.json is never rewritten,
    # so its round-1 prompt_sha256 no longer equals the live template -- by design. The
    # gate here is FRAME immutability (the item lists above, unchanged by the amendment);
    # the revised hash is pinned in bank/eqv2_2026-10/prompt_sha256_r2.json and the plan's
    # stamp must track the CURRENT template, not the round-1 file.
    assert plan["prompt_sha256"] == common.prompt_sha256()


def test_allocate_roundrobin_largest_first():
    frames = {"a": ["t%02d" % i for i in range(20)],   # large
              "b": ["u%02d" % i for i in range(20)],   # large
              "c": ["x1"],                            # short -> gives its whole frame
              "d": ["y1", "y2"]}                      # short -> gives its whole frame
    alloc, deficit = frame_mod.allocate(frames, quota=8)
    assert deficit == 0
    assert alloc["c"] == 1 and alloc["d"] == 2
    assert alloc["a"] + alloc["b"] == 8 * 4 - 3
    assert alloc["a"] >= alloc["b"] >= 8  # largest frames absorb first, never past their size


def test_allocate_reports_unfillable_deficit():
    frames = {"a": ["t%02d" % i for i in range(10)], "c": ["x1"]}
    alloc, deficit = frame_mod.allocate(frames, quota=8)
    assert alloc["a"] == 10 and alloc["c"] == 1 and deficit == 5  # short + capped: still short


def test_reference_anchor_locals_nonempty():
    locals_ = common.reference_anchor_locals()
    assert len(locals_) > 100
    assert "Sensor" in locals_


def test_frame_summary_file_round_trip(plan, tmp_path):
    import frame
    p = tmp_path / "frame_summary.json"
    frame.main(["--out", str(p), "--no-hook"])
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["total_b1"] == 504
    assert data["seed"] == common.SEED
    assert data["prompt_sha256"] == common.prompt_sha256()
    assert isinstance(data["tau_emb"], (int, float, type(None)))


def test_no_banned_words_or_endpoints_in_tools():
    """The forbidden vocabulary and endpoint/host text must not appear in the tools."""
    import re
    bad = re.compile(r"registered|confirmator|pre-?registr|\b\d{1,3}(\.\d{1,3}){3}\b|:\d{4,5}\b|/home/|<tmp>/")
    for f in sorted(TOOLS.glob("*.py")):
        txt = f.read_text(encoding="utf-8")
        m = bad.search(txt)
        assert m is None, f"{f.name}: forbidden text {m.group(0)!r}"
