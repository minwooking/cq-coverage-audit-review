# Study 2 (addendum 32) -- automatic report

> **LLM-labeled; not human-validated beyond Stage 1.** AI-generated; a person must review it. All numbers come from `results.json`, written by `analyze.py` from the raw call records; nothing was tuned after the first model call.

## Stage 1: calibration gate

Gate rule (PLAN 32.6): PASS iff at least one primary model passes both humans; pair passes iff n >= 30 and the lower 95% BCa bound of kappa(LLM, human) >= kappa(AH, R2) on the same cells - 0.10.
**Verdict: FAIL** (passing models: none; headline labeler: None).

| model | human | n cells | kappa(LLM, human) [95% CI] | kappa(AH, R2) same cells | gate ref (-0.10) | exact agreement | pass |
|---|---|---:|---|---|---:|---|:-:|
| GLM-4.7-Flash | AH | 188 | 0.245 [0.103, 0.422] | 0.595 [0.268, 0.833] | 0.495 | 0.585 [0.476, 0.690] | no |
| GLM-4.7-Flash | R2 | 188 | 0.187 [0.015, 0.374] | 0.595 [0.268, 0.833] | 0.495 | 0.564 [0.450, 0.672] | no |
| gpt-oss-20b | AH | 188 | 0.310 [0.153, 0.505] | 0.595 [0.268, 0.833] | 0.495 | 0.617 [0.490, 0.734] | no |
| gpt-oss-20b | R2 | 188 | 0.291 [0.076, 0.508] | 0.595 [0.268, 0.833] | 0.495 | 0.617 [0.471, 0.742] | no |
| Qwen3.8-Flash-Next | - | 0 | no labeled cells | | | | |

### Unsupported credit pi-hat (share of cells with registered-judge J >= 2 and S = 0) on the same cells

| model | pi-hat under LLM | under AH | under R2 | LLM - AH | LLM - R2 |
|---|---|---|---|---|---|
| GLM-4.7-Flash | 36.7% [27.0, 47.1] | 7.4% [2.1, 18.5] | 13.8% [5.9, 26.3] | 29.3% [17.7, 41.0] | 22.9% [8.9, 36.8] |
| gpt-oss-20b | 34.6% [23.7, 46.3] | 7.4% [2.1, 18.5] | 13.8% [5.9, 26.3] | 27.1% [17.2, 38.5] | 20.7% [8.0, 33.5] |

All 188 cells: kappa(AH, R2) = 0.595 [0.268, 0.833]; pi-hat AH = 7.4% [2.1, 18.5], R2 = 13.8% [5.9, 26.3].

### Label coverage, consistency and reliability

| model | cells with label / attempted | undefined | context skip | share of label 1 | R25 coverage | alpha (25 slots) | valid slot share |
|---|---:|---:|---:|---|---|---|---:|
| GLM-4.7-Flash | 188 / 188 | 0 | 0 | 39.4% [29.2, 50.0] | 5.9% [2.1, 13.5] | 0.156 [0.122, 0.206] | 0.9989 |
| gpt-oss-20b | 188 / 188 | 0 | 0 | 38.3% [26.7, 51.6] | 39.4% [27.2, 52.7] | 0.434 [0.337, 0.544] | 1.0 |

### Agreement of the R25-consistent subset (secondary)

- GLM-4.7-Flash: n = 11; kappa vs AH 0.154 [0.000, 1.000], vs R2 0.154 [0.000, 1.000]; human-human on the same cells 1.000 [0.000, 1.000].
- gpt-oss-20b: n = 74; kappa vs AH 0.584 [0.272, 0.855], vs R2 0.306 [-0.027, 0.670]; human-human on the same cells 0.703 [0.280, 0.923].

### View term coverage (PLAN 32.4; target >= 90%, reported whatever it is)

- The retrieval view holds the expected-answer terms (anchors and >= 50% of the answer terms on one line) in 57 / 188 cells (30.3%). The full rendering itself holds them in 60 / 188 (31.9%), which is the ceiling of any view of it under this strict single-line test; given that the full rendering holds them, the view holds them in 57 / 60 (95.0%). The subgraph views of addendum 30 held them in 21 / 188 (11.2%).
- Judge span located in the rendering: all pieces found in 127 of 141 cells that had a span. Fallback used in 12 primary cells; character cap reached in 20.
- By variant (view / full / subgraph holds terms, of n): A: 7/7/5 of 23; B: 10/11/4 of 33; C: 10/11/3 of 33; D: 10/11/3 of 33; E: 10/10/3 of 33; F: 10/10/3 of 33.
- The anchor half of the test is true by construction wherever an anchor line exists; the informative half is the answer-term fraction.

### Negative control (diagnostic): the 24 registered ablated controls, majority label

- GLM-4.7-Flash: labeled S = 0 in 22 of 24 (S = 1: 2, undefined: 0).
- gpt-oss-20b: labeled S = 0 in 22 of 24 (S = 1: 2, undefined: 0).
- Qwen3.8-Flash-Next: labeled S = 0 in 0 of 24 (S = 1: 0, undefined: 24).

### Timing record (per-call latency, seconds)

- GLM-4.7-Flash: {'n_calls': 5300, 'n_with_latency': 5300, 'n_with_timestamp': 5300, 'p05': 1.22, 'p50': 4.33, 'p95': 14.4, 'max': 213.93, 'share_below_0.5s': 0.0011, 'prompt_tokens': 47744336, 'completion_tokens': 641435}
- gpt-oss-20b: {'n_calls': 5300, 'n_with_latency': 5300, 'n_with_timestamp': 5300, 'p05': 2.25, 'p50': 5.67, 'p95': 15.17, 'max': 343.9, 'share_below_0.5s': 0.0, 'prompt_tokens': 45001072, 'completion_tokens': 1120594}
- Qwen3.8-Flash-Next: {'n_calls': 0, 'n_with_latency': 0}

## Stage 2: expanded audit

- Bank: 84 questions (frozen sha256 `a39bcc0fd88587de8ef2fe14304948995b8e5bb3e6e5cfb04303784ffc2a33c8`); eligible cells 208 of 504 (by variant {'A': 67, 'B': 29, 'C': 28, 'D': 28, 'E': 28, 'F': 28}); **eligible clusters 70** (target >= 60: met); clusters eligible in both A and B: 26.
- Judges: GLM-4.7-Flash (glm), gpt-oss-20b (gptoss). the registered holdout judge has no route here; named non-Qwen judges on question-only subgraph views (deviation stated in PLAN 32.8).
- Stage 1 gate: FAIL.

**Not run as an audit: Stage 1 gate failed: Stage 2 is not run as an LLM-labeled audit.** Judge-only descriptive scores are in `results_stage2.json`.
