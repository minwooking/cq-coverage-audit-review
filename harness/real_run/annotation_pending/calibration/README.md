# Calibration practice items (out-of-scored-sample)

13 cells that are **not part of the 224 scored cells** (they were excluded from the
sealed run by the frozen RUNBOOK exclusion rules), so practicing on them cannot contaminate
the study. Fill `A`, `evidence_span_verbatim`, `rater_L1`, `note` exactly as you would in
the real pass, then compare against the table below. Results are practice — not scores,
not recorded as labels.

## Expected verdicts (with honesty caveats)

| Items | CQs | Variant | Expectation | Caveat |
|---|---|---|---|---|
| 1–10 | CQB13, 14, 18, 19, 20, 24, 32, 33, 35, 36 | A | `A=0` | Exclusion rationale: variant-A pipeline could not recover an answer for these CQs (RUNBOOK real-run exclusions). Expect no sufficient span in the A view. "Excluded" is a run-design fact, not a pre-adjudicated human verdict — if you find a genuine span anyway, that is itself calibration info: write it down. |
| 11–13 | CQB15, 22, 23 | B | likely `A=0` | Excluded corpus-rare in **all** variants; view should be sparse on the target relation. Not guaranteed empty — decide on the text, not on the exclusion story. |

## What this calibrates

The skill that matters for G1 is **not seeing support that isn't there** — all 13 items
skew negative on purpose. Positive-anchor practice comes from the rubric boundary
examples in `LABELER_GUIDE.md` §"Boundary examples" (read before the items).

## After practicing

Write one paragraph on any interpretation question you had (e.g., "is a class assertion
plus a domain/range pair enough for a 'what is X' CQ?") and resolve it **in writing now**,
against the frozen anchors — not after seeing real cells (CALIBRATION_PLAN §2).

Views: [`../views/`](../views/) (sha256-identical to the sealed `rendered_view_path` targets;
verified 2026-10-06, see [`../views/SHA256SUMS.txt`](../views/SHA256SUMS.txt)).
