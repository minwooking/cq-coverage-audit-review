# Second judge for the Brick holdout: gpt-5.6-luna (exploratory, post hoc)

**Status: the data run is NOT complete. 5 of 224 cells are scored (a budget-capped pilot on variant A); 219 remain.**
The run stopped before the bulk of the work on purpose, because the token estimate below is about 25 times the run that exhausted the shared GPT quota on 2026-10-08. Everything needed to finish is in place and resume-safe; the decision to spend the tokens is not mine. Nothing here is confirmatory: the run happens after the holdout results and the human labels were known, and PREREG.md registers no second judge.

## What was built

| Piece | Where |
|---|---|
| Runner (imports `run_holdout`, same cell plan, digest-verified) | `paper/access2026/harness/run_second_judge.py` |
| Scores (valid cells only, same schema as `real_run/cells.jsonl` plus one `second_judge` key) | `cells.jsonl` |
| Failed attempts (kept out of `cells.jsonl`) | `failures.jsonl` (absent: 0 failures so far) |
| Model ID, timestamps, digests, settings, call counts, failures, stop reason | `run_manifest.json` |
| Agreement, sensitivity, G6 (each section says exactly why it is `not_computable`) | `analysis.json` from `analyze_second_judge.py` |
| Tests on synthetic fixtures (analysis and runner, no network) | `paper/access2026/harness/test_second_judge.py` |

## Model and availability

- Model: `gpt-5.6-luna`. The proxy reported exactly `gpt-5.6-luna` in the availability probe and in every cell response.
- Why this one: PREREG names no second judge for G6, so the fallback applies (an OpenAI GPT-5.6-series model on <internal-proxy>). It is neither Gemini (judge 1) nor Qwen (label drafter). PREREG.md section 8 already used `gpt-5.6-luna` through the same proxy for the disclosed LLM auxiliary check, a task with a different prompt that does not feed A.
- Supply: only the local <internal-proxy> proxy `http://<local-endpoint>/v1` (<internal-proxy> 2.41.0); the runner refuses any other host. No API key was needed or used; the optional `HOLDOUT_JUDGE_API_KEY` is never logged.
- `/v1/models` for this model: context 922000 tokens, max output 128000, default reasoning effort `medium`, a higher pricing tier above 272000 prompt tokens. The largest cell is about 0.62M tokens, so every cell fits.

## What is identical to the original run, and the one deviation

Identical (verified, `run_manifest.json` -> `digests`): bank sha256, rubric sha256 `d0c397584bd62ca2ba62cf3833b1ad70862d6be22be52a4c3ffa111529756ebf`, rendering-spec sha256, `variant_views_sha256` `16ede3938e2729c70467c51195dd0f32869c8f375d5945e12d40aa9f1fa50b8f`, `queue_sha256` `2ba0a20ad9d85a15a8e9fc8a806999c97ec02ee717faf96475bf5114f8159926` (all equal to `real_run/MANIFEST.json`), and **all 224 per-cell `artifact_digest` values equal those in `real_run/cells.jsonl`** (0 mismatches) before any request. System prompt = `run_holdout.RUBRIC` (sha256 `85e208799f10b756125c524dc43222064ac946f3c01f000ee03cf331800cee72`), user message = `ARTIFACT:\n{artifact}\n\nQUESTION: {question}`, `temperature=0.0`, `max_tokens=1024`, no `extra_body`. `test_request_body_is_the_registered_body_minus_response_format` checks the request body against `run_holdout.call_judge`'s.

Deviation (forced): `response_format={"type":"json_object"}` is omitted. The <internal-proxy> adapter answers HTTP 502 `adapter_eof` to any request that carries it; the runner re-probes this on every start (`run_manifest.json` -> `response_format_probe`: with = HTTP 502, without = HTTP 200), the same finding as `llm_auxiliary_check.py`. The system prompt still asks for JSON; the reply is parsed strictly, then by outermost `{...}` (`parse_mode` per cell); a non-integer or out-of-range score is a failed cell, not a cast.

Not equal to judge 1: judge 1 ran Gemini with `thinking_level=minimal`; here the reasoning effort is the proxy default (`medium`) and `temperature=0.0` does not make this reasoning model bit-reproducible. Observed 2026-10-09: the same cell (`primary:A:CQB02`, identical request) scored 2 in an unsaved calibration probe and 3 in the saved pilot. Treat judge 2's scores as one draw.

## Token budget (estimate before the full run)

Calibration on this proxy (usage.prompt_tokens / artifact chars): variant B slice 3.94, variant F slice 3.80, variant A whole 4.19 chars per token (A cells: 69,878 prompt tokens each, measured). Central estimate uses 3.9, the budget guard reserves with 3.7.

| Tier | Cells | Prompt tokens (central) | (conservative) |
|---|---|---|---|
| 1: primary A and B | 56 | 18.3M | 19.2M |
| 2: primary C, D, E, F | 132 | 80.8M | 85.2M |
| 3: the 36 control cells (not used by any analysis) | 36 | 19.5M | 20.5M |
| all primary | 188 | 99.1M | 104.5M |
| **all 224** | 224 | **118.6M** | 125.0M |

Completion tokens are negligible (about 150-600 per cell). Variants B-F are 1.9-2.4 M characters per cell (about 0.49-0.62 M tokens), variant A 0.29 M characters (70 k tokens). Prompt caching is not dependable here: `cached_tokens` was 0 for sequential repeats and 69,376 of 349,390 in the three-worker pilot.

Why this is a decision for a human (estimate, not measurement): the only quota record on disk is the stale `<proxy-config-path>` from the 2026-10-08 incident (persona run, about 4.6 M tokens, workers up to 11): 5-hour window 100 %, weekly 16 % (weekly reset 2026-10-15). Scaled from that, 118.6 M tokens is on the order of 25 five-hour windows and several times the weekly allowance; tier 1 alone (about 18 M) is about four windows and over half a week. See `<internal-proxy>-batch-concurrency-quota` in the project memory.

What tier 1 buys: G6 and the A->B sensitivity need only the A and B primary cells (`analyze_holdout._direction` reads variants A and B); agreement needs any scored cells; coverage per variant, pi-hat and the ranking need every primary cell.

## Commands

Run from the worktree root. `PY=<repo>/.venv/bin/python`, `export PYTHONPATH=$PWD/src`.

```
# no network: verify digests, print the token table, list what is pending
$PY paper/access2026/harness/run_second_judge.py --estimate

# resume (cells already in cells.jsonl are skipped). --token-budget is mandatory;
# at most 3 workers; the first usage-limit 429 stops the run; 3 failed cells in a row stop it.
# tier 1 (A and B primary; about 18-19 M tokens, several quota windows):
$PY paper/access2026/harness/run_second_judge.py --model gpt-5.6-luna --variants A,B --kinds primary --token-budget 20000000
# or one quota window at a time, repeated until run_manifest.json counts.cells_remaining is 0:
$PY paper/access2026/harness/run_second_judge.py --model gpt-5.6-luna --token-budget 4000000
# tier 2 / 3:  --variants C,D,E,F --kinds primary   /   --kinds ablated_control,preserved_control

# analysis (about 2 s at B = 10,000; reproduces the judge-1 numbers first)
$PY paper/access2026/harness/real_run/second_judge/gpt-5.6-luna/analyze_second_judge.py

# tests
$PY -m pytest paper/access2026/harness/test_second_judge.py -q
$PY -m pytest paper/access2026/harness -q
```

Cells are scored in priority order (primary A, B, C, D, E, F, then controls), so an interrupted run holds the most analysable subset. Results are written per cell as they arrive; `run_manifest.json` is rewritten at the end of each invocation with the cumulative counts, token totals and per-invocation stop reasons.

## Results so far (pilot, descriptive only)

- Cells: 5 scored (variant A, `primary:A:CQB01..05`), 0 failed attempts, 2 invocations (350108 tokens in the pilot, 0 in the manifest-refresh invocation).
- Token use recorded by the runner: prompt 349390, completion 718, cached 69376, reasoning 414. Calibration probes made outside the runner (scratch scripts, not saved): about 357 k prompt tokens.
- Agreement on those 5 cells, no interval (fewer than 10 clusters): exact 0.40, QWK -0.25, binary kappa of 1[J>=2] 0.00, mean J2-J1 +0.4. Five cells from one variant say nothing about agreement.
- `analysis.json` lists every section that cannot be computed yet, with the missing-cell counts. G6 is `not_computable` for exactly one reason: the judge-2 scores of 18 A cells and all 33 B cells are missing (the non-Qwen direction component reads variants A and B only). The two components that need only judge 1 are already known: A->B on L1* with the AH labels is not resolved (delta 0.478, 95% CI [-0.087, 1.043]) and fragility K = 0. Because `analyze_holdout._g6` returns `fail` when any component fails, G6 will evaluate to `fail` whatever judge 2's direction is (this follows from the gate's code and judge-1 numbers, not from a judge-2 run). Judge 1 alone, judge-only scale: A->B delta 0.565, CI [0.043, 1.130], resolved; the AH demotion is what makes it unresolved.
- Reproduction check: this analysis code reproduces the committed judge-1 coverage (all six variants, with CIs), A->B (delta, CI, Holm p) and pi-hat (with CI) with max abs difference 0.0 over 25 quantities.

## How G6 is computed

By `analyze_holdout._g6`, unchanged: A->B consistency (judge 1, L1* with the AH labels: delta > 0 and the BCa CI above 0), non-Qwen direction (mean over CQs of the raw judge-2 B minus A, same sign as the L1* direction under judge 1, both nonzero), fragility K >= 6 (judge 1, L1*). PREREG registers G6 against a Qwen primary judge; here neither judge is Qwen, so judge 2 fills the non-Qwen slot, and PREREG 12.1 D10 still forbids counting judge 1's own family as satisfying it. A mirrored reading (roles swapped) is added to `analysis.json` as descriptive only.

## Caveats the analysis carries

- The AH labels were adjudicated next to judge-1 material (its evidence span, a Qwen draft). pi-hat and L1* under judge 2 treat A as a property of the cell and inherit that conditioning; judge-only coverage does not use A.
- Variant rankings and the A->B contrast are descriptive: PREREG section 4 calls differences below 0.53 L1 unresolved and forbids 'tie' language.
- `MIN_CLUSTERS_FOR_CI = 10` (below it the BCa interval is withheld) is this script's choice, not registered.
- Other sessions have untracked files in this worktree (`persona_pass`, `ask_alignment`, ...); none were read or touched. This task did not touch PREREG.md, main.tex, supplement.tex, BRIEF.md, analyze_holdout.py, run_holdout.py or the original cells.jsonl (git shows main.tex, supplement.tex and BRIEF.md as modified, from other sessions, before this task began; the original cells.jsonl sha256 is unchanged). Nothing was committed.

## sha256

Outputs:

| File | sha256 |
|---|---|
| `paper/access2026/harness/real_run/second_judge/gpt-5.6-luna/cells.jsonl` | `926902324c55cfbaf83829acfd67546d0ac7f3cfe0674cab7da1069810d7d7a6` |
| `paper/access2026/harness/real_run/second_judge/gpt-5.6-luna/run_manifest.json` | `c604123cc15eae02830eb3690ebb3ccac0833dfeb2da4a28f753eb8ab0276ec5` |
| `paper/access2026/harness/real_run/second_judge/gpt-5.6-luna/analysis.json` | `c6a0fa08b15c81385741a0a92a94fcf56d8f7f650726158015996b132fb1560c` |
| `paper/access2026/harness/real_run/second_judge/gpt-5.6-luna/analyze_second_judge.py` | `371d5348d9593723ce631a34348c092be514200a98f1cb4471dcfbd51b6772da` |
| `paper/access2026/harness/run_second_judge.py` | `391327cef64fbb862a896b421bdce2252c6192d13cd6e74be91f460a621cb811` |
| `paper/access2026/harness/test_second_judge.py` | `cfa158a19adea58971a6bf9c28b00ecbcb6689392fd12b5a1ba0a6cc9ba31290` |

Inputs (unchanged):

| File | sha256 |
|---|---|
| original real_run/cells.jsonl (judge 1, gemini-3.6-flash) | `bfd5b3c83981c8a6ec970b93f460bab7409daf047a2e048bfaa90b5adfd0d4af` |
| unsealed per_cell.rerun_0dbe6e9.json (AH labels A, judge-1 J) | `5aebf70b6af9b4468f3c066ba84215699316ae5342d33b5c61d6cb4bd90a9248` |
| unsealed holdout_results_human.rerun_0dbe6e9.json (reproduction target) | `ee2650c7cfa1e7655305def2c7437ee9972cf7f7e5813460b4c81c4a84d7da49` |
| analyze_holdout.py (imported, unchanged) | `3278d71c70829889838aa8f61c4f5b0217b9ef3e921976a8ea5fc0c0fd122e10` |
| run_holdout.py (imported, unchanged) | `b13aff69300064bcdf03fb89194100d49b46095725888a56d1626d82c3712db0` |
| rubric/RUBRIC_L1.md (frozen) | `d0c397584bd62ca2ba62cf3833b1ad70862d6be22be52a4c3ffa111529756ebf` |
| rubric/RENDERING_SPEC.md (frozen) | `eb0399af5152ac001074f1a0c27b23652a42a2f9ceeebf95a669abf703ec0a3e` |
| bank/cq_bank_brick_v1.csv (frozen) | `993c5e1164540dce0f2f9bf2e6ed397cf45910da7889300feeaad6543edb8507` |

`README.md` is not hashed here (it contains the hashes).

## Tests

- `test_second_judge.py`: 46 passed in 11.5 s (synthetic fixtures; no network)
- `pytest paper/access2026/harness -q` (whole harness, run while other sessions' untracked tests were present): 1123 passed, 2 skipped, 1 failed in 146.7 s. The failure is test_exploratory_reanalysis.py::test_committed_artifacts_are_consistent_with_the_code, in a file another session left untracked (its recorded script hash is stale); it does not touch any file of this task and was not changed

Generated output must be reviewed and tested before use; this is analysis code and a scoring runner, not a production change. Before this analysis is quoted outside the project, check it for confidential company information, personal information and credentials.
