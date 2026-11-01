# PREREG addendum 33 -- preserved-control labels on the Study 2 labeler (post hoc, small)

> **LLM-labeled; post hoc; not human-validated.** AI-generated draft; the author must review it before it is relied on. Date: 2026-10-19. This file is committed alone, before any model call of this addendum. `main.tex`, `main_ko.tex` and `supplement.tex` are not edited by this addendum. All code and commands named here are AI-generated and must be reviewed and tested by a person before reuse; none of it is to be applied to a production system without that review. Before this file or any output is shared outside the team, check that no confidential company information, host name, address, port, key or personal data is in it.

## 33.1 Purpose and status

Addendum 32 (Study 2) labeled the 188 primary cells and the 24 registered **ablated** controls (anchor lines removed from the rendering): both primary models marked 22 of the 24 ablated controls `S = 0`. That is the sensitivity side of a control pair. This addendum adds the **specificity counterpart**: the 12 registered **preserved** (non-ablated) controls, whose rendering still holds the anchor lines. The question is whether the same labeler, under the same rule, marks cells with intact evidence `S = 1`, so that the 22/24 result is not a labeler that says `S = 0` everywhere.

**Status.** Post hoc: the 12 preserved controls were not part of the Study 2 manifest, and the choice to label them was made after the Study 2 results were known. It replaces no human label, changes no gate and no headline number of the paper, and is reported whatever the outcome.

**What this session knew before this commit.** (i) The Study 2 aggregates, including 22 of 24 ablated controls labeled `S = 0` by both models and gate FAIL; (ii) the registered judge's scores of the 12 preserved cells are in the committed `harness/real_run/cells.jsonl` (these are the paper's own seeded-control numbers: mean `J` 2.167, `J >= 2` on 10 of 12); (iii) no view of these 12 cells was built under the Study 2 builder, no model call was made on them under the Study 2 labeler. No human label is read by this addendum, and no per-cell human label of any control is used.

## 33.2 Method (unchanged from addendum 32; nothing is re-tuned)

* **Cells.** The 12 cells with `cell_kind = preserved_control` in `harness/real_run/cells.jsonl`: `F:CQB04, F:CQB20, C:CQB08, F:CQB03, A:CQB11, D:CQB29, C:CQB09, B:CQB01, F:CQB31, E:CQB20, E:CQB36, D:CQB03` (cell ids carry the prefix `preserved_control:`).
* **View builder.** Exactly `s2_views.build_view` of addendum 32 (PLAN 32.4, parameters N = 600, LINE_CAP = 4000, CAP_CHARS = 100,000, MIN_CHARS = 2,000, FALLBACK_CAP = 20,000), on the **unablated full rendering** of the cell's variant, the bank row's `grounding` and `question`, and the registered judge's quoted evidence of that cell as the span (as for the primary cells). The bank's `expected_answer` is read only to measure the term coverage of the view, as in Stage 1. The builder is invoked by a new manifest function `s2_cells.py preserved` (`manifests/preserved.json`); that function only selects the 12 cells and calls the same code path as the primary cells; no rule changes.
* **Labeler.** The five personas of addendum 30 (`domain`, `ontology`, `auditor`, `kgqa`, `generalist`) x seeds 1..5 at temperature 0.7 = 25 slots per cell and model, system prompt = persona preamble + `NEW_BASE` (`s2_personas.py`, unchanged), user message built as in Stage 1, a fresh request per slot, `R_raw` without a floor, span check against the view the model saw, at most two retries on an unparsable reply. Runner: `s2_run_labels.py` with one added `--stage preserved` choice (manifest and raw-file name only).
* **Models.** `GLM-4.7-Flash` and `gpt-oss-20b`, the vLLM endpoints on the shared server host, request only, reached through an SSH port-forward (as in Study 2); the tunnel is closed when the run ends. Nothing is started, stopped, restarted or reconfigured on the host; the shared server is not touched; Qwen is not run. Keys come from the environment and are never printed or written; no host name, address or port is written to any committed file. Concurrency 8 per model with the courtesy gate on. Records are appended to `raw/<model>_preserved.jsonl` (resumable: a slot with a terminal record is not sent again), committed gzip-compressed like the Stage 1 raw files.
* **Cell label and consistency rule (Study 2, unchanged).** Cell label = majority of the valid `S_final` slots (needs >= 15 valid slots of 25; a tie or fewer valid slots leaves the cell undefined, counted). A cell is *consistent* if at least 23 of the 25 `S_final` agree (R25).

## 33.3 Outcome measures (fixed here, before any call)

Per model (`glm`, `gptoss`), over the 12 preserved controls:

* **(a)** the number of controls the 25-label majority marks `S = 1`;
* **(b)** the number of controls that are consistent under the Study 2 rule (>= 23 of 25 agree, on either label);
* **(c)** the number of controls that are consistent **and** `S = 1`.

For **both models** the same three counts are reported as the number of controls that satisfy the condition under **each** of the two models (the intersection). Also reported: undefined cells, the number of valid slots, the view term coverage of the 12 views, and the registered judge's `J` of the cells that are marked `S = 0`, for context only. There is no threshold, no pass/fail and no gate. The comparison figure is the 22 of 24 ablated controls labeled `S = 0` (Study 2, `results_stage1.json`). The result is reported whatever it is; if the labelers mark many preserved controls `S = 0`, that is stated as a limitation of the 22/24 result.

## 33.4 Order of work

1. This file, committed alone (the freeze).
2. Manifest function, runner choice, analysis script and a synthetic test, committed before the first call; tokenizer preflight (no generation) on the 12 views.
3. Labeling runs on both models; tunnel closed.
4. Analysis, `results_preserved.json` and `REPORT_preserved.md`, raw files gzip-compressed, committed. Any change after the first call goes to `DEVIATIONS.md`.
