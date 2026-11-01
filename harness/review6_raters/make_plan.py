#!/usr/bin/env python3
"""Generate PLAN.md (addendum 28) from prompts.py, cells_manifest.json and the pinned files.  AI-generated; review before use."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prompts as P  # noqa: E402


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


m = json.loads((HERE / "cells_manifest.json").read_text(encoding="utf-8"))
cells = sorted(m["cells"], key=lambda c: c["cell_id"])
sub = [c for c in cells if c["view_kind"] == "subgraph"]
fb = [c for c in cells if c["view_kind"] != "subgraph"]
byv = {}
for c in sub:
    byv.setdefault(c["variant"], []).append(c["cq_id"])
clusters = sorted({c["cluster_id"] for c in sub})
ids182 = "\n".join(c["cell_id"] for c in sub)
dry = (HERE / "dryrun_notes.md").read_text(encoding="utf-8") if (HERE / "dryrun_notes.md").exists() else "(to be filled after the live dry-run)"
pins = {
    "cells_manifest.json": sha(HERE / "cells_manifest.json"),
    "prompts.py": sha(HERE / "prompts.py"),
    "build_inputs.py": sha(HERE / "build_inputs.py"),
    "run_rater.py": sha(HERE / "run_rater.py"),
    "test_raters.py": sha(HERE / "test_raters.py"),
    "analyze_raters.py": sha(HERE / "analyze_raters.py"),
}
pin_lines = "\n".join(f"* `{k}` `{v}`" for k, v in pins.items())
cell_table = "\n".join(f"| {v} | {len(byv[v])} | {', '.join(q.replace('CQB', '') for q in byv[v])} |" for v in sorted(byv))
doc = f"""# PREREG addendum 28 (exploratory) -- LLM-rater stability and cross-family agreement, without human labeling

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

* **Primary set for both experiments: the 182 primary holdout cells that have a subgraph view** ({len(clusters)} CQ clusters). The 188 primary cells minus **6 cells with no subgraph** ({', '.join(c['cell_id'].replace('primary:', '') for c in fb)}); S21 gave those 6 the full rendering (about 73k tokens for A-CQB27, 490k-600k for B-F CQB32), which does not fit a 65,536-token window; they are not rated by GLM, gpt-oss or Claude (the only exception is the contrast rater `qwen`, whose window holds A-CQB27) and the skips are logged. Per variant (CQ numbers):

| variant | cells | CQ ids (CQB..) |
|---|---|---|
{cell_table}

* **Contrast rater coverage ("all 188 cells"):** `qwen` is sent every one of the 188 cells except those whose estimated prompt (characters / 4) plus the retry budget exceeds its 262,144-token window. By the estimates in `cells_manifest.json` that is the 5 cells B-F CQB32 (about 488k-604k tokens); A-CQB27 (about 74k tokens, full view) fits and is sent. So `qwen` rates 183 cells; the 5 unsent cells are logged as `context_skip`. Pairwise comparisons with the other raters use the 182 common cells; `qwen` vs the humans is also reported on all cells it scored.
* Material = the question-relevant subgraph text of the length experiment (`length_experiment/inputs/<V>/<CQ>/subgraph.txt`), each file sha256-checked against `inputs/manifest.jsonl`, and the **same text luna saw in S21** (`cells_manifest.json` was built only after checking that every one of the 188 materials has exactly the `view_sha256` stored in the S21 raw file). Question text, Korean category and Korean reference translation come from the labeling-site cell file (`labeling_site/data/cells.json`, keyed by an opaque id) matched to the bank by question text; **the key files, the rater zip and the human export are never opened**.
* The 182 cell ids (sha256 of the sorted list `{hashlib.sha256(ids182.encode()).hexdigest()}`) are `primary:<variant>:<CQ>` for every row of `cells_manifest.json` with `view_kind == "subgraph"`. AH labels (`locked_labels/primary_working.csv`) and second-rater labels (`annotation/second_pass_2026-10-13/v3/labels_for_analysis_v3.csv`) are read by `analyze_raters.py` only through the existing readers `rater_luna.read_labels`; per-cell human labels are never written to a repository file.
* Judge scores J for pi-hat are the registered holdout judge's (`harness/real_run/cells.jsonl`).

## 4. Conditions

Every call is one request with no conversation history: system message = rater prompt, user message = template of section 6.4. **Score-blind:** question and rendering only; no J, no judge span, no AH label, no draft. Output: `S` in {{0,1}}, a verbatim `span`, `R` in {{0..3}}. The deterministic span check, `S_final` and `R_floor` are defined in section 5.1.

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

**5.1 Labels per call.** `S_raw`, `R_raw` as returned. Span check: whitespace-normalised (`\\s+` -> one space, strip), the cited span must be a substring of the whitespace-normalised rendering the rater saw; if `S_raw = 1` and the span is not a substring (or is empty), `S_final = 0`; the verbatim rate (S_raw=1 spans that pass) is reported for every labeler. `R_floor = max(R_raw, 1)` when `S_final = 1`, else `R_raw`. Both R versions are stored; **primary analyses use `S_final` and `R_floor`**; `S_raw` / `R_raw` are sensitivity analyses. The analysis recomputes the span check from the stored span and the material file and counts disagreements with the runner's stored flags.

**5.2 Resampling.** Whole-cluster bootstrap over CQ clusters, BCa 95%, B = 10,000, seed 20260913, midrank ties, leave-one-cluster-out jackknife: the scheme of `analyze_holdout.cluster_bootstrap_stat` (many statistics are evaluated on the same resamples).

**5.3 Experiment 1 statistics.** Krippendorff's alpha (nominal) on `S_final` across runs (cells as units, runs as coders); mean pairwise QWK on `R_floor` across runs (`_qwk_from_values` formula); pi-hat per run = share of cells with registered-judge J >= 2 and `S_final = 0` (`analyze_holdout._pi_stat`'s estimand), its range across runs in percentage points; each with its BCa interval. Sets: `all7` = a1, a2, b1, b2, b3, c1, c2; `a_temp0` = {{a1, a2}}; `b_temp07` = {{b1, b2, b3}}; `c_paraphrase` = {{a1, c1, c2}} (the original wording and its two paraphrases). Reference pi-hat for AH, the second rater and `luna_s21` on the same cells.
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

All raters receive exactly one of these three system prompts; there is no other instruction. `base` is the S21 prompt, imported unchanged from `rater_luna.RATER_PROMPT` (sha256 `{P.SHA['base']}`).

### 6.1 `base` (S21 rater prompt, sha256 `{P.SHA['base']}`)

~~~~
{P.BASE}
~~~~

### 6.2 `p1` (paraphrase 1: reworded, same section order; sha256 `{P.SHA['p1']}`)

~~~~
{P.P1}
~~~~

### 6.3 `p2` (paraphrase 2: reworded, sections reordered; sha256 `{P.SHA['p2']}`)

~~~~
{P.P2}
~~~~

**Equivalence checklist (author to verify).** Both paraphrases keep: the task framing and the statement that the rules equal the human site's; the two independent outputs S and R; the ban on outside knowledge; the S-versus-R explanation; the identical library example with questions A and B and their S/R readings; the PROTOCOL.md quotation (English, verbatim); the S rule (verbatim span, shortest sufficient span, empty span and a note when S=0); the four R anchors 0-3 with the same wording of each anchor; the three boundary cases with the R-anchor links; the span-selection rules; the symbol legend (`<`, `::`, `IND`, `OP/DP`, `{{p=o}}`); the ban on guessing pipeline or variant; the JSON output contract with the same four keys in the same order. Equivalence is by hand, not by a back-translation test; a residual difference in meaning would show up as lower agreement in condition (c) and cannot be separated from sensitivity to wording.

### 6.4 User message (identical for every rater and prompt)

~~~~
자료:
<material text>

범주: <Korean category>
질문: <question>
참고 번역: <Korean reference translation>      (line omitted when there is none)
~~~~

## 7. Dry-run before the freeze

{dry}

## 8. Pins at freeze

* Repository HEAD at freeze: recorded in the commit; the working tree has unrelated uncommitted files of other sessions that are not touched.
* Files (sha256 at freeze; only `PLAN.md` and `analyze_raters.py` are committed, the others are listed so that the run can be checked against them):
{pin_lines}
* Registered inputs unchanged: bank `bank/cq_bank_brick_v1.csv`, length-experiment manifest, `harness/real_run/cells.jsonl`, S21 raw file.

## 9. Outputs

Under `harness/review6_raters/`: `PLAN.md`, `analyze_raters.py` (committed); `build_inputs.py`, `prompts.py`, `run_rater.py`, `test_raters.py`, `make_plan.py`, `cells_manifest.json`, `raw/<run>.jsonl` and `raw/<run>.meta.jsonl` (calls, tokens, wall time, stop reasons), `results.json`, `REPORT_auto.md`, `REPORT.md`, `labels_for_analysis_majority.csv`, `holdout_results_majority.json` (aggregate only). The per-cell file of the unchanged audit is written outside the repository. Checkpoints go to the session progress file after each step and about every 50% and 100% of each run.

## 10. Limitations stated before the run

* The rater is not the S21 rater; conclusions about luna's own stability are not available.
* One rater model (GLM-4.7-Flash, thinking switched off, a shared bf16 vLLM server) carries Experiment 1; its stability may not transfer to other raters. At temperature 0 differences between `a1` and `a2` measure serving nondeterminism only.
* The raters see the subgraph, not the full rendering the human raters saw; evidence outside the subgraph is invisible to them. The 6 cells without a subgraph are not rated by the new raters.
* The span check can only lower `S`; humans were not held to it. Kappa with a human is agreement, not accuracy, and AH labels were AI-drafted and first-author-revised.
* The human-human kappa interval ([0.268, 0.833]) is wide: non-inferiority against a fixed 0.595 with a 0.10 margin is a strong requirement that 182 cells in {len(clusters)} clusters are unlikely to resolve; "unresolved" is the expected outcome for several rows and is a result.
* At most two independent families unless the Anthropic route is authenticated; gpt-oss-20b and luna share a vendor.
* The contrast rater differs from the cross-family raters in more than family: it reasons before answering (thinking cannot be switched off through the gateway), is a different size, and runs on a different server; one contrast rater cannot isolate family overlap. It is also served by NVFP4 weights.
* Paraphrase equivalence is by hand.
* Exploratory: no confirmatory threshold; every result is reported, including failures to meet a criterion.

## 11. Events that must not happen before this freeze

1. A scoring call by any new rater on an experiment input beyond the 5-cell dry-run of section 7 (discarded). 2. Reading any label of a new rater on an experiment cell beyond those 5 dry-run cells. 3. Changing sections 3-6 after seeing a label of a new rater on an experiment cell. Allowed and done before the freeze: code and offline tests with a local fake server (`test_raters.py`, all checks pass), the selfcheck, building `cells_manifest.json`, the probes of section 1 (availability only, no experiment input), the tokenizer preflight on the pending cells.
"""
(HERE / "PLAN.md").write_text(doc, encoding="utf-8")
print("PLAN.md", len(doc), "chars")
for k, v in pins.items():
    print(k, v)
