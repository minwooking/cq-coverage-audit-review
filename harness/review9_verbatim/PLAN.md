# PREREG addendum 29 (exploratory, post hoc) -- verbatim-span check on the 188 primary Brick holdout cells

> AI-generated draft; the author must review it before it is relied on. Date: 2026-10-18. **This addendum is post hoc: it was written after the analysis ran and after every score and every label it uses already existed.** It has no freeze commit before the data. The analysis code and its first results are the git commit `24d7166` ("harness(access): review-9 verbatim-span check on the 188 holdout cells (post hoc, no model calls)"). The manuscript sources are not edited by this file. All code and commands named here are AI-generated and must be reviewed and tested by a person before reuse.

## 29.1 Status and purpose

Exploratory and post hoc. No confirmatory hypothesis, no threshold, no equivalence margin, no multiplicity correction. No model call, no network access and no server access were used.

Purpose: the natural-document check of addendum 27 showed that the span a judge quotes often fails to occur verbatim in the view it received, and the manuscript proposed the test as a label-free audit step. This addendum asks what the test does on the Brick holdout cells, where evidence labels exist: (i) how many credits (`J >= 2`) of the registered holdout judge quote a span that occurs verbatim in the rendering the judge saw; (ii) how many of the unsupported-credit events (`J >= 2`, `S = 0`, the events of the unsupported-credit rate) fail the test (recall), and how many supported credits fail it (false-flag rate); (iii) what the unsupported-credit rate and the `A -> B` contrast become when credit is withdrawn on failing cells; (iv) the same quantities for the other judge runs already in the repository; (v) whether the AH rater's labels disagree more with the second rater's labels on cells that the AH rater saved quickly.

What this session knew before the analysis (disclosure): the registered judge's scores, the AH labels, the second rater's labels, the unsupported-credit rates (7.4% and 13.8%), the gate record, the natural-corpus verbatim results of addendum 27 and the cross-judge and rater results of addenda 26 and 28.

## 29.2 Test, credit and withdrawal (fixed in `analyze.py`)

* Test: `norm` and `verbatim` are imported from `harness/review6_natural/analyze_natural.py`, the function of addendum 27: whitespace runs collapse, the ends are stripped, the match is case sensitive and a plain substring test against the whitespace-normalised view; a list of spans passes only if every non-empty string element does; an empty or non-string span fails.
* Credit: `J >= 2`. Withdrawal: `J* = J` if `J < 2` or the span is verbatim, else `min(J, 1)`. `L1*` with the check applies the rater's rule to `J*`.
* Sensitivities (labelled as such): full withdrawal (`J* = 0` on a failing credit, `A -> B` only) and an elision-tolerant matcher (a span split at `...` or the ellipsis character; every fragment of at least 12 characters must be verbatim; a strict pass is always a pass); credit defined as `J >= 1`.
* Intervals: question-cluster BCa 95%, 10,000 resamples, seed 20260913, the analyzer's own draws (`fast_ci` equals the analyzer's function; checked in the self-test and on the headline statistics).

## 29.3 Inputs

The registered holdout judge's cells (`harness/real_run/cells.jsonl`) and the rendering of each variant (`harness/variants/<V>/rendered_view.txt`, digest equal to the artifact digest of every cell); the other judge runs (luna on the full views, the 60,000-character truncation and the subgraph views; `gpt-oss-20b` and `GLM-4.7-Flash` on the subgraph views, three repeats each; the two 48-cell panels); the AH labels and the second rater's labels as the de-identified analysis files that `harness/review6_reanalysis/` reads; the AH rater's dwell time (`audit_elapsed_s`) from the same unsealed per-cell file. The second rater's dwell time was not recorded. Per-cell labels and label disagreements are not written to any output.

## 29.4 Outputs and reproduction

`results.json` (aggregates and label-free per-cell flags), `REPORT.md` (the reading), `analyze.py` (self-test first, about 5 s), `make_tables.py` (the table bodies of manuscript Table A8 and of supplement Section S27, written from `results.json`; `--check` compares them with the sources) and this file. Reproduce: `python3 harness/review9_verbatim/analyze.py`.

## 29.5 What the addendum does not claim

It does not claim that the test measures support, that a failing span is an error of the judge, or that withdrawal improves the audit: the result is that every unsupported credit of the holdout judge quotes a verbatim span (0 of 14 events on the AH labels, 0 of 26 on the second rater's labels), that the test flags 14 credits that both raters judged supported, and that the unsupported-credit rate and the `A -> B` estimates do not change. Other judges quote less often verbatim and the test then catches and flags more, with modest lift. The dwell comparison is descriptive.
