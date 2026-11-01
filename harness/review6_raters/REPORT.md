# Addendum 28 -- LLM-rater stability and cross-family agreement: REPORT

AI-generated report; post hoc with respect to the original plan, pre-specified with respect to these runs (`PLAN.md`, commit `c8328bf`, written before the first scoring call). Code, commands and figures here are AI-generated and must be reviewed and tested by a person before reuse; nothing in this directory is to be applied to a production system without that review. Per-cell human labels are not reproduced anywhere in this directory (aggregates only).

**Claim ceiling kept:** the experiments ask whether LLM-rater labels are stable, whether independent families agree, and whether agreement is comparable to human-human. They do not measure accuracy and nothing below should be read as "LLMs are more accurate".

## 1. Result in one paragraph

Both candidate Table 10 rows come out **not supported**. A GLM-4.7-Flash rater using the S21 prompt reproduces its own labels when the request is repeated at temperature 0 (alpha 0.91 [0.77, 0.98]), but not at temperature 0.7 (alpha 0.21 [0.11, 0.34]) and not under two reworded prompts (alpha 0.60 [0.51, 0.72]); pooled, alpha is 0.40 [0.31, 0.52], QWK 0.49 [0.40, 0.60] and the range of the unsupported-credit estimate pi-hat is 22.0 pp (criteria: alpha lower bound >= 0.80, QWK lower bound >= 0.70, range <= 5 pp). Two independent families (Zhipu, OpenAI-open) agree with each other at kappa 0.20 [0.04, 0.36] and with the humans at kappa -0.06 to 0.16, far below the human-human 0.595 (non-inferiority floor 0.495; 5 of 5 required kappas fail on the point estimate). A Qwen rater of the extractor's family does not differ detectably from them. The third family (Anthropic) could not be reached, and the original test-retest of the S21 rater (luna) could not run, because the luna quota was exhausted (HTTP 402).

## 2. What was run, against the original brief

| item | original brief | what ran | why |
|---|---|---|---|
| Experiment 1 rater | `gpt-5.6-luna` via <internal-proxy>, 188 cells, S21 labels as run 0 | **GLM-4.7-Flash** (a shared server, vLLM, request-only), 182 cells with a subgraph view, runs a1, a2, b1-b3, c1, c2 (7 runs, all 182/182 valid) | <internal-proxy> luna answered HTTP 402 / 429 on every dry-run call; coordinator instruction. The S21 luna labels became a separate label source; the S21 rater itself was **not** retested |
| Experiment 2 families | OpenAI luna, Zhipu GLM, Anthropic non-Sonnet Claude (+ gpt-oss) | **Zhipu GLM-4.7-Flash** (= run a1) and **OpenAI-open gpt-oss-20b**, 182/182 valid each; **no Anthropic run** | <internal-proxy> Anthropic route: HTTP 401 "Not logged in" (authentication failed; user action). A read-only scan of all reachable model servers found no other non-Qwen, non-Google family |
| same-family contrast | (added by the author) | **Qwen3.8-Flash-Next** (container `<container>`, <internal-host>, via <internal-proxy> gateway; thinking on): 183 cells sent, **179 valid**, 4 invalid (reasoning exhausted the 12,288-token retry budget), 5 not sent (window) | the 5 cells B-F CQB32 (~0.5M tokens) exceed its 262k window; the 4 invalid cells are not re-sent or imputed (plan 4.1) |
| luna full-rendering auxiliary | 48 cells | **dropped** | luna blocked |
| `majority-vote` audit | three family raters | GLM + gpt-oss + **S21 luna labels as a stand-in for the missing family** | no third family |

The Claude route can be completed without any change of plan once the author re-authenticates the account (an interactive login that I did not attempt): `python3 run_rater.py --run haiku --out raw/haiku.jsonl --token-budget 6000000 --confirm-addendum28-frozen --workers 3` followed by `python3 analyze_raters.py run --claude haiku`. With three families the status rule of the plan (3 families, lower bounds >= 0.495) can then be evaluated; with the present kappas it would still be "not supported".

## 3. Experiment 1 -- test-retest (GLM-4.7-Flash, S21 prompt, 182 cells, 32 clusters)

Labels: S after the verbatim-span check, R with the R>=1 floor when S=1 (raw versions in section 7). BCa 95% over CQ clusters, B = 10,000, seed 20260913. **Status: not supported** (at least one criterion fails on its point estimate in the pooled set or in a condition set).

| set | alpha on S [95%] | lower bound >= 0.80 | mean pairwise QWK on R [95%] | lower bound >= 0.70 | pi-hat range, pp | <= 5 pp |
|---|---|---|---|---|---|---|
| all 7 runs | 0.40 [0.31, 0.52] | no | 0.49 [0.40, 0.60] | no | 21.98 | no |
| (a) temperature 0, runs a1 and a2 | 0.91 [0.77, 0.98] | no | 0.92 [0.84, 0.97] | yes | 1.65 | yes |
| (b) temperature 0.7, runs b1-b3 | 0.21 [0.11, 0.34] | no | 0.36 [0.25, 0.48] | no | 21.98 | no |
| (c) wording: a1 and the two paraphrases c1, c2 | 0.60 [0.51, 0.72] | no | 0.68 [0.57, 0.78] | no | 6.04 | no |

Per run (S = S_final; pi-hat = share of cells with registered-judge J >= 2 and S = 0):

| run | S=1 share | mean R | pi-hat | verbatim spans among S_raw=1 |
|---|---|---|---|---|
| a1 | 18.7% | 1.24 | 58.8% | 34/63 (54%) |
| a2 | 20.3% | 1.19 | 57.1% | 37/62 (60%) |
| b1 | 31.3% | 2.22 | 49.5% | 57/119 (48%) |
| b2 | 46.2% | 2.46 | 38.5% | 84/144 (58%) |
| b3 | 14.8% | 1.40 | 60.4% | 27/51 (53%) |
| c1 | 24.7% | 1.35 | 52.7% | 45/79 (57%) |
| c2 | 18.7% | 1.55 | 57.7% | 34/60 (57%) |

Reference pi-hat on the same 182 cells: AH 7.7%, second rater 14.3%, S21 luna labels 38.5% (published 28.7% on 188 cells before the span check). Readings (all descriptive): (a) the two temperature-0 runs agree (alpha 0.91, QWK 0.92, pi-hat range 1.65 pp), but alpha's lower bound (0.77) is below 0.80 and the runs were 35 minutes apart on a quiet server, so this measures serving determinism only; (b) at temperature 0.7 the S = 1 share swings from 14.8% to 46.2% and mean R from 1.40 to 2.46; (c) the wording of the prompt moves the S = 1 share between 18.7% and 24.7%. GLM-4.7-Flash with thinking switched off is also far stricter than the humans: it marks 18.7% of cells supported against 73.4% (AH) and 67.0% (second rater), and only 54% of the spans it cites for S=1 are verbatim.

## 4. Experiment 2 -- cross-family raters (182 common cells)

Reference on these cells: AH vs second rater kappa 0.578 [0.235, 0.835], QWK 0.759 [0.612, 0.886], alpha 0.576 [0.219, 0.838] (188 cells: kappa 0.595 [0.268, 0.833]). Non-inferiority floor 0.595 - 0.10 = 0.495 on the BCa lower bound (fixed benchmark; the human-human interval is wide, so a paired difference against the human-human kappa on the same cells is also given). **Status: not supported**: all 5 required kappas have a point estimate below 0.495, and only 2 of the 3 families the claim is about were available.

Krippendorff alpha across the two family raters: 0.20 [0.03, 0.37].

| pair (S_final) | kappa [95%] | lower bound >= 0.495 | kappa minus human-human kappa [95%] | QWK on R_floor [95%] |
|---|---|---|---|---|
| GLM-4.7-Flash vs gpt-oss-20b (LLM-LLM) | 0.20 [0.04, 0.36] | no | -0.37 [-0.70, 0.00] | 0.53 [0.36, 0.69] |
| GLM-4.7-Flash vs AH | 0.00 [-0.08, 0.10] | no | -0.57 [-0.86, -0.21] | 0.10 [-0.03, 0.26] |
| GLM-4.7-Flash vs second rater | -0.06 [-0.18, 0.05] | no | -0.64 [-0.91, -0.30] | 0.07 [-0.05, 0.22] |
| gpt-oss-20b vs AH | 0.16 [0.06, 0.31] | no | -0.42 [-0.67, -0.11] | 0.27 [0.11, 0.43] |
| gpt-oss-20b vs second rater | 0.07 [-0.10, 0.22] | no | -0.51 [-0.72, -0.23] | 0.18 [0.05, 0.34] |

Sensitivity without the span check: kappa(GLM, gpt-oss) 0.46 [0.28, 0.63]; gpt-oss with AH 0.28 [0.13, 0.49], with the second rater 0.17 [-0.06, 0.40]; GLM with AH 0.06 [-0.07, 0.24], with the second rater 0.03 [-0.13, 0.24]. The span check lowers every kappa with a human and none of the conclusions changes.

**Where the two humans disagree on S** (31 of the 182 cells; the 32nd of the 188 is one of the six cells without a subgraph): AH = 1 and second rater = 0 in 22, the reverse in 9. Descriptive counts of which side each rater takes:

| rater | scored | same S as AH | same S as second rater | S=1 where AH=1, second=0 | S=1 where AH=0, second=1 |
|---|---|---|---|---|---|
| zhipu_glm | 31 | 15 | 16 | 6 of 22 | 0 of 9 |
| openai_open_gptoss | 31 | 18 | 13 | 11 of 22 | 2 of 9 |
| openai_luna_s21 | 31 | 17 | 14 | 12 of 22 | 4 of 9 |
| qwen_same_family | 31 | 14 | 17 | 6 of 22 | 1 of 9 |

No rater leans consistently to one human: the split mostly follows the raters' own low rate of S = 1 (they say S = 0 in most of these cells, which coincides with the second rater in the 22 cells of the first kind and with AH in the 9 of the second kind).

## 5. Same-family contrast (Qwen3.8-Flash-Next) and the S21 luna labels

Qwen is the extractor's family and is **not counted** among the cross-family raters in any rule. It labeled 179 of the 183 cells it was sent (its kappas with the humans are on those). On the 178 cells labeled by every rater: mean kappa with the two humans, Qwen 0.07 [-0.09, 0.23] against the cross-family raters 0.05 [-0.03, 0.15] (difference 0.03 [-0.13, 0.14]); mean kappa of Qwen with the cross-family raters 0.23 [0.11, 0.35] against kappa between them 0.21 [0.05, 0.37] (difference 0.02 [-0.16, 0.18]). **No detectable effect of family overlap** at this sample size; every difference interval contains 0, and all raters of every family sit between kappa -0.06 and 0.16 with the humans. Qwen differs from the cross-family raters in more than family (thinking on, size, NVFP4 weights), so one contrast rater cannot isolate family.

| pair | kappa(S) [95%] | minus human-human [95%] |
|---|---|---|
| Qwen vs GLM-4.7-Flash | 0.13 [-0.05, 0.34] | -0.45 [-0.78, -0.10] |
| Qwen vs gpt-oss-20b | 0.34 [0.17, 0.49] | -0.24 [-0.52, 0.08] |
| Qwen vs AH | 0.09 [-0.08, 0.24] | -0.49 [-0.80, -0.14] |
| Qwen vs second rater | 0.06 [-0.15, 0.24] | -0.52 [-0.82, -0.17] |
| luna (S21 labels) vs GLM-4.7-Flash | 0.34 [0.19, 0.50] | -0.23 [-0.52, 0.11] |
| luna (S21 labels) vs gpt-oss-20b | 0.47 [0.31, 0.61] | -0.11 [-0.42, 0.26] |
| luna (S21 labels) vs Qwen | 0.46 [0.23, 0.68] | -0.12 [-0.45, 0.23] |
| luna (S21 labels) vs AH | 0.13 [-0.05, 0.34] | -0.45 [-0.75, -0.11] |
| luna (S21 labels) vs second rater | 0.06 [-0.17, 0.28] | -0.51 [-0.78, -0.18] |

Qwen vs the humans on all 179 cells it scored: AH 0.08 [-0.09, 0.23], second rater 0.06 [-0.14, 0.24]. S21 luna labels (with the span check; published values without it: kappa 0.175 with AH, 0.145 with the second rater) on 188 cells: AH 0.13 [-0.03, 0.34], second rater 0.09 [-0.14, 0.31]. luna and gpt-oss share a vendor and have the highest LLM-LLM kappa (0.47 [0.31, 0.61]); that overlap is why luna is not an independent family next to gpt-oss.

## 6. Majority-vote label source (unchanged audit)

Raters zhipu_glm, openai_open_gptoss, openai_luna_s21 (the S21 luna labels stand in for the missing third family; the six cells without a subgraph carry the luna label only). S = 1 in 52 of 188 cells. `analyze_holdout.py` run unchanged (seed 20260913): **pi-hat = 45.7%** [33.9, 58.0] (86 events, 26 of 33 clusters; AH 7.4%, second rater 13.8%, S21 luna 28.7% over the same 188 cells). Gate record: G1 fail (upper bound 0.910), G4 fail (QWK 0.518), G5 fail (MAE 1.085), G2/G3/G6/G7/G8 not computable (no washout, controls, audit trail or spot-check for a label source that is not human). G1 fails here as it does on the AH labels (upper bound 0.282 there); G4 and G5, sealed on the AH labels until the washout, fail here. The labels are so conservative (S = 1 in 28% of cells) that pi-hat is high; this is a property of the LLM raters, not a finding about the judge.

## 7. Sensitivity, verbatim check, cost and time

Without the span check and with raw R, the stability picture is the same: alpha(all 7) 0.38 [0.28, 0.50], QWK 0.49 [0.40, 0.60], pi-hat range 35.7 pp; for the temperature-0 pair alpha 0.94 [0.85, 0.99]. The R floor never matters for the criteria (raw R gives the same QWK). Verbatim rates of cited spans for S_raw = 1 (all runs and raters): GLM 48-60%, gpt-oss 70%, Qwen 85%, S21 luna 80% (the recomputed check equals the runner's stored flag in every record).

| run file | valid | prompt tokens | completion tokens | wall s | first start (UTC) |
|---|---|---|---|---|---|
| a1 | 182 | 2,188,289 | 20,222 | 328 | 2026-10-17T17:10:28 |
| a2 | 182 | 2,188,289 | 21,149 | 155 | 2026-10-17T17:46:01 |
| b1 | 182 | 2,188,289 | 20,353 | 162 | 2026-10-17T17:48:36 |
| b2 | 182 | 2,188,289 | 18,637 | 156 | 2026-10-17T17:51:18 |
| b3 | 182 | 2,188,289 | 20,498 | 161 | 2026-10-17T17:53:54 |
| c1 | 182 | 2,195,751 | 21,402 | 155 | 2026-10-17T17:15:56 |
| c2 | 182 | 2,184,467 | 19,247 | 149 | 2026-10-17T17:18:32 |
| dry_qwen | 5 | 48,843 | 10,964 | 81 | 2026-10-17T09:39:21 |
| gptoss | 182 | 2,167,348 | 44,333 | 338 | 2026-10-17T17:10:28 |
| qwen | 179 | 2,744,491 | 717,083 | 1804 | 2026-10-17T09:44:41 |

Totals: 20,282,345 prompt tokens and 913,888 completion tokens (usage fields, failed attempts and the 5-cell dry-run included); 58 minutes of summed call time, analysis 25 s. No OpenAI call was made; the Qwen route used about 2.7M tokens of the 4M cap. shared-server calls ran at 3 workers per endpoint with the courtesy gate (it never had to wait: nobody else used the endpoints); the first Qwen call was at 09:44 UTC, the shared-server runs from 17:10 to 17:57 UTC (a2 started 35 minutes after a1), and the whole task took about 8 hours of wall time because shared-server calls had to wait for two other agents and the luna quota was exhausted.

## 8. Deviations from the plan, failures, and open points

* **Failures to meet the criteria (all reported above):** Experiment 1 pooled and sets (b), (c) fail on point estimates; set (a) meets the point criteria but its alpha lower bound (0.77) is below 0.80. Experiment 2: every required kappa is below 0.495.
* **Deviations after the freeze** (`deviations_after_freeze.md`; changed files: `run_rater.py` (opt-in courtesy gate, operational), `test_raters.py`, `analyze_raters.py` (two changes, diff in `analyze_raters.post_freeze.diff`: family-only primary block so that the 4 invalid Qwen cells do not shrink the required comparisons; absolute output path for the unchanged audit). No threshold, status rule, statistic definition, prompt, cell or request changed. The committed `analyze_raters.py` is `c8328bf`; the working-tree version that produced these numbers is uncommitted, as instructed.
* The Qwen run was started with the frozen runner before the gate was added; its 4 invalid cells are listed in `raw/qwen.jsonl` (B:CQB09, B:CQB12, D:CQB12, E:CQB09).
* GLM and gpt-oss had no live dry-run before the freeze (shared-server calls had to wait for the judge agent); none was needed in the end (0 invalid GLM replies, 3 gpt-oss retries, all valid).
* The trailer of the plan commit is the text the brief specified (`Claude Opus 5.5`); the commit was authored by Claude Sonnet 5.5, which the commit body states. Amend if the attribution should read differently.
* Paraphrase equivalence is by hand; the 182 cells are 32 clusters; the raters saw the subgraph while the humans saw the full rendering; GLM ran with thinking off and gpt-oss at low reasoning effort, Qwen with thinking on (the gateway ignored the switch). These choices are in the plan; they may explain part of the low kappa with humans and are not separable here.
* Security and hygiene: no secret was printed or stored; no host address or port is recorded in any file of this directory.

## 9. Suggested manuscript text (not applied; .tex files untouched)

**VII-D(e)** (LaTeX, numbers from `results.json`; the Supplementary Section number S28 is a placeholder):

```latex
\emph{(e) LLM raters without further human labeling} (post hoc, no new human label; Supplementary Section~S28). Two experiments asked whether LLM-rater labels behave like a measuring instrument. The rater prompt of Supplementary Section~S21 (the human raters' criteria) and a deterministic check that the cited span occurs verbatim in the rendering were applied to the $182$ primary cells that have a subgraph view. The S21 rater, \texttt{gpt-5.6-luna}, could not be run again (its quota was exhausted), so an open-weight rater, GLM-4.7-Flash, took its place. Two temperature-$0$ runs started $35$ minutes apart agreed closely (Krippendorff $\alpha=0.91$ $[0.77,0.98]$ on support, QWK $0.92$), which measures serving determinism only. Three runs at temperature $0.7$ did not ($\alpha=0.21$), and two reworded prompts moved the labels ($\alpha=0.60$ together with the original wording). The unsupported-credit estimate $\hat\pi$ ranged over $22$ percentage points across the seven runs ($38\%$ to $60\%$). Across families (GLM-4.7-Flash and gpt-oss-20b; no Anthropic model could be reached) the agreement on support was $\kappa=0.20$ $[0.04,0.36]$, and each rater's $\kappa$ with the AH labels and with the second rater lay between $-0.06$ and $0.16$, against $\kappa_{\mathrm{source}}=0.595$ between the two human raters (margin $0.10$, so a lower bound of at least $0.495$ was required; the human-human interval $[0.268,0.833]$ is wide). The LLM raters marked $19$ to $36\%$ of cells as supported against $67.0$ and $73.4\%$ for the two humans, and a rater from the extractor's own family (Qwen3.8-Flash-Next) did not differ detectably from the cross-family raters in $\kappa$ with the humans (difference $+0.03$ $[-0.13,0.14]$). Rerunning the audit unchanged on a majority vote of three LLM raters (GLM-4.7-Flash, gpt-oss-20b and the S21 labels) gives $\hat\pi=45.7\%$ $[33.9,58.0]$, and gate G1 still fails. None of this measures accuracy: the criteria for stability and for human-level agreement were not met, so LLM-rater labels remain a sensitivity analysis and not a substitute for human labels.
```

**Table 10 rows** (`Claim & Status & Where`):

```latex
LLM-rater labels are stable across runs and prompts & not supported (GLM-4.7-Flash rater; the S21 rater was not re-run) & \ref{subsec:labelfree} \\
Independent LLM-rater families agree at the human--human level & not supported (two families) & \ref{subsec:labelfree} \\
```

Status per the pre-specified criteria: row 1 **not supported** (pooled alpha 0.40, QWK 0.49, pi-hat range 22 pp; the criteria need alpha and QWK lower bounds >= 0.80 and 0.70 and a range <= 5 pp; the temperature-0 pair alone meets the point criteria but not the alpha lower bound); row 2 **not supported** (point kappas -0.06 to 0.20 against a floor of 0.495, with two instead of three families). Neither "supported" nor "unresolved" is available for a row whose criteria fail on the point estimate. A weaker, accurate wording for the manuscript is that the S21 labels are a single-run, single-prompt sensitivity analysis whose instability and low agreement with humans are now measured.

## 10. Files

`PLAN.md`, `analyze_raters.py` (committed, `c8328bf`); `results.json` (all numbers, sources with sha256, token totals, wall time), `REPORT_auto.md` (all tables), `REPORT.md`, `raw/*.jsonl` and `raw/*.meta.jsonl` (per-call records, one meta line per invocation), `labels_for_analysis_majority.csv`, `holdout_results_majority.json` (aggregate output of the unchanged audit), `deviations_after_freeze.md`, `analyze_raters.post_freeze.diff`, `dryrun_notes.md`, helper scripts (`build_inputs.py`, `prompts.py`, `run_rater.py`, `test_raters.py`, `make_plan.py`, `make_report.py`, `shared_server_chain.sh`). The audit's per-cell file was written outside the repository.
