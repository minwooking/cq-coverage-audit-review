# Human evidence-labeling packet

**This packet is scaffolding. Do not enter human labels in this repository.**
`PREREG.md` is authoritative if any convenience wording differs.

## Files

- `LABELER_GUIDE.md`: one-page operating instructions and boundary examples.
- `labels_primary_pass_blank.csv`, `labels_washout_reassessment_pass_blank.csv`: populated, label-blank sheets for the sealed 224-cell `real_run` judge pass (224 primary + preregistered 72 washout rows; built by the builder on 2026-09-21, commit 3e3a9e4; cell_ids verified to match `real_run/cells.jsonl` exactly, no labels filled). An earlier wording called these "header-only placeholders" — that predates the real-run build and no longer describes them.
- `build_label_packet.py`: run with a completed judge-run directory containing `cells.jsonl`; each row is pointed at its variant's `harness/variants/{variant}/rendered_view.txt` (a shared `schema_view.txt` in the run directory is accepted as a legacy fallback). It writes the primary pass and the same-annotator washout reassessment pass with deterministic orders (seeds 20260913 and 20260914). A run with fewer than 72 cells cannot produce the preregistered washout subset and is explicitly warned.
- `ADJUDICATION_TEMPLATE.md`: disagreement resolution and audit record.
- `compute_agreement.py`: binary Cohen's kappa, raw agreement, and disagreement IDs for two aligned exports.
- `test_compute_agreement.py`: standalone tests (`uv run pytest annotation/packet -q`).
- `_example_from_simulated/`: **SIMULATED — 실제 라벨링에 쓰지 말 것**; generated from `harness/simulated_run/`, not a real judge run.
- `PROTOCOL_DISCREPANCIES.md`: cross-file issues that must be resolved before collection.

## Tomorrow's order

1. Complete `../CONSENT_TEMPLATE.md` and secure-storage/acknowledgment steps.
2. Run calibration using `../CALIBRATION_PLAN.md`; practice items must be outside the scored sample.
3. Run the primary pass in row order. Record the shortest verbatim evidence span, `A` (`0` or `1`), and note. No per-session cell cap and no minimum gap between sessions (PREREG §12, D19); dwell per cell is logged instead.
4. Preserve the raw primary-pass export and audit timestamps.
5. After at least 21 days (earliest 2026-10-30, target on or after 2026-11-06), run the same annotator's washout pass on the packet built by `harness/build_washout_packet.py` (72 primary cells plus the 36 controls, opaque IDs, frozen paraphrases; PREREG §12.3). Do not consult the primary pass. AI chat tools are permitted; record their use in the session-end form (D20).
6. Run `compute_agreement.py` for binary A consistency if aligned exports are available. This is diagnostic only; preregistered G2 is ordinal intra-rater QWK on 0–3 `rater_L1` scores and requires the separate registered CI method.
7. Resolve disagreements with `ADJUDICATION_TEMPLATE.md`, preserving both raw exports.
8. Keep the approved raw CSV exports immutable and pass them directly to `harness/analyze_holdout.py` with `--labels` (and `--labels-washout` for G2). Use `--label-source human` when the export has no provenance column. The analyzer joins by `cell_id`, validates every `A`, and records the label provenance; it does not require mutating `cells.jsonl`.
