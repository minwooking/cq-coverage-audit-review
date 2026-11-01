# Batch 2 (b2) procedure: tools, composition rules, expected composition (addendum 47, 47.3 "Batch 2")

> **AI-generated draft.** The tools, tests and this file were written by an AI assistant; a person must review and test
> them before they are used. Plan-based, **exploratory** (addendum 47.0): no pre-commitment label is attached to this
> bank. Nothing here edits `PLAN.md`, `AMENDMENT_47A1.md`, the frozen b1 bank or any frozen evidence file.

## What this file is

47.3 calls for a second batch when the judgeable pairs of b1 fall below 210 (C4: K1 = 66), and fixes its size rule.
This file records how the b2 item list is composed and how b2 is drafted, validated, de-duplicated, audited and
screened. The author approved running b2; the composition rules below were set by the maintainer. Drafting has **not**
started when this file is written: the work described here is tools, tests, the item list and this procedure.

## Rules (as implemented)

1. **Size.** N2 = 504 (the 47.3 cap; read once from the size file by `tools/plan_b2.py`, recorded in
   `batch2_plan.json`). Category quota = N2 / 6 = 84, the same quota rule as b1.
2. **Capacity.** Per category: the frame tail (`frame_summary.json`, key `frame_tail`) minus the tail items b1 used.
   A category with no tail (instances, relations, slots_facets) has capacity 0 and no b2 rows.
3. **Reallocation.** A quota the capacity cannot fill is redistributed by `frame.allocate` -- the function that
   allocated b1 (round-robin, largest remaining frame first; test `test_allocate_roundrobin_largest_first`). A category
   whose tail is used up gets 0; the plan is not changed.
4. **Selection.** Within a category the items are the front of the remaining tail, in the order `frame.py` fixed with
   seed 20260913; nothing is reshuffled. Frame ranks are `frame_tail_frame_rank`.
5. **Ids.** `CQE505` onward in canonical category order (concept_definition, taxonomy, relations, slots_facets,
   instances, methodology), tail order within a category.
6. **Prompt.** The revised template, SHA-256 `a20414e1bfd2e5c354066696d13b4e76229a1ea2b3714347de2ec56ac9008b84`
   (`prompt_sha256_r2.json`); `draft.py` stops when the live template hash differs (unchanged behaviour). Model
   parameters (temperature 0, max_tokens 256, thinking off, JSON output, no tools) and the in-flight cap (default 8,
   hard cap 16) are b1's.
7. **Outputs.** `draft_b2.jsonl`, `validated_b2.jsonl`, `validate_report_b2.json`, `dedup_log_b2.csv`,
   `BLIND_AUDIT_b2.md`; logs in `bank/eqv2_2026-10/logs_b2/` (set `EQV2_LOG_DIR`). Validation V1-V6 (V1f included) with
   exactly one replacement wave; de-duplication D1-D5 against the five reference banks **and the frozen b1 bank**.
8. **Author screen (b2 CP-1).** 30 rows over the categories that hold b2 rows (expected: concept_definition, taxonomy,
   methodology), equal shares (10 each for three categories). A category with fewer passing ids than its share gives
   all of them and the missing rows go one at a time, in canonical order, to the other categories. Seed **20260915**;
   the b1 / round-2 per-category shuffle (one `Random(seed)`, canonical order, per category the sorted ids shuffled,
   the first k kept, output in id order). Acceptance as in b1: <= 3 failures accepts, >= 4 rejects; a rejected b2 means
   the study proceeds on b1 alone, labeled "target not met", and b2 is not re-drafted (47.3).
9. **Blindness.** The drafting, validation and de-duplication tools may not read the C4 outputs or the size file (see
   "Blind patterns"). They read `batch2_plan.json` only.

## Deriving what b1 used of the tail

b1's single replacement wave (`validate.py`) walks each category's tail strictly in order with one pointer; a dropped
row consumes tail candidates until one validates. In the committed b1 report (`validate_report_b1_r2.json`) every
dropped row of a category that has a tail was replaced (`replaced_by` is set; the 10 unreplaced drops are all in the
three categories without a tail). The replacing rows are in `validated_b1_r2.jsonl` (field `term`; the frozen bank
carries the same questions). The consumed prefix of a category is therefore `tail[:k+1]`, with k the largest tail index
among the terms of the replacing rows; a candidate that was drafted but failed validation lies below k and is consumed
too. `plan_b2.py` computes this and stops if a replacing term is not in the tail, two rows share a tail term, or a
tail-bearing category has an unreplaced drop. Cross-check (run when the round-2 call log is present, test
`test_b1_used_tail_matches_draft_call_log_when_present`): the tail terms drafted in the wave are exactly the indices
0..k of each prefix. No frozen file is modified.

| category | tail items | used by b1 | remaining | quota | taken from quota | redistributed in | **b2 rows** |
|---|---|---|---|---|---|---|---|
| concept_definition | 984 | 5 (5 replacements) | 979 | 84 | 84 | 135 | **219** |
| taxonomy | 1453 | 31 (24 replacements, 7 candidates failed) | 1422 | 84 | 84 | 136 | **220** |
| relations | 0 | 0 | 0 | 84 | 0 | 0 | **0** |
| slots_facets | 0 | 0 | 0 | 84 | 0 | 0 | **0** |
| instances | 0 | 0 | 0 | 84 | 0 | 0 | **0** |
| methodology | 74 | 9 (8 replacements, 1 candidate failed) | 65 | 84 | 65 | 0 | **65** |
| total | 2511 | 45 | 2466 | | | | **504** |

The quota of the three tail-less categories (252) and methodology's shortfall (19) give 271 rows to redistribute;
taxonomy, the largest remaining frame, takes 136 and concept_definition 135. Ids: concept_definition `CQE505`-`CQE723`,
taxonomy `CQE724`-`CQE943`, methodology `CQE944`-`CQE1008`. Methodology's tail is fully used by the 65 b2 rows, so b2's
replacement wave has no methodology candidates (a dropped methodology row stays dropped; the batch continues short).

## Item list and hashes

`bank/eqv2_2026-10/batch2_plan.json` holds N2, per-category capacity / quota / allocation, and the 504 items (`cq_id`,
`category`, `term`, `frame_rank`, `tail_index`). It carries no timestamp and is rewritten byte-identically from the same
inputs.

| quantity | SHA-256 |
|---|---|
| `batch2_plan.json` (file) | `9160ddb1bd00d5b9b97db9686e1715c035a3c7cb9e66c2fa7caed77e42fbd81a` |
| item list (`items_sha256` inside the file: sorted-key compact JSON of `items`) | `2dff621d42996c19859cb16c9e7f8337dc1f3186c7858f0520590880ac233b09` |
| prompt template | `a20414e1bfd2e5c354066696d13b4e76229a1ea2b3714347de2ec56ac9008b84` |
| b1 item list (`common.frame_items(frame, "b1")`, unchanged) | `b17eb97a6e143d90fbde9cc60c3e7c8fb6647179257092e68258282372c2c047` |

`common.frame_items(frame, "b2")` reads the plan and checks every item against the frame tail and the id sequence, so a
hand-edited plan is refused. Regenerate and compare with `python3 plan_b2.py --size-file <size json> --check`.

## Commands (run from `bank/eqv2_2026-10/tools`; the model route comes from the environment, never from a file)

```
# item list (reads the size file once; writes ../batch2_plan.json)
python3 plan_b2.py --size-file ../<size json> --out ../batch2_plan.json

# b1 as a de-duplication reference (derived file; the frozen bank is only read)
python3 plan_b2.py --b1-extra ../cq_bank_brick_eqv2_b1.csv --out ../b1_as_extra.jsonl

# draft (P3-style; --execute only when the author says go)
EQV2_LOG_DIR=../logs_b2 EQV2_DRAFT_ENDPOINT=... EQV2_DRAFT_MODEL=... \
    python3 draft.py --batch b2 --execute --out ../draft_b2.jsonl

# validate V1-V6 with D1-D5 against the five reference banks and b1; one replacement wave
EQV2_LOG_DIR=../logs_b2 python3 validate.py --batch b2 --rows ../draft_b2.jsonl --out ../validated_b2.jsonl \
    --report ../validate_report_b2.json --extra ../b1_as_extra.jsonl

# de-duplication log
EQV2_LOG_DIR=../logs_b2 python3 dedup.py --batch b2 --rows ../draft_b2.jsonl --extra ../b1_as_extra.jsonl \
    --log ../dedup_log_b2.csv

# blind audit (B1 static, B2 runtime log; B3 with the drafting session transcripts)
EQV2_LOG_DIR=../logs_b2 python3 blind_audit.py --logs ../logs_b2 --out ../BLIND_AUDIT_b2.md

# author screen sample and sheet (seed 20260915)
python3 screen_sample.py --preset b2 --out ../screen_b2_sample.csv --sheet ../screen_b2_sheet.csv
```

`screen_b2_sheet.csv` has the columns of `screen_b1_sheet.csv` (five text columns, then the five criteria columns,
blank). The drafting step's replacement wave needs a drafter callable (as in b1's P3); the `--extra` option of
`validate.py` and `dedup.py` refuses a b2 run without it. Ids from `CQE1000` have four digits: V1 accepts
`CQE\d{3,4}` (b1's three-digit ids pass unchanged), and ordered output uses the numeric id (for b1's three-digit ids
this equals the string order).

## Blind patterns

`tools/blind_patterns.json` already blocked `eligibility` (as a substring, so `eligibility_b1.json`), `manifests/`,
`views_for_raters` and `annotation/`. Added: `view_manifest`, `pairs_b1`, `C4_REPORT`, `inputs/` and `BATCH2_SIZE`.
Same-purpose static and runtime enforcement (`blind_audit.py` B1 scan and the audit hook); `eligibility.py` and
`views.py` stay exempt by name, and `blind_audit.py` is unchanged. `plan_b2.py` is not a drafting tool: it takes the
size file as an argument, installs no hook, and is scanned (not exempt) by B1 with zero violations. The existing b1
open logs (five log directories) contain zero hits under the extended list.

## Limits

- **The rules were written after b1 and C4 were seen.** The maintainer set them knowing b1's outcome (K1 = 66 < 210).
  They use only the quota and the tail sizes; eligibility, scores and yield did not enter the category allocation. That
  separates the item list from the pair-yield results but does not make it independent of them.
- **b2 omits the highest-yield category.** Relations had the highest pair yield in b1 (0.68, as the maintainer
  reported it; this procedure did not open C4 outputs) and has no tail, so b2 contains none. Its expected number of
  judgeable pairs may be lower than b1's average yield suggests; no estimate is made here, and the "target not met"
  label applies if the total stays under 210.
- **Composition is concentrated.** 439 of 504 rows (87%) are concept_definition and taxonomy; methodology, 65 rows, is
  the whole of its tail. A methodology row dropped in validation is not replaced.
- **Terms recur across categories.** A term can sit in several category frames. In b2, 32 terms occur in two categories
  and 82 b2 terms also occur in b1 under another category (b1 itself has 43 such terms). Different category, different
  question and grounding; D1-D5 apply as written.
- **Same prompt and route as the b1 re-draft.** The template, the model family and the sampling parameters are b1's, so
  b2 shares b1's style limits. Screening covers 30 of 504 rows; the rest stand unscreened.
- **Not checked here:** the embedding step of D5 (needs the local model; the tests inject a mock), and the real
  validation and de-duplication of b2 rows, which need drafted rows.
