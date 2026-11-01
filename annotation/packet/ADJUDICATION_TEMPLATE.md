# Adjudication record template

Use this only after the primary-pass and washout-reassessment exports from the same annotator are complete and consistency has been computed. This is not an inter-rater adjudication: do not describe the two passes as independent raters. Do not edit either raw export to resolve a disagreement. Preserve both original exports and record every decision below.

## Procedure

1. Freeze and hash the two raw pass exports; confirm the washout export is the preregistered matched subset and that each `A` is `0` or `1`.
2. Produce the disagreement list with `compute_agreement.py`.
3. For each disagreement, a designated adjudicator reads the CQ and the same rendered ontology view, without using `J` or judge rationale. Apply the protocol definition: `A=1` only if a verbatim span in the supplied material supports the answer; otherwise `A=0`.
4. Record the adjudicator's shortest sufficient span (or leave it empty), decision, and reason below. If the protocol cannot resolve the case, retain both original labels, record the unresolved status, and do not silently choose a value.
5. Keep a separate audit trail. A post-submission change to a raw label requires an explicit reason, timestamp, and reviewer sign-off.
6. Only after the adjudication record and sealed exports are checked should the project owner derive `L1*` and pass the approved label file to `harness/analyze_holdout.py`.

## Disagreement log

Copy one block per disagreement. Use the actual opaque `cell_id`; do not add judge score or judge rationale.

```text
cell_id:
primary_pass_A:
washout_reassessment_pass_A:
adjudicator_A:        # 0 or 1
CQ text:
rendered_view_path:
adjudicator_evidence_span_verbatim:
reason:
status:                # resolved / unresolved
adjudicator_id:
started_utc:
completed_utc:
raw_exports_hashes:
reviewer_check:
reviewer_utc:
```

## Release checklist

- [ ] Consent/acknowledgment retained.
- [ ] Raw round exports are preserved read-only.
- [ ] Cell IDs and row counts match.
- [ ] Every disagreement has a completed block or is explicitly unresolved.
- [ ] Evidence spans are verbatim and traceable to the rendered view.
- [ ] No judge `J`, rationale, names, or endpoint credentials entered the label package.
- [ ] A second human verified export integrity and de-identification.
- [ ] Approved labels are mapped back to the run's cell records only by the project owner.
