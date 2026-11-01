"""Offline tests for run_natural_judges.py with a fake OpenAI-compatible server (AI-generated; no network beyond localhost)."""
import json, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_natural_judges as rj  # noqa: E402

MODE = {"fail": False, "calls": 0, "auth": set(), "maxw": 0, "cur": 0}
LOCK = threading.Lock()


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n))
        with LOCK:
            MODE["auth"].add(self.headers.get("Authorization"))
        if self.path == "/tokenize":
            out = {"count": sum(len(m["content"]) for m in body["messages"]) // 4}
        else:
            with LOCK:
                MODE["calls"] += 1
                MODE["cur"] += 1
                MODE["maxw"] = max(MODE["maxw"], MODE["cur"])
            time.sleep(0.01)
            with LOCK:
                MODE["cur"] -= 1
            if MODE["fail"]:
                self.send_response(500); self.end_headers(); self.wfile.write(b"boom"); return
            out = {"choices": [{"message": {"content": json.dumps({"score": 2, "evidence": "x"})}, "finish_reason": "stop"}],
                   "usage": {"prompt_tokens": 100, "completion_tokens": 7}}
        data = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(data)


def serve():
    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/v1"


def lines(p):
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def test_all():
    rj.sj.time.sleep = lambda s: None  # skip retry backoff
    srv, ep = serve()
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        assert rj.main(["--judge", "fake", "--test", "--endpoint", ep, "--corpus", "both", "--repeats", "2", "--out-dir", str(td)]) == 0
        nat = lines(td / "raw_fake_natural.jsonl"); tpl = lines(td / "raw_fake_template.jsonl")
        assert len(nat) == 72 * 2 and len(tpl) == 54 * 2, (len(nat), len(tpl))
        assert all(r["valid"] and r["J"] == 2 for r in nat + tpl)
        assert MODE["maxw"] <= 3, MODE["maxw"]
        before = MODE["calls"]
        # resume: nothing new is sent
        assert rj.main(["--judge", "fake", "--test", "--endpoint", ep, "--corpus", "both", "--repeats", "2", "--out-dir", str(td)]) == 0
        assert MODE["calls"] == before
        # reuse: records of the right judge with identical prompt hash are copied, not re-scored
        td2 = Path(td) / "reuse"
        jobs = rj.sj.load_jobs(rj.JOBS["template"], None)
        src = td / "a26.jsonl"
        src.write_text("\n".join(json.dumps({"judge": "fake", "study": "holdout_subgraph", "cell_id": j["cell_id"], "repeat": r, "valid": True,
                                             "J": 1, "prompt_sha256": j["prompt_sha256"], "status": "ok"}) for j in jobs[:5] for r in (1, 2)) + "\n")
        before = MODE["calls"]
        assert rj.main(["--judge", "fake", "--test", "--endpoint", ep, "--corpus", "template", "--repeats", "2", "--out-dir", str(td2), "--reuse-raw", str(src)]) == 0
        t = lines(td2 / "raw_fake_template.jsonl")
        assert sum(1 for r in t if r.get("reused_from_addendum26")) == 10
        assert MODE["calls"] - before == 54 * 2 - 10
        # consecutive endpoint failures stop the run
        MODE["fail"] = True
        td3 = Path(td) / "fail"
        assert rj.main(["--judge", "fake", "--test", "--endpoint", ep, "--corpus", "natural", "--repeats", "1", "--out-dir", str(td3)]) == 0
        man = json.loads(next(td3.glob("MANIFEST_run_*.json")).read_text())
        assert man["abort_reason"] == "consecutive_endpoint_failures", man["abort_reason"]
        assert len(lines(td3 / "raw_fake_natural.jsonl")) < 72
        MODE["fail"] = False
        # budget stop
        td4 = Path(td) / "budget"
        assert rj.main(["--judge", "fake", "--test", "--endpoint", ep, "--corpus", "natural", "--repeats", "1", "--budget", "500", "--out-dir", str(td4)]) == 0
        man = json.loads(next(td4.glob("MANIFEST_run_*.json")).read_text())
        assert man["abort_reason"] == "token_budget"
        # qwenflash uses a bearer key, others send 'none'
        MODE["auth"].clear()
        td5 = Path(td) / "auth"
        rj.sj.JUDGES["fake2"] = dict(rj.sj.JUDGES["qwenflash"])  # not used; keeps table intact
    srv.shutdown()


if __name__ == "__main__":
    test_all(); print("tests passed")
