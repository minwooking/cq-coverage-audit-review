# PREREG addendum 28 (exploratory) -- LLM-rater stability and cross-family agreement, without human labeling

> AI-generated draft; the author must review it before it is relied on. Date: 2026-10-17. **Addendum 28: post hoc with respect to the original plan, pre-specified with respect to these new data.** This file and `analyze_raters.py` are frozen by a single commit before any scoring call on an experiment input. The manuscript sources (`main.tex`, `main_ko.tex`, `supplement*.tex`) are not edited. All code, commands and configuration named here are AI-generated and must be reviewed and tested by a person before reuse; none of it is to be applied to a production system without that review.

## 1. Status, claim ceiling, and what changed before the freeze

**Exploratory and post hoc.** No confirmatory hypothesis. The pre-specified criteria below only decide the words "supported / not supported / unresolved" for two candidate Table 10 rows.

**Claim ceiling (fixed before any run):** "the LLM rater is stable, families agree, and agreement is comparable to human-human". Nothing here is aimed at, or will be written as, "LLMs are more accurate than humans". Human labels are never ground truth in this addendum; kappa with a human is an agreement number.

**Amendment record (made at plan time, before any scoring call).**

* *Original brief:* Experiment 1 = test-retest of the S21 rater (`gpt-5.6-luna` through the <internal-proxy> proxy) on the 188 primary cells, with the S21 labels as run 0; Experiment 2 = three families (OpenAI luna, Zhipu GLM-4.7-Flash, a non-Sonnet Claude) plus gpt-oss-20b; auxiliary = luna on the full rendering of 48 sampled cells.
* *Observed at 2026-10-17 09:27-09:32 UTC:* (i) the <internal-proxy> route for `gpt-5.6-luna` answered HTTP 402 "Payment Required" (preceded by HTTP 429 with Retry-After 60 s) on every call of the dry-run that was sent (7 calls; no label was produced); a read-only status query reported the quota as exhausted (nothing was changed). The judge agent working in parallel saw the same 402. (ii) The <internal-proxy> route for Anthropic models answered HTTP 401 "Not logged in to anthropic" (haiku-5-5 and opus-5-5; one call each); logging in is the user's action and was not attempted. (iii) A read-only scan of the model servers reachable from this machine (`/v1/models` names only) found no generative family other than Qwen (the extractor's family), Google (the judge's family), OpenAI-open (gpt-oss-20b) and Zhipu (GLM-4.7-Flash). No job is launched on the shared server (`nvidia-smi` still errors there, per the judge agent); the one already-running container used for the contrast rater is reached by request only, through the gateway.
* *Amendment instructed by the coordinating agent (course correction, same day, before scoring):* Experiment 1 uses **GLM-4.7-Flash on the shared server** as the rater with the same conditions (a)/(b)/(c); the existing S21 luna labels are a **separate label source, not run 0**; Experiment 2 families = Zhipu (GLM-4.7-Flash), Anthropic (non-Sonnet Claude only if a route exists that is not on the exhausted quota), OpenAI-open (gpt-oss-20b); if Claude is unavailable and no third non-Qwen, non-Google family is reachable without stopping anyone's container, two families are run and the shortfall is reported; the luna full-rendering auxiliary is dropped. **No call to `gpt-5.6-luna` is made in this addendum.**
* *Further instruction relayed from the author (same day, before scoring):* luna is **permanently blocked** for this task, so the amendment above stands. The author also asked for the **qwen-next-flash model served on the shared server** to be used in luna's place, as an extra **"same-family rater (contrast)"** in Experiment 2: one run, all 188 cells, temperature 0, with its kappa with the humans and with the other raters reported next to the cross-family values, to show directly whether family overlap matters. Qwen is the extractor's family, so it is **not counted among the cross-family raters** in any rule below. Endpoint check (read-only, section 2): the container is `<container>`; the port named `qwen-next-flash` on that host is a forwarder to another machine, not this model. Access is request-only, at most 3 concurrent requests per endpoint, and no container is stopped.
* *Consequence stated up front:* Experiment 1 no longer retests the S21 luna rater. It tests whether **an LLM rater using the S21 prompt and protocol (GLM-4.7-Flash)** is stable across runs and prompts. Nothing in this addendum can support or contradict the stability of the luna labels themselves. Experiment 2 will have at most two independent families unless the Anthropic route is authenticated by the user before the end of the task; the rule in section 5.4 then caps its status at "unresolved".

**What this session knew before scoring (disclosure).** The S21 results (`harness/llm_rater_luna_2026-10-15/subgraph_r25/`): the luna labels on 188 cells (S=1 in 85 cells as published, 68 once the span check below is applied to the stored spans; R distribution; pi-hat 28.7%), the human-human kappa on S (0.595 [0.268, 0.833], 188 cells) and QWK on R (0.728 [0.567, 0.859]), reproduced bit-exactly by `analyze_raters.py selfcheck`. The selfcheck reads the AH and second-rater label files but prints only these two aggregates. The judge agent's progress notes (not its J values for any cell). **No GLM, gpt-oss or Claude output on any experiment input has been seen**, except the 5-cell dry-run of section 7, which is discarded and re-run inside the experiments.

## 2. Raters (models)

| key | model | route | decoding | context |
|---|---|---|---|---|
| `glm` (Experiment 1 rater; Experiment 2 family "Zhipu") | `zai-org/GLM-4.7-Flash`, bf16 | vLLM v0.19.1 container on the shared server (2 GPUs, TP 2), OpenAI-compatible, **request-only** through a local port-forward (no container is stopped, restarted or reconfigured; no file is written on the host) | `max_tokens` 2048 (retry 4096, at most 2 retries on an empty / non-JSON / out-of-range reply), `temperature` and `seed` per condition, `chat_template_kwargs.enable_thinking=false` (the same thinking-minimal switch the judge agent froze), no `response_format` | `max_model_len` 65,536 |
| `gptoss` (Experiment 2 family "OpenAI-open") | `openai/gpt-oss-20b` | same host, another container of the same project, same route | `reasoning_effort: "low"`, otherwise as above; temperature 0, seed 20260913 | 65,536 |
| `haiku` or `opus` (Experiment 2 family "Anthropic", conditional) | `anthropic/claude-haiku-5-5`, else `anthropic/claude-opus-5-5` (never Sonnet 5.5, which consulted on the AH labels) | <internal-proxy> proxy (`/v1/chat/completions`), the route the earlier Sonnet 5.5 cross-judge used (`harness/real_run/paired_ai_audit_48/anthropic__claude-sonnet-5-5/run_manifest.json`) | `temperature` 0.0 if the API accepts it, else omitted and disclosed (the Sonnet route rejected it); no seed; no `response_format`; `max_tokens` 2048/4096 as above | probed at run time |
| `qwen` (Experiment 2 **same-family contrast rater**, never counted as a cross-family rater) | `nvidia/Qwen3.8-Flash-Next-NVFP4`, served name `Qwen/Qwen3.8-Flash-Next` (container `<container>`, vLLM v0.30.0, TP 2, expert parallel, MTP speculative decoding, NVFP4) on the shared server | **<internal-proxy> gateway only**, provider `<internal-proxy>`, model id `<internal-proxy>/Qwen/Qwen3.8-Flash-Next`; confirmed read-only: `/v1/models` of the gateway lists it, a tiny probe returned `model: Qwen/Qwen3.8-Flash-Next` with `system_fingerprint` `vllm-0.30.0-tp2-ep-...`, matching the container's engine and parallelism, and a read-only container query (names, image and launch arguments only) shows it with `--max-model-len 262144`. The direct server port requires a credential; none was used or is recorded here | `temperature` 0, no seed, no `response_format`; the gateway ignores `chat_template_kwargs.enable_thinking=false` (probed: reasoning tokens were still produced), so **thinking stays on** (unlike GLM and gpt-oss); `max_tokens` 6144 (retry 12288, at most 2 retries) | 262,144 |
| `luna_s21` (descriptive label source, **no new call**) | `gpt-5.6-luna` labels of S21 (2026-10-15), subgraph view for 182 cells and the full view for 6 | stored raw file `subgraph_r25/luna_rater_subgraph_raw.jsonl` | as published (temperature 0, seed 20260913) | n/a |

The Anthropic route is probed (one tiny call per model) before Experiment 2 starts and again at the end; if it answers HTTP 401 or any quota error it is reported as "not run" and not retried in a loop. Family note: gpt-oss-20b and luna share a vendor (OpenAI); in Experiment 2 the OpenAI family is represented by gpt-oss-20b, and luna's S21 labels are reported next to it as an additional, overlapping source. Weights are not pinned by hash; the container image tag (v0.19.1) and the model ids are the pin.

## 3. Cells

* **Primary set for both experiments: the 182 primary holdout cells that have a subgraph view** (32 CQ clusters). The 188 primary cells minus **6 cells with no subgraph** (A:CQB27, B:CQB32, C:CQB32, D:CQB32, E:CQB32, F:CQB32); S21 gave those 6 the full rendering (about 73k tokens for A-CQB27, 490k-600k for B-F CQB32), which does not fit a 65,536-token window; they are not rated by GLM, gpt-oss or Claude (the only exception is the contrast rater `qwen`, whose window holds A-CQB27) and the skips are logged. Per variant (CQ numbers):

| variant | cells | CQ ids (CQB..) |
|---|---|---|
| A | 22 | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 16, 17, 21, 25, 26, 28, 29, 30, 31, 34 |
| B | 32 | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 24, 25, 26, 27, 28, 29, 30, 31, 33, 34, 35, 36 |
| C | 32 | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 24, 25, 26, 27, 28, 29, 30, 31, 33, 34, 35, 36 |
| D | 32 | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 24, 25, 26, 27, 28, 29, 30, 31, 33, 34, 35, 36 |
| E | 32 | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 24, 25, 26, 27, 28, 29, 30, 31, 33, 34, 35, 36 |
| F | 32 | 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 24, 25, 26, 27, 28, 29, 30, 31, 33, 34, 35, 36 |

* **Contrast rater coverage ("all 188 cells"):** `qwen` is sent every one of the 188 cells except those whose estimated prompt (characters / 4) plus the retry budget exceeds its 262,144-token window. By the estimates in `cells_manifest.json` that is the 5 cells B-F CQB32 (about 488k-604k tokens); A-CQB27 (about 74k tokens, full view) fits and is sent. So `qwen` rates 183 cells; the 5 unsent cells are logged as `context_skip`. Pairwise comparisons with the other raters use the 182 common cells; `qwen` vs the humans is also reported on all cells it scored.
* Material = the question-relevant subgraph text of the length experiment (`length_experiment/inputs/<V>/<CQ>/subgraph.txt`), each file sha256-checked against `inputs/manifest.jsonl`, and the **same text luna saw in S21** (`cells_manifest.json` was built only after checking that every one of the 188 materials has exactly the `view_sha256` stored in the S21 raw file). Question text, Korean category and Korean reference translation come from the labeling-site cell file (`labeling_site/data/cells.json`, keyed by an opaque id) matched to the bank by question text; **the key files, the rater zip and the human export are never opened**.
* The 182 cell ids (sha256 of the sorted list `da1453e8aa81c05f11765c3a1e5bd117be5bbd760661f0a81e5e58da1fc5ac45`) are `primary:<variant>:<CQ>` for every row of `cells_manifest.json` with `view_kind == "subgraph"`. AH labels (`locked_labels/primary_working.csv`) and second-rater labels (`annotation/second_pass_2026-10-13/v3/labels_for_analysis_v3.csv`) are read by `analyze_raters.py` only through the existing readers `rater_luna.read_labels`; per-cell human labels are never written to a repository file.
* Judge scores J for pi-hat are the registered holdout judge's (`harness/real_run/cells.jsonl`).

## 4. Conditions

Every call is one request with no conversation history: system message = rater prompt, user message = template of section 6.4. **Score-blind:** question and rendering only; no J, no judge span, no AH label, no draft. Output: `S` in {0,1}, a verbatim `span`, `R` in {0..3}. The deterministic span check, `S_final` and `R_floor` are defined in section 5.1.

**Experiment 1 -- test-retest (rater GLM-4.7-Flash, 182 cells).** Concurrency at most 3 per endpoint.

| run | prompt | temperature | seed sent | cell order | note |
|---|---|---|---|---|---|
| `a1` | base (S21 prompt) | 0 | 20260913 | sorted | also the Experiment 2 GLM rater |
| `a2` | base | 0 | 20260913 | sorted | started at least 30 min after `a1` started; identical request bodies; measures serving determinism only (batching and floating-point nondeterminism of a shared vLLM server), not sampling variance |
| `b1`, `b2`, `b3` | base | 0.7 | 20260914, 20260915, 20260916 | `random.Random(20260913 + 100k).shuffle(sorted ids)`, k = 1, 2, 3 | sampling variance; cell order differs in every run |
| `c1` | paraphrase P1 | 0 | 20260913 | sorted | meaning-preserving rewording, same order of sections |
| `c2` | paraphrase P2 | 0 | 20260913 | sorted | meaning-preserving rewording and reordered sections |

Run order: `a1, c1, c2, a2, b1, b2, b3` (so that `a2` is naturally separated from `a1`). `gptoss` runs concurrently on its own endpoint. If a run stops early (see 4.1) the experiment reports what completed; a condition set with a missing run is "not computable" and the status rule (5.4) then yields "unresolved".

**Experiment 2 -- cross-family raters (182 cells, base prompt, temperature 0, one run each).** Family raters: GLM (= run `a1`; the same request as a separate temperature-0 run, reused rather than repeated), gpt-oss-20b, and Claude if the route exists. Extra, not counted as cross-family: **`qwen` same-family contrast** (one run, temperature 0, 183 cells as in section 3; <internal-proxy> gateway, workers at most 3, pacing 1 request per second, hard cap 4,000,000 actual prompt tokens, estimate about 2.2M) and the descriptive label source `luna_s21` (188 cells, existing labels). `qwen` does not depend on the shared-server phase and may start right after the freeze.

**4.1 Stop rules (no retry loops).** Workers at most 3 per endpoint. HTTP 402/403, an HTTP 429 whose Retry-After exceeds 300 s, or 5 consecutive failed calls stop the run; 429/5xx/network errors are retried 3 times (5, 15, 45 s) inside a call; a reply that is not valid JSON is retried at most twice with the larger output budget (4096 tokens; 12288 for `qwen`) (any other failure leaves the cell without a valid record; nothing is imputed). Preflight on the two vLLM endpoints: the server's `/tokenize` gives exact prompt-token counts for every pending cell; a cell with prompt + 4096 > 65,536 tokens is skipped and logged (the gateway routes have no tokenizer endpoint; `qwen` uses the character estimate of section 3). The Claude route has a hard cap of 6,000,000 actual prompt tokens, the `qwen` route of 4,000,000 (estimate 1.9M by characters/4, about 3M with the 1.5x ratio seen for Sonnet), checked before each call. **Wall-clock deadline for all calls: 2026-10-17 14:00 UTC**; whatever is incomplete then is reported as incomplete. shared-server calls start only after the judge agent's call phase has ended (its two tmux sessions are gone), and endpoints are reached only by request.

## 5. Metrics, thresholds and the analysis path

Code path: `harness/review6_raters/analyze_raters.py` (this file's companion, committed with it). It imports `harness/analyze_holdout.py` (resampling routine pieces `_group_clusters`, `_bca_interval`, `_finite`, `_qwk_from_values`; and the **unchanged** audit, run as a subprocess) and `harness/llm_rater_luna_2026-10-15/rater_luna.py` (`read_labels`, label paths only). Run: `python3 analyze_raters.py selfcheck` then `python3 analyze_raters.py run [--claude haiku|opus]`. `selfcheck` verifies bit-exactness of the bootstrap against `analyze_holdout.cluster_bootstrap_stat`, the numpy QWK against `_qwk_from_values`, alpha against a naive coincidence-matrix implementation, and reproduces the S21 human-human kappa and QWK intervals.

**5.1 Labels per call.** `S_raw`, `R_raw` as returned. Span check: whitespace-normalised (`\s+` -> one space, strip), the cited span must be a substring of the whitespace-normalised rendering the rater saw; if `S_raw = 1` and the span is not a substring (or is empty), `S_final = 0`; the verbatim rate (S_raw=1 spans that pass) is reported for every labeler. `R_floor = max(R_raw, 1)` when `S_final = 1`, else `R_raw`. Both R versions are stored; **primary analyses use `S_final` and `R_floor`**; `S_raw` / `R_raw` are sensitivity analyses. The analysis recomputes the span check from the stored span and the material file and counts disagreements with the runner's stored flags.

**5.2 Resampling.** Whole-cluster bootstrap over CQ clusters, BCa 95%, B = 10,000, seed 20260913, midrank ties, leave-one-cluster-out jackknife: the scheme of `analyze_holdout.cluster_bootstrap_stat` (many statistics are evaluated on the same resamples).

**5.3 Experiment 1 statistics.** Krippendorff's alpha (nominal) on `S_final` across runs (cells as units, runs as coders); mean pairwise QWK on `R_floor` across runs (`_qwk_from_values` formula); pi-hat per run = share of cells with registered-judge J >= 2 and `S_final = 0` (`analyze_holdout._pi_stat`'s estimand), its range across runs in percentage points; each with its BCa interval. Sets: `all7` = a1, a2, b1, b2, b3, c1, c2; `a_temp0` = {a1, a2}; `b_temp07` = {b1, b2, b3}; `c_paraphrase` = {a1, c1, c2} (the original wording and its two paraphrases). Reference pi-hat for AH, the second rater and `luna_s21` on the same cells.
**Criteria (thresholds fixed here):** alpha lower bound >= 0.80; QWK lower bound >= 0.70; pi-hat range <= 5 pp (point estimate).

**5.4 Status rules (three states, applied mechanically).**
* *Row 1, "LLM-rater labels are stable across runs and prompts"* (rater = GLM-4.7-Flash; see section 1 for what this does not cover): **supported** iff all three criteria hold in `all7` and in each of `a_temp0`, `b_temp07`, `c_paraphrase` (alpha and QWK by lower bound, pi-hat range by point); **not supported** iff any criterion fails on its point estimate in `all7` or in any set; **unresolved** otherwise (all point estimates pass but a lower bound does not, or a set is incomplete).
* *Experiment 2 statistics.* Krippendorff alpha (nominal, `S_final`) across the family raters; pairwise Cohen kappa on `S_final` among all raters; kappa of each rater with AH and with the second rater; QWK on `R_floor` for the same pairs (descriptive); the same quantities for AH vs the second rater on the same cells as the reference.
* *Non-inferiority, pre-specified:* the benchmark is the human-human kappa on S, **kappa_source = 0.595** (AH vs second rater, 188 cells; BCa 95% interval [0.268, 0.833], very wide), the **margin is 0.10**, so a kappa is non-inferior when its BCa 95% lower bound is **>= 0.495** (the benchmark is treated as a fixed number, as the brief specifies). Because the benchmark itself is uncertain, a paired sensitivity is reported for every pair: kappa(pair) minus kappa(AH, second rater) on the same cells with its BCa interval, non-inferior when the lower bound exceeds -0.10. Both readings are reported; the primary status uses the fixed-benchmark reading.
* *Row 2, "independent LLM-rater families agree at the human-human level":* required kappas = every pairwise kappa among the family raters and every family rater with AH and with the second rater. **not supported** iff the point kappa of any required pair is below 0.495; **unresolved** iff fewer than 3 independent families have labels (the claim is about three; with two the maximum is "unresolved") or all point kappas are >= 0.495 but a lower bound is below it; **supported** iff 3 families and every required kappa has a lower bound >= 0.495. No multiplicity adjustment (an intersection of requirements).
* *Same-family contrast (descriptive, no threshold, never in a status rule):* kappa(S) of `qwen` with AH, with the second rater and with each other rater (these rows sit in the same pair table as the cross-family rows); mean kappa of `qwen` with the two humans against the mean of the cross-family raters with the two humans, and their difference; mean kappa of `qwen` with the cross-family raters against the mean kappa between cross-family raters, and their difference; per cross-family rater, kappa(`qwen`, human) minus kappa(rater, human); all with BCa intervals on the 182 common cells, plus `qwen` vs humans on all cells it scored. Reading: a difference whose interval excludes 0 would indicate that family overlap with the extractor (or the other differences between `qwen` and the cross-family raters: thinking on, size) changes agreement; an interval containing 0 shows no detectable difference at this sample size.
* *Majority-vote label source:* S = majority of `S_final`, R = median of `R_floor` over three raters (GLM, gpt-oss and Claude if available; otherwise GLM, gpt-oss and the S21 luna labels, flagged as a stand-in for the missing family); the 6 cells without a subgraph view carry the S21 luna label only (documented). The **unchanged** `analyze_holdout.py` is run on it exactly as for S21 (`--labels`, seed 20260913); pi-hat and the gate record are reported as returned.
* *Descriptive only:* on the cells where AH and the second rater disagree on S (aggregate counts only), which side each rater takes.

## 6. Prompts (full text)

All raters receive exactly one of these three system prompts; there is no other instruction. `base` is the S21 prompt, imported unchanged from `rater_luna.RATER_PROMPT` (sha256 `efb8a43fd89e6281777eb97047a91495c1aaba22ef96148735125c33db04f769`).

### 6.1 `base` (S21 rater prompt, sha256 `efb8a43fd89e6281777eb97047a91495c1aaba22ef96148735125c33db04f769`)

~~~~
당신은 온톨로지 자료가 질문에 답할 수 있는지 확인하는 평가자입니다. 아래 판정 기준은 사람 평가자가 라벨링 사이트에서 받는 기준과 같습니다(사이트 조작 방법만 뺐습니다). 질문 하나와 그 질문에 딸린 자료(텍스트) 하나를 받습니다. 자료에서 답의 근거를 찾아 판정해 주세요.

## 무엇을 판정하나요
각 질문마다 두 가지를 서로 독립적으로 입력합니다.
- S: 제공 자료 안에 글자 그대로의 구간이 질문의 답을 뒷받침하는가 (있다 / 없다)
- R: 자료가 질문에 얼마나 답하는가 (0~3점)
자료 밖 지식, 외부 검색, 본인의 배경지식으로 빈틈을 채우지 마세요.

## S와 R은 어떻게 다른가요
S는 '인용할 수 있는 문장이 있는가'를 묻고, R은 '자료 전체가 답으로 충분한가'를 묻습니다. S를 먼저 정하고, R은 S에 맞추지 말고 따로 판단합니다.
아래는 이 작업의 자료와 무관한 가상 예시(도서관 시스템)입니다.
Reservation | A request to hold an Item for a Member.
Loan | A borrowing of one Item by one Member for a fixed period.
Member | A person registered to borrow Items.
Event
Item
- 질문 A: What is a Reservation? — 첫 줄이 직접 정의합니다. S=1이고, 인용할 구간은 첫 줄입니다. 질문에 완전히 답하므로 R은 3입니다.
- 질문 B: Is Loan a subclass of Event? — Loan과 Event라는 이름은 보이지만 둘의 포함 관계를 말하는 문장은 없습니다. 주제가 가까운 것만으로는 근거가 아니므로 S=0입니다. 개념은 있고 핵심 관계가 빠졌으므로 R은 1에 가깝습니다. S=0이면 근거 칸을 비우고 메모에 이유를 씁니다.

## S: 근거 지지 여부 (0/1)
연구 프로토콜(PROTOCOL.md) 원문:
"Set `evidence_supported` to `1` only when a verbatim span in the supplied material supports the answer to the CQ. Set it to `0` when no such span exists. Copy the shortest sufficient verbatim span, preserving punctuation and whitespace where practical; if unsupported, leave the span empty and explain briefly why no supporting span exists. Do not infer support from the graph, external sources, or the annotator's knowledge."
제공 자료 안의 글자 그대로의 구간이 질문의 답을 뒷받침할 때만 S=1(근거 있음)입니다. 아니면 S=0(근거 없음)입니다. S=1이면 가장 짧은 충분 구간을 근거 칸에 복사하고, S=0이면 근거 칸을 비우고 메모에 이유를 짧게 씁니다. 자료 밖 지식, 외부 출처, 그래프 추론으로 채우지 않습니다.

## R: 자료가 질문에 답하는 정도 (0–3)
- 0  관련된 개념이나 관계가 없다.
- 1  부분적: 개념은 있지만 핵심 관계나 계층이 빠져 있다.
- 2  대체로: 핵심 개념과 관계가 있고 사소한 빈틈만 있다.
- 3  완전: 질문에 완전히 답한다.
R은 S를 정한 뒤에 입력하되, S 값에 맞추지 말고 자료의 답변 충분성만 보고 매깁니다. S=0인데 R이 높거나 그 반대도 가능합니다.

## 경계 예시(안내서 기준)
- 관련 개념은 있지만 질문이 묻는 핵심 관계나 계층을 문장으로 말하지 않으면 S=0입니다. 주제가 가깝다는 것만으로는 근거가 아닙니다(R 앵커 1의 '부분적'에 해당).
- 핵심 개념과 요구된 관계가 있고 작은 세부만 빠졌다면 S=1이며, 답을 뒷받침하는 구간을 인용합니다(R 앵커 2의 '대체로'에 해당).
- 개념과 관계·정의가 질문에 직접 답하도록 적혀 있으면 S=1이며, 가장 짧은 충분 구간을 인용합니다(R 앵커 3의 '완전'에 해당).
확신이 없으면 자료를 머릿속으로 보충하지 마세요. 글자 그대로 인용할 충분한 구간이 없으면 S=0으로 하고, 불확실한 이유를 메모에 적습니다.

## 근거 구간은 어떻게 고르나요
- 자료에서 질문의 핵심 단어를 찾습니다(대소문자 구분 없음).
- 답을 뒷받침하는 가장 짧은 구간을 고릅니다.
- 관계는 기호로 적혀 있어요. 'A < B'는 A가 B의 하위 클래스, 'IND X a T'는 X가 T의 사례라는 뜻이에요.
- 구두점과 공백은 가능한 한 원문 그대로 둡니다. 직접 고쳐 쓰면 '원문에서 찾을 수 없음'으로 표시됩니다.

## 자료 읽는 법 (기호 설명)
- `A | 이름 < B,C` : A는 B와 C의 하위 클래스(subClassOf)예요. 예: `Building < …#Location`은 Building이 Location의 하위 클래스라는 뜻.
- `:: 문장` : 그 항목의 정의·설명이에요.
- `IND X | 이름 a T` : X는 T의 사례(인스턴스, type)예요.
- `OP P dom:D rng:R inv:I` : 속성 P의 정의역(D)·치역(R)·역관계(I)예요. DP는 값 속성이에요.
- `{p=o; …}` : 그 밖의 관계(술어 p의 값 o)예요.

## 지켜 주세요
- 파이프라인·모델 출력, 점수, 정답 후보를 알아내려 하지 않습니다. 자료 이름이나 내용으로 어떤 변형인지 추측하지 않습니다.

## 출력 형식
다른 글 없이 JSON 객체 하나만 출력합니다.
{"S": 0 또는 1, "R": 0~3의 정수, "span": "S=1이면 자료 원문 그대로의 가장 짧은 충분 구간, S=0이면 빈 문자열", "note": "S=0이면 근거가 없는 이유(필수), S=1이면 필요할 때만 짧은 메모"}
~~~~

### 6.2 `p1` (paraphrase 1: reworded, same section order; sha256 `e87a41f5e22c26499390265b1c80dc44bfbf7e84b364480054bc189167519ff5`)

~~~~
당신은 온톨로지로 만든 자료가 주어진 질문에 답을 줄 수 있는지 점검하는 심사자입니다. 이 판정 규칙은 사람 심사자가 라벨링 사이트에서 읽는 규칙과 동일합니다(사이트 사용법만 제외했습니다). 입력으로 질문 하나와 그 질문에 붙은 자료(텍스트) 하나가 주어집니다. 자료 안에서 답의 근거를 찾아 판정하세요.

## 판정 항목
질문마다 서로 독립인 두 값을 정합니다.
- S: 제공된 자료 안에, 글자 그대로 옮길 수 있는 구간이 질문의 답을 뒷받침하는지 (있음 / 없음)
- R: 자료가 질문에 답하는 정도 (0~3점)
자료 밖의 지식, 외부 검색, 개인적인 배경지식으로 빈 곳을 메우지 마세요.

## S와 R의 차이
S는 "인용할 만한 문장이 있는가"를 묻고, R은 "자료 전체가 답으로 충분한가"를 묻습니다. S를 먼저 정한 다음, R은 S에 끌려가지 말고 따로 판단하세요.
다음은 이 과제의 자료와 관련 없는 가상의 예(도서관 시스템)입니다.
Reservation | A request to hold an Item for a Member.
Loan | A borrowing of one Item by one Member for a fixed period.
Member | A person registered to borrow Items.
Event
Item
- 질문 A: What is a Reservation? — 첫 줄이 곧바로 정의합니다. S=1이며 인용 구간은 첫 줄입니다. 질문에 완전히 답하므로 R은 3입니다.
- 질문 B: Is Loan a subclass of Event? — Loan과 Event라는 이름은 나오지만 둘의 포함 관계를 말하는 문장은 없습니다. 주제가 비슷하다는 것만으로는 근거가 되지 않으므로 S=0입니다. 개념은 있으나 핵심 관계가 없으니 R은 1에 가깝습니다. S=0일 때는 근거 칸을 비워 두고 메모에 이유를 적습니다.

## S: 근거가 뒷받침되는가 (0/1)
연구 프로토콜(PROTOCOL.md)의 원문은 다음과 같습니다.
"Set `evidence_supported` to `1` only when a verbatim span in the supplied material supports the answer to the CQ. Set it to `0` when no such span exists. Copy the shortest sufficient verbatim span, preserving punctuation and whitespace where practical; if unsupported, leave the span empty and explain briefly why no supporting span exists. Do not infer support from the graph, external sources, or the annotator's knowledge."
요약하면, 제공된 자료 안의 글자 그대로의 구간이 질문의 답을 뒷받침할 때에만 S=1(근거 있음)이고, 그렇지 않으면 S=0(근거 없음)입니다. S=1이면 가장 짧으면서 충분한 구간을 근거 칸에 그대로 복사하고, S=0이면 근거 칸을 비운 채 메모에 이유를 짧게 적습니다. 자료 밖 지식, 외부 출처, 그래프에서의 추론으로 채우지 않습니다.

## R: 자료가 질문에 답하는 정도 (0~3)
- 0  관련된 개념이나 관계가 전혀 없다.
- 1  부분적: 개념은 있으나 핵심 관계나 계층이 빠져 있다.
- 2  대체로: 핵심 개념과 관계가 있고 사소한 빈틈만 남아 있다.
- 3  완전: 질문에 완전히 답한다.
R은 S를 정한 뒤에 적되, S 값에 맞추지 말고 자료가 답으로 얼마나 충분한지만 보고 매기세요. S=0인데 R이 높을 수도, 그 반대일 수도 있습니다.

## 경계 사례 (안내서 기준)
- 관련 개념은 있어도 질문이 묻는 핵심 관계나 계층을 문장으로 말하지 않으면 S=0입니다. 주제가 가깝다는 것만으로는 근거가 아닙니다(R 앵커 1, '부분적').
- 핵심 개념과 요구된 관계가 있고 작은 세부만 빠졌다면 S=1이며, 답을 뒷받침하는 구간을 인용합니다(R 앵커 2, '대체로').
- 개념과 관계·정의가 질문에 곧바로 답하도록 적혀 있으면 S=1이며, 가장 짧으면서 충분한 구간을 인용합니다(R 앵커 3, '완전').
확신이 서지 않으면 자료를 머릿속으로 보충하지 마세요. 글자 그대로 인용할 충분한 구간이 없다면 S=0으로 하고, 확신하지 못하는 이유를 메모에 남기세요.

## 근거 구간 고르는 법
- 자료에서 질문의 핵심 단어를 찾으세요(대소문자는 구분하지 않습니다).
- 답을 뒷받침하는 가장 짧은 구간을 고르세요.
- 관계는 기호로 표기되어 있습니다. 'A < B'는 A가 B의 하위 클래스, 'IND X a T'는 X가 T의 사례라는 뜻입니다.
- 구두점과 공백은 가능한 한 원문 그대로 두세요. 직접 고쳐 쓰면 '원문에서 찾을 수 없음'으로 처리됩니다.

## 자료 기호 읽는 법
- `A | 이름 < B,C` : A는 B와 C의 하위 클래스(subClassOf)입니다. 예: `Building < …#Location`은 Building이 Location의 하위 클래스라는 뜻입니다.
- `:: 문장` : 해당 항목의 정의·설명입니다.
- `IND X | 이름 a T` : X는 T의 사례(인스턴스, type)입니다.
- `OP P dom:D rng:R inv:I` : 속성 P의 정의역(D), 치역(R), 역관계(I)입니다. DP는 값 속성입니다.
- `{p=o; …}` : 그 밖의 관계(술어 p의 값 o)입니다.

## 주의 사항
- 파이프라인이나 모델의 출력, 점수, 정답 후보를 알아내려 하지 마세요. 자료의 이름이나 내용을 보고 어떤 변형인지 짐작하지 마세요.

## 출력 형식
다른 글은 쓰지 말고 JSON 객체 하나만 출력하세요.
{"S": 0 또는 1, "R": 0~3의 정수, "span": "S=1이면 자료 원문 그대로의 가장 짧고 충분한 구간, S=0이면 빈 문자열", "note": "S=0이면 근거가 없는 이유(필수), S=1이면 필요할 때만 짧은 메모"}
~~~~

### 6.3 `p2` (paraphrase 2: reworded, sections reordered; sha256 `3e281e10eacbf6f664194a2ab599de572dd2c1c2cc83f6d72243f2dd4059cb75`)

~~~~
온톨로지 자료가 질문에 답할 수 있는지 판정하는 평가를 맡았습니다. 판정 기준은 사람 평가자가 라벨링 사이트에서 받는 것과 같고, 사이트 조작 설명만 빠져 있습니다. 질문 하나와 자료(텍스트) 하나가 주어지면, 자료에서 답의 근거를 찾아 아래 순서대로 판정하세요.

## 먼저 자료 읽는 법
- `A | 이름 < B,C` : A는 B와 C의 하위 클래스(subClassOf)라는 표기입니다. 예: `Building < …#Location`은 Building이 Location의 하위 클래스라는 뜻입니다.
- `:: 문장` : 그 항목의 정의 또는 설명입니다.
- `IND X | 이름 a T` : X는 T의 사례(인스턴스, type)입니다.
- `OP P dom:D rng:R inv:I` : 속성 P의 정의역은 D, 치역은 R, 역관계는 I입니다. DP는 값 속성을 가리킵니다.
- `{p=o; …}` : 위에 해당하지 않는 관계로, 술어 p의 값이 o라는 뜻입니다.

## 정해야 할 두 가지 값
두 값은 서로 독립적으로 정합니다.
- S (0 또는 1): 제공된 자료 안에 글자 그대로의 구간이 있어 그 구간이 질문의 답을 뒷받침하면 1, 없으면 0
- R (0~3의 정수): 자료가 질문에 얼마나 답을 주는지에 대한 점수
자료에 없는 내용은 쓰지 않습니다. 외부 검색, 외부 지식, 평가자 본인의 배경지식으로 부족한 부분을 채우는 것은 금지입니다.

## S 기준
연구 프로토콜(PROTOCOL.md) 원문:
"Set `evidence_supported` to `1` only when a verbatim span in the supplied material supports the answer to the CQ. Set it to `0` when no such span exists. Copy the shortest sufficient verbatim span, preserving punctuation and whitespace where practical; if unsupported, leave the span empty and explain briefly why no supporting span exists. Do not infer support from the graph, external sources, or the annotator's knowledge."
쉬운 말로 풀면 이렇습니다. 자료 안의 글자 그대로의 구간이 질문의 답을 뒷받침할 때만 S=1이고, 아니면 S=0입니다. S=1이면 충분한 구간 중 가장 짧은 것을 근거 칸에 복사합니다. S=0이면 근거 칸은 비우고 왜 근거가 없는지 메모에 짧게 씁니다. 자료 밖 지식, 외부 출처, 그래프에서 끌어낸 추론은 근거가 아닙니다.

## 근거 구간 선택
- 질문의 핵심 단어를 자료에서 찾습니다(대소문자 무시).
- 답을 뒷받침하는 구간 가운데 가장 짧은 것을 고릅니다.
- 관계는 기호로 적혀 있습니다. 'A < B'는 A가 B의 하위 클래스, 'IND X a T'는 X가 T의 사례입니다.
- 구두점과 공백은 되도록 원문 그대로 둡니다. 임의로 고쳐 쓰면 '원문에서 찾을 수 없음'으로 표시됩니다.

## R 기준
- 0  관련된 개념도 관계도 없다.
- 1  부분적: 개념은 나오지만 핵심 관계나 계층이 빠져 있다.
- 2  대체로: 핵심 개념과 관계가 있고, 사소한 빈틈만 있다.
- 3  완전: 질문에 완전히 답한다.
S를 정한 다음에 R을 매기되, R은 S와 무관하게 자료가 답으로 충분한지만 기준으로 삼습니다. S=0이면서 R이 높거나, S=1이면서 R이 낮은 경우도 가능합니다.

## S와 R의 구분, 그리고 경계 사례
S는 "인용할 문장이 있는가", R은 "자료 전체가 답이 되기에 충분한가"를 묻는 것입니다. 아래는 이 과제의 자료와 무관한 가상의 도서관 시스템 예시입니다.
Reservation | A request to hold an Item for a Member.
Loan | A borrowing of one Item by one Member for a fixed period.
Member | A person registered to borrow Items.
Event
Item
- 질문 A: What is a Reservation? — 첫 줄이 직접 정의하므로 S=1이고 인용 구간은 첫 줄입니다. 질문에 완전히 답하므로 R=3입니다.
- 질문 B: Is Loan a subclass of Event? — Loan과 Event가 각각 나오지만 둘이 포함 관계라는 문장은 없습니다. 주제가 가깝다는 이유만으로는 근거가 되지 않으니 S=0입니다. 개념은 있고 핵심 관계가 빠졌으므로 R은 1 근처입니다. S=0이면 근거 칸을 비우고 메모에 이유를 씁니다.
경계 판단 원칙(안내서 기준):
- 관련 개념이 있어도 질문이 묻는 핵심 관계·계층이 문장으로 서술되어 있지 않으면 S=0 (R 앵커 1, '부분적').
- 핵심 개념과 요구된 관계가 있고 작은 세부만 없다면 S=1이며, 답을 뒷받침하는 구간을 인용 (R 앵커 2, '대체로').
- 개념과 관계·정의가 질문에 직접 답하도록 적혀 있으면 S=1이며, 충분한 구간 중 가장 짧은 것을 인용 (R 앵커 3, '완전').
자신이 없을 때 자료를 상상으로 보충하지 마세요. 글자 그대로 인용할 충분한 구간이 없으면 S=0이고, 불확실한 이유를 메모에 적습니다.

## 금지 사항
- 파이프라인·모델의 출력, 점수, 정답 후보를 알아내려고 하지 않습니다. 자료의 이름이나 내용에서 어떤 변형인지 추측하지도 않습니다.

## 답변 형식
설명 없이 JSON 객체 하나만 출력합니다.
{"S": 0 또는 1, "R": 0~3의 정수, "span": "S=1이면 자료 원문 그대로의 가장 짧은 충분 구간, S=0이면 빈 문자열", "note": "S=0이면 근거가 없는 이유(필수), S=1이면 필요할 때만 짧은 메모"}
~~~~

**Equivalence checklist (author to verify).** Both paraphrases keep: the task framing and the statement that the rules equal the human site's; the two independent outputs S and R; the ban on outside knowledge; the S-versus-R explanation; the identical library example with questions A and B and their S/R readings; the PROTOCOL.md quotation (English, verbatim); the S rule (verbatim span, shortest sufficient span, empty span and a note when S=0); the four R anchors 0-3 with the same wording of each anchor; the three boundary cases with the R-anchor links; the span-selection rules; the symbol legend (`<`, `::`, `IND`, `OP/DP`, `{p=o}`); the ban on guessing pipeline or variant; the JSON output contract with the same four keys in the same order. Equivalence is by hand, not by a back-translation test; a residual difference in meaning would show up as lower agreement in condition (c) and cannot be separated from sensitivity to wording.

### 6.4 User message (identical for every rater and prompt)

~~~~
자료:
<material text>

범주: <Korean category>
질문: <question>
참고 번역: <Korean reference translation>      (line omitted when there is none)
~~~~

## 7. Dry-run before the freeze

* **Offline harness test (local fake OpenAI-compatible server, no network, no key):** `test_raters.py`, 26 checks, all pass: a 5-cell dry-run through `run_rater.py` (positions 0, 40, 80, 120, 160 of the sorted 182-cell list); a full 182-cell run and its resume (a second invocation sends nothing); at most 3 concurrent requests; the span check forces `S_final = 0` for a non-verbatim span and `R_floor >= 1` when `S_final = 1`; an invalid first reply is retried with the larger budget; a context-length reply is recorded as `context_skip`; HTTP 429 with a long Retry-After stops the run; a token budget below the first call's estimate prevents any call; the request bodies of run `a1` (temperature 0.0, seed 20260913), `b2` (temperature 0.7, seed 20260915) and the paraphrase prompts (`c1` uses P1); the analysis end to end, including the unchanged audit on the majority-vote labels. `analyze_raters.py selfcheck` passes (bit-exact bootstrap; reproduces the S21 human-human kappa 0.5950 [0.2677, 0.8331] and QWK 0.7279 [0.5667, 0.8591]).
* **Live 5-cell dry-run, `qwen` through the <internal-proxy> gateway (request-only; cells A:CQB01, B:CQB20, F:CQB11, E:CQB03, C:CQB30):** 5 of 5 replies valid on the first attempt; prompt tokens 48,843 against an estimate of 42,506 (ratio 1.15); completion tokens 10,964 (largest 4,966, so the first-attempt budget of 6,144 holds); latency 8.6-81 s per call with thinking on. The outputs are discarded and these 5 cells are re-run inside the experiment; the file `raw/dry_qwen.jsonl` stays for the token count and is excluded from every analysis by its `dry_` prefix. This dry-run is where the thinking-on setting and the larger output budget of `qwen` were fixed.
* **`gpt-5.6-luna` (<internal-proxy>):** the live dry-run was attempted at 09:27-09:31 UTC; every call that was sent (7) returned HTTP 402 "Payment Required", some after HTTP 429 replies with Retry-After 60 s; the other 2 were not sent (the run stopped on the first 402, as the runner's stop rule requires). No label was produced. This is the observation behind the amendment in section 1.
* **Anthropic route (<internal-proxy>):** HTTP 401 "Not logged in to anthropic" for `claude-haiku-5-5` and `claude-opus-5-5` (one tiny call each, no experiment input).
* **shared-server raters (`glm`, `gptoss`): no live dry-run before the freeze.** The judge agent's call phase on the same two endpoints was still running at the freeze, and shared-server calls are to start only after it ends. Their first calls are therefore real calls. No change to sections 3-6 is made after seeing their labels: invalid replies, context skips and server errors are reported as they occur (4.1); any change would need a new addendum.


## 8. Pins at freeze

* Repository HEAD at freeze: recorded in the commit; the working tree has unrelated uncommitted files of other sessions that are not touched.
* Files (sha256 at freeze; only `PLAN.md` and `analyze_raters.py` are committed, the others are listed so that the run can be checked against them):
* `cells_manifest.json` `112e49e1c7f80b77d390c62c6f6e8f85f00299707edddfd7e343d2218fde5a2d`
* `prompts.py` `bcad86af1baea524a30f923f480ba8e0e91f2fa20e1a426754f804678a214db3`
* `build_inputs.py` `d79d03c60837e822341c4f7b37d328d7d8be6856d2edb7a8dbfd26898ae63817`
* `run_rater.py` `1ec60a7ea047d49a83d278682ffc9556e43964115c4318eef13b5d3aa2d1d99d`
* `test_raters.py` `c2d622fe175220c98df5a9a08f913beae3cce2387363f4c33176d7a4462a53a0`
* `analyze_raters.py` `dbf40ecb49bec615ad3e200f21b45f36c3cdb5a6aa225fe51ea40a4096ff9f2f`
* Registered inputs unchanged: bank `bank/cq_bank_brick_v1.csv`, length-experiment manifest, `harness/real_run/cells.jsonl`, S21 raw file.

## 9. Outputs

Under `harness/review6_raters/`: `PLAN.md`, `analyze_raters.py` (committed); `build_inputs.py`, `prompts.py`, `run_rater.py`, `test_raters.py`, `make_plan.py`, `cells_manifest.json`, `raw/<run>.jsonl` and `raw/<run>.meta.jsonl` (calls, tokens, wall time, stop reasons), `results.json`, `REPORT_auto.md`, `REPORT.md`, `labels_for_analysis_majority.csv`, `holdout_results_majority.json` (aggregate only). The per-cell file of the unchanged audit is written outside the repository. Checkpoints go to the session progress file after each step and about every 50% and 100% of each run.

## 10. Limitations stated before the run

* The rater is not the S21 rater; conclusions about luna's own stability are not available.
* One rater model (GLM-4.7-Flash, thinking switched off, a shared bf16 vLLM server) carries Experiment 1; its stability may not transfer to other raters. At temperature 0 differences between `a1` and `a2` measure serving nondeterminism only.
* The raters see the subgraph, not the full rendering the human raters saw; evidence outside the subgraph is invisible to them. The 6 cells without a subgraph are not rated by the new raters.
* The span check can only lower `S`; humans were not held to it. Kappa with a human is agreement, not accuracy, and AH labels were AI-drafted and first-author-revised.
* The human-human kappa interval ([0.268, 0.833]) is wide: non-inferiority against a fixed 0.595 with a 0.10 margin is a strong requirement that 182 cells in 32 clusters are unlikely to resolve; "unresolved" is the expected outcome for several rows and is a result.
* At most two independent families unless the Anthropic route is authenticated; gpt-oss-20b and luna share a vendor.
* The contrast rater differs from the cross-family raters in more than family: it reasons before answering (thinking cannot be switched off through the gateway), is a different size, and runs on a different server; one contrast rater cannot isolate family overlap. It is also served by NVFP4 weights.
* Paraphrase equivalence is by hand.
* Exploratory: no confirmatory threshold; every result is reported, including failures to meet a criterion.

## 11. Events that must not happen before this freeze

1. A scoring call by any new rater on an experiment input beyond the 5-cell dry-run of section 7 (discarded). 2. Reading any label of a new rater on an experiment cell beyond those 5 dry-run cells. 3. Changing sections 3-6 after seeing a label of a new rater on an experiment cell. Allowed and done before the freeze: code and offline tests with a local fake server (`test_raters.py`, all checks pass), the selfcheck, building `cells_manifest.json`, the probes of section 1 (availability only, no experiment input), the tokenizer preflight on the pending cells.
