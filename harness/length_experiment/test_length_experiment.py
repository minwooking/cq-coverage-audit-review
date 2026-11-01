"""Tests for the rendering-length experiment tools.  ALL DATA IS SYNTHETIC; no network."""
from __future__ import annotations

import csv
import inspect
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import analyze_length as al  # noqa: E402
import make_inputs as mi  # noqa: E402
import run_length_judge as rj  # noqa: E402

G = "http://test.org/g#"
NAMES = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel", "India",
         "Juliet", "Kilo", "Lima", "Widget", "Gadget"]


def make_variants(root: Path) -> Path:
    vdir = root / "variants" / "A"
    vdir.mkdir(parents=True)
    ttl = ["@prefix g: <http://test.org/g#> .",
           "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
           "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
           "@prefix skos: <http://www.w3.org/2004/02/skos/core#> ."]
    for n in NAMES:
        ttl.append(f'g:{n} a owl:Class ; rdfs:label "{n}" ; skos:definition "def of {n.lower()}" .')
    ttl.append("g:Widget rdfs:subClassOf g:Gadget .")
    (vdir / "graph_A.ttl").write_text("\n".join(ttl) + "\n", encoding="utf-8")
    view = "\n".join(f"line {i:05d} " + "x" * 40 for i in range(3000))  # ~ 153k chars
    (vdir / "rendered_view.txt").write_text(view, encoding="utf-8")
    return root / "variants"


def write_bank(path: Path, grounding: str = "skos:definition g:Widget", answer: str = "secret") -> Path:
    rows = [{"cq_id": "CQ1", "category": "c", "question": "What is a Widget?", "grounding": grounding,
             "expected_answer": answer, "cluster_id": "K1"},
            {"cq_id": "CQ2", "category": "c", "question": "Explain zzzqqq please", "grounding": grounding,
             "expected_answer": answer, "cluster_id": "K2"}]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path


# ---- truncation rule ------------------------------------------------------

def test_limit_view_short_unchanged():
    assert mi.limit_view("a\nb", 10) == ("a\nb", False)


def test_limit_view_cuts_at_line_boundary_and_marks():
    text, trunc = mi.limit_view("aaaa\nbbbb\ncccc", 7)
    assert trunc and text == "aaaa\n" + mi.TRUNC_MARKER
    # head ends exactly on a complete line -> keep it whole
    text, trunc = mi.limit_view("aaaa\nbbbb\ncccc", 9)
    assert trunc and text == "aaaa\nbbbb\n" + mi.TRUNC_MARKER
    # no newline in head -> hard cut
    text, _ = mi.limit_view("abcdefghij", 4)
    assert text == "abcd\n" + mi.TRUNC_MARKER


def test_limited_head_never_exceeds_limit():
    text, _ = mi.limit_view("\n".join("y" * 30 for _ in range(5000)))
    assert len(text) <= mi.LIMITED_CHARS + 1 + len(mi.TRUNC_MARKER)


# ---- generation, not_applicable, leak guard ---------------------------------

def test_generate_conditions_and_not_applicable(tmp_path):
    vdir = make_variants(tmp_path)
    bank = write_bank(tmp_path / "bank.csv")
    out = tmp_path / "inputs"
    recs = mi.generate(bank, out, ("A",), vdir)
    by = {(r["cq_id"], r["condition"]): r for r in recs}
    assert by[("CQ1", "full")]["ref"] and not (out / "A" / "CQ1" / "full.txt").exists()
    assert by[("CQ1", "full")]["chars"] == 3000 * 51 + 2999
    lim = by[("CQ1", "limited")]
    assert lim["truncated"] and (out / "A" / "CQ1" / "limited.txt").read_text().endswith("[truncated]")
    sg = by[("CQ1", "subgraph")]
    assert sg["status"] == "ok" and sg["matched_nodes"] >= 1
    txt = (out / "A" / "CQ1" / "subgraph.txt").read_text()
    assert "Widget" in txt and "Gadget" in txt            # hop-1 neighbour via subClassOf
    na = by[("CQ2", "subgraph")]
    assert na["status"] == "not_applicable" and na["matched_nodes"] == 0
    assert not (out / "A" / "CQ2" / "subgraph.txt").exists()
    assert sg["est_tokens"] == -(-sg["chars"] // 4)
    assert len(sg["sha256"]) == 64


def test_subgraph_uses_same_renderer_format(tmp_path):
    """Sub-graph lines are byte-identical to the lines schema_view gives the full graph."""
    from run_simulated import schema_view
    vdir = make_variants(tmp_path)
    full_lines = set(schema_view(vdir / "A" / "graph_A.ttl").split("\n"))
    ctx = mi.VariantContext("A", vdir)
    text, roots, _ = mi.build_subgraph_text(ctx, "What is a Widget?")
    assert roots >= 1
    assert set(text.split("\n")) <= full_lines


def test_no_answer_leak_bank_columns_do_not_matter(tmp_path):
    vdir = make_variants(tmp_path)
    b1 = write_bank(tmp_path / "b1.csv", "skos:definition g:Widget", "ANSWER-ONE")
    b2 = write_bank(tmp_path / "b2.csv", "g:Alpha ~ g:Bravo > g:Lima", "TOTALLY DIFFERENT")
    r1 = mi.generate(b1, tmp_path / "o1", ("A",), vdir)
    r2 = mi.generate(b2, tmp_path / "o2", ("A",), vdir)
    key = lambda rs: [(r["cq_id"], r["condition"], r["status"], r["sha256"], r["matched_nodes"]) for r in rs]
    assert key(r1) == key(r2)


def test_load_questions_drops_forbidden_columns(tmp_path):
    rows = mi.load_questions(write_bank(tmp_path / "b.csv"))
    assert set(rows[0]) == set(mi.ALLOWED_BANK_COLUMNS)
    for col in mi.SUBGRAPH_FORBIDDEN_COLUMNS:
        assert col not in rows[0]


def test_extraction_code_never_names_forbidden_columns():
    for fn in (mi.build_subgraph_text, mi.generate, mi.load_questions):
        src = inspect.getsource(fn)
        for col in mi.SUBGRAPH_FORBIDDEN_COLUMNS:
            assert col not in src.replace('SUBGRAPH_FORBIDDEN_COLUMNS', ""), (fn.__name__, col)
    assert "JudgeEvidence((), {})" in inspect.getsource(mi.build_subgraph_text)


# ---- run_length_judge ------------------------------------------------------

def _gen(tmp_path):
    vdir = make_variants(tmp_path)
    bank = write_bank(tmp_path / "bank.csv")
    recs = mi.generate(bank, tmp_path / "inputs", ("A",), vdir)
    man = tmp_path / "inputs" / "manifest.jsonl"
    man.write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    return bank, man


def test_dry_run_prints_totals_without_network(tmp_path, capsys, monkeypatch):
    bank, man = _gen(tmp_path)
    monkeypatch.delenv("HOLDOUT_JUDGE_API_KEY", raising=False)
    assert rj.main(["--dry-run", "--manifest", str(man), "--bank", str(bank), "--variants", "A"]) == 0
    out = capsys.readouterr().out
    assert "TOTAL full" in out and "TOTAL subgraph" in out and "calls=2" in out
    assert "n/a" in out


def test_real_run_refused_without_freeze_confirmation(tmp_path):
    bank, man = _gen(tmp_path)
    with pytest.raises(SystemExit, match="not frozen"):
        rj.main(["--manifest", str(man), "--bank", str(bank), "--out", str(tmp_path / "c.jsonl")])
    assert not (tmp_path / "c.jsonl").exists()


def test_workers_capped_at_three(tmp_path):
    bank, man = _gen(tmp_path)
    with pytest.raises(SystemExit, match="--workers"):
        rj.main(["--dry-run", "--workers", "4", "--manifest", str(man), "--bank", str(bank)])


def test_reduced_design_keeps_full_for_variant_a_only():
    man = [{"condition": c, "variant": v, "status": "ok", "documented_exclusion": False}
           for c in rj.CONDITIONS for v in ("A", "B")]
    sel = rj.select(man, rj.CONDITIONS, ("A", "B"), "reduced", False)
    assert [(r["condition"], r["variant"]) for r in sel if r["condition"] == "full"] == [("full", "A")]
    assert len(rj.select(man, rj.CONDITIONS, ("A", "B"), "full", False)) == 6


# ---- analyze_length (synthetic scores) -----------------------------------

def _cells(path: Path, scores: dict[tuple[str, str], int]):
    """scores[(condition, cq)] = J ; variant A ; cluster = cq."""
    with path.open("w") as fh:
        for (cond, cq), j in scores.items():
            fh.write(json.dumps({
                "cell_id": f"length:{cond}:A:{cq}", "pair_id": f"A:{cq}", "condition": cond,
                "cq_id": cq, "cluster_id": cq, "variant": "A", "J": j,
                "judge_response": {"score": j, "evidence": ""}, "judge_response_parsed": True}) + "\n")


def test_analyze_separates_judge_error_from_information_deficit(tmp_path):
    bank, man = _gen(tmp_path)
    # extend bank/manifest to 4 synthetic CQs by hand: CQ1 (grounding present in subgraph),
    # plus fabricate manifest rows whose files we write ourselves.
    sub = tmp_path / "sub"; sub.mkdir()
    (sub / "has.txt").write_text("g:Widget | Widget\n", encoding="utf-8")
    (sub / "lacks.txt").write_text("g:Alpha | Alpha\n", encoding="utf-8")
    with bank.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["cq_id", "category", "question", "grounding", "expected_answer", "cluster_id"])
        w.writeheader()
        for i in range(1, 7):
            w.writerow({"cq_id": f"Q{i}", "category": "c", "question": "q", "grounding": "g:Widget",
                        "expected_answer": "x", "cluster_id": f"Q{i}"})
    rows = []
    for i in range(1, 7):
        for cond in ("limited", "subgraph"):
            rows.append({"condition": cond, "variant": "A", "cq_id": f"Q{i}", "status": "ok",
                         "path": str(sub / ("has.txt" if i <= 3 else "lacks.txt"))})
    rows.append({"condition": "subgraph", "variant": "A", "cq_id": "Q9", "status": "not_applicable", "path": None})
    man.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    scores = {}
    for i in range(1, 7):
        scores[("full", f"Q{i}")] = 3
        scores[("limited", f"Q{i}")] = 3
        scores[("subgraph", f"Q{i}")] = 0       # all six drop under subgraph
    cells = tmp_path / "cells.jsonl"; _cells(cells, scores)
    res = al.analyze(cells, man, bank, B=200, seed=1)
    sep = {s["reduced_condition"]: s for s in res["separation"]}["subgraph"]
    assert sep["n_full_J_ge2"] == 6
    assert sep["judge_error_candidate"] == 3 and sep["information_deficit"] == 3
    c = {x["contrast"]: x for x in res["contrasts"]}
    assert c["full-subgraph"]["mean_diff"] == 3.0 and c["full-subgraph"]["n_pairs"] == 6
    assert c["full-limited"]["mean_diff"] == 0.0 and c["full-limited"]["exact_agreement"] == 1.0
    assert res["not_applicable_inputs"] == {"subgraph": 1}
    assert res["distribution"]["subgraph"]["counts"]["0"] == 6
    assert res["distribution"]["full"]["mean"] == 3.0


def test_contrast_interval_and_qwk(tmp_path):
    scores = {}
    for i in range(1, 9):
        scores[("full", f"Q{i}")] = 2 + (i % 2)
        scores[("limited", f"Q{i}")] = 2 + (i % 2) - (1 if i % 4 == 0 else 0)
    cells = tmp_path / "c.jsonl"; _cells(cells, scores)
    by, inv = al.load_scores(cells)
    r = al.contrast(by, "full", "limited", B=300, seed=7)
    assert r["n_pairs"] == 8 and r["n_clusters"] == 8 and inv == {}
    assert r["mean_diff"] == pytest.approx(0.25)
    lo, hi = r["interval"]["ci95"]
    assert lo <= r["interval"]["cluster_mean_diff"] <= hi
    assert -1.0 <= r["qwk"] <= 1.0


def test_invalid_records_excluded(tmp_path):
    cells = tmp_path / "c.jsonl"
    cells.write_text(json.dumps({"pair_id": "A:Q1", "condition": "full", "J": 0,
                                 "judge_response": {"_error": "boom"}, "judge_response_parsed": False}) + "\n")
    by, inv = al.load_scores(cells)
    assert by == {} and inv["full"] == 1


# ---- addendum 22: registered-judge rescoring (synthetic, no network) ----------

def _reg_manifest(tmp_path):
    rows = []
    for v in ("A", "B"):
        for cq in ("CQ1", "CQ2"):
            for cond in ("full", "limited", "subgraph"):
                rows.append({"condition": cond, "variant": v, "cq_id": cq, "status": "ok",
                             "documented_exclusion": False, "sha256": f"d{v}{cq}", "chars": 100,
                             "est_tokens": 25, "path": str(tmp_path / "art.txt"), "category": "c",
                             "cluster_id": cq})
    (tmp_path / "art.txt").write_text("g:Widget | Widget\n", encoding="utf-8")
    man = tmp_path / "manifest.jsonl"
    man.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    bank = write_bank(tmp_path / "bank.csv")
    return rows, man, bank


def test_registered_all_selects_limited_and_subgraph_for_all_variants(tmp_path):
    rows, _, _ = _reg_manifest(tmp_path)
    sel = rj.select(rows, rj.REGISTERED_ALL_CONDITIONS, ("A", "B"), "registered-all", False)
    assert {r["condition"] for r in sel} == {"limited", "subgraph"} and len(sel) == 8
    sel_full = rj.select(rows, rj.CONDITIONS, ("A", "B"), "registered-all", False)
    assert all(r["condition"] != "full" for r in sel_full)


def test_registered_all_refused_without_addendum22_and_never_legacy_out(tmp_path, monkeypatch):
    _, man, bank = _reg_manifest(tmp_path)
    base = ["--design", "registered-all", "--manifest", str(man), "--bank", str(bank)]
    with pytest.raises(SystemExit, match="addendum 22"):
        rj.main(base + ["--out", str(tmp_path / "c.jsonl")])
    with pytest.raises(SystemExit, match="cells_length.jsonl"):
        rj.main(base + ["--out", str(rj.LEGACY_OUT), "--confirm-addendum22-frozen"])
    # the addendum-17 flag does not unlock the new design
    with pytest.raises(SystemExit, match="addendum 22"):
        rj.main(base + ["--out", str(tmp_path / "c.jsonl"), "--confirm-addendum17-frozen"])


def test_registered_all_requires_registered_model_manifest_hash_and_env_key(tmp_path, monkeypatch):
    _, man, bank = _reg_manifest(tmp_path)
    args = ["--design", "registered-all", "--manifest", str(man), "--bank", str(bank),
            "--out", str(tmp_path / "o" / "c.jsonl"), "--confirm-addendum22-frozen"]
    with pytest.raises(SystemExit, match="manifest sha256"):
        rj.main(args)
    monkeypatch.setattr(rj, "EXPECTED_MANIFEST_SHA256", rj.sha256_file(man))
    monkeypatch.setenv("HOLDOUT_JUDGE_ENDPOINT", "http://localhost:1/v1")
    monkeypatch.setenv("HOLDOUT_JUDGE_MODEL", "gpt-5.6-luna")
    with pytest.raises(SystemExit, match="gemini-3.6-flash"):
        rj.main(args)
    monkeypatch.setenv("HOLDOUT_JUDGE_ENDPOINT", "https://generativelanguage.googleapis.com/v1beta/openai")
    monkeypatch.setenv("HOLDOUT_JUDGE_MODEL", "gemini-3.6-flash")
    monkeypatch.delenv("HOLDOUT_JUDGE_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="HOLDOUT_JUDGE_API_KEY is not set"):
        rj.main(args)
    assert "--api-key" not in inspect.getsource(rj)


def test_registered_all_mocked_run_resumes_and_hides_key(tmp_path, monkeypatch, capsys):
    _, man, bank = _reg_manifest(tmp_path)
    monkeypatch.setattr(rj, "EXPECTED_MANIFEST_SHA256", rj.sha256_file(man))
    monkeypatch.setenv("HOLDOUT_JUDGE_ENDPOINT", "https://generativelanguage.googleapis.com/v1beta/openai")
    monkeypatch.setenv("HOLDOUT_JUDGE_MODEL", "gemini-3.6-flash")
    monkeypatch.setenv("HOLDOUT_JUDGE_API_KEY", "SECRET-KEY-XYZ")
    calls = []

    def fake(cell, endpoint, model, key, *a):
        calls.append(cell["cell_id"])
        return {"cell_id": cell["cell_id"], "cq_id": cell["cq_id"], "cluster_id": cell["cluster_id"],
                "category": "c", "variant": cell["variant"], "cell_kind": "primary", "J": 2, "A": 0,
                "judge_response": {"score": 2}, "judge_response_parsed": True,
                "artifact_digest": cell["artifact_digest"]}
    monkeypatch.setattr(rj.rh, "_judge_one_cell", fake)
    out = tmp_path / "o" / "c.jsonl"
    args = ["--design", "registered-all", "--manifest", str(man), "--bank", str(bank), "--out", str(out),
            "--workers", "3", "--confirm-addendum22-frozen"]
    assert rj.main(args) == 0 and len(calls) == 8
    assert rj.main(args) == 0 and len(calls) == 8            # resume: nothing re-sent
    text = capsys.readouterr().out + out.read_text() + (out.parent / "MANIFEST_length.json").read_text()
    assert "SECRET-KEY-XYZ" not in text


def test_holdout_full_adapter_and_agreement(tmp_path):
    rows, man, bank = _reg_manifest(tmp_path)
    hold = tmp_path / "hold.jsonl"
    with hold.open("w") as fh:
        for v in ("A", "B"):
            for cq in ("CQ1", "CQ2"):
                fh.write(json.dumps({"cell_id": f"primary:{v}:{cq}", "cq_id": cq, "cluster_id": cq,
                                     "variant": v, "cell_kind": "primary", "J": 3,
                                     "judge_response": {"score": 3}, "judge_response_parsed": True,
                                     "artifact_digest": f"d{v}{cq}"}) + "\n")
        fh.write(json.dumps({"cell_id": "ablated_control:A:CQ1", "cq_id": "CQ1", "cluster_id": "CQ1",
                             "variant": "A", "cell_kind": "ablated_control", "J": 0,
                             "judge_response": {"score": 0}, "judge_response_parsed": True}) + "\n")
    full = al.load_holdout_full(hold, rows)
    assert sorted(full) == ["A:CQ1", "A:CQ2", "B:CQ1", "B:CQ2"] and full["A:CQ1"]["condition"] == "full"
    chk = rj.holdout_reuse_check(rows, hold)
    assert chk["holdout_valid_primary"] == 4 and chk["digest_matches_manifest"] == 4
    by_a = {"full": full, "limited": {"A:CQ1": {"J": 2}, "A:CQ2": {"J": 1}}}
    by_b = {"full": full, "limited": {"A:CQ1": {"J": 2}, "A:CQ2": {"J": 0}}}
    ag = {r["condition"]: r for r in al.agreement(by_a, by_b)}
    assert ag["full"]["exact_agreement"] == 1.0 and ag["limited"]["exact_agreement"] == 0.5
    cells = tmp_path / "c.jsonl"
    scores = {("limited", "CQ1"): 1, ("subgraph", "CQ1"): 2, ("limited", "CQ2"): 0, ("subgraph", "CQ2"): 3}
    _cells(cells, scores)
    res = al.analyze(cells, man, bank, B=100, seed=1, holdout_cells=hold, compare_cells=cells)
    assert res["distribution"]["full"]["n"] == 4 or res["distribution"]["full"]["n"] == 4
    assert "# 등록 judge" in al.report_ko(res)


# ---- addendum 23: luna-full-BF ----------------------------------------------

def _luna_manifest(tmp_path, variants=("A", "B", "C")):
    rows = []
    for v in variants:
        for cq in ("CQ1", "CQ2"):
            for cond in ("full", "limited"):
                rows.append({"condition": cond, "variant": v, "cq_id": cq, "status": "ok",
                             "documented_exclusion": False, "sha256": f"d{v}{cq}", "chars": 100,
                             "est_tokens": 25, "path": str(tmp_path / "art.txt"), "category": "c",
                             "cluster_id": cq})
    (tmp_path / "art.txt").write_text("g:Widget | Widget\n", encoding="utf-8")
    man = tmp_path / "manifest.jsonl"
    man.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return rows, man, write_bank(tmp_path / "bank.csv")


def test_luna_full_selects_full_views_of_b_to_f_only(tmp_path):
    rows, _, _ = _luna_manifest(tmp_path)
    sel = rj.select(rows, ("full",), rj.LUNA_VARIANT_ORDER, "luna-full-BF", False)
    assert {(r["condition"], r["variant"]) for r in sel} == {("full", "B"), ("full", "C")} and len(sel) == 4


def test_luna_full_refusals(tmp_path, monkeypatch):
    _, man, bank = _luna_manifest(tmp_path)
    base = ["--design", "luna-full-BF", "--manifest", str(man), "--bank", str(bank),
            "--out", str(tmp_path / "o" / "c.jsonl")]
    with pytest.raises(SystemExit, match="addendum 23"):
        rj.main(base)
    with pytest.raises(SystemExit, match="addendum 23"):
        rj.main(base + ["--confirm-addendum22-frozen", "--confirm-addendum17-frozen"])
    with pytest.raises(SystemExit, match="cells_length.jsonl"):
        rj.main(["--design", "luna-full-BF", "--manifest", str(man), "--bank", str(bank),
                 "--out", str(rj.LEGACY_OUT), "--confirm-addendum23-frozen"])
    monkeypatch.setattr(rj, "EXPECTED_MANIFEST_SHA256", rj.sha256_file(man))
    monkeypatch.setenv("HOLDOUT_JUDGE_ENDPOINT", "http://localhost:PORT/v1")
    monkeypatch.setenv("HOLDOUT_JUDGE_MODEL", "gemini-3.6-flash")
    with pytest.raises(SystemExit, match="gpt-5.6-luna"):
        rj.main(base + ["--confirm-addendum23-frozen"])
    monkeypatch.setenv("HOLDOUT_JUDGE_ENDPOINT", "https://example.com/v1")
    monkeypatch.setenv("HOLDOUT_JUDGE_MODEL", "gpt-5.6-luna")
    with pytest.raises(SystemExit, match="local <internal-proxy>"):
        rj.main(base + ["--confirm-addendum23-frozen"])


def _luna_fake(calls, fail=None):
    def fake(cell, endpoint, model, key, *a):
        calls.append(cell["cell_id"])
        base = {"cell_id": cell["cell_id"], "cq_id": cell["cq_id"], "cluster_id": cell["cluster_id"],
                "category": "c", "variant": cell["variant"], "cell_kind": "primary", "A": 0,
                "artifact_digest": cell["artifact_digest"]}
        if fail and fail(cell):
            return {**base, "J": 0, "judge_response": {"_error": "<HTTPError 402: 'Payment Required'>"},
                    "judge_response_parsed": False}
        return {**base, "J": 2, "judge_response": {"score": 2}, "judge_response_parsed": True}
    return fake


def _luna_env(monkeypatch, man):
    monkeypatch.setattr(rj, "EXPECTED_MANIFEST_SHA256", rj.sha256_file(man))
    monkeypatch.setenv("HOLDOUT_JUDGE_ENDPOINT", "http://localhost:PORT/v1")
    monkeypatch.setenv("HOLDOUT_JUDGE_MODEL", "gpt-5.6-luna")
    monkeypatch.setenv("HOLDOUT_JUDGE_API_KEY", "placeholder")


def test_luna_full_runs_variant_major_writes_progress_and_resumes(tmp_path, monkeypatch):
    _, man, bank = _luna_manifest(tmp_path)
    _luna_env(monkeypatch, man)
    calls = []
    monkeypatch.setattr(rj.rh, "_judge_one_cell", _luna_fake(calls))
    out = tmp_path / "o" / "c.jsonl"
    args = ["--design", "luna-full-BF", "--manifest", str(man), "--bank", str(bank), "--out", str(out),
            "--workers", "1", "--confirm-addendum23-frozen"]
    assert rj.main(args) == 0
    assert [c.split(":")[2] for c in calls] == ["B", "B", "C", "C"]
    prog = (out.parent / "PROGRESS.md").read_text()
    assert "variant B: cells 2/2" in prog and "variant C: cells 2/2" in prog
    assert rj.main(args) == 0 and len(calls) == 4            # resume: nothing re-sent


def test_luna_full_quota_error_stops_gracefully_keeping_completed_variants(tmp_path, monkeypatch):
    _, man, bank = _luna_manifest(tmp_path)
    _luna_env(monkeypatch, man)
    calls = []
    monkeypatch.setattr(rj.rh, "_judge_one_cell", _luna_fake(calls, fail=lambda c: c["variant"] == "C"))
    out = tmp_path / "o" / "c.jsonl"
    args = ["--design", "luna-full-BF", "--manifest", str(man), "--bank", str(bank), "--out", str(out),
            "--workers", "1", "--confirm-addendum23-frozen"]
    assert rj.main(args) == 0
    assert len(calls) == 3                                   # B x2, first C call hits 402 -> stop
    mf = list(out.parent.glob("MANIFEST_run_*.json"))[0].read_text()
    assert '"abort_reason": "quota_error"' in mf
    assert "variant B: cells 2/2" in (out.parent / "PROGRESS.md").read_text()


def test_luna_full_token_budget_stops(tmp_path, monkeypatch):
    _, man, bank = _luna_manifest(tmp_path)
    _luna_env(monkeypatch, man)
    calls = []
    monkeypatch.setattr(rj.rh, "_judge_one_cell", _luna_fake(calls))
    out = tmp_path / "o" / "c.jsonl"
    assert rj.main(["--design", "luna-full-BF", "--manifest", str(man), "--bank", str(bank), "--out", str(out),
                    "--workers", "1", "--token-budget", "1", "--confirm-addendum23-frozen"]) == 0
    assert len(calls) == 1


def test_quota_and_context_error_detectors():
    assert rj.is_quota_error({"judge_response": {"_error": "<HTTPError 429: 'Too Many'>"}})
    assert not rj.is_quota_error({"judge_response": {"_error": "<HTTPError 502: 'Bad'>"}})
    assert rj.is_context_error({"judge_response": {"_error": "<HTTPError 400: 'x'>",
                                                   "_error_body": "maximum context length exceeded"}})


def test_analyze_merges_extra_full_cells_and_per_variant(tmp_path):
    rows, man, bank = _luna_manifest(tmp_path, variants=("A", "B"))
    base = tmp_path / "base.jsonl"
    extra = tmp_path / "extra.jsonl"
    recs = []
    for v in ("A", "B"):
        for cq in ("CQ1", "CQ2"):
            for cond in ("limited", "subgraph"):
                recs.append((cond, v, cq, 1 if cond == "limited" else 2))
    recs.append(("full", "A", "CQ1", 3)); recs.append(("full", "A", "CQ2", 3))
    with base.open("w") as fh:
        for cond, v, cq, j in recs:
            fh.write(json.dumps({"cell_id": f"length:{cond}:{v}:{cq}", "pair_id": f"{v}:{cq}", "condition": cond,
                                 "cq_id": cq, "cluster_id": cq, "variant": v, "cell_kind": "primary", "J": j,
                                 "judge_response": {"score": j}, "judge_response_parsed": True}) + "\n")
    with extra.open("w") as fh:
        for cq in ("CQ1", "CQ2"):
            fh.write(json.dumps({"cell_id": f"length:full:B:{cq}", "pair_id": f"B:{cq}", "condition": "full",
                                 "cq_id": cq, "cluster_id": cq, "variant": "B", "cell_kind": "primary", "J": 2,
                                 "judge_response": {"score": 2}, "judge_response_parsed": True}) + "\n")
    res = al.analyze(base, man, bank, B=100, seed=1, extra_full_cells=extra, per_variant=True)
    assert res["distribution"]["full"]["n"] == 4
    assert res["distribution"]["full"]["coverage_j_ge2"] == 1.0
    assert set(res["per_variant"]) == {"A", "B"}
    cb = {c["contrast"]: c for c in res["per_variant"]["B"]["contrasts"]}
    assert cb["full-limited"]["n_pairs"] == 2 and cb["full-limited"]["mean_diff"] == 1.0
    assert cb["full-subgraph"]["mean_diff"] == 0.0
    assert "variant별" in al.report_ko(res)


def test_retry_after_longer_than_cap_fails_cell_without_sleeping(monkeypatch):
    """A 429 with a huge Retry-After (2.5M s hung the addendum-23 run) must not be waited out."""
    import email.message
    import run_holdout as rh

    hdrs = email.message.Message()
    hdrs["Retry-After"] = "2497900"
    calls = {"n": 0}

    def fake_urlopen(request, timeout=None):
        calls["n"] += 1
        raise rh.urllib.error.HTTPError("https://example.invalid/chat/completions", 429, "x", hdrs, None)

    monkeypatch.setattr(rh.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(rh.time, "sleep", lambda s: pytest.fail("must not sleep on a capped Retry-After"))
    monkeypatch.setattr(rh, "JUDGE_MIN_REQUEST_INTERVAL_S", 0.0)
    response, parsed = rh.call_judge("https://example.invalid", "m", "q", "a", "key", 1024)
    assert parsed is False and calls["n"] == 1
    assert rj.is_quota_error({"judge_response": response})  # the stop rule still sees the 429
    assert rh.JUDGE_RETRY_AFTER_CAP_S == 300.0
    assert response["_retry_after_s"] == 2497900.0


def test_retry_after_within_cap_is_still_honored(monkeypatch):
    import email.message
    import run_holdout as rh

    hdrs = email.message.Message()
    hdrs["Retry-After"] = "120"
    seq = []

    def fake_urlopen(request, timeout=None):
        if not seq:
            seq.append(1)
            raise rh.urllib.error.HTTPError("https://example.invalid/x", 429, "x", hdrs, None)

        class R:
            def read(self): return b'{"choices":[{"message":{"content":"{\\"score\\": 2}"}}]}'
            def __enter__(self): return self
            def __exit__(self, *a): return None
        return R()

    sleeps = []
    monkeypatch.setattr(rh.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(rh.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(rh, "JUDGE_MIN_REQUEST_INTERVAL_S", 0.0)
    response, parsed = rh.call_judge("https://example.invalid", "m", "q", "a", "key", 1024)
    assert parsed is True and 120.0 in sleeps
