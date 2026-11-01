"""Offline tests for the addendum-26 scorer and analysis (synthetic data, a local fake server, no real judge).

Run: python3 -m pytest harness/review6_judges/test_review6.py -q
"""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import score_judges as sj  # noqa: E402


# ----------------------------------------------------------------------------- fake server
class FakeState:
    calls = []
    lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        text = "".join(m["content"] for m in body["messages"])
        if self.path.endswith("/tokenize"):
            return self._send(200, {"count": len(text) // 4 + 5})
        mt = body["max_tokens"]
        with FakeState.lock:
            FakeState.calls.append((text[-60:], mt, body.get("response_format"), body.get("reasoning_effort"),
                                    body.get("temperature")))
        usage = {"prompt_tokens": len(text) // 4, "completion_tokens": 20}
        if "CONTEXTBOMB" in text:
            return self._send(400, {"error": {"message": "This model's maximum context length is 65536 tokens."}})
        if "TRUNC" in text and mt == sj.FIRST_MAX_TOKENS:
            return self._send(200, {"choices": [{"message": {"content": None, "reasoning_content": "thinking..."},
                                                 "finish_reason": "length"}], "usage": usage})
        if "FENCE" in text:
            content = "```json\n{\"score\": 2, \"evidence\": \"x\"}\n```"
        elif "BADJSON" in text:
            content = "I cannot comply"
        elif "FIVE" in text:
            content = "{\"score\": 5, \"evidence\": \"\"}"
        else:
            content = json.dumps({"score": 3, "evidence": "span"})
        return self._send(200, {"choices": [{"message": {"content": content}, "finish_reason": "stop"}], "usage": usage})


@pytest.fixture()
def server():
    FakeState.calls = []
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()


def job(i, marker=""):
    system, user = "SYS", f"ARTIFACT:\nbody {marker}\n\nQUESTION: q{i}"
    return {"job_id": f"x|{i}", "study": "holdout_subgraph", "cell_id": f"primary:A:CQ{i:02d}",
            "cell_kind": "primary", "variant": "A", "cq_id": f"CQ{i:02d}", "cluster_id": f"CQ{i:02d}",
            "category": "c", "system": system, "user": user, "prompt_sha256": sj.sha256_text(system + "\n\x00\n" + user)}


def write_jobs(path, jobs):
    path.write_text("\n".join(json.dumps(j) for j in jobs) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------------- parse
@pytest.mark.parametrize("content,j,ok", [
    ('{"score": 2, "evidence": "a"}', 2, True),
    ('```json\n{"score": 0, "evidence": ""}\n```', 0, True),
    ('Sure: {"score": 3, "evidence": "q"} done', 3, True),
    ('{"score": 2.4, "evidence": "a"}', 2, True),
    ('{"score": 4}', None, False),
    ('{"score": "2"}', None, False),
    ('{"score": true}', None, False),
    ('no json', None, False),
    ('', None, False),
    (None, None, False),
])
def test_parse_reply(content, j, ok):
    got = sj.parse_reply(content)
    assert (got[0], got[2]) == (j, ok)


def test_loads_lenient_flags_fence():
    assert sj.loads_lenient('{"a": 1}') == ({"a": 1}, False)
    assert sj.loads_lenient('```json\n{"a": 1}\n```') == ({"a": 1}, True)


# ----------------------------------------------------------------------------- scorer end to end
def test_scorer_end_to_end_retry_skip_resume(server, tmp_path):
    jobs = [job(1), job(2, "TRUNC"), job(3, "FENCE"), job(4, "BADJSON"), job(5, "CONTEXTBOMB"), job(6, "FIVE")]
    jp, out = tmp_path / "jobs.jsonl", tmp_path / "raw.jsonl"
    write_jobs(jp, jobs)
    rc = sj.main(["--jobs", str(jp), "--judge", "fake", "--endpoint", server, "--out", str(out),
                  "--repeats", "2", "--workers", "3"])
    assert rc == 0
    recs = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    by = {}
    for r in recs:
        by.setdefault(r["cell_id"], []).append(r)
    assert all(r["J"] == 3 and r["valid"] for r in by["primary:A:CQ01"])
    # truncated first attempt is retried with the larger budget
    t = by["primary:A:CQ02"]
    assert len(t) == 2 and all(r["valid"] and len(r["attempts"]) == 2 and r["attempts"][1]["max_tokens"] == 4096 for r in t)
    f = by["primary:A:CQ03"]
    assert all(r["J"] == 2 and r["lenient_parse"] for r in f)
    b = by["primary:A:CQ04"]
    assert all(not r["valid"] and r["status"] == "invalid" and len(r["attempts"]) == 3 and r["J"] is None for r in b)
    five = by["primary:A:CQ06"]
    assert all(not r["valid"] and r["status"] == "invalid" for r in five)
    # a context error is not retried and is recorded as a skip
    c = by["primary:A:CQ05"]
    assert all(r["status"] == "context_skip" and len(r["attempts"]) == 1 for r in c)
    # every request used the registered decoding
    assert all(x[2] == {"type": "json_object"} and x[4] == 0.0 for x in FakeState.calls)
    # resume: only the invalid cells are sent again; valid/context-skip are not
    FakeState.calls = []
    sj.main(["--jobs", str(jp), "--judge", "fake", "--endpoint", server, "--out", str(out), "--repeats", "2",
             "--workers", "2"])
    # only the 2 invalid cells x 2 repeats x 3 attempts are sent again
    assert len(FakeState.calls) == 12
    recs2 = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    ok1 = [r for r in recs2 if r["cell_id"] == "primary:A:CQ01" and r["valid"]]
    assert len(ok1) == 2  # not duplicated


def test_preflight_over_context_cell_is_skipped_not_sent(server, tmp_path):
    big = job(1, "x" * 4 * 70000)
    jobs = [big, job(2)]
    jp, out = tmp_path / "jobs.jsonl", tmp_path / "raw.jsonl"
    write_jobs(jp, jobs)
    sj.main(["--jobs", str(jp), "--judge", "fake", "--endpoint", server, "--out", str(out), "--repeats", "1"])
    recs = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    skip = [r for r in recs if r["cell_id"] == "primary:A:CQ01"]
    assert len(skip) == 1 and skip[0]["status"] == "context_skip" and skip[0]["repeat"] == 0
    assert len(FakeState.calls) == 1  # only the fitting cell was sent


def test_workers_cap_and_freeze_flag(server, tmp_path):
    jp = tmp_path / "jobs.jsonl"
    write_jobs(jp, [job(1)])
    with pytest.raises(SystemExit):
        sj.main(["--jobs", str(jp), "--judge", "fake", "--endpoint", server, "--out", str(tmp_path / "o"),
                 "--workers", "4"])
    with pytest.raises(SystemExit):  # a real judge is refused without the freeze confirmation
        sj.main(["--jobs", str(jp), "--judge", "glm", "--endpoint", server, "--out", str(tmp_path / "o")])


def test_prompt_hash_guard(tmp_path):
    j = job(1)
    j["user"] += " tampered"
    jp = tmp_path / "jobs.jsonl"
    write_jobs(jp, [j])
    with pytest.raises(SystemExit):
        sj.load_jobs(jp, None)


# ----------------------------------------------------------------------------- analysis (synthetic raw, real job ids)
def _synthetic_raw(tmp_path):
    import random
    jobs = [json.loads(line) for line in (HERE / "jobs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    raw = tmp_path / "raw"
    raw.mkdir()
    rng = random.Random(1)
    for judge in ("gptoss", "glm"):
        with (raw / f"raw_{judge}.jsonl").open("w", encoding="utf-8") as fh:
            for j in jobs:
                base = 1 if j["variant"] == "A" else 3
                if j["cell_kind"] == "ablated_control":
                    base = 0
                for r in (1, 2, 3):
                    score = base
                    if judge == "glm" and r == 3 and rng.random() < 0.3:
                        score = max(0, base - 1)
                    fh.write(json.dumps({"judge": judge, "study": j["study"], "cell_id": j["cell_id"],
                                         "cell_kind": j["cell_kind"], "variant": j["variant"], "cq_id": j["cq_id"],
                                         "cluster_id": j["cluster_id"], "repeat": r, "valid": True, "status": "ok", "J": score,
                                         "attempts": [{}], "prompt_tokens": 100, "completion_tokens": 10, "latency_s": 1.0,
                                         "started_utc": "2026-10-17T00:00:00+00:00"}) + "\n")
    return raw


def test_analysis_known_structure(tmp_path, monkeypatch):
    import analyze_review6 as an
    monkeypatch.setattr(an, "B", 200)
    raw = _synthetic_raw(tmp_path)
    out = tmp_path / "out"
    assert an.main(["--raw-dir", str(raw), "--out-dir", str(out)]) == 0
    res = json.loads((out / "results.json").read_text(encoding="utf-8"))
    gp = res["judges"]["gptoss"]
    # constructed: A scores 1, B-F score 3 -> A->B = +2 in both studies, other contrasts 0
    assert gp["dev"]["contrasts"]["A->B"]["delta"] == pytest.approx(2.0)
    assert gp["holdout_subgraph"]["contrasts"]["A->B"]["delta"] == pytest.approx(2.0)
    assert gp["dev"]["contrasts"]["B->C"]["delta"] == pytest.approx(0.0)
    assert gp["holdout_subgraph"]["contrasts"]["A->B"]["n_pairs"] == 22
    # identical repeats: agreement 1, ICC 1
    rr = gp["dev"]["run_to_run"]
    assert rr["pairwise_exact_agreement"]["estimate"] == pytest.approx(1.0)
    assert rr["icc_2_1"] == pytest.approx(1.0)
    # perturbed repeat 3 lowers agreement and ICC
    rg = res["judges"]["glm"]["dev"]["run_to_run"]
    assert rg["pairwise_exact_agreement"]["estimate"] < 1.0 and rg["icc_2_1"] < 1.0
    # paper convention: half-up mean of repeats 1 and 2 (3,3 -> 3; 1,1 -> 1)
    assert gp["dev"]["A_to_B_paper_convention_halfup_mean_of_repeats_1_2"]["delta"] == pytest.approx(2.0)
    # controls: ablated -> share J>=2 = 0, preserved -> 1
    assert gp["holdout_control"]["ablated_control"]["mean_share_J_ge_2"] == 0.0
    pres = [json.loads(line) for line in (HERE / "jobs.jsonl").read_text(encoding="utf-8").splitlines()
            if '"preserved_control"' in line]
    assert gp["holdout_control"]["preserved_control"]["mean_share_J_ge_2"] == pytest.approx(
        sum(1 for j in pres if j["variant"] != "A") / len(pres))  # variant A scores 1 in the synthetic data
    # pi-hat computed against the tracked independent labels, and references present
    assert "1" in gp["holdout_subgraph"]["pi_hat"]["independent rater (v3)"]
    assert res["references"]["dev"]["qwen_dev_judge"]["contrasts"]["A->B"]["delta"] == pytest.approx(1.0)
    assert (out / "REPORT.md").read_text(encoding="utf-8").startswith("# REPORT")
    # cost and missing cells
    assert gp["cost"]["all"]["calls"] == 305 * 3 and gp["invalid_or_missing"] == []


def test_icc_helper_edge_cases():
    import numpy as np
    import analyze_review6 as an
    same = np.array([[1, 1, 1], [3, 3, 3], [2, 2, 2.0]])
    assert an.icc_from_matrix(same) == pytest.approx((1.0, 1.0))
    flat = np.array([[2, 2, 2], [2, 2, 2], [2, 2, 2.0]])
    a, b = an.icc_from_matrix(flat)
    assert a != a and b != b  # nan: no between-cell variance


def test_missing_judge_is_reported_not_crashed(tmp_path, monkeypatch):
    import analyze_review6 as an
    monkeypatch.setattr(an, "B", 100)
    raw = _synthetic_raw(tmp_path)
    (raw / "raw_glm.jsonl").unlink()
    out = tmp_path / "out"
    an.main(["--raw-dir", str(raw), "--out-dir", str(out)])
    res = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert res["judges"]["glm"]["note"].startswith("no records")


def test_salvage_sensitivity_only_in_secondary(tmp_path, monkeypatch):
    import analyze_review6 as an
    monkeypatch.setattr(an, "B", 100)
    raw = _synthetic_raw(tmp_path)
    # make two dev records of gptoss invalid: one truncated-with-score prefix, one empty
    path = raw / "raw_gptoss.jsonl"
    recs = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    hit = 0
    for r in recs:
        if r["study"] == "dev" and r["variant"] == "B" and r["cq_id"] == "CQ01" and r["repeat"] in (1, 2):
            r.update(valid=False, status="invalid", J=None,
                     raw_content='{"score": 3, "evidence": ["a", "b", "c' if r["repeat"] == 1 else "")
            hit += 1
    assert hit == 2
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    out = tmp_path / "out"
    an.main(["--raw-dir", str(raw), "--out-dir", str(out)])
    res = json.loads((out / "results.json").read_text(encoding="utf-8"))
    miss = {(m["cell_id"], m["repeat"]) for m in res["judges"]["gptoss"]["invalid_or_missing"]}
    assert ("dev:B:CQ01", 1) in miss and ("dev:B:CQ01", 2) in miss  # primary: nothing salvaged
    assert res["sensitivity_salvage"]["gptoss"]["n_salvaged_scores"] == 1  # only the prefix reply
    assert "## 8. Sensitivity" in (out / "REPORT.md").read_text(encoding="utf-8")
    assert an.SALVAGE_RE.match('{"score": 2, "evid') and not an.SALVAGE_RE.match('{"evidence": [], "score": 2}')
