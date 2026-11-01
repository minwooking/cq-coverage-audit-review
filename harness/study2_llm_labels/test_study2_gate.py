"""Tests of the Stage 1 gate rule, the label rules and the statistics helpers (PLAN.md 32.5-32.6), plus the runner against a
fake OpenAI-compatible server.  Synthetic data only; no human label, no real endpoint, no key.
Run:  python3 -m pytest -q test_study2_gate.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
_spec = importlib.util.spec_from_file_location("s2_analyze", HERE / "analyze.py")
AN = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(AN)


# ---------------------------------------------------------------- gate rule
def test_pair_passes_boundaries():
    assert AN.pair_passes(30, 0.50, 0.60) is True            # lb == ref (0.60 - 0.10 = 0.50 up to float): pass
    assert AN.pair_passes(30, 0.4999, 0.60) is False
    assert AN.pair_passes(29, 0.9, 0.60) is False             # fewer than 30 cells: not evaluable
    assert AN.pair_passes(100, None, 0.60) is False
    assert AN.pair_passes(100, 0.2, None) is False
    assert AN.pair_passes(100, 0.2, 0.30) is True              # ref = 0.20
    assert AN.pair_passes(100, 0.19, 0.30) is False


def test_stage1_verdict_combinations():
    v = AN.stage1_verdict
    assert v({"glm": {"AH": True, "R2": True}, "gptoss": {"AH": False, "R2": False}})["headline_labeler"] == "glm"
    assert v({"glm": {"AH": True, "R2": False}, "gptoss": {"AH": False, "R2": True}})["pass"] is False   # needs one model for both humans
    assert v({"glm": {"AH": False, "R2": False}, "gptoss": {"AH": True, "R2": True}})["headline_labeler"] == "gptoss"
    r = v({"glm": {"AH": True, "R2": True}, "gptoss": {"AH": True, "R2": True}})
    assert r["pass"] and r["passing_models"] == ["glm", "gptoss"] and r["headline_labeler"] == "glm"
    assert v({"qwen": {"AH": True, "R2": True}})["pass"] is False                                       # qwen never counts
    assert v({})["pass"] is False


# ---------------------------------------------------------------- label rules
def test_majority_tie_min_valid_and_median():
    S = np.full((4, 25), np.nan)
    R = np.full((4, 25), np.nan)
    S[0, :] = 1; R[0, :] = 2                                   # unanimous 1, R=2
    S[1, :13] = 1; S[1, 13:25] = 0; R[1, :] = [0, 1] * 12 + [3]   # 13 vs 12 -> 1
    S[2, :14] = 1; S[2, 14:] = 0; S[2, 24] = np.nan; R[2, :] = 1   # 14 vs 10, 24 valid -> 1
    S[3, :7] = 1; S[3, 7:14] = 0; R[3, :14] = 3                # 14 valid: below 15 -> undefined
    lab = AN.cell_labels(S, R)
    assert lab["L"][0] == 1 and lab["L"][1] == 1 and lab["L"][2] == 1 and np.isnan(lab["L"][3])
    assert lab["R"][0] == 2 and np.isnan(lab["R"][3])
    assert lab["consistent"][0] and not lab["consistent"][1]
    # tie: 15 valid slots cannot tie; 16 valid slots 8-8 -> undefined
    S2 = np.full((1, 25), np.nan); S2[0, :8] = 1; S2[0, 8:16] = 0; R2 = np.full((1, 25), 1.0)
    assert np.isnan(AN.cell_labels(S2, R2)["L"][0])
    # lower median of an even count
    R3 = np.full((1, 25), np.nan); R3[0, :16] = [0] * 8 + [3] * 8
    S3 = np.full((1, 25), 1.0)
    assert AN.cell_labels(S3, R3)["R"][0] == 0


def test_split_half_rating_columns():
    R = np.zeros((1, 25))
    for k, (p, s) in enumerate(AN.SLOTS):
        R[0, k] = 3 if s in (4, 5) else 1
    a, b = AN.split_half_rating(R)
    assert a[0] == 1 and b[0] == 3


def test_slot_matrices_last_terminal_wins_and_context_skip():
    recs = [{"cell_id": "c1", "persona": "domain", "seed": 1, "status": "ok", "S_final": 0, "R_raw": 1},
            {"cell_id": "c1", "persona": "domain", "seed": 1, "status": "ok", "S_final": 1, "R_raw": 2},
            {"cell_id": "c1", "persona": "domain", "seed": 2, "status": "invalid"},
            {"cell_id": "c1", "persona": "domain", "seed": 3, "status": "error"},
            {"cell_id": "c2", "persona": None, "seed": None, "status": "context_skip"}]
    m = AN.slot_matrices(recs, ["c1", "c2"])
    assert m["S"][0, 0] == 1 and m["R"][0, 0] == 2 and np.isnan(m["S"][0, 1]) and np.isnan(m["S"][0, 2])
    assert m["context_skip"] == {"c2"}


# ---------------------------------------------------------------- statistics helpers equal review10's
def test_helpers_equal_review10_copies():
    spec = importlib.util.spec_from_file_location("r10an", HERE.parent / "review10_llm_labels" / "analyze.py")
    old = sys.path[:]
    try:
        r10 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(r10)
    finally:
        sys.path[:] = old
    rng = np.random.default_rng(1)
    cl = np.array([f"Q{i % 17}" for i in range(120)])
    x = rng.integers(0, 2, 120).astype(float)
    y = np.where(rng.random(120) < 0.7, x, 1 - x)
    assert AN.kappa_ci(cl, x, y) == r10.kappa_ci(cl, x, y)
    assert AN.agree_ci(cl, x, y) == r10.agree_ci(cl, x, y)
    X = rng.integers(0, 2, (120, 25)).astype(float)
    assert np.allclose(AN.alpha_from(AN.alpha_cols(X).sum(0, keepdims=True)), r10.alpha_from(r10.alpha_cols(X).sum(0, keepdims=True)))


def test_human_block_runs_and_pi():
    rng = np.random.default_rng(2)
    n = 90
    cl = np.array([f"Q{i % 18}" for i in range(n)])
    a = rng.integers(0, 2, n).astype(float)
    r = np.where(rng.random(n) < 0.8, a, 1 - a)
    L = np.where(rng.random(n) < 0.9, a, 1 - a)
    J = rng.integers(0, 4, n).astype(float)
    b = AN.human_block(cl, L, {"AH": a, "R2": r}, J)
    assert b["n_cells"] == n and set(b["vs_human"]) == {"AH", "R2"}
    assert 0 <= b["pi_hat"]["LLM"]["est"] <= 1
    exp = float(((J >= 2) & (L == 0)).mean())
    assert abs(b["pi_hat"]["LLM"]["est"] - exp) < 1e-3


# ---------------------------------------------------------------- runner against a fake server
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(n))
        user = body["messages"][1]["content"]
        view = user.split("자료:\n", 1)[1].split("\n\n범주:", 1)[0]
        first = next((l for l in view.splitlines() if l.strip() and l.strip() != "[…]"), "")
        reply = json.dumps({"S": 1, "R": 0, "span": first[:60], "note": ""}, ensure_ascii=False)
        data = json.dumps({"choices": [{"message": {"content": reply}, "finish_reason": "stop"}],
                           "usage": {"prompt_tokens": 100, "completion_tokens": 20}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def test_runner_fake_server_and_resume():
    if not (HERE / "manifests" / "stage1.json").exists():
        import pytest
        pytest.skip("stage1 manifest not built")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, S2_RAW_DIR=d)
        cmd = [sys.executable, str(HERE / "s2_run_labels.py"), "--model", "fake", "--stage", "stage1",
               "--endpoint", f"http://127.0.0.1:{port}/v1", "--workers", "3", "--limit-cells", "2",
               "--progress", str(Path(d) / "p.md")]
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, r.stderr[-2000:]
        recs = [json.loads(l) for l in (Path(d) / "fake_stage1.jsonl").read_text().splitlines()]
        assert len(recs) == 50
        assert all(x["status"] == "ok" and x["R_raw"] == 0 and x["S_final"] == 1 and x["span_verbatim"] for x in recs)
        assert all(x["started_at_utc"] and x["latency_s"] is not None for x in recs)      # the timing record
        assert not any("R_floor" in x for x in recs)                                     # no floor in this study
        assert {x["persona"] for x in recs} == set(AN.PERSONAS) and {x["seed"] for x in recs} == {1, 2, 3, 4, 5}
        text = json.dumps(recs)
        assert "127.0.0.1" not in text and str(port) not in text                          # no address in a record
        r2 = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300)
        assert r2.returncode == 0
        assert len((Path(d) / "fake_stage1.jsonl").read_text().splitlines()) == 50       # resume: nothing re-sent
    srv.shutdown()
