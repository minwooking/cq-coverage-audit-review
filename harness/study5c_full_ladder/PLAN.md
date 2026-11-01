# PREREG addendum 36, amendment C (exploratory, post hoc) -- the full A-F ladder on the three new W3C domains

> AI-generated draft; the author must review it before it is relied on. Date: 2026-10-20. Post hoc: written after addendum 36 and amendment B and with knowledge of their results (A->B and A->F/B->F judge-score contrasts on DCAT, SOSA/SSN, PROV). This file is committed alone, before any model call of this amendment (only local file listings and hash checks were made). `main.tex`, `main_ko.tex`, `supplement.tex`, `study5_judge_panel/` and `study5b_small_judges/` are not touched (code is imported or copied, never edited there). All code named here is AI-generated and must be reviewed and tested by a person before reuse; none of it is to be applied to a production system. Before this file or any output is shared outside the team, check that no confidential company information, host name, address, port, key or personal data is in it.

## C.1 Question

Author question: "why only B when C and D exist". Study 5 scored A, B and F on DCAT, SOSA/SSN and PROV. The intermediate variants C, D, E were built by the same run as F (the C-F steps of the pipeline, one command log per domain) but never scored. This amendment scores them so the full ladder A-F is available with the judge panel, as it is for the Brick holdout. Exploratory, judge-score only, no human labels, no confirmatory hypothesis. Results are reported whatever they show; no threshold, margin, seed or rule is changed after any score is seen.

## C.2 Cells

* A, B, F cells and their scores are those of addendum 36 (`study5_judge_panel/`): reused, not re-requested (prompts byte-identical; A/B from Study 4's stored jobs, F from addendum 36's packaging).
* **New C, D, E cells.** The graphs are `<domain>/work/ontology_{C,D,E}.ttl` of the addendum 36 F build (same build log, same work directory as `ontology_F.ttl`; the log shows build-c, refine-d, build-d, select-standards, build-e, build-f all OK in one run; sha256 of each graph is recorded in the variant MANIFEST). Each is packaged and viewed exactly as F was: full rendering by `run_simulated.schema_view`, question-only sub-graph view (hop 2) by `length_experiment/make_inputs.generate` (the bank text of the question only; the bank's expected answer is never read), and **eligible under the paper's strict rule** (`run_holdout._grounding_match_info(...)["can_ablate"]`) on that variant's own full rendering, with the same frozen bank (hash checked against its freeze). Prompt = system `run_holdout.RUBRIC`, user `ARTIFACT:\n{view}\n\nQUESTION: {question}`, the same code as `study5_judge_panel/prepare_f.py` generalised to a variant letter.
* A cell is "scored by a judge" when at least one of its 3 repeats is valid; cell J = mean of valid repeats.

## C.3 Judges (each its own analysis; temperature 0, 3 repeats, scorer of addendum 26 unchanged via `study5_judge_panel/score_panel.py`: `json_object`, max_tokens 1024 and two retries at 4096, thinking-minimal switch, nothing imputed)

| id | model | route | counts toward the panel summary |
|---|---|---|---|
| `glm` | GLM-4.7-Flash | a shared server, request-only through an SSH tunnel | yes (independent) |
| `gptoss` | gpt-oss-20b | a shared server, request-only through an SSH tunnel | yes (independent) |
| `q38` | Qwen3.8-Flash-Next | <internal-host>, request-only (GPUs 2-4 only serve it; GPU 0 is another agent's container and is not touched) | yes (as in addendum 36; Qwen lineage, flagged) |
| `q80` | Qwen3-Next-80B-A3B-Instruct-FP8 | <internal-host>, request-only | **no** (same model id as the extractor; reported, labelled) |
| `gw` | gpt-5.6-luna through the local gateway | 1-call probe first (it was quota-exhausted, 429, at the end of addendum 36); scored only if the probe returns HTTP 200, then within a **2,000,000 prompt-token budget**, workers <= 3, pass order repeat 1 over all new cells, then 2, then 3, stop on 3 consecutive 402/429 | yes if run (incomplete repeats labelled) |

Servers are shared; nothing is started, stopped or reconfigured; no container is touched. Workers from a probe, at most 3 per endpoint, halved on error bursts; resumable JSONL; tunnels closed at the end. If an endpoint is down it is skipped and reported. No host, port or key in any committed file; raw JSONL is gitignored; score CSVs are committed.

## C.4 Analysis (fixed before any new score)

Paper's rule, same code path as addenda 34-36 (`study5_judge_panel/analyze` / `study4_domains/analyze.contrast_from_d`): cell J = mean of valid repeats; per cluster d = J(second) - J(first); question-clustered paired BCa bootstrap (seed 20260913, B = 10,000); 95% BCa excludes 0 -> resolved (direction named); else 90% BCa inside **+-0.50 (pre-fixed here)** -> equivalent; else unresolved; fewer than 10 clusters -> underpowered. **+-0.30 is also reported** as a second equivalence reading (post hoc, labelled; it does not change a decision). Exact sign test and Wilcoxon (zeros dropped) reported.

* **Contrasts.** Adjacent: A->B, B->C, C->D, D->E, E->F. Against A: A->B, A->C, A->D, A->E, A->F. Per domain (DCAT, SOSA/SSN, PROV) and **pooled over the three domains** (clusters qualified `<domain>:<cq>`, clustered by question within domain). A cluster enters a contrast only when both cells are eligible and scored by that judge.
* **Panel summary** (as in addendum 36): per contrast and scope, the number of independent judges (`glm`, `gptoss`, `q38`, plus `gw` if it ran; `q80` stated separately as same family) resolving second > first, first > second, equivalent, unresolved. Plus a descriptive per-cell panel-mean J (all valid judge repeats, with and without `q80`), labelled a descriptive aggregate, not a judge.
* **Ladder table.** domain x variant: n eligible cells and mean J per judge (over cells eligible and scored), for A..F.
* **Monotonicity.** Per judge: the sequence of pooled-domain (and per-domain) mean J along B -> C -> D -> E -> F, with the number of adjacent steps that are non-decreasing and a flag "monotone non-decreasing" (descriptive; mean over all eligible cells of each variant, and also over the clusters eligible in all five variants B-F).
* Tests on synthetic data for the analysis code are committed with it.

## C.5 Order of work, outputs, commits

1. This file, committed alone. 2. Code (variant packaging, job assembly, analysis, tests) committed before results. 3. Score CSVs, `results.json`, `REPORT_auto.md`, `tables.tex` committed last; `PROGRESS.md` with ETA. Deviations to `DEVIATIONS.md`. Only explicit paths are staged; `index.lock` is retried. Reserved files (`site_key*`, `labeling_sheet_key*`, `human_labels_export*`, `views_for_raters.zip`, `.env`) are never opened. Corpus text, graphs and views of SOSA/SSN and PROV are not committed (document licence); DCAT artifacts may be. Tunnels are closed at the end.
