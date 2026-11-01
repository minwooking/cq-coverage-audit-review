# Calibration and Washout Plan

This is a prospective plan; it contains no completed labels, names, or statistics.

1. Freeze the rubric, bank digest, seed, and item order before the first label. Record the rubric digest in PREREG at freeze; do not backfill it after seeing results.
2. Train the annotator using rubric anchors and practice items that are not part of the 36-question scored sample. Resolve interpretation questions in writing without changing the frozen anchors.
3. Run the primary pass over 216 Brick cells. Record evidence verdict, verbatim span, timestamps, and notes in the CSV. Keep the judge score unavailable until the evidence decision is saved, then enter it from the sealed score source.
4. Run the separately planned raw-TTL pass for the 24 ASK-inexpressible questions only; keep it separate from the washout sample.
5. After at least 21 days, re-score 72 stratified cells (48 proportional by category and judge band; 24 enriched for ASK/judge conflicts), presenting a paraphrase where authored. Do not use the first label during re-scoring.
6. Compute intra-rater quadratic-weighted kappa with its confidence interval, and report only after the audit trail and sealed exports are checked. The preregistered gate is CI lower bound at least 0.70; this is necessary, not sufficient.
7. Apply the preregistered one-sided demotion to obtain L1*. Report G1, G2, G3, G4, G5, G6, G7, and any G8 only from the released, reproducible exports. No gate is marked complete in this plan.

## Pre-registered gate thresholds (PREREG.md §2, table lines 107-114)

Reproduced here for the annotator's convenience. PREREG.md is authoritative; if this
table and PREREG ever disagree, PREREG wins and this file is the one that is wrong.

| Gate | Quantity | Threshold | Direction |
|---|---|---|---|
| G1 | silent over-credit pi, CQ-clustered CI upper bound | <= 10% | two-sided |
| G2 | intra-rater QWK (washout re-score, n=72) | CI lower >= 0.70 | necessary, not sufficient |
| G3 | annotator negative control (ablated cells marked unsupported) | >= 22/24 | two-sided |
| G4 | human-judge QWK | fails if CI upper < 0.60 | FALSIFICATION-ONLY: can fail, can never pass |
| G5 | MAE(J,H) | CI upper <= 0.50 | two-sided |
| G6 | A->B consistency + non-Qwen judge direction agreement + fragility K >= 6 | consistency | two-sided |
| G7 | audit-trail integrity | 100% of labels timestamped before unblind commit; 0 post-hoc edits; cells under 20s < 3% | two-sided |
| G8 | external 36-cell spot-check (if obtained) | fails if mean signed-difference CI excludes 0 in the lenient direction | FALSIFICATION-ONLY |

Two things the annotator must understand before starting:

- **G1 is effectively zero-tolerance at this sample size.** With n=36 CQ-clusters, 0
  observed events gives an exact Clopper-Pearson upper bound of 8.0% (one-sided 95%)
  or 9.7% (one-sided 97.5%), and a single event gives 12.5% or 14.5% respectively — so
  one silent over-credit already breaches the 10% gate under either level, and even a
  clean zero leaves only 0.3 points of slack at the stricter level. (3/36 = 8.3% is the
  rule-of-three approximation, not the exact bound.) The failure-event
  counting unit is the CQ-cluster, not the cell and not the raw judge sample.
- **G4 and G8 can only fail.** High human-judge agreement under non-independence is
  expected regardless of validity, so passing them establishes nothing. Do not report
  either as "passed".

Failure policy (PREREG lines 309-315): if G1 or G5 fails, the judge is NOT called
calibrated and the outcome is reported as a negative result. If G4 fails, the judge is
declared uncalibrated and quantitative conclusions are restricted to the ASK-oracle track.

Human-only checks before release: consent and acknowledgment, annotator identity handling, secure storage, independent export review, de-identification, and confirmation that no judge rationale or endpoint credential entered the annotation package.
