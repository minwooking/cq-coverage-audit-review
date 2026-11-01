"""Tests for validate.py -- V1..V6 gates and the one replacement wave (addendum 47,
plan-based, exploratory). AI-generated draft: a person must review and test it before use.

Rows for the base cases are built from REAL frame items via common.build_facts (so they
pass V2/V3/V4 and never trip D3 -- b1 terms are anchor-excluded by construction).
Embeddings are mocked (conftest MockEmbed); no model, no network, nothing forbidden read.
"""
import csv
import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import common  # noqa: E402
import dedup as dedup_mod  # noqa: E402
import validate as validate_mod  # noqa: E402

ROW_COLS = ("cq_id", "category", "question", "grounding", "expected_answer", "ask",
            "ask_expressible", "batch", "frame_rank", "draft_model", "prompt_sha256")

_ANCHOR_FN: list = []


def anchor():
    if not _ANCHOR_FN:
        _ANCHOR_FN.append(validate_mod.run_holdout_anchor_fn()[0])
    return _ANCHOR_FN[0]


def make_row(snap, item, **over):
    """A well-formed draft row for one real frame item: model text approximated by the
    term's local name (V2-clean); script-side fields come from build_facts."""
    facts = common.build_facts(snap, item["term"], item["category"], item["frame_rank"])
    row = {"cq_id": item["cq_id"], "category": item["category"], "term": item["term"],
           "question": f"What is {common.local(item['term'])}?",
           "grounding": facts["grounding"], "expected_answer": facts["expected_answer"],
           "ask": facts["ask"], "ask_expressible": facts["ask_expressible"],
           "batch": "b1", "frame_rank": item["frame_rank"], "draft_model": "mock",
           "prompt_sha256": common.prompt_sha256()}
    row.update(over)
    return row


@pytest.fixture
def vctx(snap, mock_embed):
    return dedup_mod.build_context(snap, embed=mock_embed, tau=0.9)


@pytest.fixture
def base_row(snap, frame_plan):
    return make_row(snap, common.frame_items(frame_plan)[0])


# ---------------------------------------------------------------- V1
def test_v1_happy_path(snap, base_row, vctx):
    assert validate_mod.validate_row(snap, base_row, anchor(), vctx) == []


def test_v1_column_shape_cases(snap, base_row, vctx):
    def fails(row):
        return validate_mod.validate_row(snap, row, anchor(), vctx)
    r = dict(base_row); del r["ask"]
    assert any("V1 missing column" in f for f in fails(r))
    assert any("V1 cq_id pattern" in f for f in fails({**base_row, "cq_id": "XQB001"}))
    assert any("V1 unknown category" in f for f in fails({**base_row, "category": "bogus"}))
    assert any("question-mark" in f for f in fails({**base_row, "question": "What is it? Really?"}))
    assert any("word count" in f for f in fails({**base_row, "question": "word " * 31 + "brick:Sensor?"}))


# ---------------------------------------------------------------- V2
def test_v2_name_or_label(snap, base_row, vctx):
    assert validate_mod.validate_row(snap, base_row, anchor(), vctx) == []
    assert any("V2" in f for f in validate_mod.validate_row(
        snap, {**base_row, "question": "What does this device class mean?"}, anchor(), vctx))


# ---------------------------------------------------------------- V3
def test_v3_anchor_exists(snap, base_row, vctx):
    r = {**base_row, "grounding": "skos:definition brick:NoSuchTerm_ZZZ"}
    assert any("V3 anchors missing" in f for f in validate_mod.validate_row(snap, r, anchor(), vctx))


# ---------------------------------------------------------------- V4
def test_v4_ask_true(snap, base_row, vctx):
    r = {**base_row, "ask": "ASK { brick:NoSuchTerm_ZZZ skos:definition ?d }"}
    assert any("V4" in f for f in validate_mod.validate_row(snap, r, anchor(), vctx))
    r = {**base_row, "ask": "ASK { brick:Sensor skos:definition ?d }"}
    assert not any(f.startswith("V4") for f in validate_mod.validate_row(snap, r, anchor(), vctx))


# ---------------------------------------------------------------- V5
def test_v5_leak_rules(snap, base_row, vctx):
    r = {**base_row, "question": "A point that carries the value of a device across systems?",
         "expected_answer": "A point that carries the value of a device that measures variables"}
    fails = validate_mod.validate_row(snap, r, anchor(), vctx)
    assert any("V5 longest common substring" in f for f in fails)
    exp = base_row["expected_answer"]
    # expected answer embedded in the question: lcs long, jaccard high
    fails = validate_mod.validate_row(snap, {**base_row, "question": exp + "?"}, anchor(), vctx)
    assert any("V5" in f for f in fails)


# ---------------------------------------------------------------- V6 via D-rules
def test_v6_reference_duplicate_caught(snap, mock_embed):
    ctx = dedup_mod.build_context(snap, embed=mock_embed, tau=0.9)
    v1 = common.ACCESS / "bank" / "cq_bank_brick_v1.csv"
    with v1.open(newline="", encoding="utf-8") as fh:
        first = next(iter(csv.DictReader(fh)))
    r = {"cq_id": "CQE900", "category": "concept_definition", "term": "brick:Sensor",
         "question": first["question"], "grounding": first["grounding"],
         "expected_answer": first.get("expected_answer", ""), "ask": "ASK { ?s ?p ?o }",
         "ask_expressible": "partial", "batch": "b1", "frame_rank": 0,
         "draft_model": "mock", "prompt_sha256": common.prompt_sha256()}
    fails = validate_mod.validate_row(snap, r, anchor(), ctx)
    assert any("D1" in f for f in fails)


# ---------------------------------------------------------------- batch + wave
def test_batch_drop_and_replace(snap, frame_plan, mock_embed):
    items = common.frame_items(frame_plan)[:2]
    rows = [make_row(snap, items[0]),
            make_row(snap, items[1], question="What does the ghost term mean?")]
    seen = []

    def drafter(term, cat, rank, cid):
        seen.append((term, cat, rank, cid))
        it = {"cq_id": cid, "category": cat, "term": term, "frame_rank": rank, "batch": "b1"}
        return make_row(snap, it)

    res = validate_mod.validate_batch(rows, snap, frame_plan, "b1", drafter=drafter, embed=mock_embed, tau=0.9)
    assert len(res["kept"]) == 2
    dropped = res["dropped"][0]
    assert dropped["replaced_by"] == items[1]["cq_id"]
    assert seen
    term, cat, rank, _ = seen[0]
    assert term in frame_plan["categories"]["concept_definition"]["frame_tail"]
    assert rank in (0, 1, 2)
    assert res["still_short_by"]["concept_definition"] == \
        frame_plan["categories"]["concept_definition"]["allocation_b1"] - 2


def test_batch_no_drafter_continues_short(snap, frame_plan, mock_embed):
    items = common.frame_items(frame_plan)[:2]
    rows = [make_row(snap, items[0]),
            make_row(snap, items[1], question="What does the ghost term mean?")]
    res = validate_mod.validate_batch(rows, snap, frame_plan, "b1", embed=mock_embed, tau=0.9)
    assert len(res["kept"]) == 1 and len(res["dropped"]) == 1
    assert res["still_short_by"]


def test_dropped_record_fields(snap, frame_plan, mock_embed):
    items = common.frame_items(frame_plan)[:1]
    rows = [make_row(snap, items[0], question="What does the ghost term mean?")]
    res = validate_mod.validate_batch(rows, snap, frame_plan, "b1", embed=mock_embed, tau=0.9)
    d = res["dropped"][0]
    assert set(d) == {"cq_id", "term", "category", "reasons", "replaced_by"}
    assert d["term"] == items[0]["term"]
    assert any(f.startswith("V2") for f in d["reasons"])


def test_anchor_route_recorded():
    _, route = validate_mod.run_holdout_anchor_fn()
    assert route in ("import", "ast-extract")


# ---------------------------------------------------------------- main()
def test_validate_main_writes_out_and_report(tmp_path, snap, frame_plan, monkeypatch,
                                             mock_embed):
    orig = dedup_mod.build_context
    monkeypatch.setattr(dedup_mod, "build_context",
                        lambda s, extra_rows=None, embed=None, tau=None: orig(
                            s, extra_rows=extra_rows, embed=mock_embed, tau=0.9))
    items = common.frame_items(frame_plan)[:2]
    rows = [make_row(snap, items[0]),
            make_row(snap, items[1], question="What does the ghost term mean?")]
    rp = tmp_path / "rows.jsonl"
    rp.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    frame_path = tmp_path / "frame_summary.json"
    frame_path.write_text(json.dumps(frame_plan), encoding="utf-8")
    out, rep = tmp_path / "validated.jsonl", tmp_path / "report.json"
    rc = validate_mod.main(["--rows", str(rp), "--out", str(out), "--frame", str(frame_path),
                            "--report", str(rep), "--no-hook"])
    assert rc == 0
    kept = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert [r["cq_id"] for r in kept] == [items[0]["cq_id"]]
    report = json.loads(rep.read_text(encoding="utf-8"))
    assert report["n_kept"] == 1 and report["n_dropped"] == 1
    assert report["anchor_route"] in ("import", "ast-extract")
