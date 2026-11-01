"""Tests for draft.py -- blind drafting with a mock client (addendum 47, plan-based, exploratory).
AI-generated draft: a person must review and test it before use.

No network: the real client is only built with --execute; these tests inject MockClient.
The audit-hook test installs the process-global hook once (test-order note: files run
alphabetically and the hook test lives here, after test_blind_audit.py).
"""
import json
import re
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import common  # noqa: E402
import draft as draft_mod  # noqa: E402

FRAME = {}


def frame_items(frame_plan):
    return common.frame_items(frame_plan)


# ---------------------------------------------------------------- request shape
def test_request_body_has_no_tools():
    """47.3: drafting requests carry NO tools (the assert lives in make_request_body)."""
    body = draft_mod.make_request_body([{"role": "system", "content": "s"},
                                        {"role": "user", "content": "x"}], "m")
    assert "tools" not in body and "functions" not in body
    assert body["temperature"] == 0 and body["max_tokens"] == 256
    assert body["response_format"] == {"type": "json_object"}
    assert body["enable_thinking"] is False


def test_make_request_body_asserts_no_tools_in_source():
    """47.3 'asserted in code': make_request_body's own body must contain the guard."""
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(draft_mod.make_request_body))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            txt = ast.dump(node)
            if "tools" in txt and "functions" in txt:
                return
    pytest.fail("make_request_body lost its no-tools assert")


def test_plan_items_b2_reads_the_batch2_plan():
    """C2 refused b2 (no batch-1 outcome counts); with batch2_plan.json it is planned from
    the plan, cross-checked against the frame tail (tests/test_batch2.py covers the rest)."""
    frame = json.loads((common.BANK / "frame_summary.json").read_text(encoding="utf-8"))
    items = draft_mod.plan_items(frame, "b2")
    assert len(items) == 504 and items[0]["cq_id"] == "CQE505" and {i["batch"] for i in items} == {"b2"}
    with pytest.raises(draft_mod.DraftRefused):
        draft_mod.plan_items(frame, "b3")


def test_mockclient_deterministic_questions():
    c = draft_mod.MockClient()
    body = draft_mod.make_request_body(
        [{"role": "system", "content": "s"},
         {"role": "user", "content": "Term: brick:Sensor  Local name: Sensor"}], "m")
    r1 = c.complete(body)
    r2 = c.complete(body)
    assert json.loads(r1[0]) == json.loads(r2[0])


def test_parse_question_errors():
    with pytest.raises(draft_mod.DraftCallError):
        draft_mod.parse_question("not json {")
    with pytest.raises(draft_mod.DraftCallError):
        draft_mod.parse_question(json.dumps({"answer": "x"}))


# ---------------------------------------------------------------- draft_one
def test_draft_one_produces_full_row(snap, frame_items_fixture, tmp_logs):
    draft_mod._CALL_LOG = tmp_logs / "calls.jsonl"
    item = frame_items_fixture[0]
    row = draft_mod.draft_one(draft_mod.MockClient(), item, snap)
    assert row["cq_id"] == item["cq_id"] and row["category"] == item["category"]
    assert "?" in row["question"] and len(row["question"].split()) <= 30
    for col in ("grounding", "expected_answer", "ask", "ask_expressible", "cluster_id",
                "batch", "frame_rank", "draft_model", "prompt_sha256"):
        assert col in row
    assert row["ask"].startswith("ASK {")
    assert row["cluster_id"] == row["cq_id"]  # 47.3 freeze: cluster_id == cq_id
    assert row["prompt_sha256"] == common.prompt_sha256()


def test_draft_one_shape_retry_failure(tmp_logs, monkeypatch):
    """A 31-word generation never enters the batch: it retries RETRIES times and raises."""
    monkeypatch.setattr(draft_mod.time, "sleep", lambda *_a, **_k: None)

    class Chatty:
        model = "mock-chatty"
        def __init__(self):
            self.calls = 0
        def complete(self, body):
            self.calls += 1
            return json.dumps({"question": "word " * 30 + "word?"}), 0.1
    item = {"cq_id": "CQE999", "category": "concept_definition", "term": "brick:Sensor",
            "frame_rank": 0, "batch": "b1"}
    draft_mod._CALL_LOG = tmp_logs / "calls.jsonl"
    ch = Chatty()
    with pytest.raises(draft_mod.DraftCallError):
        draft_mod.draft_one(ch, item, common.Snapshot(common.SNAPSHOT))
    assert ch.calls == draft_mod.RETRIES


def test_taxonomy_prompt_matches_ask_form(snap):
    """taxonomy_kind fix (the previous worker's edit): the prompt frame and the ASK body
    must agree. rank=1 with children -> children-form ASK and children-phrased prompt;
    rank != 1 -> parents-form for both. Childless terms always parents-form."""
    terms = sorted(snap.terms())
    with_kids = next(t for t in terms
                     if t.startswith("brick:") and snap.children(t) and snap.parents(t))
    kids_only = next(t for t in terms
                     if t.startswith("brick:") and snap.children(t) and not snap.parents(t))
    f1 = common.build_facts(snap, with_kids, "taxonomy", 1)
    assert f1["kind"] == 1 and "SELECT (COUNT(DISTINCT ?c)" in f1["ask"]
    p1 = common.build_prompt("taxonomy", 1, f1, with_kids, f1["kind"])
    assert "subclasses" in p1[1]["content"].lower()
    f0 = common.build_facts(snap, with_kids, "taxonomy", 2)
    assert f0["kind"] == 0 and "NOT EXISTS" in f0["ask"]
    p0 = common.build_prompt("taxonomy", 2, f0, with_kids, f0["kind"])
    assert "subclass" not in p0[1]["content"].lower().split("Instruction:")[-1] \
        .replace("superclass", "")  # children-phrasing must not appear
    fk = common.build_facts(snap, kids_only, "taxonomy", 1)
    assert fk["kind"] == 1 and "SELECT (COUNT" in fk["ask"]  # children -> children form
    for rank in range(3):  # childless -> never children form
        fc = common.build_facts(snap, next(t for t in terms if t.startswith("brick:")
                                           and not snap.children(t)), "taxonomy", rank)
        assert fc["kind"] == 0


def test_draft_one_uses_facts_kind_not_item_kind(snap, tmp_logs):
    """An item carrying a stale 'kind' must NOT steer the prompt -- facts decide."""
    draft_mod._CALL_LOG = tmp_logs / "calls.jsonl"
    terms = sorted(snap.terms())
    term = next(t for t in terms if t.startswith("brick:") and snap.children(t)
                and snap.parents(t))
    item = {"cq_id": "CQE998", "category": "taxonomy", "term": term, "frame_rank": 1,
            "kind": 0, "batch": "b1"}
    row = draft_mod.draft_one(draft_mod.MockClient(), item, snap)
    assert "SELECT (COUNT(DISTINCT ?c)" in row["ask"]  # ASK is children form (rank 1)


# ---------------------------------------------------------------- run_draft + resume
def test_run_draft_and_resume(tmp_logs, frame_items_fixture):
    snap = common.Snapshot(common.SNAPSHOT)
    items = frame_items_fixture[:8]
    out = tmp_logs / "draft_b1.jsonl"
    log = tmp_logs / "calls_b1.jsonl"
    res = draft_mod.run_draft(items, snap, draft_mod.MockClient(), out, log, workers=2)
    assert res["requested"] == 8 and res["resumed_skipped"] == 0 and not res["failed"]
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 8
    assert {r["cq_id"] for r in rows} == {i["cq_id"] for i in items}
    # resume: pre-mark two ids as already done
    done = {r["cq_id"] for r in rows[:2]}
    out.write_text("".join(json.dumps(r) + "\n" for r in rows[:2]), encoding="utf-8")
    res2 = draft_mod.run_draft(items, snap, draft_mod.MockClient(), out, log, workers=1)
    assert res2["resumed_skipped"] == 2 and res2["requested"] == 6
    assert len([l for l in out.read_text(encoding="utf-8").splitlines()]) == 8


def test_run_draft_records_failures(tmp_logs, monkeypatch):
    monkeypatch.setattr(draft_mod.time, "sleep", lambda *_a, **_k: None)
    class Failing:
        model = "nope"
        def complete(self, body):
            raise draft_mod.DraftCallError("boom", retry_after=0.0)
    snap = common.Snapshot(common.SNAPSHOT)
    item = {"cq_id": "CQE997", "category": "concept_definition", "term": "brick:Sensor",
            "frame_rank": 0, "batch": "b1"}
    res = draft_mod.run_draft([item], snap, Failing(), tmp_logs / "d.jsonl",
                              tmp_logs / "c.jsonl", workers=1)
    assert res["failed"] and res["failed"][0]["cq_id"] == "CQE997"


# ---------------------------------------------------------------- logs hygiene
def test_call_log_has_no_host_or_port(tmp_logs, frame_items_fixture):
    snap = common.Snapshot(common.SNAPSHOT)
    log = tmp_logs / "calls.jsonl"
    draft_mod.run_draft(frame_items_fixture[:4], snap, draft_mod.MockClient(),
                        tmp_logs / "d.jsonl", log, workers=1)
    txt = log.read_text(encoding="utf-8")
    assert "://" not in txt
    assert re.search(r"\b\d{1,3}(\.\d{1,3}){3}\b", txt) is None
    rec = json.loads(txt.splitlines()[0])
    assert set(rec) >= {"ts", "cq_id", "prompt", "response", "latency_s", "model_id", "ok"}


# ---------------------------------------------------------------- audit hook
def test_audit_hook_blocks_forbidden_path(tmp_logs):
    common.install_blind_hooks("blind_open_log_b1.jsonl")
    forbidden = common.ACCESS / "harness" / "variants" / "A" / "rendered_view.txt"
    with pytest.raises(common.BlindAuditError):
        open(forbidden, "r", encoding="utf-8")
    with pytest.raises(common.BlindAuditError):
        common.os.listdir(str(common.ACCESS / "harness" / "variants" / "A"))
    # the attempt IS logged (then the raise) -- that is how B2 detects it; allowed reads
    # log with only ts/event/path keys (never host or port)
    open(common.SNAPSHOT, "rb").close()
    recs = [json.loads(l) for l in
            (tmp_logs / "blind_open_log_b1.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()]
    assert recs and all(set(r) == {"ts", "event", "path"} for r in recs)
    assert any("rendered_view.txt" in r["path"] for r in recs)  # blocked attempt recorded
    assert any(str(common.SNAPSHOT) in r["path"] for r in recs)  # allowed read recorded
