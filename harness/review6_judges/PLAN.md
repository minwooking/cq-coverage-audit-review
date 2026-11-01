# PREREG addendum 26 (exploratory) -- non-Qwen judges on views that fit their context: judge-family effect and run-to-run variance

> AI-generated draft; the author must review it before it is relied on. Date: 2026-10-17. This file alone is frozen by a single commit before any judge scoring call. The manuscript sources (`main.tex`, `main_ko.tex`, `supplement*.tex`) are not edited by this addendum. All code, commands and configuration named here are AI-generated and must be reviewed and tested by a person before reuse.

## 26.1 Status and purpose

**Exploratory and post hoc.** No confirmatory hypothesis, no pass/fail threshold, no equivalence margin, no multiplicity correction. Everything below is descriptive and is read only as far as the intervals allow.

Purpose: the development study (Ontology-101, 16 questions, variants A-F) was extracted and judged by the same model family (Qwen3-Next), and the Brick holdout's A->B contrast has an interval that includes zero. This addendum asks, with judges **outside the extractor's family** and outside the registered holdout judge's family: (i) does the development A->B contrast of +1.000 survive; (ii) what are the A->B contrast and per-variant means on the holdout views that fit the judges' context; (iii) how large is run-to-run variance for these judges; (iv) how far are these judges from luna and from the registered holdout judge (gemini-3.6-flash) in offset and in contrast direction; (v) what unsupported-credit rate pi-hat do they show against independent-rater labels.

What this session already knows before scoring (disclosure): the registered holdout judge's J, the luna subgraph J (addendum 17/23/25), the development judge's (Qwen) scores, the independent-rater (v3) labels and their pi-hat (13.8%), the holdout A->B (+0.478 on AH labels, +0.565 on J) and the development A->B (+1.000). **No scoring call has been made with either new judge on any experiment input**; the new judges' outputs are unseen.

## 26.2 Judges (two; both non-Qwen)

| id | model | server | context |
|---|---|---|---|
| `gptoss` | `openai/gpt-oss-20b` | vLLM v0.19.1 container on the shared server (2 GPUs, tensor-parallel 2), OpenAI-compatible | `max_model_len` 65,536 (read from `/v1/models`) |
| `glm` | `zai-org/GLM-4.7-Flash` | same host, another container of the same project, bfloat16 | `max_model_len` 65,536 |

The two servers are shared. They are used **by request only**: no container is stopped, restarted or reconfigured, concurrency is at most 3 per endpoint, and the scorer runs on the host inside `tmux`. Addresses are not recorded in this file.

**No third judge.** The shared-server GPUs show 94.8 GiB of 95.8 GiB in use on both devices (three resident vLLM containers), so a Gemma-4-26B server cannot be started without stopping a service on a shared server, which is not allowed. On the shared server `nvidia-smi` still fails with "Driver/library version mismatch" (NVML 580.178), so nothing is launched there. The model servers on that host that answered `/v1/models` serve Qwen models (qwen-next-flash, Qwen3.5); two other local ports gave no answer, and a LiteLLM proxy for another model was not probed or used (its upstream is unknown), so no non-Qwen judge is available there by request. If either endpoint becomes unusable, the run reports it and continues with the judge that works.

Family note: `gptoss` (OpenAI open-weight) and luna (`gpt-5.6-luna`, OpenAI) share a vendor; `glm` (Zhipu) shares no vendor with the extractor (Qwen), the registered holdout judge (Google) or luna. Weights are not pinned by hash; the container image tag (v0.19.1) and model ids are the pin.

## 26.3 Views, cells, repeats

All inputs are built by `build_jobs.py` (no network) into `jobs.jsonl` (sha256 in 26.9). Nothing from labels, expected answers, judge scores or variant names enters a prompt (exception in 26.4 for the development prompt).

* **(a) `holdout_subgraph`, 182 cells.** The 188 primary holdout cells (216 variant x question pairs minus the 28 documented exclusions) minus the **6 cells with no subgraph** (A-CQB27 and B-F CQB32; addendum 25 gave them the full view, which is about 73k tokens for A and 490k-600k for B-F and does not fit a 65,536-token window; they are skipped and logged). View = the subgraph text of the length experiment (`length_experiment/inputs/<V>/<CQ>/subgraph.txt`, sha256 checked against `inputs/manifest.jsonl`, whose own sha256 `46277713...ceaa32` is verified). Per variant: A 22, B-F 32 each. Paired A->B questions: 22 (the paper's 23 minus A-CQB27).
* **(b) `holdout_control`, 27 cells.** The registered controls re-built on the **subgraph text** with the registered functions: 15 ablated (`ablate_rendered_view` applied to the subgraph; 9 of the 24 registered ablated controls have no grounding span in their subgraph and cannot be built, listed in `jobs_build_skips.json`) and 12 preserved (same subgraph, registered paraphrase). This is a **new construction**: the luna subgraph run (addendum 25) used no controls.
* **(c) `dev`, 96 cells.** The 16 development questions x 6 variants on the **development rendering**: the stored judge-facing summaries of `output/abcdef_evaluation.json` (13k-104k characters). A tokenizer preflight (`/tokenize`, no generation) on both servers shows **every one of the 305 cells fits** (max prompt 27,813 tokens for `gptoss`, 29,035 for `glm`; plus the 4,096-token retry budget, far below 65,536). So **no development subgraph analogue is built**.
* **Repeats: 3** per (cell, judge). Calls: 305 x 3 = 915 per judge, 1,830 in total. Repeats are separate passes (all cells of repeat 1, then 2, then 3), each in a seeded shuffle (seed 20260913 + 1000 x repeat), so batch composition differs between repeats. A cell whose prompt plus the retry budget exceeds the window is skipped and logged (none expected).

## 26.4 Prompts (reused, not edited)

* Holdout (a, b): `run_holdout.RUBRIC` as system message (string sha256 `85e208799f10b756125c524dc43222064ac946f3c01f000ee03cf331800cee72`; it carries the 0-3 anchors "0 = no related concept or relation present; 1 = partial; 2 = mostly; 3 = complete" and the JSON output instruction) and `ARTIFACT:\n{view}\n\nQUESTION: {question}` as user message, exactly as `call_judge` builds it.
* Development (c): `eval_ab.JUDGE_SYSTEM` (sha256 `288b62cad65132777849d76dfb8a724251cc1b4139f750eb2e86dcf30f561e9f`) and the `judge_cq` user message: `LAYER1_RUBRIC` (sha256 `193f4f57ecf20dff1c7434db7247d7a405e1ff61f99b83feebb01f3873112315`), the question with its id and category, the one-line "What a good answer needs" hint, and `ONTOLOGY {A-F} SUMMARY:` + the stored summary, then the JSON instruction. All 96 messages were checked byte-for-byte against the output of `eval_ab.judge_cq` (test run before the freeze). The development prompt shows the ontology letter and the question id, as the original development run did; the holdout prompt does not.
* Every job carries `prompt_sha256`; the scorer refuses to start if any differs from its recomputed value.

## 26.5 Decoding

As in the substitute-judge runs: `temperature` 0.0, `response_format` `{"type":"json_object"}`, `max_tokens` 1024, one request per cell and repeat with no conversation history, no `seed` field.

**One deviation, fixed here: a thinking-minimal switch**, the analogue of the registered judge's `thinking_level=minimal` and the substitute judges' `enable_thinking=false`: `gptoss`: `reasoning_effort: "low"`; `glm`: `chat_template_kwargs: {"enable_thinking": false}`. Reason: both are reasoning models whose default thinking took 470-690 completion tokens of the 1024 budget on a synthetic three-line input (16 calls with a toy ontology before this freeze; no experiment input was used), so the budget cannot be assumed to suffice on real inputs. No other decoding option is changed.

**Retry rule** (the development harness's rule: retry with a larger budget): a reply that is empty, not JSON, has no numeric `score`, has a score outside 0-3 after rounding, or ends with `finish_reason=length` without parsable JSON is retried with `max_tokens` 4096, at most 2 retries (3 attempts). Parsing: strict `json.loads`, then the lenient fence/brace extraction of `llm.loads_lenient` (flagged `lenient_parse`). A score is `J = round(score)`, valid iff in {0,1,2,3}; a non-integer score is flagged. **Nothing is imputed**: a cell that stays invalid is `valid=false`, listed in the report and left out of the estimates. HTTP 429/5xx/network errors are retried 3 times (5, 15, 45 s); a 400 "context length" reply is recorded as `context_skip` without retry. Records keep: cell id, judge, repeat, J, the cited span (`evidence` as returned), the raw reply, finish reason, reasoning length and its first 300 characters, prompt and completion tokens, per-attempt log and latency.

Because `temperature` is 0, **run-to-run differences measure serving-stack (batching, floating point) nondeterminism, not sampling variance**, as with the two samples of the development judge. Sampling-temperature variance is not measured here.

## 26.6 Analyses (all descriptive; code = `analyze_review6.py`, written while the scoring runs and before any J value is read)

Per-cell score of a judge = mean of its valid repeats (primary). Intervals: **question-clustered BCa, 95%, B = 10,000, seed 20260913**, through `analyze_holdout.cluster_bootstrap_delta` / `cluster_bootstrap_stat` (cluster = `cluster_id`: the CQ for the holdout, 32 clusters among the 182 cells and 22 paired questions for A->B; each development question is its own cluster, 16). Contrasts, in both studies: **A->B (headline), B->C, C->D, D->E, E->F, D->F** (the six pairs of the paper's Table S6), mean per-question difference of per-cell scores.

1. **A->B per judge**, holdout subgraph (J only; the holdout's AH/L1* labels are not used) and development, with the BCa interval; also the A->B of each single repeat (1, 2, 3) and, for development, the paper's convention (half-up rounded mean of repeats 1 and 2). Reference A->B recomputed with the same code: Qwen development judge (paper's +1.000), registered holdout judge J on the full view (gemini-3.6-flash, `real_run/cells.jsonl`), luna subgraph J (`length_experiment/cells_length.jsonl`), on the same questions and on their own full sets.
2. **Per-variant means** of J and coverage (share of cells with J >= 2), per judge and study, next to the same references.
3. **Run-to-run:** per judge and study, the mean pairwise exact agreement over the 3 repeats (pairs 1-2, 1-3, 2-3 within a cell), the share of cells with 3 identical scores, and ICC(2,1) and ICC(2,3) (two-way random, absolute agreement; cells as targets, repeats as raters; cells with 3 valid repeats), with question-clustered intervals.
4. **Offset vs luna subgraph** (holdout, cells valid for both): mean(J_judge - J_luna) with the BCa interval, exact agreement and quadratic weighted kappa (`analyze_holdout._qwk_from_values`), each computed per repeat and averaged over the 3 repeats. The same against the registered holdout judge's J (full view; different input, flagged). Inter-judge agreement (`gptoss` vs `glm`) likewise.
5. **Contrast-direction agreement:** for each of the six contrasts, the sign (+, 0, -) of each judge's mean difference against the references (holdout: gemini-3.6-flash J and luna; development: the Qwen judge and, as a further reference, the stored Gemini and panel runs of `output_judge3`), reported as counts of matching signs out of 6, and the per-question A->B delta sign agreement. Counts, not tests.
6. **Unsupported-credit rate** pi-hat = share of primary cells with J >= 2 and S = 0 (`analyze_holdout.silent_over_credit_rate`, the paper's estimator, cluster BCa), per repeat then summarized (mean, min, max over repeats) per judge, against the **independent rater's (v3) S labels** (`annotation/second_pass_2026-10-13/v3/labels_for_analysis_v3.csv`, tracked, column `A`), over the 182 cells; the same estimator for the registered holdout judge and luna on the same cells. **AH (first-author-revised) labels are not used:** the per-cell AH file lives in the locked label directory, which is not opened under this brief; `analyze_review6.py --ah-labels PATH` runs the same estimator when the author supplies a path. Caveat: S was assigned on the full rendering, the judges here see the subgraph. Controls: share of ablated controls with J >= 2 and of preserved controls with J >= 2, per judge (descriptive).
7. **Cost:** prompt and completion token totals (server `usage`), wall time and calls per judge and study, invalid and context-skipped counts.

## 26.7 Outputs

Under `harness/review6_judges/`: `PLAN.md` (this file, the only committed file), `build_jobs.py`, `jobs.jsonl`, `jobs_build_skips.json`, `score_judges.py`, `analyze_review6.py`, `test_review6.py`, `raw/raw_<judge>.jsonl`, `raw/*_preflight.json`, `raw/*_progress.log`, `results.json`, `REPORT.md`. Nothing else is committed. Checkpoints go to the session scratchpad progress file after each step and about every 25% of calls.

## 26.8 Deviations from the registered setup and limitations (stated before the run)

* The judges are not the registered holdout judge and not the development judge; results are read within this addendum, not as the registered judge's behavior.
* Holdout inputs are the question-relevant **subgraph** (at most 18.4k prompt tokens), not the full view the registered judge and the human raters saw; evidence outside the subgraph is invisible to the judges. 6 primary cells (no subgraph) are not scored. Subgraph controls are a new construction (15 of 24 ablated, 12 of 12 preserved).
* The development study uses the original rendering and prompt; only the judge changes (and the thinking-minimal switch).
* Thinking-minimal switch and the 4,096-token retry budget are deviations from the registered 1024-token single attempt.
* `temperature` 0 means the repeats do not sample; ICC and agreement describe serving nondeterminism only.
* Servers are shared; their weights, quantization and load are not controlled.
* Only two judges; judge-family conclusions rest on n = 2 families and the contrasts of 22 (holdout) and 16 (development) questions.
* pi-hat is against the independent rater, not AH; S refers to the full rendering.
* Exploratory: intervals are descriptive; no direction is pre-specified.

## 26.9 Pins at freeze

Repository HEAD at freeze: `f107732` (the working tree has unrelated uncommitted edits by another session, not touched here). Files (sha256):

* `jobs.jsonl` `30190f072caa33a32b77586c76b60d5debf68febae3749bd27e0a483e8be524c` (305 jobs: 182 + 27 + 96)
* `jobs_build_skips.json` `1a124842e9e7a5797415d2f4d5f2d6e1c72ba58cef08ef94d3b803ba321415a9`
* `build_jobs.py` `bf4890bb885b533060d33eb2e5db09f61ec9f854dc9f8ddbeba62baec3aa485e`
* `score_judges.py` `3788576cd22eb73d7568d032a4db869de3a195c76c5cbeb6e6f42f5e6239a753`
* bank `bank/cq_bank_brick_v1.csv` `993c5e1164540dce0f2f9bf2e6ed397cf45910da7889300feeaad6543edb8507`
* length-experiment manifest `46277713c3828da145278c6e4622c8c0a84f193c7e58c9a91489e2d918ceaa32`
* `harness/real_run/cells.jsonl` `bfd5b3c83981c8a6ec970b93f460bab7409daf047a2e048bfaa90b5adfd0d4af`
* `output/abcdef_evaluation.json` `780a1b2e721d18998521112350f8dfec0e3f74bf611e43e3c89fd88465d92b60`
* `eval/competency_questions.json` `a0063d15e05ecb826bdba20218be8ab5b0de38a15b3a2144812a2ec6a7af61aa`
* `src/chunktograph/eval_ab.py` `19c5aa4d2464ec05e5348053e167088b0b0509587795d492a6c495bd739e845d`

`analyze_review6.py` and `test_review6.py` are not pinned: the analysis is written while the scoring runs and is held to 26.6 as written. Any change to a pinned file after this commit is recorded in `REPORT.md` under "Deviations after freeze"; a change of judge, prompt or decoding requires a new addendum.

## 26.10 Events that must not happen before this freeze

1. A generation call by `gptoss` or `glm` on any experiment input (cell of `jobs.jsonl`). 2. Reading any J of the new judges. 3. Changing 26.3-26.6 after seeing a J. Allowed and done before the freeze: code and offline tests with a fake local server, the synthetic toy-ontology probe (16 calls), the tokenizer-only preflight on all 305 cells, building `jobs.jsonl`.
