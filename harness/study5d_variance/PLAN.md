# PREREG addendum 36, amendment D (exploratory, post hoc) -- variance decomposition of the Study 5 judge panel

> AI-generated draft; the author must review it before it is relied on. Date: 2026-10-21. Post hoc: written after addendum 36 and amendments B and C, with knowledge of their per-judge contrasts (they differ visibly across judges). Committed alone before any computation of this amendment. Cheap re-analysis of committed score CSVs: no model call, no server access, no change to the paper.

## D.1 Question
An expert review asked whether the A->B contrast interacts with the judge (a judge-dependent contrast) or is a common effect plus judge level offsets, and what the within-judge repeat agreement is as a ceiling for the between-judge agreement (QWK 0.39-0.68).

## D.2 Data (committed CSVs only)
`study5_judge_panel/scores_{glm,gptoss,q38,q80,gw}.csv` (gw = luna, partly 2 repeats), `study5b_small_judges/scores_{q38_27b,q35_9b,q35_4b}.csv`; cells from `study5_judge_panel/cells_ab.json` (372 A/B cells) and per-judge paper contrasts from the `results.json` of Study 5 and 5b. C, D, E (amendment C) have no A/B pair and enter only the repeat-agreement file check, not the interaction. Raw JSONL (gitignored) is not read.

## D.3 Scopes and judge sets (fixed)
- Scopes: `brick_pool` (58 source questions; per question the mean over banks, as in addendum 34 A1) and `new_domains_pooled` (99 questions of DCAT, SOSA/SSN, PROV with both A and B); never mixed.
- Judge sets: INDEP = {glm, gptoss, q38, gw}; INDEP+SF = INDEP + q80 (the five-judge panel; q80 is the extractor's family); LADDER = {q38_27b, q35_9b, q35_4b}; ALL = all eight. Interaction analysis uses complete cases: only questions with A and B scored by every judge of the set (n recorded).

## D.4 Analyses (fixed before computation)
(a) Model: J ~ variant + judge + variant x judge + (1|question) + (1|question:variant) + (1|question:judge) + repeat residual. The (1|question:judge) term is added to the brief's specification because judge-by-question disagreement is the largest judge-related variance and would otherwise leak into the interaction error term; this is stated as a refinement fixed here, not found later. statsmodels is not installed and no package is installed; the fit is the method-of-moments (expected-mean-squares) decomposition of the mixed ANOVA on unit means y_{q,v,j} (mean over repeats and banks), question random, variant and judge fixed:
 - sigma2_vj = max(0, (MS_vj - MS_qvj)/Q) * (V-1)(J-1)/(V J); components sigma2_q, sigma2_qv, sigma2_qj, sigma2_qvj (net of repeat noise s2_rep/n_rep), s2_rep (within-cell repeat variance), sigma2_v, sigma2_j (fixed-effect variances), negatives truncated at 0.
 - Interaction share = sigma2_vj / (sum of all components). Also reported: the share of the variance that is variant-related, sigma2_vj / (sigma2_v + sigma2_vj + sigma2_qv).
 - Tests of H0 "no judge x variant interaction" on T = sigma2_vj: (i) question-clustered bootstrap, B = 2000, seed 20260913: interaction effects are subtracted from the data (null imposed), questions resampled with replacement, one-sided p = (1 + #{T* >= T_obs}) / (B + 1); (ii) permutation test, 2000 permutations, seed 20260913: judge main effects removed, then judge labels permuted within each question x variant cell; (iii) classical F = MS_vj / MS_qvj reported for reference only. The decision uses (i); (ii) and (iii) are reported beside it.
(b) Per judge and scope: within-judge repeat agreement = mean over repeat pairs of the quadratic weighted kappa (k = 4, 0-3) across the cells in scope; ICC(2,1) of cells x repeats (cells with the modal number of repeats; two-way random, absolute agreement) as the agreement ceiling; between-judge QWK = mean over the other judges in the five-judge-plus-ladder pool of the pairwise QWK in the paper's way (per cell median_low of repeats), and a repeat-1-versus-repeat-1 between-judge QWK comparable to the repeat pairs. Reading: within-judge >= between-judge is expected; the gap is the part of disagreement that is judge, not noise.
(c) Per judge and scope: Delta mixed = mean over complete-case questions of the unit-level B - A (the fixed variant + variant x judge estimate), with question-clustered bootstrap 95% percentile CI (B = 2000, seed 20260913), beside the paper's BCa delta and CI from the committed `results.json` (all cells available to that judge). Empirical-Bayes shrunk estimate (judge as random slope) in `results.json`. Between-judge SD of the contrast: sample SD over judges of the Delta, with a question-clustered bootstrap percentile CI, and the noise-corrected SD sqrt(max(0, var_j(Delta_j) - mean_j se_j^2)).
(d) Reported for the scope x judge-set grid of D.3: INDEP, INDEP+SF, LADDER, ALL, so that same-family and ladder judges are shown separately and pooled with and without.

## D.5 Reading rule (fixed)
"Judge-dependent contrast" is supported for a scope and judge set if the clustered-bootstrap interaction test gives p < 0.05 or the interaction variance share >= 10%; otherwise the contrasts are consistent with a common effect plus judge level offsets. No threshold changes after a result. Exploratory; judge scores, not human labels.

## D.6 Outputs and order
`analyze.py` (+ `test_analyze.py` on synthetic data), `results.json`, `REPORT_auto.md`, `tables.tex` (one appendix-size table: scope x judge -> within-judge repeat QWK, between-judge QWK, Delta mixed, Delta BCa, plus the interaction-test line). Commits: this plan first; code, results and report after.
