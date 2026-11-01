# Protocol discrepancies requiring human decision

These items are recorded without changing `PREREG.md`, `annotation/PROTOCOL.md`, `annotation/CALIBRATION_PLAN.md`, or the rubric. A project owner must resolve them before collection or document the binding interpretation in the freeze record.

## 1. Judge score visibility versus packet contents

- `annotation/PROTOCOL.md:7` says the annotator receives the judge's Layer-1 score (0--3), then says the score must remain unavailable while the evidence decision is made and may be entered only after the evidence verdict is recorded.
- `annotation/CALIBRATION_PLAN.md:7` repeats the sealed-score workflow: keep the judge score unavailable until the evidence decision is saved, then enter it from the sealed score source.
- `annotation/SCORING_SHEET_TEMPLATE.csv:1` includes `J_judge` as a column.
- The packet builder (`annotation/packet/build_label_packet.py`, output schema) intentionally omits `J_judge`, and the generated packet CSVs contain no judge score or judge rationale.

**Decision required:** determine whether the binding pre-registration requires a post-verdict score-entry workflow (score supplied after A is recorded) or whether the packet is required to remain fully score-free and the owner joins sealed J values later. The packet does not silently choose between these interpretations; it follows the requested score-free handoff for tomorrow's evidence pass.

## 2. CSV ingestion path in `analyze_holdout.py` — resolved

- `harness/analyze_holdout.py` now accepts `--labels` for the primary packet and
  joins `A` to the JSONL records by `cell_id`; label-only and unexpected
  cell-only IDs fail with the offending IDs listed.
- Blank or non-binary `A` values fail by default. `--allow-partial` is an
  explicit opt-in that omits unlabeled cells from the coverage denominator and
  records the IDs, counts, fraction, and denominator formula in
  `label_coverage`.
- `--labels-washout` validates the reassessment packet and computes the
  matched `rater_L1` G2 point estimate. CSV provenance is required unless
  `--label-source` supplies it; unknown provenance cannot be inferred as human.
  Output records `label_source` and `SIMULATED`.
- Regression coverage is in `harness/test_analyze_holdout.py` (join,
  identifier mismatch, invalid/blank `A`, one-sided demotion, and missing
  provenance). The released command is therefore available without changing
  `PREREG.md` or the rubric.
