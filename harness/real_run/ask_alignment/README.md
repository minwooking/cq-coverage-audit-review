# ASK oracle after a mechanical ct: -> brick: alignment (exploratory, post hoc)

**Status: EXPLORATORY and POST HOC.** The alignment in this directory was designed and run on
2026-10-09, *after* the holdout judge scores and the AH labels were known. It is not
registered, feeds no gate (G1-G8), and no number here may be reported as a pre-registered
result. The manuscript must disclose that the term alignment was built after the results were
known. The AH labels (`A`) are LLM-assisted (AI-drafted, author-revised), not independent human
labels; the judge `J` is gemini-3.6-flash.

Purpose: PREREG.md section 7 (L894-937) records that the 18 `ask_expressible == yes` bank
queries return `false` on all 6 variant graphs (108/108) because the pipeline mints
`ct:` = `http://example.org/chunktograph#` terms (written `ex:` in the Turtle files) while the
queries use `brick:`. This rerun removes that artifact mechanically and asks what is left of
the only judge-independent, label-free referent the paper has.

## Command

```
cd <worktree root>
PYTHONPATH=$PWD/src <repo>/.venv/bin/python \
  paper/access2026/harness/real_run/ask_alignment/ask_alignment.py
```

About 15 s, deterministic (no timestamps, sorted keys; two runs gave byte-identical outputs).
Tests: `PYTHONPATH=$PWD/src .venv/bin/python -m pytest paper/access2026/harness -q`.

## What it does

1. **Mapping (per variant).** For each variant graph, every Brick-side term used by the 18
   queries (52 `brick:`, 1 `rec:`, 1 `qudt:` = 54 terms) is matched to `ct:` terms of *that
   graph* by deterministic rules, first rule with a candidate decides:
   `local_exact` > `local_normalized` (camelCase / `_` / `-` / case) > `local_joined`
   (token boundaries dropped: `hasPoint` = `haspoint`) > `label` (Brick rdfs:label /
   skos:prefLabel from the frozen snapshot = ct rdfs:label / skos:prefLabel) > `label_to_local`
   > `ns_prefixed_local` (`brick:hasPoint` -> `brick-haspoint` / `brick_hasPoint`).
   One candidate = `mapped`; several at the deciding rule = `ambiguous`; none = `unmapped`.
   Candidates found only by lower-priority rules are kept as alternates. `mapping.csv` has one
   row per (variant, Brick term): rule, chosen ct IRI, candidates, alternates, CQs using it.
   No LLM, no manual edit.
2. **Rewrite queries, not graphs.** Brick-side IRIs in each query become the mapped ct IRIs. A
   query with any unmapped or ambiguous term in a variant is `not_evaluable` there and is never
   counted as false. Each rewritten query is run with rdflib on the variant's graph.
3. **Join** to J and A of the primary cells (`per_cell.rerun_0dbe6e9.json`; J cross-checked
   against `cells.jsonl`, 0 mismatches). Intervals: `analyze_holdout.cluster_bootstrap_stat`,
   BCa, B = 10,000, seed 20260913, cluster = CQ.
4. **Secondary any-candidate run** (upper bound): an ASK counts as true if any assignment of one
   candidate (from any rule) per term makes it true (cap 256 assignments per query).

Three scope decisions I made, all after seeing the pipeline vocabulary (disclose them):
(a) `rec:` and `qudt:` IRIs are rewritten like `brick:` (otherwise CQB17/CQB24 stay false for
the same namespace reason; rdf/rdfs/owl/skos/sh/xsd are never rewritten); (b) the
`ns_prefixed_local` rule exists because the pipeline mints `brick-haspoint` / `brick_hasPoint`
for Brick terms; it has the lowest priority; (c) pipeline scaffolding terms (`Class_*`, `p_*`,
`section_*`; 96-111 per B-F graph, 0 in A) are not candidates. (c) was added after the first
mapping showed `brick:Alarm` -> `ct:Class_alarm` in B-F; it changed that one mapping and no
outcome (overall counts were 7/63/38 before and after). The rule order was fixed in the first
draft, before any outcome was seen.

## Results (all exploratory)

**Mapping** (54 terms per variant): A 52 mapped (38 `local_exact`, 13 `label`, 1
`ns_prefixed_local`), 2 unmapped (`brick:EntityProperty`, `qudt:hasQuantityKind`). B-F 47 mapped
(29 `local_normalized`, 18 `ns_prefixed_local`), 7 unmapped (the two above plus
`brick:buildingPrimaryFunction`, `feeds`, `isReplacedBy`, `isVirtualMeter`, `yearBuilt`). 0
ambiguous. 9 (A) / 29 (B-F) terms also have candidates under lower-priority rules.

**ASK outcomes, 18 CQs x 6 variants = 108 runs:** true 7, false 63, not evaluable 38.

| variant | true | false | not evaluable |
|---|--:|--:|--:|
| A | 7 | 8 | 3 |
| B-F (each) | 0 | 11 | 7 |

All 7 trues are variant A: CQB07, 08, 10, 12, 22, 32, 33. CQB21, 23, 24 are not evaluable on
every variant; CQB15, 22, 32, 33 additionally on B-F. Any-candidate upper bound: true 11, false
49, not evaluable 38, cap exceeded 10 (CQB09, CQB12 on B-F); the 4 extra trues are CQB13-16 on A.

**Concordance** (cells = primary (CQ, variant) cells of ASK CQs with an evaluable ASK: 63 of 84,
11 CQ clusters). Rows ASK, columns other.

| ASK vs J>=2 | J>=2 | J<2 |   | ASK vs A | A=1 | A=0 |
|---|--:|--:|---|---|--:|--:|
| ASK true | 4 | 0 | | ASK true | 4 | 0 |
| ASK false | 51 | 8 | | ASK false | 53 | 6 |

Cohen kappa 0.020 (agreement 19.0%) for J, 0.014 (15.9%) for A. Cluster BCa 95% for kappa:
J [0.003, 0.085], A [0.000, 0.080]. ASK true is 4/4 consistent with J>=2 and A=1 but recovers
only 4 of 55 J>=2 and 4 of 57 A=1 cells. By group (no interval): variant A n=8, ASK true 4,
kappa 0.50 (J) / 0.25 (A); B-F n=55, ASK never true, kappa 0. Any-candidate run (n=53): kappa
0.036 (J, BCa [0.006, 0.197]), 0.026 (A, [0.000, 0.172]).

**Per variant** (primary cells of the 18 ASK CQs; judge coverage = 100*sum(J)/(3n), the
`judge_only_J.py` statistic; intervals BCa, cluster = CQ):

| var | ASK T/F/NE (18) | judged cells | evaluable | ASK pass / evaluable [BCa] | judge coverage % [BCa] | J>=2 share (evaluable) |
|---|---|--:|--:|---|---|--:|
| A | 7/8/3 | 9 | 8 | 4/8 = .50 [.13, .88] | 77.8 [44.4, 96.3] | .75 |
| B | 0/11/7 | 15 | 11 | 0/11 = 0 (degenerate) | 68.9 [46.7, 84.4] | .91 |
| C | 0/11/7 | 15 | 11 | 0/11 = 0 (degenerate) | 71.1 [48.9, 86.7] | .91 |
| D | 0/11/7 | 15 | 11 | 0/11 = 0 (degenerate) | 64.4 [40.0, 82.2] | .91 |
| E | 0/11/7 | 15 | 11 | 0/11 = 0 (degenerate) | 64.4 [40.0, 84.4] | .82 |
| F | 0/11/7 | 15 | 11 | 0/11 = 0 (degenerate) | 71.1 [46.7, 88.9] | .91 |

Pooled ASK-true share of evaluable cells 4/63 = .063, BCa [.016, .111].
Variant A has 9 judged cells on ASK CQs (A was graded on 23 CQs); its other 9 ASK runs (CQB13,
14, 15, 18, 22, 23, 24, 32, 33) have no primary cell and are outside every concordance number.

## Caveats

- **Few clusters.** 11 CQ clusters in the concordance, 8-15 per variant; only 4 clusters
  (CQB07, 08, 10, 12) contain an ASK-true cell, and kappa is 0 in any resample without them. The
  kappa intervals are fragile and their lower bound sits on that floor. Treat them as a
  description of instability, not as coverage statements.
- **Predicates are not aligned, so B-F false is about the query vocabulary, not content.** Only
  terms are rewritten. The queries test `rdfs:subClassOf` / `owl:inverseOf` / `sh:path` /
  `owl:disjointWith`. B-F graphs hold 0 `owl:inverseOf` (A: 15), 0 `sh:path` / `sh:class` /
  `owl:disjointWith`, and only 10-14 `rdfs:subClassOf` triples (A: 1,946), all with a `Class_*`
  scaffolding subject; they express the hierarchy as `ct:p_subclass` (B-D, ~1,980 triples) or
  `skos:broader` to non-section nodes (E, F: 2,007 in E). Of the 55 B-F false outcomes, 30 need a
  predicate with zero triples in the graph and the other 25 (CQB07-10, 12) depend on
  `rdfs:subClassOf`; none can come out true. Aligning predicates would be a further post hoc
  rule; it was not done. Over all 108 runs, 33 of the 63 false outcomes need a zero-triple
  predicate (`core_predicates_absent` in `ask_results.json`).
- **Single-candidate rewrites can mix tiers.** In A, CQB13 rewrites to `ct:hasPoint` (exact)
  `owl:inverseOf` `ct:brick_isPointOf` (label), which is false, while the all-prefixed pair
  carries the inverse (any-candidate run true). The 7 vs 11 gap brackets this arbitrariness.
- **Not evaluable is not absence, but it is not coverage either.** A term with no `ct:`
  counterpart under the rules is plausibly missing from the graph; the brief says not to score
  it false, so it only shrinks the denominator (38 of 108 runs; 63 of 84 judged cells remain).
- **Confounded pooling.** Every ASK-true is in variant A, a differently rendered, schema-shaped
  graph (0 individuals), so pooled kappa mixes variant with ASK. A vs B-F pass rates reflect
  representation as much as content.
- **ASK is partial and weak in places.** 18 of 36 CQs; none for concept-definition or instances.
  CQB32/CQB33 are existence checks (true if the mapped term occurs in any triple); CQB09 needs
  exactly 24 subclasses.
- **Ceiling.** J>=2 holds in 87% and A=1 in 90% of evaluable cells, so kappa is near 0 even though
  ASK-true never contradicts them.
- **Not independent of this paper's analysis choices:** the mapping is judge-independent and
  label-independent in construction, but its design followed the results.
- The rewriter assumes space-separated SPARQL tokens and skips strings, comments and `<...>`;
  the 18 queries contain no such edge cases. Per-cell J / A are not written to the outputs.
- Generated code and results: review and test before relying on them (corporate rule); nothing
  here is for external distribution without checking for confidential or personal content.

## Files and sha256

| file | sha256 |
|---|---|
| `ask_alignment.py` | `6098c6ee6f57b4085f548bd2919f2a222e5998347c73ee7c826ba148214e91ba` |
| `mapping.csv` (324 rows) | `1e23509009a891d97d0fe171a51fe03ee7ab8da122e7848a8f9e296dc460d85d` |
| `ask_results.json` | `7778107a2b3c6b2f82a36116940cd0f2ec592546eeab06579987f95f7c02c865` |
| `../../test_ask_alignment.py` | `ee12b6867d7ce0bbfa7a87b62dc7602f45f3367348471087e464d073301eb0e4` |

Inputs (read-only; all 18 query hashes are in `ask_results.json` -> `inputs_sha256`):

| input | sha256 |
|---|---|
| `bank/cq_bank_brick_v1.csv` | `993c5e1164540dce0f2f9bf2e6ed397cf45910da7889300feeaad6543edb8507` |
| `data/brick-v1.4.4.ttl` | `b65720b7b9b64c646745c689777e6138c0d59ce0088df0aeb78fbd444d04d8e7` |
| `harness/real_run/results_human_pass/unsealed_2026-10-09/per_cell.rerun_0dbe6e9.json` | `5aebf70b6af9b4468f3c066ba84215699316ae5342d33b5c61d6cb4bd90a9248` |
| `harness/real_run/cells.jsonl` | `bfd5b3c83981c8a6ec970b93f460bab7409daf047a2e048bfaa90b5adfd0d4af` |
| `harness/analyze_holdout.py` | `3278d71c70829889838aa8f61c4f5b0217b9ef3e921976a8ea5fc0c0fd122e10` |
| `harness/variants/A/graph_A.ttl` | `1a5cc075065ac1f493e7731ac20e638481754c1a79f586b6e82a25320cb1bc32` |
| `harness/variants/B/graph_B.ttl` | `20d015a83b1158fdf1bc598b75127f63eed088f0a10bc54e91d88d411b4fe490` |
| `harness/variants/C/graph_C.ttl` | `c057252c5c5b33750984de600ea6c2b176a8319c6f71fe6663b72f8d8f902629` |
| `harness/variants/D/graph_D.ttl` | `268a748b8c15d1bc96ec16b503bcada62e49d8143b57ff617da4737cce3e4585` |
| `harness/variants/E/graph_E.ttl` | `6283eb356de2a3f9eec3b02470c435c864b775aaaa23ec4575fc3da0ea54c8c7` |
| `harness/variants/F/graph_F.ttl` | `8fa73d3782bee329078808a7a7e9e10f37989eecdef63f778215b626d91bbcb1` |

Not touched: PREREG.md, main.tex, supplement.tex, BRIEF.md, analyze_holdout.py, the registered
bank and snapshot. Nothing committed. No `persona_pass/` directory was opened; the test run
below excluded `harness/persona_pass/`, `harness/real_run/persona_pass/` and
`harness/test_persona_pass.py` for that reason.

Test run: `pytest paper/access2026/harness -q` (with those three paths ignored): 979 passed, 2
skipped (37 tests in `test_ask_alignment.py`).
