"""Tests for the registered manifest-driven holdout queue."""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
import threading
import time
from pathlib import Path

import pytest

import run_holdout


BANK = run_holdout.ACCESS / "bank" / "cq_bank_brick_v1.csv"


def _rows() -> list[dict]:
    with BANK.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _fixture_view_line(row: dict) -> str:
    """Build a fixture line that satisfies a row's grounding the way a real
    renderer would: every bare local name (whether it started out
    unqualified/control-syntax, or is the local half of a real ontology
    qname) gets its own short ``#fragment`` -- that is what
    ``_local_name_present_ci`` actually looks for post-fix (see
    ``run_holdout.py``'s namespace/case-agnostic matching) -- and the
    literal grounding text is kept too so the exact-qname path
    (``_qualified_anchor_present``) still has something to find for rows
    whose renderer (e.g. the direct Brick-TBox view) does write qnames out
    literally.
    """
    anchors = run_holdout._grounding_anchors(row["grounding"])
    fragments = " ".join(
        f"#{anchor.split(':', 1)[1] if ':' in anchor else anchor}" for anchor in anchors
    )
    return f"support {fragments} {row['grounding']} {row['cq_id']}"


def _manifest(path: Path, count: int = 6) -> Path:
    rows = _rows()
    # Every frozen grounding is present in the fake render.  This exercises the
    # real ablation code without fabricating a variant artifact in the runner.
    view = "\n".join(_fixture_view_line(row) for row in rows)
    path.write_text(json.dumps({
        "variants": [{"id": f"V{i}", "view": view} for i in range(count)]
    }), encoding="utf-8")
    return path


def _registered_manifest(path: Path, *, view: str | None = None) -> Path:
    rows = _rows()
    view = view or "\n".join(_fixture_view_line(row) for row in rows)
    graph = path.parent / "graph.ttl"
    rendered = path.parent / "rendered_view.txt"
    graph.write_text("@prefix brick: <https://brickschema.org/schema/Brick#> .\n", encoding="utf-8")
    rendered.write_text(view, encoding="utf-8")
    entry = {
        "id": "V0",
        "graph_path": graph.name,
        "rendered_view_path": rendered.name,
        "graph_sha256": hashlib.sha256(graph.read_bytes()).hexdigest(),
        "rendered_view_sha256": hashlib.sha256(rendered.read_bytes()).hexdigest(),
    }
    payload = {"variants": [dict(entry, id=f"V{i}") for i in range(6)]}
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_registered_cell_plan_has_216_plus_controls(tmp_path: Path):
    manifest = _manifest(tmp_path / "MANIFEST.json")
    variants = run_holdout.load_variant_manifest(manifest, require_six=False)
    plan = run_holdout.build_cell_plan(_rows(), variants)
    assert len(plan) == 252
    assert sum(cell["cell_kind"] == "primary" for cell in plan) == 216
    assert sum(cell["cell_kind"] == "ablated_control" for cell in plan) == 24
    assert sum(cell["cell_kind"] == "preserved_control" for cell in plan) == 12
    assert all(cell["artifact_digest"] == run_holdout.hashlib.sha256(cell["artifact"].encode()).hexdigest()
               for cell in plan)


def test_same_registered_seed_has_same_queue_order(tmp_path: Path):
    manifest = _manifest(tmp_path / "MANIFEST.json")
    variants = run_holdout.load_variant_manifest(manifest, require_six=False)
    first = [run_holdout.cell_key(cell) for cell in run_holdout.build_cell_plan(_rows(), variants, 20260913)]
    second = [run_holdout.cell_key(cell) for cell in run_holdout.build_cell_plan(_rows(), variants, 20260913)]
    other = [run_holdout.cell_key(cell) for cell in run_holdout.build_cell_plan(_rows(), variants, 20260913)]
    assert first == second == other
    assert {cell.split(":", 1)[0] for cell in first} == {"primary", "ablated_control", "preserved_control"}


def test_missing_variant_manifest_fails_clearly(tmp_path: Path):
    with pytest.raises(SystemExit, match="변이 산출물이 없다"):
        run_holdout.load_variant_manifest(tmp_path / "does-not-exist.json")


def test_records_have_audit_fields_and_resume_attempt_preserves_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    manifest = _registered_manifest(tmp_path / "MANIFEST.json")
    out = tmp_path / "run"
    calls: list[str] = []

    def fake_judge(endpoint, model, question, artifact, key, max_tokens):
        calls.append(question)
        return {"score": 2, "evidence": ""}, True

    monkeypatch.setattr(run_holdout, "call_judge", fake_judge)
    monkeypatch.setenv(run_holdout.API_KEY_ENV, "test-only-key")
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--out", str(out), "--force",
        "--variants-manifest", str(manifest), "--endpoint", "http://judge.test/v1",
        "--model", "test-judge",
    ])
    assert run_holdout.main() == 0
    cells_path = out / "cells.jsonl"
    records = [json.loads(line) for line in cells_path.read_text().splitlines()]
    assert len(records) == 252
    required = {"variant", "cell_kind", "started_at_utc", "elapsed_s", "attempt", "artifact_digest"}
    assert all(required <= record.keys() for record in records)
    assert all(run_holdout._audit_complete(record) for record in records)
    first_success = records[1]
    first = records[0]
    first["judge_response"] = {"_error": "transient"}
    first["judge_response_parsed"] = False
    cells_path.write_text("".join(json.dumps(record) + "\n" for record in records))

    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--out", str(out), "--force",
        "--variants-manifest", str(manifest), "--endpoint", "http://judge.test/v1",
        "--model", "test-judge",
    ])
    assert run_holdout.main() == 0
    retried = [json.loads(line) for line in cells_path.read_text().splitlines()]
    by_id = {record["cell_id"]: record for record in retried}
    assert by_id[first["cell_id"]]["attempt"] == 2
    assert by_id[first["cell_id"]]["started_at_utc"] != first["started_at_utc"]
    assert by_id[first_success["cell_id"]]["attempt"] == 1
    assert by_id[first_success["cell_id"]]["started_at_utc"] == first_success["started_at_utc"]
    assert by_id[first_success["cell_id"]]["elapsed_s"] == first_success["elapsed_s"]


# --- 4-way concurrent judge dispatch (2026-09-21, PREREG.md's qwen-next-flash
# addendum: run_holdout.py switched from a sequential per-cell loop to
# ThreadPoolExecutor(max_workers=JUDGE_CONCURRENCY)). These tests check the
# concurrency is real (workers actually overlap), that JUDGE_CONCURRENCY
# governs how much, that concurrent writes to cells.jsonl never interleave
# or duplicate a record, and that resume still submits only pending cells. --

def test_main_runs_judge_calls_concurrently(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Prove workers actually overlap in time, not just that the runner
    accepts a max_workers argument without using it."""
    manifest = _registered_manifest(tmp_path / "MANIFEST.json")
    out = tmp_path / "run"
    lock = threading.Lock()
    state = {"inflight": 0, "max_inflight": 0}

    def fake_judge(endpoint, model, question, artifact, key, max_tokens):
        with lock:
            state["inflight"] += 1
            state["max_inflight"] = max(state["max_inflight"], state["inflight"])
        time.sleep(0.02)
        with lock:
            state["inflight"] -= 1
        return {"score": 2, "evidence": ""}, True

    monkeypatch.setattr(run_holdout, "call_judge", fake_judge)
    monkeypatch.setenv(run_holdout.API_KEY_ENV, "test-only-key")
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--out", str(out), "--force",
        "--variants-manifest", str(manifest), "--endpoint", "http://judge.test/v1",
        "--model", "test-judge",
    ])
    assert run_holdout.main() == 0
    assert state["max_inflight"] >= 2, "judge calls never overlapped -- concurrency isn't actually happening"
    assert state["max_inflight"] <= run_holdout.JUDGE_CONCURRENCY


def test_judge_concurrency_setting_caps_actual_parallelism(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """JUDGE_CONCURRENCY (overridable via HOLDOUT_JUDGE_CONCURRENCY) must be
    the actual ThreadPoolExecutor width, not just a documented default."""
    manifest = _registered_manifest(tmp_path / "MANIFEST.json")
    out = tmp_path / "run"
    lock = threading.Lock()
    state = {"inflight": 0, "max_inflight": 0}

    def fake_judge(endpoint, model, question, artifact, key, max_tokens):
        with lock:
            state["inflight"] += 1
            state["max_inflight"] = max(state["max_inflight"], state["inflight"])
        time.sleep(0.02)
        with lock:
            state["inflight"] -= 1
        return {"score": 2, "evidence": ""}, True

    monkeypatch.setattr(run_holdout, "call_judge", fake_judge)
    monkeypatch.setattr(run_holdout, "JUDGE_CONCURRENCY", 1)
    monkeypatch.setenv(run_holdout.API_KEY_ENV, "test-only-key")
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--out", str(out), "--force",
        "--variants-manifest", str(manifest), "--endpoint", "http://judge.test/v1",
        "--model", "test-judge",
    ])
    assert run_holdout.main() == 0
    assert state["max_inflight"] == 1


def test_main_concurrent_writes_produce_one_well_formed_record_per_cell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Every worker thread's record must land as exactly one intact JSON
    line -- no torn/interleaved writes, no duplicate or missing cells,
    regardless of the (deliberately uneven, so non-submission-order)
    completion order."""
    manifest = _registered_manifest(tmp_path / "MANIFEST.json")
    out = tmp_path / "run"
    counter = {"n": 0}
    counter_lock = threading.Lock()

    def fake_judge(endpoint, model, question, artifact, key, max_tokens):
        with counter_lock:
            counter["n"] += 1
            n = counter["n"]
        time.sleep(0.001 * (n % 5))
        return {"score": n % 4, "evidence": f"cell-{n}"}, True

    monkeypatch.setattr(run_holdout, "call_judge", fake_judge)
    monkeypatch.setenv(run_holdout.API_KEY_ENV, "test-only-key")
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--out", str(out), "--force",
        "--variants-manifest", str(manifest), "--endpoint", "http://judge.test/v1",
        "--model", "test-judge",
    ])
    assert run_holdout.main() == 0
    cells_path = out / "cells.jsonl"
    lines = [line for line in cells_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    # json.loads raises on any torn/interleaved line -- this is the corruption check.
    records = [json.loads(line) for line in lines]
    assert len(records) == 252
    cell_ids = [record["cell_id"] for record in records]
    assert len(cell_ids) == len(set(cell_ids)), "duplicate cell_id -- a cell was scored more than once"
    assert all(record["judge_response_parsed"] for record in records)


def test_resume_submits_only_pending_cells_to_the_concurrent_pool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    manifest = _registered_manifest(tmp_path / "MANIFEST.json")
    out = tmp_path / "run"
    seen: list[str] = []
    seen_lock = threading.Lock()

    def fake_judge(endpoint, model, question, artifact, key, max_tokens):
        with seen_lock:
            seen.append(question)
        return {"score": 2, "evidence": ""}, True

    monkeypatch.setattr(run_holdout, "call_judge", fake_judge)
    monkeypatch.setenv(run_holdout.API_KEY_ENV, "test-only-key")
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--out", str(out), "--force",
        "--variants-manifest", str(manifest), "--endpoint", "http://judge.test/v1",
        "--model", "test-judge",
    ])
    assert run_holdout.main() == 0
    assert len(seen) == 252

    seen.clear()
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--out", str(out), "--force",
        "--variants-manifest", str(manifest), "--endpoint", "http://judge.test/v1",
        "--model", "test-judge",
    ])
    assert run_holdout.main() == 0
    assert seen == [], "resume re-submitted already-scored cells to the concurrent pool"


def test_main_relaxes_min_interval_for_localhost_endpoint_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A self-hosted local judge has no rate limit to protect, so main()
    auto-relaxes the pacing interval to 0.0 when it isn't explicitly set."""
    manifest = _registered_manifest(tmp_path / "MANIFEST.json")
    out = tmp_path / "run"
    monkeypatch.setattr(run_holdout, "call_judge", lambda *a, **k: ({"score": 1, "evidence": ""}, True))
    monkeypatch.setenv(run_holdout.API_KEY_ENV, "test-only-key")
    monkeypatch.delenv(run_holdout.MIN_INTERVAL_ENV, raising=False)
    monkeypatch.setattr(run_holdout, "JUDGE_MIN_REQUEST_INTERVAL_S", 1.0)
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--out", str(out), "--force",
        "--variants-manifest", str(manifest), "--endpoint", "http://localhost:9999/v1",
        "--model", "test-judge",
    ])
    assert run_holdout.main() == 0
    assert run_holdout.JUDGE_MIN_REQUEST_INTERVAL_S == 0.0


def test_main_keeps_min_interval_for_localhost_when_env_var_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    manifest = _registered_manifest(tmp_path / "MANIFEST.json")
    out = tmp_path / "run"
    monkeypatch.setattr(run_holdout, "call_judge", lambda *a, **k: ({"score": 1, "evidence": ""}, True))
    monkeypatch.setenv(run_holdout.API_KEY_ENV, "test-only-key")
    monkeypatch.setenv(run_holdout.MIN_INTERVAL_ENV, "1.0")
    monkeypatch.setattr(run_holdout, "JUDGE_MIN_REQUEST_INTERVAL_S", 1.0)
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--out", str(out), "--force",
        "--variants-manifest", str(manifest), "--endpoint", "http://localhost:9999/v1",
        "--model", "test-judge",
    ])
    assert run_holdout.main() == 0
    assert run_holdout.JUDGE_MIN_REQUEST_INTERVAL_S == 1.0


def test_main_passes_extra_top_level_env_var_through_to_call_judge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    manifest = _registered_manifest(tmp_path / "MANIFEST.json")
    out = tmp_path / "run"
    captured: list[dict | None] = []

    def fake_judge(endpoint, model, question, artifact, key, max_tokens, extra_top_level=None):
        captured.append(extra_top_level)
        return {"score": 1, "evidence": ""}, True

    monkeypatch.setattr(run_holdout, "call_judge", fake_judge)
    monkeypatch.setenv(run_holdout.API_KEY_ENV, "test-only-key")
    monkeypatch.setenv(
        run_holdout.EXTRA_TOP_LEVEL_ENV,
        json.dumps({"chat_template_kwargs": {"enable_thinking": False}}),
    )
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--out", str(out), "--force",
        "--variants-manifest", str(manifest), "--endpoint", "http://judge.test/v1",
        "--model", "test-judge",
    ])
    assert run_holdout.main() == 0
    assert len(captured) == 252
    assert all(c == {"chat_template_kwargs": {"enable_thinking": False}} for c in captured)

    manifest_out = json.loads((out / "MANIFEST.json").read_text())
    assert manifest_out["judge_extra_top_level_fields"] == {"chat_template_kwargs": {"enable_thinking": False}}


def test_main_rejects_invalid_extra_top_level_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manifest = _registered_manifest(tmp_path / "MANIFEST.json")
    out = tmp_path / "run"
    monkeypatch.setattr(run_holdout, "call_judge", lambda *a, **k: pytest.fail("judge called"))
    monkeypatch.setenv(run_holdout.API_KEY_ENV, "test-only-key")
    monkeypatch.setenv(run_holdout.EXTRA_TOP_LEVEL_ENV, "{not valid json")
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--out", str(out), "--force",
        "--variants-manifest", str(manifest), "--endpoint", "http://judge.test/v1",
        "--model", "test-judge",
    ])
    with pytest.raises(SystemExit, match=f"{run_holdout.EXTRA_TOP_LEVEL_ENV} is not valid JSON"):
        run_holdout.main()


def _exc_json(exc: pytest.ExceptionInfo[SystemExit]) -> dict:
    lines = str(exc.value).splitlines()
    assert lines[0] == "REFUSING TO RUN: eligibility preflight failed"
    return json.loads(lines[1])


def test_preflight_collects_all_missing_primary_cells(tmp_path: Path):
    """With a totally unrelated view, every one of the 216 primary cells
    fails ``can_ablate`` -- but the 28 coordinates on the frozen
    ``DOCUMENTED_EXCLUSIONS`` allowlist (real variant ids A-F, same as this
    fixture happens to use) are, by design, routed to
    ``documented_exclusions`` instead of ``missing_grounding`` regardless of
    *why* they currently fail (see ``eligibility_preflight``'s docstring --
    the allowlist is coordinate-based, not reason-based). The other 188
    coordinates are unaffected and still land in ``missing_grounding``,
    which is why this still raises.
    """
    manifest = tmp_path / "unrelated.json"
    manifest.write_text(json.dumps({
        "variants": [{"id": chr(ord("A") + i), "view": "unrelated\n"} for i in range(6)]
    }), encoding="utf-8")
    variants = run_holdout.load_variant_manifest(manifest, require_six=False)
    with pytest.raises(SystemExit) as caught:
        run_holdout.eligibility_preflight(_rows(), variants)
    result = _exc_json(caught)
    assert result["checked_primary_cells"] == 216
    assert len(result["documented_exclusions"]) == 28
    assert {(item["variant"], item["cq_id"]) for item in result["documented_exclusions"]} == run_holdout.DOCUMENTED_EXCLUSION_KEYS
    assert len(result["missing_grounding"]) == 216 - 28
    missing_pairs = {(item["variant"], item["cq_id"]) for item in result["missing_grounding"]}
    assert missing_pairs.isdisjoint(run_holdout.DOCUMENTED_EXCLUSION_KEYS)
    assert len(result["ablated_control_failures"]) == 24
    assert result["missing_grounding"][0]["variant"] == "A"
    assert result["missing_grounding"][0]["cq_id"] == "CQB01"
    assert result["variants"] == ["A", "B", "C", "D", "E", "F"]


def test_preflight_rejects_bare_floating_local_names_for_every_grounding_kind(tmp_path: Path):
    """A bare local name with no identifier context at all -- just the word
    floating in prose, with no ``#fragment``-shaped anchor around it -- must
    never satisfy grounding, for EITHER kind of anchor:

    - a real ontology qname (brick:/rec:/ref:), where demanding the literal
      qname -- not just the bare word -- guards against a false positive
      like "Sensor" matching some unrelated occurrence of the word; and
    - a control-syntax-only grounding (``prop:``/``children:``/
      ``subclassof:``/... -- see ``_grounding_anchors``), where the bare
      local name IS the entire real anchor, but a namespace/case-agnostic
      match still requires it to sit in a short, on-topic identifier
      (``_local_name_present_ci``'s ``#fragment`` + word-count-cap rule) --
      not merely appear as English prose. This is exactly the discipline
      that keeps a term like "campus" mentioned in passing inside an
      unrelated multi-word extraction artifact
      ("standalone-building-manage-entrance-campus-building-ground") from
      counting as a real "brick:Campus"/"rec:Campus" grounding: see the
      commit message / final report for the manual audit that found this
      exact false positive in real chunktograph pipeline output and the
      word-count cap that was added to close it.

    This intentionally supersedes an earlier, narrower version of this test
    that only asserted the first half (bare qname-grounded local names
    fail) and separately asserted that a bare control-syntax local name
    DOES succeed on its own -- that second assertion encoded the exact
    over-permissive, no-context substring matching this fix replaces (see
    ``_local_name_present_ci``/``_anchor_present`` in run_holdout.py).
    """
    rows = _rows()
    lines = []
    for row in rows:
        anchors = run_holdout._grounding_anchors(row["grounding"])
        local_names = [anchor.split(":", 1)[1] if ":" in anchor else anchor for anchor in anchors]
        lines.append("support " + " ".join(local_names))
    view = "\n".join(lines)
    manifest = tmp_path / "local-only.json"
    manifest.write_text(json.dumps({
        "variants": [{"id": chr(ord("A") + i), "view": view} for i in range(6)]
    }), encoding="utf-8")
    variants = run_holdout.load_variant_manifest(manifest, require_six=False)
    with pytest.raises(SystemExit) as caught:
        run_holdout.eligibility_preflight(rows, variants)
    result = _exc_json(caught)
    all_cq_ids = {row["cq_id"] for row in rows}
    # Every CQ -- qname-grounded and control-syntax-only alike -- still
    # fails on floating-word-with-no-identifier-context support, whether it
    # is reported as ``missing_grounding`` or (for the 28 coordinates on the
    # documented allowlist, which this fixture's real A-F variant ids
    # collide with) as ``documented_exclusions`` -- see the comment on
    # ``test_preflight_collects_all_missing_primary_cells`` above for why
    # that collision is expected and correct, not a bug in this fixture.
    failing_pairs = {(item["variant"], item["cq_id"]) for item in result["missing_grounding"]}
    failing_pairs |= {(item["variant"], item["cq_id"]) for item in result["documented_exclusions"]}
    all_variant_cq_pairs = {(variant, cq_id) for variant in "ABCDEF" for cq_id in all_cq_ids}
    assert failing_pairs == all_variant_cq_pairs
    assert len(result["documented_exclusions"]) == 28
    assert len(result["missing_grounding"]) == len(all_cq_ids) * 6 - 28


def _documented_exclusion_manifest(path: Path, *, extra_break: tuple[str, str] | None = None) -> Path:
    """Build a fixture where every (variant, cq_id) primary cell is grounded
    EXCEPT the 28 coordinates on ``run_holdout.DOCUMENTED_EXCLUSION_KEYS``
    (deliberately omitted, one variant-specific view per real variant id
    A-F) plus, optionally, one additional ``extra_break`` coordinate that is
    NOT on that allowlist -- used to prove the hard-refusal regression
    guard still fires for anything not explicitly documented.
    """
    rows = _rows()
    variants_payload = []
    for variant_id in ("A", "B", "C", "D", "E", "F"):
        lines = []
        for row in rows:
            cq_id = row["cq_id"]
            if (variant_id, cq_id) in run_holdout.DOCUMENTED_EXCLUSION_KEYS:
                continue
            if extra_break is not None and (variant_id, cq_id) == extra_break:
                continue
            lines.append(_fixture_view_line(row))
        variants_payload.append({"id": variant_id, "view": "\n".join(lines)})
    path.write_text(json.dumps({"variants": variants_payload}), encoding="utf-8")
    return path


def test_documented_exclusions_pass_preflight_and_shrink_the_primary_pool(tmp_path: Path):
    """The 28 cells on the frozen allowlist (PREREG.md [2026-09-21]
    addendum) are excluded from ``missing_grounding`` (so preflight does not
    hard-refuse on them alone), excluded from the ablated/preserved control
    source pool, and excluded from the ``"primary"``-kind cells the
    confirmatory judge is actually asked -- 216 -> 188.
    """
    manifest = _documented_exclusion_manifest(tmp_path / "documented.json")
    variants = run_holdout.load_variant_manifest(manifest, require_six=False)
    result = run_holdout.eligibility_preflight(_rows(), variants)  # must not raise
    assert result["missing_grounding"] == []
    assert result["checked_primary_cells"] == 216
    assert result["eligible_primary_cells"] == 216 - 28
    assert len(result["documented_exclusions"]) == 28
    assert {(e["variant"], e["cq_id"]) for e in result["documented_exclusions"]} == run_holdout.DOCUMENTED_EXCLUSION_KEYS
    assert all(e["documented_exclusion_reason"] for e in result["documented_exclusions"])

    plan = run_holdout.build_cell_plan(_rows(), variants, eligibility=result)
    assert sum(c["cell_kind"] == "primary" for c in plan) == 216 - 28
    assert sum(c["cell_kind"] == "ablated_control" for c in plan) == 24
    assert sum(c["cell_kind"] == "preserved_control" for c in plan) == 12
    assert len(plan) == (216 - 28) + 24 + 12
    primary_pairs = {(c["variant"], c["cq_id"]) for c in plan if c["cell_kind"] == "primary"}
    assert primary_pairs.isdisjoint(run_holdout.DOCUMENTED_EXCLUSION_KEYS)
    ablated_pairs = {(c["variant"], c["cq_id"]) for c in plan if c["cell_kind"] == "ablated_control"}
    assert ablated_pairs.isdisjoint(run_holdout.DOCUMENTED_EXCLUSION_KEYS)


def test_undocumented_missing_grounding_still_hard_refuses(tmp_path: Path):
    """Regression guard: a missing-grounding cell that is NOT one of the 28
    documented coordinates must still hard-refuse the run, even when all 28
    documented coordinates are simultaneously missing and correctly
    tolerated. The allowlist must never silently widen to cover new
    breakage.
    """
    # CQB02's anchors do not overlap any other CQ's fixture line in this
    # bank (verified: no other row's grounding text or #fragment shares an
    # anchor with CQB02's), so omitting only its own line genuinely removes
    # its grounding from the whole view -- unlike e.g. CQB01 ("Sensor"),
    # whose bare local name also appears inside CQB07/CQB11's unrelated
    # control-syntax groundings and so stays coincidentally "grounded" by
    # their lines even after CQB01's own line is dropped.
    manifest = _documented_exclusion_manifest(
        tmp_path / "documented_plus_new_break.json", extra_break=("B", "CQB02"),
    )
    variants = run_holdout.load_variant_manifest(manifest, require_six=False)
    with pytest.raises(SystemExit) as caught:
        run_holdout.eligibility_preflight(_rows(), variants)
    result = _exc_json(caught)
    assert len(result["documented_exclusions"]) == 28
    assert [(item["variant"], item["cq_id"]) for item in result["missing_grounding"]] == [("B", "CQB02")]


def test_preflight_accepts_short_iri_fragment_local_names_namespace_and_case_agnostic(tmp_path: Path):
    """The namespace-/case-agnostic fix: giving every anchor (both a real
    qname's bare local half, and an already-bare control-syntax anchor) a
    short ``#fragment``-shaped, lowercased home -- exactly how the real
    chunktograph pipeline renders every class/property/individual local
    name, under its own ``ct:`` namespace rather than the bank's authoring
    prefix, and always lowercase -- satisfies grounding for every CQ in the
    bank, with zero false positives reported.
    """
    rows = _rows()
    view = "\n".join(_fixture_view_line(row) for row in rows)
    manifest = tmp_path / "fragment-local.json"
    manifest.write_text(json.dumps({
        "variants": [{"id": chr(ord("A") + i), "view": view} for i in range(6)]
    }), encoding="utf-8")
    variants = run_holdout.load_variant_manifest(manifest, require_six=False)
    # No SystemExit: every row is eligible.
    result = run_holdout.eligibility_preflight(rows, variants)
    assert result["missing_grounding"] == []
    assert result["false_positive_local_name_matches"] == []


def test_qualified_anchor_requires_an_exact_token():
    cases = [
        ("brick:Sensor", "brick:Sensor", True),
        ("brick:Sensor.", "brick:Sensor", True),
        ("brick:Sensor,", "brick:Sensor", True),
        ("brick:Sensor);", "brick:Sensor", True),
        ("x(brick:Sensor),", "brick:Sensor", True),
        ("brick:Sensor:Extra", "brick:Sensor", False),
        ("brick:Sensor.v2", "brick:Sensor", False),
        ("brick:Sensor-extra", "brick:Sensor", False),
        ("brick:Sensor..", "brick:Sensor", False),
        ("brick:Sensor.-v2", "brick:Sensor", False),
        ("xbrick:Sensor", "brick:Sensor", False),
        ("foo:brick:Sensor", "brick:Sensor", False),
        ("brick:SensorSuffix", "brick:Sensor", False),
        ("brick:Sensor_2", "brick:Sensor", False),
        ("brick:Sensor.v2", "brick:Sensor.v2", True),
        ("brick:Sensor-extra,", "brick:Sensor-extra", True),
        ("subclassof:X>Y.", "subclassof:X>Y", True),
        ("subclassof:X>Y>Z", "subclassof:X>Y", False),
        ("inverse:X~Y!", "inverse:X~Y", True),
        ("inverse:X~Y~Z", "inverse:X~Y", False),
        ("children:X", "children:X", True),
        ("children:X>Y", "children:X", False),
    ]
    for line, anchor, expected in cases:
        assert run_holdout._qualified_anchor_present(line, anchor) is expected


def test_preflight_requires_complete_qualified_grounding():
    """Post namespace/case-agnostic fix: a qualified (real-prefix) anchor is
    satisfied by either the literal exact qname OR a short ``#fragment``
    local-name match (case-insensitive); a control-syntax-only anchor -- its
    bare local name is already the whole real anchor -- is satisfied ONLY by
    the same short ``#fragment`` match, never by the word floating in plain
    prose with no identifier context (that bare-prose case is exactly the
    false-positive-prone substring matching this fix replaces -- see
    ``_local_name_present_ci`` in run_holdout.py and the CQB05/"Campus"
    false positive documented in the commit message / final report).
    """
    rows = {row["cq_id"]: row for row in _rows()}
    cases = [
        # CQB01 is qname-grounded (skos:definition brick:Sensor).
        ("CQB01", [
            ("Sensor", False),                # bare word, no identifier context
            ("brick:Sensor", True),            # literal exact qname
            ("brick:Sensor Sensor", True),
            ("notbrick:Sensor", False),         # embedded in a larger qname-like token
            ("brick:SensorSuffix", False),      # alnum continuation suffix
            ("#brick-sensor", True),            # chunktograph-shaped: own namespace, lowercase
            ("#SENSOR", True),                  # case-folded, bare fragment
            ("#sensors", False),                # different, plural token
            ("#ifcFileLocation", False),        # unrelated camelCase token (no boundary at all)
            # A real chunktograph extraction artifact: the whole garbled
            # sentence became one pseudo class name, "sensor" merely swept
            # up inside it -- rejected by the short-word-run cap exactly
            # like the real "campus" false positive it is modeled on.
            ("#standalone-building-manage-entrance-sensor-building-ground", False),
        ]),
        # CQB07/CQB08/CQB13 are control-syntax-only groundings (subclassof:/
        # children:/inverse:). The renderer never emits "subclassof:"/
        # "children:"/"inverse:" literally -- those are bank-internal control
        # prefixes, not namespaces -- so the bare local term(s) are the whole
        # real anchor (see _grounding_anchors). They still require a short
        # #fragment identifier context, not bare floating prose -- otherwise
        # any incidental appearance of the word anywhere in the artifact
        # would (wrongly) ground the CQ.
        ("CQB07", [
            ("Sensor Point", False),
            ("#Sensor #Point", True),
            ("#sensor #point", True),      # case-folded
            ("#Point", False),             # only half the requirement present
        ]),
        ("CQB08", [
            ("Point", False),
            ("#Point", True),
            ("#point", True),
            ("#points", False),
        ]),
        ("CQB13", [
            ("hasPoint isPointOf", False),
            ("#hasPoint #isPointOf", True),
            ("#haspoint #ispointof", True),
        ]),
    ]
    for cq_id, views in cases:
        row = rows[cq_id]
        for view, expected in views:
            assert run_holdout._grounding_match_info(view, row)["can_ablate"] is expected, (cq_id, view)

    local_only = {"grounding": "Sensor"}
    assert run_holdout._grounding_match_info("#Sensor", local_only)["can_ablate"]
    assert not run_holdout._grounding_match_info("Sensor", local_only)["can_ablate"]
    assert not run_holdout._grounding_match_info("unrelated", local_only)["can_ablate"]


def test_substring_matcher_and_ablation_remain_unchanged():
    row = next(row for row in _rows() if row["cq_id"] == "CQB01")
    view = "notbrick:Sensor\nbrick:SensorSuffix\nbrick:Sensor\nkeep\n"
    # The raw, deliberately-naive ``_matching_line_numbers`` predicate itself
    # is unchanged and still over-matches on a plain substring basis -- this
    # is exactly why real ablation no longer calls it directly (see below).
    assert run_holdout._matching_line_numbers(view, ["brick:Sensor"]) == [1, 2, 3]
    # ``ablate_rendered_view`` now goes through
    # ``_matching_line_numbers_namespace_agnostic``, which rejects
    # "notbrick:Sensor" (embedded in a larger qname-like token) and
    # "brick:SensorSuffix" (has an alnum-continuation suffix) exactly as
    # ``_qualified_anchor_present``/``_local_name_present_ci`` do -- so only
    # the genuinely exact "brick:Sensor" occurrence on line 3 is removed.
    # This is a deliberate precision improvement over the old naive-substring
    # ablation (which used to over-strip both false-positive lines too,
    # silently removing unrelated content from an "ablated control" cell)
    # made while fixing the same over-strictness bug for real chunktograph
    # pipeline artifacts (see run_holdout.py's namespace/case-agnostic
    # grounding-anchor matching).
    assert run_holdout.ablate_rendered_view(view, row) == "notbrick:Sensor\nbrick:SensorSuffix\nkeep\n"


def test_preflight_result_is_deterministic_and_plan_digests_are_stable(tmp_path: Path):
    manifest = _manifest(tmp_path / "MANIFEST.json")
    variants = run_holdout.load_variant_manifest(manifest, require_six=False)
    first = run_holdout.eligibility_preflight(_rows(), variants)
    second = run_holdout.eligibility_preflight(_rows(), variants)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    plan = run_holdout.build_cell_plan(_rows(), variants, eligibility=first)
    assert all(cell["artifact_digest"] == run_holdout.hashlib.sha256(cell["artifact"].encode()).hexdigest()
               for cell in plan)
    assert [variant.view for variant in variants] == [variant.view for variant in run_holdout.load_variant_manifest(manifest, require_six=False)]


def test_main_refuses_preflight_before_api_key_or_judge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    manifest = _registered_manifest(tmp_path / "unrelated.json", view="unrelated")
    monkeypatch.delenv(run_holdout.API_KEY_ENV, raising=False)
    monkeypatch.setattr(run_holdout, "call_judge", lambda *args: pytest.fail("judge called"))
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--out", str(tmp_path / "run"),
        "--variants-manifest", str(manifest), "--endpoint", "http://judge.test/v1",
        "--model", "test-judge",
    ])
    with pytest.raises(SystemExit) as caught:
        run_holdout.main()
    assert str(caught.value).startswith("REFUSING TO RUN: eligibility preflight failed\n{")
    assert run_holdout.API_KEY_ENV not in str(caught.value)


def test_registered_graph_digest_mismatch_fails_closed(tmp_path: Path):
    manifest = _registered_manifest(tmp_path / "MANIFEST.json")
    (tmp_path / "graph.ttl").write_text("changed\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="graph SHA256 mismatch"):
        run_holdout.load_variant_manifest(manifest)


def test_registered_rendered_view_digest_mismatch_fails_closed(tmp_path: Path):
    manifest = _registered_manifest(tmp_path / "MANIFEST.json")
    (tmp_path / "rendered_view.txt").write_text("changed\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="rendered view SHA256 mismatch"):
        run_holdout.load_variant_manifest(manifest)


@pytest.mark.parametrize("missing_field, expected", [
    ("graph_path", "graph file not found"),
    ("rendered_view_path", "rendered view not found"),
])
def test_registered_missing_artifact_path_fails_closed(
    tmp_path: Path, missing_field: str, expected: str
):
    manifest = _registered_manifest(tmp_path / "MANIFEST.json")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["variants"][0][missing_field] = "does-not-exist"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SystemExit, match=expected):
        run_holdout.load_variant_manifest(manifest)


def test_path_shaped_view_loads_and_explicit_path_wins(tmp_path: Path):
    manifest = _registered_manifest(tmp_path / "MANIFEST.json")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    explicit = tmp_path / "explicit.txt"
    fallback = tmp_path / "fallback.txt"
    explicit.write_text("explicit\n", encoding="utf-8")
    fallback.write_text("fallback\n", encoding="utf-8")
    payload["variants"][0].pop("rendered_view_path")
    payload["variants"][0]["view"] = explicit.name
    payload["variants"][0]["rendered_view_sha256"] = hashlib.sha256(explicit.read_bytes()).hexdigest()
    payload["variants"][1]["view"] = fallback.name
    payload["variants"][1]["rendered_view_path"] = explicit.name
    payload["variants"][1]["rendered_view_sha256"] = hashlib.sha256(explicit.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    variants = run_holdout.load_variant_manifest(manifest)
    assert variants[0].view == "explicit\n"
    assert variants[1].view == "explicit\n"


def test_inline_fixture_remains_supported_when_six_artifacts_are_not_required(tmp_path: Path):
    manifest = _manifest(tmp_path / "MANIFEST.json", count=1)
    variants = run_holdout.load_variant_manifest(manifest, require_six=False)
    assert variants[0].view.startswith("support ")
    assert variants[0].source == "inline"


# --- call_judge network-layer retry/backoff (added after the real Gemini
# 3.6-flash run hit HTTP 429 on 158/224 cells with no retry logic) ---------


class _FakeResponse:
    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc_info) -> None:
        return None


def _http_error(code: int, retry_after: str | None = None) -> "run_holdout.urllib.error.HTTPError":
    import email.message

    hdrs = email.message.Message()
    if retry_after is not None:
        hdrs["Retry-After"] = retry_after
    return run_holdout.urllib.error.HTTPError(
        url="https://example.invalid/chat/completions",
        code=code,
        msg="error",
        hdrs=hdrs,
        fp=None,
    )


def test_call_judge_retries_429_then_succeeds(monkeypatch: pytest.MonkeyPatch):
    calls = {"n": 0}
    sleeps: list[float] = []

    def fake_urlopen(request, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _http_error(429, retry_after="0.01")
        return _FakeResponse({"choices": [{"message": {"content": json.dumps({"score": 2})}}]})

    monkeypatch.setattr(run_holdout.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(run_holdout.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(run_holdout, "JUDGE_MIN_REQUEST_INTERVAL_S", 0.0)

    response, parsed = run_holdout.call_judge(
        "https://example.invalid", "m", "q", "a", "key", 1024
    )

    assert parsed is True
    assert response == {"score": 2}
    assert calls["n"] == 3
    # Two 429s were retried (Retry-After honored), pacing sleeps are also 0s.
    assert sleeps.count(0.01) == 2


def test_call_judge_exhausts_retries_and_records_error(monkeypatch: pytest.MonkeyPatch):
    def fake_urlopen(request, timeout=None):
        raise _http_error(429)

    monkeypatch.setattr(run_holdout.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(run_holdout.time, "sleep", lambda s: None)
    monkeypatch.setattr(run_holdout, "JUDGE_MIN_REQUEST_INTERVAL_S", 0.0)
    monkeypatch.setattr(run_holdout, "JUDGE_MAX_RETRIES", 2)

    response, parsed = run_holdout.call_judge(
        "https://example.invalid", "m", "q", "a", "key", 1024
    )

    assert parsed is False
    assert "429" in response["_error"]


def test_call_judge_does_not_retry_non_429_http_errors(monkeypatch: pytest.MonkeyPatch):
    calls = {"n": 0}

    def fake_urlopen(request, timeout=None):
        calls["n"] += 1
        raise _http_error(500)

    monkeypatch.setattr(run_holdout.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(run_holdout.time, "sleep", lambda s: pytest.fail("should not sleep/retry on non-429"))
    monkeypatch.setattr(run_holdout, "JUDGE_MIN_REQUEST_INTERVAL_S", 0.0)

    response, parsed = run_holdout.call_judge(
        "https://example.invalid", "m", "q", "a", "key", 1024
    )

    assert parsed is False
    assert calls["n"] == 1
    assert "500" in response["_error"]


def test_pace_judge_request_sleeps_for_remaining_interval(monkeypatch: pytest.MonkeyPatch):
    times = iter([100.2, 100.2])
    monkeypatch.setattr(run_holdout.time, "monotonic", lambda: next(times))
    sleeps: list[float] = []
    monkeypatch.setattr(run_holdout.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(run_holdout, "JUDGE_MIN_REQUEST_INTERVAL_S", 1.0)
    monkeypatch.setattr(run_holdout, "_last_judge_request_mono", 100.0)

    run_holdout._pace_judge_request()

    assert sleeps == [pytest.approx(0.8)]


# --- extra_top_level request-body merge (2026-09-21, qwen-next-flash addendum:
# vLLM ignores fields nested under a top-level "extra_body" key -- unlike
# Gemini's translator -- so chat_template_kwargs must be merged as genuine
# top-level request fields; this is a distinct code path from extra_body). ---

def test_call_judge_merges_extra_top_level_fields_into_request_body(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}

    def fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data)
        return _FakeResponse({"choices": [{"message": {"content": json.dumps({"score": 1})}}]})

    monkeypatch.setattr(run_holdout.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(run_holdout, "JUDGE_MIN_REQUEST_INTERVAL_S", 0.0)

    response, parsed = run_holdout.call_judge(
        "https://example.invalid", "m", "q", "a", "key", 1024,
        extra_top_level={"chat_template_kwargs": {"enable_thinking": False}},
    )

    assert parsed is True
    assert "extra_body" not in captured["body"], "extra_top_level must not be nested under extra_body"
    assert captured["body"]["chat_template_kwargs"] == {"enable_thinking": False}
    # Untouched: the registered decoding parameters stay exactly as before.
    assert captured["body"]["temperature"] == 0.0
    assert captured["body"]["max_tokens"] == 1024
    assert captured["body"]["response_format"] == {"type": "json_object"}


def test_call_judge_extra_body_and_extra_top_level_are_independent(monkeypatch: pytest.MonkeyPatch):
    """Both mechanisms can be set at once (e.g. a future provider needing
    both shapes) without one clobbering the other."""
    captured: dict = {}

    def fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data)
        return _FakeResponse({"choices": [{"message": {"content": json.dumps({"score": 1})}}]})

    monkeypatch.setattr(run_holdout.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(run_holdout, "JUDGE_MIN_REQUEST_INTERVAL_S", 0.0)

    run_holdout.call_judge(
        "https://example.invalid", "m", "q", "a", "key", 1024,
        extra_body={"google": {"thinking_config": {"thinking_level": "minimal"}}},
        extra_top_level={"chat_template_kwargs": {"enable_thinking": False}},
    )

    assert captured["body"]["extra_body"] == {"google": {"thinking_config": {"thinking_level": "minimal"}}}
    assert captured["body"]["chat_template_kwargs"] == {"enable_thinking": False}


# --- Repo-relative manifest paths (2026-09-25): run_holdout.py used to write
# str(args.variants_manifest.resolve()) verbatim into MANIFEST.json, so every
# committed run manifest baked in whichever worktree produced it (a stray
# .claude/worktrees/<session-id>/... prefix that means nothing once the
# worktree is gone). _relative() now records a repo-relative POSIX path when
# the file is inside this repo, and falls back to the absolute path
# otherwise -- mirroring build_repair_candidate.py's REPO/_relative(). ---

def test_relative_returns_repo_relative_posix_path_when_inside_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(run_holdout, "REPO", tmp_path)
    nested = tmp_path / "a" / "b" / "manifest.json"
    nested.parent.mkdir(parents=True)
    nested.write_text("{}", encoding="utf-8")
    assert run_holdout._relative(nested) == "a/b/manifest.json"


def test_relative_falls_back_to_absolute_path_when_outside_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    monkeypatch.setattr(run_holdout, "REPO", repo_dir)
    outside = tmp_path / "elsewhere" / "manifest.json"
    outside.parent.mkdir(parents=True)
    outside.write_text("{}", encoding="utf-8")
    assert run_holdout._relative(outside) == str(outside.resolve())


def test_dry_run_manifest_variant_manifest_field_is_repo_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The dry-run MANIFEST.json (build() around the --dry-run branch) must
    route its variant_manifest field through _relative(), not a raw
    str(...resolve())."""
    monkeypatch.setattr(run_holdout, "REPO", tmp_path)
    manifest = _manifest(tmp_path / "variants_manifest.json")
    out = tmp_path / "dry"
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--dry-run", "--out", str(out),
        "--variants-manifest", str(manifest),
    ])
    assert run_holdout.main() == 0
    manifest_out = json.loads((out / "MANIFEST.json").read_text())
    assert manifest_out["variant_manifest"] == "variants_manifest.json"


def test_full_run_manifest_variant_manifest_field_is_repo_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Same guarantee for the formal/smoke run's MANIFEST.json (the second
    call site, written both before and after the judge dispatch loop)."""
    monkeypatch.setattr(run_holdout, "REPO", tmp_path)
    manifest = _registered_manifest(tmp_path / "variants_manifest.json")
    out = tmp_path / "run"
    monkeypatch.setattr(run_holdout, "call_judge", lambda *a, **k: ({"score": 1, "evidence": ""}, True))
    monkeypatch.setenv(run_holdout.API_KEY_ENV, "test-only-key")
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--out", str(out), "--force",
        "--variants-manifest", str(manifest), "--endpoint", "http://judge.test/v1",
        "--model", "test-judge",
    ])
    assert run_holdout.main() == 0
    manifest_out = json.loads((out / "MANIFEST.json").read_text())
    assert manifest_out["variant_manifest"] == "variants_manifest.json"


def test_full_run_manifest_variant_manifest_field_falls_back_to_absolute_outside_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """No REPO monkeypatch here: pytest's tmp_path is genuinely outside the
    real repo checkout, so the field must stay the resolved absolute path
    (exercising _relative()'s except ValueError fallback for real)."""
    manifest = _registered_manifest(tmp_path / "variants_manifest.json")
    out = tmp_path / "run"
    monkeypatch.setattr(run_holdout, "call_judge", lambda *a, **k: ({"score": 1, "evidence": ""}, True))
    monkeypatch.setenv(run_holdout.API_KEY_ENV, "test-only-key")
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--out", str(out), "--force",
        "--variants-manifest", str(manifest), "--endpoint", "http://judge.test/v1",
        "--model", "test-judge",
    ])
    assert run_holdout.main() == 0
    manifest_out = json.loads((out / "MANIFEST.json").read_text())
    assert manifest_out["variant_manifest"] == str(manifest.resolve())


# --- preserved-control omission for domains without a frozen paraphrase file
# (PREREG.md addendum 15 §15.2: "preserved control을 만들 수 없으면 그 종류는
# 계획에서 빼고 이유를 manifest에 적는다" -- if frozen paraphrases for the domain
# do not exist, omit that control kind from the plan and record the reason).
# Reproduced pre-fix: run_holdout.py --domain iof --dry-run died with
# AttributeError: 'NoneType' object has no attribute 'exists' inside
# _paraphrases(), because iof.toml carries no [bank].paraphrases entry.


IOF_BANK = run_holdout.ACCESS / "bank" / "iof" / "cq_bank_iof_v1.csv"


def _iof_rows() -> list[dict]:
    with IOF_BANK.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_plan_omits_preserved_controls_when_paraphrases_path_is_none(tmp_path: Path):
    """Unit: paraphrases_path=None -> eligibility_preflight records the §15.2
    omission instead of crashing, and build_cell_plan places zero
    preserved_control cells while primary + ablated controls are unaffected."""
    manifest = _manifest(tmp_path / "MANIFEST.json")
    variants = run_holdout.load_variant_manifest(manifest, require_six=False)
    eligibility = run_holdout.eligibility_preflight(_rows(), variants, 20260913, None)
    reason = eligibility["preserved_controls_omitted_reason"]
    assert reason is not None
    assert "no frozen paraphrase file" in reason and "15.2" in reason
    assert eligibility["preserved_sources"] == []
    assert eligibility["preserved_candidates"] == 0
    assert eligibility["preserved_control_failures"] == []
    plan = run_holdout.build_cell_plan(_rows(), variants, 20260913, None, eligibility)
    assert sum(cell["cell_kind"] == "preserved_control" for cell in plan) == 0
    assert sum(cell["cell_kind"] == "primary" for cell in plan) == 216
    assert sum(cell["cell_kind"] == "ablated_control" for cell in plan) == 24
    assert len(plan) == 240


def test_registered_paraphrase_path_always_has_no_omission(tmp_path: Path):
    """No-op guard for the brick pin: with a registered paraphrase file the
    eligibility result carries no omission reason and the full 252-cell plan
    (12 preserved controls) is unchanged."""
    manifest = _manifest(tmp_path / "MANIFEST.json")
    variants = run_holdout.load_variant_manifest(manifest, require_six=False)
    eligibility = run_holdout.eligibility_preflight(_rows(), variants, 20260913)
    assert eligibility["preserved_controls_omitted_reason"] is None
    plan = run_holdout.build_cell_plan(_rows(), variants, 20260913, run_holdout.PARAPHRASE_PATH, eligibility)
    assert sum(cell["cell_kind"] == "preserved_control" for cell in plan) == 12
    assert len(plan) == 252


def test_given_but_missing_paraphrase_file_still_refuses(tmp_path: Path):
    """Omission applies ONLY to an unregistered (None) path. A domain that
    registers a paraphrase file which is then missing must keep failing the
    preflight (paraphrases_unavailable), exactly as before §15.2 omission."""
    manifest = _manifest(tmp_path / "MANIFEST.json")
    variants = run_holdout.load_variant_manifest(manifest, require_six=False)
    with pytest.raises(SystemExit, match="eligibility preflight failed"):
        run_holdout.eligibility_preflight(_rows(), variants, 20260913, tmp_path / "absent.csv")


def test_iof_dry_run_completes_and_records_preserved_omission_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Wiring: the full `--domain iof --dry-run --out tmp` path (real frozen
    iof bank, fake variant manifest built from the iof rows per the existing
    fixture idiom -- never touching the real variants_iof/) no longer dies
    with the paraphrase AttributeError; its MANIFEST.json carries
    preserved_controls_omitted_reason naming domain 'iof' and addendum 15
    §15.2, and CELL_PLAN.json has zero preserved_control cells."""
    rows = _iof_rows()
    view = "\n".join(_fixture_view_line(row) for row in rows)
    manifest = tmp_path / "variants_manifest.json"
    manifest.write_text(json.dumps({
        "variants": [{"id": f"V{i}", "view": view} for i in range(6)]
    }), encoding="utf-8")
    out = tmp_path / "iof-dry"
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--domain", "iof", "--dry-run", "--out", str(out),
        "--variants-manifest", str(manifest),
    ])
    assert run_holdout.main() == 0
    plan = json.loads((out / "CELL_PLAN.json").read_text(encoding="utf-8"))
    assert sum(cell["cell_kind"] == "preserved_control" for cell in plan) == 0
    manifest_out = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest_out["preserved_control_cells"] == 0
    assert manifest_out["ablated_control_cells"] == 24
    assert manifest_out["primary_cells"] == manifest_out["planned_cells"] - 24 - 0
    reason = manifest_out["preserved_controls_omitted_reason"]
    assert reason is not None
    assert "'iof'" in reason and "no frozen paraphrase file" in reason and "15.2" in reason


# --- §15.2 per-domain auto-exclusion of mechanically grounding-absent cells.
# PREREG.md addendum 15 §15.2 (frozen): "제외는 Brick과 같은 규칙으로 셀 단위로
# 적용된다 -- 그 변이의 뷰에 grounding 앵커가 없어 ablation이 불가능한 셀이
# 제외된다. 제외된 셀은 사유와 함께 manifest에 기록되며..." The dry-run rehearsal
# against the REAL IOF variant views (<tmp>/opencode/rehearsal4-pkg, refusal dump
# <tmp>/opencode/rehearsal4-full.log) showed the strict preflight refusing the
# run: 178 of 216 cells mechanically grounding-absent (missing_grounding /
# missing_qualified_grounding -- the anchor token is simply not in that
# variant's rendered view), plus 19 ablated_control_failures from controls
# sampled out of the ineligible pool. The [eligibility]
# auto_exclude_grounding_ineligible flag (domains/iof.toml; brick.toml unset ->
# strict, byte-identical behaviour) turns EXACTLY that mechanical category into
# recorded exclusions and samples controls from eligible cells only.
# Reproduced pre-fix: SystemExit "REFUSING TO RUN: eligibility preflight failed".

REHEARSAL_PKG = Path("<tmp>/opencode/rehearsal4-pkg")
GROUNDING_ABSENT_REASON = "grounding_anchor_absent_from_view per addendum 15 §15.2"


def _iof_view(rows: list[dict], missing_cq_ids: set[str]) -> str:
    return "\n".join(_fixture_view_line(row) for row in rows if row["cq_id"] not in missing_cq_ids)


def _iof_inline_manifest(path: Path, missing_by_variant: dict[str, set[str]]) -> Path:
    rows = _iof_rows()
    path.write_text(json.dumps({
        "variants": [{"id": vid, "view": _iof_view(rows, missing)}
                     for vid, missing in missing_by_variant.items()]
    }), encoding="utf-8")
    return path


def _iof_ineligible_ids(rows: list[dict], variants: list) -> set[str]:
    """Truth by construction: cells whose grounding anchor genuinely is not
    ablatable in that variant's view, per the UNCHANGED matcher."""
    return {
        f"primary:{variant.variant_id}:{row['cq_id']}"
        for variant in variants for row in rows
        if not run_holdout._grounding_match_info(variant.view, row)["can_ablate"]
    }


def _iof_registered_manifest(path: Path, missing_by_variant: dict[str, set[str]]) -> Path:
    """Six-variant artifact manifest (graph + rendered view files with their
    digests), the shape a formal --domain iof run requires."""
    rows = _iof_rows()
    entries = []
    for vid, missing in missing_by_variant.items():
        graph = path.parent / f"graph_{vid}.ttl"
        rendered = path.parent / f"rendered_{vid}.txt"
        graph.write_text("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n", encoding="utf-8")
        rendered.write_text(_iof_view(rows, missing), encoding="utf-8")
        entries.append({
            "id": vid,
            "graph_path": graph.name,
            "rendered_view_path": rendered.name,
            "graph_sha256": hashlib.sha256(graph.read_bytes()).hexdigest(),
            "rendered_view_sha256": hashlib.sha256(rendered.read_bytes()).hexdigest(),
        })
    path.write_text(json.dumps({"variants": entries}), encoding="utf-8")
    return path


def test_flag_on_preflight_excludes_grounding_absent_cells_instead_of_refusing(tmp_path: Path):
    """Flag ON: cells failing EXACTLY the mechanical grounding-absence category
    become recorded exclusions (no abort), derived only from the check itself,
    with the §15.2 reason; nothing lands in missing_grounding."""
    rows = _iof_rows()
    manifest = _iof_inline_manifest(
        tmp_path / "M.json",
        {"A": {"CQI01", "CQI02"}, "B": {"CQI03"}} | {vid: set() for vid in "CDEF"})
    variants = run_holdout.load_variant_manifest(manifest, require_six=False)
    expected = _iof_ineligible_ids(rows, variants)
    assert expected, "fixture must actually produce grounding-absent cells"
    eligibility = run_holdout.eligibility_preflight(
        rows, variants, 20260913, None, {}, auto_exclude_grounding_ineligible=True)
    assert eligibility["missing_grounding"] == []
    assert eligibility["documented_exclusions"] == []
    excluded = eligibility["auto_exclusions"]
    assert {entry["cell_id"] for entry in excluded} == expected
    for entry in excluded:
        assert set(entry) == {
            "cell_id", "variant", "cq_id", "missing_required_grounding_anchors", "reason"}
        assert entry["reason"] == GROUNDING_ABSENT_REASON
        assert isinstance(entry["missing_required_grounding_anchors"], list)
    counts = eligibility["eligibility_counts"]
    assert counts["checked_primary_cells"] == 6 * 36
    assert counts["excluded_grounding_absent"] == len(expected)
    assert counts["eligible_primary_cells"] == 6 * 36 - len(expected)
    # the eligibility itself must never hand-author an exclusion: every entry
    # traces to a can_ablate=false diagnostic from the untouched matcher
    for entry in excluded:
        diagnostic = next(d for d in eligibility["primary_cells"] if d["cell_id"] == entry["cell_id"])
        assert not diagnostic["can_ablate"]


def test_flag_off_preflight_still_refuses_grounding_absent_cells(tmp_path: Path):
    """Flag OFF (the default, i.e. brick semantics): any ineligible
    non-excluded cell still aborts the run exactly as before this change."""
    rows = _iof_rows()
    manifest = _iof_inline_manifest(tmp_path / "M.json", {"A": {"CQI01"}})
    variants = run_holdout.load_variant_manifest(manifest, require_six=False)
    with pytest.raises(SystemExit) as raised:
        run_holdout.eligibility_preflight(rows, variants, 20260913, None, {})
    message = str(raised.value)
    assert "eligibility preflight failed" in message
    assert "primary:A:CQI01" in message


def test_flag_on_samples_ablated_controls_only_from_eligible_cells(tmp_path: Path):
    """Flag ON: the 24 registered ablated controls are drawn ONLY from
    eligible primary cells (this is the 19-control-failure fix) and the plan
    carries eligible primaries + 24 controls, no preserved kind."""
    rows = _iof_rows()
    dropped = {row["cq_id"] for row in rows[:20]}
    missing = {vid: set(dropped) for vid in "ABCDE"} | {"F": set()}
    manifest = _iof_inline_manifest(tmp_path / "M.json", missing)
    variants = run_holdout.load_variant_manifest(manifest, require_six=False)
    eligibility = run_holdout.eligibility_preflight(
        rows, variants, 20260913, None, {}, auto_exclude_grounding_ineligible=True)
    excluded_ids = {entry["cell_id"] for entry in eligibility["auto_exclusions"]}
    assert excluded_ids, "fixture must produce exclusions"
    assert eligibility["ablated_control_failures"] == []
    assert eligibility["preserved_controls_omitted_reason"] is not None
    ablated = eligibility["ablated_sources"]
    assert len(ablated) == run_holdout.REGISTERED_ABLATED == 24
    assert len(set(ablated)) == 24
    assert set(ablated) & excluded_ids == set()
    plan = run_holdout.build_cell_plan(rows, variants, 20260913, None, eligibility, {})
    primary_cells = [cell for cell in plan if cell["cell_kind"] == "primary"]
    assert {run_holdout.cell_key(cell) for cell in primary_cells} & excluded_ids == set()
    assert len(primary_cells) == eligibility["eligibility_counts"]["eligible_primary_cells"]
    assert sum(cell["cell_kind"] == "ablated_control" for cell in plan) == 24
    assert sum(cell["cell_kind"] == "preserved_control" for cell in plan) == 0
    assert len(plan) == len(primary_cells) + 24


def test_flag_on_still_refuses_when_eligible_pool_falls_below_registered_controls(tmp_path: Path):
    """Auto-exclusion must not fabricate a run whose eligible pool cannot
    supply the registered controls: with only 22 eligible cells (230 excluded),
    the preflight still hard-refuses -- registered counts are not negotiable."""
    rows = _iof_rows()
    dropped = {row["cq_id"] for row in rows[:14]}
    filler = "# variant filler without any grounding anchors\n"
    missing = {vid: set(dropped) for vid in "ABCDEF"}
    path = tmp_path / "M.json"
    path.write_text(json.dumps({
        "variants": [
            {"id": vid, "view": filler} for vid in "ABCDE"
        ] + [{"id": "F", "view": _iof_view(rows, missing["F"])}]
    }), encoding="utf-8")
    variants = run_holdout.load_variant_manifest(path, require_six=False)
    assert len(_iof_ineligible_ids(rows, variants)) == 5 * 36 + 14
    with pytest.raises(SystemExit, match="fewer_than_registered_eligible_primary_cells"):
        run_holdout.eligibility_preflight(
            rows, variants, 20260913, None, {}, auto_exclude_grounding_ineligible=True)


def test_iof_dry_run_auto_excludes_and_records_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Wiring (fixture package): --domain iof --dry-run with the real
    iof.toml flag ON completes exit 0 instead of refusing; MANIFEST.json
    carries exclusions[] entries with the §15.2 reason + eligibility counts,
    CELL_PLAN.json contains only eligible primaries plus the 24 controls."""
    rows = _iof_rows()
    manifest = _iof_inline_manifest(
        tmp_path / "M.json",
        {"A": {"CQI01"}, "B": {"CQI02", "CQI03"}} | {vid: set() for vid in "CDEF"})
    variants = run_holdout.load_variant_manifest(manifest, require_six=False)
    n_excluded = len(_iof_ineligible_ids(rows, variants))
    assert n_excluded > 0
    out = tmp_path / "dry"
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--domain", "iof", "--dry-run", "--out", str(out),
        "--variants-manifest", str(manifest),
    ])
    assert run_holdout.main() == 0
    plan = json.loads((out / "CELL_PLAN.json").read_text(encoding="utf-8"))
    assert sum(cell["cell_kind"] == "primary" for cell in plan) == 6 * 36 - n_excluded
    assert sum(cell["cell_kind"] == "ablated_control" for cell in plan) == 24
    assert sum(cell["cell_kind"] == "preserved_control" for cell in plan) == 0
    manifest_out = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest_out["eligibility_exclusion_count"] == n_excluded
    assert manifest_out["eligibility_counts"] == {
        "checked_primary_cells": 216,
        "excluded_grounding_absent": n_excluded,
        "eligible_primary_cells": 216 - n_excluded,
    }
    entries = manifest_out["eligibility_exclusions"]
    assert len(entries) == n_excluded
    assert all(entry["reason"] == GROUNDING_ABSENT_REASON for entry in entries)
    assert manifest_out["preserved_controls_omitted_reason"] is not None


def test_iof_full_run_manifest_carries_exclusions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """The formal-run manifest writer propagates the same exclusions[] +
    counts as the dry-run writer (six-variant registered package, fake judge,
    no network)."""
    rows = _iof_rows()
    dropped = {row["cq_id"] for row in rows[:4]}
    manifest = _iof_registered_manifest(
        tmp_path / "M.json", {"A": set(dropped), "B": set(dropped)} | {vid: set() for vid in "CDEF"})
    out = tmp_path / "run"
    monkeypatch.setattr(
        run_holdout, "call_judge", lambda *a, **k: ({"score": 1, "evidence": ""}, True))
    monkeypatch.setenv(run_holdout.API_KEY_ENV, "test-only-key")
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--domain", "iof", "--out", str(out),
        "--variants-manifest", str(manifest), "--endpoint", "http://judge.test/v1",
        "--model", "test-judge",
    ])
    assert run_holdout.main() == 0
    manifest_out = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest_out["results_present"] is True
    assert manifest_out["eligibility_counts"] == {
        "checked_primary_cells": 216,
        "excluded_grounding_absent": 8,
        "eligible_primary_cells": 208,
    }
    assert manifest_out["eligibility_exclusion_count"] == 8
    assert all(entry["reason"] == GROUNDING_ABSENT_REASON
               for entry in manifest_out["eligibility_exclusions"])


@pytest.mark.skipif(
    not (REHEARSAL_PKG / "MANIFEST.json").is_file(),
    reason="rehearsal4 variant package is a /tmp rehearsal artifact, absent on other machines")
def test_iof_dry_run_completes_on_real_rehearsal_variant_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The exact rehearsal command that refused pre-fix now completes: real
    IOF variant views -> 216 checked, 178 grounding-absent exclusions, 38
    planned primaries (A8 B6 C6 D6 E6 F6) + 24 eligible-sampled controls + 0
    preserved."""
    pkg = tmp_path / "pkg"
    shutil.copytree(REHEARSAL_PKG, pkg)
    out = tmp_path / "cellplan"
    monkeypatch.setattr(sys, "argv", [
        "run_holdout.py", "--domain", "iof", "--dry-run", "--out", str(out),
        "--variants-manifest", str(pkg / "MANIFEST.json"),
    ])
    assert run_holdout.main() == 0
    plan = json.loads((out / "CELL_PLAN.json").read_text(encoding="utf-8"))
    assert sum(cell["cell_kind"] == "primary" for cell in plan) == 38
    assert sum(cell["cell_kind"] == "ablated_control" for cell in plan) == 24
    assert sum(cell["cell_kind"] == "preserved_control" for cell in plan) == 0
    assert len(plan) == 62
    manifest_out = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest_out["eligibility_counts"] == {
        "checked_primary_cells": 216,
        "excluded_grounding_absent": 178,
        "eligible_primary_cells": 38,
    }
    entries = manifest_out["eligibility_exclusions"]
    assert len(entries) == 178
    assert {entry["reason"] for entry in entries} == {GROUNDING_ABSENT_REASON}
    excluded_coords = {(entry["variant"], entry["cq_id"]) for entry in entries}
    per_variant = {
        vid: sum(cell["cell_kind"] == "primary" and cell["variant"] == vid for cell in plan)
        for vid in "ABCDEF"
    }
    assert per_variant == {"A": 8, "B": 6, "C": 6, "D": 6, "E": 6, "F": 6}
    # controls were sampled from eligible cells only: no ablated control sits
    # on an excluded coordinate
    for cell in plan:
        if cell["cell_kind"] == "ablated_control":
            assert (cell["variant"], cell["cq_id"]) not in excluded_coords
