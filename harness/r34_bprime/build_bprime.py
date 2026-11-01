#!/usr/bin/env python3
"""E2 step 1: rebuild stage 4 from the existing triples.json into a NEW dir.
usage: build_bprime.py <triples.json> <typing_cache_src> <out_dir> [--tag NAME]
Run with PYTHONPATH=<src tree to test>. Counts LLM calls (should be 0 on cache hit)."""
import json, shutil, sys
from pathlib import Path
from chunktograph import stage4_ontology as s4
from chunktograph.config import DEFAULT_BASE_IRI
from chunktograph.llm import LLMClient
tri, cache_src, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
cache = out / ".cache_typing"
if not cache.exists(): shutil.copytree(cache_src, cache)
s4.TYPING_CACHE_DIR = cache
class Counting(LLMClient):
    calls = 0
    def chat_json(self, *a, **k):
        Counting.calls += 1; return super().chat_json(*a, **k)
llm = Counting("http://localhost:PORT/v1", "local/qwen-next-flash", "none", timeout=180.0)
g = s4.run(json.loads(tri.read_text()), DEFAULT_BASE_IRI, out / "ontology.ttl", llm=llm)
print(f"built {len(g)} triples; llm_calls={Counting.calls}; src={s4.__file__}")
# split into tbox/abox like the pipeline's `split` command (needed for the schema-faithful L2 view)
from chunktograph import split as split_mod
n_t, n_a = split_mod.split_file(out/"ontology.ttl", out/"tbox.ttl", out/"abox.ttl")
if "--tag" in sys.argv:
    t = sys.argv[sys.argv.index("--tag")+1]
    for k in ("ontology","tbox","abox"): (out/f"{k}_{t}.ttl").write_text((out/f"{k}.ttl").read_text())
print("split", n_t, n_a)
