"""Tests of the Stage 2 audit wiring on synthetic data (no model, no human label, no network).
Run:  python3 -m pytest -q test_study2_stage2.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import s2_stage2_analysis as SA  # noqa: E402
import s2_stage2 as S2  # noqa: E402


def synthetic(n_q=60, seed=0):
    rng = np.random.default_rng(seed)
    rows, jm, prim = [], {}, {}
    for q in range(n_q):
        cq = f"CQX{q:02d}"
        for v in "ABCDEF":
            cid = f"primary:{v}:{cq}"
            rows.append({"cell_id": cid, "cell_kind": "primary", "variant": v, "cq_id": cq, "cat": "concept_definition"})
            base = 3 if v != "A" else 2
            J = int(np.clip(base - rng.integers(0, 3), 0, 3))
            S = 1 if (J >= 2 and rng.random() < 0.9) or rng.random() < 0.1 else 0
            R = int(np.clip(J + rng.integers(-1, 2), 0, 3))
            ev = ["some quoted span"]
            jm[cid] = {j: {"J": int(np.clip(J + (rng.integers(-1, 2) if j == "gptoss" else 0), 0, 3)), "evidence": ev, "evidence_at_median": ev, "n_valid": 3} for j in SA.JUDGES}
            prim[cid] = (S, R)
    ctrl = {}
    for i in range(24):
        cid = f"ablated_control:B:CQX{i:02d}"
        rows.append({"cell_id": cid, "cell_kind": "ablated_control", "variant": "B", "cq_id": f"CQX{i:02d}", "cat": "concept_definition"})
        ctrl[cid] = (0 if i < 23 else 1, 0)
    return rows, jm, prim, ctrl


def test_audit_one_runs_and_has_all_gates():
    rows, jm, prim, ctrl = synthetic()
    labels = {"prim": prim, "ctrl": ctrl, "g2": {"intra_rater_qwk": 0.8, "ci_lo": 0.75, "n": 360}}
    recs = [{"status": "ok", "started_at_utc": "2026-10-19T00:00:00+00:00", "latency_s": 2.0} for _ in range(100)]
    jviews = {r["cell_id"]: "x some quoted span y" for r in rows if r["cell_kind"] == "primary"}
    out = SA.audit_one(rows, labels, jm, jviews, "glm", "gptoss", recs)
    assert out["n_cells"] == 360 and out["n_clusters"] == 60
    g = out["gates"]
    assert set(g) == {"G1_silent_over_credit", "G2_intra_rater_qwk", "G3_negative_control", "G4_human_judge_qwk", "G5_mae_judge_human",
                      "G6_consistency", "G7_audit_trail", "G8_external_spotcheck"}
    assert g["G3_negative_control"]["status"] == "pass"            # 23 of 24 unsupported >= 22
    assert g["G2_intra_rater_qwk"]["status"] == "pass"
    assert g["G7_audit_trail"]["status"] == "pass" and g["G8_external_spotcheck"]["status"] == "not_computable"
    assert out["two_way_counts"]["n"] == 360
    assert out["verbatim_span_check"]["share_verbatim"] == 1.0
    assert out["A_to_B_mde"]["n_pairs"] == 60 and out["A_to_B_mde"]["mde_80pct_power"] is not None
    assert "pi_hat" in out and out["pi_hat"]["n_cells"] == 360


def test_g3_undefined_control_counts_as_failure():
    rows, jm, prim, ctrl = synthetic(n_q=30)
    for k in list(ctrl)[:3]:
        del ctrl[k]                                                    # three undefined controls -> A=1 -> 21 of 24 unsupported -> fail
    labels = {"prim": prim, "ctrl": ctrl, "g2": None}
    out = SA.audit_one(rows, labels, jm, {r["cell_id"]: "x" for r in rows}, "glm", "glm", [])
    assert out["gates"]["G3_negative_control"]["status"] == "fail"


def test_g7_fails_on_fast_calls_or_missing_latency():
    fast = [{"status": "ok", "started_at_utc": "t", "latency_s": 0.1} for _ in range(10)]
    assert SA.g7_gate(fast)["status"] == "fail"
    miss = [{"status": "ok", "started_at_utc": "t", "latency_s": None}] + [{"status": "ok", "started_at_utc": "t", "latency_s": 3.0}] * 99
    assert SA.g7_gate(miss)["status"] == "fail"
    good = [{"status": "ok", "started_at_utc": "t", "latency_s": 3.0}] * 50
    assert SA.g7_gate(good)["status"] == "pass"


def test_verbatim_in():
    view = "alpha beta gamma\ndelta   epsilon zeta eta theta"
    assert SA.verbatim_in(["beta gamma delta epsilon"], view) is True
    assert SA.verbatim_in(["beta gamma delta wrong"], view) is False
    assert SA.verbatim_in(["alpha beta gamma ... delta epsilon zeta eta theta"], view) is True
    assert SA.verbatim_in([], view) is None


def test_judge_median_lower_median_and_evidence():
    recs = {"glm": [{"cell_id": "c", "valid": True, "J": 3, "repeat": 1, "evidence": "e1"},
                    {"cell_id": "c", "valid": True, "J": 1, "repeat": 2, "evidence": "e2"},
                    {"cell_id": "c", "valid": True, "J": 2, "repeat": 3, "evidence": ["e3", "e1"]},
                    {"cell_id": "d", "valid": False, "J": None, "repeat": 1}]}
    jm = S2.judge_median(recs)
    assert jm["c"]["glm"]["J"] == 2 and jm["c"]["glm"]["evidence"] == ["e1", "e2", "e3"] and jm["c"]["glm"]["evidence_at_median"] == ["e3", "e1"]
    assert "d" not in jm


def test_eligibility_rule_uses_the_papers_strict_rule():
    src = (HERE / "s2_stage2.py").read_text(encoding="utf-8")
    assert 'info["can_ablate"]' in src and "documented" not in src.split("def eligibility")[1].split("def load_elig")[0].lower()


def test_descriptive_when_gate_fails():
    rows, jm, prim, ctrl = synthetic(n_q=10)
    d = SA.descriptive_judge_only(rows, jm)
    assert d["glm"]["n_cells"] == 60 and "pi_hat" not in d["glm"]
