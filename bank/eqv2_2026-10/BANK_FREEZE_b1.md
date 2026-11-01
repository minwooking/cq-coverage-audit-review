# Freeze of the eqv2 bank, batch b1 (addendum 47, 47.3 CP-2; manuscript Study 12)

> **AI-generated draft.** This file and every file it freezes were written by an AI assistant; the author must review
> them before they are relied on. Plan-based, **exploratory** -- no pre-commitment label of the kind used for earlier
> studies is attached to this bank (addendum 47.0). No row was checked against a rendering, an eligibility result, a
> graph or a judge score; only 30 of the 494 rows were read by the author. Nothing in this file is a registration.

Frozen by the commit that adds this file; the git commit time is the authoritative date (drafted 2026-10-28). The
author approved the freeze (CP-2) in the working session after the maintainer's report on this bank, and the maintainer
made the commit and created the tag `access2026-eqv2-b1-freeze` on that approval.

| field | value |
|---|---|
| Bank file | `bank/eqv2_2026-10/cq_bank_brick_eqv2_b1.csv` |
| Rows | 494 (`CQE001`..`CQE504`, with 10 ids absent -- see "Short categories") |
| Bank SHA-256 | `b8478fca86de80b0c998eb6e5a3f7f11ef62433bcc75428e0bf8abe03d336efe` (every file of this freeze commit except that list itself is in `SHA256SUMS_b1_freeze.txt`) |
| Tag | `access2026-eqv2-b1-freeze` (created with the freeze commit) |
| Tool commit | `20b2a73` (bank tools, tests, `frame_summary.json` -- C2) |
| Prompt-revision commit | `67f5dcd` (amendment 47.A1, written after the CP-1 rejection of b1, before the re-draft) |
| Row provenance | `validated_b1_r2.jsonl` (round 2, sha256 `913208815287a8ff11299626ee9d8ee7aaf0847e8d45dc9f83b9b574e8a8617c`); no question, grounding or expected-answer text was edited to produce this file |
| Preceding draft file | `draft_b1_r2.jsonl`, 504 rows, sha256 `fba2dbe0654f9a1ce493b3016a57918f2c62dc4f0f7bd1f1684e01aa14388ff7` |
| Snapshot | `data/brick-v1.4.4.ttl`, sha256 `b65720b7b9b64c646745c689777e6138c0d59ce0088df0aeb78fbd444d04d8e7` |
| Seed (frame) | `20260913`, pinned in `frame_summary.json` |
| Seed (round-2 sample) | `20260914` (47.A1.5; the drawn ids and the procedure are recorded in `logs_r2/DEVIATIONS_r2.md` D6) |
| Prompt SHA-256 (this bank) | `a20414e1bfd2e5c354066696d13b4e76229a1ea2b3714347de2ec56ac9008b84` (`prompt_sha256_r2.json`) |
| Previous prompt SHA-256 | `baf4e1fe6367e387b5fb443d873e850275fe53563d67e8f0c4ccd20dbaa3987f` (`frame_summary.json`, round 1 -- not rewritten) |
| `tau_emb` | `0.5168` (`tau_emb.json`: p10 of 36 holdout-paraphrase cosine pairs, `all-MiniLM-L6-v2`, local CPU) |
| Renderings (not used here, stated for the record) | A `f6cca070efee8d933b41ba96d2d2b9c666af5bd804926c22ae0834b099830b98`, B `d0b9543521340c2719381cc7d1312b704322c0e33d452166212840854cbc165f`; graphs A `1a5cc075065ac1f493e7731ac20e638481754c1a79f586b6e82a25320cb1bc32`, B `20d015a83b1158fdf1bc598b75127f63eed088f0a10bc54e91d88d411b4fe490` |

## Columns

The 20 columns of `bank/expansion_2026-10/cq_bank_brick_expansion_v1.csv` come first, in that order, then the five
columns 47.3 adds (`author_screen`, `batch`, `frame_rank`, `draft_model`, `prompt_sha256`). `cluster_id` equals `cq_id`
on every row (47.3's justification: D3 makes the primary grounding term unique). Values are taken verbatim from
`validated_b1_r2.jsonl`; no question text was touched.

Eleven expansion columns are **blank on every row**, and `created` carries one value. The blanks are not an oversight:

| column | why blank |
|---|---|
| `ask_query_file` | the eqv2 tools never write `.rq` files; the ASK query is kept inline in `validated_b1_r2.jsonl` (field `ask`). There is no file to point at. |
| `author_review` | the author read a 30-row sample (CP-1), not the bank; see `author_screen`. |
| `screen_format`, `screen_grounding`, `screen_ask`, `screen_fail`, `screen_notes`, `screen_dup`, `nearest_existing` | the expansion builder recorded these per row in its own CSV. Here the equivalent machinery is `validate_report_b1_r2.json` (V1--V6, per-row drop reasons) and `dedup_log_b1_r2.csv` (D1--D5, per-row nearest reference). Reformatting those results into these columns would be a transcription that changes nothing except the chance of error, so they stay where they are. |
| `anchor_rule_check` | not performed in this stage: it belongs to the frame/anchor machinery whose output is C4, and C4 has not run. |
| `eligibility_anchors` | not computed. Eligibility requires the A and B renderings and is the subject of 47.4 (commit C4); opening them or computing them before the freeze is forbidden by 47.3. |
| `created` | **filled**: `2026-10-27` on all 494 rows. Not a bank-constant but a measured one: it is the UTC date of the drafting call that produced each row, read from `logs_r2/draft_calls_b1.jsonl`, where all 504 drafted ids (the 494 kept ids without exception) carry that date. |

`status` is `draft` on every row (the value the draft rows carry); `author_screen` is `passed_r2_sample` on the 30
sampled ids and `unscreened` on the other 464.

## Rows per category, and why the small categories are short

| category | drafted (frame allocation) | validated (this bank) | short by | frame size after exclusion | frame tail |
|---|---|---|---|---|---|
| concept_definition | 140 | 140 | 0 | 1124 | 984 items |
| taxonomy | 141 | 141 | 0 | 1594 | 1453 items |
| methodology | 140 | 140 | 0 | 214 | 74 items |
| instances | 33 | 28 | 5 | 33 (= whole frame) | none |
| slots_facets | 25 | 23 | 2 | 25 (= whole frame) | none |
| relations | 25 | 22 | 3 | 25 (= whole frame) | none |
| **total** | **504** | **494** | **10** | | |

The 84-per-category quota of 47.3 is not met by `instances`, `relations` and `slots_facets` **even though their whole
frame was drafted**: their frames, after the exclusion of every term used as a grounding anchor by the five reference
banks plus their aliases, are smaller than 84 (33, 25, 25 terms), so they give their whole frame and the deficit
(171 items) is redistributed round-robin to the three largest frames -- 140 / 140 / 141 (recorded in
`frame_summary.json`'s `redistribution` block, where `deficit_after_redistribution` is 0).

The remaining 10 missing rows are validation losses: 47 drafted rows failed V1--V6/D1--D5, 37 of them were replaced
from a frame tail (all 37 came from the three big categories' tails, as 47.3 requires), and 10 could not be replaced
because those categories have no tail -- 5 instances, 3 relations, 2 slots_facets. `relations` is short by the three
rows that fail V4 in both rounds (`CQE290` `brick:hasAddress`, `CQE298` `brick:isAssociatedWith`, `CQE300`
`rec:includes`, whose shape carries no `sh:class`; 47.A1.2), which is the same 3 that the round-2 report gives as
`still_short_by` alongside 5 instances and 2 slots_facets. So the 10 unreplaced ids are exactly those 10. Nothing was
added or re-labelled to reach 504, and no rule, threshold or seed was changed to make the categories fuller.

Category skew is therefore structural, not a side effect of this freeze: 141 + 140 + 140 of the 494 rows sit in the
three large categories, and any cluster-level analysis over this bank should say so.

## Author screen (CP-1): what was actually read

* Round 1: 30 rows drawn with seed 20260913 over the V-passing ids -- **6 failures of 30, batch rejected**
  (`screen_b1_sheet_filled_r1.csv`, committed in `67f5dcd`, sha256 `8f2561604829064768baa44dd72b1078b262189c9aa1d8453976e0805abf0951`;
  the blank sheet `c36c663ed40305ebdc6a5bc75d2db09ab03d8571fb8f50be648587c5f98c6372`; the per-row reason table is in
  `harness/study29_eqv2_ab/AMENDMENT_47A1.md` 47.A1.1). Five of the six were `relations` rows: the prompt filled the
  shape-owner slot with the property itself, so the sentence repeated the term.
* Amendment 47.A1 (commit `67f5dcd`) is the one and only prompt revision 47.3 allows, and it was committed before any
  re-draft. The whole item list was re-drafted; the new sample draws with seed 20260914.
* Round 2: 30 rows sampled (`screen_b1_r2_sample.csv`, sha256 `65a7fed298ee48a9b81012f348b2588a62c6e14c02eac7111b68178561c013c3`;
  blank sheet `screen_b1_r2_sheet.csv`, sha256 `15a2849cc87b4f58a63f342b90dfcc9d60f5712c681902a6e613afece04420de`) --
  **0 failures of 30, accepted** (`SCREEN_b1_r2_RESULT.md`; that file records how the verdict was established: the
  saved sheet came back byte-identical to the blank, so the acceptance rests on the author's stated answer, not on the
  file). Because there were 0 sampled failures, `screen_b1.csv` holds a header only.
* **Limitation, stated plainly: the author reviewed 30 of 494 rows. 464 rows are unscreened.** The acceptance rule
  (accept on <= 3 failures of 30) bounds the bad-row rate; it is not a check of every row: at a true bad-row rate of
  10% the rule would have accepted with probability 0.647, at 15% with 0.322 (addendum 47.10). Both screens were run
  by the author who knows the study's hypothesis. No rendering, graph, eligibility or judge information was shown or
  consulted at any screen step.

## Validation and de-duplication tally (round 2, the accepted run)

* Input drafts 504 -> kept 494; dropped 47 rows, of which 37 were replaced from the frame tail and 10 were not
  replaceable. Source: `validate_report_b1_r2.json` (sha256 `39344367bdea3b6deecf38361f66b7ca8b181661fe8880e8855ac0e0988b70a3`),
  `n_in` 504 / `n_kept` 494 / `n_dropped` 47 / `still_short_by` {relations 3, slots_facets 2, instances 5}.
* Drop reasons, counting a row once per rule class (a row can appear in more than one class: 47 rows, 51 class hits):
  V5 long-common-substring >= 40 chars 17 rows; V5 token Jaccard > 0.50 26 rows; V4 ASK not true on the snapshot 3
  rows (the three `relations` shape-owner rows above); V2 term name/label absent from the question 1 row;
  D4 question token Jaccard >= 0.80 1 row; D5 embedding cosine >= `tau_emb` with anchor Jaccard >= 0.5 3 rows.
  By category: `taxonomy` 24 (all V5), `concept_definition` 5, `methodology` 8 (5 V5 + 3 D5), `instances` 5,
  `relations` 3 (all V4), `slots_facets` 2.
* De-duplication: `dedup_log_b1_r2.csv` (sha256 `db2888a7b6112aac309f42c1f9226c1c3d3dc72049fe9fb4b70e526dfcb7f36f`)
  has exactly one row per kept `cq_id`, all decisions `keep`, rule `-`; the highest cosine to the nearest reference
  row is 0.937 and 0 pairs reach the log-only 0.95 line. Reference banks: `cq_bank_brick_v1.csv`, `study2_llm_labels/bank_frozen_v1.csv`,
  `expansion_2026-10/cq_bank_brick_expansion_v1.csv`, `cq_bank_brick_v2.csv`, `cq_bank_brick_v1_paraphrases.csv`.
  `cluster_id` = `cq_id` is justified by D3's uniqueness of the primary grounding term.
* Blind audit of the accepted run: `BLIND_AUDIT_b1_r2.md` -- B1 PASS, B2 PASS (0 forbidden opens), B3 CHECK, with the
  limitation text quoted in `BANK_PROVENANCE_b1.md`.

## What this freeze forbids from now on

From this commit onward, no question text, no grounding, no expected answer, no ASK, no category, no `cq_id` and no
validation or de-duplication rule of this bank is changed. A later change needs a new dated freeze of its own. If the
judgeable-pair count from 47.4 falls short of 210, batch b2 may be drafted under 47.3's batch-2 rule and 47.A1.5's
naming discipline; b2 asserts the prompt hash pinned above, and b1 is never edited to accommodate it.

## Next

**C4: eligibility and the judgeable-pair set** (47.4) -- `_grounding_match_info` on the full A and B renderings, the
question-only view manifest, and the pair/floor sets. That is the first step that reads the renderings, and it is the
first thing that can be done with this bank committed. Nothing in this freeze asserts anything about eligibility,
pair yield or judge scores; the claim ceiling stays what 47.1 says it is (judge scores of two substitute judges on
question-only views of an AI-drafted bank the author screened on a sample only).
