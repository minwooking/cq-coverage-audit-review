# Paired AI audit, stages 1-3: three-judge J comparison (EXPLORATORY, POST HOC)

Two AI judges of distinct families (OpenAI `gpt-5.6-luna`, Anthropic `anthropic/claude-sonnet-5-5`) scored the
registered 48 cells; the registered Gemini J scores come from `real_run/cells.jsonl` (read only).
This is an AI-vs-AI agreement table, not human evidence, not a validation, not a G6 evaluation; the registered
G1/G5/G7 gate failures stand. Nothing here goes into the manuscript except through `BRIEF.md` and human review.

## Completeness (what the numbers are computed on)

- luna: 48/48 cells (A3 B9 C13 D7 E10 F6).
- sonnet: **48/48** cells. Stage 2 stopped at 25/48 on an Anthropic HTTP 429; stage 3 (resumed 2026-10-09
  13:32 UTC, workers 2, no retry loop) scored the remaining 23 cells (D7 E10 F6) without a failure.
- Analyzer (`paired_analysis.json`): `computed`, 48 paired cells, 28 CQ clusters, no missing cells.
  This supersedes the earlier `computed_on_partial_data` result (25 cells).
- All intervals resample CQ clusters (not cells). The analyzer interval is BCa; the three-way table below uses a
  plain percentile cluster bootstrap (5000 resamples, seed 20261009) and is descriptive only.
- Decoding is asymmetric: luna temperature 0.0; sonnet at the model default (its API rejects `temperature`).
  Neither run is guaranteed bit-reproducible (reasoning models behind a proxy).
- Cells were scored over three invocations at different times; sonnet's stage-3 cells (D-F) carry prompts of about
  0.97-0.98M tokens each (above the proxy's 272k higher-price tier).

## Luna vs Sonnet (analyzer output, 48 paired cells, 28 clusters)

| metric | estimate | 95% CI (BCa, CQ clusters) |
|---|---|---|
| exact agreement | 0.375 | 0.22 - 0.55 |
| QWK | 0.347 | 0.13 - 0.56 |
| binary kappa (J>=2), supplementary | 0.253 | 0.04 - 0.51 |
| mean signed diff (sonnet - luna) | -0.65 | -0.94 - -0.35 |
| mean abs diff | 0.81 | 0.57 - 1.07 |

Confusion counts (rows luna J 0..3, columns sonnet J 0..3):
`[[0,0,0,0],[1,6,1,1],[0,7,0,1],[0,8,11,12]]`. Share J>=2: luna 0.81, sonnet 0.54.
Binary kappa carries a skewed-prevalence caution; cite descriptively.

## Three-way table against the registered Gemini J (all pairs 48 cells, 28 clusters)

| pair | exact agreement (95% CI) | QWK (95% CI) | mean diff (2nd - 1st) (95% CI) |
|---|---|---|---|
| luna - Gemini | 0.458 (0.29 - 0.62) | 0.483 (0.30 - 0.65) | -0.54 (-0.89 .. -0.23), Gemini lower |
| sonnet - Gemini | 0.292 (0.15 - 0.44) | 0.498 (0.24 - 0.70) | +0.10 (-0.30 .. 0.51) |
| luna - sonnet | 0.375 (0.23 - 0.55) | 0.347 (0.15 - 0.56) | -0.65 (-0.93 .. -0.34), sonnet lower |

Confusion counts (rows first judge, columns second judge, levels J 0..3):
- luna (rows) vs Gemini (cols): `[[0,0,0,0],[7,0,1,1],[5,0,0,3],[2,2,5,22]]`
- sonnet (rows) vs Gemini (cols): `[[1,0,0,0],[12,1,1,7],[1,0,2,9],[0,1,3,10]]`
- luna (rows) vs sonnet (cols): `[[0,0,0,0],[1,6,1,1],[0,7,0,1],[0,8,11,12]]`

J marginals (counts J0, J1, J2, J3), 48 cells: Gemini [14, 2, 6, 26]; luna [0, 9, 8, 31]; sonnet [1, 21, 12, 14].
All three identical on 9 of 48 cells.

Reading notes: luna and sonnet differ systematically (sonnet lower by 0.65 J on average, CI excludes 0). Gemini
places 14 of 48 cells at J0 where luna places none and sonnet one; sonnet places 12 of those 14 at J1. Sonnet-Gemini
exact agreement is the lowest of the three pairs but QWK is the highest; the intervals of the three pairs overlap on
both metrics, so the data do not separate the pairs. Agreement between AI judges is not correctness, and low exact
agreement here mostly reflects level offsets (J0 vs J1, J2 vs J3), not random disagreement.

## Per-variant exact agreement (matching cells / cells scored by both)

| variant | luna-Gemini | luna-sonnet | sonnet-Gemini |
|---|---|---|---|
| A | 1/3 | 1/3 | 1/3 |
| B | 4/9 | 1/9 | 1/9 |
| C | 5/13 | 4/13 | 4/13 |
| D | 5/7 | 3/7 | 2/7 |
| E | 4/10 | 5/10 | 5/10 |
| F | 3/6 | 4/6 | 1/6 |

Cell counts of 3-13 per variant: no per-variant interval is attempted; read as counts only.

## Appendix: per-cell J

| cell | Gemini (registered) | luna | sonnet |
|---|---|---|---|
| A:CQB02 | 3 | 3 | 2 |
| A:CQB09 | 1 | 3 | 3 |
| A:CQB26 | 0 | 1 | 0 |
| B:CQB01 | 2 | 3 | 1 |
| B:CQB05 | 3 | 3 | 3 |
| B:CQB13 | 3 | 3 | 2 |
| B:CQB18 | 3 | 3 | 2 |
| B:CQB19 | 3 | 2 | 1 |
| B:CQB27 | 3 | 1 | 2 |
| B:CQB29 | 3 | 3 | 1 |
| B:CQB32 | 0 | 2 | 1 |
| B:CQB33 | 0 | 2 | 1 |
| C:CQB01 | 3 | 2 | 3 |
| C:CQB02 | 3 | 3 | 3 |
| C:CQB03 | 3 | 3 | 1 |
| C:CQB11 | 0 | 1 | 1 |
| C:CQB14 | 2 | 3 | 2 |
| C:CQB16 | 3 | 3 | 3 |
| C:CQB18 | 3 | 3 | 2 |
| C:CQB19 | 3 | 3 | 1 |
| C:CQB20 | 3 | 2 | 1 |
| C:CQB26 | 0 | 3 | 1 |
| C:CQB28 | 0 | 1 | 1 |
| C:CQB35 | 0 | 2 | 1 |
| C:CQB36 | 0 | 3 | 2 |
| D:CQB06 | 3 | 3 | 3 |
| D:CQB10 | 3 | 3 | 3 |
| D:CQB18 | 3 | 3 | 2 |
| D:CQB19 | 3 | 3 | 1 |
| D:CQB29 | 3 | 3 | 1 |
| D:CQB30 | 2 | 1 | 3 |
| D:CQB32 | 0 | 1 | 1 |
| E:CQB01 | 3 | 3 | 3 |
| E:CQB07 | 3 | 3 | 3 |
| E:CQB10 | 3 | 3 | 3 |
| E:CQB12 | 2 | 3 | 3 |
| E:CQB18 | 2 | 3 | 2 |
| E:CQB19 | 3 | 3 | 2 |
| E:CQB20 | 0 | 2 | 1 |
| E:CQB24 | 0 | 1 | 1 |
| E:CQB26 | 1 | 3 | 1 |
| E:CQB33 | 0 | 2 | 1 |
| F:CQB07 | 3 | 3 | 3 |
| F:CQB08 | 2 | 3 | 3 |
| F:CQB14 | 3 | 3 | 2 |
| F:CQB20 | 0 | 1 | 1 |
| F:CQB34 | 0 | 1 | 1 |
| F:CQB36 | 3 | 3 | 2 |
