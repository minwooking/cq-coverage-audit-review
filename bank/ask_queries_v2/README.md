# bank/ask_queries_v2 (addendum 16, frozen before execution)

One standardized SPARQL file per bank CQ (CQB01-CQB36, from `bank/cq_bank_brick_v1.csv`). The
originals in `bank/ask_queries/` are not modified.

- `class=deterministic`: 18 CQs with `ask_expressible = yes` (CQB07-18, 21-24, 32, 33).
- `class=expert`: 18 CQs with `ask_expressible = partial` (CQB01-06, 19, 20, 25-31, 34-36).
- Standardization: every file is an `ASK` form (kept: rdflib evaluates all 36 as ASK, so no
  SELECT-existence rewrite is needed), the same eight PREFIX lines plus `rdf:`, a two-line
  provenance header, and the `a` verb written as `rdf:type` (CQB19-24) so that the predicate map can
  see it. No other change; bodies are otherwise byte-identical to `bank/ask_queries/`.
- The files use Brick vocabulary only. Term mapping (steps 1-6 of `ask_alignment.py`) and the
  predicate map (step 7, `harness/real_run/ask_alignment_v2/predicate_map.csv`) are applied at run
  time to a copy of the query text, never here.
- `SHA256.txt` lists the hash of each file.
