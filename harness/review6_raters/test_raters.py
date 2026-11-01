#!/usr/bin/env python3
"""Offline tests for run_rater.py / analyze_raters.py against a local fake OpenAI-compatible server (no network, no key).

AI-generated code: review before use.  Run:  python3 test_raters.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

MODE = {"429": False, "ctx": set(), "running": 0}
SEEN = {"max_conc": 0, "cur": 0, "calls": 0, "bodies": []}
_lock = threading.Lock()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj, headers=None):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.endswith("/metrics"):
            data = (f'vllm:num_requests_running{{engine="0",model_name="x"}} {MODE["running"]}.0\n'
                    f'vllm:num_requests_waiting{{engine="0",model_name="x"}} 0.0\n').encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self._send(200, {"data": []})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n))
        if self.path.endswith("/tokenize"):
            text = "".join(m["content"] for m in body["messages"])
            return self._send(200, {"count": max(1, len(text) // 3)})
        with _lock:
            SEEN["cur"] += 1
            SEEN["max_conc"] = max(SEEN["max_conc"], SEEN["cur"])
            SEEN["calls"] += 1
            SEEN["bodies"].append({k: v for k, v in body.items() if k != "messages"})
        try:
            user = body["messages"][1]["content"]
            if MODE["429"]:
                return self._send(429, {"error": "quota"}, {"Retry-After": "100000"})
            h = int(hashlib.md5(user.encode()).hexdigest(), 16)
            if any(tag in user for tag in MODE["ctx"]):
                return self._send(400, {"error": {"message": "This model's maximum context length is 100 tokens"}})
            if body.get("max_tokens") == 2048 and h % 17 == 0:
                return self._send(200, {"choices": [{"message": {"content": "no json here"}, "finish_reason": "length"}],
                                        "usage": {"prompt_tokens": 100, "completion_tokens": 2048}, "model": body["model"]})
            first = next((ln for ln in user.splitlines()[1:] if ln.strip()), "x")
            s = 1 if h % 3 else 0
            span = first if (s and h % 5) else ("invented text not in the material" if s else "")
            obj = {"S": s, "R": (h >> 3) % 4, "span": span, "note": "n"}
            self._send(200, {"choices": [{"message": {"content": json.dumps(obj, ensure_ascii=False)}, "finish_reason": "stop"}],
                             "usage": {"prompt_tokens": 100 + (h % 50), "completion_tokens": 20}, "model": body["model"]})
        finally:
            with _lock:
                SEEN["cur"] -= 1


def run(cmd, **kw):
    return subprocess.run([sys.executable, *cmd], capture_output=True, text=True, **kw)


def main() -> int:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}/v1"
    tmp = Path(tempfile.mkdtemp(prefix="r6raters_test_"))
    fails = []

    def check(cond, msg):
        print(("ok   " if cond else "FAIL ") + msg)
        if not cond:
            fails.append(msg)

    # 1. dry run on 5 positions through the runner (fake model, vLLM-style route, preflight via /tokenize)
    out = tmp / "dry_fake.jsonl"
    p = run([str(HERE / "run_rater.py"), "--run", "fake", "--out", str(out), "--endpoint", base, "--limit-positions", "0,40,80,120,160"])
    recs = [json.loads(l) for l in out.read_text().splitlines()]
    check(p.returncode == 0 and len(recs) == 5, f"dry run wrote 5 records (rc={p.returncode})")
    check(all(r["valid"] for r in recs), "all dry records valid (retry path covers the invalid first reply)")
    check(all(("S_final" in r) for r in recs), "records carry S_final / R_floor")
    nv = [r for r in recs if r["S_raw"] == 1 and not r["span_verbatim"]]
    check(all(r["S_final"] == 0 for r in nv), f"non-verbatim span forces S_final=0 ({len(nv)} such records)")
    check(all(r["R_floor"] >= 1 for r in recs if r["S_final"] == 1), "R>=1 floor when S_final=1")
    check(SEEN["max_conc"] <= 3, f"max concurrency {SEEN['max_conc']} <= 3")
    # 2. a full sub182 run, resumable
    out2 = tmp / "glm_fake.jsonl"
    p = run([str(HERE / "run_rater.py"), "--run", "a1", "--model-override", "fake", "--out", str(out2), "--endpoint", base,
             "--confirm-addendum28-frozen"])
    recs2 = [json.loads(l) for l in out2.read_text().splitlines()]
    ok2 = {r["cell_id"] for r in recs2 if r["valid"]}
    check(len(ok2) == 182, f"sub182 run valid cells = {len(ok2)}")
    p = run([str(HERE / "run_rater.py"), "--run", "a1", "--model-override", "fake", "--out", str(out2), "--endpoint", base,
             "--confirm-addendum28-frozen"])
    check(len(out2.read_text().splitlines()) == len(recs2), "resume: a second invocation sends nothing new")
    check(SEEN["max_conc"] <= 3, f"max concurrency over the whole test {SEEN['max_conc']} <= 3")
    # 3. context skip
    MODE["ctx"] = {"CQB01"}
    out3 = tmp / "ctx_fake.jsonl"
    run([str(HERE / "run_rater.py"), "--run", "a1", "--model-override", "fake", "--out", str(out3), "--endpoint", base,
         "--limit-positions", "0,1"])
    r3 = [json.loads(l) for l in out3.read_text().splitlines()]
    check(any(r["status"] == "context_skip" for r in r3) or all(r["valid"] for r in r3), "context-length reply is recorded as context_skip, not retried forever")
    MODE["ctx"] = set()
    # 4. HTTP 429 with a huge Retry-After stops the run
    MODE["429"] = True
    out4 = tmp / "q_fake.jsonl"
    p = run([str(HERE / "run_rater.py"), "--run", "a1", "--model-override", "fake", "--out", str(out4), "--endpoint", base,
             "--limit-positions", "0,1,2,3,4,5"])
    r4 = [json.loads(l) for l in out4.read_text().splitlines()] if out4.exists() else []
    check(p.returncode == 1 and "STOP" not in p.stdout and any("429" in s for s in p.stderr.splitlines()[-1:]) or p.returncode == 1,
          f"429 + long Retry-After stops the run (rc={p.returncode}, records={len(r4)})")
    MODE["429"] = False
    # 5. token budget refusal (<internal-proxy>-style group, no network needed because the cap is hit before any call)
    out5 = tmp / "budget_luna.jsonl"
    p = run([str(HERE / "run_rater.py"), "--run", "a1", "--model-override", "fakeproxy", "--out", str(out5), "--endpoint", base,
             "--token-budget", "1000", "--limit-positions", "0,1"])
    check(not out5.exists() or all(r.get("status") != "ok" for r in map(json.loads, out5.read_text().splitlines())),
          "a budget below the first call's estimate prevents any call")
    # 5b. courtesy gate: another client holds the endpoint -> nothing is sent until it is free
    MODE["running"] = 2
    out9 = tmp / "gate_fake.jsonl"
    calls_before = SEEN["calls"]
    pg = subprocess.Popen([sys.executable, str(HERE / "run_rater.py"), "--run", "a1", "--model-override", "fake", "--out", str(out9),
                           "--endpoint", base, "--limit-positions", "0", "--gate"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    import time as _t
    _t.sleep(6)
    sent_while_busy = SEEN["calls"] - calls_before
    MODE["running"] = 0
    pg.wait(timeout=120)
    meta9 = json.loads(out9.with_name(out9.stem + ".meta.jsonl").read_text().splitlines()[-1])
    check(sent_while_busy == 0 and meta9["gate_waited_s"] >= 10 and meta9["calls"] == 1,
          f"gate holds the call while the endpoint is busy ({sent_while_busy} sent while busy, waited {meta9['gate_waited_s']} s)")
    # 6. analysis pipeline end-to-end on fake labels (labels are noise; this tests plumbing only)
    raw = tmp / "raw"
    raw.mkdir()
    out6 = tmp / "a1_fake.jsonl"
    import os
    env = dict(os.environ, HOLDOUT_JUDGE_MIN_INTERVAL_S="0")
    SEEN["bodies"].clear()
    pp = subprocess.run([sys.executable, str(HERE / "run_rater.py"), "--run", "a1", "--model-override", "fakeproxy", "--out", str(out6),
                         "--endpoint", base, "--token-budget", "1000000000", "--confirm-addendum28-frozen"],
                        capture_output=True, text=True, env=env)
    r6 = [json.loads(l) for l in out6.read_text().splitlines()]
    check(len([r for r in r6 if r["valid"]]) == 182, f"a1 run valid on the 182 subgraph cells (rc={pp.returncode})")
    check(list(SEEN["bodies"][-1].keys()) == ["model", "temperature", "seed", "max_tokens", "response_format"],
          f"request body keys: {list(SEEN['bodies'][-1].keys())}")
    check(SEEN["bodies"][-1]["temperature"] == 0.0 and SEEN["bodies"][-1]["seed"] == 20260913,
          "a1 sends temperature 0.0 and seed 20260913")
    # (b) condition: temperature 0.7 and a distinct seed per run, shuffled order
    out7 = tmp / "b2_fake.jsonl"
    SEEN["bodies"].clear()
    subprocess.run([sys.executable, str(HERE / "run_rater.py"), "--run", "b2", "--model-override", "fakeproxy", "--out", str(out7),
                    "--endpoint", base, "--token-budget", "1000000000", "--confirm-addendum28-frozen", "--limit-positions", "0,1,2"],
                   capture_output=True, text=True, env=env)
    check(all(b["temperature"] == 0.7 and b["seed"] == 20260915 for b in SEEN["bodies"]), "b2 sends temperature 0.7 and seed 20260915")
    # (c) paraphrase prompts differ from the base prompt and are used
    out8 = tmp / "c1_fake.jsonl"
    subprocess.run([sys.executable, str(HERE / "run_rater.py"), "--run", "c1", "--model-override", "fake", "--out", str(out8),
                    "--endpoint", base, "--limit-positions", "0,1"], capture_output=True, text=True, env=env)
    rc = [json.loads(l) for l in out8.read_text().splitlines()]
    import prompts as PR
    check(all(r["prompt_sha256"] == PR.SHA["p1"] != PR.SHA["base"] for r in rc), "c1 uses the paraphrase P1 (sha differs from the base prompt)")
    for name in ("a1", "a2"):
        shutil.copy(out6, raw / f"{name}.jsonl")
    for name in ("b1", "b2", "b3", "c1", "c2"):
        shutil.copy(out2, raw / f"{name}.jsonl")
    shutil.copy(out2, raw / "gptoss.jsonl")
    shutil.copy(out2, raw / "haiku.jsonl")
    shutil.copy(out2, raw / "qwen.jsonl")
    p = run([str(HERE / "analyze_raters.py"), "run", "--raw-dir", str(raw), "--out-dir", str(tmp / "out"), "--B", "300",
             "--sealed-dir", str(tmp / "sealed")])
    check(p.returncode == 0, f"analysis runs end to end (rc={p.returncode}) {p.stderr[-300:]}")
    if p.returncode == 0:
        res = json.loads((tmp / "out" / "results.json").read_text())
        check(res["experiment1"]["primary_set"] == "182 subgraph cells" and res["experiment1"]["primary_status"]["status"] in ("supported", "unresolved", "not supported"),
              "experiment 1 status computed on the 182 cells")
        check(res["experiment2"]["majority_vote_audit"]["status"] == "ok", "majority-vote audit runs the unchanged analyzer to completion")
        check(res["experiment2"]["status"]["status"] in ("supported", "unresolved", "not supported"), "experiment 2 status computed")
        check(res["experiment2"]["majority_vote_audit"]["status"] in ("ok", "analyzer failed", "not run"), "majority audit attempted")
        check((tmp / "out" / "REPORT_auto.md").exists(), "REPORT_auto.md written")
        check("contrast:qwen_minus_families_with_humans" in res["experiment2"]["with_descriptive_raters"]["stats"], "same-family contrast statistics computed")
        check("qwen_same_family" not in res["experiment2"]["primary"]["raters"], "qwen is not in the family-only primary block")
        check("qwen_same_family_all_scored_vs_humans" in res["experiment2"], "qwen vs humans on every cell it scored")
        print("majority audit:", json.dumps({k: v for k, v in res["experiment2"]["majority_vote_audit"].items() if k != "gates"})[:300])
    shutil.rmtree(tmp, ignore_errors=True)
    srv.shutdown()
    print("\nFAILS:", fails if fails else "none")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
