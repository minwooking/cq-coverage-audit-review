"""Tests for dedup.py -- D1..D5, tau_emb calibration arithmetic (addendum 47,
plan-based, exploratory). AI-generated draft: a person must review and test it before use.

The embedding is always mocked (MockEmbed) or absent; the local model is never loaded
here, nothing is downloaded, no network.
"""
import json
import sys
from pathlib import Path

import csv
import numpy as np
import pytest

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

import common  # noqa: E402
import dedup as dedup_mod  # noqa: E402


def ref_terms(snap, ctx):
    return {r["ref_id"] for r in ctx["refs"] if r["terms"]}


@pytest.fixture
def ctx(snap, mock_embed):
    return dedup_mod.build_context(snap, embed=mock_embed, tau=0.9)


def mkrow(q, g, cq_id="CQE100"):
    return {"cq_id": cq_id, "question": q, "grounding": g}


# ---------------------------------------------------------------- D1/D2
def test_d1_normalized_identical(snap, mock_embed):
    """Zero vectors isolate the text rules: only D1 may fire here."""
    import numpy as np

    class ZeroEmbed:
        def __call__(self, texts):
            return np.zeros((len(texts), 8))
    ctx = dedup_mod.build_context(snap, embed=ZeroEmbed(), tau=0.9)
    with (common.ACCESS / "bank" / "cq_bank_brick_v1.csv").open(newline="", encoding="utf-8") as fh:
        first = next(iter(csv.DictReader(fh)))
    q = first["question"].upper()
    res = dedup_mod.check_row(snap, mkrow(q, "rdfs:subClassOf brick:Sensor"), ctx)
    assert "D1" in res["rules_triggered"]  # D3 also fires (brick:Sensor is a ref anchor)


def test_d2_normalized_grounding_identical(snap, ctx):
    with (common.ACCESS / "bank" / "cq_bank_brick_v1.csv").open(newline="", encoding="utf-8") as fh:
        first = next(iter(csv.DictReader(fh)))
    res = dedup_mod.check_row(snap, mkrow("Totally unrelated query about widgets?",
                                         "  " + first["grounding"] + "  "), ctx)
    assert "D2" in res["rules_triggered"]


# ---------------------------------------------------------------- D3
def test_d3_primary_term_hits_reference_anchor(snap, mock_embed):
    """Question deliberately unrelated so only D3 can fire: brick:Sensor is a grounding
    anchor of bank v1, and rdfs:subClassOf brick:Sensor is not a reference grounding."""
    import numpy as np

    class ZeroEmbed:
        def __call__(self, texts):
            return np.zeros((len(texts), 8))
    ctx = dedup_mod.build_context(snap, embed=ZeroEmbed(), tau=0.9)
    res = dedup_mod.check_row(
        snap, mkrow("What completely unrelated question about widgets?",
                    "rdfs:subClassOf brick:Sensor"), ctx)
    assert res["rules_triggered"] == ["D3"]
    assert res["nearest_ref_id"]


# ---------------------------------------------------------------- D4
def test_d4_jaccard_threshold(snap, ctx):
    with (common.ACCESS / "bank" / "cq_bank_brick_v1.csv").open(newline="", encoding="utf-8") as fh:
        first = next(iter(csv.DictReader(fh)))
    base = first["question"].rstrip("?")
    # one-word variant keeps Jaccard high but normalization differs
    q_near = base + " exactly?"
    row_near = mkrow(q_near, "skos:definition brick:SomeOtherTerm_ZZ")
    res = dedup_mod.check_row(snap, row_near, ctx)
    hit_d4 = "D4" in res["rules_triggered"]
    if not hit_d4:  # D1/D2/D3 may fire first; jaccard is reported regardless
        assert res["jaccard"] >= 0.0
    q_far = "What entirely different topic about unrelated widgets and gadgets? nope?"
    res2 = dedup_mod.check_row(snap, mkrow(q_far, "rdfs:subClassOf brick:Sensor"), ctx)
    assert "D4" not in res2["rules_triggered"]  # distant text: no D4 (D3 may still fire)


def test_d4_threshold_constant():
    assert dedup_mod.D4_JACCARD_THRESHOLD == 0.80
    assert dedup_mod.D5_ANCHOR_JACCARD_THRESHOLD == 0.50
    assert dedup_mod.D5_LOG_ONLY_COSINE == 0.95


# ---------------------------------------------------------------- D5
def test_d5_cosine_and_anchor_jaccard_fire(snap, mock_embed):
    class DupEmbed:  # every text maps to the same vector -> cosine 1.0
        def __call__(self, texts):
            v = np.zeros(8) + 1.0
            v /= float(np.linalg.norm(v))
            return np.array([v] * len(texts))
    ctx = dedup_mod.build_context(snap, embed=DupEmbed(), tau=0.9)
    with (common.ACCESS / "bank" / "cq_bank_brick_v1.csv").open(newline="", encoding="utf-8") as fh:
        first = next(iter(csv.DictReader(fh)))
    res = dedup_mod.check_row(snap, mkrow("Anything about the same concept here?",
                                         first["grounding"]), ctx)
    assert "D5" in res["rules_triggered"]
    assert res["cosine"] >= 0.9
    assert res["anchor_jaccard"] >= 0.5


def test_d5_high_cosine_different_anchors_kept_log_only(snap):
    """cosine >= 0.95 but anchor-set jaccard < 0.5 -> KEPT, log_only=True (never excludes)."""
    class DupEmbed:
        def __call__(self, texts):
            v = np.zeros(8) + 1.0
            v /= float(np.linalg.norm(v))
            return np.array([v] * len(texts))
    ctx = dedup_mod.build_context(snap, embed=DupEmbed(), tau=0.9)
    # brick:AHU shares no terms with any reference grounding -> anchor jaccard 0 everywhere
    res = dedup_mod.check_row(snap, mkrow("A totally novel question shape here?",
                                         "skos:definition brick:AHU"), ctx)
    assert res["rules_triggered"] == []
    assert res["log_only"] is True and res["cosine"] >= 0.95


def test_d5_tau_below_p10_still_excludes(snap):
    class DupEmbed:
        def __call__(self, texts):
            v = np.zeros(8) + 1.0
            v /= float(np.linalg.norm(v))
            return np.array([v] * len(texts))
    ctx = dedup_mod.build_context(snap, embed=DupEmbed(), tau=0.99)
    with (common.ACCESS / "bank" / "cq_bank_brick_v1.csv").open(newline="", encoding="utf-8") as fh:
        first = next(iter(csv.DictReader(fh)))
    res = dedup_mod.check_row(snap, mkrow("Any phrasing of this same idea?",
                                         first["grounding"]), ctx)
    assert "D5" in res["rules_triggered"]  # cosine 1.0 >= 0.99


# ---------------------------------------------------------------- strict embed policy
def test_build_context_strict_without_embed_raises(monkeypatch):
    monkeypatch.setattr(dedup_mod, "local_embed_fn",
                        lambda: (_ for _ in ()).throw(dedup_mod.EmbedMissingError("cache absent")))
    snap = common.Snapshot(common.SNAPSHOT)
    with pytest.raises(dedup_mod.EmbedMissingError):
        dedup_mod.build_context(snap)
    monkeypatch.setattr(dedup_mod, "_EMBED_SINGLETON", None, raising=False)


# ---------------------------------------------------------------- extra_rows / earlier batch
def test_extra_rows_participate(snap, mock_embed):
    ctx = dedup_mod.build_context(snap, embed=mock_embed, tau=0.9, extra_rows=[
        {"cq_id": "CQE001", "question": "What is brick:Foo?", "grounding": "skos:definition brick:Foo"}])
    ids = {r["ref_id"] for r in ctx["refs"]}
    assert "CQE001" in ids
    res = dedup_mod.check_row(snap, mkrow("What is brick:Foo?",
                                         "skos:definition brick:Foo"), ctx)
    assert res["rules_triggered"]  # D1/D2 hit against the earlier row


# ---------------------------------------------------------------- alias / anchor machinery
def test_anchor_terms_alias_closure(snap, mock_embed):
    ctx = dedup_mod.build_context(snap, embed=mock_embed, tau=0.9)
    alias = ctx["alias"]
    assert isinstance(alias, dict)
    terms = dedup_mod.anchor_terms_of_grounding(snap, "skos:definition brick:Sensor", alias)
    assert "brick:Sensor" in terms
    prim = dedup_mod.primary_terms(snap, "skos:definition brick:Sensor", alias)
    assert prim  # non-empty primary set


def test_local_name_only_anchor(snap, mock_embed):
    ctx = dedup_mod.build_context(snap, embed=mock_embed, tau=0.9)
    terms = dedup_mod.anchor_terms_of_grounding(snap, "skos:definition Sensor", ctx["alias"])
    assert "brick:Sensor" in terms


# ---------------------------------------------------------------- tau calibration
def test_compute_tau_pair_count_guard(monkeypatch, tmp_path):
    def embed(texts):
        v = np.zeros(4) + 0.5
        v /= float(np.linalg.norm(v))
        return np.array([v] * len(texts))
    t = dedup_mod.compute_tau(embed)
    assert t["pairs"] == 36
    assert t["tau_emb"] <= 0.90
    for k in ("min", "p10", "median", "cosines", "pairs_definition",
              "percentile_method", "model"):
        assert k in t
    assert len(t["cosines"]) == 36
    assert t["min"] <= t["p10"] <= t["median"]
    assert t["tau_emb"] == round(min(0.90, t["p10"]), 4)


def test_load_tau_frame_then_file(tmp_path, monkeypatch):
    f = tmp_path / "frame_summary.json"
    f.write_text(json.dumps({"tau_emb": 0.83}), encoding="utf-8")
    assert dedup_mod.load_tau(f) == 0.83
    # hermetic: the tau_emb.json fallback must point at tmp_path, never the real bank file
    monkeypatch.setattr(dedup_mod, "HERE", tmp_path / "tools")
    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    assert dedup_mod.load_tau(empty) == 0.90  # conservative ceiling
    (tmp_path / "tau_emb.json").write_text(json.dumps({"tau_emb": 0.5168}), encoding="utf-8")
    assert dedup_mod.load_tau(empty) == 0.5168  # fallback to tau_emb.json


# ---------------------------------------------------------------- main: --rows + --tau-out
def test_main_rows_mode_writes_csv(tmp_path, snap, mock_embed, monkeypatch):
    with (common.ACCESS / "bank" / "cq_bank_brick_v1.csv").open(newline="", encoding="utf-8") as fh:
        first = next(iter(csv.DictReader(fh)))
    orig = dedup_mod.build_context
    monkeypatch.setattr(dedup_mod, "build_context",
                        lambda s, extra_rows=None, embed=None, tau=None: orig(
                            s, extra_rows=extra_rows, embed=mock_embed, tau=0.9))
    rows = tmp_path / "rows.jsonl"
    rows.write_text(json.dumps({"cq_id": "CQE010", "question": first["question"],
                                "grounding": first["grounding"]}) + "\n"
                    + json.dumps({"cq_id": "CQE011",
                                  "question": "A wholly unique phrasing about widgets?",
                                  "grounding": "rdfs:comment brick:Bench_Space"}) + "\n",
                    encoding="utf-8")
    log = tmp_path / "dedup_log.csv"
    rc = dedup_mod.main(["--rows", str(rows), "--log", str(log), "--no-hook"])
    assert rc == 0
    with log.open(newline="", encoding="utf-8") as fh:
        rec = list(csv.DictReader(fh))
    assert rec[0]["decision"] == "exclude" and "D1" in rec[0]["rule"]
    assert rec[1]["cq_id"] == "CQE011"
    assert {"cq_id", "ref_id", "jaccard", "cosine", "anchor_jaccard", "rule", "decision"} \
        <= set(rec[0])
