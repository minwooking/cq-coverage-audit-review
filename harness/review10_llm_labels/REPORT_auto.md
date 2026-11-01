# Addendum 30 -- automatic tables (results.json)

AI-generated; post hoc. Intervals: question-clustered BCa 95%, B = 10,000, seed 20260913. No per-cell human label appears here.

Human-human kappa on all 188 cells: 0.595 [0.268, 0.833], agreement 83.0% [69.0, 92.5].

## Verdict (PLAN 30.8)

**supports the paper's current conclusion**

| comparison | consistent cells | LB of kappa(LLM, human) | human-human kappa - 0.10 (same cells) | close |
|---|---|---|---|---|
| glm:AH | 38 | 0.0 | 0.6745 | False |
| glm:R2 | 38 | 0.0 | 0.6745 | False |
| gptoss:AH | 101 | 0.0 | 0.5984 | False |
| gptoss:R2 | 101 | 0.0 | 0.5984 | False |

## glm

Evaluated cells 182 (context skip 6, partial or missing 0); slots ok 4521 / invalid 29, parse rate 0.9936; span re-check mismatches 0.

| rule | consistent / evaluated | coverage | S=1 share of consistent labels | kappa AH | agreement AH | kappa R2 | agreement R2 | human-human kappa (same cells) | human-human kappa (complement) |
|---|---|---|---|---|---|---|---|---|---|
| R25 | 38 / 182 | 20.9% [12.6, 31.1] | 2.6% [0.0, 16.7] | 0.028 [0.000, 0.273] | 36.8% [14.9, 65.8] | 0.035 [0.000, 0.305] | 42.1% [17.5, 69.2] | 0.774 [0.167, 1.000] | 0.508 [0.143, 0.813] |
| R25U | 9 / 182 | 5.0% [1.7, 11.1] | 0.0% [0.0, 0.0] | 0.000 [-0.000, 0.000] | 44.4% [0.0, 92.3] | 0.000 [-0.000, 0.000] | 44.4% [0.0, 92.3] | 1.000 [0.000, 1.000] | 0.547 [0.196, 0.820] |

pi-hat on the R25-consistent cells: LLM 68.4% [36.6, 87.2], AH 5.3% [0.0, 23.8], R2 13.2% [0.0, 39.3]; LLM minus AH 0.632 [0.342, 0.851], LLM minus R2 0.553 [0.286, 0.800].

Unfiltered majority of the 25 labels (all evaluated cells): kappa AH 0.045 [-0.044, 0.171], kappa R2 -0.013 [-0.162, 0.131], S=1 share 19.8% [11.3, 32.5], pi-hat 56.0% [42.2, 68.8].

| persona | S=1 share | kappa AH | kappa R2 | pi-hat | alpha across 5 seeds |
|---|---|---|---|---|---|
| domain | 24.9% [16.1, 36.6] | 0.139 [0.046, 0.285] | 0.078 [-0.069, 0.236] | 51.9% [39.3, 63.9] | 0.113 [0.045, 0.190] |
| ontology | 21.4% [14.3, 31.5] | 0.058 [-0.012, 0.175] | 0.004 [-0.114, 0.137] | 55.5% [42.6, 66.8] | 0.149 [0.082, 0.223] |
| auditor | 18.9% [11.9, 30.0] | 0.036 [-0.038, 0.151] | -0.026 [-0.164, 0.097] | 57.8% [44.6, 69.6] | 0.107 [0.048, 0.182] |
| kgqa | 22.5% [14.3, 34.2] | 0.050 [-0.043, 0.176] | -0.003 [-0.185, 0.131] | 54.4% [41.0, 66.8] | 0.172 [0.100, 0.266] |
| generalist | 19.6% [12.2, 29.8] | 0.041 [-0.040, 0.139] | -0.037 [-0.182, 0.073] | 57.5% [44.2, 69.7] | 0.134 [0.071, 0.212] |

alpha across all 25 slots 0.202 [0.158, 0.258]; alpha between persona labels 0.571 [0.466, 0.698]; mean pairwise kappa between persona labels 0.572 [0.468, 0.698].

Sensitivity S_raw (R25): consistent 6 / 182.

## gptoss

Evaluated cells 182 (context skip 6, partial or missing 0); slots ok 4550 / invalid 0, parse rate 1.0; span re-check mismatches 0.

| rule | consistent / evaluated | coverage | S=1 share of consistent labels | kappa AH | agreement AH | kappa R2 | agreement R2 | human-human kappa (same cells) | human-human kappa (complement) |
|---|---|---|---|---|---|---|---|---|---|
| R25 | 101 / 182 | 55.5% [40.9, 69.4] | 2.0% [0.0, 6.9] | 0.024 [0.000, 0.108] | 39.6% [20.9, 60.4] | 0.020 [0.000, 0.097] | 35.6% [17.6, 57.9] | 0.698 [0.252, 0.921] | 0.336 [0.000, 0.903] |
| R25U | 70 / 182 | 38.5% [25.9, 52.5] | 1.4% [0.0, 9.8] | 0.019 [-0.000, 0.181] | 41.4% [19.7, 65.6] | 0.018 [0.000, 0.186] | 40.0% [18.1, 64.7] | 0.671 [0.141, 0.945] | 0.466 [0.073, 0.861] |

pi-hat on the R25-consistent cells: LLM 59.4% [38.7, 76.7], AH 10.9% [2.0, 28.6], R2 6.9% [1.0, 21.2]; LLM minus AH 0.485 [0.293, 0.677], LLM minus R2 0.525 [0.320, 0.722].

Unfiltered majority of the 25 labels (all evaluated cells): kappa AH 0.110 [0.047, 0.233], kappa R2 0.048 [-0.087, 0.175], S=1 share 15.4% [8.3, 25.9], pi-hat 58.2% [44.5, 70.4].

| persona | S=1 share | kappa AH | kappa R2 | pi-hat | alpha across 5 seeds |
|---|---|---|---|---|---|
| domain | 15.9% [9.0, 26.5] | 0.082 [0.024, 0.194] | -0.034 [-0.210, 0.069] | 58.2% [44.9, 70.1] | 0.369 [0.264, 0.513] |
| ontology | 19.8% [12.3, 30.5] | 0.129 [0.054, 0.262] | 0.041 [-0.131, 0.170] | 55.5% [42.2, 67.8] | 0.382 [0.303, 0.473] |
| auditor | 15.9% [9.0, 25.4] | 0.098 [0.038, 0.210] | 0.019 [-0.089, 0.142] | 57.7% [44.2, 69.9] | 0.370 [0.274, 0.462] |
| kgqa | 19.8% [11.1, 31.7] | 0.146 [0.062, 0.289] | -0.013 [-0.208, 0.139] | 54.4% [41.1, 67.4] | 0.438 [0.328, 0.544] |
| generalist | 18.1% [10.8, 28.3] | 0.132 [0.060, 0.264] | 0.059 [-0.076, 0.194] | 56.0% [43.2, 67.7] | 0.398 [0.281, 0.514] |

alpha across all 25 slots 0.385 [0.311, 0.466]; alpha between persona labels 0.526 [0.395, 0.666]; mean pairwise kappa between persona labels 0.525 [0.394, 0.668].

Sensitivity S_raw (R25): consistent 107 / 182.

## qwen

Evaluated cells 183 (context skip 5, partial or missing 0); slots ok 4530 / invalid 45, parse rate 0.9902; span re-check mismatches 0.

| rule | consistent / evaluated | coverage | S=1 share of consistent labels | kappa AH | agreement AH | kappa R2 | agreement R2 | human-human kappa (same cells) | human-human kappa (complement) |
|---|---|---|---|---|---|---|---|---|---|
| R25 | 139 / 183 | 76.0% [63.6, 86.1] | 18.7% [8.7, 34.9] | 0.134 [0.043, 0.342] | 42.4% [25.5, 61.2] | 0.163 [0.030, 0.399] | 49.6% [32.8, 67.2] | 0.619 [0.238, 0.874] | 0.396 [-0.149, 1.000] |
| R25U | 118 / 183 | 64.5% [50.8, 77.0] | 13.6% [5.5, 30.8] | 0.110 [0.033, 0.322] | 40.7% [23.1, 60.4] | 0.144 [0.049, 0.383] | 46.6% [28.6, 65.8] | 0.699 [0.259, 0.928] | 0.286 [-0.149, 0.878] |

pi-hat on the R25-consistent cells: LLM 49.6% [32.2, 66.4], AH 2.9% [0.0, 15.6], R2 12.2% [4.4, 27.6]; LLM minus AH 0.468 [0.296, 0.639], LLM minus R2 0.374 [0.218, 0.547].

Unfiltered majority of the 25 labels (all evaluated cells): kappa AH 0.063 [-0.111, 0.246], kappa R2 0.091 [-0.143, 0.288], S=1 share 27.9% [15.7, 43.3], pi-hat 47.5% [32.4, 62.3].

| persona | S=1 share | kappa AH | kappa R2 | pi-hat | alpha across 5 seeds |
|---|---|---|---|---|---|
| domain | 27.3% [16.2, 41.5] | 0.112 [-0.010, 0.293] | 0.141 [-0.034, 0.333] | 47.0% [33.3, 60.8] | 0.756 [0.651, 0.850] |
| ontology | 25.1% [14.2, 40.1] | 0.128 [0.024, 0.327] | 0.117 [-0.090, 0.294] | 50.3% [35.2, 64.7] | 0.784 [0.670, 0.871] |
| auditor | 24.0% [13.3, 39.0] | 0.118 [0.008, 0.318] | 0.086 [-0.120, 0.269] | 50.8% [35.8, 64.8] | 0.743 [0.621, 0.856] |
| kgqa | 28.4% [16.3, 43.6] | 0.050 [-0.134, 0.234] | 0.117 [-0.091, 0.323] | 47.0% [32.2, 61.5] | 0.813 [0.723, 0.896] |
| generalist | 26.5% [15.0, 41.3] | 0.088 [-0.056, 0.267] | 0.096 [-0.126, 0.283] | 48.1% [33.5, 62.5] | 0.778 [0.699, 0.867] |

alpha across all 25 slots 0.755 [0.655, 0.853]; alpha between persona labels 0.819 [0.683, 0.917]; mean pairwise kappa between persona labels 0.820 [0.682, 0.918].

Sensitivity S_raw (R25): consistent 145 / 183.

## RX_primary (models glm, gptoss)

consensus 25 / 182 (13.7% [7.2, 23.8]).

kappa AH 0.000 [-0.000, 0.000], kappa R2 0.000 [-0.000, 0.000], human-human kappa on the same cells 0.920 [0.075, 1.000].

## RX_all (models glm, gptoss, qwen)

consensus 91 / 182 (50.0% [35.5, 64.4]).

kappa AH 0.023 [0.000, 0.125], kappa R2 0.028 [0.000, 0.146], human-human kappa on the same cells 0.715 [0.250, 1.000].

## Tier 2a: remaining holdout cells (36-question bank) (28 cells) -- NO HUMAN REFERENCE

* glm: evaluated 28/28; R25 consistent 8 (28.6% [9.1, 55.6]), label 1: 0, label 0: 8; R25U 3 (10.7% [2.3, 28.6]); S=1 share of the unfiltered majority 28.6% [7.7, 64.6]
* gptoss: evaluated 28/28; R25 consistent 20 (71.4% [45.5, 87.0]), label 1: 1, label 0: 19; R25U 16 (57.1% [27.8, 78.6]); S=1 share of the unfiltered majority 10.7% [3.0, 22.2]
* qwen: evaluated 28/28; R25 consistent 22 (78.6% [61.5, 88.9]), label 1: 5, label 0: 17; R25U 20 (71.4% [54.5, 84.6]); S=1 share of the unfiltered majority 25.0% [5.6, 60.6]
* RX-primary (glm + gptoss): consensus 7/28 (25.0% [9.1, 55.6])

| model | variant | evaluated | R25 consistent (cov.) | label 1 / label 0 | R25U | S=1 share, unfiltered majority |
|---|---|---|---|---|---|---|
| glm | A | 13/13 | 7 (53.8% [23.1, 76.9]) | 0 / 7 | 3 | 30.8% [7.7, 61.5] |
| glm | B | 3/3 | 0 (0.0% [0.0, 0.0]) | 0 / 0 | 0 | 33.3% [0.0, 100.0] |
| glm | C | 3/3 | 1 (33.3% [0.0, 100.0]) | 0 / 1 | 0 | 33.3% [0.0, 100.0] |
| glm | D | 3/3 | 0 (0.0% [0.0, 0.0]) | 0 / 0 | 0 | 0.0% [0.0, 0.0] |
| glm | E | 3/3 | 0 (0.0% [0.0, 0.0]) | 0 / 0 | 0 | 33.3% [0.0, 100.0] |
| glm | F | 3/3 | 0 (0.0% [0.0, 0.0]) | 0 / 0 | 0 | 33.3% [0.0, 100.0] |
| gptoss | A | 13/13 | 9 (69.2% [38.5, 92.3]) | 1 / 8 | 6 | 23.1% [7.7, 53.8] |
| gptoss | B | 3/3 | 2 (66.7% [0.0, 100.0]) | 0 / 2 | 2 | 0.0% [0.0, 0.0] |
| gptoss | C | 3/3 | 2 (66.7% [0.0, 100.0]) | 0 / 2 | 2 | 0.0% [0.0, 0.0] |
| gptoss | D | 3/3 | 3 (100.0% [100.0, 100.0]) | 0 / 3 | 2 | 0.0% [0.0, 0.0] |
| gptoss | E | 3/3 | 2 (66.7% [0.0, 100.0]) | 0 / 2 | 2 | 0.0% [0.0, 0.0] |
| gptoss | F | 3/3 | 2 (66.7% [0.0, 100.0]) | 0 / 2 | 2 | 0.0% [0.0, 0.0] |
| qwen | A | 13/13 | 10 (76.9% [46.2, 92.3]) | 1 / 9 | 9 | 15.4% [0.0, 46.2] |
| qwen | B | 3/3 | 2 (66.7% [0.0, 100.0]) | 0 / 2 | 2 | 33.3% [0.0, 100.0] |
| qwen | C | 3/3 | 2 (66.7% [0.0, 100.0]) | 1 / 1 | 2 | 33.3% [0.0, 100.0] |
| qwen | D | 3/3 | 2 (66.7% [0.0, 100.0]) | 1 / 1 | 2 | 33.3% [0.0, 100.0] |
| qwen | E | 3/3 | 3 (100.0% [100.0, 100.0]) | 1 / 2 | 3 | 33.3% [0.0, 100.0] |
| qwen | F | 3/3 | 3 (100.0% [100.0, 100.0]) | 1 / 2 | 2 | 33.3% [0.0, 100.0] |

## Tier 2b: natural-documentation cells (72 cells) -- NO HUMAN REFERENCE

* glm: evaluated 72/72; R25 consistent 11 (15.3% [8.3, 26.4]), label 1: 1, label 0: 10; R25U 4 (5.6% [1.4, 12.5]); S=1 share of the unfiltered majority 29.2% [18.1, 43.1]; pi-hat under the consistent LLM label judge_gptoss 0.0% [0.0, 0.0] (n=11), judge_glm 27.3% [7.1, 66.7] (n=11)
* gptoss: evaluated 72/72; R25 consistent 54 (75.0% [62.5, 84.7]), label 1: 4, label 0: 50; R25U 45 (62.5% [48.6, 75.0]); S=1 share of the unfiltered majority 12.5% [5.6, 23.6]; pi-hat under the consistent LLM label judge_gptoss 9.3% [3.5, 23.6] (n=54), judge_glm 44.4% [29.4, 61.1] (n=54)
* qwen: evaluated 72/72; R25 consistent 65 (90.3% [81.9, 95.8]), label 1: 6, label 0: 59; R25U 60 (83.3% [75.0, 90.3]); S=1 share of the unfiltered majority 9.7% [4.2, 20.8]; pi-hat under the consistent LLM label judge_gptoss 18.5% [10.4, 30.0] (n=65), judge_glm 46.2% [32.9, 59.7] (n=65)
* RX-primary (glm + gptoss): consensus 10/72 (13.9% [6.9, 25.0])

| model | variant | evaluated | R25 consistent (cov.) | label 1 / label 0 | R25U | S=1 share, unfiltered majority |
|---|---|---|---|---|---|---|
| glm | A | 36/36 | 7 (19.4% [8.3, 36.1]) | 1 / 6 | 4 | 33.3% [19.4, 50.0] |
| glm | B | 36/36 | 4 (11.1% [2.8, 25.0]) | 0 / 4 | 0 | 25.0% [13.9, 41.7] |
| gptoss | A | 36/36 | 29 (80.6% [63.9, 91.7]) | 3 / 26 | 25 | 19.4% [8.3, 33.3] |
| gptoss | B | 36/36 | 25 (69.4% [52.8, 83.3]) | 1 / 24 | 20 | 5.6% [0.0, 19.4] |
| qwen | A | 36/36 | 34 (94.4% [83.3, 100.0]) | 6 / 28 | 32 | 16.7% [5.6, 30.6] |
| qwen | B | 36/36 | 31 (86.1% [72.2, 94.4]) | 0 / 31 | 28 | 2.8% [0.0, 15.6] |

## Tier 3a: holdout paraphrases (213 cells) -- NO HUMAN REFERENCE

* glm: evaluated 213/213; R25 consistent 45 (21.1% [13.2, 32.1]), label 1: 1, label 0: 44; R25U 19 (8.9% [4.2, 16.3]); S=1 share of the unfiltered majority 15.0% [9.7, 22.8]
* gptoss: evaluated 213/213; R25 consistent 130 (61.0% [48.8, 71.1]), label 1: 2, label 0: 128; R25U 89 (41.8% [30.0, 53.8]); S=1 share of the unfiltered majority 14.1% [8.5, 23.7]
* qwen: evaluated 60/213; R25 consistent 55 (91.7% [73.6, 98.3]), label 1: 7, label 0: 48; R25U 50 (83.3% [66.7, 93.4]); S=1 share of the unfiltered majority 13.3% [3.5, 31.7]
* RX-primary (glm + gptoss): consensus 38/213 (17.8% [10.3, 28.6])

| model | variant | evaluated | R25 consistent (cov.) | label 1 / label 0 | R25U | S=1 share, unfiltered majority |
|---|---|---|---|---|---|---|
| glm | A | 33/33 | 6 (18.2% [9.1, 33.3]) | 1 / 5 | 2 | 30.3% [15.2, 48.5] |
| glm | B | 36/36 | 8 (22.2% [11.1, 38.9]) | 0 / 8 | 1 | 8.3% [2.8, 22.2] |
| glm | C | 36/36 | 3 (8.3% [2.8, 22.2]) | 0 / 3 | 2 | 11.1% [2.8, 25.0] |
| glm | D | 36/36 | 6 (16.7% [5.6, 30.6]) | 0 / 6 | 3 | 11.1% [2.8, 25.0] |
| glm | E | 36/36 | 11 (30.6% [16.7, 47.2]) | 0 / 11 | 6 | 13.9% [5.6, 27.8] |
| glm | F | 36/36 | 11 (30.6% [16.7, 47.2]) | 0 / 11 | 5 | 16.7% [5.6, 33.3] |
| gptoss | A | 33/33 | 14 (42.4% [27.3, 60.6]) | 2 / 12 | 12 | 33.3% [18.2, 51.5] |
| gptoss | B | 36/36 | 23 (63.9% [47.2, 77.8]) | 0 / 23 | 15 | 5.6% [0.0, 16.7] |
| gptoss | C | 36/36 | 19 (52.8% [36.1, 69.4]) | 0 / 19 | 16 | 8.3% [2.8, 22.2] |
| gptoss | D | 36/36 | 25 (69.4% [52.8, 83.3]) | 0 / 25 | 16 | 13.9% [5.6, 27.8] |
| gptoss | E | 36/36 | 24 (66.7% [50.0, 80.6]) | 0 / 24 | 15 | 11.1% [2.8, 25.0] |
| gptoss | F | 36/36 | 25 (69.4% [52.8, 83.3]) | 0 / 25 | 15 | 13.9% [5.6, 27.8] |
| qwen | A | 6/33 | 6 (100.0% [100.0, 100.0]) | 1 / 5 | 6 | 16.7% [0.0, 66.7] |
| qwen | B | 12/36 | 11 (91.7% [58.3, 100.0]) | 3 / 8 | 8 | 25.0% [8.3, 58.3] |
| qwen | C | 8/36 | 7 (87.5% [50.0, 100.0]) | 0 / 7 | 7 | 0.0% [0.0, 0.0] |
| qwen | D | 10/36 | 9 (90.0% [50.0, 100.0]) | 0 / 9 | 8 | 10.0% [0.0, 50.0] |
| qwen | E | 14/36 | 13 (92.9% [64.3, 100.0]) | 3 / 10 | 12 | 21.4% [7.1, 50.0] |
| qwen | F | 10/36 | 9 (90.0% [60.0, 100.0]) | 0 / 9 | 9 | 0.0% [0.0, 0.0] |

## Tier 3b: holdout extra questions (v2) (140 cells) -- NO HUMAN REFERENCE

* glm: evaluated 140/140; R25 consistent 17 (12.1% [5.7, 24.6]), label 1: 0, label 0: 17; R25U 10 (7.1% [3.5, 14.6]); S=1 share of the unfiltered majority 26.1% [15.8, 39.6]
* gptoss: evaluated 140/140; R25 consistent 97 (69.3% [53.5, 81.8]), label 1: 1, label 0: 96; R25U 78 (55.7% [39.7, 70.8]); S=1 share of the unfiltered majority 7.9% [3.5, 21.4]
* RX-primary (glm + gptoss): consensus 14/140 (10.0% [4.3, 22.7])

| model | variant | evaluated | R25 consistent (cov.) | label 1 / label 0 | R25U | S=1 share, unfiltered majority |
|---|---|---|---|---|---|---|
| glm | A | 23/23 | 3 (13.0% [4.3, 34.8]) | 0 / 3 | 3 | 30.4% [13.0, 52.2] |
| glm | B | 23/23 | 2 (8.7% [0.0, 26.1]) | 0 / 2 | 1 | 13.6% [4.5, 36.4] |
| glm | C | 23/23 | 2 (8.7% [0.0, 26.1]) | 0 / 2 | 1 | 21.7% [8.7, 43.5] |
| glm | D | 23/23 | 3 (13.0% [4.3, 34.8]) | 0 / 3 | 1 | 27.3% [13.6, 50.0] |
| glm | E | 24/24 | 4 (16.7% [4.2, 37.5]) | 0 / 4 | 3 | 29.2% [12.5, 50.0] |
| glm | F | 24/24 | 3 (12.5% [4.2, 33.3]) | 0 / 3 | 1 | 33.3% [16.7, 54.2] |
| gptoss | A | 23/23 | 15 (65.2% [43.5, 82.6]) | 1 / 14 | 12 | 17.4% [4.3, 39.1] |
| gptoss | B | 23/23 | 15 (65.2% [43.5, 82.6]) | 0 / 15 | 10 | 8.7% [0.0, 26.1] |
| gptoss | C | 23/23 | 16 (69.6% [47.8, 87.0]) | 0 / 16 | 14 | 4.3% [0.0, 21.7] |
| gptoss | D | 23/23 | 17 (73.9% [52.2, 87.0]) | 0 / 17 | 13 | 8.7% [0.0, 26.1] |
| gptoss | E | 24/24 | 18 (75.0% [54.2, 87.5]) | 0 / 18 | 15 | 4.2% [0.0, 20.8] |
| gptoss | F | 24/24 | 16 (66.7% [45.8, 83.3]) | 0 / 16 | 14 | 4.2% [0.0, 20.8] |

## Tier 3c: development bank (106 cells) -- NO HUMAN REFERENCE

* glm: evaluated 106/106; R25 consistent 15 (14.1% [6.5, 31.8]), label 1: 0, label 0: 15; R25U 6 (5.7% [1.9, 14.9]); S=1 share of the unfiltered majority 21.7% [11.2, 38.3]
* gptoss: evaluated 106/106; R25 consistent 50 (47.2% [32.0, 64.5]), label 1: 3, label 0: 47; R25U 30 (28.3% [17.1, 46.2]); S=1 share of the unfiltered majority 17.9% [9.5, 32.1]
* qwen: evaluated 106/106; R25 consistent 62 (58.5% [42.6, 73.3]), label 1: 17, label 0: 45; R25U 48 (45.3% [31.1, 63.0]); S=1 share of the unfiltered majority 50.0% [32.7, 67.3]
* RX-primary (glm + gptoss): consensus 12/106 (11.3% [3.8, 29.9])

| model | variant | evaluated | R25 consistent (cov.) | label 1 / label 0 | R25U | S=1 share, unfiltered majority |
|---|---|---|---|---|---|---|
| glm | A | 16/16 | 4 (25.0% [6.2, 50.0]) | 0 / 4 | 2 | 18.8% [6.2, 43.8] |
| glm | B | 18/18 | 2 (11.1% [0.0, 33.3]) | 0 / 2 | 1 | 16.7% [5.6, 38.9] |
| glm | C | 18/18 | 3 (16.7% [5.6, 38.9]) | 0 / 3 | 1 | 16.7% [5.6, 38.9] |
| glm | D | 18/18 | 3 (16.7% [5.6, 38.9]) | 0 / 3 | 1 | 11.1% [0.0, 33.3] |
| glm | E | 18/18 | 1 (5.6% [0.0, 27.8]) | 0 / 1 | 0 | 33.3% [16.7, 55.6] |
| glm | F | 18/18 | 2 (11.1% [0.0, 33.3]) | 0 / 2 | 1 | 33.3% [16.7, 55.6] |
| gptoss | A | 16/16 | 13 (81.2% [56.2, 93.8]) | 1 / 12 | 8 | 18.8% [6.2, 43.8] |
| gptoss | B | 18/18 | 6 (33.3% [16.7, 55.6]) | 0 / 6 | 4 | 16.7% [5.6, 38.9] |
| gptoss | C | 18/18 | 9 (50.0% [27.8, 72.2]) | 0 / 9 | 4 | 5.6% [0.0, 27.8] |
| gptoss | D | 18/18 | 6 (33.3% [16.7, 55.6]) | 0 / 6 | 4 | 16.7% [5.6, 38.9] |
| gptoss | E | 18/18 | 9 (50.0% [27.8, 72.2]) | 1 / 8 | 4 | 22.2% [5.6, 44.4] |
| gptoss | F | 18/18 | 7 (38.9% [16.7, 61.1]) | 1 / 6 | 6 | 27.8% [11.1, 50.0] |
| qwen | A | 16/16 | 14 (87.5% [62.5, 100.0]) | 2 / 12 | 13 | 18.8% [6.2, 43.8] |
| qwen | B | 18/18 | 8 (44.4% [22.2, 66.7]) | 3 / 5 | 7 | 61.1% [38.9, 83.3] |
| qwen | C | 18/18 | 10 (55.6% [33.3, 77.8]) | 3 / 7 | 8 | 50.0% [27.8, 72.2] |
| qwen | D | 18/18 | 10 (55.6% [33.3, 77.8]) | 3 / 7 | 6 | 55.6% [33.3, 77.8] |
| qwen | E | 18/18 | 10 (55.6% [33.3, 77.8]) | 3 / 7 | 7 | 55.6% [33.3, 77.8] |
| qwen | F | 18/18 | 10 (55.6% [33.3, 77.8]) | 3 / 7 | 7 | 55.6% [33.3, 77.8] |

## Tier 3d: second domain (internal; aggregate only) (28 cells) -- NO HUMAN REFERENCE

* glm: evaluated 28/28; R25 consistent 4 (14.3% [3.3, 34.6]), label 1: 0, label 0: 4; R25U 2 (7.1% [0.0, 22.2]); S=1 share of the unfiltered majority 7.4% [0.0, 23.9]
* gptoss: evaluated 28/28; R25 consistent 17 (60.7% [36.7, 82.8]), label 1: 0, label 0: 17; R25U 15 (53.6% [24.1, 79.3]); S=1 share of the unfiltered majority 17.9% [3.7, 40.7]
* qwen: evaluated 28/28; R25 consistent 26 (92.9% [77.8, 100.0]), label 1: 4, label 0: 22; R25U 24 (85.7% [61.5, 96.5]); S=1 share of the unfiltered majority 17.9% [6.5, 36.7]
* RX-primary (glm + gptoss): consensus 2/28 (7.1% [0.0, 32.2])

| model | variant | evaluated | R25 consistent (cov.) | label 1 / label 0 | R25U | S=1 share, unfiltered majority |
|---|---|---|---|---|---|---|
| glm | A | 14/14 | 4 (28.6% [7.1, 62.5]) | 0 / 4 | 2 | 15.4% [0.0, 41.7] |
| glm | B | 12/12 | 0 (0.0% [0.0, 0.0]) | 0 / 0 | 0 | 0.0% [0.0, 0.0] |
| glm | C | 2/2 | 0 (0.0% [0.0, 0.0]) | 0 / 0 | 0 | 0.0% [0.0, 0.0] |
| gptoss | A | 14/14 | 6 (42.9% [15.4, 75.0]) | 0 / 6 | 6 | 21.4% [0.0, 58.8] |
| gptoss | B | 12/12 | 9 (75.0% [46.2, 91.7]) | 0 / 9 | 7 | 16.7% [0.0, 45.5] |
| gptoss | C | 2/2 | 2 (100.0% [100.0, 100.0]) | 0 / 2 | 2 | 0.0% [0.0, 0.0] |
| qwen | A | 14/14 | 13 (92.9% [65.7, 100.0]) | 4 / 9 | 11 | 35.7% [13.3, 69.2] |
| qwen | B | 12/12 | 11 (91.7% [54.5, 100.0]) | 0 / 11 | 11 | 0.0% [0.0, 0.0] |
| qwen | C | 2/2 | 2 (100.0% [100.0, 100.0]) | 0 / 2 | 2 | 0.0% [0.0, 0.0] |

## Tier 3e: expansion draft (unfrozen) (504 cells) -- NO HUMAN REFERENCE

* glm: evaluated 504/504; R25 consistent 72 (14.3% [10.1, 20.0]), label 1: 5, label 0: 67; R25U 30 (5.9% [3.8, 9.7]); S=1 share of the unfiltered majority 25.0% [19.4, 31.4]
* gptoss: evaluated 504/504; R25 consistent 284 (56.4% [47.6, 64.9]), label 1: 12, label 0: 272; R25U 216 (42.9% [34.6, 51.4]); S=1 share of the unfiltered majority 17.5% [12.9, 23.4]
* RX-primary (glm + gptoss): consensus 59/504 (11.7% [7.7, 17.5])

| model | variant | evaluated | R25 consistent (cov.) | label 1 / label 0 | R25U | S=1 share, unfiltered majority |
|---|---|---|---|---|---|---|
| glm | A | 84/84 | 18 (21.4% [13.1, 30.9]) | 5 / 13 | 12 | 41.7% [32.1, 52.4] |
| glm | B | 84/84 | 11 (13.1% [7.1, 21.4]) | 0 / 11 | 3 | 20.2% [13.1, 29.8] |
| glm | C | 84/84 | 9 (10.7% [5.9, 19.1]) | 0 / 9 | 0 | 22.6% [14.3, 32.1] |
| glm | D | 84/84 | 8 (9.5% [4.8, 17.9]) | 0 / 8 | 2 | 26.2% [17.9, 36.9] |
| glm | E | 84/84 | 13 (15.5% [8.3, 25.0]) | 0 / 13 | 7 | 22.6% [14.3, 32.1] |
| glm | F | 84/84 | 13 (15.5% [8.3, 25.0]) | 0 / 13 | 6 | 16.7% [9.5, 26.2] |
| gptoss | A | 84/84 | 52 (61.9% [51.2, 71.4]) | 10 / 42 | 42 | 35.7% [26.2, 46.4] |
| gptoss | B | 84/84 | 47 (56.0% [45.2, 66.7]) | 1 / 46 | 37 | 16.7% [9.5, 26.2] |
| gptoss | C | 84/84 | 47 (56.0% [45.2, 65.5]) | 0 / 47 | 37 | 13.1% [7.1, 21.4] |
| gptoss | D | 84/84 | 40 (47.6% [36.9, 58.3]) | 0 / 40 | 32 | 13.1% [7.1, 21.4] |
| gptoss | E | 84/84 | 49 (58.3% [47.6, 69.0]) | 1 / 48 | 34 | 13.1% [7.1, 21.4] |
| gptoss | F | 84/84 | 49 (58.3% [47.6, 69.0]) | 0 / 49 | 34 | 13.1% [7.1, 21.4] |
