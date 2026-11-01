#!/usr/bin/env python3
"""Offline tests of addendum 30 (review10_llm_labels): personas, runner (fake OpenAI-compatible server, no network, no
key), parser and span check, consistency rules, and the analysis (synthetic data only).  AI-generated; review before use.

Run:  python3 test_ensemble.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import personas as PS  # noqa: E402

SEEN = {"max_conc": 0, "cur": 0, "calls": 0, "bodies": [], "systems": set()}
MODE = {"reject_seed": False, "junk": False}
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
        data = b'vllm:num_requests_running{engine="0"} 0.0\nvllm:num_requests_waiting{engine="0"} 0.0\n'
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n))
        with _lock:
            SEEN["cur"] += 1
            SEEN["max_conc"] = max(SEEN["max_conc"], SEEN["cur"])
            SEEN["calls"] += 1
            SEEN["bodies"].append({k: v for k, v in body.items() if k != "messages"})
            SEEN["systems"].add(hashlib.sha256(body["messages"][0]["content"].encode()).hexdigest())
        try:
            if MODE["junk"]:
                return self._send(200, {"choices": [{"message": {"content": "not json"}, "finish_reason": "stop"}],
                                        "usage": {"prompt_tokens": 100, "completion_tokens": 5}})
            if MODE["reject_seed"] and "seed" in body:
                return self._send(400, {"error": {"message": "unknown field: seed"}})
            user = body["messages"][1]["content"]
            sysm = body["messages"][0]["content"]
            h = int(hashlib.md5((user + sysm + str(body.get("seed"))).encode()).hexdigest(), 16)
            if body.get("max_tokens") == 2048 and h % 23 == 0:
                return self._send(200, {"choices": [{"message": {"content": "no json here"}, "finish_reason": "length"}],
                                        "usage": {"prompt_tokens": 100, "completion_tokens": 2048}})
            first = next((ln for ln in user.splitlines()[1:] if ln.strip()), "x")
            s = 1 if h % 3 else 0
            span = first if (s and h % 5) else ("invented text not in the material" if s else "")
            obj = {"S": s, "R": (h >> 3) % 4, "span": span, "note": "n"}
            self._send(200, {"choices": [{"message": {"content": json.dumps(obj, ensure_ascii=False)}, "finish_reason": "stop"}],
                             "usage": {"prompt_tokens": 100 + (h % 50), "completion_tokens": 20}})
        finally:
            with _lock:
                SEEN["cur"] -= 1


def run(cmd, **kw):
    return subprocess.run([sys.executable, *cmd], capture_output=True, text=True, **kw)


def main() -> int:
    fails: list[str] = []

    def check(cond, msg):
        print(("ok   " if cond else "FAIL ") + msg)
        if not cond:
            fails.append(msg)

    # ---- 1. personas: five, criteria text identical, preambles quoted verbatim in PLAN.md
    check(PS.PERSONAS == ["domain", "ontology", "auditor", "kgqa", "generalist"], "five personas in the fixed order")
    check(all(PS.SYSTEM[p].endswith(PS.BASE) for p in PS.PERSONAS), "every system prompt ends with the identical criteria text")
    check(len({PS.PREAMBLE[p] for p in PS.PERSONAS}) == 5, "the five preambles differ")
    check(PS.BASE_SHA256 == "efb8a43fd89e6281777eb97047a91495c1aaba22ef96148735125c33db04f769", "criteria text = the S21 prompt (sha256)")
    plan = (HERE / "PLAN.md").read_text(encoding="utf-8")
    check(all(PS.PREAMBLE[p] in plan and PS.PREAMBLE_SHA256[p] in plan for p in PS.PERSONAS), "PLAN.md quotes every preamble and its sha256")

    # ---- 2. parser and span check (the functions the runner uses)
    import rater_luna as rl
    import run_rater as RR
    ok, _ = rl.parse_content('```json\n{"S": 1, "R": 3, "span": "a b", "note": ""}\n```')
    check(ok == {"S": 1, "R": 3, "span": "a b", "note": ""}, "parser accepts a fenced JSON object")
    ok, _ = rl.parse_content('Sure. {"S": 0, "R": 1, "span": "", "note": "x"} done')
    check(ok is not None and ok["S"] == 0, "parser extracts the object from surrounding text")
    for bad in ("", "no json", '{"S": 2, "R": 1}', '{"S": 1, "R": 4}', '{"S": "x", "R": 1}', "[1, 2]"):
        check(rl.parse_content(bad)[0] is None, f"parser rejects {bad!r}")
    f = RR.finalize({"S": 1, "R": 0, "span": "foo   bar", "note": ""}, "xx foo bar yy")
    check(f["S_final"] == 1 and f["R_floor"] == 1 and f["span_verbatim"] is True, "verbatim span (whitespace-normalised) keeps S=1, R floor 1")
    f = RR.finalize({"S": 1, "R": 3, "span": "not there", "note": ""}, "xx foo bar yy")
    check(f["S_final"] == 0 and f["S_raw"] == 1 and f["span_verbatim"] is False, "non-verbatim span -> S_final 0")
    f = RR.finalize({"S": 1, "R": 3, "span": "", "note": ""}, "xx")
    check(f["S_final"] == 0, "S=1 with an empty span -> S_final 0")

    # ---- 3. runner on the fake server
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}/v1"
    tmp = Path(tempfile.mkdtemp(prefix="r10_test_"))
    out = tmp / "fake_t1.jsonl"
    p = run([str(HERE / "run_ensemble.py"), "--model", "fake", "--tiers", "1", "--out", str(out), "--endpoint", base, "--limit-cells", "4", "--gate"])
    recs = [json.loads(l) for l in out.read_text().splitlines()]
    check(p.returncode == 0, f"runner exit 0 (rc={p.returncode})")
    check(len(recs) == 100 and all(r["status"] in ("ok", "invalid") for r in recs), f"4 cells x 25 slots = 100 records ({len(recs)})")
    check({(r["persona"], r["seed"]) for r in recs} == {(pp, s) for pp in PS.PERSONAS for s in (1, 2, 3, 4, 5)}, "every (persona, seed) slot occurs")
    check(all(r["cell_id"].startswith("primary:") for r in recs), "records carry the cell id")
    forbidden = ("127.0.0.1", "localhost", f":{port}", "Authorization", "Bearer", "ssh ")
    check(not any(any(w in json.dumps(r) for w in forbidden) for r in recs), "records contain no address, port or key")
    check(all(b.get("temperature") == 0.7 for b in SEEN["bodies"]), "every request has temperature 0.7")
    seeds_sent = {b.get("seed") for b in SEEN["bodies"]}
    check(seeds_sent == {1, 2, 3, 4, 5}, f"seed parameter 1..5 sent ({sorted(s for s in seeds_sent if s)})")
    check(len(SEEN["systems"]) == 5, f"five distinct system prompts sent ({len(SEEN['systems'])})")
    check(SEEN["max_conc"] <= 3, f"max concurrency {SEEN['max_conc']} <= 3")
    nv = [r for r in recs if r["status"] == "ok" and r["S_raw"] == 1 and not r["span_verbatim"]]
    check(all(r["S_final"] == 0 for r in nv), f"non-verbatim span forces S_final=0 ({len(nv)} records)")
    n0 = len(recs)
    p = run([str(HERE / "run_ensemble.py"), "--model", "fake", "--tiers", "1", "--out", str(out), "--endpoint", base, "--limit-cells", "4"])
    check(len(out.read_text().splitlines()) == n0, "resume: a second invocation sends nothing new")
    p = run([str(HERE / "run_ensemble.py"), "--model", "fake", "--tiers", "1", "--out", str(out), "--endpoint", base, "--limit-cells", "6"])
    n1 = len(out.read_text().splitlines())
    check(n1 == n0 + 50, f"resume with a larger limit sends only the 2 new cells ({n1 - n0} new records)")
    # context skip: the 6 fallback cells (65,536-token window)
    out2 = tmp / "fake_t1_all.jsonl"
    p = run([str(HERE / "run_ensemble.py"), "--model", "fake", "--tiers", "1", "--out", str(out2), "--endpoint", base, "--limit-cells", "188"], timeout=900)
    r2 = [json.loads(l) for l in out2.read_text().splitlines()]
    sk = sorted(r["cell_id"] for r in r2 if r["status"] == "context_skip")
    check(sk == sorted(["primary:A:CQB27"] + [f"primary:{v}:CQB32" for v in "BCDEF"]), f"the 6 full-view fallback cells are context_skip ({len(sk)})")
    ok_cells = {r["cell_id"] for r in r2 if r["status"] in ("ok", "invalid")}
    check(len(ok_cells) == 182 and len([r for r in r2 if r["status"] in ("ok", "invalid")]) == 182 * 25, "182 cells x 25 slots evaluated")
    # wall-clock cap: no new cell starts
    out3 = tmp / "fake_cap.jsonl"
    run([str(HERE / "run_ensemble.py"), "--model", "fake", "--tiers", "1", "--out", str(out3), "--endpoint", base, "--limit-cells", "10", "--max-wall-s", "0.0001", "--workers", "1"])
    check((not out3.exists()) or len(out3.read_text().splitlines()) <= 25, "wall-clock cap stops new cells")
    # seed rejected by the endpoint -> omitted and recorded
    MODE["reject_seed"] = True
    out4 = tmp / "fake_noseed.jsonl"
    run([str(HERE / "run_ensemble.py"), "--model", "fake", "--tiers", "1", "--out", str(out4), "--endpoint", base, "--limit-cells", "1"])
    r4 = [json.loads(l) for l in out4.read_text().splitlines()]
    meta = [json.loads(l) for l in (tmp / "fake_noseed.meta.jsonl").read_text().splitlines()]
    check(len(r4) == 25 and all(r["status"] in ("ok", "invalid") for r in r4) and meta[-1]["seed_sent"] is False and meta[-1]["seed_note"], "rejected seed is omitted, recorded in the run metadata")
    MODE["reject_seed"] = False
    # unparsable replies: three attempts, then the slot is invalid and terminal (not re-sent on resume)
    MODE["junk"] = True
    out6 = tmp / "fake_junk.jsonl"
    run([str(HERE / "run_ensemble.py"), "--model", "fake", "--tiers", "1", "--out", str(out6), "--endpoint", base, "--limit-cells", "1"])
    r6 = [json.loads(l) for l in out6.read_text().splitlines()]
    check(len(r6) == 25 and all(r["status"] == "invalid" and r["attempts"] == 3 for r in r6), "junk replies: 3 attempts, slot invalid")
    run([str(HERE / "run_ensemble.py"), "--model", "fake", "--tiers", "1", "--out", str(out6), "--endpoint", base, "--limit-cells", "1"])
    check(len(out6.read_text().splitlines()) == 25, "invalid slots are terminal: not re-sent on resume")
    MODE["junk"] = False
    # pilot: 2 cells x 5 personas x seed 1
    out5 = tmp / "fake_pilot.jsonl"
    run([str(HERE / "run_ensemble.py"), "--model", "fake", "--tiers", "1", "--out", str(out5), "--endpoint", base, "--pilot"])
    r5 = [json.loads(l) for l in out5.read_text().splitlines()]
    check(len(r5) == 10 and {r["seed"] for r in r5} == {1}, f"pilot = 10 calls, seed 1 ({len(r5)})")
    # amendment A1: several tiers from one shared queue, per-tier raw files, internal tier in raw_internal/
    if (HERE / "manifests" / "dev.json").exists():
        import os
        rawdir = tmp / "rawdir"
        env = dict(os.environ, R10_RAW_DIR=str(rawdir))
        p = subprocess.run([sys.executable, str(HERE / "run_ensemble.py"), "--model", "fake", "--tiers", "1,3c,3d", "--endpoint", base,
                            "--limit-cells", "2", "--workers", "8", "--progress", str(tmp / "prog.md"), "--report-every-s", "1"],
                           capture_output=True, text=True, env=env)
        names = sorted(f.name for d in rawdir.iterdir() for f in d.iterdir() if f.name.endswith("_t1.jsonl") or f.name.endswith("_t3c.jsonl") or f.name.endswith("_t3d.jsonl"))
        check(p.returncode == 0 and names == ["fake_t1.jsonl", "fake_t3c.jsonl", "fake_t3d.jsonl"], f"multi-tier run writes one file per tier ({names})")
        check((rawdir / "raw_internal" / "fake_t3d.jsonl").exists() and not (rawdir / "raw" / "fake_t3d.jsonl").exists(), "second-domain tier goes to raw_internal/")
        n3c = len((rawdir / "raw" / "fake_t3c.jsonl").read_text().splitlines())
        check(n3c == 50, f"tier 3c: 2 cells x 25 slots ({n3c})")
        prog = (tmp / "prog.md").read_text()
        check("tier=3c finished" in prog and "ETA=" in prog and "rate=" in prog, "progress file has tier-finished and rate/ETA lines")
        check(SEEN["max_conc"] <= 8, f"concurrency {SEEN['max_conc']} <= the 8 requested workers")
        check(subprocess.run([sys.executable, str(HERE / "run_ensemble.py"), "--model", "fake", "--tiers", "1", "--endpoint", base, "--workers", "33"],
                             capture_output=True, text=True, env=env).returncode != 0, "more than 32 workers is refused")
    # tier 2 sets
    import cells as C
    check((len(C.load_tier("1")), len(C.load_tier("2a")), len(C.load_tier("2b"))) == (188, 28, 72), "tier sizes 188 / 28 / 72")
    order = C.order(C.load_tier("1"))
    check(order == C.order(C.load_tier("1")) and sorted(order) == sorted(r["cell_id"] for r in C.load_tier("1")), "cell order is a fixed permutation")

    # ---- 4. analysis (synthetic data)
    import analyze as A
    fails += A.run_selftests(check)

    print("ALL OK" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
