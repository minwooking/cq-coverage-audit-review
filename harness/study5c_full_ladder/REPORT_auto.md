# Addendum 36 amendment C -- judge-score ladder A-F on three W3C domains; not human-labelled; exploratory, post hoc (addendum 36 amendment C)

Post hoc, exploratory. A, B, F scores reused from Study 5; C, D, E new. Independent set = GLM-4.7-Flash, gpt-oss-20b, Qwen3.8-Flash-Next (Qwen lineage, flagged); Qwen3-Next-80B is the extractor's model id (same family), shown separately. Equivalence margin +-0.50 (pre-fixed), +-0.30 shown in brackets only where it differs. The gateway judge (gpt-5.6-luna) returned HTTP 402 on its probe and was not scored.

## Cells (eligible, scored) per domain and variant

| domain | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| dcat | 28 | 26 | 27 | 27 | 27 | 27 |
| ssn | 42 | 41 | 41 | 41 | 41 | 41 |
| prov | 40 | 37 | 36 | 36 | 37 | 37 |

## Ladder: mean J per judge (n cells)

### GLM-4.7-Flash (independent)

| scope | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| dcat | 2.00 (28) | 2.15 (26) | 1.99 (27) | 2.06 (27) | 1.96 (27) | 1.98 (27) |
| ssn | 1.86 (42) | 2.36 (41) | 2.26 (41) | 2.18 (41) | 2.28 (41) | 2.24 (41) |
| prov | 2.01 (40) | 2.32 (37) | 2.33 (36) | 2.35 (36) | 2.33 (37) | 2.36 (37) |
| new_domains_pooled | 1.95 (110) | 2.29 (104) | 2.21 (104) | 2.21 (104) | 2.22 (105) | 2.22 (105) |

### gpt-oss-20b (independent)

| scope | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| dcat | 2.25 (28) | 1.95 (26) | 2.31 (27) | 2.20 (27) | 2.14 (27) | 2.09 (27) |
| ssn | 2.13 (42) | 1.85 (41) | 2.02 (41) | 2.02 (41) | 2.02 (41) | 1.99 (41) |
| prov | 1.94 (40) | 2.10 (37) | 1.93 (36) | 1.81 (36) | 1.80 (37) | 1.76 (37) |
| new_domains_pooled | 2.09 (110) | 1.96 (104) | 2.06 (104) | 1.99 (104) | 1.97 (105) | 1.93 (105) |

### Qwen3.8-Flash-Next (Qwen lineage (counted independent per brief))

| scope | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| dcat | 2.19 (28) | 2.09 (26) | 2.05 (27) | 2.05 (27) | 2.00 (27) | 2.00 (27) |
| ssn | 2.02 (42) | 1.77 (41) | 1.76 (41) | 1.75 (41) | 1.69 (41) | 1.63 (41) |
| prov | 2.16 (40) | 2.41 (37) | 2.25 (36) | 2.22 (36) | 2.00 (37) | 2.00 (37) |
| new_domains_pooled | 2.11 (110) | 2.08 (104) | 2.00 (104) | 1.99 (104) | 1.88 (105) | 1.85 (105) |

### Qwen3-Next-80B-A3B (extractor's model id) (same family)

| scope | A | B | C | D | E | F |
|---|---|---|---|---|---|---|
| dcat | 1.98 (28) | 1.74 (26) | 1.94 (27) | 1.89 (27) | 1.81 (27) | 1.86 (27) |
| ssn | 2.11 (42) | 1.99 (41) | 1.95 (41) | 2.00 (41) | 1.93 (41) | 1.88 (41) |
| prov | 1.88 (40) | 2.09 (37) | 2.11 (36) | 2.14 (36) | 2.17 (37) | 2.08 (37) |
| new_domains_pooled | 1.99 (110) | 1.96 (104) | 2.00 (104) | 2.02 (104) | 1.98 (105) | 1.95 (105) |

## Monotonicity along B -> C -> D -> E -> F (descriptive)

| judge | scope | means B..F (all eligible cells) | non-decreasing steps | monotone | common clusters (n) means B..F | monotone |
|---|---|---|---|---|---|---|
| GLM-4.7-Flash | dcat | 2.15 1.99 2.06 1.96 1.98 | 2/4 | False | 2.15 1.99 2.06 1.96 1.97 (26) | False |
| GLM-4.7-Flash | ssn | 2.36 2.26 2.18 2.28 2.24 | 1/4 | False | 2.36 2.26 2.18 2.28 2.24 (41) | False |
| GLM-4.7-Flash | prov | 2.32 2.33 2.35 2.33 2.36 | 3/4 | False | 2.32 2.33 2.35 2.34 2.37 (36) | False |
| GLM-4.7-Flash | new_domains_pooled | 2.29 2.21 2.21 2.22 2.22 | 2/4 | False | 2.29 2.22 2.21 2.22 2.22 (103) | False |
| gpt-oss-20b | dcat | 1.95 2.31 2.20 2.14 2.09 | 1/4 | False | 1.95 2.28 2.17 2.10 2.05 (26) | False |
| gpt-oss-20b | ssn | 1.85 2.02 2.02 2.02 1.99 | 2/4 | False | 1.85 2.02 2.02 2.02 1.99 (41) | False |
| gpt-oss-20b | prov | 2.10 1.93 1.81 1.80 1.76 | 0/4 | False | 2.07 1.93 1.81 1.81 1.76 (36) | False |
| gpt-oss-20b | new_domains_pooled | 1.96 2.06 1.99 1.97 1.93 | 1/4 | False | 1.95 2.06 1.98 1.96 1.93 (103) | False |
| Qwen3.8-Flash-Next | dcat | 2.09 2.05 2.05 2.00 2.00 | 2/4 | False | 2.09 2.08 2.08 2.04 2.04 (26) | False |
| Qwen3.8-Flash-Next | ssn | 1.77 1.76 1.75 1.69 1.63 | 0/4 | False | 1.77 1.76 1.75 1.69 1.63 (41) | False |
| Qwen3.8-Flash-Next | prov | 2.41 2.25 2.22 2.00 2.00 | 0/4 | False | 2.40 2.25 2.22 2.06 2.05 (36) | False |
| Qwen3.8-Flash-Next | new_domains_pooled | 2.08 2.00 1.99 1.88 1.85 | 0/4 | False | 2.07 2.01 2.00 1.91 1.88 (103) | False |
| Qwen3-Next-80B-A3B (extractor's model id) | dcat | 1.74 1.94 1.89 1.81 1.86 | 2/4 | False | 1.74 1.92 1.90 1.81 1.83 (26) | False |
| Qwen3-Next-80B-A3B (extractor's model id) | ssn | 1.99 1.95 2.00 1.93 1.88 | 1/4 | False | 1.99 1.95 2.00 1.93 1.88 (41) | False |
| Qwen3-Next-80B-A3B (extractor's model id) | prov | 2.09 2.11 2.14 2.17 2.08 | 3/4 | False | 2.06 2.11 2.14 2.19 2.10 (36) | False |
| Qwen3-Next-80B-A3B (extractor's model id) | new_domains_pooled | 1.96 2.00 2.02 1.98 1.95 | 2/4 | False | 1.95 2.00 2.02 1.99 1.94 (103) | False |
| panel_mean_all | dcat | 1.98 2.07 2.05 1.98 1.98 | 2/4 | False | 1.98 2.07 2.05 1.98 1.97 (26) | False |
| panel_mean_all | ssn | 1.99 2.00 1.99 1.98 1.93 | 1/4 | False | 1.99 2.00 1.99 1.98 1.93 (41) | False |
| panel_mean_all | prov | 2.23 2.16 2.13 2.08 2.05 | 0/4 | False | 2.22 2.16 2.13 2.10 2.07 (36) | False |
| panel_mean_all | new_domains_pooled | 2.07 2.07 2.05 2.01 1.99 | 0/4 | False | 2.07 2.07 2.05 2.02 1.99 (103) | False |
| panel_mean_without_q80 | dcat | 2.06 2.12 2.10 2.03 2.02 | 1/4 | False | 2.06 2.12 2.10 2.03 2.02 (26) | False |
| panel_mean_without_q80 | ssn | 1.99 2.01 1.98 1.99 1.95 | 2/4 | False | 1.99 2.01 1.98 1.99 1.95 (41) | False |
| panel_mean_without_q80 | prov | 2.28 2.17 2.13 2.05 2.04 | 0/4 | False | 2.27 2.17 2.13 2.07 2.06 (36) | False |
| panel_mean_without_q80 | new_domains_pooled | 2.11 2.09 2.06 2.02 2.00 | 0/4 | False | 2.10 2.09 2.06 2.03 2.01 (103) | False |

## Adjacent contrasts, per judge (n; delta [95% BCa]; decision)

### A -> B

| scope | GLM-4.7-Flash | gpt-oss-20b | Qwen3.8-Flash-Next | Qwen3-Next-80B-A3B (extractor's model id) | panel mean (descr.) |
|---|---|---|---|---|---|
| dcat | n=21; +0.143 [-0.11, +0.54]; equivalent (at 0.30: unresolved) | n=21; -0.397 [-1.06, +0.30]; unresolved | n=21; -0.095 [-0.67, +0.41]; unresolved | n=21; -0.286 [-0.68, +0.03]; unresolved | n=21; -0.159 [-0.49, +0.10]; equivalent (at 0.30: unresolved) |
| ssn | n=41; +0.520 [+0.24, +0.85]; resolved_B_gt_A | n=41; -0.317 [-0.79, +0.19]; unresolved | n=41; -0.293 [-0.65, +0.08]; unresolved | n=41; -0.163 [-0.49, +0.21]; equivalent (at 0.30: unresolved) | n=41; -0.065 [-0.31, +0.20]; equivalent |
| prov | n=37; +0.270 [+0.02, +0.59]; resolved_B_gt_A | n=37; +0.081 [-0.48, +0.59]; unresolved | n=37; +0.270 [-0.05, +0.57]; unresolved | n=37; +0.297 [-0.14, +0.77]; unresolved | n=37; +0.230 [-0.01, +0.50]; equivalent (at 0.30: unresolved) |
| new_domains_pooled | n=99; +0.347 [+0.18, +0.54]; resolved_B_gt_A | n=99; -0.185 [-0.51, +0.14]; equivalent (at 0.30: unresolved) | n=99; -0.040 [-0.27, +0.18]; equivalent | n=99; -0.017 [-0.25, +0.23]; equivalent | n=99; +0.025 [-0.13, +0.18]; equivalent |

### B -> C

| scope | GLM-4.7-Flash | gpt-oss-20b | Qwen3.8-Flash-Next | Qwen3-Next-80B-A3B (extractor's model id) | panel mean (descr.) |
|---|---|---|---|---|---|
| dcat | n=26; -0.167 [-0.33, -0.06]; resolved_B_gt_C | n=26; +0.333 [+0.09, +0.76]; resolved_C_gt_B | n=26; -0.013 [-0.15, +0.08]; equivalent | n=26; +0.179 [+0.03, +0.37]; resolved_C_gt_B | n=26; +0.083 [-0.01, +0.20]; equivalent |
| ssn | n=41; -0.098 [-0.24, +0.01]; equivalent | n=41; +0.179 [-0.11, +0.53]; equivalent (at 0.30: unresolved) | n=41; -0.016 [-0.15, +0.10]; equivalent | n=41; -0.041 [-0.12, +0.04]; equivalent | n=41; +0.006 [-0.08, +0.11]; equivalent |
| prov | n=36; +0.009 [-0.13, +0.16]; equivalent | n=36; -0.148 [-0.59, +0.22]; unresolved | n=36; -0.148 [-0.31, -0.01]; resolved_B_gt_C | n=36; +0.046 [-0.20, +0.31]; equivalent | n=36; -0.060 [-0.23, +0.10]; equivalent |
| new_domains_pooled | n=103; -0.078 [-0.16, -0.00]; resolved_B_gt_C | n=103; +0.104 [-0.10, +0.31]; equivalent | n=103; -0.061 [-0.15, +0.01]; equivalent | n=103; +0.045 [-0.06, +0.16]; equivalent | n=103; +0.003 [-0.07, +0.07]; equivalent |

### C -> D

| scope | GLM-4.7-Flash | gpt-oss-20b | Qwen3.8-Flash-Next | Qwen3-Next-80B-A3B (extractor's model id) | panel mean (descr.) |
|---|---|---|---|---|---|
| dcat | n=27; +0.074 [-0.02, +0.23]; equivalent | n=27; -0.111 [-0.52, +0.11]; equivalent (at 0.30: unresolved) | n=27; +0.000 [-0.09, +0.09]; equivalent | n=27; -0.049 [-0.22, +0.10]; equivalent | n=27; -0.022 [-0.13, +0.06]; equivalent |
| ssn | n=41; -0.081 [-0.28, +0.04]; equivalent | n=41; +0.000 [-0.28, +0.24]; equivalent | n=41; -0.008 [-0.17, +0.15]; equivalent | n=41; +0.049 [-0.11, +0.27]; equivalent | n=41; -0.008 [-0.17, +0.13]; equivalent |
| prov | n=36; +0.019 [-0.06, +0.11]; equivalent | n=36; -0.120 [-0.44, +0.25]; equivalent (at 0.30: unresolved) | n=36; -0.028 [-0.17, +0.10]; equivalent | n=36; +0.028 [-0.09, +0.17]; equivalent | n=36; -0.025 [-0.13, +0.09]; equivalent |
| new_domains_pooled | n=104; -0.006 [-0.09, +0.06]; equivalent | n=104; -0.071 [-0.25, +0.10]; equivalent | n=104; -0.013 [-0.10, +0.07]; equivalent | n=104; +0.016 [-0.07, +0.12]; equivalent | n=104; -0.018 [-0.09, +0.05]; equivalent |

### D -> E

| scope | GLM-4.7-Flash | gpt-oss-20b | Qwen3.8-Flash-Next | Qwen3-Next-80B-A3B (extractor's model id) | panel mean (descr.) |
|---|---|---|---|---|---|
| dcat | n=27; -0.099 [-0.27, +0.04]; equivalent | n=27; -0.062 [-0.36, +0.20]; equivalent | n=27; -0.049 [-0.15, +0.07]; equivalent | n=27; -0.074 [-0.33, +0.07]; equivalent | n=27; -0.071 [-0.17, +0.03]; equivalent |
| ssn | n=41; +0.098 [-0.02, +0.26]; equivalent | n=41; -0.008 [-0.33, +0.35]; equivalent | n=41; -0.057 [-0.21, +0.10]; equivalent | n=41; -0.073 [-0.24, +0.06]; equivalent | n=41; -0.010 [-0.14, +0.15]; equivalent |
| prov | n=36; -0.009 [-0.13, +0.12]; equivalent | n=36; +0.000 [-0.37, +0.44]; equivalent (at 0.30: unresolved) | n=36; -0.167 [-0.34, -0.02]; resolved_D_gt_E | n=36; +0.056 [-0.25, +0.31]; equivalent | n=36; -0.030 [-0.18, +0.13]; equivalent |
| new_domains_pooled | n=104; +0.010 [-0.07, +0.09]; equivalent | n=104; -0.019 [-0.22, +0.20]; equivalent | n=104; -0.093 [-0.18, -0.01]; resolved_D_gt_E | n=104; -0.029 [-0.16, +0.09]; equivalent | n=104; -0.033 [-0.11, +0.05]; equivalent |

### E -> F

| scope | GLM-4.7-Flash | gpt-oss-20b | Qwen3.8-Flash-Next | Qwen3-Next-80B-A3B (extractor's model id) | panel mean (descr.) |
|---|---|---|---|---|---|
| dcat | n=27; +0.012 [-0.06, +0.10]; equivalent | n=27; -0.049 [-0.25, +0.00]; equivalent | n=27; +0.000 [-0.06, +0.06]; equivalent | n=27; +0.049 [-0.05, +0.16]; equivalent | n=27; +0.003 [-0.06, +0.04]; equivalent |
| ssn | n=41; -0.033 [-0.11, +0.04]; equivalent | n=41; -0.024 [-0.15, +0.10]; equivalent | n=41; -0.065 [-0.15, +0.02]; equivalent | n=41; -0.049 [-0.13, +0.05]; equivalent | n=41; -0.043 [-0.08, -0.00]; resolved_E_gt_F |
| prov | n=37; +0.027 [-0.07, +0.13]; equivalent | n=37; -0.045 [-0.38, +0.27]; equivalent (at 0.30: unresolved) | n=37; +0.000 [-0.08, +0.08]; equivalent | n=37; -0.090 [-0.21, -0.00]; resolved_E_gt_F | n=37; -0.027 [-0.12, +0.06]; equivalent |
| new_domains_pooled | n=105; +0.000 [-0.05, +0.05]; equivalent | n=105; -0.038 [-0.17, +0.09]; equivalent | n=105; -0.025 [-0.07, +0.02]; equivalent | n=105; -0.038 [-0.10, +0.02]; equivalent | n=105; -0.025 [-0.07, +0.01]; equivalent |

## Contrasts against A (per judge)

### A -> C

| scope | GLM-4.7-Flash | gpt-oss-20b | Qwen3.8-Flash-Next | Qwen3-Next-80B-A3B (extractor's model id) |
|---|---|---|---|---|
| dcat | n=22; +0.045 [-0.18, +0.44]; equivalent (at 0.30: unresolved) | n=22; -0.030 [-0.73, +0.73]; unresolved | n=22; -0.121 [-0.65, +0.39]; unresolved | n=22; -0.045 [-0.38, +0.26]; equivalent (at 0.30: unresolved) |
| ssn | n=41; +0.423 [+0.15, +0.74]; resolved_C_gt_A | n=41; -0.138 [-0.58, +0.28]; unresolved | n=41; -0.309 [-0.68, +0.09]; unresolved | n=41; -0.203 [-0.57, +0.17]; unresolved |
| prov | n=36; +0.315 [+0.07, +0.64]; resolved_C_gt_A | n=36; -0.065 [-0.67, +0.54]; unresolved | n=36; +0.130 [-0.19, +0.48]; equivalent (at 0.30: unresolved) | n=36; +0.352 [-0.14, +0.84]; unresolved |
| new_domains_pooled | n=99; +0.300 [+0.14, +0.49]; resolved_C_gt_A | n=99; -0.088 [-0.41, +0.24]; equivalent (at 0.30: unresolved) | n=99; -0.108 [-0.34, +0.13]; equivalent (at 0.30: unresolved) | n=99; +0.034 [-0.21, +0.30]; equivalent |

### A -> D

| scope | GLM-4.7-Flash | gpt-oss-20b | Qwen3.8-Flash-Next | Qwen3-Next-80B-A3B (extractor's model id) |
|---|---|---|---|---|
| dcat | n=22; +0.061 [-0.21, +0.44]; equivalent (at 0.30: unresolved) | n=22; -0.121 [-0.68, +0.45]; unresolved | n=22; -0.136 [-0.67, +0.36]; unresolved | n=22; -0.152 [-0.44, +0.17]; equivalent (at 0.30: unresolved) |
| ssn | n=41; +0.341 [+0.03, +0.67]; resolved_D_gt_A | n=41; -0.138 [-0.59, +0.30]; unresolved | n=41; -0.317 [-0.71, +0.08]; unresolved | n=41; -0.154 [-0.56, +0.28]; equivalent (at 0.30: unresolved) |
| prov | n=36; +0.333 [+0.08, +0.66]; resolved_D_gt_A | n=36; -0.185 [-0.77, +0.37]; unresolved | n=36; +0.102 [-0.20, +0.43]; equivalent (at 0.30: unresolved) | n=36; +0.380 [-0.04, +0.85]; unresolved |
| new_domains_pooled | n=99; +0.276 [+0.11, +0.47]; resolved_D_gt_A | n=99; -0.152 [-0.46, +0.15]; equivalent (at 0.30: unresolved) | n=99; -0.125 [-0.36, +0.11]; equivalent (at 0.30: unresolved) | n=99; +0.040 [-0.20, +0.30]; equivalent |

### A -> E

| scope | GLM-4.7-Flash | gpt-oss-20b | Qwen3.8-Flash-Next | Qwen3-Next-80B-A3B (extractor's model id) |
|---|---|---|---|---|
| dcat | n=22; +0.030 [-0.24, +0.44]; equivalent (at 0.30: unresolved) | n=22; -0.136 [-0.82, +0.55]; unresolved | n=22; -0.121 [-0.68, +0.44]; unresolved | n=22; -0.212 [-0.67, +0.12]; unresolved |
| ssn | n=41; +0.439 [+0.16, +0.76]; resolved_E_gt_A | n=41; -0.146 [-0.58, +0.29]; unresolved | n=41; -0.374 [-0.76, +0.02]; unresolved | n=41; -0.228 [-0.58, +0.15]; unresolved |
| prov | n=36; +0.324 [+0.06, +0.68]; resolved_E_gt_A | n=36; -0.185 [-0.72, +0.37]; unresolved | n=36; -0.065 [-0.39, +0.26]; equivalent (at 0.30: unresolved) | n=36; +0.435 [-0.03, +0.87]; unresolved |
| new_domains_pooled | n=99; +0.306 [+0.14, +0.52]; resolved_E_gt_A | n=99; -0.158 [-0.46, +0.15]; equivalent (at 0.30: unresolved) | n=99; -0.205 [-0.43, +0.03]; equivalent (at 0.30: unresolved) | n=99; +0.017 [-0.23, +0.27]; equivalent |

### A -> F

| scope | GLM-4.7-Flash | gpt-oss-20b | Qwen3.8-Flash-Next | Qwen3-Next-80B-A3B (extractor's model id) |
|---|---|---|---|---|
| dcat | n=22; +0.076 [-0.18, +0.48]; equivalent (at 0.30: unresolved) | n=22; -0.136 [-0.82, +0.55]; unresolved | n=22; -0.136 [-0.70, +0.41]; unresolved | n=22; -0.121 [-0.61, +0.23]; unresolved |
| ssn | n=41; +0.407 [+0.15, +0.73]; resolved_F_gt_A | n=41; -0.171 [-0.60, +0.27]; unresolved | n=41; -0.439 [-0.82, -0.02]; resolved_A_gt_F | n=41; -0.276 [-0.61, +0.10]; unresolved |
| prov | n=36; +0.352 [+0.10, +0.69]; resolved_F_gt_A | n=36; -0.231 [-0.73, +0.31]; unresolved | n=36; -0.074 [-0.41, +0.27]; equivalent (at 0.30: unresolved) | n=36; +0.343 [-0.10, +0.76]; unresolved |
| new_domains_pooled | n=99; +0.313 [+0.15, +0.51]; resolved_F_gt_A | n=99; -0.185 [-0.48, +0.12]; equivalent (at 0.30: unresolved) | n=99; -0.239 [-0.48, -0.00]; resolved_A_gt_F | n=99; -0.017 [-0.25, +0.23]; equivalent |

## Panel summary (independent judges: second>first / first>second / equivalent / unresolved / underpowered; same-family q80 decision)

| contrast | scope | n judges | independent | q80 |
|---|---|---|---|---|
| A->B | dcat | 3 | 0 / 0 / 1 / 2 / 0 | unresolved |
| A->B | ssn | 3 | 1 / 0 / 0 / 2 / 0 | equivalent |
| A->B | prov | 3 | 1 / 0 / 0 / 2 / 0 | unresolved |
| A->B | new_domains_pooled | 3 | 1 / 0 / 2 / 0 / 0 | equivalent |
| B->C | dcat | 3 | 1 / 1 / 1 / 0 / 0 | second_gt_first |
| B->C | ssn | 3 | 0 / 0 / 3 / 0 / 0 | equivalent |
| B->C | prov | 3 | 0 / 1 / 1 / 1 / 0 | equivalent |
| B->C | new_domains_pooled | 3 | 0 / 1 / 2 / 0 / 0 | equivalent |
| C->D | dcat | 3 | 0 / 0 / 3 / 0 / 0 | equivalent |
| C->D | ssn | 3 | 0 / 0 / 3 / 0 / 0 | equivalent |
| C->D | prov | 3 | 0 / 0 / 3 / 0 / 0 | equivalent |
| C->D | new_domains_pooled | 3 | 0 / 0 / 3 / 0 / 0 | equivalent |
| D->E | dcat | 3 | 0 / 0 / 3 / 0 / 0 | equivalent |
| D->E | ssn | 3 | 0 / 0 / 3 / 0 / 0 | equivalent |
| D->E | prov | 3 | 0 / 1 / 2 / 0 / 0 | equivalent |
| D->E | new_domains_pooled | 3 | 0 / 1 / 2 / 0 / 0 | equivalent |
| E->F | dcat | 3 | 0 / 0 / 3 / 0 / 0 | equivalent |
| E->F | ssn | 3 | 0 / 0 / 3 / 0 / 0 | equivalent |
| E->F | prov | 3 | 0 / 0 / 3 / 0 / 0 | first_gt_second |
| E->F | new_domains_pooled | 3 | 0 / 0 / 3 / 0 / 0 | equivalent |
| A->C | dcat | 3 | 0 / 0 / 1 / 2 / 0 | equivalent |
| A->C | ssn | 3 | 1 / 0 / 0 / 2 / 0 | unresolved |
| A->C | prov | 3 | 1 / 0 / 1 / 1 / 0 | unresolved |
| A->C | new_domains_pooled | 3 | 1 / 0 / 2 / 0 / 0 | equivalent |
| A->D | dcat | 3 | 0 / 0 / 1 / 2 / 0 | equivalent |
| A->D | ssn | 3 | 1 / 0 / 0 / 2 / 0 | equivalent |
| A->D | prov | 3 | 1 / 0 / 1 / 1 / 0 | unresolved |
| A->D | new_domains_pooled | 3 | 1 / 0 / 2 / 0 / 0 | equivalent |
| A->E | dcat | 3 | 0 / 0 / 1 / 2 / 0 | unresolved |
| A->E | ssn | 3 | 1 / 0 / 0 / 2 / 0 | unresolved |
| A->E | prov | 3 | 1 / 0 / 1 / 1 / 0 | unresolved |
| A->E | new_domains_pooled | 3 | 1 / 0 / 2 / 0 / 0 | equivalent |
| A->F | dcat | 3 | 0 / 0 / 1 / 2 / 0 | unresolved |
| A->F | ssn | 3 | 1 / 1 / 0 / 1 / 0 | unresolved |
| A->F | prov | 3 | 1 / 0 / 1 / 1 / 0 | unresolved |
| A->F | new_domains_pooled | 3 | 1 / 1 / 1 / 0 / 0 | equivalent |

## Agreement on the C, D, E cells (QWK on per-cell median-low of repeats)

- glm~gptoss: n=313, QWK 0.303, exact 0.358
- glm~q38: n=313, QWK 0.531, exact 0.450
- glm~q80: n=313, QWK 0.519, exact 0.502
- gptoss~q38: n=313, QWK 0.407, exact 0.450
- gptoss~q80: n=313, QWK 0.486, exact 0.556
- q38~q80: n=313, QWK 0.637, exact 0.502

## Calls (C, D, E)

- glm: {"records": 939, "valid": 939, "invalid": 0, "prompt_tokens": 9840393, "completion_tokens": 118524, "model": "zai-org/GLM-4.7-Flash"}
- gptoss: {"records": 939, "valid": 938, "invalid": 1, "prompt_tokens": 9908421, "completion_tokens": 140582, "model": "openai/gpt-oss-20b"}
- q38: {"records": 939, "valid": 939, "invalid": 0, "prompt_tokens": 10175553, "completion_tokens": 147901, "model": "Qwen/Qwen3.8-Flash-Next"}
- q80: {"records": 939, "valid": 939, "invalid": 0, "prompt_tokens": 10107999, "completion_tokens": 126639, "model": "Qwen/Qwen3-Next-80B-A3B-Instruct-FP8"}
