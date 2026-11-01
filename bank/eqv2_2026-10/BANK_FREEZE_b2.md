# Freeze of the eqv2 bank, batch b2 (addendum 47, 47.3 "Batch 2"; manuscript Study 12)

> **AI-generated draft.** This file and every file it freezes were written by an AI assistant; the author must review
> them before they are relied on. Plan-based, **exploratory** -- no pre-commitment label of the kind used for earlier
> studies is attached to this bank (addendum 47.0). No row was checked against a rendering, an eligibility result, a
> graph or a judge score; **only 30 of the 456 rows were read by the author**, and the pass of those 30 rests on the
> author's stated answer, because the saved sheet is byte-identical to the blank one (`SCREEN_b2_RESULT.md`). The rows are
> AI drafts, not a human-checked answer key.

Frozen by the commit that adds this file; the git commit time is the authoritative date (drafted 2026-10-28). This file
states what the frozen files are; whether the freeze has been approved, committed or tagged is read from the repository
(`git log`, `git tag`), not from this text. The tag name this freeze carries is `access2026-eqv2-b2-freeze`.

**b2 was composed after the C4 result for b1 was known** (`C4_REPORT.md`: judgeable pairs K1 = 66 of N1 = 494, pair yield
0.1336, target 210 not met; `BATCH2_SIZE.json`). The composition rules were written by the maintainer with that number in
view (`BATCH2_PROCEDURE.md`, "Limits"). They use only quota and tail sizes, not eligibility, scores or yield, but that
does not make the b2 item list independent of the C4 outcome. b2 is therefore a second, later batch of an exploratory bank, not a
second draw from the same blind position as b1.

| field | value |
|---|---|
| Bank file | `bank/eqv2_2026-10/cq_bank_brick_eqv2_b2.csv` |
| Rows | 456 (`CQE505`..`CQE1006`; ids are the b2 plan's `CQE505`..`CQE1008` with 48 methodology ids absent -- see "Rows per category") |
| Bank SHA-256 | `ff32b2fbc518e696d285b2bc6cfccac7648efe6bf80a566f1293ac883c8225d4` (every file of this freeze commit except `SHA256SUMS_b2_freeze.txt` is listed, with its hash, in `SHA256SUMS_b2_freeze.txt`) |
| Tag | `access2026-eqv2-b2-freeze` |
| Procedure and tool commit | `579d0dc` (tag `access2026-eqv2-b2-procedure`): b2 tools, tests, `BATCH2_PROCEDURE.md`, `batch2_plan.json`; committed 2026-10-28 16:58:03 +0900 (07:58:03 UTC), before the first b2 drafting call (07:59:09 UTC in `logs_b2_frozen/draft_calls_b2.jsonl`) |
| Item list | `batch2_plan.json`, sha256 `9160ddb1bd00d5b9b97db9686e1715c035a3c7cb9e66c2fa7caed77e42fbd81a` (504 items; committed in `579d0dc`) |
| Row provenance | `validated_b2.jsonl` (sha256 `9a2d8d532774deca0853189a5b5a127a8d8813d6987c89b00b5fb86f2846de6d`); no question, grounding or expected-answer text was edited to produce this file |
| Preceding draft file | `draft_b2.jsonl`, 504 rows, sha256 `2679257d3804bb86d162a0796c04cd44ef5519c850013b71c3649eabd40201e1` |
| Frozen b1 bank (reference, never edited) | `cq_bank_brick_eqv2_b1.csv`, tag `access2026-eqv2-b1-freeze` (commit `9879780`), sha256 `b8478fca86de80b0c998eb6e5a3f7f11ef62433bcc75428e0bf8abe03d336efe` |
| Snapshot | `data/brick-v1.4.4.ttl`, sha256 `b65720b7b9b64c646745c689777e6138c0d59ce0088df0aeb78fbd444d04d8e7` |
| Seed (frame) | `20260913`, pinned in `frame_summary.json` (b2 takes the frame tail in the order that seed fixed; nothing is reshuffled) |
| Seed (b2 screen sample) | `20260915` |
| Prompt SHA-256 (this bank) | `a20414e1bfd2e5c354066696d13b4e76229a1ea2b3714347de2ec56ac9008b84` -- the b1 round-2 template, unchanged (`prompt_sha256_r2.json`) |
| `tau_emb` | `0.5168` (`tau_emb.json`, unchanged) |
| Drafting calls | 875 (504 first attempts + 371 replacement-wave calls), all `ok`, all attempt 1, 2026-10-28 07:59--08:12 UTC, route id `<internal-proxy>/Qwen/Qwen3.8-Flash-Next` |

## Columns

The same 25 columns as `cq_bank_brick_eqv2_b1.csv`, in the same order: the 20 columns of
`bank/expansion_2026-10/cq_bank_brick_expansion_v1.csv`, then `author_screen`, `batch`, `frame_rank`, `draft_model`,
`prompt_sha256`. The projection was written by the same procedure as b1's file; as a check on the procedure, the same
code run over `validated_b1_r2.jsonl` with b1's sample file reproduces `cq_bank_brick_eqv2_b1.csv` byte for byte. Line
endings are CRLF, as in b1. `cluster_id` equals `cq_id` on every row (D3 makes the primary grounding term unique).
Values are taken verbatim from `validated_b2.jsonl`; no question text was touched. Rows are ordered by the **numeric**
id (`CQE999` precedes `CQE1000`).

Eleven expansion columns are **blank on every row**, exactly as in b1; the reasons are those of `BANK_FREEZE_b1.md`
("Columns"), with the b2 file names:

| column | why blank |
|---|---|
| `ask_query_file` | the eqv2 tools never write `.rq` files; the ASK query is kept inline in `validated_b2.jsonl` (field `ask`). |
| `author_review` | the author read a 30-row sample (CP-1), not the bank; see `author_screen`. |
| `screen_format`, `screen_grounding`, `screen_ask`, `screen_fail`, `screen_notes`, `screen_dup`, `nearest_existing` | the equivalent machinery is `validate_report_b2.json` (V1--V6, per-row drop reasons) and `dedup_log_b2.csv` (D1--D5, per-row nearest reference). Transcribing those into these columns would change nothing except the chance of error. |
| `anchor_rule_check` | belongs to the frame/anchor machinery whose output is eligibility, which was not run on b2 before this freeze. |
| `eligibility_anchors` | not computed. Eligibility needs the A and B renderings (47.4) and is not part of this freeze. |
| `created` | **blank**, as in the frozen b1 file. (`BANK_FREEZE_b1.md` says `created` is filled with `2026-10-27` on all 494 rows; the frozen b1 CSV in fact has it blank on every row. The b1 text is not edited; b2 follows the b1 file as it is. The measured drafting date of every b2 row is 2026-10-28 UTC, from `logs_b2_frozen/draft_calls_b2.jsonl`.) |

`status` is `draft` on every row; `ask_expressible` is `yes` on 237 rows and `partial` on 219; `frame_rank` is 0 / 1 / 2 on
127 / 153 / 176 rows; `author_screen` is `passed_b2_sample` on the 30 sampled ids and `unscreened` on the other **426**.
`batch` is `b2`.

## Rows per category

| category | b2 plan allocation | kept (this bank) | short by | frame tail left for replacement |
|---|---|---|---|---|
| concept_definition | 219 | 219 | 0 | 760 items after the 219 |
| taxonomy | 220 | 220 | 0 | 1,202 items after the 220 |
| methodology | 65 | **17** | 48 | none: the 65 rows were the whole remaining tail |
| relations, slots_facets, instances | 0 | 0 | -- | none: these categories have no tail |
| **total** | **504** | **456** | **48** | |

(The "tail left" figures are the plan's `remaining` minus the allocation, 979 - 219 and 1,422 - 220; they describe what b2 did not
draw and are context, not used by the bank.)

The categories without a tail (`instances`, `relations`, `slots_facets`) contribute no b2 rows: their frames were drafted
whole in b1, so they have nothing left. **b2 contains no `relations` row, although `relations` had the highest pair
yield in b1 (0.682 of 22 rows)**; the pair yield of the b2 rows is not known and is not estimated here. The procedure
states this limit itself (`BATCH2_PROCEDURE.md`, "Limits").

**Methodology is 17 rows, not 65.** The 65 methodology items were the entire tail of that category (74 tail items, 9 used
by b1). 48 of them failed validation (47 on a de-duplication rule, 1 on both a form rule and a de-duplication rule); methodology has no tail
left for the single replacement wave, so a dropped methodology row stays dropped. Nothing was added, relabelled or relaxed to reach 65, and no rule,
threshold or seed was changed. Consequently **439 of the 456 rows (96%) are `concept_definition` and `taxonomy`**, and any
analysis by category should say so.

## First-pass yield and the replacement wave

* 504 first-attempt drafts -> **253 passed V1--V6 and D1--D5 on the first pass: 50.2%**; 251 ids failed (83
  `concept_definition`, 120 `taxonomy`, 48 `methodology`).
* One replacement wave (47.3): 203 of the 251 failed ids were replaced from the frame tail (371 wave calls over those 203
  ids -- the number of wave candidates that failed validation is therefore 371 - 203 = 168, an inference, not a logged
  field); 48 methodology ids could not be replaced. Replacement keeps the id and changes the term: **203 of the 456 rows
  carry a term different from the one `batch2_plan.json` allocated to their id**, and 253 carry the allocated term.
* What dropped the 251 ids (a row counted once per rule class; `validate_report_b2.json`): form/validation rules V only 45
  ids, de-duplication rules D only 193, both 13. By rule, with a row counted once per rule: D4 118, D5 114, D3 112, V5 token
  Jaccard > 0.50 49, V5 longest common substring >= 40 chars 14, D2 13, V4 (ASK not true on the snapshot) 2. The
  de-duplication share is much larger than in b1; that b2 is also de-duplicated against the frozen b1 bank is a likely
  reason (an inference, not tested).
* `validate_report_b2.json`: `n_in` 504, `n_kept` 456, `n_dropped` 251, `still_short_by` {methodology 48}.

## Author screen (CP-1): what was actually read

* 30 rows, 10 each from `concept_definition`, `taxonomy` and `methodology`, drawn with seed 20260915 by the b1 per-category
  procedure after sorting ids by number (`screen_b2_sample.csv`, sha256 `71b65b52bb32f07a98fe87c9ead8b54f130fb7558ac4d54f3f5cb3e69d2f8256`;
  blank sheet `screen_b2_sheet.csv`, sha256 `163049671b49c310d7822e769c3d2748e6c05eff4691dc03dc12639ea618596c`). Acceptance rule as in
  b1: <= 3 failures accepts, >= 4 rejects (`BATCH2_PROCEDURE.md` rule 8, committed before any b2 drafting call).
* Result: **0 failures of 30, accepted** (`SCREEN_b2_RESULT.md`). `screen_b2.csv` holds a header only, as `screen_b1.csv` does.
* **How that result was established, stated plainly.** The sheet the author saved, `screen_b2_sheet_filled.csv`, is
  byte-identical to the blank sheet (same sha256); no criterion carries a mark. A blank sheet cannot show whether every row
  passed or the marks were not saved, so the screen did not take the blank cells as a pass; the author then answered in
  the working session that the blank sheet is correct, and the 0-failure reading rests on that statement, not on the file.
  `screen_b2_sheet_filled.csv` is frozen with the other screen files because the result file points to it and because
  b1's identical-to-blank `screen_b1_r2_sheet_filled.csv` is frozen the same way.
* **Limitation: the author reviewed 30 of 456 rows. 426 rows are unscreened.** Of those, the screen is thin on the two
  big categories (10 of 219 and 10 of 220) and thick on methodology (10 of 17). The acceptance rule bounds the bad-row
  rate; it is not a check of every row: at a true bad-row rate of 10% the rule would have accepted with probability 0.647,
  at 15% with 0.322 (addendum 47.10). The screen read wording and agreement with the snapshot only. The author knows the
  study's hypothesis. No rendering, graph, eligibility or judge information was shown or consulted at any screen step.
* Three methodology rows whose question carries the term's definition (`CQE950`, `CQE975`, `CQE985`) were pointed out to
  the author beforehand as possible criterion-1 or criterion-4 rows; under the reading above none was marked.

## De-duplication

`dedup_log_b2.csv` was **recomputed over the 456 final rows** (maintainer, `logs_b2_frozen/DEVIATIONS_b2.md` D10); the
first log, computed over the 504 original drafts, is kept unchanged as `dedup_log_b2_rawdraft.csv`. Reference banks: the five
of b1 plus the frozen b1 bank (read as `b1_as_extra.jsonl`, a 494-row derived file of the b1 bank's ids, categories,
questions and groundings). Final log: one row per kept id, **450 keep, 6 log_only, 0 excluded**; the six log-only rows
(`CQE520`, `CQE523`, `CQE562`, `CQE595`, `CQE727`, `CQE809`; cosine 0.952--0.984) reach the log-only 0.95 line and stay in the
bank. The highest cosine to the nearest reference row is 0.984 (b1: 0.937, 0 pairs at 0.95). The raw-draft log has 504
rows: 296 keep, 206 exclude, 2 log_only; 160 of the 456 kept ids carry a non-keep decision there, because that decision
belongs to the dropped original row whose id the replacement reuses. For that reason `dedup_log_b2_rawdraft.csv` must not be
read as a statement about the bank.

## Blind audit

`BLIND_AUDIT_b2.md`: **B1 PASS, B2 PASS (0 forbidden opens), B3 NOT RUN.** B3, the transcript scan that b1's round 2 ran
with a stated limitation, was not run for b2 because the drafting sessions' transcripts were not identified
(`DEVIATIONS_b2.md` D8); b2 therefore has runtime-open-log evidence only (32,291 recorded opens in
`logs_b2_frozen/blind_open_log_b2.jsonl`, plus 167 in the audit/plan log). The limitation in the audit file applies:
B1-B2 cannot prove what a human or agent saw, and the session that designed the frame had read access to the renderings
and graphs. Beyond that, **the b2 composition rules were set after the C4 numbers were seen**, which the blind hook
neither covers nor claims to.

## Deviations from 47.3 as written

D1--D10 of `logs_b2_frozen/DEVIATIONS_b2.md` (same text as `logs_b2/DEVIATIONS_b2.md`); `BANK_PROVENANCE_b2.md` summarises
each. All are caller-side: no file under `tools/`, no item, no rule and no pinned hash was changed by any of them.

## What this freeze forbids from now on

From this commit onward, no question text, no grounding, no expected answer, no ASK, no category, no `cq_id` and no
validation or de-duplication rule of this bank is changed. A later change needs a new dated freeze of its own, and b1 is
never edited to accommodate b2.

## Next

Eligibility and the judgeable-pair set for the b2 rows (47.4): `_grounding_match_info` on the full renderings and the
question-only view manifest. That is the first step that reads the renderings for b2. Nothing in this freeze asserts
anything about eligibility, pair yield or judge scores for b2. If the b1 + b2 judgeable pairs stay under 210, the
procedure's label "target not met" applies (`BATCH2_PROCEDURE.md` rule 8, 47.3). The claim ceiling stays what 47.1 says it
is: judge scores of two substitute judges on question-only views of an AI-drafted bank the author screened on a sample only.
