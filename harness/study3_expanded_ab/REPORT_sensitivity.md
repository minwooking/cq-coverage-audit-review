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
