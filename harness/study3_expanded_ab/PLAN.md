# PREREG addendum 34 -- expanded A->B judge-score contrast on the Study 2 expansion bank (post hoc)

> **Judge-score contrast on the expansion bank; not human-labelled; post hoc.** AI-generated draft; the author must review it before it is relied on. Date: 2026-10-20. This file is committed alone, before any computation or model call of this addendum. `main.tex`, `main_ko.tex` and `supplement.tex` are not edited by this addendum. All code named here is AI-generated and must be reviewed and tested by a person before reuse; none of it is to be applied to a production system without that review. Before this file or any output is shared outside the team, check that no confidential company information, host name, address, port, key or personal data is in it.

## 34.1 Purpose and status

The holdout A->B contrast (baseline A vs structured base build B) is unresolved at 23 questions (33 eligible clusters in the L1* analysis; MDE 0.675 at the pre-specified sigma 1.155, 0.784 / 0.861 at the holdout sigma for J / L1*; observed delta +0.478). The author asked for more cases. The frozen 84-question expansion bank (sha256 `a39bcc0fd88587de8ef2fe14304948995b8e5bb3e6e5cfb04303784ffc2a33c8`, tag `access2026-study2-bank-freeze`, addendum 32) was already judged on A..F in Study 2 Stage 2. This addendum re-analyses those judge scores for A vs B. Nothing here changes a registered result, gate or headline number; it is reported whatever it is.

## 34.2 What exists (read from `harness/study2_llm_labels` before this commit; no score value was read)

* `manifests/eligibility.json` / `results_stage2.json`: paper's strict eligibility (`_grounding_match_info(...)["can_ablate"]`, no allowlist) per (variant, question). Counts: 84 questions, 504 cells, 208 eligible cells (A 67, B 29, C-F 28 each), 70 eligible clusters, **26 clusters eligible in both A and B**. These counts are structure, not scores.
* `raw/judge_glm_stage2.jsonl` and `raw/judge_gptoss_stage2.jsonl`: 624 records each = 208 eligible cells x 3 repeats (temperature 0, as addendum 26), `invalid=0` in the committed progress logs.
* **Consequence.** All 84 questions were not scored in every cell: only eligible cells were scored (by design of addendum 32). Repeats already number 3 per judge per eligible cell. **No new judge call is needed, and none is made by this addendum.** The tunnel to the shared server is therefore not opened. If the analysis finds a missing or invalid record, it is reported as missing; it is not re-requested.
* The paper's eligibility rule limits the A->B set: only 26 of 70 eligible clusters have both an eligible A cell and an eligible B cell. The set cannot be enlarged without changing the rule, which is not done.

## 34.3 Outcome (fixed)

* Per cluster (= question; one question per cluster in this bank): `d = mean_J(B) - mean_J(A)`, where each cell's J is the **mean of its 3 repeats** (valid repeats only). Contrast = mean of `d` over the eligible-in-both clusters.
* Interval: question-clustered paired BCa bootstrap, the paper's routine `analyze_holdout.cluster_bootstrap_delta` (seed 20260913, B = 10,000, mid-rank ties); 95% BCa for "resolved", 90% BCa for the TOST equivalence reading.
* Also reported: exact two-sided sign test on the non-zero `d`, and paired Wilcoxon signed-rank (zeros dropped, `analyze_holdout.wilcoxon_zeros_dropped`).
* Sensitivity (labelled as such, not the outcome): the same with the Stage 2 convention, J = median of the 3 repeats (integer).
* **Judges, each its own analysis, never pooled:** GLM-4.7-Flash (`glm`) and gpt-oss-20b (`gptoss`). The registered holdout judge (`gemini-3.6-flash`, external API) has **no route here** (no key configured); these judges are named non-Qwen substitutes and their numbers are not the registered judge's.

## 34.4 Views

Exactly Study 2 Stage 2's judge views: the **question-only subgraph** of the variant's graph built for the question (addendum 30 `exp` manifest, sha256 `e4b18886511b36b4841dbc599b7032793b047f59857a12ad5cdac37751a2b7bd`), system = `run_holdout.RUBRIC`, user = `ARTIFACT:\n{view}\n\nQUESTION: {question}`, temperature 0, `json_object`. These are **not** the full renderings (0.3 to 2.4 million characters, too long for a 65,536-token window): a deviation from the registered judge's input, named in addendum 32.8. Consequence for reading: the views are built from the question's terms, so a contrast of A and B on them is a contrast of what a question-focused extract of each build holds, not of the judge reading the whole build.

## 34.5 Power and decision rule (fixed before computing)

* MDE formula of the paper (80% power, two-sided 0.05, normal approximation): `MDE = (z_{0.975} + z_{0.80}) * sigma / sqrt(n)` with z sum 2.8016; it reproduces the paper's 0.675 at n = 23, sigma = 1.155.
* Prospective MDE at `n` = number of eligible-in-both clusters (26 per the structure above): sigma = 1.155 -> 0.634; sigma = 1.343 (holdout J) -> 0.738; sigma = 1.473 (holdout L1*) -> 0.809. The realized sigma of this bank's `d` is also reported, with its MDE. **Stated in advance:** at n = 26 the MDE is about the same as at n = 23, so this expansion does not by itself add power over the holdout for a +0.478 effect; the number of clusters is limited by the paper's eligibility rule, not by the bank size. The result is reported whatever it is.
* Decision (the paper's three decisions, unchanged): **resolved** = the 95% BCa interval excludes 0 (the sign of the Wilcoxon statistic is reported next to it; the manuscript's rank-agreement rule is reported as `decision_with_rank_rule`); **equivalent within +-0.50** = not resolved and the 90% BCa interval lies inside (-0.50, +0.50) (TOST at alpha 0.05 per side; `analyze_holdout.tost_decision` with margin 0.50); otherwise **unresolved**. No threshold, margin or seed is changed after any score is seen.

## 34.6 Secondary: bridge to the 36-question holdout bank

Planned: the same contrast restricted to expansion questions that are also holdout-bank questions. Checked on text before any score was read: the expansion bank and `bank/cq_bank_brick_v2.csv` share **0 identical question texts and 0 identical grounding strings**, and the cluster ids are disjoint (CQX vs CQB). The bridge subset is therefore **empty and not computable**; it is reported as such. No near-duplicate matching is substituted. As a context-only substitute the report also gives the registered-judge holdout A->B numbers from the paper (read from the paper's committed text, not recomputed).

## 34.7 Labels

There are no evidence labels on the new questions. The contrast is on J, **not** on the label-corrected L1*. Every table and report carries: "judge-score contrast on the expansion bank; not human-labelled".

## 34.8 Outputs and order of work

1. This file, committed alone.
2. `analyze.py`, `test_analyze.py` (synthetic), then `results.json`, `REPORT_auto.md`, `tables.tex` (one appendix-table row set and one supplement-table row set, per judge, with the bridge row), committed. Any change after the first score is read goes to `DEVIATIONS.md`.
3. No host, address, port or key appears in any committed file; the reserved files (`site_key*`, `labeling_sheet_key*`, `human_labels_export*`, `views_for_raters.zip`, `.env`) are not opened.

---

## 34.A1 Amendment (2026-10-20, post hoc; committed before any new score is read or any new call is made)

**Trigger.** The coordinator widened the scope: use every question that has A and B variant graphs, not only the 84-question bank. Section 34.1-34.8 stand for the expansion-bank analysis (already computed from existing Stage 2 scores and committed; interim). A1 **adds** analyses; it changes no threshold, seed, margin, interval method or decision rule of 34.3-34.5. Nothing is re-fit after seeing data.

**A1.1 Inventory (no model call).** For every bank with A and B graphs: number of questions, questions with a non-N/A A and B view, eligible clusters (paper's strict rule on the full rendering where the bank has a grounding; where it has none, "view exists in both A and B" is used and labeled `eligibility = view-exists`), frozen or not, artifact-blind or not. Banks: Brick holdout (36), its paraphrases (Tier 3a, 36), v2 extras (Tier 3b, 24), expansion (84), development bank (Ontology-101: the 16-question judged set, and the 18-question extended bank), natural-documentation Brick A/B (36), second domain (manufacturing; aggregate only). Frozen means a committed freeze tag/hash; AI-drafted and unfrozen banks (expansion draft was later frozen unreviewed; v2 extras; paraphrases; development extended bank; manufacturing) are labeled "AI-draft/unreviewed" and sit in a **separate row/block** from the frozen holdout.

**A1.2 Scoring.** Existing scores are reused where they exist with the same judge, rubric, temperature 0 and 3 repeats: holdout subgraph (addendum 26, `review6_judges/raw`), development summaries (addendum 26), natural-documentation (addendum 27, `review6_natural/raw`), expansion (Study 2 Stage 2). **Missing A/B cells** (paraphrases, v2 extras, development extended bank, manufacturing, and any holdout/other A/B cell without a score) are scored with both judges (glm, gptoss), 3 repeats each, same `run_holdout.RUBRIC` and user message as Stage 2, on the question-only subgraph view of addendum 30. Access: request-only through an SSH port-forward to the shared server; concurrency chosen by a probe and never exceeded; backoff on errors; resumable JSONL; the tunnel is closed at the end; no host, address, port or key is written to any committed file. The shared server is not touched.

**A1.3 Analyses (judge score J, mean of repeats per cell, paired B - A per cluster, same BCa seed 20260913, B = 10,000, same decision rule, same MDE formula).** Each reports eligible-cluster count n, mean J A and B, delta [95% BCa], MDE at sigma 1.155 / 1.343 and at the realized sigma, sign and Wilcoxon p, decision.
 (a) per bank (one row per bank/judge/view type);
 (b) pooled over all **Brick-holdout-graph** banks (holdout, paraphrases, v2 extras, expansion), clustered by **source question**: a paraphrase shares the cluster of its source question (so it is not an independent unit), and within a cluster all (bank, question) A-B differences are averaged to one cluster difference before bootstrapping. Two pools are reported, never merged: **frozen-only** (holdout) and **all** (adds AI-draft/unreviewed banks, labeled);
 (c) per domain: Brick holdout graphs (pool b), development corpus, natural Brick documentation, second domain (aggregate only; no per-question rows reported).
Where a source question appears in two banks with different view constructions, the view construction is never mixed within one cell; the per-bank and per-pool tables state the view type.

**A1.4 Limits stated in advance.** Views are subgraphs, not the registered judge's full renderings; judges are glm and gptoss, not the registered judge; no labels (J only); eligibility for banks without grounding is `view-exists`, weaker than the paper's rule; banks other than the frozen holdout are AI-drafted and unreviewed by the author; pooling raises n but also mixes question sources, so the pooled estimate is a different estimand than the holdout's. The pooled result is reported whatever it is.

---

## 34.A2 Amendment (2026-10-20, post hoc; committed before anything of A2 is computed)

**Why.** The main analysis (34.3, A1.3) keeps only clusters with a scored A cell and a scored B cell. A cell is absent when the variant graph has no question-relevant content (no subgraph view, or the paper's rule finds no matching line). Dropping those clusters can bias A->B, in a direction that depends on which variant is missing more often. This is a **sensitivity analysis**; it does **not** replace the main analysis and no main number is changed.

**A2.1 Rule (fixed here).** For each bank, take **all its eligible clusters**: expansion 70 (eligible in at least one of A-F by the paper's rule); holdout and paraphrases: clusters with a primary (eligible) cell in at least one variant of the registered 188; v2 extras: clusters eligible under the paper's rule in at least one of A-F; development, natural documentation, second domain: every question of the bank (eligibility = view-exists). For every such cluster, a missing A or B cell (no judge score: not eligible, or no subgraph view) is given **J = 0**, the judge's floor for "cannot answer"; scored cells keep their mean-of-repeats J. Then the same paired B - A contrast, BCa (seed 20260913, B = 10,000), sign and Wilcoxon tests, MDE and decision rule as the main analysis. Pools follow A1.3(b): imputed per-bank clusters, clustered by source question.

**A2.2 Counts.** Per bank and judge: eligible clusters, missing A cells, missing B cells, missing in both, and (where the paper's rule applies) how many of the missing cells are eligible-by-rule but have no view or score versus ineligible by rule.

**A2.3 Limits stated in advance.** J = 0 is an assumption, not a measurement: a variant graph can lack a matching subgraph for the question text while still holding the answer elsewhere; a floor imputation therefore favors the variant with more content and is an upper-bound-style stress test of the dropped-cell bias, not an estimate of the true contrast. No new model call is made; a question that would need one is skipped and reported. Results are reported whatever they are, next to the main analysis, and labelled "sensitivity, post hoc, not human-labelled".

---

## 34.A3 Amendment (2026-10-20, post hoc; committed before anything of A3 is computed)

**Why.** External review 16 notes that the 84-question expansion bank was scored by the substitute judges without human labels, so a Brick pool that contains it is not independent of the bank intended for a later confirmatory run. A3 adds a Brick pool **without** the expansion bank and states the equivalence decision of every Study 3 and Study 4 row under the holdout's registered margin as well.

**A3.1 No-expansion pool (computed).** Same code path as A1.3(b): `analyze_all.pool([holdout, paraphrases, v2_extras])`, clustered by source question, same BCa seed 20260913, B = 10,000, same decision rule at margin 0.50 and the same MDE formula, for glm and gptoss separately. Script: `analyze_a3.py` (reads only the committed judge records; no label, no model call). Output: `results_a3.json`.

**A3.2 Margin +-0.30 (computed from stored intervals).** The margin +-0.50 was pre-fixed in addenda 34 and 35 (this file; `study4_domains/PLAN.md`). The holdout's registered margin is +-0.30. For every row of Tables A9 and S65-S67 the decision is re-derived with `analyze_holdout.tost_decision` at margin 0.30 from the stored 95% and 90% BCa intervals (resolved is unchanged; equivalent becomes unresolved where the 90% interval is not inside +-0.30). No interval, seed or score changes.

**A3.3 Limits.** Post hoc and exploratory like A1/A2; the 0.30 reading is a sensitivity reading and does not replace the pre-fixed 0.50 decisions.
