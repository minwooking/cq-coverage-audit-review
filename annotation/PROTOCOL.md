# Evidence-Anchored Annotation Protocol

## Scope
This protocol applies to the frozen Brick holdout: 36 competency questions and six artifact variants (216 cells). It does not alter the bank, the preregistration, or the manuscript.

## Required inputs
For each cell, the annotator receives the same material supplied to the confirmatory judge, the opaque cell identifier, the question, and the judge's Layer-1 score (0--3). The annotator must not receive the judge rationale or score while making the evidence decision; enter the score only after the evidence verdict is recorded. Variant identity cannot be assumed blinded because content may reveal provenance.

## Layer-1 anchors
- 0: no related concept or relation.
- 1: partial: concepts present, but a key relation or hierarchy is missing.
- 2: mostly: core concept and relation present, with minor gaps.
- 3: complete.

## Evidence verdict
Set `evidence_supported` to `1` only when a verbatim span in the supplied material supports the answer to the CQ. Set it to `0` when no such span exists. Copy the shortest sufficient verbatim span, preserving punctuation and whitespace where practical; if unsupported, leave the span empty and explain briefly why no supporting span exists. Do not infer support from the graph, external sources, or the annotator's knowledge.

## Adjudicated label
For primary Brick cells only:
`L1* = J` when evidence_supported=1; otherwise `L1* = min(J, 1)`.
Coverage is `sum(L1*) / (36 * 3) * 100`. The silent over-credit event is `J >= 2 and evidence_supported = 0`.

## Blinding, order, and timing
Use the frozen seed and constrained shuffle; keep cells sharing a CQ separated by at least 20 positions. Record start/end timestamps and any interruption. Do not revise a submitted label without an audit-trail entry. Washout re-scoring is a separate pass after at least 21 days and uses a paraphrase where available.

## Human-only safeguards
The annotator must complete consent/acknowledgment procedures before scoring, retain the raw completed sheet securely, and have a second human verify the final export and de-identification. No labels, scores, names, or statistics belong in this template before collection.
