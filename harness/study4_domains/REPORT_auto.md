# Addendum 35 results -- judge-score contrast on standards-based domains; not human-labelled; exploratory

Post hoc, judge-score only. Banks are AI drafts not reviewed by an author. Extractor: the paper's model id on a different serving deployment; judges GLM-4.7-Flash and gpt-oss-20b (non-Qwen), each its own analysis. Views: question-only sub-graphs (not the full renderings).

- build dcat: 426 chunks / 114539 chars; triples A 1877, B 4271; baseline sections skipped 1; extractor calls failed 0; jobs 54; eligible-but-no-subgraph []
- build ssn: 433 chunks / 103172 chars; triples A 2057, B 5922; baseline sections skipped 3; extractor calls failed 0; jobs 83; eligible-but-no-subgraph []
- build prov: 458 chunks / 122405 chars; triples A 2398, B 6015; baseline sections skipped 3; extractor calls failed 0; jobs 77; eligible-but-no-subgraph ['primary:A:CQP38', 'primary:B:CQP38']

## dcat -- GLM-4.7-Flash
- bank 42 questions; eligible clusters: A 28, B 26, both 21; records 162 (0 invalid)
- coverage (both-eligible set, 100*sumJ/3n): A 68.8, B 73.5; all-eligible: A 66.7 (n 28), B 71.8 (n 26)
- n 21 (missing 0); mean J A 2.063, B 2.206; delta +0.143, 95% BCa [-0.111, +0.536], 90% BCa [-0.063, +0.460]
- sign test 5 up / 4 down / 12 tied, p 1.0000; Wilcoxon p 0.5508
- MDE: prespecified_1.155 0.706, holdout_J_1.343 0.821; realized sigma 0.727 -> 0.444
- decision **equivalent** (rank rule: equivalent), margin +-0.50
- verbatim-span check (credits J>=2): A: 35/66 strict, 35/66 elision-tolerant; B: 26/69 strict, 33/69 elision-tolerant

## dcat -- gpt-oss-20b
- bank 42 questions; eligible clusters: A 28, B 26, both 21; records 162 (0 invalid)
- coverage (both-eligible set, 100*sumJ/3n): A 81.0, B 67.7; all-eligible: A 75.0 (n 28), B 65.0 (n 26)
- n 21 (missing 0); mean J A 2.429, B 2.032; delta -0.397, 95% BCa [-1.063, +0.302], 90% BCa [-0.952, +0.175]
- sign test 2 up / 7 down / 12 tied, p 0.1797; Wilcoxon p 0.3555
- MDE: prespecified_1.155 0.706, holdout_J_1.343 0.821; realized sigma 1.608 -> 0.983
- decision **unresolved** (rank rule: unresolved), margin +-0.50
- verbatim-span check (credits J>=2): A: 45/63 strict, 45/63 elision-tolerant; B: 15/49 strict, 19/49 elision-tolerant

## ssn -- GLM-4.7-Flash
- bank 42 questions; eligible clusters: A 42, B 41, both 41; records 249 (0 invalid)
- coverage (both-eligible set, 100*sumJ/3n): A 61.2, B 78.6; all-eligible: A 61.9 (n 42), B 78.6 (n 41)
- n 41 (missing 0); mean J A 1.837, B 2.358; delta +0.520, 95% BCa [+0.244, +0.846], 90% BCa [+0.285, +0.797]
- sign test 19 up / 4 down / 18 tied, p 0.0026; Wilcoxon p 0.0045
- MDE: prespecified_1.155 0.505, holdout_J_1.343 0.588; realized sigma 1.003 -> 0.439
- decision **resolved** (rank rule: resolved), margin +-0.50
- verbatim-span check (credits J>=2): A: 55/90 strict, 55/90 elision-tolerant; B: 62/106 strict, 64/106 elision-tolerant

## ssn -- gpt-oss-20b
- bank 42 questions; eligible clusters: A 42, B 41, both 41; records 249 (1 invalid)
- coverage (both-eligible set, 100*sumJ/3n): A 72.1, B 61.5; all-eligible: A 71.2 (n 42), B 61.5 (n 41)
- n 41 (missing 0); mean J A 2.163, B 1.846; delta -0.317, 95% BCa [-0.789, +0.187], 90% BCa [-0.708, +0.098]
- sign test 7 up / 14 down / 20 tied, p 0.1892; Wilcoxon p 0.2617
- MDE: prespecified_1.155 0.505, holdout_J_1.343 0.588; realized sigma 1.602 -> 0.701
- decision **unresolved** (rank rule: unresolved), margin +-0.50
- verbatim-span check (credits J>=2): A: 61/87 strict, 62/87 elision-tolerant; B: 25/74 strict, 32/74 elision-tolerant

## prov -- GLM-4.7-Flash
- bank 41 questions; eligible clusters: A 41, B 38, both 38; records 231 (0 invalid)
- coverage (both-eligible set, 100*sumJ/3n): A 68.2, B 77.2; all-eligible: A 66.9 (n 40), B 77.2 (n 37)
- n 37 (missing 1); mean J A 2.045, B 2.315; delta +0.270, 95% BCa [+0.018, +0.595], 90% BCa [+0.045, +0.541]
- sign test 13 up / 11 down / 13 tied, p 0.8388; Wilcoxon p 0.0801
- MDE: prespecified_1.155 0.532, holdout_J_1.343 0.619; realized sigma 0.909 -> 0.419
- decision **resolved** (rank rule: resolved), margin +-0.50
- verbatim-span check (credits J>=2): A: 30/90 strict, 33/90 elision-tolerant; B: 53/101 strict, 58/101 elision-tolerant

## prov -- gpt-oss-20b
- bank 41 questions; eligible clusters: A 41, B 38, both 38; records 231 (0 invalid)
- coverage (both-eligible set, 100*sumJ/3n): A 67.3, B 70.0; all-eligible: A 64.7 (n 40), B 70.0 (n 37)
- n 37 (missing 1); mean J A 2.018, B 2.099; delta +0.081, 95% BCa [-0.477, +0.586], 90% BCa [-0.387, +0.505]
- sign test 11 up / 9 down / 17 tied, p 0.8238; Wilcoxon p 0.8806
- MDE: prespecified_1.155 0.532, holdout_J_1.343 0.619; realized sigma 1.656 -> 0.763
- decision **unresolved** (rank rule: unresolved), margin +-0.50
- verbatim-span check (credits J>=2): A: 37/78 strict, 38/78 elision-tolerant; B: 25/77 strict, 33/77 elision-tolerant

## pooled over dcat, ssn, prov -- GLM-4.7-Flash
- n 99 ({'dcat': 21, 'ssn': 41, 'prov': 37}); delta +0.347, 95% BCa [+0.182, +0.542], 90% [+0.209, +0.508]; sign 37/19/43 p 0.0222; Wilcoxon p 0.0007; MDE prespecified_1.155 0.325, holdout_J_1.343 0.378, realized 0.259; decision **resolved**

## pooled over dcat, ssn, prov -- gpt-oss-20b
- n 99 ({'dcat': 21, 'ssn': 41, 'prov': 37}); delta -0.185, 95% BCa [-0.505, +0.145], 90% [-0.448, +0.088]; sign 20/30/49 p 0.2026; Wilcoxon p 0.2678; MDE prespecified_1.155 0.325, holdout_J_1.343 0.378, realized 0.456; decision **equivalent**
