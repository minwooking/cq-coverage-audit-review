# A/B/C/Bp Ontology Evaluation (LLM-as-judge)

Judge model: Qwen3-Next-80B-A3B-Instruct-FP8. 2 judges per item, rounded mean.

A = naive direct-LLM. B = all-at-once structured pipeline. C = incremental weighted builder targeting B's weak dimensions (D2 accuracy, D4 semantic richness, D5 consistency, D7 clarity).

## Graph statistics

| Metric | A | B | C | Bp |
|---|---|---|---|---|
| Classes | 94 | 7 | 7 | 7 |
| Object properties | 71 | 9 | 6 | 60 |
| Datatype properties | 8 | 1 | 2 | 1 |
| Individuals | 30 | 12 | 8 | 133 |
| Triples | 769 | 365 | 364 | 1124 |

## Layer 1 — CQ answerability (0–3 per CQ)

| CQ | Category | A | B | C | Bp |
|---|---|---|---|---|---|
| MFGCQ01 | concept_definition | 2 | 1 | 1 | 0 |
| MFGCQ02 | concept_definition | 2 | 1 | 1 | 2 |
| MFGCQ03 | taxonomy | 1 | 1 | 1 | 2 |
| MFGCQ04 | taxonomy | 1 | 0 | 1 | 1 |
| MFGCQ05 | taxonomy | 1 | 0 | 0 | 1 |
| MFGCQ06 | relations | 1 | 0 | 0 | 1 |
| MFGCQ07 | relations | 1 | 1 | 0 | 1 |
| MFGCQ08 | slots_facets | 1 | 1 | 1 | 2 |
| MFGCQ09 | slots_facets | 1 | 0 | 0 | 2 |
| MFGCQ10 | instances | 1 | 1 | 1 | 2 |
| MFGCQ11 | methodology | 2 | 1 | 1 | 1 |
| MFGCQ12 | methodology | 2 | 1 | 1 | 1 |
| **Total** |  | **16/36** | **8/36** | **8/36** | **16/36** |

## Per-category means (CQ)

| Category | A | B | C | Bp |
|---|---|---|---|---|
| concept_definition | 2.00 | 1.00 | 1.00 | 1.00 |
| instances | 1.00 | 1.00 | 1.00 | 2.00 |
| methodology | 2.00 | 1.00 | 1.00 | 1.00 |
| relations | 1.00 | 0.50 | 0.00 | 1.00 |
| slots_facets | 1.00 | 0.50 | 0.50 | 2.00 |
| taxonomy | 1.00 | 0.33 | 0.67 | 1.33 |

## Layer 2 — quality dimensions (1–5)

| Dim | Name | A | B | C | Bp |
|---|---|---|---|---|---|
| D1 | Coverage / 완전성 | 4 | 1 | 2 | 2 |
| D2 | Accuracy / 정확성 | 3 | 1 | 2 | 2 |
| D3 | Taxonomy / 계층 구조 | 3 | 2 | 2 | 2 |
| D4 | Semantic Richness / 의미 풍부성 | 5 | 2 | 2 | 2 |
| D5 | Consistency / 일관성 | 3 | 2 | 2 | 2 |
| D6 | Standard Reuse / 표준 어휘 정합 | 4 | 2 | 3 | 3 |
| D7 | Clarity / 명료성 | 4 | 2 | 2 | 2 |
| **Total** |  | **26/35** | **12/35** | **15/35** | **15/35** |

## Aggregate

| Score | A | B | C | Bp |
|---|---|---|---|---|
| CQ Coverage % | 44.4 | 22.2 | 22.2 | 44.4 |
| Quality % | 74.3 | 34.3 | 42.9 | 42.9 |
| **Overall %** | **59.4** | **28.3** | **32.5** | **43.7** |

**Winner: A**

## C vs B — targeted dimension deltas

| Dim | Name | B | C | Δ |
|---|---|---|---|---|
| D2 | Accuracy / 정확성 | 1 | 2 | +1 ↑ |
| D4 | Semantic Richness / 의미 풍부성 | 2 | 2 | +0 → |
| D5 | Consistency / 일관성 | 2 | 2 | +0 → |
| D7 | Clarity / 명료성 | 2 | 2 | +0 → |

## Qualitative summary

Winner: A. A overall 59.4% (CQ 44.4%, Quality 74.3%). B overall 28.3% (CQ 22.2%, Quality 34.3%). C overall 32.5% (CQ 22.2%, Quality 42.9%). Bp overall 43.7% (CQ 44.4%, Quality 42.9%). C-vs-B targeted dimensions: D2 1→2, D4 2→2, D5 2→2, D7 2→2.
