# Addendum 34 A1 -- judge-score contrast (J, subgraph views, named non-registered judges) across question banks; not human-labelled; only the holdout and expansion banks are frozen, the rest are AI-draft/unreviewed

### Inventory (questions with A and B variant graphs)

| bank | questions | with A and B view | eligible clusters in A and B (glm / gptoss) | frozen | artifact-blind |
|---|---|---|---|---|---|
| holdout | 36 | 36 subgraph views exist; 22 with both A and B scored-eligible | 22 / 22 | yes (registered, PREREG freeze) | as documented in the paper; not re-audited here |
| paraphrases (Tier 3a) | 36 | 33 | 21 / 21 | no freeze record checked | AI-completed paraphrases of the holdout questions; same grounding as source |
| v2 extras (Tier 3b) | 24 | 22 | 10 / 10 | no freeze record checked (v2 pool, 60 rows) | not assessed here |
| expansion (Study 2) | 84 | 84 | 26 / 26 | yes (sha256 a39bcc0f..., tag access2026-study2-bank-freeze) | artifact-blind per README, static builder scan only (BANK_PROVENANCE); author-unreviewed AI draft |
| development (Ontology-101) | 18 | 16 | 15 / 16 | no | not assessed; extended bank adds CQ17-18 |
| natural documentation (Brick) | 36 | 36 | 36 / 36 | no (same 36 holdout questions, other graphs) | analyst-read grounding check before build, not blind (addendum 27) |
| second domain (manufacturing) | 12 | 11 | 11 / 11 | no | aggregate only |

Heterogeneity is visible and not tested here: gpt-oss-20b has holdout +0.409 but expansion -0.564, so the pooled Brick estimate mixes banks that disagree in sign for that judge. Pooling raises n but is a different estimand than the holdout's.


Post hoc. Mean of repeats per cell; paired B - A per cluster; BCa 95% (seed 20260913, B = 10,000). MDE at sigma 1.155 / 1.343 / realized. Frozen = holdout and expansion (hash/tag); all other banks are AI-draft/unreviewed and sit in separate rows.

## GLM-4.7-Flash

### (a) per bank
| row | n clusters | J(A) | J(B) | delta [95% BCa] | MDE | sign p / Wilcoxon p | decision | note |
|---|---|---|---|---|---|---|---|---|
| holdout (frozen; subgraph; elig paper rule (registered 188 primary cells)) | 22 | 1.561 | 2.106 | +0.545 [-0.076, +1.182] | 0.69 / 0.80 / 0.93 | 0.302 / 0.104 | unresolved | |
| paraphrases (AI-draft; subgraph; elig paper rule via source question's grounding) | 21 | 1.286 | 1.730 | +0.444 [-0.238, +1.079] | 0.71 / 0.82 / 0.96 | 0.648 / 0.146 | unresolved | |
| v2_extras (AI-draft; subgraph; elig paper rule (v2 bank grounding)) | 10 | 1.467 | 1.867 | +0.400 [-0.067, +1.300] | 1.02 / 1.19 / 0.93 | 1.000 / 0.656 | unresolved | |
| expansion (frozen; subgraph; elig paper rule (Stage 2 eligible cells)) | 26 | 1.410 | 1.769 | +0.359 [-0.154, +0.885] | 0.63 / 0.74 / 0.76 | 1.000 / 0.176 | unresolved | |
| dev_summary (AI-draft; dev rendering summary; elig view-exists) | 15 | 1.422 | 1.889 | +0.467 [+0.178, +0.956] | 0.84 / 0.97 / 0.54 | 0.031 / 0.031 | resolved | |
| dev_ext_subgraph (AI-draft; subgraph; elig view-exists) | 16 | 1.542 | 2.688 | +1.146 [+0.674, +1.708] | 0.81 / 0.94 / 0.77 | 0.000 / 0.000 | resolved | |
| natural_docs (AI-draft; subgraph; elig view-exists (36 question S_full)) | 36 | 1.454 | 1.556 | +0.102 [-0.231, +0.426] | 0.54 / 0.63 / 0.47 | 1.000 / 0.533 | equivalent | |
| second_domain_mfg (AI-draft; subgraph; elig view-exists) | 11 | 2.364 | 1.030 | -1.333 [-1.848, -0.848] | 0.98 / 1.13 / 0.76 | 0.002 / 0.002 | resolved | |

### (b) pooled, Brick holdout graphs, clustered by source question
| row | n clusters | J(A) | J(B) | delta [95% BCa] | MDE | sign p / Wilcoxon p | decision | note |
|---|---|---|---|---|---|---|---|---|
| brick_frozen_only (holdout) | 22 | 1.561 | 2.106 | +0.545 [-0.076, +1.182] | 0.69 / 0.80 / 0.93 | 0.302 / 0.104 | unresolved | |
| brick_frozen (holdout + expansion; expansion unreviewed) | 48 | 1.479 | 1.924 | +0.444 [+0.035, +0.840] | 0.47 / 0.54 / 0.59 | 0.487 / 0.026 | resolved | |
| brick_all (+ paraphrases, v2 extras; AI-draft) | 58 | 1.440 | 1.853 | +0.414 [+0.080, +0.753] | 0.42 / 0.49 / 0.48 | 0.451 / 0.014 | resolved | |

### (c) per domain
| row | n clusters | J(A) | J(B) | delta [95% BCa] | MDE | sign p / Wilcoxon p | decision | note |
|---|---|---|---|---|---|---|---|---|
| brick holdout graphs (all pool) | 58 | 1.440 | 1.853 | +0.414 [+0.080, +0.753] | 0.42 / 0.49 / 0.48 | 0.451 / 0.014 | resolved | |
| development corpus (summary + ext subgraph, clustered by question) | 17 | 1.402 | 2.216 | +0.814 [+0.510, +1.206] | 0.78 / 0.91 / 0.51 | 0.000 / 0.000 | resolved | |
| natural Brick documentation | 36 | 1.454 | 1.556 | +0.102 [-0.231, +0.426] | 0.54 / 0.63 / 0.47 | 1.000 / 0.533 | equivalent | |
| second domain (aggregate only) | 11 | 2.364 | 1.030 | -1.333 [-1.848, -0.848] | 0.98 / 1.13 / 0.76 | 0.002 / 0.002 | resolved | |

## gpt-oss-20b

### (a) per bank
| row | n clusters | J(A) | J(B) | delta [95% BCa] | MDE | sign p / Wilcoxon p | decision | note |
|---|---|---|---|---|---|---|---|---|
| holdout (frozen; subgraph; elig paper rule (registered 188 primary cells)) | 22 | 1.621 | 2.030 | +0.409 [-0.242, +1.045] | 0.69 / 0.80 / 0.95 | 0.581 / 0.238 | unresolved | |
| paraphrases (AI-draft; subgraph; elig paper rule via source question's grounding) | 21 | 1.619 | 1.635 | +0.016 [-0.952, +0.905] | 0.71 / 0.82 / 1.36 | 0.454 / 0.958 | unresolved | |
| v2_extras (AI-draft; subgraph; elig paper rule (v2 bank grounding)) | 10 | 1.500 | 1.733 | +0.233 [-0.667, +1.400] | 1.02 / 1.19 / 1.53 | 1.000 / 0.625 | unresolved | |
| expansion (frozen; subgraph; elig paper rule (Stage 2 eligible cells)) | 26 | 2.256 | 1.692 | -0.564 [-1.167, +0.154] | 0.63 / 0.74 / 0.95 | 0.118 / 0.188 | unresolved | |
| dev_summary (AI-draft; dev rendering summary; elig view-exists) | 16 | 0.958 | 2.146 | +1.188 [+0.021, +2.000] | 0.81 / 0.94 / 1.43 | 0.039 / 0.080 | resolved | |
| dev_ext_subgraph (AI-draft; subgraph; elig view-exists) | 16 | 1.333 | 2.458 | +1.125 [+0.562, +1.771] | 0.81 / 0.94 / 0.90 | 0.008 / 0.008 | resolved | |
| natural_docs (AI-draft; subgraph; elig view-exists (36 question S_full)) | 36 | 0.954 | 1.324 | +0.370 [-0.093, +0.843] | 0.54 / 0.63 / 0.68 | 0.143 / 0.190 | unresolved | |
| second_domain_mfg (AI-draft; subgraph; elig view-exists) | 11 | 2.545 | 1.333 | -1.212 [-2.152, -0.121] | 0.98 / 1.13 / 1.52 | 0.289 / 0.062 | resolved | |

### (b) pooled, Brick holdout graphs, clustered by source question
| row | n clusters | J(A) | J(B) | delta [95% BCa] | MDE | sign p / Wilcoxon p | decision | note |
|---|---|---|---|---|---|---|---|---|
| brick_frozen_only (holdout) | 22 | 1.621 | 2.030 | +0.409 [-0.242, +1.045] | 0.69 / 0.80 / 0.95 | 0.581 / 0.238 | unresolved | |
| brick_frozen (holdout + expansion; expansion unreviewed) | 48 | 1.965 | 1.847 | -0.118 [-0.606, +0.375] | 0.47 / 0.54 / 0.70 | 0.572 / 0.774 | unresolved | |
| brick_all (+ paraphrases, v2 extras; AI-draft) | 58 | 1.897 | 1.764 | -0.132 [-0.552, +0.287] | 0.42 / 0.49 / 0.61 | 1.000 / 0.520 | equivalent | |

### (c) per domain
| row | n clusters | J(A) | J(B) | delta [95% BCa] | MDE | sign p / Wilcoxon p | decision | note |
|---|---|---|---|---|---|---|---|---|
| brick holdout graphs (all pool) | 58 | 1.897 | 1.764 | -0.132 [-0.552, +0.287] | 0.42 / 0.49 / 0.61 | 1.000 / 0.520 | equivalent | |
| development corpus (summary + ext subgraph, clustered by question) | 17 | 1.078 | 2.255 | +1.176 [+0.559, +1.775] | 0.78 / 0.91 / 0.92 | 0.006 / 0.005 | resolved | |
| natural Brick documentation | 36 | 0.954 | 1.324 | +0.370 [-0.093, +0.843] | 0.54 / 0.63 / 0.68 | 0.143 / 0.190 | unresolved | |
| second domain (aggregate only) | 11 | 2.545 | 1.333 | -1.212 [-2.152, -0.121] | 0.98 / 1.13 / 1.52 | 0.289 / 0.062 | resolved | |

---

## A2 sensitivity -- sensitivity, post hoc, not human-labelled: a missing A or B cell is set to J = 0 (judge floor); main analysis unchanged

Universe per bank = all eligible clusters (expansion 70). A missing A or B cell (not eligible by the paper's rule, or no subgraph view) is J = 0. Main = the main analysis (clusters with both cells scored). Counts are cells in the universe; 'elig, no view' = eligible by rule but no view or score.

### GLM-4.7-Flash

#### per bank
| row | universe n | miss A / B / both (elig, no view A / B) | main n, delta | sens. J(A) | sens. J(B) | sens. delta [95% BCa] | MDE (1.155 / 1.343 / realized) | sign p / Wilcoxon p | decision (main -> sens.) |
|---|---|---|---|---|---|---|---|---|---|
| holdout | 33 | 11 / 1 / 1 (1 / 1) | 22, +0.545 | 1.040 | 1.667 | +0.626 [+0.131, +1.091] | 0.56 / 0.65 / 0.69 | 0.064 / 0.016 | unresolved -> resolved |
| paraphrases | 33 | 12 / 0 / 0 (2 / 0) | 21, +0.444 | 0.818 | 1.485 | +0.667 [+0.162, +1.111] | 0.56 / 0.65 / 0.68 | 0.076 / 0.008 | unresolved -> resolved |
| v2_extras | 17 | 2 / 5 / 0 (0 / 1) | 10, +0.400 | 1.373 | 1.314 | -0.059 [-0.882, +0.667] | 0.78 / 0.91 / 1.14 | 1.000 / 0.819 | unresolved -> unresolved |
| expansion | 70 | 3 / 41 / 0 (0 / 0) | 26, +0.359 | 1.562 | 0.752 | -0.810 [-1.224, -0.386] | 0.39 / 0.45 / 0.60 | 0.001 / 0.000 | unresolved -> resolved |
| dev_summary | 16 | 0 / 1 / 0 (0 / 0) | 15, +0.467 | 1.396 | 1.771 | +0.375 [+0.042, +0.833] | 0.81 / 0.94 / 0.56 | 0.125 / 0.094 | resolved -> resolved |
| dev_ext_subgraph | 18 | 2 / 0 / 0 (0 / 0) | 16, +1.146 | 1.370 | 2.630 | +1.259 [+0.796, +1.815] | 0.76 / 0.89 / 0.74 | 0.000 / 0.001 | resolved -> resolved |
| natural_docs | 36 | 0 / 0 / 0 (0 / 0) | 36, +0.102 | 1.454 | 1.556 | +0.102 [-0.231, +0.426] | 0.54 / 0.63 / 0.47 | 1.000 / 0.533 | equivalent -> equivalent |
| second_domain_mfg | 12 | 0 / 1 / 0 (0 / 0) | 11, -1.333 | 2.417 | 0.944 | -1.472 [-2.028, -0.972] | 0.93 / 1.09 / 0.79 | 0.001 / 0.001 | resolved -> resolved |

#### pooled and per domain
| row | universe n | miss A / B / both (elig, no view A / B) | main n, delta | sens. J(A) | sens. J(B) | sens. delta [95% BCa] | MDE (1.155 / 1.343 / realized) | sign p / Wilcoxon p | decision (main -> sens.) |
|---|---|---|---|---|---|---|---|---|---|
| brick_frozen_only (holdout) | 33 | - | 22, +0.545 | 1.040 | 1.667 | +0.626 [+0.131, +1.091] | 0.56 / 0.65 / 0.69 | 0.064 / 0.016 | unresolved -> resolved |
| brick_frozen (holdout + expansion) | 103 | - | 48, +0.444 | 1.395 | 1.045 | -0.350 [-0.693, -0.006] | 0.32 / 0.37 / 0.50 | 0.086 / 0.027 | resolved -> resolved |
| brick_all (+ paraphrases, v2 extras; AI-draft) | 120 | - | 58, +0.414 | 1.361 | 1.058 | -0.303 [-0.624, +0.006] | 0.30 / 0.34 / 0.45 | 0.235 / 0.041 | resolved -> unresolved |
| brick holdout graphs (all pool) | 120 | - | 58, +0.414 | 1.361 | 1.058 | -0.303 [-0.624, +0.006] | 0.30 / 0.34 / 0.45 | 0.235 / 0.041 | resolved -> unresolved |
| development corpus (summary + ext) | 18 | - | 17, +0.814 | 1.306 | 2.139 | +0.833 [+0.509, +1.244] | 0.76 / 0.89 / 0.53 | 0.000 / 0.001 | resolved -> resolved |
| natural Brick documentation | 36 | 0 / 0 / 0 (0 / 0) | 36, +0.102 | 1.454 | 1.556 | +0.102 [-0.231, +0.426] | 0.54 / 0.63 / 0.47 | 1.000 / 0.533 | equivalent -> equivalent |
| second domain (aggregate only) | 12 | 0 / 1 / 0 (0 / 0) | 11, -1.333 | 2.417 | 0.944 | -1.472 [-2.028, -0.972] | 0.93 / 1.09 / 0.79 | 0.001 / 0.001 | resolved -> resolved |

### gpt-oss-20b

#### per bank
| row | universe n | miss A / B / both (elig, no view A / B) | main n, delta | sens. J(A) | sens. J(B) | sens. delta [95% BCa] | MDE (1.155 / 1.343 / realized) | sign p / Wilcoxon p | decision (main -> sens.) |
|---|---|---|---|---|---|---|---|---|---|
| holdout | 33 | 11 / 1 / 1 (1 / 1) | 22, +0.409 | 1.081 | 1.788 | +0.707 [+0.192, +1.222] | 0.56 / 0.65 / 0.75 | 0.027 / 0.017 | unresolved -> resolved |
| paraphrases | 33 | 12 / 0 / 0 (2 / 0) | 21, +0.016 | 1.030 | 1.485 | +0.455 [-0.273, +1.101] | 0.56 / 0.65 / 0.99 | 0.035 / 0.223 | unresolved -> unresolved |
| v2_extras | 17 | 2 / 5 / 0 (0 / 1) | 10, +0.233 | 1.255 | 1.373 | +0.118 [-0.784, +1.039] | 0.78 / 0.91 / 1.35 | 1.000 / 0.741 | unresolved -> unresolved |
| expansion | 70 | 3 / 41 / 0 (0 / 0) | 26, -0.564 | 1.857 | 0.676 | -1.181 [-1.562, -0.771] | 0.39 / 0.45 / 0.57 | 0.000 / 0.000 | unresolved -> resolved |
| dev_summary | 16 | 0 / 0 / 0 (0 / 0) | 16, +1.188 | 0.958 | 2.146 | +1.188 [+0.021, +2.000] | 0.81 / 0.94 / 1.43 | 0.039 / 0.080 | resolved -> resolved |
| dev_ext_subgraph | 18 | 2 / 0 / 0 (0 / 0) | 16, +1.125 | 1.185 | 2.519 | +1.333 [+0.741, +1.963] | 0.76 / 0.89 / 0.89 | 0.002 / 0.002 | resolved -> resolved |
| natural_docs | 36 | 0 / 0 / 0 (0 / 0) | 36, +0.370 | 0.954 | 1.324 | +0.370 [-0.093, +0.843] | 0.54 / 0.63 / 0.68 | 0.143 / 0.190 | unresolved -> unresolved |
| second_domain_mfg | 12 | 0 / 1 / 0 (0 / 0) | 11, -1.212 | 2.625 | 1.222 | -1.403 [-2.236, -0.361] | 0.93 / 1.09 / 1.41 | 0.180 / 0.031 | resolved -> resolved |

#### pooled and per domain
| row | universe n | miss A / B / both (elig, no view A / B) | main n, delta | sens. J(A) | sens. J(B) | sens. delta [95% BCa] | MDE (1.155 / 1.343 / realized) | sign p / Wilcoxon p | decision (main -> sens.) |
|---|---|---|---|---|---|---|---|---|---|
| brick_frozen_only (holdout) | 33 | - | 22, +0.409 | 1.081 | 1.788 | +0.707 [+0.192, +1.222] | 0.56 / 0.65 / 0.75 | 0.027 / 0.017 | unresolved -> resolved |
| brick_frozen (holdout + expansion) | 103 | - | 48, -0.118 | 1.608 | 1.032 | -0.576 [-0.929, -0.210] | 0.32 / 0.37 / 0.52 | 0.023 / 0.002 | unresolved -> resolved |
| brick_all (+ paraphrases, v2 extras; AI-draft) | 120 | - | 58, -0.132 | 1.551 | 1.039 | -0.512 [-0.848, -0.192] | 0.30 / 0.34 / 0.47 | 0.119 / 0.001 | equivalent -> resolved |
| brick holdout graphs (all pool) | 120 | - | 58, -0.132 | 1.551 | 1.039 | -0.512 [-0.848, -0.192] | 0.30 / 0.34 / 0.47 | 0.119 / 0.001 | equivalent -> resolved |
| development corpus (summary + ext) | 18 | - | 17, +1.176 | 1.019 | 2.296 | +1.278 [+0.648, +1.870] | 0.76 / 0.89 / 0.91 | 0.003 / 0.002 | resolved -> resolved |
| natural Brick documentation | 36 | 0 / 0 / 0 (0 / 0) | 36, +0.370 | 0.954 | 1.324 | +0.370 [-0.093, +0.843] | 0.54 / 0.63 / 0.68 | 0.143 / 0.190 | unresolved -> unresolved |
| second domain (aggregate only) | 12 | 0 / 1 / 0 (0 / 0) | 11, -1.212 | 2.625 | 1.222 | -1.403 [-2.236, -0.361] | 0.93 / 1.09 / 1.41 | 0.180 / 0.031 | resolved -> resolved |

Reading: the floor is an assumption, not a measurement (PLAN A2.3); it favors the variant whose graph has more matching content.

**Missing-cell pattern (counts above).** Missing cells are almost all ineligible by the paper's rule (the variant graph has no matching line), not eligible cells without a view: "elig, no view" is 0 to 2 per bank. The direction of the gap differs by bank: holdout and paraphrases miss A cells (11 and 12 of 33), the expansion bank misses B cells (41 of 70, A 3). The floor therefore moves the holdout toward B > A and the expansion toward A > B, and the pool is a sum of these opposite pushes; the sensitivity is a stress test of dropped-cell bias, not an estimate of the true contrast.
