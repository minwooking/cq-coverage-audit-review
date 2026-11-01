# REPORT -- addendum 26 (exploratory): non-Qwen judges on views that fit their context

> AI-generated draft; the author must review it before use. Exploratory and post hoc; descriptive only (PLAN.md 26.1). Intervals are question-clustered BCa 95% (B = 10,000, seed 20260913) unless a table says otherwise. Do not copy this into external material without checking it for internal addresses and unpublished data.

## 0. What was run and what it shows (descriptive; all numbers are in the tables below)

**Run.** Two non-Qwen judges, gpt-oss-20b and GLM-4.7-Flash (vLLM servers on the shared server, used by request only, at most 3 concurrent requests each; no container was touched). 305 cells x 3 repeats = 915 calls per judge, 1,830 in total, on 2026-10-17 from 08:57Z to 10:08Z (gpt-oss 2,695 s, GLM 4,192 s, the two judges ran concurrently). Cells: 182 holdout subgraph primary cells, 27 subgraph controls (15 ablated, 12 preserved), and 96 development cells on the original development rendering. Every prompt fit the 65,536-token window; no cell was skipped for context and no development subgraph analogue was needed. Frozen PLAN.md = commit `87355a0`; prompts, decoding, views and cells were not changed after it (pins below). Totals (server `usage`): gpt-oss 11.88M prompt and 0.21M completion tokens (about 13.0M prompt tokens counting retried requests), GLM 12.12M and 0.31M (about 15.3M with retries).

**Validity.** Holdout: 0 invalid calls for both judges. Development: 8 of 288 calls invalid for gpt-oss (all development; 5 cells have a missing repeat, 1 cell has none valid) and 46 of 288 for GLM (26 cells have a missing repeat, 5 have none valid). Every invalid reply ended at the token limit after the three attempts of the frozen retry rule: GLM's `evidence` list runs on until the JSON is cut off (the reply starts with a valid `{"score": N,`), and gpt-oss's reasoning uses the whole 4,096 tokens in some replies. The failures are not deterministic across repeats (retries recovered 46 of GLM's 92 retried cells), so a cell can have one to three valid repeats; a cell's score is the mean of its valid repeats. Section 8 repeats the headline numbers with the score read from the truncated reply; it changes none of the readings below.

**Development A->B (16 questions).** Same bank, rendering and prompt, judge changed. gpt-oss-20b +1.188 [+0.021, +2.000]; GLM-4.7-Flash +0.467 [+0.178, +0.956] on 15 pairs (+0.479 [+0.208, +0.917] with the salvage sensitivity). For comparison the same code gives Qwen (the extractor family) +1.000 [+0.500, +1.625] and the stored Gemini-3-flash-lite re-score +1.625 [+1.062, +2.188]. The direction survives with both new judges and both intervals exclude zero (gpt-oss only just: lower end +0.021). The size does not carry over: GLM's estimate is about half of Qwen's and the gpt-oss interval spans almost the whole range. Under the paper's convention (half-up mean of repeats 1 and 2) GLM gives +0.333 [0.000, +1.000], because rounding turns small differences into 0 or 1. Coverage A->B (share J >= 2): gpt-oss 0.29 -> 0.71, GLM 0.60 -> 0.89. Among questions where both a new judge and Qwen moved A->B, the direction always agreed (7/7, 6/6).

**Holdout A->B on the subgraph view (22 paired questions).** gpt-oss +0.409 [-0.242, +1.045]; GLM +0.545 [-0.076, +1.182]. On the same 22 pairs the registered holdout judge (full view) gives +0.455 [0.000, +1.000] (its own 23 pairs: +0.565 [+0.043, +1.130]) and luna on the subgraph +0.091 [-0.500, +0.682]. Both new intervals include zero. The point estimates are positive and close to the registered judge's, and higher than luna's; with these intervals nothing separates the four.

**Variant means.** The pipeline variants B-F are within about 0.3 J of each other for every judge except gpt-oss on development (0.50, B 2.15 against E 2.65), and the order among them differs by judge (Section 2). A is lowest on the development rendering for both new judges (mean J 0.96 and 1.40 against 1.82-2.65 for B-F). On the holdout subgraph A is not clearly lower (1.62 and 1.56 against 1.59-1.84), and luna ranks A highest (2.23).

**Judge scale.** The new judges are stricter than the references. Offset (judge minus reference), holdout subgraph: against luna -0.210 [-0.533, +0.111] (gpt-oss) and -0.255 [-0.493, -0.053] (GLM); against the registered judge's full-view J -0.293 and -0.350 (both intervals include zero). Development, against Qwen: -0.396 [-0.714, -0.184] and -0.819 [-0.935, -0.621]. Exact agreement with luna is 0.45 (gpt-oss) and 0.36 (GLM), QWK 0.36 and 0.55; the two new judges agree with each other on 0.46 of holdout cells (QWK 0.52) and 0.09 of development cells (QWK 0.32). The score scales are also shaped differently: gpt-oss almost never gives 2 on the holdout (2 of 546 calls) and GLM never gives 3 on the development rendering (0 of 242), so coverage (J >= 2) is not comparable across judges and contrasts should be read within a judge.

**Run-to-run (temperature 0, so serving nondeterminism: batching and floating point on shared servers).** Pairwise exact agreement over the three repeats: gpt-oss 0.846 [0.788, 0.898] on the holdout (41 of 182 cells changed score at least once) and 0.897 [0.824, 0.953] on development; GLM 0.769 [0.700, 0.832] (61 of 182 cells) and 0.943 [0.879, 0.981] on development (70 cells with three valid repeats). ICC(2,1): gpt-oss 0.816 and 0.918, GLM 0.857 and 0.886 (intervals in Section 3). The development Qwen judge's two samples agreed on 0.969 of items in the paper, so these judges are less repeatable than that reference. The single-repeat A->B moves by up to 0.36 between repeats (gpt-oss development +1.125 to +1.250, GLM development +0.273 to +0.600, holdout +0.273 to +0.636).

**Contrast direction.** Over the six contrasts the sign of the mean difference matches the references on 1 to 4 of 6 (Section 5), which is what small contrasts near zero allow; it is not a test. The A->B sign matches every reference in both studies (8 of 8 comparisons, all positive).

**Unsupported credit against the independent rater's S labels (182 cells).** pi-hat: gpt-oss 0.123 (repeats 0.121-0.126), GLM 0.168 (0.159-0.176), with per-repeat intervals of about [0.05, 0.24] and [0.08, 0.30]; the registered judge (full view) 0.143 (26/182) [0.061, 0.273] and luna 0.179 (32/179) [0.085, 0.328] on the same cells. The four rates and their intervals overlap. **Controls (subgraph analogue, descriptive):** J >= 2 on 8.9% of ablated controls for gpt-oss and 46.7% for GLM (15 cells x 3 repeats); on 52.8% and 61.1% of the preserved controls (12 x 3). A judge that still credits half of the ablated controls with their grounding lines removed would show the over-credit that the audit looks for, but the ablation removes only the grounding lines and the subgraph may carry other support.

## 0.1 Deviations after the freeze (not in PLAN.md)

1. Section 8 (salvage sensitivity) and the per-study invalid summary in `results.json` were added after the runs; the scorer, prompts, decoding, views, cells and the primary analysis are as frozen. Section 8 uses a rule fixed before it was run: a truncated reply that starts with `{"score": N,` yields N.
2. PLAN 26.6-1 asks for reference A->B "on the same questions and on their own full sets"; the report shows both (reference rows marked "judges' 182 cells only" are the same-question versions).
3. The pinned files (`jobs.jsonl`, `jobs_build_skips.json`, `build_jobs.py`, `score_judges.py`; the copies on the host too) were verified unchanged by sha256 after the runs; `PLAN.md` is unchanged since commit `87355a0`. No call was repeated or re-run; no cell was context-skipped.
4. The reference development A->B interval is recomputed here with the plan's BCa rule: Qwen +1.000 [+0.500, +1.625], against [+0.500, +1.563] in the paper (a percentile bootstrap with seed 0); the point estimate is identical.
5. The brief named the 188 primary cells and 36 controls "used in the luna subgraph run"; that run had no controls. The 27 subgraph controls here are a new construction (PLAN 26.3).

## 0.2 What was not done and cautions

* **No third judge.** The shared-server GPUs have no free memory (94.8 of 95.8 GiB used on both) and the shared server still fails `nvidia-smi` (driver/library mismatch), so no Gemma or DeepSeek server was launched; judge-family statements rest on two families.
* **No AH labels.** pi-hat uses the independent rater's labels. The per-cell AH file is in the locked label directory and was not opened. To run the same estimator on AH: `python3 harness/review6_judges/analyze_review6.py --ah-labels <csv with columns cell_id,A>` (about 35 s).
* The labels were assigned on the full rendering, the judges here saw the subgraph; the evidence the rater found may lie outside it.
* Cell scores are means of valid repeats; the interval widths reflect 15-22 paired questions and are descriptive, with no multiplicity correction.
* The servers are shared and the two judge runs overlapped in time; latency figures are not a clean speed measure.
* Retry at 4,096 tokens costs about 10% more prompt tokens for gpt-oss and about 26% more for GLM (all-attempts estimate against final-attempt counts); a prompt that asks for a short `evidence` field would avoid most of GLM's invalid replies but is a prompt change and needs a new addendum.
* AI-generated analysis and code: review and test before relying on any number. Before any of this goes into external material, check it for internal addresses, host names and unpublished data (none are recorded in these files).

## 1. A->B and the six contrasts

### Development study (16 questions, development rendering)

| source | contrast | mean delta | 95% BCa | pairs |
|---|---|---|---|---|
| gpt-oss-20b | A->B | +1.188 | [+0.021, +2.000] | 16 |
| gpt-oss-20b | B->C | +0.411 | [-0.211, +1.267] | 15 |
| gpt-oss-20b | C->D | -0.056 | [-0.813, +0.222] | 15 |
| gpt-oss-20b | D->E | +0.167 | [-0.104, +0.875] | 16 |
| gpt-oss-20b | E->F | -0.135 | [-0.438, -0.021] | 16 |
| gpt-oss-20b | D->F | +0.031 | [-0.375, +0.646] | 16 |
| GLM-4.7-Flash | A->B | +0.467 | [+0.178, +0.956] | 15 |
| GLM-4.7-Flash | B->C | -0.044 | [-0.133, +0.000] | 15 |
| GLM-4.7-Flash | C->D | +0.167 | [+0.024, +0.445] | 14 |
| GLM-4.7-Flash | D->E | -0.056 | [-0.178, +0.000] | 15 |
| GLM-4.7-Flash | E->F | -0.078 | [-0.333, +0.000] | 15 |
| GLM-4.7-Flash | D->F | -0.133 | [-0.356, -0.022] | 15 |
| ref: qwen_dev_judge | A->B | +1.000 | [+0.500, +1.625] | 16 |
| ref: qwen_dev_judge | B->C | +0.000 | [-0.188, +0.188] | 16 |
| ref: qwen_dev_judge | C->D | +0.062 | [-0.125, +0.312] | 16 |
| ref: qwen_dev_judge | D->E | -0.062 | [-0.312, +0.000] | 16 |
| ref: qwen_dev_judge | E->F | +0.062 | [+0.000, +0.312] | 16 |
| ref: qwen_dev_judge | D->F | +0.000 | [-0.188, +0.188] | 16 |
| ref: gemini3_flash_lite_dev | A->B | +1.625 | [+1.062, +2.188] | 16 |
| ref: gemini3_flash_lite_dev | B->C | -0.125 | [-0.375, +0.000] | 16 |
| ref: gemini3_flash_lite_dev | C->D | -0.062 | [-0.312, +0.125] | 16 |
| ref: gemini3_flash_lite_dev | D->E | -0.062 | [-0.312, +0.000] | 16 |
| ref: gemini3_flash_lite_dev | E->F | +0.000 | [-0.250, +0.250] | 16 |
| ref: gemini3_flash_lite_dev | D->F | -0.062 | [-0.312, +0.125] | 16 |

A->B per single repeat, gpt-oss-20b: r1 +1.250 [+0.062, +2.062]; r2 +1.188 [+0.062, +2.000]; r3 +1.125 [+0.000, +1.938]
A->B, paper convention (half-up mean of repeats 1 and 2), gpt-oss-20b: +1.188 [+0.062, +2.000]
A->B per single repeat, GLM-4.7-Flash: r1 +0.273 [+0.000, +0.909]; r2 +0.600 [+0.200, +1.200]; r3 +0.500 [+0.214, +1.000]
A->B, paper convention (half-up mean of repeats 1 and 2), GLM-4.7-Flash: +0.333 [+0.000, +1.000]

### Brick holdout, subgraph view (22 paired questions)

| source | contrast | mean delta | 95% BCa | pairs |
|---|---|---|---|---|
| gpt-oss-20b | A->B | +0.409 | [-0.242, +1.045] | 22 |
| gpt-oss-20b | B->C | -0.156 | [-0.458, +0.219] | 32 |
| gpt-oss-20b | C->D | +0.135 | [-0.250, +0.510] | 32 |
| gpt-oss-20b | D->E | -0.198 | [-0.604, +0.188] | 32 |
| gpt-oss-20b | E->F | +0.083 | [-0.083, +0.344] | 32 |
| gpt-oss-20b | D->F | -0.115 | [-0.583, +0.323] | 32 |
| GLM-4.7-Flash | A->B | +0.545 | [-0.076, +1.182] | 22 |
| GLM-4.7-Flash | B->C | -0.000 | [-0.208, +0.219] | 32 |
| GLM-4.7-Flash | C->D | +0.031 | [-0.062, +0.167] | 32 |
| GLM-4.7-Flash | D->E | -0.156 | [-0.344, +0.031] | 32 |
| GLM-4.7-Flash | E->F | +0.031 | [-0.083, +0.177] | 32 |
| GLM-4.7-Flash | D->F | -0.125 | [-0.323, +0.052] | 32 |
| ref: registered_gemini_J_full_view | A->B | +0.565 | [+0.043, +1.130] | 23 |
| ref: registered_gemini_J_full_view | B->C | +0.000 | [-0.273, +0.333] | 33 |
| ref: registered_gemini_J_full_view | C->D | -0.273 | [-0.606, -0.061] | 33 |
| ref: registered_gemini_J_full_view | D->E | +0.212 | [-0.091, +0.545] | 33 |
| ref: registered_gemini_J_full_view | E->F | +0.061 | [-0.152, +0.364] | 33 |
| ref: registered_gemini_J_full_view | D->F | +0.273 | [+0.030, +0.606] | 33 |
| ref (judges' 182 cells only): registered_gemini_J_full_view | A->B | +0.455 | [+0.000, +1.000] | 22 |
| ref (judges' 182 cells only): registered_gemini_J_full_view | B->C | +0.000 | [-0.281, +0.344] | 32 |
| ref (judges' 182 cells only): registered_gemini_J_full_view | C->D | -0.281 | [-0.625, -0.062] | 32 |
| ref (judges' 182 cells only): registered_gemini_J_full_view | D->E | +0.188 | [-0.125, +0.531] | 32 |
| ref (judges' 182 cells only): registered_gemini_J_full_view | E->F | +0.062 | [-0.156, +0.406] | 32 |
| ref (judges' 182 cells only): registered_gemini_J_full_view | D->F | +0.250 | [+0.031, +0.594] | 32 |
| ref: luna_subgraph | A->B | +0.091 | [-0.500, +0.682] | 22 |
| ref: luna_subgraph | B->C | -0.194 | [-0.452, +0.000] | 31 |
| ref: luna_subgraph | C->D | +0.032 | [-0.129, +0.258] | 31 |
| ref: luna_subgraph | D->E | +0.031 | [-0.281, +0.344] | 32 |
| ref: luna_subgraph | E->F | -0.200 | [-0.433, -0.033] | 30 |
| ref: luna_subgraph | D->F | -0.167 | [-0.467, +0.133] | 30 |
| ref (judges' 179 cells only): luna_subgraph | A->B | +0.091 | [-0.500, +0.682] | 22 |
| ref (judges' 179 cells only): luna_subgraph | B->C | -0.194 | [-0.452, +0.000] | 31 |
| ref (judges' 179 cells only): luna_subgraph | C->D | +0.032 | [-0.129, +0.258] | 31 |
| ref (judges' 179 cells only): luna_subgraph | D->E | +0.031 | [-0.281, +0.344] | 32 |
| ref (judges' 179 cells only): luna_subgraph | E->F | -0.200 | [-0.433, -0.033] | 30 |
| ref (judges' 179 cells only): luna_subgraph | D->F | -0.167 | [-0.467, +0.133] | 30 |

A->B per single repeat, gpt-oss-20b: r1 +0.500 [-0.318, +1.273]; r2 +0.455 [-0.273, +1.227]; r3 +0.273 [-0.409, +0.955]
A->B per single repeat, GLM-4.7-Flash: r1 +0.636 [-0.045, +1.273]; r2 +0.364 [-0.364, +1.045]; r3 +0.636 [-0.045, +1.318]

## 2. Per-variant means (J) and coverage (share J >= 2)

### dev

| source | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| gpt-oss-20b mean J | 0.96 | 2.15 | 2.50 | 2.48 | 2.65 | 2.51 |
| gpt-oss-20b coverage | 0.292 | 0.708 | 0.811 | 0.823 | 0.854 | 0.833 |
| GLM-4.7-Flash mean J | 1.40 | 1.89 | 1.84 | 1.96 | 1.90 | 1.82 |
| GLM-4.7-Flash coverage | 0.604 | 0.889 | 0.844 | 0.956 | 0.900 | 0.822 |
| ref qwen_dev_judge mean J | 1.75 | 2.75 | 2.75 | 2.81 | 2.75 | 2.81 |
| ref qwen_dev_judge coverage | 0.562 | 0.938 | 1.000 | 1.000 | 1.000 | 1.000 |
| ref gemini3_flash_lite_dev mean J | 1.31 | 2.94 | 2.81 | 2.75 | 2.69 | 2.69 |
| ref gemini3_flash_lite_dev coverage | 0.438 | 1.000 | 1.000 | 1.000 | 0.938 | 1.000 |

### holdout_subgraph

| source | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| gpt-oss-20b mean J | 1.62 | 1.84 | 1.69 | 1.82 | 1.62 | 1.71 |
| gpt-oss-20b coverage | 0.530 | 0.573 | 0.521 | 0.573 | 0.490 | 0.521 |
| GLM-4.7-Flash mean J | 1.56 | 1.72 | 1.72 | 1.75 | 1.59 | 1.62 |
| GLM-4.7-Flash coverage | 0.530 | 0.677 | 0.688 | 0.708 | 0.604 | 0.615 |
| ref registered_gemini_J_full_view mean J | 1.74 | 2.06 | 2.06 | 1.79 | 2.00 | 2.06 |
| ref registered_gemini_J_full_view coverage | 0.565 | 0.788 | 0.758 | 0.667 | 0.667 | 0.727 |
| ref luna_subgraph mean J | 2.23 | 2.03 | 1.87 | 1.88 | 1.91 | 1.77 |
| ref luna_subgraph coverage | 0.682 | 0.594 | 0.516 | 0.469 | 0.531 | 0.500 |

## 3. Run-to-run (3 repeats, temperature 0: serving nondeterminism, not sampling variance)

| judge | study | cells | pairwise exact agr. | 95% | all 3 identical | cells with any disagreement | ICC(2,1) | 95% | ICC(2,3) |
|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-20b | holdout_subgraph | 182 | 0.846 | [0.788, 0.898] | 0.775 | 41 | 0.816 | [0.732, 0.881] | 0.930 |
| gpt-oss-20b | dev | 91 | 0.897 | [0.824, 0.953] | 0.846 | 14 | 0.918 | [0.824, 0.974] | 0.971 |
| GLM-4.7-Flash | holdout_subgraph | 182 | 0.769 | [0.700, 0.832] | 0.665 | 61 | 0.857 | [0.795, 0.904] | 0.947 |
| GLM-4.7-Flash | dev | 70 | 0.943 | [0.879, 0.981] | 0.914 | 6 | 0.886 | [0.684, 0.970] | 0.959 |

Exact agreement is BCa; ICC intervals are percentile question-clustered bootstrap.

## 4. Offsets and agreement against luna (subgraph) and the registered holdout judge / dev Qwen judge

| judge | study | reference | shared cells | offset (judge - ref) | 95% BCa | exact (mean of repeats) | within 1 | QWK |
|---|---|---|---|---|---|---|---|---|
| gpt-oss-20b | holdout_subgraph | registered_gemini_J_full_view | 182 | -0.293 | [-0.711, +0.087] | 0.430 | 0.652 | 0.227 |
| gpt-oss-20b | holdout_subgraph | luna_subgraph | 179 | -0.210 | [-0.533, +0.111] | 0.453 | 0.715 | 0.355 |
| gpt-oss-20b | dev | qwen_dev_judge | 95 | -0.396 | [-0.714, -0.184] | 0.654 | 0.839 | 0.432 |
| gpt-oss-20b | dev | gemini3_flash_lite_dev | 95 | -0.323 | [-0.635, -0.115] | 0.693 | 0.854 | 0.534 |
| GLM-4.7-Flash | holdout_subgraph | registered_gemini_J_full_view | 182 | -0.350 | [-0.760, +0.009] | 0.390 | 0.674 | 0.244 |
| GLM-4.7-Flash | holdout_subgraph | luna_subgraph | 179 | -0.255 | [-0.493, -0.053] | 0.358 | 0.905 | 0.550 |
| GLM-4.7-Flash | dev | qwen_dev_judge | 91 | -0.819 | [-0.935, -0.621] | 0.165 | 0.942 | 0.323 |
| GLM-4.7-Flash | dev | gemini3_flash_lite_dev | 91 | -0.731 | [-0.850, -0.549] | 0.206 | 0.955 | 0.382 |

Inter-judge (gpt-oss vs GLM), holdout_subgraph: exact 0.463, QWK 0.517 (mean over repeats).

Inter-judge (gpt-oss vs GLM), dev: exact 0.089, QWK 0.321 (mean over repeats).

Reference rows on the holdout compare different inputs for the registered judge (full view) and the same input for luna (subgraph).

## 5. Contrast-direction agreement (sign of mean delta, six contrasts, shared cells)

| judge | study | reference | contrasts with same sign | per-question A->B same sign | both nonzero & same direction / both nonzero |
|---|---|---|---|---|---|
| gpt-oss-20b | holdout_subgraph | registered_gemini_J_full_view | 2/6 | 8/22 | 5/9 |
| gpt-oss-20b | holdout_subgraph | luna_subgraph | 4/6 | 11/22 | 6/8 |
| gpt-oss-20b | dev | qwen_dev_judge | 1/6 | 9/16 | 7/7 |
| gpt-oss-20b | dev | gemini3_flash_lite_dev | 2/6 | 12/16 | 10/10 |
| GLM-4.7-Flash | holdout_subgraph | registered_gemini_J_full_view | 3/6 | 10/22 | 7/11 |
| GLM-4.7-Flash | holdout_subgraph | luna_subgraph | 3/6 | 10/22 | 5/10 |
| GLM-4.7-Flash | dev | qwen_dev_judge | 4/6 | 13/15 | 6/6 |
| GLM-4.7-Flash | dev | gemini3_flash_lite_dev | 4/6 | 10/15 | 6/6 |

## 6. Unsupported-credit rate pi-hat (J >= 2 and S = 0) on the 182 subgraph cells

S labels: the independent rater (v3); AH labels are not read (see PLAN 26.6-6) unless the author supplied a path.

| label set | source | pi-hat (repeat mean; min-max) | per-repeat pi-hat [95% BCa] |
|---|---|---|---|
| independent rater (v3) | ref registered_gemini_J_full_view | 0.143 (events 26/182) | 0.143 [0.061, 0.273] |
| independent rater (v3) | ref luna_subgraph | 0.179 (events 32/179) | 0.179 [0.085, 0.328] |
| independent rater (v3) | gpt-oss-20b | 0.123 (0.121-0.126) | r1 0.121 [0.060, 0.221]; r2 0.126 [0.061, 0.231]; r3 0.121 [0.051, 0.236] |
| independent rater (v3) | GLM-4.7-Flash | 0.168 (0.159-0.176) | r1 0.170 [0.084, 0.294]; r2 0.159 [0.078, 0.283]; r3 0.176 [0.088, 0.303] |

### Controls (subgraph analogue; share of cells with J >= 2)

| judge | ablated (15 planned) | preserved (12 planned) |
|---|---|---|
| gpt-oss-20b | 0.089 (n per repeat [15, 15, 15]) | 0.528 (n per repeat [12, 12, 12]) |
| GLM-4.7-Flash | 0.467 (n per repeat [15, 15, 15]) | 0.611 (n per repeat [12, 12, 12]) |

## 7. Score distributions, validity and cost

| judge | study | J=0 | J=1 | J=2 | J=3 | calls | valid | invalid | cells needing retry | prompt tokens (final attempt) | completion tokens | wall span (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-20b | holdout_subgraph | 187 | 67 | 2 | 290 | 546 | 546 | 0 | 10 | 5,609,733 | 72,971 | 2665.3 |
| gpt-oss-20b | holdout_control |  |  |  |  | 81 | 81 | 0 | 3 | 746,157 | 11,328 | 2650.4 |
| gpt-oss-20b | dev | 55 | 22 | 11 | 192 | 288 | 280 | 8 | 29 | 5,524,218 | 125,868 | 2694.7 |
| gpt-oss-20b | all |  |  |  |  | 915 | 907 | 8 | 42 | 11,880,108 | 210,167 | 2694.7 |
| GLM-4.7-Flash | holdout_subgraph | 149 | 46 | 189 | 162 | 546 | 546 | 0 | 2 | 5,599,254 | 41,822 | 4122.5 |
| GLM-4.7-Flash | holdout_control |  |  |  |  | 81 | 81 | 0 | 0 | 745,305 | 5,239 | 4108.3 |
| GLM-4.7-Flash | dev | 10 | 27 | 205 | 0 | 288 | 242 | 46 | 90 | 5,773,488 | 259,108 | 4192.5 |
| GLM-4.7-Flash | all |  |  |  |  | 915 | 869 | 46 | 92 | 12,118,047 | 306,169 | 4192.5 |

Cells without a valid score are listed per judge in `results.json` (`invalid_or_missing`); nothing was imputed.

## 8. Sensitivity added after the freeze (not in PLAN.md): scores salvaged from truncated JSON

A reply that is cut off at the token limit but starts with `{"score": N,` has its score read from that prefix; replies with no content (reasoning used the whole budget) stay invalid. The primary analysis above does not use these scores.

| judge | study | salvaged (cell, repeat) scores | A->B primary | A->B with salvage | pairwise exact agr. primary | with salvage |
|---|---|---|---|---|---|---|
| gpt-oss-20b | holdout_subgraph | 0 | +0.409 [-0.242, +1.045] | +0.409 [-0.242, +1.045] | 0.846 | 0.846 |
| gpt-oss-20b | dev | 2 | +1.188 [+0.021, +2.000] | +1.188 [+0.021, +2.000] | 0.897 | 0.891 |
| GLM-4.7-Flash | holdout_subgraph | 0 | +0.545 [-0.076, +1.182] | +0.545 [-0.076, +1.182] | 0.769 | 0.769 |
| GLM-4.7-Flash | dev | 46 | +0.467 [+0.178, +0.956] | +0.479 [+0.208, +0.917] | 0.943 | 0.910 |

