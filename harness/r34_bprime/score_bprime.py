#!/usr/bin/env python3
"""E2 steps 2-3: score A, B, C, B' with ONE judge (local/qwen-next-flash via <internal-proxy>) in a FRESH cache.
usage: score_bprime.py <bank_json> <tag:ko|en> [--dry-run]
Writes harness/r34_bprime/eval_<tag>.json|md and token_log_<tag>.json. NUM_JUDGES=2, workers<=3."""
import json, sys, threading
from pathlib import Path
from chunktograph import eval_ab
from chunktograph.llm import LLMClient, loads_lenient

ROOT = Path(__file__).resolve().parents[4]          # repo root
OUT = Path(__file__).resolve().parent
bank, tag = sys.argv[1], sys.argv[2]
dry = "--dry-run" in sys.argv
BUDGET = 1_500_000
lock = threading.Lock(); tok = {"calls": 0, "prompt": 0, "completion": 0}

class Metered(LLMClient):
    def _meter(self, resp):
        u = getattr(resp, "usage", None)
        with lock:
            tok["calls"] += 1
            if u: tok["prompt"] += u.prompt_tokens; tok["completion"] += u.completion_tokens
            if tok["prompt"] + tok["completion"] > BUDGET: raise SystemExit("TOKEN BUDGET EXCEEDED")
    def chat_json(self, system, user, max_tokens=1024):
        resp = self._client.chat.completions.create(model=self.model, messages=[{"role":"system","content":system},{"role":"user","content":user}], temperature=0.0, max_tokens=max_tokens, response_format={"type":"json_object"})
        self._meter(resp); return loads_lenient(resp.choices[0].message.content)
    def chat_text(self, system, user, max_tokens=2048):
        resp = self._client.chat.completions.create(model=self.model, messages=[{"role":"system","content":system},{"role":"user","content":user}], temperature=0.0, max_tokens=max_tokens)
        self._meter(resp); return resp.choices[0].message.content or ""

eval_ab.CACHE_DIR = OUT / f"cache_{tag}" / "eval"; eval_ab.CACHE_DIR.mkdir(parents=True, exist_ok=True)
paths = {"A": ROOT/"output_mfg/ontology_A.ttl", "B": ROOT/"output_mfg/ontology_B.ttl",
         "C": ROOT/"output_mfg/ontology_C.ttl", "Bp": ROOT/"output_mfg/r34_bprime/ontology_Bp.ttl"}
for p in paths.values(): assert p.exists(), p
llm = Metered("http://localhost:PORT/v1", "local/qwen-next-flash", "none", timeout=300.0)
print(f"[judge] <internal-proxy> local/qwen-next-flash NUM_JUDGES={eval_ab.NUM_JUDGES} bank={bank} cache={eval_ab.CACHE_DIR}")
if dry: print("dry-run: ok", {k: v.exists() for k, v in paths.items()}); sys.exit(0)
res = eval_ab.run_abc({k: str(v) for k, v in paths.items()}, bank, llm, OUT/f"eval_{tag}.json", OUT/f"eval_{tag}.md", concurrency=3)
(OUT/f"token_log_{tag}.json").write_text(json.dumps(tok, indent=1))
print("[done]", tok, {n: round(res["aggregate"][n]["cq_coverage_pct"],1) for n in res["aggregate"]["ontologies"]})
