# Addendum 36B results -- judge-score contrasts for a Qwen size ladder; not human-labelled; exploratory, post hoc (addendum 36 amendment B)

Models: Qwen3.8-27B (as requested); Qwen3.5-9B and Qwen3.5-4B stand in for the non-existent Qwen3.8-8B / -4B (PLAN B.1). All three are the extractor's vendor, not its model; they are **not** in the pre-fixed independent-family count of addendum 36 (PLAN B.2). Temperature 0, 3 repeats, thinking off, Study 5 prompts and scorer.

## A -> B per judge (n; delta [95% BCa]; decision)

| scope | Qwen3.8-27B | Qwen3.5-9B | Qwen3.5-4B |
|---|---|---|---|
| holdout | n=22; +0.091 [-0.500, +0.773]; unresolved | n=22; +0.879 [+0.167, +1.576]; resolved_B_gt_A | n=22; +0.439 [-0.091, +0.955]; unresolved |
| paraphrases | n=21; -0.349 [-1.143, +0.333]; unresolved | n=21; +0.048 [-0.857, +0.905]; unresolved | n=21; -0.333 [-0.857, +0.286]; unresolved |
| v2_extras | n=10; +0.000 [-1.000, +1.200]; unresolved | n=10; +1.100 [+0.200, +2.100]; resolved_B_gt_A | n=10; +0.667 [-0.233, +1.567]; unresolved |
| expansion | n=26; +0.385 [-0.308, +1.077]; unresolved | n=26; +0.436 [-0.244, +1.128]; unresolved | n=26; +0.359 [-0.218, +0.846]; unresolved |
| brick_pool | n=58; +0.126 [-0.302, +0.549]; equivalent | n=58; +0.560 [+0.126, +0.986]; resolved_B_gt_A | n=58; +0.299 [-0.037, +0.626]; unresolved |
| dcat | n=21; -0.587 [-1.159, +0.000]; unresolved | n=21; -0.905 [-1.476, -0.429]; resolved_A_gt_B | n=20; -0.217 [-0.750, +0.217]; unresolved |
| ssn | n=41; -0.512 [-0.992, -0.041]; resolved_A_gt_B | n=41; -0.130 [-0.569, +0.301]; equivalent | n=41; +0.089 [-0.276, +0.480]; equivalent |
| prov | n=37; -0.081 [-0.432, +0.324]; equivalent | n=37; +0.045 [-0.514, +0.622]; unresolved | n=37; +0.000 [-0.252, +0.315]; equivalent |
| new_domains_pooled | n=99; -0.367 [-0.640, -0.084]; resolved_A_gt_B | n=99; -0.229 [-0.535, +0.084]; equivalent | n=98; -0.007 [-0.224, +0.211]; equivalent |

## Ladder count (judges per decision)

| contrast | scope | resolved B>A / A>B / equivalent / unresolved / underpowered |
|---|---|---|
| A->B | brick_pool | 1 / 0 / 1 / 1 / 0 (of 3) |
| A->B | dcat | 0 / 1 / 0 / 2 / 0 (of 3) |
| A->B | expansion | 0 / 0 / 0 / 3 / 0 (of 3) |
| A->B | holdout | 1 / 0 / 0 / 2 / 0 (of 3) |
| A->B | new_domains_pooled | 0 / 1 / 2 / 0 / 0 (of 3) |
| A->B | paraphrases | 0 / 0 / 0 / 3 / 0 (of 3) |
| A->B | prov | 0 / 0 / 2 / 1 / 0 (of 3) |
| A->B | ssn | 0 / 1 / 2 / 0 / 0 (of 3) |
| A->B | v2_extras | 1 / 0 / 0 / 2 / 0 (of 3) |
| A->F | dcat | 0 / 2 / 0 / 1 / 0 (of 3) |
| A->F | new_domains_pooled | 0 / 1 / 1 / 1 / 0 (of 3) |
| A->F | prov | 0 / 1 / 2 / 0 / 0 (of 3) |
| A->F | ssn | 0 / 0 / 1 / 2 / 0 (of 3) |
| B->F | dcat | 0 / 0 / 3 / 0 / 0 (of 3) |
| B->F | new_domains_pooled | 0 / 1 / 2 / 0 / 0 (of 3) |
| B->F | prov | 1 / 1 / 1 / 0 / 0 (of 3) |
| B->F | ssn | 0 / 0 / 3 / 0 / 0 (of 3) |

## Variant F contrasts (per judge)

### Qwen3.8-27B
- A->F|dcat: n=22; -0.561 [-1.121, -0.015]; resolved_A_gt_F
- A->F|ssn: n=41; -0.537 [-1.073, +0.024]; unresolved
- A->F|prov: n=36; -0.509 [-0.991, -0.037]; resolved_A_gt_F
- A->F|new_domains_pooled: n=99; -0.532 [-0.835, -0.212]; resolved_A_gt_F
- B->F|dcat: n=26; -0.038 [-0.269, +0.231]; equivalent
- B->F|ssn: n=41; -0.024 [-0.301, +0.236]; equivalent
- B->F|prov: n=36; -0.454 [-0.759, -0.176]; resolved_B_gt_F
- B->F|new_domains_pooled: n=103; -0.178 [-0.350, -0.019]; resolved_B_gt_F

### Qwen3.5-9B
- A->F|dcat: n=22; -0.864 [-1.455, -0.409]; resolved_A_gt_F
- A->F|ssn: n=41; -0.146 [-0.577, +0.301]; unresolved
- A->F|prov: n=35; -0.048 [-0.571, +0.514]; equivalent
- A->F|new_domains_pooled: n=98; -0.272 [-0.561, +0.034]; unresolved
- B->F|dcat: n=26; -0.090 [-0.449, +0.000]; equivalent
- B->F|ssn: n=41; -0.016 [-0.260, +0.220]; equivalent
- B->F|prov: n=35; -0.181 [-0.524, +0.076]; equivalent
- B->F|new_domains_pooled: n=102; -0.092 [-0.248, +0.045]; equivalent

### Qwen3.5-4B
- A->F|dcat: n=22; -0.348 [-0.833, +0.061]; unresolved
- A->F|ssn: n=41; -0.098 [-0.528, +0.341]; equivalent
- A->F|prov: n=36; +0.204 [-0.065, +0.556]; equivalent
- A->F|new_domains_pooled: n=99; -0.044 [-0.279, +0.185]; equivalent
- B->F|dcat: n=25; -0.147 [-0.413, +0.027]; equivalent
- B->F|ssn: n=41; -0.187 [-0.496, +0.091]; equivalent
- B->F|prov: n=36; +0.176 [+0.028, +0.519]; resolved_F_gt_B
- B->F|new_domains_pooled: n=102; -0.049 [-0.202, +0.098]; equivalent

## Pairwise agreement with the other panel judges (QWK on per-cell median-low of repeats)

**A_B_cells**
- glm~q38_27b: n=372, QWK 0.443, exact agreement 0.508
- glm~q35_9b: n=372, QWK 0.464, exact agreement 0.524
- glm~q35_4b: n=371, QWK 0.493, exact agreement 0.482
- gptoss~q38_27b: n=372, QWK 0.465, exact agreement 0.543
- gptoss~q35_9b: n=372, QWK 0.446, exact agreement 0.610
- gptoss~q35_4b: n=371, QWK 0.436, exact agreement 0.412
- q38~q38_27b: n=372, QWK 0.671, exact agreement 0.591
- q38~q35_9b: n=372, QWK 0.513, exact agreement 0.591
- q38~q35_4b: n=371, QWK 0.516, exact agreement 0.420
- q80~q38_27b: n=372, QWK 0.539, exact agreement 0.551
- q80~q35_9b: n=372, QWK 0.600, exact agreement 0.608
- q80~q35_4b: n=371, QWK 0.562, exact agreement 0.464
- gw~q38_27b: n=372, QWK 0.572, exact agreement 0.419
- gw~q35_9b: n=372, QWK 0.440, exact agreement 0.390
- gw~q35_4b: n=371, QWK 0.412, exact agreement 0.302
- q38_27b~q35_9b: n=372, QWK 0.576, exact agreement 0.610
- q38_27b~q35_4b: n=371, QWK 0.624, exact agreement 0.531
- q35_9b~q35_4b: n=371, QWK 0.639, exact agreement 0.558

**F_cells**
- glm~q38_27b: n=105, QWK 0.253, exact agreement 0.362
- glm~q35_9b: n=104, QWK 0.324, exact agreement 0.481
- glm~q35_4b: n=105, QWK 0.455, exact agreement 0.476
- gptoss~q38_27b: n=105, QWK 0.327, exact agreement 0.305
- gptoss~q35_9b: n=104, QWK 0.398, exact agreement 0.519
- gptoss~q35_4b: n=105, QWK 0.366, exact agreement 0.381
- q38~q38_27b: n=105, QWK 0.584, exact agreement 0.448
- q38~q35_9b: n=104, QWK 0.460, exact agreement 0.442
- q38~q35_4b: n=105, QWK 0.545, exact agreement 0.438
- q80~q38_27b: n=105, QWK 0.478, exact agreement 0.410
- q80~q35_9b: n=104, QWK 0.482, exact agreement 0.529
- q80~q35_4b: n=105, QWK 0.576, exact agreement 0.505
- gw~q38_27b: n=105, QWK 0.534, exact agreement 0.200
- gw~q35_9b: n=104, QWK 0.370, exact agreement 0.221
- gw~q35_4b: n=105, QWK 0.394, exact agreement 0.257
- q38_27b~q35_9b: n=104, QWK 0.474, exact agreement 0.510
- q38_27b~q35_4b: n=105, QWK 0.502, exact agreement 0.524
- q35_9b~q35_4b: n=104, QWK 0.579, exact agreement 0.519

## Calls

- q38_27b: {"records": 1431, "valid": 1431, "invalid": 0, "context_skip": 0, "prompt_tokens": 10322649, "completion_tokens": 93636, "model": "Qwen/Qwen3.8-27B"}
- q35_9b: {"records": 1431, "valid": 1426, "invalid": 5, "context_skip": 0, "prompt_tokens": 10322649, "completion_tokens": 172546, "model": "Qwen/Qwen3.5-9B"}
- q35_4b: {"records": 1431, "valid": 1428, "invalid": 3, "context_skip": 0, "prompt_tokens": 10322649, "completion_tokens": 142719, "model": "Qwen/Qwen3.5-4B"}
