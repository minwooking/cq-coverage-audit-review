"""Tests for amendment 47.A1 (CP-1 rejection of batch b1 -> one prompt revision).
AI-generated draft: a person must review and test it before use.

The CP-1 screen rejected b1 (6/30). The amendment changes ONLY:
  * the relations question frames (the {owner} placeholder is now the shape owner, so the
    doubled-term sentences CQE288/292/297 cannot be produced) and frame 2 of instances
    (plural-safe "example(s)", the CQE337 ambiguity),
  * build_prompt's substitution and the relations fact lines,
  * a V1-series form check for relations rows (the local name may appear at most once).
Everything else -- templates of the other four categories and instances frames 0/1,
SYSTEM_PROMPT, the item list, frame, seed, D1-D5, tau_emb, model parameters -- is pinned
byte-identical or list-identical by the tests below.
"""
import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import common  # noqa: E402
import draft as draft_mod  # noqa: E402
import validate as validate_mod  # noqa: E402

# --------------------------------------------------------------- frozen C2 text (byte pin)
# Transcribed from the C2 tool (commit 20b2a73). 47.A1 may not touch any of this text.
C2_SYSTEM_PROMPT = (
    "You write ONE short exam question in English about the named term of the Brick "
    "schema, using ONLY the supplied facts. Output JSON: {\"question\": \"...\"}. "
    "Exactly one question mark. At most 30 words. The question must name the term exactly "
    "as given. Do not invent facts not shown. No other keys, no explanation."
)
C2_UNTOUCHED = {
    "concept_definition": [
        "Ask what the term {local} is or represents.",
        "Ask what the term {local} represents, in your own words.",
        "Ask for a definition of {local}, phrased differently from a textbook gloss.",
    ],
    "taxonomy": [
        "Ask for the direct superclass(es) of {local}.",
        "Ask which classes are the direct subclasses of {local}.",
        "Ask where {local} sits in the class hierarchy (parent side), phrased freshly.",
    ],
    "slots_facets": [
        "Ask what the property {local} records.",
        "Ask which quantity or facet {local} captures.",
        "Ask for the meaning of {local} as an entity property.",
    ],
    "methodology": [
        "Ask how the schema documents the change to the term {local}.",
        "Ask what happened to {local} and what replaces it.",
        "Ask how users should handle the term {local} now.",
    ],
}


def test_system_prompt_and_other_category_frames_byte_invariant():
    assert common.SYSTEM_PROMPT == C2_SYSTEM_PROMPT
    for cat, frames in C2_UNTOUCHED.items():
        assert common.FRAME_TEMPLATES[cat] == frames, cat


def test_instances_only_frame_two_changed():
    inst = common.FRAME_TEMPLATES["instances"]
    assert inst[0] == "Ask which examples the definition of {local} gives ({key_side})."
    assert inst[1] == "Ask what the definition of {local} lists as instances or examples."
    # the amended frame: no forced singular, explicit multi-example handling (CQE337)
    assert "example(s)" in inst[2]
    assert "for an example that" not in inst[2].lower()


def test_relations_frames_name_owner_and_local_once_distinct():
    for frame in common.FRAME_TEMPLATES["relations"]:
        text = frame.format(local="brick:fooOf", owner="brick:BarOwner")
        assert "brick:BarOwner" in text
        assert "brick:fooOf" in text
        assert text.count("brick:fooOf") == 1
        assert text.count("brick:BarOwner") == 1


# --------------------------------------------------------------- build_prompt wiring
def test_build_prompt_relations_substitutes_shape_owner(snap, frame_plan):
    import re
    items = [it for it in common.frame_items(frame_plan) if it["category"] == "relations"]
    for it in items:
        facts = common.build_facts(snap, it["term"], "relations", it["frame_rank"])
        assert facts["owner"] == snap.owner_of_prop(it["term"])
        assert facts["owner"] != it["term"]  # the C2 defect: owner was the property term
        p = common.build_prompt("relations", it["frame_rank"], facts, it["term"], 0)
        user = p[1]["content"]
        instr = user.split("Instruction:", 1)[1]
        assert facts["owner"] in instr, it["cq_id"]
        assert "shape owner: " + facts["owner"] in user, it["cq_id"]
        assert "property name: " + it["term"] in user, it["cq_id"]
        # the instruction must not be the old doubled sentence
        assert instr.count(common.local(it["term"])) <= 1


def test_build_prompt_other_categories_have_no_owner_line(snap, frame_plan):
    for cat in ("concept_definition", "taxonomy", "slots_facets", "instances", "methodology"):
        it = next(i for i in common.frame_items(frame_plan) if i["category"] == cat)
        facts = common.build_facts(snap, it["term"], cat, it["frame_rank"])
        p = common.build_prompt(cat, it["frame_rank"], facts, it["term"], facts["kind"])
        assert "shape owner" not in p[1]["content"]


# --------------------------------------------------------------- hash pinning
def test_prompt_hash_changed_from_round_one_and_pinned():
    assert common.prompt_sha256() != "baf4e1fe6367e387b5fb443d873e850275fe53563d67e8f0c4ccd20dbaa3987f"
    pin = common.BANK / "prompt_sha256_r2.json"
    if not pin.exists():
        pytest.skip("prompt_sha256_r2.json not present (pre-amendment checkout)")
    data = json.loads(pin.read_text(encoding="utf-8"))
    assert data["prompt_sha256"] == common.prompt_sha256()
    assert data["previous_sha256"] == "baf4e1fe6367e387b5fb443d873e850275fe53563d67e8f0c4ccd20dbaa3987f"


def test_expected_sha_prefers_r2_file_then_frame(tmp_path, monkeypatch):
    r2 = tmp_path / "prompt_sha256_r2.json"
    frame = tmp_path / "frame_summary.json"
    frame.write_text(json.dumps({"prompt_sha256": "f" * 64}), encoding="utf-8")
    r2.write_text(json.dumps({"prompt_sha256": "a" * 64}), encoding="utf-8")
    monkeypatch.setattr(common, "PROMPT_SHA256_FILE", r2)
    monkeypatch.setattr(common, "FRAME_SUMMARY", frame)
    assert common.expected_prompt_sha256() == "a" * 64
    r2.unlink()
    assert common.expected_prompt_sha256() == "f" * 64
    frame.unlink()
    assert common.expected_prompt_sha256() == ""


def test_item_list_unchanged_by_amendment(frame_plan):
    """The amendment may not move a single frame item: the committed b1 lists (and their
    frame ranks) must still match a freshly built plan."""
    committed = common.FRAME_SUMMARY
    if not committed.exists():
        pytest.skip("committed frame_summary.json not present")
    data = json.loads(committed.read_text(encoding="utf-8"))
    for c in common.CATEGORIES:
        assert frame_plan["categories"][c]["b1_terms"] == data["categories"][c]["b1_terms"]
        assert frame_plan["categories"][c]["b1_frame_rank"] == data["categories"][c]["b1_frame_rank"]
        assert frame_plan["categories"][c]["frame_tail"] == data["categories"][c]["frame_tail"]
    ids = [it["cq_id"] for it in common.frame_items(data)]
    assert ids == [f"CQE{i:03d}" for i in range(1, 505)]


# --------------------------------------------------------------- V1f (relations form check)
def _rel_row(snap, item, question):
    facts = common.build_facts(snap, item["term"], "relations", item["frame_rank"])
    return {"cq_id": item["cq_id"], "category": "relations", "term": item["term"],
            "question": question, "grounding": facts["grounding"],
            "expected_answer": facts["expected_answer"], "ask": facts["ask"],
            "ask_expressible": facts["ask_expressible"], "batch": "b1",
            "frame_rank": item["frame_rank"], "draft_model": "mock",
            "prompt_sha256": common.prompt_sha256()}


def test_v1f_relations_double_name_fails(snap, frame_plan, mock_embed):
    import dedup as dedup_mod
    ctx = dedup_mod.build_context(snap, embed=mock_embed, tau=0.9)
    anchor = validate_mod.run_holdout_anchor_fn()[0]
    item = next(i for i in common.frame_items(frame_plan) if i["category"] == "relations")
    dbl = _rel_row(snap, item, f"What does {item['term']} record for {item['term']}?")
    fails = validate_mod.validate_row(snap, dbl, anchor, ctx)
    assert any(f == "V1 relations term repeated in question" for f in fails), fails
    one = _rel_row(snap, item, f"Which class does {item['term']} point to when "
                               f"{snap.owner_of_prop(item['term'])} uses it?")
    fails = validate_mod.validate_row(snap, one, anchor, ctx)
    assert not any("V1 relations" in f for f in fails), fails


def test_v1f_never_fires_outside_relations(snap, frame_plan, mock_embed):
    import dedup as dedup_mod
    ctx = dedup_mod.build_context(snap, embed=mock_embed, tau=0.9)
    anchor = validate_mod.run_holdout_anchor_fn()[0]
    for cat in ("concept_definition", "taxonomy", "slots_facets", "instances", "methodology"):
        item = next(i for i in common.frame_items(frame_plan) if i["category"] == cat)
        facts = common.build_facts(snap, item["term"], cat, item["frame_rank"])
        q = f"What is {item['term']} and what does {item['term']} mean?"  # doubled ON purpose
        row = {"cq_id": item["cq_id"], "category": cat, "term": item["term"], "question": q,
               "grounding": facts["grounding"], "expected_answer": facts["expected_answer"],
               "ask": facts["ask"], "ask_expressible": facts["ask_expressible"], "batch": "b1",
               "frame_rank": item["frame_rank"], "draft_model": "mock",
               "prompt_sha256": common.prompt_sha256()}
        fails = validate_mod.validate_row(snap, row, anchor, ctx)
        assert not any("V1 relations" in f for f in fails), (cat, fails)


def test_v1f_on_round_one_validated_rows_only_relations_fire(tmp_path, snap):
    """Regression on real round-1 text (committed file may be absent -> skip): replay the
    V1f rule over all validated rows and assert it fires ONLY on relations rows, so the
    amendment cannot change the pass/fail verdict of any other category."""
    validated = common.BANK / "validated_b1.jsonl"
    if not validated.exists():
        pytest.skip("round-1 validated_b1.jsonl not present (not committed)")
    import dedup as dedup_mod
    ctx = _mock_ctx(snap)
    anchor = validate_mod.run_holdout_anchor_fn()[0]
    rows = [json.loads(l) for l in validated.read_text(encoding="utf-8").splitlines() if l.strip()]
    frame = json.loads(common.FRAME_SUMMARY.read_text(encoding="utf-8"))
    idx = {it["cq_id"]: it for it in common.frame_items(frame)}
    fired = {"relations": 0, "other": 0}
    for r in rows:
        if not r.get("term"):
            r = {**r, "term": idx.get(r.get("cq_id"), {}).get("term", "")}
        fails = validate_mod.validate_row(snap, dict(r), anchor, ctx)
        hit = any(f == "V1 relations term repeated in question" for f in fails)
        if hit:
            fired["relations" if r.get("category") == "relations" else "other"] += 1
    assert fired["other"] == 0
    assert fired["relations"] >= 14  # 16 doubled round-1 relations rows, V4-drops aside


def _mock_ctx(snap):
    import numpy as np
    import hashlib
    import dedup as dedup_mod

    class E:
        def __call__(self, texts):
            out = []
            for t in texts:
                seed = int.from_bytes(hashlib.sha256(t.lower().encode()).digest()[:8], "little")
                v = np.array([(seed >> (i * 3)) % 13 for i in range(16)], dtype=float) + 1.0
                out.append(v / float(np.linalg.norm(v)))
            return np.array(out)

    return dedup_mod.build_context(snap, embed=E(), tau=0.9)
