# Human evidence-labeling guide

## What to read

For each row, read exactly these three things:

1. **CQ text** (`cq_text`): the competency question.
2. **Rendered ontology view** at `rendered_view_path`: the same rendered material supplied to the judge. Search or inspect the relevant part, but do not infer beyond what is written there.
3. The row's **evidence span** field, which you will fill with the shortest sufficient verbatim span from that rendered view. Preserve punctuation and whitespace where practical.

A run may contain multiple variant cells; the builder preserves every row in `cells.jsonl`, exposes the judge's quoted evidence span for checking, and points each row to the rendered view that row's judge saw: `harness/variants/{variant}/rendered_view.txt`. Legacy single-variant smoke/dry runs used one shared `schema_view.txt` in the run directory instead; the builder falls back to it only when the per-variant views do not cover every row.

## Decision to record

Record `A=1` (**supported**) only when a verbatim span in the supplied rendered view supports an answer to the CQ. Record `A=0` (**unsupported**) when no such span exists. If unsupported, leave `evidence_span_verbatim` empty and briefly explain why in `note`. Do not use the graph, external sources, or your own domain knowledge to fill a gap.

This is an evidence decision, not a new answerability score. `A` does not mean that the answer is perfect; it asks only whether the supplied material contains a sufficient textual anchor for the CQ. The later adjudicated score is `L1*=J` when `A=1`, otherwise `L1*=min(J,1)`.

### Boundary examples from the rubric

- **A=0, related concept but missing relation:** the view names both concepts, but does not state the key relation or hierarchy asked by the CQ. This corresponds to the rubric's Layer-1 score-1 “partial” anchor; topical proximity alone is not support.
- **A=1, core concept and relation with a minor gap:** the view contains the CQ's core concept and requested relation, while a small detail is absent. This matches the rubric's “mostly” anchor (score 2); quote the span that supports the answer.
- **A=1, complete direct statement:** the view contains the concept and relation/definition needed to answer the CQ directly. This matches the rubric's “complete” anchor (score 3); quote the shortest sufficient span.

When uncertain, do not repair the source mentally. Mark `A=0` if no verbatim sufficient span can be quoted and explain the uncertainty in `note` for adjudication.

## AI draft review mode (owner primary pass only — PREREG §11, AH mode)

**Scope: this section applies only to the owner's 224-row primary pass.** The
blind second annotator never sees an AI draft; where a draft is absent, follow
the from-scratch decision procedure above.

From 2026-10-07 the owner's pass is registered as AI-drafted, human-revised
(AH): the labeling screen shows a draft card (`A`, `L1`, span, note — with the
drafting model and time) and pre-fills the input fields with it. The labels
that pass produced are called **LLM-assisted (AI-drafted, author-revised)
labels**. Your job is a review, not a rubber stamp:

- Re-derive the decision from the view before saving. The draft can be wrong
  with confidence; a plausible-looking span that fails the verbatim check is a
  wrong draft.
- Agree → press 저장 as-is (recorded as `changed=false`). Disagree → edit any
  field first; edits are recorded as `changed=true` with the draft preserved in
  the audit sidecar. **Do not avoid changing a wrong draft** — correction rate
  is itself a registered reported quantity, and suppressing corrections
  silently inflates agreement statistics.
- The draft was generated judge-blind (from the sheet and view only, never the
  verdicts) — it carries no information about `J`, so agreeing with it neither
  proves nor disproves the judge.
- The evidence rules above are unchanged: A=1 needs a verbatim view span,
  A=0 clears the span and needs a note, edits after saving need an audit
  reason. The registered 60-cells-per-session cap and 12-hour gap were removed
  during this pass (a logged deviation, PREREG §12 D5). The washout re-score
  and the second-annotator pass do NOT use drafts or translations (no draft
  file is connected to them).

## What must remain blind

Do **not** look for or record the judge's `J` score, judge rationale, or any judge response field while making the evidence decision. The packet's `judge_evidence_span` is the supplied span to verify against the CQ and rendered view; do not treat the judge's claim as proof, and do not use judge reasoning to decide support. Variant identity may be inferable from content; the protocol does not claim variant blinding.

## Order and timing

Work in the provided row order. Cells from the same CQ were shuffled using the registered seed and are intended to be separated by at least 20 positions where that is feasible (the achieved minimum is reported in the packet manifest). Record start/end timestamps and interruptions in your audit log. For the washout and second-annotator passes there is **no cap on cells per session and no minimum gap between sessions** (PREREG §12, D19): score as many cells as you like in one sitting or split the work over any number of sessions. The tool records each session's start and end and the time spent on every cell; it enforces no minimum time. (In the washout and second-annotator screens that time is measured by your browser, from opening a row to saving it, and stored as `dwell_ms` in milliseconds; you never enter it.) Aim for about 90 seconds per cell; do not rush a difficult case. Do not revise a submitted row without an audit-trail entry.

Complete consent/acknowledgment first. Calibration practice uses items outside the scored sample; follow [`../CALIBRATION_PLAN.md`](../CALIBRATION_PLAN.md). The washout re-score is a separate pass at least 21 days (target 28 days) after the last save of the first pass. It uses a new order, new opaque item IDs and the paraphrased CQ text on every row (the original CQ on the rows of a cluster whose paraphrase failed the semantic-equivalence check), and it mixes in the 36 control rows. Do not consult the primary pass while doing the washout pass, and do not open the packet's sealed mapping.

## AI chat tools (washout and second-annotator passes)

AI chat tools are permitted in these two passes (PREREG §12, D20). Using one does not change the decision rule: `A=1` still needs a verbatim span from the rendered view you were given.

- When you finish a sitting, press **세션 종료 · AI 사용 보고** (top right of the screen) and enter whether you used an AI tool (yes/no), its name, and about how many cells you used it on. You may skip the form; a skipped or unanswered report is recorded as "not recorded". Each report covers only the saves since the previous report (one sitting); reports are appended, never replaced, so give one at the end of every sitting.
- Every row has an optional **AI 사용** tick. Tick it on rows where you used an AI tool. Leaving it empty means "not recorded", not "no AI used". It never blocks saving.
- The second annotator must not see the study's own outputs: the AI drafts, the judge's output beyond the quoted span on screen, the author's labels, any LLM-assisted or persona result, or any result figure. This blind is about the study's outputs, not about AI tools.
- These two screens show no AI draft card and no translation, and hide the cell ID, CQ ID, category and variant.

## Opening the labeling screen (washout and second-annotator passes)

The person running the tool gives you one link that ends in `?token=` and a long random string. Open it once, in the browser you will use for the whole session: the page loads and the string is replaced by a cookie, so it disappears from the address bar. The link works one time only, so do not forward it or open it on a second device; if the page says a token is needed, or after the operator restarts the tool, ask for a new link. Your saves are written to disk with every save, so closing the page loses nothing. Every row needs `A` and `rater_L1` (and a span when `A=1`); the screen will not save a row without them. The second annotator also needs a `note` on every row (all four columns, DN-9) and the screen refuses a save without one; in the washout the note is optional.

## Saving

Edit only the blank round CSV assigned to you. Keep the header and `cell_id` unchanged. Fill `evidence_span_verbatim`, `A` (`0` or `1`), and `note`; do not add names, judge scores, judge rationales, or credentials. (With `label_assist.py --packet` the tool writes the working CSV for you and adds two columns: `ai_used` (`yes` where you ticked **AI 사용**, empty otherwise) and `dwell_ms` (the time on the row in milliseconds, measured by your browser). You never edit the CSV by hand.) Save the raw completed sheet securely. A second human must verify the final export and de-identification before analysis. The project owner will compute agreement and supply the released label file to `harness/analyze_holdout.py`.

The blank CSVs and scripts are scaffolding. Do not use files under `_example_from_simulated/` for real labeling.
