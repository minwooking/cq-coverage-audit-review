# Addendum 36 amendment D -- variance decomposition of judge-panel scores; not human-labelled; exploratory, post hoc (addendum 36 amendment D)

AI-generated; review before relying on it. Rule fixed in PLAN.md D.5: supported if bootstrap p < 0.05 or interaction share >= 10%.

## Judge x variant interaction (variance components, mixed ANOVA on unit means)

| scope | judges | Q | interaction share [95% CI] | share of variant variance | boot p | perm p | F p | reading |
|---|---|---|---|---|---|---|---|---|
| brick_pool | INDEP | 58 | 0.005 [0.000, 0.020] | 0.02 | 0.025 | 0.020 | 0.019 | judge-dependent contrast supported |
| brick_pool | INDEP+SF | 58 | 0.014 [0.005, 0.032] | 0.04 | <0.001 | <0.001 | <0.001 | judge-dependent contrast supported |
| brick_pool | LADDER | 58 | 0.003 [0.000, 0.019] | 0.01 | 0.092 | 0.090 | 0.085 | common effect plus judge level offsets |
| brick_pool | ALL | 58 | 0.010 [0.004, 0.026] | 0.03 | <0.001 | <0.001 | <0.001 | judge-dependent contrast supported |
| new_domains_pooled | INDEP | 99 | 0.007 [0.001, 0.019] | 0.04 | 0.004 | 0.004 | 0.002 | judge-dependent contrast supported |
| new_domains_pooled | INDEP+SF | 99 | 0.005 [0.001, 0.015] | 0.03 | 0.011 | 0.004 | 0.006 | judge-dependent contrast supported |
| new_domains_pooled | LADDER | 98 | 0.002 [0.000, 0.010] | 0.01 | 0.036 | 0.062 | 0.039 | judge-dependent contrast supported |
| new_domains_pooled | ALL | 98 | 0.005 [0.002, 0.013] | 0.02 | 0.004 | <0.001 | <0.001 | judge-dependent contrast supported |

## Variance components (share of total, single-repeat scale)

| scope | judges | question | question_x_variant | question_x_judge | variant | judge | variant_x_judge | question_x_variant_x_judge_net | repeat |
|---|---|---|---|---|---|---|---|---|---|
| brick_pool | INDEP | 0.245 | 0.284 | 0.010 | 0.000 | 0.017 | 0.005 | 0.314 | 0.124 |
| brick_pool | INDEP+SF | 0.184 | 0.315 | 0.018 | 0.002 | 0.018 | 0.014 | 0.324 | 0.126 |
| brick_pool | LADDER | 0.170 | 0.437 | 0.022 | 0.012 | 0.002 | 0.003 | 0.343 | 0.010 |
| brick_pool | ALL | 0.164 | 0.324 | 0.026 | 0.005 | 0.052 | 0.010 | 0.340 | 0.078 |
| new_domains_pooled | INDEP | 0.319 | 0.165 | 0.012 | 0.000 | 0.000 | 0.007 | 0.381 | 0.117 |
| new_domains_pooled | INDEP+SF | 0.344 | 0.152 | 0.012 | 0.000 | 0.000 | 0.005 | 0.377 | 0.111 |
| new_domains_pooled | LADDER | 0.304 | 0.288 | 0.110 | 0.004 | 0.000 | 0.002 | 0.281 | 0.010 |
| new_domains_pooled | ALL | 0.319 | 0.199 | 0.050 | 0.000 | 0.032 | 0.005 | 0.330 | 0.065 |

## Between-judge SD of the A->B contrast

| scope | judges | Q | mean delta | SD [95% CI] | noise-corrected SD |
|---|---|---|---|---|---|
| brick_pool | INDEP | 58 | 0.05 | 0.25 [0.13, 0.42] | 0.17 |
| brick_pool | INDEP+SF | 58 | 0.17 | 0.35 [0.24, 0.51] | 0.30 |
| brick_pool | LADDER | 58 | 0.33 | 0.22 [0.07, 0.43] | 0.07 |
| brick_pool | ALL | 58 | 0.23 | 0.30 [0.21, 0.45] | 0.23 |
| new_domains_pooled | INDEP | 99 | 0.01 | 0.23 [0.13, 0.39] | 0.20 |
| new_domains_pooled | INDEP+SF | 99 | 0.01 | 0.20 [0.12, 0.34] | 0.16 |
| new_domains_pooled | LADDER | 98 | -0.20 | 0.18 [0.06, 0.32] | 0.11 |
| new_domains_pooled | ALL | 98 | -0.07 | 0.21 [0.15, 0.32] | 0.17 |

## Per judge: repeat agreement and contrasts

| scope | judge | within QWK | ICC(2,1) | between QWK (median) [range] | between QWK (repeat 1) | delta mixed (ALL complete cases) [CI] | delta BCa [CI] |
|---|---|---|---|---|---|---|---|
| brick_pool | GLM-4.7-Flash | 0.87 | 0.87 | 0.46 [0.39, 0.51] | 0.46 | 0.41 [0.09, 0.75] | 0.41 [0.08, 0.75] (n=58) |
| brick_pool | gpt-oss-20b | 0.83 | 0.83 | 0.44 [0.39, 0.52] | 0.40 | -0.13 [-0.57, 0.32] | -0.13 [-0.55, 0.29] (n=58) |
| brick_pool | Qwen3.8-Flash-Next | 0.93 | 0.93 | 0.54 [0.43, 0.72] | 0.55 | -0.07 [-0.41, 0.28] | -0.07 [-0.41, 0.28] (n=58) |
| brick_pool | Qwen3-Next-80B | 0.88 | 0.88 | 0.51 [0.42, 0.60] | 0.50 | 0.67 [0.24, 1.07] | 0.67 [0.24, 1.06] (n=58) |
| brick_pool | luna | 0.93 | 0.93 | 0.45 [0.35, 0.72] | 0.46 | -0.02 [-0.31, 0.29] | -0.02 [-0.31, 0.29] (n=58) |
| brick_pool | Qwen3.8-27B | 1.00 | 1.00 | 0.53 [0.41, 0.64] | 0.55 | 0.13 [-0.31, 0.56] | 0.13 [-0.30, 0.55] (n=58) |
| brick_pool | Qwen3.5-9B | 0.98 | 0.98 | 0.50 [0.37, 0.67] | 0.51 | 0.56 [0.13, 1.00] | 0.56 [0.13, 0.99] (n=58) |
| brick_pool | Qwen3.5-4B | 0.99 | 0.99 | 0.49 [0.35, 0.67] | 0.50 | 0.30 [-0.04, 0.63] | 0.30 [-0.04, 0.63] (n=58) |
| new_domains_pooled | GLM-4.7-Flash | 0.87 | 0.87 | 0.44 [0.34, 0.53] | 0.44 | 0.35 [0.17, 0.54] | 0.35 [0.18, 0.54] (n=99) |
| new_domains_pooled | gpt-oss-20b | 0.88 | 0.88 | 0.46 [0.34, 0.55] | 0.44 | -0.18 [-0.51, 0.13] | -0.19 [-0.51, 0.14] (n=99) |
| new_domains_pooled | Qwen3.8-Flash-Next | 0.93 | 0.93 | 0.60 [0.53, 0.70] | 0.59 | -0.05 [-0.27, 0.17] | -0.04 [-0.27, 0.18] (n=99) |
| new_domains_pooled | Qwen3-Next-80B | 0.91 | 0.91 | 0.53 [0.43, 0.63] | 0.53 | -0.01 [-0.24, 0.22] | -0.02 [-0.25, 0.23] (n=99) |
| new_domains_pooled | luna | 0.84 | 0.83 | 0.52 [0.39, 0.65] | 0.50 | -0.06 [-0.26, 0.13] | -0.07 [-0.27, 0.13] (n=99) |
| new_domains_pooled | Qwen3.8-27B | 1.00 | 1.00 | 0.57 [0.40, 0.70] | 0.57 | -0.36 [-0.64, -0.09] | -0.37 [-0.64, -0.08] (n=99) |
| new_domains_pooled | Qwen3.5-9B | 0.99 | 0.99 | 0.54 [0.43, 0.60] | 0.53 | -0.22 [-0.53, 0.09] | -0.23 [-0.54, 0.08] (n=99) |
| new_domains_pooled | Qwen3.5-4B | 0.99 | 0.99 | 0.55 [0.42, 0.65] | 0.54 | -0.01 [-0.22, 0.21] | -0.01 [-0.22, 0.21] (n=98) |

Caveats: judge scores, not human labels; unit means over repeats and banks; complete-case questions only (Q column); method-of-moments components, negatives truncated at 0; judges treated as fixed, so shares describe this panel; delta mixed equals the paper's delta where the question sets coincide (it is the same mean of per-question B-A), differing only through complete-case restriction; the rule of PLAN D.5 is an OR of significance and share, so a significant but tiny share (see the share column) is read 'supported' mechanically.
