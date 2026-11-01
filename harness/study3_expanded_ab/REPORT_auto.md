# Addendum 34 results -- judge-score contrast on the expansion bank; not human-labelled

Post hoc. Views: question-only subgraphs (Study 2 Stage 2 judge views). Registered holdout judge has no route; named judges only.
Eligible clusters total 70; eligible in both A and B (the paired set) 26.
Bridge subset: not computable (expansion and holdout banks share 0 question texts, 0 groundings, disjoint ids (PLAN 34.6)).

## GLM-4.7-Flash -- primary (mean of 3 repeats)
- n clusters 26 (missing 0); mean J A 1.410, B 1.769; delta +0.359, 95% BCa [-0.154, +0.885], 90% BCa [-0.077, +0.808]
- sign test: 9 up / 9 down / 8 tied, p 1.0000; Wilcoxon p 0.1761
- MDE prospective: prespecified_1.155 0.635, holdout_J_1.343 0.738, holdout_L1star_1.473 0.809; realized sigma 1.379 -> MDE 0.758
- decision: **unresolved** (with manuscript rank rule: unresolved), margin +-0.50

## GLM-4.7-Flash -- sensitivity (median of repeats)
- n clusters 26 (missing 0); mean J A 1.500, B 1.808; delta +0.308, 95% BCa [-0.231, +0.885], 90% BCa [-0.154, +0.808]
- sign test: 8 up / 8 down / 10 tied, p 1.0000; Wilcoxon p 0.1889
- MDE prospective: prespecified_1.155 0.635, holdout_J_1.343 0.738, holdout_L1star_1.473 0.809; realized sigma 1.490 -> MDE 0.819
- decision: **unresolved** (with manuscript rank rule: unresolved), margin +-0.50

## gpt-oss-20b -- primary (mean of 3 repeats)
- n clusters 26 (missing 0); mean J A 2.256, B 1.692; delta -0.564, 95% BCa [-1.167, +0.154], 90% BCa [-1.064, +0.026]
- sign test: 4 up / 11 down / 11 tied, p 0.1185; Wilcoxon p 0.1878
- MDE prospective: prespecified_1.155 0.635, holdout_J_1.343 0.738, holdout_L1star_1.473 0.809; realized sigma 1.730 -> MDE 0.951
- decision: **unresolved** (with manuscript rank rule: unresolved), margin +-0.50

## gpt-oss-20b -- sensitivity (median of repeats)
- n clusters 26 (missing 0); mean J A 2.231, B 1.577; delta -0.654, 95% BCa [-1.346, +0.115], 90% BCa [-1.231, +0.000]
- sign test: 4 up / 10 down / 12 tied, p 0.1796; Wilcoxon p 0.1105
- MDE prospective: prespecified_1.155 0.635, holdout_J_1.343 0.738, holdout_L1star_1.473 0.809; realized sigma 1.938 -> MDE 1.065
- decision: **unresolved** (with manuscript rank rule: unresolved), margin +-0.50
