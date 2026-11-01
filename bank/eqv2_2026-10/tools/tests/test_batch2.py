"""Tests for the batch-2 support (addendum 47, 47.3 'Batch 2'; BATCH2_PROCEDURE.md).
AI-generated draft: a person must review and test it before use.

No model call, no network.  Inputs are committed files only: frame_summary.json, the
committed b1 validation report / validated rows / frozen bank, and batch2_plan.json.
Nothing here opens an eligibility, view, pair, C4 or annotation file.
"""
import csv
import hashlib
import json
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import blind_audit  # noqa: E402
import common  # noqa: E402
import dedup as dedup_mod  # noqa: E402
import draft as draft_mod  # noqa: E402
import plan_b2  # noqa: E402
import screen_sample  # noqa: E402
import validate as validate_mod  # noqa: E402
from test_validate import make_row  # noqa: E402

BANK = common.BANK
N2 = 504  # the value in the size file; the tests never open that file (the plan records it)

# Pinned from the b1 code as it was before the b2 change (HEAD 769871d).
B1_ITEMS_SHA = "b17eb97a6e143d90fbde9cc60c3e7c8fb6647179257092e68258282372c2c047"
PROMPT_R2 = "a20414e1bfd2e5c354066696d13b4e76229a1ea2b3714347de2ec56ac9008b84"


@pytest.fixture(scope="module")
def frame():
    return json.loads((BANK / "frame_summary.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def b1_inputs():
    return (json.loads(plan_b2.B1_REPORT.read_text(encoding="utf-8")),
            plan_b2.read_jsonl(plan_b2.B1_VALIDATED))


@pytest.fixture(scope="module")
def plan(frame, b1_inputs):
    return plan_b2.build_plan(frame, b1_inputs[0], b1_inputs[1], N2)


# ---------------------------------------------------------------- capacity
def test_b1_used_tail_counts(frame, b1_inputs):
    used = plan_b2.b1_used_tail_counts(frame, *b1_inputs)
    assert used == {"concept_definition": 5, "taxonomy": 31, "relations": 0,
                    "slots_facets": 0, "instances": 0, "methodology": 9}


def test_used_prefix_covers_every_b1_replacement(frame, b1_inputs):
    used = plan_b2.b1_used_tail_counts(frame, *b1_inputs)
    repl = plan_b2.b1_replacing_terms(*b1_inputs)
    assert sum(len(v) for v in repl.values()) == 37
    for cat, terms in repl.items():
        tail = frame["categories"][cat]["frame_tail"]
        assert set(terms) <= set(tail[:used[cat]])
        assert all(t not in frame["categories"][cat]["b1_terms"] for t in terms)


def test_b1_used_tail_matches_draft_call_log_when_present(frame, b1_inputs):
    log = BANK / "logs_r2" / "draft_calls_b1.jsonl"
    if not log.exists():
        pytest.skip("round-2 draft call log is not in this checkout")
    used = plan_b2.b1_used_tail_counts(frame, *b1_inputs)
    recs = plan_b2.read_jsonl(log)
    for cat in ("concept_definition", "taxonomy", "methodology"):
        tail = frame["categories"][cat]["frame_tail"]
        pos = {t: i for i, t in enumerate(tail)}
        drafted = {pos[r["term"]] for r in recs if r["category"] == cat and r["term"] in pos}
        assert drafted == set(range(used[cat]))  # every drafted tail term, none beyond the prefix


def test_capacity_excludes_b1_use(plan, frame):
    c = plan["categories"]
    for cat in common.CATEGORIES:
        tail_len = len(frame["categories"][cat]["frame_tail"])
        assert c[cat]["tail_total"] == tail_len
        assert c[cat]["remaining"] == tail_len - c[cat]["b1_used"]
    assert (c["concept_definition"]["remaining"], c["taxonomy"]["remaining"],
            c["methodology"]["remaining"]) == (979, 1422, 65)
    for cat in ("instances", "relations", "slots_facets"):
        assert c[cat]["remaining"] == 0 and c[cat]["allocation_b2"] == 0


# ---------------------------------------------------------------- allocation
def test_quota_and_redistribution(plan):
    assert plan["n2"] == N2 and plan["quota_per_category"] == 84
    alloc = {c: v["allocation_b2"] for c, v in plan["categories"].items()}
    assert alloc == {"concept_definition": 219, "taxonomy": 220, "relations": 0,
                     "slots_facets": 0, "instances": 0, "methodology": 65}
    assert sum(alloc.values()) == N2 == plan["n_items"] == len(plan["items"])
    assert all(alloc[c] <= plan["categories"][c]["remaining"] for c in alloc)


def test_allocation_is_the_shared_function(plan, frame, b1_inputs):
    used = plan_b2.b1_used_tail_counts(frame, *b1_inputs)
    remaining = {c: frame["categories"][c]["frame_tail"][used[c]:] for c in common.CATEGORIES}
    import frame as frame_mod
    alloc, deficit = frame_mod.allocate(remaining, quota=84)
    assert deficit == 0
    assert alloc == {c: v["allocation_b2"] for c, v in plan["categories"].items()}


def test_total_capacity_below_n2_is_refused(frame, b1_inputs):
    with pytest.raises(plan_b2.PlanError):
        plan_b2.build_plan(frame, *b1_inputs, 6 * 1000)  # 6000 > total remaining capacity
    with pytest.raises(plan_b2.PlanError):
        plan_b2.build_plan(frame, *b1_inputs, 500)  # not a multiple of 6


# ---------------------------------------------------------------- items, ids, order
def test_ids_are_sequential_from_cqe505_in_canonical_order(plan):
    ids = [it["cq_id"] for it in plan["items"]]
    assert ids == [f"CQE{n}" for n in range(505, 505 + N2)]
    order = [common.CATEGORIES.index(it["category"]) for it in plan["items"]]
    assert order == sorted(order)


def test_items_are_tail_prefix_in_tail_order_with_tail_ranks(plan, frame):
    for cat in common.CATEGORIES:
        catd = frame["categories"][cat]
        mine = [it for it in plan["items"] if it["category"] == cat]
        start = plan["categories"][cat]["b1_used"]
        assert [it["tail_index"] for it in mine] == list(range(start, start + len(mine)))
        assert [it["term"] for it in mine] == catd["frame_tail"][start:start + len(mine)]
        assert [it["frame_rank"] for it in mine] == catd["frame_tail_frame_rank"][start:start + len(mine)]


def test_no_b2_term_repeats_or_reuses_a_b1_term_within_its_category(plan, frame):
    kept_b1 = plan_b2.read_jsonl(plan_b2.B1_VALIDATED)  # includes the replacement wave's rows
    for cat in common.CATEGORIES:
        mine = [it["term"] for it in plan["items"] if it["category"] == cat]
        assert len(set(mine)) == len(mine)
        assert not set(mine) & set(frame["categories"][cat]["b1_terms"])
        assert not set(mine) & {r["term"] for r in kept_b1 if r["category"] == cat}


def test_cross_category_term_overlap_is_the_frames_own_and_is_pinned(plan, frame):
    """A term can sit in several category frames (a different question shape and grounding
    per category); b1 has 43 such terms, b2 has the counts below.  Documented, not hidden."""
    from collections import Counter
    c = Counter(it["term"] for it in plan["items"])
    assert sum(1 for v in c.values() if v > 1) == 32
    b1_terms = {t for cat in common.CATEGORIES for t in frame["categories"][cat]["b1_terms"]}
    assert len(set(c) & b1_terms) == 82


def test_common_frame_items_b2_matches_plan(plan, frame):
    items = common.frame_items(frame, "b2")
    assert [(i["cq_id"], i["category"], i["term"], i["frame_rank"]) for i in items] == \
        [(i["cq_id"], i["category"], i["term"], i["frame_rank"]) for i in plan["items"]]
    assert {i["batch"] for i in items} == {"b2"}
    assert draft_mod.plan_items(frame, "b2") == items


def test_committed_plan_equals_recomputation(plan):
    committed = (BANK / "batch2_plan.json").read_text(encoding="utf-8")
    assert committed == plan_b2.render(plan)
    assert json.loads(committed)["items_sha256"] == plan["items_sha256"]


def test_tampered_plan_is_refused(tmp_path, frame, plan):
    bad = json.loads(plan_b2.render(plan))
    bad["items"][0]["term"] = "brick:Not_The_Tail_Term"
    p = tmp_path / "p.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        common.batch2_items(frame, p)


# ---------------------------------------------------------------- determinism
def test_plan_is_deterministic(frame, b1_inputs, plan):
    again = plan_b2.build_plan(json.loads(json.dumps(frame)), *b1_inputs, N2)
    assert plan_b2.render(again) == plan_b2.render(plan)
    assert again["items_sha256"] == plan["items_sha256"]
    assert plan["items_sha256"] == plan_b2.items_sha256(plan["items"])


# ---------------------------------------------------------------- b1 untouched
def test_b1_items_prompt_and_template_hash_unchanged(frame):
    items = common.frame_items(frame, "b1")
    assert len(items) == 504 and items[0]["cq_id"] == "CQE001" and items[-1]["cq_id"] == "CQE504"
    assert hashlib.sha256(json.dumps(items, sort_keys=True, ensure_ascii=False).encode()).hexdigest() == B1_ITEMS_SHA
    assert common.frame_items(frame) == items  # the default batch is still b1
    assert common.prompt_sha256() == PROMPT_R2 == common.expected_prompt_sha256()
    assert draft_mod.plan_items(frame, "b1") == items


def test_b1_validation_order_is_unchanged_for_three_digit_ids():
    ids = ["CQE010", "CQE002", "CQE504", "CQE100"]
    assert sorted(ids, key=common.cq_sort_key) == sorted(ids)
    assert sorted(["CQE1000", "CQE505"], key=common.cq_sort_key) == ["CQE505", "CQE1000"]


def test_draft_refuses_unknown_batch(frame):
    with pytest.raises(draft_mod.DraftRefused):
        draft_mod.plan_items(frame, "b3")


# ---------------------------------------------------------------- b2 drafting (mock only)
def test_b2_mock_draft_rows(tmp_path, snap, frame):
    items = common.frame_items(frame, "b2")
    pick = [items[0], items[-1]]  # first concept_definition row, last methodology row
    out = tmp_path / "draft_b2.jsonl"
    res = draft_mod.run_draft(pick, snap, draft_mod.MockClient(), out, tmp_path / "calls.jsonl", workers=1)
    assert res["failed"] == []
    rows = plan_b2.read_jsonl(out)
    assert [r["cq_id"] for r in rows] == ["CQE505", "CQE1008"]
    assert {r["batch"] for r in rows} == {"b2"} and {r["prompt_sha256"] for r in rows} == {PROMPT_R2}


def test_b2_validation_wave_uses_the_leftover_tail(snap, frame, plan, mock_embed):
    items = [it for it in common.frame_items(frame, "b2") if it["category"] == "concept_definition"][:2]
    rows = [make_row(snap, items[0], batch="b2"),
            make_row(snap, items[1], batch="b2", question="What does the ghost term mean?")]
    seen = []

    def drafter(term, cat, rank, cid):
        seen.append((term, cat, rank, cid))
        return make_row(snap, {"cq_id": cid, "category": cat, "term": term, "frame_rank": rank}, batch="b2")

    res = validate_mod.validate_batch(rows, snap, frame, "b2", drafter=drafter, embed=mock_embed, tau=0.9)
    cd = plan["categories"]["concept_definition"]
    first_free = frame["categories"]["concept_definition"]["frame_tail"][cd["tail_next_index"]]
    assert seen[0][0] == first_free  # past b1's wave AND past the 219 b2 items
    assert res["dropped"][0]["replaced_by"] == items[1]["cq_id"]
    assert res["still_short_by"]["concept_definition"] == cd["allocation_b2"] - 2
    assert "instances" not in res["still_short_by"]  # zero-row categories are not 'short'


def test_b2_methodology_tail_is_exhausted(frame):
    tails, ranks = common.batch2_leftover_tails(frame)
    assert tails["methodology"] == [] and ranks["methodology"] == []
    assert len(tails["concept_definition"]) == 984 - 224 and len(tails["taxonomy"]) == 1453 - 251


def test_four_digit_ids_pass_v1_and_three_digit_rule_still_holds(snap, frame, mock_embed):
    last = common.frame_items(frame, "b2")[-1]
    ctx = dedup_mod.build_context(snap, embed=mock_embed, tau=0.9)
    row = make_row(snap, last, batch="b2")
    assert not [f for f in validate_mod.validate_row(snap, row, validate_mod.run_holdout_anchor_fn()[0], ctx)
                if f.startswith("V1")]
    bad = dict(row, cq_id="CQE12345")
    assert any("V1 cq_id pattern" in f for f in
               validate_mod.validate_row(snap, bad, validate_mod.run_holdout_anchor_fn()[0], ctx))


# ---------------------------------------------------------------- dedup against b1
def test_b1_bank_as_extra_rows_feeds_d1(snap, mock_embed):
    extra = plan_b2.b1_bank_as_extra_rows(BANK / "cq_bank_brick_eqv2_b1.csv")
    assert len(extra) == 494 and set(extra[0]) == {"cq_id", "category", "question", "grounding"}
    ctx = dedup_mod.build_context(snap, extra_rows=extra, embed=mock_embed, tau=0.9)
    twin = {"cq_id": "CQE505", "question": extra[0]["question"], "grounding": "skos:definition brick:Zzz_Not_A_Term"}
    res = dedup_mod.check_row(snap, twin, ctx)
    assert "D1" in res["rules_triggered"] and res["nearest_ref_id"] == extra[0]["cq_id"]


def test_b1_extra_conversion_leaves_the_frozen_bank_untouched(tmp_path):
    bank = BANK / "cq_bank_brick_eqv2_b1.csv"
    before = hashlib.sha256(bank.read_bytes()).hexdigest()
    assert plan_b2.main(["--b1-extra", str(bank), "--out", str(tmp_path / "x.jsonl")]) == 0
    assert hashlib.sha256(bank.read_bytes()).hexdigest() == before


# ---------------------------------------------------------------- screen sample
def test_sample_reproduces_the_committed_round2_sample_and_sheet(tmp_path):
    rows = plan_b2.read_jsonl(BANK / "validated_b1_r2.jsonl")
    sample = screen_sample.draw_sample(rows, 20260914)
    out, sheet = tmp_path / "s.csv", tmp_path / "t.csv"
    screen_sample.write_outputs(sample, out, sheet, eol="\r\n")
    assert out.read_bytes() == (BANK / "screen_b1_r2_sample.csv").read_bytes()
    assert sheet.read_bytes() == (BANK / "screen_b1_r2_sheet.csv").read_bytes()


def test_sample_reproduces_the_committed_round1_sample_when_present(tmp_path):
    src = BANK / "round1" / "validated_b1.jsonl"
    if not src.exists():
        pytest.skip("round-1 validated rows are not in this checkout")
    sample = screen_sample.draw_sample(plan_b2.read_jsonl(src), 20260913)
    out, sheet = tmp_path / "s.csv", tmp_path / "t.csv"
    screen_sample.write_outputs(sample, out, sheet)
    assert out.read_bytes() == (BANK / "screen_b1_sample.csv").read_bytes()
    assert sheet.read_bytes() == (BANK / "screen_b1_sheet.csv").read_bytes()


def test_sheet_columns_match_the_b1_sheet():
    with (BANK / "screen_b1_sheet.csv").open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh))
    assert header == screen_sample.SAMPLE_COLUMNS + screen_sample.CRITERIA_COLUMNS


def test_sample_allocation_rules():
    cats = common.CATEGORIES
    assert screen_sample.allocate_sample({c: 80 for c in cats}) == {c: 5 for c in cats}
    three = {"concept_definition": 200, "taxonomy": 200, "methodology": 50}
    assert screen_sample.allocate_sample(three) == {"concept_definition": 10, "taxonomy": 10, "relations": 0,
                                                    "slots_facets": 0, "instances": 0, "methodology": 10}
    short = {"concept_definition": 200, "taxonomy": 200, "methodology": 7}
    k = screen_sample.allocate_sample(short)
    assert k["methodology"] == 7 and k["concept_definition"] == 12 and k["taxonomy"] == 11 and sum(k.values()) == 30
    assert sum(screen_sample.allocate_sample({"taxonomy": 4, "concept_definition": 3}).values()) == 7  # fewer ids than 30


def test_b2_sample_is_deterministic_and_balanced(snap, frame):
    items = common.frame_items(frame, "b2")
    rows = [{"cq_id": i["cq_id"], "category": i["category"], "question": "q", "grounding": "g",
             "expected_answer": "a"} for i in items]
    a = screen_sample.draw_sample(rows, 20260915)
    b = screen_sample.draw_sample(list(reversed(rows)), 20260915)
    assert a == b and len(a) == 30
    per = {c: sum(1 for r in a if r["category"] == c) for c in common.CATEGORIES}
    assert per == {"concept_definition": 10, "taxonomy": 10, "relations": 0, "slots_facets": 0,
                   "instances": 0, "methodology": 10}
    nums = [common.cq_sort_key(r["cq_id"])[0] for r in a]
    assert nums == sorted(nums)  # numeric id order (CQE1000.. after CQE999)


# ---------------------------------------------------------------- blind patterns
C4_PATHS = ["eligibility_b1.json", "view_manifest_b1.jsonl", "pairs_b1.json", "C4_REPORT.md",
            "inputs/A/q1.txt", "BATCH2_SIZE.json"]


@pytest.mark.parametrize("name", C4_PATHS)
def test_b2_forbidden_patterns_block_c4_outputs(name):
    synthetic = "/synthetic/eqv2/" + name
    assert common.forbidden_hit(synthetic), name


@pytest.mark.parametrize("name", C4_PATHS)
def test_runtime_hook_raises_on_c4_outputs(tmp_logs, name):
    common.install_blind_hooks("blind_open_log_b2.jsonl")
    with pytest.raises(common.BlindAuditError):
        open("/synthetic/eqv2/" + name, "rb")  # the hook fires before the file system is asked


def test_new_patterns_do_not_block_the_b2_inputs(tmp_logs):
    common.install_blind_hooks("blind_open_log_b2.jsonl")
    for p in (BANK / "batch2_plan.json", BANK / "frame_summary.json", common.SNAPSHOT,
              BANK / "prompt_sha256_r2.json", BANK / "cq_bank_brick_eqv2_b1.csv"):
        assert common.forbidden_hit(str(p)) is None, p
        open(p, "rb").close()


def test_pattern_file_keeps_the_old_entries_and_adds_five():
    cfg = json.loads((TOOLS / "blind_patterns.json").read_text(encoding="utf-8"))
    pats = cfg["patterns"]
    for old in ("eligibility", "views_for_raters", "manifests/", "annotation/", "length_experiment/inputs"):
        assert old in pats
    assert pats[-5:] == ["view_manifest", "pairs_b1", "C4_REPORT", "inputs/", "BATCH2_SIZE"]
    assert cfg["boundary_patterns"] == ["jobs_", "job.json", "draft_jobs", "run_log", "runlog"]


def test_blind_audit_b1_passes_with_the_new_tools_and_patterns():
    static = blind_audit.audit_static(TOOLS)
    viol = {f: [h for h in hits if h.get("severity") == "violation"] for f, hits in static.items()}
    assert not any(viol.values()), viol
    assert {"plan_b2.py", "screen_sample.py"} <= set(static)  # the new tools are scanned, not exempt
    assert blind_audit.EXEMPT_BY_NAME == ("eligibility.py", "views.py")


def test_b2_drafting_tools_do_not_name_the_size_file_or_c4_outputs():
    """The drafting, validation and de-duplication tools read only batch2_plan.json."""
    for name in ("draft.py", "validate.py", "dedup.py", "common.py"):
        src = (TOOLS / name).read_text(encoding="utf-8")
        for token in ("BATCH2_SIZE", "view_manifest", "pairs_b1", "C4_REPORT", "eligibility_b1"):
            assert token not in src, (name, token)
