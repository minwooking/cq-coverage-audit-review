# REPORT -- addendum 27 (exploratory): natural-document Brick corpus, A and B scored by three judges

> AI-generated report from `results.json` (written by `make_report.py`); the author must review it before use. Exploratory and post hoc; descriptive only, no decision rule and no multiplicity correction (PLAN.md 27.1, 27.A1.8). Intervals are question-clustered BCa 95% (B = 10000, seed 20260913). Code and commands in this directory are AI-generated and must be reviewed and tested before reuse; nothing here is applied to a production system. Before external use, check the numbers for internal addresses and unpublished data (none are intended; the corpus is public documentation).

## 0. What was done and what it shows

**Question.** When baseline A and the pipeline's base build B are built from hand-written Brick documentation (no schema file) and scored with the frozen 36-question bank on question-relevant subgraph views, does the A -> B contrast behave as on the template-corpus holdout, and what does a deterministic verbatim-span check change? (PLAN 27.1, 27.A1.)

**Run.** Corpus: 70 files, 859 atomic chunks, 319,329 characters (`corpus_stats.json`). Grounding check before any build: the analyst read (not blind) finds the answer present in full for 15, in part for 9 and not at all for 12 of 36 questions, so 24 of 36 (66.7%) are answerable; the stop rule (< 20%) did not fire. A and B were built with the unchanged pipeline commands on one server (1182 extractor calls, no failure). The planned judge (gpt-5.6-luna) was blocked (HTTP 402) and no luna score exists; the scoring judges are gpt-oss-20b and GLM-4.7-Flash (primary, non-Qwen) and Qwen3.8-Flash-Next (same-family contrast), three repeats each, 72 natural cells; the template A/B subgraph cells (54, 22 paired questions) were scored by the same judges (records of addendum 26 reused where the prompt checksum matched).

**Result (descriptive).** A -> B over all 36 questions: gptoss +0.370 [-0.093, +0.843]; glm +0.102 [-0.231, +0.426]; qwenflash +0.037 [-0.269, +0.398] (score points). Every interval includes zero, as on the template corpus. With the verbatim-span demotion the contrast moves to gptoss 0.000 [-0.370, +0.380]; glm +0.139 [-0.176, +0.491]; qwenflash -0.296 [-0.611, +0.019]. The share of credits (J >= 2) whose quoted span occurs verbatim in the view is lower on B views than on A views for all three judges (table 3).

## 1. Table for the manuscript (as written into `results.json`)

| judge | family | natural S_full A->B [95%] | natural S_elig A->B [95%] | template (22 q) A->B [95%] | natural-template (22 q) [95%] | verbatim J>=2 share nat A/B |
|---|---|---|---|---|---|---|
| gptoss | primary non-Qwen | +0.370 [-0.093, +0.843] | +0.472 [-0.194, +1.095] | +0.409 [-0.242, +1.045] | -0.106 [-1.030, +0.758] | 0.87/0.45 |
| glm | primary non-Qwen | +0.102 [-0.231, +0.426] | +0.111 [-0.347, +0.556] | +0.545 [-0.076, +1.182] | -0.606 [-1.379, +0.273] | 0.69/0.61 |
| qwenflash | same-family judge (contrast) | +0.037 [-0.269, +0.398] | +0.056 [-0.403, +0.569] | -0.136 [-0.697, +0.439] | +0.061 [-0.682, +0.788] | 0.94/0.32 |

Columns: judge | family | natural S_full A->B | natural S_elig A->B | template (22 q) A->B | natural minus template (22 q) | share of J >= 2 records with a verbatim span, natural A/B.

## 2. A -> B by question set (score points; BCa 95%)

| judge | set | n | coverage A, B (%) | share J >= 2 A, B (%) | A -> B | B>A / = / < |
|---|---|---|---|---|---|---|
| gptoss | S_full | 36 | 31.8, 44.1 | 27.8, 41.7 | +0.370 [-0.093, +0.843] | 12 / 19 / 5 |
| gptoss | S_elig | 24 | 43.5, 59.3 | 37.5, 58.3 | +0.472 [-0.194, +1.095] | 10 / 10 / 4 |
| gptoss | S_elig_L1 | 28 | 33.7, 47.2 | 28.6, 46.4 | +0.405 [-0.167, +0.940] | 10 / 14 / 4 |
| gptoss | S_art | 16 | 35.4, 47.2 | 31.2, 43.8 | +0.354 [-0.458, +1.000] | 6 / 8 / 2 |
| glm | S_full | 36 | 48.5, 51.9 | 50.0, 58.3 | +0.102 [-0.231, +0.426] | 13 / 10 / 13 |
| glm | S_elig | 24 | 61.1, 64.8 | 66.7, 79.2 | +0.111 [-0.347, +0.556] | 9 / 5 / 10 |
| glm | S_elig_L1 | 28 | 56.3, 56.0 | 60.7, 64.3 | -0.012 [-0.405, +0.369] | 9 / 7 / 12 |
| glm | S_art | 16 | 67.4, 67.4 | 68.8, 81.2 | 0.000 [-0.667, +0.521] | 6 / 2 / 8 |
| qwenflash | S_full | 36 | 34.6, 35.8 | 30.6, 33.3 | +0.037 [-0.269, +0.398] | 10 / 15 / 11 |
| qwenflash | S_elig | 24 | 47.7, 49.5 | 41.7, 45.8 | +0.056 [-0.403, +0.569] | 9 / 6 / 9 |
| qwenflash | S_elig_L1 | 28 | 38.1, 37.7 | 32.1, 32.1 | -0.012 [-0.393, +0.393] | 9 / 9 / 10 |
| qwenflash | S_art | 16 | 43.1, 42.4 | 37.5, 37.5 | -0.021 [-0.604, +0.604] | 7 / 3 / 6 |

Sets: S_full = all 36 questions; S_elig = questions rated full or partial by the analyst read (24); S_elig_L1 = questions passing the automated section tier (28); S_art = questions whose anchors appear in both views (16).

## 3. Verbatim-span check (descriptive; a string test, not an evidence label)

| judge | corpus | A: J >= 2 records, verbatim | B: J >= 2 records, verbatim | A -> B raw | A -> B after demotion |
|---|---|---|---|---|---|
| gptoss | natural (36 q) | 26 of 30 (0.87) | 20 of 44 (0.45) | +0.370 [-0.093, +0.843] | 0.000 [-0.370, +0.380] |
| gptoss | template (22 q) | 23 of 35 (0.66) | 23 of 55 (0.42) | +0.409 [-0.242, +1.045] | -0.076 [-0.652, +0.500] |
| glm | natural (36 q) | 42 of 61 (0.69) | 44 of 72 (0.61) | +0.102 [-0.231, +0.426] | +0.139 [-0.176, +0.491] |
| glm | template (22 q) | 20 of 35 (0.57) | 32 of 65 (0.49) | +0.545 [-0.076, +1.182] | +0.424 [-0.136, +1.030] |
| qwenflash | natural (36 q) | 33 of 35 (0.94) | 13 of 41 (0.32) | +0.037 [-0.269, +0.398] | -0.296 [-0.611, +0.019] |
| qwenflash | template (22 q) | 42 of 48 (0.88) | 40 of 52 (0.77) | -0.136 [-0.697, +0.439] | -0.212 [-0.758, +0.394] |

Rule (PLAN 27.7-4, 27.A1.8-4): a record with J >= 2 keeps its score only if its `evidence` string occurs verbatim in the view that was sent (whitespace normalized, case sensitive; a list counts only if every non-empty element does); otherwise J* = min(J, 1). Records, not cells, are counted (three repeats per cell).

## 4. Natural against template, same judge (22 questions in both corpora)

| judge | natural A -> B | template A -> B | natural minus template |
|---|---|---|---|
| gptoss | +0.303 [-0.318, +0.909] | +0.409 [-0.242, +1.045] | -0.106 [-1.030, +0.758] |
| glm | -0.061 [-0.545, +0.379] | +0.545 [-0.076, +1.182] | -0.606 [-1.379, +0.273] |
| qwenflash | -0.076 [-0.500, +0.364] | -0.136 [-0.697, +0.439] | +0.061 [-0.682, +0.788] |

Historical context only (not part of the comparison): the template A -> B under the substitute judge gpt-5.6-luna on subgraph views was +0.091 [-0.500, +0.682] on 22 questions (`harness/length_experiment`).

## 5. Agreement, stability and cost

| judge | repeat pairwise exact agreement, natural / template | all three identical, natural / template | prompt tokens (natural) | completion tokens |
|---|---|---|---|---|
| gptoss | 0.944 / 0.827 | 0.917 / 0.741 | 1,552,767 | 28,593 |
| glm | 0.787 / 0.815 | 0.694 / 0.722 | 1,537,191 | 11,908 |
| qwenflash | 0.889 / 0.883 | 0.833 / 0.833 | 1,584,723 | 12,979 |

Cross-judge agreement on the natural cells (mean over repeats): gptoss vs glm QWK 0.456, exact 0.417; gptoss vs qwenflash QWK 0.747, exact 0.639; glm vs qwenflash QWK 0.561, exact 0.519. The sign of the natural A -> B (S_full) is positive for all three judges.

## 6. Artifacts and extractor

| variant | triples | OWL classes | named individuals | rendered view (lines, characters) |
|---|---|---|---|---|
| A | 7,417 | 635 | 594 | 1,751, 275,604 |
| B | 21,080 | 12 | 2,522 | 3,175, 1,053,272 |

Artifact preflight (anchor terms present in the full rendered view): both A and B for 16 questions, A only for 6, B only for 4, neither for 10 (A 22, B 20 of 36). Extractor: 1182 calls, 373,858 prompt and 341,391 completion tokens, no failure. The full views were not scored (B's view cannot fit the 65,536-token window and the estimate exceeded the budget).

## 7. Deviations, cautions and what was not done

* **Planned judge blocked.** gpt-5.6-luna through the local proxy answered HTTP 429 and then 402 on the three in-flight calls (B:CQB01, B:CQB10, B:CQB29); by PLAN 27.6 the run stopped, the three invalid records were discarded (kept in `luna_402_discarded/` as evidence of the block), and **no luna score exists for the natural corpus** (amendment 1, commit `7500f27`). The replacement judges are not the registered holdout judge and not luna; their scores are not comparable to registered-judge or luna scores.
* **Same-family contrast judge** (amendment 2, commit `248129f`, at the author's request): Qwen3.8-Flash-Next (NVFP4 weights) shares a model line with the extractor but is a different checkpoint and quantization, so "same family" means shared lineage. It is a contrast, never a headline.
* **Extractor weights.** The extractor is addressed by the holdout build's served name, but the container behind it now serves NVFP4 weights and was started after the holdout build; the weights may differ from those of the holdout build. A and B here are matched with each other, not provably with the holdout.
* **Analyst read is not blind** (the reader had the bank's expected answers), so the 24 of 36 answerable questions are an analyst judgment; S_elig depends on it. The grounding record is frozen before any build (`grounding_check.json`).
* One corpus draw, 36 questions, three repeats per cell at temperature 0 (serving nondeterminism): an interval, not a demonstration. Judge servers were used request-only (at most three concurrent requests); nothing was installed or changed on them.
* The verbatim check is a string test: it substitutes for no human evidence label and says nothing about whether a verbatim span answers the question.
* Not done: the full-view condition (budget and window), a second natural corpus, a natural-document bank written independently of the schema, human labels on the natural cells.

## 8. Files

`PLAN.md` (committed before any build or call, with amendments 27.A1 and 27.A2), `SOURCES.md`, `GROUNDING.md`, `grounding_check.json`, `corpus/` (fetched files with checksums, cleaned text, `natural_corpus.json`), `corpus_stats.json`, `variants/{A,B}/`, `inputs/` (subgraph texts and manifest), `jobs_natural.jsonl`, `raw/` (per-call records), `results.json`, `analyze_natural.py`, `make_report.py`, `REPORT.md`. Re-run the analysis: `python3 analyze_natural.py` (reads `raw/` and the frozen inputs), then `python3 make_report.py`.
