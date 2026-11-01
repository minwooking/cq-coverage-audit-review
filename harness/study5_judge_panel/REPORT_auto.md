# Addendum 36 results -- judge-score contrasts across a judge panel; not human-labelled; exploratory, post hoc (addendum 36)

Post hoc. Named non-registered judges only (the registered holdout judge has no route). Views = question-only sub-graphs (Studies 3-4). `qwen3-next-80B` shares the extractor's model id (same family) and is excluded from the interpretation rule; `Qwen3.8-Flash-Next` is Qwen lineage and is counted independent as instructed (sensitivity without it is given). Banks are AI drafts for the new domains and for the non-holdout Brick banks.

## Interpretation rule (pre-fixed, PLAN 36.6)

Wording permitted: **judge-dependent**.

- brick_pool: 1 of 4 independent-family judges resolved B > A (rule >= 3: False); without Qwen3.8-Flash-Next: 1 of 3 (False).
- new_domains_pooled: 1 of 4 independent-family judges resolved B > A (rule >= 3: False); without Qwen3.8-Flash-Next: 1 of 3 (False).

## Per-judge decisions, A -> B (n; delta [95% BCa]; decision)

| scope | GLM-4.7-Flash | gpt-oss-20b | Qwen3.8-Flash-Next | Qwen3-Next-80B-A3B (extractor's model id) | gateway judge | panel mean (descriptive) |
|---|---|---|---|---|---|---|
| holdout | n=22; +0.545 [-0.076, +1.182]; unresolved | n=22; +0.409 [-0.242, +1.045]; unresolved | n=22; -0.091 [-0.667, +0.500]; unresolved | n=22; +0.758 [+0.045, +1.408]; resolved_B_gt_A | n=22; -0.023 [-0.545, +0.523]; equivalent | n=22; +0.344 [-0.167, +0.797]; unresolved |
| paraphrases | n=21; +0.444 [-0.238, +1.079]; unresolved | n=21; +0.016 [-0.952, +0.905]; unresolved | n=21; -0.349 [-1.079, +0.333]; unresolved | n=21; +0.270 [-0.714, +1.190]; unresolved | n=21; -0.119 [-0.786, +0.619]; unresolved | n=21; +0.064 [-0.659, +0.722]; unresolved |
| v2_extras | n=10; +0.400 [-0.067, +1.300]; unresolved | n=10; +0.233 [-0.667, +1.400]; unresolved | n=10; -0.100 [-0.800, +0.200]; unresolved | n=10; +1.100 [+0.233, +2.000]; resolved_B_gt_A | n=10; -0.367 [-1.050, +0.083]; unresolved | n=10; +0.288 [+0.117, +0.537]; resolved_B_gt_A |
| expansion | n=26; +0.359 [-0.154, +0.885]; unresolved | n=26; -0.564 [-1.167, +0.154]; unresolved | n=26; +0.051 [-0.500, +0.654]; unresolved | n=26; +0.641 [+0.038, +1.218]; resolved_B_gt_A | n=26; +0.160 [-0.244, +0.631]; unresolved | n=26; +0.126 [-0.274, +0.621]; unresolved |
| brick_pool | n=58; +0.414 [+0.080, +0.753]; resolved_B_gt_A | n=58; -0.132 [-0.552, +0.287]; equivalent | n=58; -0.075 [-0.414, +0.276]; equivalent | n=58; +0.670 [+0.244, +1.060]; resolved_B_gt_A | n=58; -0.017 [-0.313, +0.286]; equivalent | n=58; +0.183 [-0.102, +0.460]; equivalent |
| dcat | n=21; +0.143 [-0.111, +0.536]; equivalent | n=21; -0.397 [-1.063, +0.302]; unresolved | n=21; -0.095 [-0.667, +0.413]; unresolved | n=21; -0.286 [-0.683, +0.032]; unresolved | n=21; -0.238 [-0.690, +0.262]; unresolved | n=21; -0.171 [-0.521, +0.118]; equivalent |
| ssn | n=41; +0.520 [+0.244, +0.846]; resolved_B_gt_A | n=41; -0.317 [-0.789, +0.187]; unresolved | n=41; -0.293 [-0.650, +0.081]; unresolved | n=41; -0.163 [-0.488, +0.211]; equivalent | n=41; -0.159 [-0.443, +0.146]; equivalent | n=41; -0.081 [-0.311, +0.169]; equivalent |
| prov | n=37; +0.270 [+0.018, +0.595]; resolved_B_gt_A | n=37; +0.081 [-0.477, +0.586]; unresolved | n=37; +0.270 [-0.054, +0.568]; unresolved | n=37; +0.297 [-0.135, +0.766]; unresolved | n=37; +0.126 [-0.176, +0.437]; equivalent | n=37; +0.215 [-0.012, +0.470]; equivalent |
| new_domains_pooled | n=99; +0.347 [+0.182, +0.542]; resolved_B_gt_A | n=99; -0.185 [-0.505, +0.145]; equivalent | n=99; -0.040 [-0.269, +0.182]; equivalent | n=99; -0.017 [-0.249, +0.232]; equivalent | n=99; -0.069 [-0.266, +0.130]; equivalent | n=99; +0.010 [-0.139, +0.162]; equivalent |

## Panel summary (number of judges per decision)

| contrast | scope | independent (n judges) | resolved B>A / A>B / equivalent / unresolved / underpowered | same-family | without Qwen3.8-Flash-Next |
|---|---|---|---|---|---|
| A->B | brick_pool | 4 | 1 / 0 / 3 / 0 / 0 | 1 / 0 / 0 / 0 / 0 | 1 / 0 / 2 / 0 / 0 |
| A->B | dcat | 4 | 0 / 0 / 1 / 3 / 0 | 0 / 0 / 0 / 1 / 0 | 0 / 0 / 1 / 2 / 0 |
| A->B | expansion | 4 | 0 / 0 / 0 / 4 / 0 | 1 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 3 / 0 |
| A->B | holdout | 4 | 0 / 0 / 1 / 3 / 0 | 1 / 0 / 0 / 0 / 0 | 0 / 0 / 1 / 2 / 0 |
| A->B | new_domains_pooled | 4 | 1 / 0 / 3 / 0 / 0 | 0 / 0 / 1 / 0 / 0 | 1 / 0 / 2 / 0 / 0 |
| A->B | paraphrases | 4 | 0 / 0 / 0 / 4 / 0 | 0 / 0 / 0 / 1 / 0 | 0 / 0 / 0 / 3 / 0 |
| A->B | prov | 4 | 1 / 0 / 1 / 2 / 0 | 0 / 0 / 0 / 1 / 0 | 1 / 0 / 1 / 1 / 0 |
| A->B | ssn | 4 | 1 / 0 / 1 / 2 / 0 | 0 / 0 / 1 / 0 / 0 | 1 / 0 / 1 / 1 / 0 |
| A->B | v2_extras | 4 | 0 / 0 / 0 / 4 / 0 | 1 / 0 / 0 / 0 / 0 | 0 / 0 / 0 / 3 / 0 |
| A->F | dcat | 4 | 0 / 0 / 1 / 3 / 0 | 0 / 0 / 0 / 1 / 0 | 0 / 0 / 1 / 2 / 0 |
| A->F | new_domains_pooled | 4 | 1 / 1 / 2 / 0 / 0 | 0 / 0 / 1 / 0 / 0 | 1 / 0 / 2 / 0 / 0 |
| A->F | prov | 4 | 1 / 0 / 2 / 1 / 0 | 0 / 0 / 0 / 1 / 0 | 1 / 0 / 1 / 1 / 0 |
| A->F | ssn | 4 | 1 / 1 / 1 / 1 / 0 | 0 / 0 / 0 / 1 / 0 | 1 / 0 / 1 / 1 / 0 |
| B->F | dcat | 4 | 0 / 1 / 3 / 0 / 0 | 0 / 0 / 1 / 0 / 0 | 0 / 1 / 2 / 0 / 0 |
| B->F | new_domains_pooled | 4 | 0 / 2 / 2 / 0 / 0 | 0 / 0 / 1 / 0 / 0 | 0 / 1 / 2 / 0 / 0 |
| B->F | prov | 4 | 0 / 2 / 1 / 1 / 0 | 0 / 0 / 1 / 0 / 0 | 0 / 1 / 1 / 1 / 0 |
| B->F | ssn | 4 | 0 / 1 / 3 / 0 / 0 | 0 / 1 / 0 / 0 / 0 | 0 / 1 / 2 / 0 / 0 |

### panel_mean_all (descriptive aggregate, not a judge; judges: glm, gptoss, q38, q80, gw; cells 477)

- A->B|holdout: n=22; +0.344 [-0.167, +0.797]; unresolved
- A->B|paraphrases: n=21; +0.064 [-0.659, +0.722]; unresolved
- A->B|v2_extras: n=10; +0.288 [+0.117, +0.537]; resolved_B_gt_A
- A->B|expansion: n=26; +0.126 [-0.274, +0.621]; unresolved
- A->B|brick_pool: n=58; +0.183 [-0.102, +0.460]; equivalent
- A->B|dcat: n=21; -0.171 [-0.521, +0.118]; equivalent
- A->B|ssn: n=41; -0.081 [-0.311, +0.169]; equivalent
- A->B|prov: n=37; +0.215 [-0.012, +0.470]; equivalent
- A->B|new_domains_pooled: n=99; +0.010 [-0.139, +0.162]; equivalent
- A->F|dcat: n=22; -0.105 [-0.478, +0.208]; equivalent
- A->F|ssn: n=41; -0.129 [-0.370, +0.144]; equivalent
- A->F|prov: n=36; +0.056 [-0.194, +0.309]; equivalent
- A->F|new_domains_pooled: n=99; -0.056 [-0.214, +0.107]; equivalent
- B->F|dcat: n=26; -0.009 [-0.090, +0.082]; equivalent
- B->F|ssn: n=41; -0.048 [-0.139, +0.048]; equivalent
- B->F|prov: n=36; -0.173 [-0.340, -0.002]; resolved_B_gt_F
- B->F|new_domains_pooled: n=103; -0.082 [-0.160, -0.012]; resolved_B_gt_F

### panel_mean_without_q80 (descriptive aggregate, not a judge; judges: glm, gptoss, q38, gw; cells 477)

- A->B|holdout: n=22; +0.231 [-0.244, +0.680]; unresolved
- A->B|paraphrases: n=21; +0.011 [-0.657, +0.635]; unresolved
- A->B|v2_extras: n=10; +0.067 [-0.171, +0.316]; equivalent
- A->B|expansion: n=26; -0.015 [-0.405, +0.499]; equivalent
- A->B|brick_pool: n=58; +0.051 [-0.220, +0.330]; equivalent
- A->B|dcat: n=21; -0.137 [-0.537, +0.225]; equivalent
- A->B|ssn: n=41; -0.057 [-0.301, +0.204]; equivalent
- A->B|prov: n=37; +0.190 [-0.045, +0.437]; equivalent
- A->B|new_domains_pooled: n=99; +0.018 [-0.140, +0.181]; equivalent
- A->F|dcat: n=22; -0.099 [-0.503, +0.255]; equivalent
- A->F|ssn: n=41; -0.087 [-0.327, +0.192]; equivalent
- A->F|prov: n=36; -0.023 [-0.251, +0.229]; equivalent
- A->F|new_domains_pooled: n=99; -0.066 [-0.221, +0.101]; equivalent
- B->F|dcat: n=26; -0.038 [-0.105, +0.052]; equivalent
- B->F|ssn: n=41; -0.030 [-0.137, +0.083]; equivalent
- B->F|prov: n=36; -0.228 [-0.410, -0.045]; resolved_B_gt_F
- B->F|new_domains_pooled: n=103; -0.101 [-0.188, -0.025]; resolved_B_gt_F

## Variant F contrasts (per judge)

### GLM-4.7-Flash
- A->F|dcat: n=22; +0.076 [-0.182, +0.485]; equivalent
- A->F|ssn: n=41; +0.407 [+0.146, +0.725]; resolved_F_gt_A
- A->F|prov: n=36; +0.352 [+0.102, +0.694]; resolved_F_gt_A
- A->F|new_domains_pooled: n=99; +0.313 [+0.155, +0.512]; resolved_F_gt_A
- B->F|dcat: n=26; -0.179 [-0.372, -0.026]; resolved_B_gt_F
- B->F|ssn: n=41; -0.114 [-0.220, -0.024]; resolved_B_gt_F
- B->F|prov: n=36; +0.046 [-0.093, +0.194]; equivalent
- B->F|new_domains_pooled: n=103; -0.074 [-0.155, +0.006]; equivalent

### gpt-oss-20b
- A->F|dcat: n=22; -0.136 [-0.818, +0.545]; unresolved
- A->F|ssn: n=41; -0.171 [-0.602, +0.268]; unresolved
- A->F|prov: n=36; -0.231 [-0.731, +0.306]; unresolved
- A->F|new_domains_pooled: n=99; -0.185 [-0.485, +0.125]; equivalent
- B->F|dcat: n=26; +0.103 [-0.013, +0.380]; equivalent
- B->F|ssn: n=41; +0.146 [-0.171, +0.455]; equivalent
- B->F|prov: n=36; -0.315 [-0.787, +0.185]; unresolved
- B->F|new_domains_pooled: n=103; -0.026 [-0.252, +0.188]; equivalent

### Qwen3.8-Flash-Next
- A->F|dcat: n=22; -0.136 [-0.697, +0.409]; unresolved
- A->F|ssn: n=41; -0.439 [-0.821, -0.024]; resolved_A_gt_F
- A->F|prov: n=36; -0.074 [-0.407, +0.269]; equivalent
- A->F|new_domains_pooled: n=99; -0.239 [-0.478, -0.003]; resolved_A_gt_F
- B->F|dcat: n=26; -0.051 [-0.218, +0.077]; equivalent
- B->F|ssn: n=41; -0.146 [-0.301, +0.016]; equivalent
- B->F|prov: n=36; -0.352 [-0.565, -0.176]; resolved_B_gt_F
- B->F|new_domains_pooled: n=103; -0.194 [-0.298, -0.097]; resolved_B_gt_F

### Qwen3-Next-80B-A3B (extractor's model id)
- A->F|dcat: n=22; -0.121 [-0.606, +0.227]; unresolved
- A->F|ssn: n=41; -0.276 [-0.610, +0.098]; unresolved
- A->F|prov: n=36; +0.343 [-0.099, +0.759]; unresolved
- A->F|new_domains_pooled: n=99; -0.017 [-0.253, +0.229]; equivalent
- B->F|dcat: n=26; +0.090 [-0.115, +0.308]; equivalent
- B->F|ssn: n=41; -0.114 [-0.236, -0.016]; resolved_B_gt_F
- B->F|prov: n=36; +0.037 [-0.194, +0.306]; equivalent
- B->F|new_domains_pooled: n=103; -0.010 [-0.120, +0.104]; equivalent

### gateway judge
- A->F|dcat: n=22; -0.250 [-0.659, +0.182]; unresolved
- A->F|ssn: n=41; -0.183 [-0.500, +0.171]; equivalent
- A->F|prov: n=36; -0.208 [-0.500, +0.111]; equivalent
- A->F|new_domains_pooled: n=99; -0.207 [-0.399, +0.007]; equivalent
- B->F|dcat: n=26; -0.006 [-0.141, +0.122]; equivalent
- B->F|ssn: n=41; -0.024 [-0.211, +0.171]; equivalent
- B->F|prov: n=36; -0.352 [-0.606, -0.139]; resolved_B_gt_F
- B->F|new_domains_pooled: n=103; -0.134 [-0.257, -0.019]; resolved_B_gt_F

## Pairwise judge agreement (QWK on the per-cell median-low of repeats)

**A_B_cells**
- glm~gptoss: n=372, QWK 0.422, exact agreement 0.478
- glm~q38: n=372, QWK 0.524, exact agreement 0.530
- glm~q80: n=372, QWK 0.487, exact agreement 0.505
- glm~gw: n=372, QWK 0.389, exact agreement 0.382
- gptoss~q38: n=372, QWK 0.538, exact agreement 0.629
- gptoss~q80: n=372, QWK 0.452, exact agreement 0.570
- gptoss~gw: n=372, QWK 0.451, exact agreement 0.454
- q38~q80: n=372, QWK 0.577, exact agreement 0.616
- q38~gw: n=372, QWK 0.680, exact agreement 0.597
- q80~gw: n=372, QWK 0.444, exact agreement 0.425

**F_cells**
- glm~gptoss: n=105, QWK 0.195, exact agreement 0.324
- glm~q38: n=105, QWK 0.441, exact agreement 0.429
- glm~q80: n=105, QWK 0.485, exact agreement 0.448
- glm~gw: n=105, QWK 0.176, exact agreement 0.190
- gptoss~q38: n=105, QWK 0.349, exact agreement 0.448
- gptoss~q80: n=105, QWK 0.517, exact agreement 0.552
- gptoss~gw: n=105, QWK 0.386, exact agreement 0.362
- q38~q80: n=105, QWK 0.557, exact agreement 0.419
- q38~gw: n=105, QWK 0.617, exact agreement 0.495
- q80~gw: n=105, QWK 0.451, exact agreement 0.314

## Calls

- glm: {"records": 315, "valid": 1431, "invalid": 0, "context_skip": 0, "prompt_tokens": 3246807, "completion_tokens": 42800, "model": "zai-org/GLM-4.7-Flash"}
- gptoss: {"records": 315, "valid": 1430, "invalid": 0, "context_skip": 0, "prompt_tokens": 3268233, "completion_tokens": 43538, "model": "openai/gpt-oss-20b"}
- q38: {"records": 1431, "valid": 1431, "invalid": 0, "context_skip": 0, "prompt_tokens": 10322649, "completion_tokens": 188950, "model": "Qwen/Qwen3.8-Flash-Next"}
- q80: {"records": 1431, "valid": 1431, "invalid": 0, "context_skip": 0, "prompt_tokens": 10237644, "completion_tokens": 152561, "model": "Qwen/Qwen3-Next-80B-A3B-Instruct-FP8"}
- gw: {"records": 1003, "valid": 1000, "invalid": 3, "context_skip": 0, "prompt_tokens": 7069090, "completion_tokens": 218975, "model": "gpt-5.6-luna"}
