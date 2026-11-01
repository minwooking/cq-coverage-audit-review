# Run record: paired AI audit, stages 1-2 (EXPLORATORY, POST HOC)

All times UTC, 2026-10-09. Commands were run by an AI agent under the approvals quoted below; outputs were not
reviewed by a human before the run.

## Approvals (as relayed to the executing agent)
1. Stage 1: Phase B in stages, variants A and B only (A3 + B9 = 12 cells), models `gpt-5.6-luna` and
   `claude-sonnet-5-5`, <internal-proxy> (:PORT), workers <= 3, budget 1.2 x the offline estimate per model. The human approval
   gate of the runbook was replaced by this approval; the remaining 36 cells were not to run without re-approval.
2. Model ID: use `anthropic/claude-sonnet-5-5` (the <internal-proxy>-registered name of the same model).
3. Code: opt-in `--omit-temperature` for the runner and `--omit-temperature-a/-b` for the preflight, default
   unchanged; committed separately (125a77a).
4. Budget 6.0M per model for stage 1 and, for the remaining cells, 1.3 x the remaining-cell estimate (x the
   observed stage-1 token/estimate ratio for sonnet).
5. Whole run: the user's words, as relayed: "다 승인해줄게 바로진행해" (2026-10-09), covering the remaining cell(s) of A,B and
   variants C-F for both models, with: no loop on quota/429/budget stop.

## Inputs
- Cell list `real_run/second_annotator/cell_list_48.txt`, sha256
  `bd2333d427971fb182add2e3735e1d81fd3fe343640d736eea2b612819854b7e` (48 cells). The 48-cell list was used for every
  run; no sub-list was made. Stage 1 selected A,B with `--variants A,B`; stage 2 ran without `--variants`.
- Preflight (final): verdict `ready`, families openai / anthropic (distinct), both models in `/v1/models`,
  reported IDs equal requested IDs. Output `paired_preflight.json` (the first, blocked preflight was overwritten).
- Output dirs: `gpt-5.6-luna/`, `anthropic__claude-sonnet-5-5/` (cells.jsonl, failures.jsonl, run_manifest.json).

## Invocations
| model (requested = reported) | window | cells scored | stop reason | budget given | tokens used by the ledger |
|---|---|---|---|---|---|
| gpt-5.6-luna | 11:00:57-11:01:32 | 12 (A,B) | all_selected_cells_scored | 5,985,647 | 4,644,160 |
| gpt-5.6-luna | 12:32:58-12:34:52 | +35 (C-F) | selected_cells_exhausted_with_1_failed | 30,256,123 | 22,450,079 |
| gpt-5.6-luna | 12:38:10-12:38:24 | +1 (E:CQB24, one manual re-run) | all_selected_cells_scored | 1,000,000 | 626,766 |
| anthropic/claude-sonnet-5-5 | 11:59:23-12:00:19 | 11 of 12 (A,B) | token_budget_reached | 5,985,647 | 6,688,756 |
| anthropic/claude-sonnet-5-5 | 12:35:06-12:37:26 | +14 (B:CQB33, C) | 3_consecutive_failed_cells (HTTP 429) | 46,413,212 | 13,484,217 |

Budgets were set per the approval: luna 1.3 x 23,273,941 = 30,256,123; sonnet 1.3 x 1.5 (observed stage-1
actual/estimate 6,688,756 / 4,460,333 = 1.50) x 23,801,647 = 46,413,212. Runs were sequential (luna, then sonnet);
workers 3 (1 for the single-cell re-run).

## Actual token usage (usage fields of the responses)
- luna: 48 scored cells prompt 27,079,658 (cached 8,944,896), completion 14,645, reasoning 6,568; plus the one
  failed attempt prompt 626,439, completion 263. Total prompt tokens billed about 27.71M.
- sonnet: 25 scored cells prompt 20,160,965 (cached 19,024), completion 12,008, reasoning 0. The 5 failed
  attempts (HTTP 429) carry 0 tokens.

## State at the end
- luna 48/48 cells. sonnet **25/48** (A3, B9, C13); 23 cells not scored: D (7), E (10), F (6).
  The cause is an Anthropic account rate limit (429 `rate_limit_error`), not a budget stop. Not retried, no loop.
  Re-running requires a human to check the provider's limit window first.
- Analysis: `paired_analysis.json` (`computed_on_partial_data`, 25 paired cells, 20 clusters); `stage2_summary.md`.

## Deviations from the registered scheme and the runbook
1. Sonnet requested by the prefixed <internal-proxy> ID `anthropic/claude-sonnet-5-5` (the approved name was
   `claude-sonnet-5-5`, not registered on the proxy).
2. Decoding asymmetry: luna temperature 0.0; sonnet with `temperature` omitted (model default) because the API
   returns HTTP 400 "`temperature` is deprecated for this model". The code change is the opt-in flag (125a77a).
   Sonnet's manifest records `temperature_omitted: true`.
3. `response_format` is not sent to either model (runner convention, see its module docstring).
4. Stage-1 sonnet budget stop: the run stopped at 11 of 12 cells with 6,688,756 tokens against a 5,985,647 budget.
   The ledger reserves by estimate; sonnet's tokenizer used about 1.5 x the estimate, so in-flight cells overshot.
   B:CQB33 was scored in stage 2.
5. luna's E:CQB24 failed once (HTTP 200, content not parseable as JSON); it was re-run once by hand in a separate
   invocation (J=1). This is the only re-run; the failed attempt stays in `failures.jsonl`.
6. The preflight's first run (blocked on sonnet, HTTP 400) and a few manual one-token-scale checks of the proxy
   (plain chat calls, under 1,000 tokens in total) are not part of the ledgers above.
7. Scoring of the remaining 23 sonnet cells is missing; all comparisons including sonnet cover variants A-C only.

## Claim limits
Two AI judges disagree or agree on these cells; this is not human verification and does not change the registered
gate results. Nothing from this run was written into the manuscript, BRIEF.md or PREREG.md. Review the files for
secrets and host names before any external distribution (none were written by the tools; the key was never set).

## Stage 3 (resume of sonnet D-F), added 2026-10-09

- Approval: the same user words as stage 2 ("다 승인해줄게 바로진행해", 2026-10-09), applied to the 23 pending
  sonnet cells; no loop on quota/429 (none occurred).
- Invocation: same output dir, same 48-cell list and sha256, no `--variants`, `--omit-temperature`, workers 2,
  `--token-budget 28,829,206` (= pending conservative estimate 14,784,208 x 1.3 x 1.5). `--estimate` before the run:
  already_done 25, pending_selected 23.
- Window: 2026-10-09 13:32:10 UTC (start) to 13:34:25 UTC (manifest update), about 2 min 15 s. About 9 hours after
  the stage 2 stop (12:37 UTC); no 429 recurred. Stop reason `all_selected_cells_scored`, 23 cells scored, 48/48.
- Additional usage: ledger 22,532,462 tokens (of the 28,829,206 budget); usage fields of the 23 responses: prompt
  22,520,156 (cached 1,981,605), completion 12,306, reasoning 0. No new failures (failures.jsonl still 5 lines from
  stage 2). Sonnet totals across stages: prompt about 42.7M for 48 scored cells.
- Not interrupted. Analyzer re-run: `paired_analysis.json` is now `computed` (48 paired, 28 clusters);
  `stage2_summary.md` rewritten with the three-way table on 48 cells. Deviation 7 above (variants D-F missing) is
  resolved. Nothing was written into the manuscript, BRIEF.md or PREREG.md.
