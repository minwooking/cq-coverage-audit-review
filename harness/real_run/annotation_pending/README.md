# Annotation pending — ready-to-fill sheets for the 224-cell Brick holdout

Additive, derived files created 2026-10-06 by the pre-positioning audit.
Nothing sealed was modified; sealed inputs live one level up
(`../cells.jsonl`, `../MANIFEST.json`) and their digests are recorded in
`DIGESTS.txt`.

## Contents

- `primary_pass_224_ready_to_fill.csv` — byte-copy of
  `annotation/packet/labels_primary_pass_blank.csv` (224 rows; 188 primary +
  24 ablated + 12 preserved; every `A`, `rater_L1`, `evidence_span_verbatim`
  blank). Row order is the registered-seed shuffle (seeds 20260913/20260914,
  built by `annotation/packet/build_label_packet.py` per PREREG addendum,
  commit 3e3a9e4).
- `washout_pass_72_ready_to_fill.csv` — byte-copy of
  `annotation/packet/labels_washout_reassessment_pass_blank.csv` (72 rows,
  preregistered n=72; separate pass after >=21 days, target 28).
- `DIGESTS.txt` — SHA-256 of the sealed run artifacts, both sheets, and the
  six `harness/variants/*/rendered_view.txt` the annotator reads.
- `OWNER_RUNBOOK.md` — start here: the owner's end-to-end cycle (consent →
  calibration → 4 primary sessions → second-human check → >=21-day washout →
  sealed analysis), with the proposed calendar and the exact analysis command.
- `views/rendered_view_{A..F}.txt` — local byte-copies of the six sealed
  rendered views (sha256-identical to the `rendered_view_path` targets in the
  sheets, verified 2026-10-06; see `views/SHA256SUMS.txt`). Stable path for a
  multi-week labeling cycle; the sheets' absolute paths resolve to identical
  bytes in the run worktree. E and F are byte-identical by design.
- `calibration/practice_items_13.csv` — 13 out-of-scored-sample practice
  items (10 variant-A-only exclusions + 3 corpus-rare CQs), blank, with
  expectations + caveats in `calibration/README.md`.

## About sealing

No pre-labeling sealing step (e.g. hashing `cells.jsonl`) is defined in
`annotation/PROTOCOL.md` or `harness/RUNBOOK_REAL_RUN.md`; PREREG's only
"sealed" wording (sec. around line 864) concerns owner-only answer-key
storage for the earlier instrument study. `DIGESTS.txt` is therefore an
additive provenance record chosen for this handoff, NOT a pre-registered
sealing act. If labels are returned, re-verify these digests before merging.

## Procedure for the human annotator

Follow `../../../annotation/packet/LABELER_GUIDE.md` and
`../../../annotation/packet/README.md` ("Tomorrow's order"): consent →
calibration → primary pass in row order (no session cap or minimum gap,
PREREG §12 D19; ~90 s/cell is guidance only) → >=21-day washout pass
(PREREG §12.3) → second-annotator export check (§12.4). Labels are entered OUTSIDE this repository; return the filled
CSVs, never commit them here. `J_judge` stays hidden until the verdict is
saved (open discrepancy #1 in `annotation/packet/PROTOCOL_DISCREPANCIES.md`:
owner decides post-verdict score entry vs. later sealed-J join).

## After labels return (do NOT run before then)

```bash
cd paper/access2026
uv run pytest harness/test_analyze_holdout.py -q
uv run python harness/analyze_holdout.py harness/real_run/cells.jsonl \
  --labels <primary_pass_filled.csv> \
  --labels-washout <washout_filled.csv> \
  --label-source human --seed 20260913 \
  --out harness/real_run/holdout_results.json
```

Until then, no human labels exist (`analyze_holdout` refuses blank `A`), and
the only analyzer output on disk is the disclosed non-confirmatory
`llm_auxiliary_results.json` (label_source "LLM, not human").
