# PREREG addendum 31 (exploratory, post hoc) -- an objective adjudication of the disagreements between persona-ensemble LLM labels and human evidence labels

> AI-generated draft; the author must review it before it is relied on. Date: 2026-10-19. **Addendum 31: post hoc with respect to the registered study and to addendum 30, pre-specified with respect to this check.** This file is committed alone, before any number of this addendum is computed (the repository commit that holds it is the freeze). The manuscript sources (`main.tex`, `main_ko.tex`, `supplement.tex`) are not edited by this addendum. All code, commands and configuration named here are AI-generated and must be reviewed and tested by a person before reuse; none of it is to be applied to a production system without that review. Before this file is shared outside the team, check that no confidential company information, host name, address, port or key is in it or in the outputs it names. No model call, no server access and no new label is part of this addendum.

## 31.1 Status, question, claim ceiling

Exploratory and post hoc. No confirmatory hypothesis. The reading rule of section 31.8 only decides which sentence the result supports.

**Decision it serves (main session).** The human evidence labels stay the reference and the primary label source. The persona-ensemble LLM labels of addendum 30 are an additional, post hoc label source. They do not replace the human labels, and no headline number of the paper changes. This addendum cannot change that decision; it adds a label-free reading of the cells on which the two disagree.

**Question.** On the Tier 1 cells (the 188 primary holdout cells, addendum 30) where a model's consistent label (primary rule R25: at least 23 of 25 labels agree) disagrees with a human label, which side is right according to an objective, label-free criterion: the frozen bank's expected answer and grounding terms for that question, tested on the text each side relies on?

**Claim ceiling (fixed before any number).** The criterion is a term-occurrence test, a necessary condition for support and not a sufficient one. A passed test does not prove that a span supports an answer, and a failed test does not prove that it does not. The check says on which side of a disagreement the objective term evidence lies. It does not make any label source ground truth, and no sentence of this addendum is to be read as "LLM labels are more accurate than human labels" or as the reverse for cells outside the consistent subset.

**Disclosure (what this session knew before this commit).**
(i) The addendum 30 aggregates (`results.json`, commit 8e77c0a): coverage of the consistency filter, kappa of the consistent labels with each human, human-human kappa on the same cells, the share of label 1 among the consistent labels (for GLM-4.7-Flash 2.6%), `pi-hat` under the LLM and the human labels, test-retest alpha. (ii) The structure of the files named in 31.2 (column names; the bank's columns; the line-oriented format of the renderings); the row counts and the S=1 span counts of the second rater's analysis file (126 spans for 126 label-1 cells, 18 of them multi-line, longest 17,121 characters); the first rows of the second rater's label files were displayed once while their columns were checked. (iii) **No term check of any kind has been run on any Tier 1 cell, and no per-cell human label has been crossed with a per-cell LLM label in this session** before this file's commit.

## 31.2 Inputs (read-only; sha256 at plan time)

| item | file | sha256 |
|---|---|---|
| frozen bank (columns `question`, `grounding`, `expected_answer` read here, as in addendum 27; never sent to any model) | `bank/cq_bank_brick_v1.csv` | `993c5e1164540dce0f2f9bf2e6ed397cf45910da7889300feeaad6543edb8507` (= `run_holdout.FROZEN_BANK_SHA256`, asserted) |
| grounding-term and answer-term machinery (imported, not edited) | `harness/review6_natural/grounding_check.py` (`local_anchors`, `content_terms`, `present`, `forms_of`) | `c996e4ab6796a7144746490bd09cb4a45a8f6a517ec19830bbe5e27eafbb5280` |
| whitespace normalization (same rule imported in spirit: `norm`) | `harness/review6_natural/analyze_natural.py` | `6a76431536f53b50e3295494f3c93d0c2223deefdb1a0ab2c8a3e7caffaa6216` |
| the anchor extractor behind `local_anchors` | `harness/run_holdout.py` (`_grounding_anchors`) | `2fcc43516b45b80dab9022e4f0e03dcb1730a62456e920b61b9cff32eaf12c38` |
| cell manifest: view the model saw (`view_path`), full rendering the humans saw (`full_path`), sha256 of both | `harness/review6_raters/cells_manifest.json` | `112e49e1c7f80b77d390c62c6f6e8f85f00299707edddfd7e343d2218fde5a2d` |
| full renderings A..F (E and F are identical files) | `harness/variants/<V>/rendered_view.txt` | A `f6cca070efee8d933b41ba96d2d2b9c666af5bd804926c22ae0834b099830b98`, B `d0b9543521340c2719381cc7d1312b704322c0e33d452166212840854cbc165f`, C `e1f1ec9eb249070e4d05b7f710b069e8f6995754c967632ea89fc566143b9a46`, D `ac689ff4db929896e0efa33f3983852cb7cd1ca8941731dabd531772dc09c22e`, E = F `cb451ed3cc64f134365c3d01d0e9ae91771246d262b0250edf01718a07a95f91` |
| LLM raw records (Tier 1; slot labels, quoted spans) | `harness/review10_llm_labels/raw/{glm,gptoss,qwen}_t1.jsonl.gz` | glm `5d827f6513fc00ac8cad7217853e0456b456de6542b42fe44178a8ba9d598a7a`, gptoss `ae0eebefec48ee67df5e21637b88fd0a780b48d6910a1b0b56d135e58136be7d`, qwen `ea2c467d13669d0fc5a490e3dff58cb50afd062d2abf3a2e42dc359198175e92` (the uncompressed-text digests are in `results.json` `meta.raw_sha256_of_uncompressed_text` and are asserted) |
| addendum 30 aggregates (reliability numbers) | `harness/review10_llm_labels/results.json` | `b16d8dc2fef3b80e80483ead967d40a64ea949406ebca4ccf79dd3ba3545db4c` |
| addendum 30 loaders and statistics (imported, not edited) | `harness/review10_llm_labels/analyze.py` (`Raw`, `consistent`, `bca`, `csum`, `kappa_flat`, `alpha_cols`) | `85ada1a658be97952239d417ae8ecf62c1a781fce06e04c5f7898714b5533677` |
| human labels, both raters (de-identified analysis files, through `review6_reanalysis/common.load_188`) | `harness/real_run/results_human_pass/unsealed_2026-10-09/per_cell.rerun_0dbe6e9.json` and `annotation/second_pass_2026-10-13/v3/results_v3_cells.json` | `5aebf70b6af9b4468f3c066ba84215699316ae5342d33b5c61d6cb4bd90a9248` and `13d87590eb06e5359e55a22fc018c6201caa029a4885c0c7f3a9874e2427c207` |
| the second rater's quoted spans (de-identified: columns `cell_id`, `A`, `rater_L1`, `evidence_span_verbatim` only; the input the registered analyzer takes) | `annotation/second_pass_2026-10-13/v3/labels_for_analysis_v3.csv` | `79e12f6b4c3a5979f875f98ecb53698b4a69357eb33bee9f0f50e30d88149bd4` |

**Human spans.** The second rater (R2) has quoted spans in a non-restricted analysis file (above). The first rater (AH) has none in any non-restricted file: the per-cell analysis file carries no span text, and the locked label file lives outside the repository. For AH the check therefore falls back to the rendering level (31.5). The script asserts that the label `A` of the span file equals the label `S` of the v3 per-cell file for all 188 cells and that every label-1 cell has a non-empty span and no label-0 cell has one.

**Never opened:** `site_key*`, `labeling_sheet_key*`, `human_labels_export*`, `views_for_raters.zip`, `.env` files, sealed or employee files; and `labels_v3.csv` (rater notes, dwell times). No server is contacted. No per-cell human label and no per-cell human-LLM disagreement is written to any output (aggregates only).

## 31.3 Cells and groups

Tier 1 only (the 188 primary cells; 33 question clusters). For a model `m` in {`glm`, `gptoss`, `qwen`} the cells are the `evaluated` cells of addendum 30 (182, 182, 183) that are **R25-consistent** (>= 23 of 25 `S_final` labels agree; label = majority; the `Raw`/`consistent` code of `analyze.py`). For a human `h` in {AH, R2}, with `L_i` the consistent LLM label and `S_hi` the human label of cell `i`:

* **Ag** (agreement) = `L_i = S_hi`; **Ag11** (both credit support) and **Ag00** (both give none).
* **D** (disagreement) = `L_i != S_hi`; **D10** (the human credits, the model does not: `S_h = 1`, `L = 0`) and **D01** (the model credits, the human does not: `S_h = 0`, `L = 1`).

Six (model, human) pairs. A group with fewer than 5 cells gets counts only, no interval.

## 31.4 The objective criterion (fixed here; no part of it is tuned afterwards)

For a question `q` with bank row (`grounding`, `expected_answer`):

* **anchors(q)** = `grounding_check.local_anchors(grounding)`: the local names of the schema terms the grounding refers to (the same anchors that define the paper's eligibility rule).
* **answer terms(q)** = `grounding_check.content_terms(expected_answer, forms of the anchors)`: the content words (length >= 4, stop words and anchor words removed, plural stripped) of the expected answer.
* **A text unit passes the term test** iff (a) every anchor of `q` is present in it (`grounding_check.present`: whole-form match, case-insensitive, `_` and `-` as separators, camel-case split) **and** (b) at least **50%** of the answer terms occur in it (whole-word match with an optional plural suffix, case-insensitive). This is the L2 rule of the grounding check of addendum 27 (anchors present and >= 50% of the answer terms in one unit), applied to a text unit instead of a documentation section. The 50% threshold is the one of that check and is not varied.
* **Normalization**: `norm(s) = re.sub(r"\s+", " ", s).strip()` (the rule of `analyze_natural.py`), then lower case (the rule of `grounding_check.py`), before any test.
* **Best-unit fraction** (descriptive): the largest answer-term fraction among the units that contain every anchor, 0 when none does.

**Unit** of a rendering or view = one rendered line (the renderings are line-oriented; `run_holdout._matching_line_numbers` works per line); a rendering passes iff **at least one line** passes. The unit of a quoted span = **the whole span** (the evidence unit the rater declared sufficient). Sensitivity (reported, not used for the reading): a span passes iff at least one of its lines passes.

## 31.5 The texts tested, and the primary measure

For cell `i`, model `m`, human `h`:

* `T_full(i)`: the full rendering of the cell's variant (`full_path`: what both humans saw), rendering-level test.
* `T_view(i)`: the view the model saw (`view_path`: the question-relevant subgraph for 182 cells, the full rendering for the others), rendering-level test.
* `T_span(i)`: for `h` = R2 and `S_R2 = 1`: the second rater's quoted span, span-level test. Undefined otherwise.
* `T_llm(i)`: for `L_i = 1`: the model's **modal quoted span**: among the slots with `S_final = 1`, the most frequent whitespace-normalised span (ties: the first in slot order `domain/ontology/auditor/kgqa/generalist` x seed 1..5), span-level test. Undefined for `L_i = 0`.
* **Primary human-side measure `T_H`** = `T_span` if it is defined, else `T_full`. This is the brief's rule: the span the human quoted if the human labels carry one, the full rendering otherwise (all cells of AH; the label-0 cells of R2).

**Per-cell verdict on a disagreement cell** (the credit-giver is the side that credits support, because only a credit can be checked for term support by a span):

* D10: the human credits. **credit confirmed** iff `T_H(i)` (R2: the human's span; AH: the full rendering). Confirmed -> the human is right on `i`; not confirmed -> the model is right.
* D01: the model credits. **credit confirmed** iff `T_llm(i)`. Confirmed -> the model is right on `i`; not confirmed -> the human is right.
* `human_right(i)` is 1 or 0 accordingly; `model_right(i) = 1 - human_right(i)`. A confirmed credit means the credit-giver's text carries the answer terms; a credit that is not confirmed means the credited text does not.

## 31.6 What is reported (aggregates only, per model x human)

1. `n` consistent cells; `n_Ag`, `n_Ag11`, `n_Ag00`; `n_D`, `n_D10`, `n_D01`.
2. For each group in {D, D10, D01, Ag, Ag11, Ag00}: the share with `T_H`, and the shares with `T_full`, `T_view`, `T_span` (where defined), `T_llm` (where defined), the mean best-unit fraction in `T_H`'s text; question-cluster BCa 95% intervals (B = 10,000, seed 20260913, the analyzer's draws, `analyze.bca`; where the BCa is undefined the percentile interval is given and marked).
3. **The headline pair**: the share with `T_H` on **D** and on **Ag**, and their paired difference (cluster BCa).
4. The per-cell verdict counts on D (`human_right`, `model_right`), the share `human_right` with a cluster BCa interval, and by direction.
5. Sensitivities: the single-line span variant of 31.4; the share of D10 cells where `T_full` holds but `T_view` does not (the model's view lacked a unit that the human's rendering has) and the share where neither holds.
6. **Reliability side by side** (all label-free of the adjudication; Tier 1, `S_final`): (a) human-human kappa on the 188 cells and on each model's evaluated cells (from `results.json`) and on each model's consistent cells; (b) LLM-LLM kappa between the consistent labels of the three models (cells where both are R25-consistent) and between the unfiltered majorities of 25 (cells where both are evaluated), with cluster BCa, computed from the raw files; (c) test-retest Krippendorff alpha across seeds (per persona, and across all 25 slots) per model, from `results.json`, and the number of consistent cells and the share of label 1 among them (the near-constant-label signature).

## 31.7 Procedure and order

`adjudicate.py` imports the functions named above without editing them, runs a self-test on synthetic data first (the term test on hand-made units, the group split, the verdict rule, the BCa helper against a brute-force bootstrap; no human label, no model output), then the real run, and writes `results_adjudication.json`. The script, its self-test and a hash of this file are committed before the real run is first executed; any change after that is recorded in `DEVIATIONS.md` with the reason. Nothing in 31.3-31.5 is changed after the first real run.

## 31.8 Reading rule (fixed now)

For each (model, human) pair with `n_D >= 10` (fewer: "not evaluable", counts only), let `p = share(human_right)` on D with its cluster-BCa interval.

* **The objective term evidence lies on the human side** iff the lower bound of `p` is above 0.5.
* **on the model side** iff the upper bound of `p` is below 0.5.
* **not separated** otherwise.

The paper may say, in the post hoc check on language-model raters, at most the sentence that the counts support: "on the cells where a consistent LLM label disagrees with a human, the objective term evidence lies on the human side / on the model side / is not separated, in k of 6 comparisons". The headline-pair comparison (31.6 item 3) and the baselines are reported next to it. Whatever the result, the reading is bounded by 31.1: the human labels stay the reference, the check is a term test, and the claim concerns the consistent subset only.

## 31.9 Outputs and reproduction

`adjudicate.py`, `results_adjudication.json` (aggregates only), this file, `DEVIATIONS.md` entries if any. Reproduce: `python3 harness/review10_llm_labels/adjudicate.py` (self-test first). Requires the two de-identified analysis files and the span file of 31.2.

## 31.10 What the addendum does not claim

It does not claim that a term test decides support, that the consistency filter selects correct labels, that either label source is ground truth, or that the labeler can replace human raters. It does not use a model, a server or a new label. It reports on which side of a disagreement the bank-based term evidence lies, with the baseline of the same test on the cells where the two agree, and the reliability numbers of addendum 30 next to it.

## 31.11 Results (written after the first real run; sections 31.1-31.10 above are the frozen text of commit 88e5cbc and are unchanged)

Run: `python3 harness/review10_llm_labels/adjudicate.py` at commit 0e06f6b (self-test 30 of 30 checks, then the analysis; no deviation from 31.3-31.8). `results_adjudication.json` carries the aggregates; its `meta.sha256.plan` equals the digest of the frozen plan (`ec479735...c06a`). Counts below are cells; intervals are cluster-BCa 95% (percentile where the BCa is undefined, marked in the JSON).

**Disagreement cells are almost all one direction.** The consistent labels are almost constant "unsupported" (share of label 1 among them: GLM-4.7-Flash 2.6%, gpt-oss-20b 2.0%, Qwen3.8-Flash-Next 18.7%), so D is D10 (the human credits support, the model does not) in 320 of the 322 disagreement cells summed over the six pairs (D01 = 0 except 2 cells of Qwen against R2). The "model credits, human does not" direction cannot be tested on this data.

| model | human | consistent cells | D10 + D01 | `T_H` on D | `T_H` on Ag11 (both credit) | `T_H` on Ag00 (both give none) | `T_view` on D | `human_right` on D | reading (31.8) |
|---|---|---:|---:|---|---|---|---|---|---|
| GLM-4.7-Flash | AH | 38 | 24 + 0 | 7/24 (29%; 10-64) | 1/1 | 0/13 (0%) | 1/24 (4%; 0-16) | 7/24 (29%; 10-64) | not separated |
| GLM-4.7-Flash | R2 | 38 | 22 + 0 | 7/22 (32%; 9-71) | 1/1 | 3/15 (20%; 0-75) | 1/22 (5%; 0-17) | 7/22 (32%; 9-71) | not separated |
| gpt-oss-20b | AH | 101 | 61 + 0 | 23/61 (38%; 15-66) | 1/2 | 0/38 (0%) | 0/61 (0%) | 23/61 (38%; 15-66) | not separated |
| gpt-oss-20b | R2 | 101 | 65 + 0 | 35/65 (54%; 27-79) | 1/2 | 0/34 (0%) | 0/65 (0%) | 35/65 (54%; 27-79) | not separated |
| Qwen3.8-Flash-Next | AH | 139 | 80 + 0 | 37/80 (46%; 23-70) | 16/26 (62%; 30-88) | 0/33 (0%) | 1/80 (1%; 0-8) | 37/80 (46%; 23-70) | not separated |
| Qwen3.8-Flash-Next | R2 | 139 | 68 + 2 | 35/70 (50%; 24-74) | 13/24 (54%; 21-91) | 10/45 (22%; 0-62) | 1/70 (1%; 0-8) | 37/70 (53%; 27-77) | not separated |

(`T_H` = the term test on the second rater's quoted span for R2 label-1 cells, on the full rendering otherwise; AH has no span in a non-restricted file. `T_view` = the term test on the view the model saw.)

**Reading (31.8): not separated in 6 of 6 comparisons** (0 human side, 0 model side, 0 not evaluable). The objective term evidence neither confirms the humans' credits nor the models' "unsupported" labels as the right side of the disagreement.

What the groups show, descriptively:

* The credits that the humans gave where a consistent model label disagreed passed the term test in 29-54% of the cells. In the both-credit cells that pass rate is 54-62% where there are enough cells (Qwen; GLM and gpt-oss have 1-2 such cells), and in the cells where human and model both give no support it is 0-22%. The human credits in the disagreement cells therefore carry term evidence much more often than the both-unsupported cells do, and somewhat less often than the both-credit cells.
* The view the model saw passed the term test in 0-5% of the disagreement cells (all 188 cells: 11% of views against 32% of full renderings). Of the D10 cells, 14-45% have a passing unit in the full rendering that the human saw and none in the model's view; 54-82% have none in either.
* **The pre-specified headline pair** (share of `T_H` on Ag minus on D, 31.6 item 3) is negative or not separated from zero (R2: GLM -0.07, gpt-oss -0.51, Qwen -0.17; AH: -0.22, -0.35, -0.19), because Ag is mostly Ag00, where `T_H` is 0-22% by construction of "no unit supports". It is reported as pre-specified; the group-level baselines above (Ag11, Ag00) are the readable comparison.
* Sensitivity, single-line span variant: the share of `human_right` on D for R2 is 3/22 (14%) for GLM, 21/65 (32%) for gpt-oss and 29/70 (41%) for Qwen; the intervals are 0.03-0.41, 0.12-0.62 and 0.19-0.68: in the variant the reading would stay "not separated" for gpt-oss and Qwen and would be "model side" for GLM against R2 (reported as a sensitivity only, not as the reading).

**Reliability side by side (Tier 1; all from `results.json` or the raw files, in `results_adjudication.json` `reliability`).** Human-human kappa 0.595 on the 188 cells, 0.77 / 0.70 / 0.62 on the consistent cells of GLM / gpt-oss / Qwen. LLM-human kappa of the consistent labels at most 0.16. LLM-LLM kappa between consistent labels: GLM-gpt-oss 0.00 (agreement 0.96; both near-constant), GLM-Qwen 0.48 [0.00, 1.00], gpt-oss-Qwen 0.56 [0.00, 1.00]; between the unfiltered majorities of 25: 0.32 [0.11, 0.53], 0.12 [-0.06, 0.34], 0.23 [0.02, 0.45]. Test-retest alpha across all 25 slots: GLM 0.20, gpt-oss 0.38, Qwen 0.75; per persona across the five seeds 0.11-0.17, 0.37-0.44, 0.74-0.81.

**What the sentence may say** (31.8, bounded by 31.1): on the cells where a consistent LLM label disagrees with a human, nearly all of which are the model's "unsupported" against the human's "supported", the bank-based term evidence did not separate the two sides in any of the 6 comparisons. The human labels stay the reference because they are the most reliable label source measured (human-human kappa 0.59-0.77 against LLM-LLM kappa of at most 0.32 between unfiltered majorities and test-retest alpha of 0.20-0.75), and not because the check shows them to be correct.
