# Provenance of the eqv2 bank, batch b2 (addendum 47, 47.3 "Batch 2"; manuscript Study 12)

> AI-generated draft; the author must review it before relying on it. Plan-based and exploratory; no pre-commitment label
> is attached. Written before the freeze commit, like `BANK_PROVENANCE_b1.md`. It states what was done and what was not; it
> does not say that anything has been approved, committed or tagged -- read that from the repository.

## Why there is a b2, and what that means for how it should be read

C4 on the frozen b1 bank gave 66 judgeable pairs of 494 rows (pair yield 0.1336) against the 210 the plan wants
(`C4_REPORT.md`, `BATCH2_SIZE.json`: K1 66, N1 494, target 210, needed true). 47.3's batch-2 rule then allows a second
batch of up to N2 = 504. **b2's composition was fixed after that result was known**, by rules the maintainer wrote with it
in view (`BATCH2_PROCEDURE.md`): the item list is the front of each category's remaining frame tail, the category quota is
N2 / 6 = 84 with `frame.allocate`'s round-robin redistribution of what the tail-less categories cannot give, and no
eligibility, score or yield figure entered the allocation. That separates the item list from the pair-yield results but
does not make it independent of them. The consequence is visible in the bank: it has no `relations` rows (that frame has no
tail) although `relations` had the highest b1 pair yield, and 96% of its rows are `concept_definition` and `taxonomy`.
Whether b2 lifts the judgeable pairs towards 210 is not known; nothing here estimates it.

## How the questions were written

- **Blind drafting.** `tools/draft.py` drafted all 504 items (`CQE505`..`CQE1008`) blind, with the same prompt as the b1
  round-2 draft (SHA-256 `a20414e1...`, `prompt_sha256_r2.json`; the tool stops if the live template hash differs). The model
  saw only the category, the frame rank, the term's local name and `rdfs:label`, its definition sentence, and
  parent/child/property names, all pulled by the script from `data/brick-v1.4.4.ttl`. The runtime audit hook
  (`sys.addaudithook`, patterns in `tools/blind_patterns.json`, extended for b2 by `view_manifest`, `pairs_b1`, `C4_REPORT`,
  `inputs/` and `BATCH2_SIZE`) logs every `open` and raises on a forbidden path.
- **Only the question sentence comes from the model.** `grounding`, `expected_answer` and the ASK query are built by the
  script. Temperature 0, `max_tokens` 256, JSON output, no tools, thinking off (see D1); sent through the local <internal-proxy> gateway,
  so no endpoint value, host, port or key is written to any file.
- **Model.** `Qwen3.8-Flash-Next`; the route identifier the tools recorded (`<internal-proxy>/Qwen/Qwen3.8-Flash-Next`) is kept
  unchanged in the `draft_model` column. The primary route was used for all 875 calls; the fallback was not needed.
- **Calls.** 875 logged calls, 2026-10-28 07:59:09--08:12:11 UTC, all `ok` at attempt 1: 504 first attempts and 371
  replacement-wave calls. The procedure commit `579d0dc` (07:58:03 UTC) precedes the first call.
- **What was and was not opened.** The frame was designed in a session with read access to the renderings and graphs (stated
  in 47.3, not excluded). The b2 drafting run is covered by the blind hook (below). The maintainer who wrote the b2 rules
  had seen the C4 numbers, which the hook does not cover.

## Validation, replacement and de-duplication

- **Validation V1--V6** (V1f included) with D1--D5 against the five reference banks **and the frozen b1 bank**, then exactly
  one replacement wave from the frame tail. First pass: 253 of 504 (**50.2%**) passed; 251 ids failed. 203 failed ids were
  replaced (the id is kept, the term is swapped for the next tail term that validates), 48 methodology ids were not
  (methodology's tail was fully allocated). Kept: 456.
- **Methodology is 17 rows**, because the 65 planned rows were the whole tail left after b1 and 48 failed with nothing to replace
  them (47 on de-duplication rules only, 1 on both a form and a de-duplication rule).
- **Which term is in each row.** 253 rows carry the term the plan allocated to their id; 203 carry a replacement term. In
  `logs_b2_frozen/draft_calls_b2.jsonl` the 371 wave calls cover those 203 ids (one call for 112 ids, two for 47, three for 27, and
  4 to 9 calls for the other 17); a candidate that fails validation is answered by the next tail term.
- **De-duplication log (D10).** The first `dedup_log_b2.csv` was produced over the 504 original drafts, which is not the set
  that enters the bank: 160 of the 456 kept ids carried an "exclude" or "log_only" decision that belonged to the dropped
  original row. The maintainer re-ran the same rules (D1--D5, `tau_emb` 0.5168, the five reference banks and the frozen b1
  bank as extra) over `validated_b2.jsonl` and replaced the file's content before the author saw the sample; the original is
  kept unchanged as `dedup_log_b2_rawdraft.csv`. Final: one row per kept id, 450 keep, 6 log_only, 0 excluded. The bank was
  not changed by this: it was the log that was wrong about which rows it described.
- The frozen b1 bank enters the de-duplication as `b1_as_extra.jsonl`, a derived file of that bank's 494 ids, categories,
  questions and groundings (checked equal to `cq_bank_brick_eqv2_b1.csv` on those four fields); the b1 bank itself was only read.

## Deviations from 47.3 as written (D1--D10 of `logs_b2_frozen/DEVIATIONS_b2.md`)

All are caller-side; no file under `tools/`, no item, no rule and no pinned hash was touched.

- **D1** thinking off realised as `reasoning_effort: "none"`, not `enable_thinking: false`, which the gateway ignores (same as b1 round 2 D1).
- **D2** a `content: null` envelope under HTTP 200 treated as retryable inside the tool's own 4-attempt budget (same as r2 D2); in this run 0 retries, 875 of 875 calls ok at attempt 1.
- **D3** gateway URL shape: the configured endpoint carries no path, so the driver resolves the `/v1/chat/completions` suffix, verified by a model-list request and one connectivity call; no endpoint value is in any file.
- **D4** route health checked before the run; primary route used throughout.
- **D5** the replacement wave is driven by wrapping `validate_batch` with a drafter that calls `draft.draft_one` (`validate.py` has no CLI seam for the wave); methodology had no tail left, so its drops stay dropped.
- **D6** the default model cache for the D5 embedding step was empty; the process was pointed at a pre-existing local backup of the same `all-MiniLM-L6-v2` model, offline; `tau_emb` is the pinned value.
- **D7** `blind_audit.py` crashed in `write_report` on the informational entries of exempt tools; the audit was run through a driver that executes a copy with that line made tolerant. The tool file was not edited; B1 and B2 logic is unchanged.
- **D8** **B3 (transcript scan) not run**: the drafting sessions' transcripts were not identified.
- **D9** the audit tool writes its hook log under a fixed name, so `blind_open_log_b1.jsonl` appears in `logs_b2/` next to `blind_open_log_b2.jsonl`; both have 0 forbidden opens.
- **D10** the de-duplication log was recomputed on the final rows (above).

## Blind checks (`BLIND_AUDIT_b2.md`)

- **B1** static scan of `blind_audit.py`, `common.py`, `dedup.py`, `draft.py`, `eligibility.py`, `frame.py`, `plan_b2.py`,
  `screen_sample.py`, `validate.py`, `views.py`: clean; the notes are prose mentions of the word `eligibility` in docstrings and the
  exempt-by-name entries for `eligibility.py` and `views.py` (they run only after a freeze).
- **B2** runtime open logs: 0 forbidden opens in `blind_open_log_b2.jsonl` (32,291 events) and `blind_open_log_b1.jsonl` (167
  events, the audit and plan runs). This is the decisive access evidence for the drafting run. Re-checked on the frozen copies with the tool's own matcher: 0 hits.
- **B3 not run** (D8). Unlike b1's accepted round, b2 has no transcript-scan evidence.
- **Limitation, quoted verbatim from `BLIND_AUDIT_b2.md`:**
  > B1-B2 cannot prove what a human or agent saw. The session that designed the frame had read access to the renderings and graphs, and recomputed their hashes; that access is stated, not excluded (addendum 47, 47.3).

## The author screen

30 of 456 rows, 10 each from `concept_definition`, `taxonomy` and `methodology` (seed 20260915). Result 0 failures of 30,
accepted under the <= 3 rule. **The saved sheet is byte-identical to the blank sheet, so the pass rests on the author's
stated answer** ("the blank sheet as it stands is correct"), as `SCREEN_b2_RESULT.md` records; the maintainer had asked
because a blank sheet cannot by itself separate "all passed" from "marks not saved". 426 rows were not read. The screen is much
thinner on `concept_definition` and `taxonomy` (10 of ~220 each) than on `methodology` (10 of 17). No eligibility, rendering, graph or judge
information was shown at the screen.

## What the frozen file is and is not

- It is `validated_b2.jsonl`'s 456 kept rows projected into the CSV, ordered by numeric `cq_id`, with
  **question/grounding/expected_answer byte-identical to those rows** (verified by a round-trip over every row in code, not by eye;
  the same code reproduces the frozen b1 CSV byte for byte from `validated_b1_r2.jsonl`). See `BANK_FREEZE_b2.md` for the
  columns, the blank-cell policy and the category counts.
- It is an AI draft, **not a human-checked answer key**. It carries no eligibility information: nothing from 47.4 (the
  renderings) was read or computed to make it. It says nothing about the planned judges, the full renderings, other domains, human
  labels, or support/over/under-credit (47.1).
- Files referenced but not part of this bank, by design: `frame_summary.json`, `tau_emb.json`, `prompt_sha256_r2.json`, the
  committed tools and tests, `BATCH2_PROCEDURE.md`, `batch2_plan.json` and `BATCH2_SIZE.json` (`579d0dc`), `C4_REPORT.md`
  (`769871d`), and the frozen b1 bank and its files (`9879780`).
- Not part of this freeze, by decision: round-1/round-2 working directories and logs of b1 (`round1/`, `logs/`, `logs_r2/`
  originals), `SCREEN_b1_RESULT.md` (provenance unknown, not cited by b1 either), `*_SUPERSEDED` files, the raw
  `logs_b2/` open logs (they hold absolute machine paths; `logs_b2_frozen/` is their filtered copy), and anything outside this
  directory.
