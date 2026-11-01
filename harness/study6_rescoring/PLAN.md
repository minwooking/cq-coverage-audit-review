# PREREG addendum 37 (exploratory, post hoc) -- three judge-only re-scoring studies recommended by the mock review panel

> AI-generated draft; the author must review it before it is relied on. Date: 2026-10-21. Post hoc: written after addenda 26-36 and with knowledge of their results. This file is committed alone, before any scoring call of this addendum. `main.tex`, `main_ko.tex` and `supplement*.tex` are not touched. All code named here is AI-generated and must be reviewed and tested by a person before reuse; none of it is to be applied to a production system.

## 37.1 Status, and what was done before this commit (disclosure)

Exploratory and post hoc; judge scores only; no human label is used or opened. No confirmatory hypothesis. Readings below are fixed before any score of this addendum and are applied as written.

Before this commit, and only these: (i) a read-only `GET /v1/models` on the three shared-server endpoints and the <internal-host> `Qwen3.8-Flash-Next` endpoint (the latter answered `Unauthorized`; **no API key for it exists in this session's environment, and none is requested**, so that judge is unavailable and is skipped and reported); (ii) a tokenizer-only preflight (`/tokenize`, no generation) of the six full variant renderings on three shared-server models (`fit_full_preflight.json`); (iii) offline job building (`build_jobs.py`, no network). The 1-call luna probe (37.4) happens after this commit.

What this session already knows: the registered holdout judge's J (Gemini 3.6 Flash), luna's and Sonnet's cross-family scores, the addendum-26 GLM / gpt-oss scores on subgraph views and on the development study **with** the hint, the development Qwen scores (A->B +1.000), the independent-rater labels. **No scoring call of this addendum has been made; its outputs are unseen.**

## 37.2 Judges and endpoints (request-only; nothing is started, stopped or reconfigured; GPUs 2/3/4 of the shared server untouched; no container launched)

| id | model | host | max_model_len | used for |
|---|---|---|---|---|
| `glm` | zai-org/GLM-4.7-Flash | a shared server, vLLM | 65,536 | A, B, C |
| `gptoss` | openai/gpt-oss-20b | same host | 65,536 | A, B, C |
| `qwen35` | Qwen/Qwen3.5-4B | same host, a third container; **no authentication** | 32,768 | A only; **Qwen-lineage proxy**, a 4B model, **not** the original development judge (Qwen3-Next-80B-A3B). Added because the original-family reading of A needs some Qwen-lineage judge that is reachable; its weakness is a stated limitation |
| `q38` | Qwen3.8-Flash-Next | <internal-host> :PORT | unknown | **unavailable** (no key in session); skipped. If a key appears in `CHUNKTOGRAPH_LLM_API_KEY`, A is run for it; otherwise not |
| `gw` | gpt-5.6-luna via the local gateway | local proxy | large | A only, **only if** the 1-call probe returns HTTP 200 with a parseable score (37.4); not B (luna already scored B's full views) and not C (a full-view run of 188 cells is about 10^8 prompt tokens, far beyond the gateway quota rule) |

No Claude judge is used (Sonnet consulted on AH labels). Tunnels: three local ports to the shared server and one to the shared server, opened for this run and closed at the end. No host, port or key is written to any committed file. Decoding as addendum 26: `temperature` 0.0, `response_format` json_object, `max_tokens` 1024, retry at 4096 up to twice, thinking-minimal switch (`gptoss`: `reasoning_effort` low; `glm`, `qwen35`, `q38`: `enable_thinking` false), nothing imputed, HTTP 429/5xx backoff 5/15/45 s, a 400 context error recorded as `context_skip`. The scorer is addendum 26's `score_judges.py` imported unchanged (plus judge entries). Workers: at most 3 per endpoint, halved on any burst of errors (the three endpoints are shared with another project); 3 repeats per (cell, judge); repeats are separate passes with the seeded shuffle of addendum 26. Resumable JSONL.

## 37.3 Sub-studies, cells, arms

### A. Development study without the one-line hint (96 cells = 16 questions x 6 variants)

The development judge prompt is `eval_ab.JUDGE_SYSTEM` + `judge_cq`: the Layer-1 rubric, `COMPETENCY QUESTION (id, category=...)`, **`What a good answer needs: {needs}`** (the one-line hint of main.tex Section VI), `ONTOLOGY {letter} SUMMARY:` + the stored summary. The holdout judge instead gets `run_holdout.RUBRIC` as system message and `ARTIFACT:\n{view}\n\nQUESTION: {question}`: no hint, no ontology letter, no question id or category, a different rubric text. Three arms on the stored development summaries (`jobs_A.jsonl`):

* `A_hint` -- the original development prompt, byte-identical to addendum 26's dev jobs (prompt hashes verified equal). Run only for judges that have no addendum-26 with-hint scores (`qwen35`, `gw`, `q38`); for `glm` and `gptoss` addendum 26's raw scores are the with-hint arm.
* `A_nohint` -- **primary**: the development prompt with exactly the `What a good answer needs:` line removed and nothing else changed (the single-factor test).
* `A_holdout` -- secondary: the holdout-style prompt (rubric, ARTIFACT/QUESTION, no letter, id or hint) on the same summaries.

Calls: `glm` and `gptoss` 2 arms x 96 x 3 = 576 each; `qwen35` 864; `gw` at most 864 under its budget; `q38` 864 if a key exists. Cells over a judge's window (prompt + 4,096 > max_model_len; `qwen35` has 32,768) are recorded as `context_skip` per judge and left out for that judge, and the report states how many.

### B. Cross-family re-scoring of the 48 pre-specified cells (list `real_run/second_annotator/cell_list_48.txt`, 28 questions) with judges outside the label consultation

Original panel: Gemini J (registered, full view), `gpt-5.6-luna` and `claude-sonnet-5-5` on the full view (`real_run/paired_ai_audit_48`). New judges: `glm`, `gptoss`.

**Input.** The brief asks for the same full-view input. **No full view fits**: the tokenizer preflight gives 69,617-69,856 prompt tokens for variant A and 489,948-633,998 for B-F against a 65,536 window with a 4,096 retry reserve (`fit_full_preflight.json`), so the full-view arm has **0 cells** on every shared-server judge (all 48 recorded as not scored on the full view). The paper's truncation rule (Supplement S12: first 60,000 characters, cut at a line boundary, `[truncated]` appended; the frozen `limited.txt` files, sha256 checked against the length-experiment manifest) is applied to **all 48 cells** as the arm `B_limited`; it is not silent and not the registered input. The 48 cells are the `in_cell_list_48` subset of `jobs_L.jsonl` (37.3 C), scored once. A second arm, `B_subgraph`, **reuses addendum 26's subgraph scores** (no new call) for the cells that have a subgraph.

### C. Full re-scoring of the 188 primary holdout cells by the non-Qwen judges

Cells: the 188 primary cells (A 23, B-F 33 each). Same fit rule: **full-view arm 0 cells** for `glm` and `gptoss` (reported, nothing truncated silently). New arm `C_limited`: all 188 cells on the 60,000-character view (`jobs_L.jsonl`, `glm` and `gptoss`, 3 repeats: 1,128 calls each, about 17k prompt tokens per call). Reused arm `C_subgraph`: addendum 26's `holdout_subgraph` scores (182 cells; 6 cells without a subgraph), no new call. The two arms are never pooled. References: Gemini J on the full view (`real_run/cells.jsonl`), luna on the limited and subgraph views (`length_experiment/cells_length.jsonl`) and on the full views (`length_experiment/luna_full_r35`).

## 37.4 Gateway probe (read-only first, after this commit)

`GET /v1/models` at the local gateway; if `gpt-5.6-luna` is listed, one call with the smallest `A_nohint` job in the registered request form (omitting `response_format` and then `temperature` if the gateway rejects them, each omission recorded). HTTP 200 with a parseable score -> luna becomes `gw` for sub-study A: workers <= 3, a hard budget of **9,000,000 prompt tokens**, passes in the order repeat 1 over all arms, then 2, then 3, stop on 3 consecutive 402/429. Anything else -> "no route", `gw` skipped. No other gateway model is probed.

## 37.5 Statistics (all descriptive; code = `analyze.py`, written while scoring runs and before any J is read)

Cell score of a judge = mean of its valid repeats. Contrast statistic and interval = the paper's rule: question-clustered paired BCa bootstrap, seed 20260913, B = 10,000 (the code path of `study3_expanded_ab/analyze.contrast`); 95% interval for **resolved** (excludes 0), 90% interval inside +-0.30 (the registered holdout margin) and, separately, inside +-0.50 for **equivalent**; otherwise **unresolved**; both margins always reported. MDE = 2.8 x sigma / sqrt(n) with sigma the SD of the per-question paired differences observed for that judge and arm. Fewer than 10 clusters: not interpreted.

* A: per judge and arm, A->B contrast over 16 questions (also B->C, C->D, D->E, E->F, D->F); per-variant mean J and coverage (share of cells with J >= 2); with-hint minus no-hint cell-level difference (mean, BCa, exact agreement, QWK); the A->B contrast of the with-hint arm for the same judge. References: development Qwen (paper's convention, half-up rounded mean of the two stored samples, +1.000), addendum 26's with-hint scores.
* B: per judge, **same-input** agreement (limited view) with luna's limited-view scores; **cross-input** agreement with Gemini J, luna-full and Sonnet-full: exact agreement, quadratic-weighted kappa (`analyze_holdout._qwk_from_values`, per repeat averaged) and offset mean(J_judge - J_ref) with question-clustered BCa, on the 48 cells (28 clusters). The panel QWK against Gemini of each new judge is set beside that of luna and Sonnet; the difference (new minus Sonnet) gets a cluster BCa interval. Share of J <= 1 per judge reported (floor check). The same table for the subgraph arm against luna's subgraph scores.
* C: per judge and arm, per-variant mean J and coverage A-F; A->B on J (23 or 22 paired questions); D vs B on J (33 questions) and the other D contrasts; G6-style items as far as the gate table defines them (Section V, G6 = A->B consistent, a non-Qwen judge agrees in direction, fragility K >= 6): sign agreement of each non-Qwen judge's A->B with the registered J's A->B (+0.565, resolved), its label, and inter-judge exact agreement and QWK (`glm` vs `gptoss`, each vs Gemini J, each vs luna) on shared cells. **K is not computed** (it is defined on the label set, which this addendum does not use). Run-to-run: mean pairwise exact agreement of the 3 repeats.

## 37.6 Pre-fixed readings

**A.** Judges are read separately; no pooling. The A->B contrast is **hint-independent for a judge** if it is `resolved` with a positive sign under `A_nohint`; **hint-dependent** if the same judge's with-hint arm is `resolved` positive and `A_nohint` is not; **never resolved** if neither is. The original-family reading uses `q38` if it ran; otherwise `qwen35` (a Qwen-lineage proxy, stated as such, **not** the original judge); if neither ran, "not tested for the original family". The headline sentence for the development study is allowed only as: "under the no-hint prompt, the development A->B contrast stayed resolved / became unresolved for [judges]", with the denominators. `A_holdout` is read the same way as a second condition and never replaces `A_nohint`.

**B.** The new judge counts as **comparable to Sonnet** if the 95% interval of QWK(new, Gemini) - QWK(Sonnet, Gemini) contains 0 and as **lower / higher** if it excludes 0, on the 48 cells; because the new judges see a prefix of the view, a **floor warning** is attached to any judge with more than 80% of cells at J <= 1 ("agreement is dominated by the input, not the judge"). The same-input luna comparison is the primary like-for-like reading; the Gemini/Sonnet comparison is cross-input and labeled so.

**C.** D vs B **replicates** under a judge and arm if D - B < 0 with a 95% interval excluding 0 (as the registered -0.273 [-0.576, -0.091]); **direction only** if the mean is negative and the interval includes 0; **does not replicate** if the mean is >= 0. A->B **direction agrees** with the registered judge if the mean is positive; **resolved** under the 95% rule. Both views are reported side by side; a pattern that holds on `C_subgraph` but not on `C_limited`, or the reverse, is reported as input-dependent, not averaged.

## 37.7 Deviations and limitations stated before the run

No full-view cell can be scored by any available judge (A needs about 70k tokens, B-F about 0.5-0.65 million); B and C therefore use the 60,000-character view (judges see an IRI-ordered prefix unrelated to the question, so scores sit near the floor and the comparison with full-view references measures the input as much as the judge) and the reused subgraph scores. `qwen35` is a small Qwen-lineage proxy, not the original development judge; `q38` is unavailable. Temperature 0 means repeats measure serving nondeterminism only. Servers are shared; weights and load are not controlled. Judge-family statements rest on two judges (three with `qwen35`, four with luna).

## 37.8 Outputs, commits

`PLAN.md` (committed alone), then code (`build_jobs.py`, `run_study.py`, `analyze.py`, tests, job files, `fit_full_preflight.json`), then raw records, `results.json`, `REPORT_auto.md`, `tables.tex`, `PROGRESS.md` (ETA per sub-study). Messages end with `Co-Authored-By: Claude Fable 5.1 <<email>>`. Only explicit paths are staged; `index.lock` is retried. Reserved files (`site_key*`, `labeling_sheet_key*`, `human_labels_export*`, `views_for_raters.zip`, `.env`) are not opened. Tunnels are closed at the end.

## 37.9 Pins at freeze

* `jobs_A.jsonl` `3f5ef54a3eef13589e8543bb5bd588072f4bea4788f70df036f318a1ade1c1fa` (288 jobs: 3 arms x 96)
* `jobs_L.jsonl` `8e0698b7403da54ceb286de92676e8fd244421bf54a2ace98958694f22e0ef4e` (188 jobs; 48 in the cell list)
* `build_jobs.py` `735a040f4443eeb542aaf6e28c75bcef4f00dcfe4072e88c53e0ba69b95ac2d9`
* holdout RUBRIC `85e208799f10b756125c524dc43222064ac946f3c01f000ee03cf331800cee72`; dev JUDGE_SYSTEM `288b62cad65132777849d76dfb8a724251cc1b4139f750eb2e86dcf30f561e9f`; dev LAYER1_RUBRIC `193f4f57ecf20dff1c7434db7247d7a405e1ff61f99b83feebb01f3873112315`; length manifest `46277713c3828da145278c6e4622c8c0a84f193c7e58c9a91489e2d918ceaa32`.
