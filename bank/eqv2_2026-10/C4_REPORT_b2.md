# C4 report: eligibility and judgeable pairs, bank b2 (addendum 47.4; plan-based, exploratory)

> AI-generated draft: a person must review and test the code and these numbers before use. Structure only: no model
> or judge call, no judge score. Same procedure and same imported tools as the b1 C4 (`tools/eligibility.py`,
> `tools/views.py`, unchanged); a new driver `tools_c4_b2/c4_b2.py` passes the b2 bank, set name `b2` and prefix to them.

## Inputs and hashes

| item | value |
|---|---|
| b2 bank (456 rows) sha256 | `ff32b2fb...c8225d4` (equals `SHA256SUMS_b2_freeze.txt`) |
| `run_holdout.py` sha256 (file) | `c69f105c...` (same as b1) |
| RUBRIC sha256 (imported module value) | `85e20879...` (same as b1) |
| renderings A/B, graphs A/B, builder files | same hashes as b1 (asserted by the b1 tools) |

## Headline (b2)

| quantity | value |
|---|---|
| bank rows N2 | 456 (concept_definition 219, taxonomy 220, methodology 17) |
| A eligible | 420 |
| B eligible | 55 |
| A and B eligible | 46 |
| judgeable pairs K2 (both eligible, both views non-empty) | **46** |
| eligible cells with no view (A / B) | 0 / 0 |
| floor set (judgeable in exactly one of A, B) | 383 (A only 374 = 370 + 4; B only 9) |
| pair yield y2 = K2/N2 | **0.1009** (b1 0.1336; expansion bank 0.3095) |

Reasons: A eligible 420, missing_required_anchor 2, no_matching_line 34; B eligible 55, missing_required_anchor 5,
no_matching_line 396. View status: A ok 420, not_built_ineligible 36; B ok 55, not_built_ineligible 401.

## By category (b2)

| category | rows | A elig. | B elig. | both | pairs | pair yield | floor |
|---|---|---|---|---|---|---|---|
| concept_definition | 219 | 194 | 12 | 11 | 11 | 0.050 | 184 |
| taxonomy | 220 | 212 | 39 | 31 | 31 | 0.141 | 189 |
| methodology | 17 | 14 | 4 | 4 | 4 | 0.235 | 10 |
| relations / slots_facets / instances | 0 | - | - | - | - | - | - |

Methodology has 17 rows (plan: 65); the report is on the frozen 456-row file, as given.

## Combined b1 + b2

| quantity | value |
|---|---|
| rows | 494 + 456 = 950 |
| **total pairs K = K1 + K2** | 66 + 46 = **112** |
| floor set (b1 367 + b2 383; ids disjoint) | 750 |
| shortfall vs 210 | **98** (K reaches 53% of 210) |
| combined pair yield | 112 / 950 = 0.118 |

| category | rows (b1+b2) | pairs (b1+b2) |
|---|---|---|
| concept_definition | 359 | 9 + 11 = 20 |
| taxonomy | 361 | 19 + 31 = 50 |
| methodology | 157 | 22 + 4 = 26 |
| relations | 22 | 15 + 0 = 15 |
| instances | 28 | 1 + 0 = 1 |
| slots_facets | 23 | 0 |

Id and duplicate checks (b1 vs b2): id collisions 0; b2 ids unique; exact (case/whitespace-normalised) duplicate
questions between b1 and b2 0, within b2 0; identical grounding strings shared by a b1 and a b2 row 0; judgeable-pair
id overlap 0. (Terms can recur across categories, see BATCH2_PROCEDURE.md; not checked beyond exact question text.)

## Power recomputation (normal approximation, TOST +-0.30, alpha 0.05 one-sided per side, paired SD sigma, n = K)

Power = Phi((0.30 - d)/se - z) + Phi((0.30 + d)/se - z) - 1, se = sigma/sqrt(n), z = 1.645; d = true difference.

| judge | n | se | d=0 | d=0.10 | d=0.20 | d=0.36 |
|---|---|---|---|---|---|---|
| glm (sigma 1.379) | 66 (b1 only) | 0.170 | 0.098 | 0.082 | 0.049 | 0.010 |
| glm | 112 (K) | 0.130 | 0.489 | 0.379 | 0.176 | 0.017 |
| gptoss (sigma 1.730) | 66 (b1 only) | 0.213 | 0.000 | 0.000 | 0.000 | 0.000 |
| gptoss | 112 (K) | 0.163 | 0.151 | 0.125 | 0.072 | 0.014 |

(d = 0.36 lies outside the +-0.30 margin, so the "power" there is the rate of a false equivalence call.) With K = 112
equivalence at +-0.30 stays unlikely to be shown for gptoss and is a coin flip at best for glm even at d = 0. These are
planning numbers from assumed sigmas, not results.

## Verification

- Eligibility: all 912 cells (456 x 2) recomputed with an independent aggregation (own can_ablate logic over the rule's
  primitives `_grounding_anchors` / `_anchor_present`): 0 mismatches. The rule's own function is the primary source;
  the independent code shares only those primitives.
- Views: the 475 eligible cells re-built by calling the builder's subgraph function directly (fresh graph contexts):
  status and sha256 match the manifest in all 475; view files on disk match their manifest hashes.
- Pairs: K2 = 46 recomputed from eligibility plus view status, identical id set.
- Existing tests: `tools/tests` run with PYTHONPATH set to `tools`: 129 passed. No tracked file changed.

## Files (new, untracked, nothing staged or committed)

`eligibility_b2.json`, `view_manifest_b2.jsonl`, `pairs_b2.json`, `C4_REPORT_b2.md`, `tools_c4_b2/c4_b2.py`;
views under `inputs/b2/` (git-ignored). `BATCH2_SIZE.json` was not rewritten.
