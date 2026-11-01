# REPORT (auto) -- addendum 37, study6_rescoring

> AI-generated; exploratory and post hoc; readings are PLAN.md 37.6 as written. Review before use.

## A. Development study without the hint

Reference, original Qwen development judge (with hint): A->B n=16, +1.000 [+0.500, +1.625], MDE 0.81, resolved/0.30 resolved/0.50

### GLM-4.7-Flash (`glm`): reading **hint-independent**
* A_hint (addendum 26 (reused, byte-identical prompt); valid cells 91, context-skipped 0): A->B n=15, +0.467 [+0.178, +0.956], MDE 0.54, resolved/0.30 resolved/0.50
* A_nohint (this addendum; valid cells 90, context-skipped 0): A->B n=16, +0.375 [+0.125, +0.812], MDE 0.50, resolved/0.30 resolved/0.50
* A_holdout (this addendum; valid cells 90, context-skipped 0): A->B n=15, +1.333 [+0.933, +1.844], MDE 0.67, resolved/0.30 resolved/0.50
* hint effect (no-hint minus hint, cells): +0.117 [+0.007, +0.240], exact 0.836, QWK 0.466
* A->B shift (no-hint minus hint): -0.067 [-0.511, +0.200] over 15 questions

### gpt-oss-20b (`gptoss`): reading **hint-independent**
* A_hint (addendum 26 (reused, byte-identical prompt); valid cells 95, context-skipped 0): A->B n=16, +1.188 [+0.021, +2.000], MDE 1.43, resolved/0.30 resolved/0.50
* A_nohint (this addendum; valid cells 95, context-skipped 0): A->B n=16, +1.042 [+0.146, +1.771], MDE 1.19, resolved/0.30 resolved/0.50
* A_holdout (this addendum; valid cells 94, context-skipped 0): A->B n=16, +1.917 [+1.229, +2.438], MDE 0.89, resolved/0.30 resolved/0.50
* hint effect (no-hint minus hint, cells): +0.273 [-0.128, +0.711], exact 0.728, QWK 0.445
* A->B shift (no-hint minus hint): -0.146 [-0.771, +0.500] over 16 questions

### Qwen3.5-4B (Qwen-lineage proxy) (`qwen35`): reading **hint-independent**
* A_hint (this addendum; valid cells 45, context-skipped 48): A->B n=14, +0.762 [+0.405, +1.262], MDE 0.62, resolved/0.30 resolved/0.50
* A_nohint (this addendum; valid cells 46, context-skipped 48): A->B n=15, +0.822 [+0.467, +1.222], MDE 0.57, resolved/0.30 resolved/0.50
* A_holdout (this addendum; valid cells 60, context-skipped 32): A->B n=15, +1.600 [+0.933, +2.200], MDE 0.94, resolved/0.30 resolved/0.50
* hint effect (no-hint minus hint, cells): -0.070 [-0.220, +0.030], exact 0.875, QWK 0.846
* A->B shift (no-hint minus hint): +0.051 [-0.231, +0.333] over 13 questions

* `q38`: not run
* `gw`: not run
Original-family reading: {"judge": "qwen35", "label": "Qwen3.5-4B (Qwen-lineage proxy)", "reading": "hint-independent", "is_original_model": false, "note": "Qwen-lineage proxy, not Qwen3-Next-80B-A3B"}

## B and C. Re-scoring on the 60,000-character view and reuse of addendum-26 subgraph scores

Full-view cells scored: 0 (no full view fits a 65,536-token window (fit_full_preflight.json)).

### GLM-4.7-Flash (`glm`)
* view limited (this addendum, valid cells 188): A->B n=23, +0.000 [-0.261, +0.261], MDE 0.39, equivalent/0.30 equivalent/0.50; D-B n=33, +0.101 [-0.051, +0.364], MDE 0.28, unresolved/0.30 equivalent/0.50
  * D vs B reading: does not replicate (D-B >= 0); A->B: direction differs (A->B <= 0); equivalent at 0.30, equivalent at 0.50
  * coverage by variant: A 0.06, B 0.12, C 0.15, D 0.16, E 0.15, F 0.15
  * C_188: vs Gemini full exact 0.231 QWK -0.040 offset -1.652 [-2.061, -1.168]; vs luna same view exact 0.443 QWK 0.262 offset -0.418; share J<=1 0.87
  * B_48: vs Gemini full exact 0.250 QWK -0.038 offset -1.597 [-2.126, -0.993]; vs luna same view exact 0.444 QWK 0.181 offset -0.264; share J<=1 0.85
  * B_48 QWK(new,Gemini)-QWK(Sonnet,Gemini): {"n_cells": 48, "diff": -0.5389791038939107, "ci95": [-0.7731007936762856, -0.28151328229063194], "qwk_new": -0.0410367170626349, "qwk_other": 0.4979423868312758}; reading lower; floor warning True
* view subgraph (addendum 26 (reused), valid cells 182): A->B n=22, +0.545 [-0.076, +1.182], MDE 0.93, unresolved/0.30 unresolved/0.50; D-B n=32, +0.031 [-0.146, +0.292], MDE 0.30, equivalent/0.30 equivalent/0.50
  * D vs B reading: does not replicate (D-B >= 0); A->B: direction agrees (A->B > 0); unresolved at 0.30, unresolved at 0.50
  * coverage by variant: A 0.53, B 0.68, C 0.69, D 0.71, E 0.60, F 0.61
  * C_188: vs Gemini full exact 0.390 QWK 0.244 offset -0.350 [-0.760, +0.009]; vs luna same view exact 0.358 QWK 0.550 offset -0.255; share J<=1 0.36
  * B_48: vs Gemini full exact 0.348 QWK 0.137 offset -0.572 [-1.348, -0.000]; vs luna same view exact 0.355 QWK 0.673 offset -0.203; share J<=1 0.46
  * B_48 QWK(new,Gemini)-QWK(Sonnet,Gemini): {"n_cells": 46, "diff": -0.3340852565214877, "ci95": [-0.6644466157677137, -0.05476969793920162], "qwk_new": 0.14379084967320255, "qwk_other": 0.47787610619469023}; reading lower; floor warning False

### gpt-oss-20b (`gptoss`)
* view limited (this addendum, valid cells 188): A->B n=23, -1.217 [-1.942, -0.386], MDE 1.13, resolved/0.30 resolved/0.50; D-B n=33, -0.081 [-0.505, +0.273], MDE 0.56, unresolved/0.30 equivalent/0.50
  * D vs B reading: direction only (D-B < 0, interval includes 0); A->B: direction differs (A->B <= 0); resolved at 0.30, resolved at 0.50
  * coverage by variant: A 0.55, B 0.13, C 0.07, D 0.10, E 0.06, F 0.10
  * C_188: vs Gemini full exact 0.284 QWK 0.009 offset -1.488 [-1.856, -1.051]; vs luna same view exact 0.465 QWK 0.466 offset -0.254; share J<=1 0.85
  * B_48: vs Gemini full exact 0.278 QWK -0.031 offset -1.597 [-2.072, -1.007]; vs luna same view exact 0.444 QWK 0.192 offset -0.264; share J<=1 0.91
  * B_48 QWK(new,Gemini)-QWK(Sonnet,Gemini): {"n_cells": 48, "diff": -0.5297895205892376, "ci95": [-0.7602866267520413, -0.23239963962984678], "qwk_new": -0.031847133757961776, "qwk_other": 0.4979423868312758}; reading lower; floor warning True
* view subgraph (addendum 26 (reused), valid cells 182): A->B n=22, +0.409 [-0.242, +1.045], MDE 0.95, unresolved/0.30 unresolved/0.50; D-B n=32, -0.021 [-0.427, +0.417], MDE 0.61, unresolved/0.30 equivalent/0.50
  * D vs B reading: direction only (D-B < 0, interval includes 0); A->B: direction agrees (A->B > 0); unresolved at 0.30, unresolved at 0.50
  * coverage by variant: A 0.53, B 0.57, C 0.52, D 0.57, E 0.49, F 0.52
  * C_188: vs Gemini full exact 0.430 QWK 0.227 offset -0.293 [-0.711, +0.087]; vs luna same view exact 0.453 QWK 0.355 offset -0.210; share J<=1 0.47
  * B_48: vs Gemini full exact 0.435 QWK 0.201 offset -0.355 [-0.984, +0.220]; vs luna same view exact 0.449 QWK 0.454 offset +0.014; share J<=1 0.50
  * B_48 QWK(new,Gemini)-QWK(Sonnet,Gemini): {"n_cells": 46, "diff": -0.2778761061946903, "ci95": [-0.6941776187008778, 0.09524270727900142], "qwk_new": 0.19999999999999996, "qwk_other": 0.47787610619469023}; reading comparable; floor warning False

### Inter-judge
```
{
 "limited": {
  "glm_vs_gptoss": {
   "n_cells": 188,
   "n_clusters": 33,
   "exact": 0.7242101869761445,
   "qwk": 0.2718518844651888,
   "offset": -0.16843971631205673,
   "offset_ci95": [
    -0.3350877192982456,
    0.05045045045045046
   ]
  },
  "gptoss_vs_gemini_direction": null
 },
 "subgraph": {
  "glm_vs_gptoss": {
   "n_cells": 182,
   "n_clusters": 32,
   "exact": 0.5036630036630036,
   "qwk": 0.5492614483540353,
   "offset": -0.058608058608058615,
   "offset_ci95": [
    -0.31868131868131866,
    0.24100061373518225
   ]
  },
  "gptoss_vs_gemini_direction": null
 }
}
```

### References
```
{
 "gemini_full": {
  "A->B": {
   "n": 23,
   "mean_first": 1.7391304347826086,
   "mean_second": 2.3043478260869565,
   "delta": 0.5652173913043478,
   "sd_d": 1.342524316912724,
   "ci95": [
    0.043478260869565216,
    1.1304347826086956
   ],
   "ci90": [
    0.13043478260869565,
    1.0434782608695652
   ],
   "n_pos": 10,
   "n_neg": 6,
   "n_zero": 7,
   "mde": 0.7838198796356073,
   "decision_0.30": "resolved",
   "decision_0.50": "resolved",
   "decision": "resolved",
   "sign": 1
  },
  "B->D": {
   "n": 33,
   "mean_first": 2.0606060606060606,
   "mean_second": 1.7878787878787878,
   "delta": -0.2727272727272727,
   "sd_d": 0.7190587281616534,
   "ci95": [
    -0.5757575757575758,
    -0.09090909090909091
   ],
   "ci90": [
    -0.5151515151515151,
    -0.09090909090909091
   ],
   "n_pos": 1,
   "n_neg": 6,
   "n_zero": 26,
   "mde": 0.3504817621000247,
   "decision_0.30": "resolved",
   "decision_0.50": "resolved",
   "decision": "resolved",
   "sign": -1
  },
  "cov": {
   "A": 0.5652173913043478,
   "B": 0.7878787878787878,
   "C": 0.7575757575757576,
   "D": 0.6666666666666666,
   "E": 0.6666666666666666,
   "F": 0.7272727272727273
  }
 },
 "luna_limited": {
  "A->B": {
   "n": 23,
   "mean_first": 1.3478260869565217,
   "mean_second": 0.6956521739130435,
   "delta": -0.6521739130434783,
   "sd_d": 1.495711920858301,
   "ci95": [
    -1.2608695652173914,
    -0.043478260869565216
   ],
   "ci90": [
    -1.173913043478261,
    -0.17391304347826086
   ],
   "n_pos": 3,
   "n_neg": 10,
   "n_zero": 10,
   "mde": 0.8732569853726612,
   "decision_0.30": "resolved",
   "decision_0.50": "resolved",
   "decision": "resolved",
   "sign": -1
  },
  "B->D": {
   "n": 33,
   "mean_first": 0.7575757575757576,
   "mean_second": 0.696969696969697,
   "delta": -0.06060606060606061,
   "sd_d": 0.555618683282088,
   "ci95": [
    -0.24242424242424243,
    0.12121212121212122
   ],
   "ci90": [
    -0.21212121212121213,
    0.09090909090909091
   ],
   "n_pos": 4,
   "n_neg": 6,
   "n_zero": 23,
   "mde": 0.270818234374624,
   "decision_0.30": "equivalent",
   "decision_0.50": "equivalent",
   "decision": "equivalent",
   "sign": -1
  },
  "cov": {
   "A": 0.30434782608695654,
   "B": 0.09090909090909091,
   "C": 0.06060606060606061,
   "D": 0.06060606060606061,
   "E": 0.09090909090909091,
   "F": 0.06060606060606061
  }
 },
 "luna_subgraph": {
  "A->B": {
   "n": 22,
   "mean_first": 2.227272727272727,
   "mean_second": 2.3181818181818183,
   "delta": 0.09090909090909091,
   "sd_d": 1.4444999434337429,
   "ci95": [
    -0.5,
    0.6818181818181818
   ],
   "ci90": [
    -0.4090909090909091,
    0.5909090909090909
   ],
   "n_pos": 6,
   "n_neg": 6,
   "n_zero": 10,
   "mde": 0.8623115836039956,
   "decision_0.30": "unresolved",
   "decision_0.50": "unresolved",
   "decision": "unresolved",
   "sign": 1
  },
  "B->D": {
   "n": 32,
   "mean_first": 2.03125,
   "mean_second": 1.875,
   "delta": -0.15625,
   "sd_d": 0.6772513232461859,
   "ci95": [
    -0.375,
    0.09375
   ],
   "ci90": [
    -0.34375,
    0.03125
   ],
   "n_pos": 2,
   "n_neg": 7,
   "n_zero": 23,
   "mde": 0.3352223022644583,
   "decision_0.30": "unresolved",
   "decision_0.50": "equivalent",
   "decision": "unresolved",
   "sign": -1
  },
  "cov": {
   "A": 0.6818181818181818,
   "B": 0.59375,
   "C": 0.5161290322580645,
   "D": 0.46875,
   "E": 0.53125,
   "F": 0.5
  }
 },
 "luna_full": {
  "A->B": {
   "n": 23,
   "mean_first": 2.652173913043478,
   "mean_second": 2.608695652173913,
   "delta": -0.043478260869565216,
   "sd_d": 0.5623215571155333,
   "ci95": [
    -0.21739130434782608,
    0.2608695652173913
   ],
   "ci90": [
    -0.17391304347826086,
    0.17391304347826086
   ],
   "n_pos": 1,
   "n_neg": 3,
   "n_zero": 19,
   "mde": 0.3283060199821005,
   "decision_0.30": "equivalent",
   "decision_0.50": "equivalent",
   "decision": "equivalent",
   "sign": -1
  },
  "B->D": {
   "n": 33,
   "mean_first": 2.515151515151515,
   "mean_second": 2.5757575757575757,
   "delta": 0.06060606060606061,
   "sd_d": 0.6585682358056159,
   "ci95": [
    -0.15151515151515152,
    0.2727272727272727
   ],
   "ci90": [
    -0.12121212121212122,
    0.24242424242424243
   ],
   "n_pos": 5,
   "n_neg": 3,
   "n_zero": 25,
   "mde": 0.32099764137257847,
   "decision_0.30": "equivalent",
   "decision_0.50": "equivalent",
   "decision": "equivalent",
   "sign": 1
  },
  "cov": {
   "A": 0.8260869565217391,
   "B": 0.8787878787878788,
   "C": 0.8181818181818182,
   "D": 0.8484848484848485,
   "E": 0.7878787878787878,
   "F": 0.8181818181818182
  }
 }
}
```

Panel-48 QWK vs Gemini (references):
```
{
 "luna_full": {
  "n_cells": 48,
  "n_clusters": 28,
  "exact": 0.4583333333333333,
  "qwk": 0.4830287206266318,
  "offset": 0.5416666666666666,
  "offset_ci95": [
   0.22916666666666666,
   0.9285714285714286
  ]
 },
 "sonnet_full": {
  "n_cells": 48,
  "n_clusters": 28,
  "exact": 0.2916666666666667,
  "qwk": 0.4979423868312758,
  "offset": -0.10416666666666667,
  "offset_ci95": [
   -0.5763867630706989,
   0.2553191489361702
  ]
 }
}
```
