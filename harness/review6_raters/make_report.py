#!/usr/bin/env python3
"""Compose REPORT.md and augment results.json for addendum 28 from results.json (numbers are read, not typed).
AI-generated; review before use."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
E1, E2 = R["experiment1"], R["experiment2"]
S1 = E1["primary"]["stats"]
P2 = E2["primary"]["stats"]
D2 = E2["with_descriptive_raters"]["stats"]


def c(d, nd=2):
    return f"{d['estimate']:.{nd}f} [{d['ci_lo']:.{nd}f}, {d['ci_hi']:.{nd}f}]"


def pp(d, nd=1):
    return f"{d['estimate']:.{nd}f} pp [{d['ci_lo']:.{nd}f}, {d['ci_hi']:.{nd}f}]"


def share(x):
    return f"{100 * x:.1f}%"


ver = R["verbatim_check"]
lean = E2["lean_on_AH_IND_disagreements_182"]
ma = E2["majority_vote_audit"]
cost = R["cost"]
tot = R["cost_totals"]
pr = E1["primary"]["per_run"]
refs = {k[len("pi_hat_ref:"):]: v for k, v in S1.items() if k.startswith("pi_hat_ref:")}
lun188 = E2["openai_luna_s21_all_scored_vs_humans"]["stats"]
qw = E2["qwen_same_family_all_scored_vs_humans"]
qws = qw["stats"]
sens = E1["sensitivity_S_raw_R_raw"]["stats"]
s2raw = E2["sensitivity_S_raw"]["stats"]
st1, st2 = E1["primary_status"], E2["status"]
g = ma["gates"]

rows1 = []
for name, label in (("all7", "all 7 runs"), ("a_temp0", "(a) temperature 0, runs a1 and a2"), ("b_temp07", "(b) temperature 0.7, runs b1-b3"),
                    ("c_paraphrase", "(c) wording: a1 and the two paraphrases c1, c2")):
    d = st1["sets"][name]
    rows1.append(f"| {label} | {c(S1['alpha:' + name])} | {'yes' if d['alpha']['bound_ok'] else 'no'} | {c(S1['qwk_mean_pairwise:' + name])} | "
                 f"{'yes' if d['qwk']['bound_ok'] else 'no'} | {S1['pi_range_pp:' + name]['estimate']:.2f} | {'yes' if d['pi_range_pp']['point_ok'] else 'no'} |")
runs_tbl = "\n".join(f"| {r} | {share(pr[r]['S1_share'])} | {pr[r]['R_mean']:.2f} | {share(pr[r]['pi_hat'])} | {ver[r]['verbatim']}/{ver[r]['S_raw_1']} ({100 * ver[r]['verbatim_rate']:.0f}%) |"
                     for r in ("a1", "a2", "b1", "b2", "b3", "c1", "c2"))


def prow(label, key):
    k = P2[f"kappa:{key}"]
    d = P2[f"kappa_minus_HH:{key}"]
    q = P2[f"qwk:{key}"]
    ni = "yes" if k["ci_lo"] >= 0.495 else "no"
    return f"| {label} | {c(k)} | {ni} | {c(d)} | {c(q)} |"


pair_tbl = "\n".join([prow("GLM-4.7-Flash vs gpt-oss-20b (LLM-LLM)", "zhipu_glm-openai_open_gptoss"), prow("GLM-4.7-Flash vs AH", "zhipu_glm-AH"),
                      prow("GLM-4.7-Flash vs second rater", "zhipu_glm-IND"), prow("gpt-oss-20b vs AH", "openai_open_gptoss-AH"),
                      prow("gpt-oss-20b vs second rater", "openai_open_gptoss-IND")])


def drow(label, key):
    k = D2[f"kappa:{key}"]
    d = D2[f"kappa_minus_HH:{key}"]
    return f"| {label} | {c(k)} | {c(d)} |"


desc_tbl = "\n".join([drow("Qwen vs GLM-4.7-Flash", "zhipu_glm-qwen_same_family"), drow("Qwen vs gpt-oss-20b", "openai_open_gptoss-qwen_same_family"),
                      drow("Qwen vs AH", "qwen_same_family-AH"), drow("Qwen vs second rater", "qwen_same_family-IND"),
                      drow("luna (S21 labels) vs GLM-4.7-Flash", "zhipu_glm-openai_luna_s21"),
                      drow("luna (S21 labels) vs gpt-oss-20b", "openai_open_gptoss-openai_luna_s21"),
                      drow("luna (S21 labels) vs Qwen", "openai_luna_s21-qwen_same_family"),
                      drow("luna (S21 labels) vs AH", "openai_luna_s21-AH"), drow("luna (S21 labels) vs second rater", "openai_luna_s21-IND")])
lr = lean["raters"]
lean_tbl = "\n".join(f"| {n} | {v['n_scored']} | {v['agrees_with_AH']} | {v['agrees_with_IND']} | {v['S1_when_AH1_IND0']} of {lean['AH1_IND0']} | {v['S1_when_AH0_IND1']} of {lean['AH0_IND1']} |"
                     for n, v in lr.items())
cost_tbl = "\n".join(f"| {k} | {v['calls_valid']} | {v['prompt_tokens']:,} | {v['completion_tokens']:,} | {v['wall_s']:.0f} | {(v['first_start_utc'] or '')[:19]} |"
                     for k, v in cost.items())

# ----------------------------------------------------------------------------------------------------------- suggested text
kap5 = [P2[k]["estimate"] for k in ("kappa:zhipu_glm-AH", "kappa:zhipu_glm-IND", "kappa:openai_open_gptoss-AH", "kappa:openai_open_gptoss-IND")]
sshare = {n: ver[r]["S_final_1"] / ver[r]["valid_cells"] for n, r in (("glm", "a1"), ("gptoss", "gptoss"), ("qwen", "qwen"), ("luna", "luna_s21"))}
lo_share, hi_share = 100 * min(sshare.values()), 100 * max(sshare.values())
pis = [v["pi_hat"] for v in pr.values()]
VIID = (
    rf"\emph{{(e) LLM raters without further human labeling}} (post hoc, no new human label; Supplementary Section~S28). "
    rf"Two experiments asked whether LLM-rater labels behave like a measuring instrument. "
    rf"The rater prompt of Supplementary Section~S21 (the human raters' criteria) and a deterministic check that the cited span occurs verbatim in the rendering "
    rf"were applied to the $182$ primary cells that have a subgraph view. "
    rf"The S21 rater, \texttt{{gpt-5.6-luna}}, could not be run again (its quota was exhausted), so an open-weight rater, GLM-4.7-Flash, took its place. "
    rf"Two temperature-$0$ runs started $35$ minutes apart agreed closely (Krippendorff $\alpha={S1['alpha:a_temp0']['estimate']:.2f}$ "
    rf"$[{S1['alpha:a_temp0']['ci_lo']:.2f},{S1['alpha:a_temp0']['ci_hi']:.2f}]$ on support, QWK ${S1['qwk_mean_pairwise:a_temp0']['estimate']:.2f}$), "
    rf"which measures serving determinism only. "
    rf"Three runs at temperature $0.7$ did not ($\alpha={S1['alpha:b_temp07']['estimate']:.2f}$), and two reworded prompts moved the labels "
    rf"($\alpha={S1['alpha:c_paraphrase']['estimate']:.2f}$ together with the original wording). "
    rf"The unsupported-credit estimate $\hat\pi$ ranged over ${S1['pi_range_pp:all7']['estimate']:.0f}$ percentage points across the seven runs "
    rf"(${100 * min(pis):.0f}\%$ to ${100 * max(pis):.0f}\%$). "
    rf"Across families (GLM-4.7-Flash and gpt-oss-20b; no Anthropic model could be reached) the agreement on support was "
    rf"$\kappa={P2['kappa:zhipu_glm-openai_open_gptoss']['estimate']:.2f}$ $[{P2['kappa:zhipu_glm-openai_open_gptoss']['ci_lo']:.2f},{P2['kappa:zhipu_glm-openai_open_gptoss']['ci_hi']:.2f}]$, "
    rf"and each rater's $\kappa$ with the AH labels and with the second rater lay between ${min(kap5):.2f}$ and ${max(kap5):.2f}$, "
    rf"against $\kappa_{{\mathrm{{source}}}}=0.595$ between the two human raters (margin $0.10$, so a lower bound of at least $0.495$ was required; the human-human interval $[0.268,0.833]$ is wide). "
    rf"The LLM raters marked ${lo_share:.0f}$ to ${hi_share:.0f}\%$ of cells as supported against $67.0$ and $73.4\%$ for the two humans, "
    rf"and a rater from the extractor's own family (Qwen3.8-Flash-Next) did not differ detectably from the cross-family raters in $\kappa$ with the humans "
    rf"(difference ${D2['contrast:qwen_minus_families_with_humans']['estimate']:+.2f}$ $[{D2['contrast:qwen_minus_families_with_humans']['ci_lo']:.2f},{D2['contrast:qwen_minus_families_with_humans']['ci_hi']:.2f}]$). "
    rf"Rerunning the audit unchanged on a majority vote of three LLM raters (GLM-4.7-Flash, gpt-oss-20b and the S21 labels) gives "
    rf"$\hat\pi={100 * ma['pi_hat']['pi_hat']:.1f}\%$ $[{100 * ma['pi_hat']['ci_lo']:.1f},{100 * ma['pi_hat']['ci_hi']:.1f}]$, and gate G1 still fails. "
    rf"None of this measures accuracy: the criteria for stability and for human-level agreement were not met, "
    rf"so LLM-rater labels remain a sensitivity analysis and not a substitute for human labels."
)
ROW1 = ("LLM-rater labels are stable across runs and prompts", f"{st1['status']} (GLM-4.7-Flash rater; the S21 rater was not re-run)", r"\ref{subsec:labelfree}")
ROW2 = ("Independent LLM-rater families agree at the human--human level", f"{st2['status']} (two families)", r"\ref{subsec:labelfree}")

report = f"""# Addendum 28 -- LLM-rater stability and cross-family agreement: REPORT

AI-generated report; post hoc with respect to the original plan, pre-specified with respect to these runs (`PLAN.md`, commit `c8328bf`, written before the first scoring call). Code, commands and figures here are AI-generated and must be reviewed and tested by a person before reuse; nothing in this directory is to be applied to a production system without that review. Per-cell human labels are not reproduced anywhere in this directory (aggregates only).

**Claim ceiling kept:** the experiments ask whether LLM-rater labels are stable, whether independent families agree, and whether agreement is comparable to human-human. They do not measure accuracy and nothing below should be read as "LLMs are more accurate".

## 1. Result in one paragraph

Both candidate Table 10 rows come out **not supported**. A GLM-4.7-Flash rater using the S21 prompt reproduces its own labels when the request is repeated at temperature 0 (alpha {c(S1['alpha:a_temp0'])}), but not at temperature 0.7 (alpha {c(S1['alpha:b_temp07'])}) and not under two reworded prompts (alpha {c(S1['alpha:c_paraphrase'])}); pooled, alpha is {c(S1['alpha:all7'])}, QWK {c(S1['qwk_mean_pairwise:all7'])} and the range of the unsupported-credit estimate pi-hat is {S1['pi_range_pp:all7']['estimate']:.1f} pp (criteria: alpha lower bound >= 0.80, QWK lower bound >= 0.70, range <= 5 pp). Two independent families (Zhipu, OpenAI-open) agree with each other at kappa {c(P2['kappa:zhipu_glm-openai_open_gptoss'])} and with the humans at kappa {min(P2[k]['estimate'] for k in ('kappa:zhipu_glm-AH','kappa:zhipu_glm-IND','kappa:openai_open_gptoss-AH','kappa:openai_open_gptoss-IND')):.2f} to {max(P2[k]['estimate'] for k in ('kappa:zhipu_glm-AH','kappa:zhipu_glm-IND','kappa:openai_open_gptoss-AH','kappa:openai_open_gptoss-IND')):.2f}, far below the human-human 0.595 (non-inferiority floor 0.495; 5 of 5 required kappas fail on the point estimate). A Qwen rater of the extractor's family does not differ detectably from them. The third family (Anthropic) could not be reached, and the original test-retest of the S21 rater (luna) could not run, because the luna quota was exhausted (HTTP 402).

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

Labels: S after the verbatim-span check, R with the R>=1 floor when S=1 (raw versions in section 7). BCa 95% over CQ clusters, B = 10,000, seed 20260913. **Status: {st1['status']}** ({st1['reason']}).

| set | alpha on S [95%] | lower bound >= 0.80 | mean pairwise QWK on R [95%] | lower bound >= 0.70 | pi-hat range, pp | <= 5 pp |
|---|---|---|---|---|---|---|
{chr(10).join(rows1)}

Per run (S = S_final; pi-hat = share of cells with registered-judge J >= 2 and S = 0):

| run | S=1 share | mean R | pi-hat | verbatim spans among S_raw=1 |
|---|---|---|---|---|
{runs_tbl}

Reference pi-hat on the same 182 cells: AH {share(refs['AH']['estimate'])}, second rater {share(refs['IND']['estimate'])}, S21 luna labels {share(refs['luna_s21']['estimate'])} (published 28.7% on 188 cells before the span check). Readings (all descriptive): (a) the two temperature-0 runs agree (alpha {S1['alpha:a_temp0']['estimate']:.2f}, QWK {S1['qwk_mean_pairwise:a_temp0']['estimate']:.2f}, pi-hat range {S1['pi_range_pp:a_temp0']['estimate']:.2f} pp), but alpha's lower bound ({S1['alpha:a_temp0']['ci_lo']:.2f}) is below 0.80 and the runs were 35 minutes apart on a quiet server, so this measures serving determinism only; (b) at temperature 0.7 the S = 1 share swings from {share(pr['b3']['S1_share'])} to {share(pr['b2']['S1_share'])} and mean R from {pr['b3']['R_mean']:.2f} to {pr['b2']['R_mean']:.2f}; (c) the wording of the prompt moves the S = 1 share between {share(pr['a1']['S1_share'])} and {share(pr['c1']['S1_share'])}. GLM-4.7-Flash with thinking switched off is also far stricter than the humans: it marks {share(pr['a1']['S1_share'])} of cells supported against 73.4% (AH) and 67.0% (second rater), and only {100 * ver['a1']['verbatim_rate']:.0f}% of the spans it cites for S=1 are verbatim.

## 4. Experiment 2 -- cross-family raters (182 common cells)

Reference on these cells: AH vs second rater kappa {c(P2['kappa:AH-IND'], 3)}, QWK {c(P2['qwk:AH-IND'], 3)}, alpha {c(P2['alpha:AH-IND'], 3)} (188 cells: kappa 0.595 [0.268, 0.833]). Non-inferiority floor 0.595 - 0.10 = 0.495 on the BCa lower bound (fixed benchmark; the human-human interval is wide, so a paired difference against the human-human kappa on the same cells is also given). **Status: {st2['status']}**: all {len(st2['rows'])} required kappas have a point estimate below 0.495, and only {st2['n_families']} of the 3 families the claim is about were available.

Krippendorff alpha across the two family raters: {c(P2['alpha:families'])}.

| pair (S_final) | kappa [95%] | lower bound >= 0.495 | kappa minus human-human kappa [95%] | QWK on R_floor [95%] |
|---|---|---|---|---|
{pair_tbl}

Sensitivity without the span check: kappa(GLM, gpt-oss) {c(s2raw['kappa:zhipu_glm-openai_open_gptoss'])}; gpt-oss with AH {c(s2raw['kappa:openai_open_gptoss-AH'])}, with the second rater {c(s2raw['kappa:openai_open_gptoss-IND'])}; GLM with AH {c(s2raw['kappa:zhipu_glm-AH'])}, with the second rater {c(s2raw['kappa:zhipu_glm-IND'])}. The span check lowers every kappa with a human and none of the conclusions changes.

**Where the two humans disagree on S** ({lean['n_disagree_cells_in_set']} of the 182 cells; the 32nd of the 188 is one of the six cells without a subgraph): AH = 1 and second rater = 0 in {lean['AH1_IND0']}, the reverse in {lean['AH0_IND1']}. Descriptive counts of which side each rater takes:

| rater | scored | same S as AH | same S as second rater | S=1 where AH=1, second=0 | S=1 where AH=0, second=1 |
|---|---|---|---|---|---|
{lean_tbl}

No rater leans consistently to one human: the split mostly follows the raters' own low rate of S = 1 (they say S = 0 in most of these cells, which coincides with the second rater in the {lean['AH1_IND0']} cells of the first kind and with AH in the {lean['AH0_IND1']} of the second kind).

## 5. Same-family contrast (Qwen3.8-Flash-Next) and the S21 luna labels

Qwen is the extractor's family and is **not counted** among the cross-family raters in any rule. It labeled {qw['n_cells']} of the 183 cells it was sent (its kappas with the humans are on those). On the {E2['with_descriptive_raters']['n_cells']} cells labeled by every rater: mean kappa with the two humans, Qwen {c(D2['contrast:mean_kappa_qwen_with_humans'])} against the cross-family raters {c(D2['contrast:mean_kappa_families_with_humans'])} (difference {c(D2['contrast:qwen_minus_families_with_humans'])}); mean kappa of Qwen with the cross-family raters {c(D2['contrast:mean_kappa_qwen_with_families'])} against kappa between them {c(D2['contrast:mean_kappa_between_families'])} (difference {c(D2['contrast:qwen_with_families_minus_between_families'])}). **No detectable effect of family overlap** at this sample size; every difference interval contains 0, and all raters of every family sit between kappa -0.06 and 0.16 with the humans. Qwen differs from the cross-family raters in more than family (thinking on, size, NVFP4 weights), so one contrast rater cannot isolate family.

| pair | kappa(S) [95%] | minus human-human [95%] |
|---|---|---|
{desc_tbl}

Qwen vs the humans on all {qw['n_cells']} cells it scored: AH {c(qws['kappa:qwen_same_family-AH'])}, second rater {c(qws['kappa:qwen_same_family-IND'])}. S21 luna labels (with the span check; published values without it: kappa 0.175 with AH, 0.145 with the second rater) on 188 cells: AH {c(lun188['kappa:openai_luna_s21-AH'])}, second rater {c(lun188['kappa:openai_luna_s21-IND'])}. luna and gpt-oss share a vendor and have the highest LLM-LLM kappa ({c(D2['kappa:openai_open_gptoss-openai_luna_s21'])}); that overlap is why luna is not an independent family next to gpt-oss.

## 6. Majority-vote label source (unchanged audit)

Raters {', '.join(ma['majority_raters'])} (the S21 luna labels stand in for the missing third family; the six cells without a subgraph carry the luna label only). S = 1 in {ma['S1']} of {ma['n_cells']} cells. `analyze_holdout.py` run unchanged (seed 20260913): **pi-hat = {100 * ma['pi_hat']['pi_hat']:.1f}%** [{100 * ma['pi_hat']['ci_lo']:.1f}, {100 * ma['pi_hat']['ci_hi']:.1f}] ({ma['pi_hat']['events']} events, {ma['pi_hat']['clusters_with_event']} of {ma['pi_hat']['n_clusters']} clusters; AH 7.4%, second rater 13.8%, S21 luna 28.7% over the same 188 cells). Gate record: G1 {g['G1_silent_over_credit']['status']} (upper bound {g['G1_silent_over_credit']['value']:.3f}), G4 {g['G4_human_judge_qwk']['status']} (QWK {g['G4_human_judge_qwk']['value']:.3f}), G5 {g['G5_mae_judge_human']['status']} (MAE {g['G5_mae_judge_human']['value']:.3f}), G2/G3/G6/G7/G8 not computable (no washout, controls, audit trail or spot-check for a label source that is not human). G1 fails here as it does on the AH labels (upper bound 0.282 there); G4 and G5, sealed on the AH labels until the washout, fail here. The labels are so conservative (S = 1 in {100 * ma['S1'] / ma['n_cells']:.0f}% of cells) that pi-hat is high; this is a property of the LLM raters, not a finding about the judge.

## 7. Sensitivity, verbatim check, cost and time

Without the span check and with raw R, the stability picture is the same: alpha(all 7) {c(sens['alpha:all7'])}, QWK {c(sens['qwk_mean_pairwise:all7'])}, pi-hat range {sens['pi_range_pp:all7']['estimate']:.1f} pp; for the temperature-0 pair alpha {c(sens['alpha:a_temp0'])}. The R floor never matters for the criteria (raw R gives the same QWK). Verbatim rates of cited spans for S_raw = 1 (all runs and raters): GLM {min(100 * ver[r]['verbatim_rate'] for r in ('a1','a2','b1','b2','b3','c1','c2')):.0f}-{max(100 * ver[r]['verbatim_rate'] for r in ('a1','a2','b1','b2','b3','c1','c2')):.0f}%, gpt-oss {100 * ver['gptoss']['verbatim_rate']:.0f}%, Qwen {100 * ver['qwen']['verbatim_rate']:.0f}%, S21 luna {100 * ver['luna_s21']['verbatim_rate']:.0f}% (the recomputed check equals the runner's stored flag in every record).

| run file | valid | prompt tokens | completion tokens | wall s | first start (UTC) |
|---|---|---|---|---|---|
{cost_tbl}

Totals: {tot['prompt_tokens']:,} prompt tokens and {tot['completion_tokens']:,} completion tokens (usage fields, failed attempts and the 5-cell dry-run included); {tot['wall_s_sum_of_invocations'] / 60:.0f} minutes of summed call time, analysis {R['analysis_wall_s']:.0f} s. No OpenAI call was made; the Qwen route used about {cost['qwen']['prompt_tokens'] / 1e6:.1f}M tokens of the 4M cap. shared-server calls ran at 3 workers per endpoint with the courtesy gate (it never had to wait: nobody else used the endpoints); the first Qwen call was at 09:44 UTC, the shared-server runs from 17:10 to 17:57 UTC (a2 started 35 minutes after a1), and the whole task took about 8 hours of wall time because shared-server calls had to wait for two other agents and the luna quota was exhausted.

## 8. Deviations from the plan, failures, and open points

* **Failures to meet the criteria (all reported above):** Experiment 1 pooled and sets (b), (c) fail on point estimates; set (a) meets the point criteria but its alpha lower bound ({S1['alpha:a_temp0']['ci_lo']:.2f}) is below 0.80. Experiment 2: every required kappa is below 0.495.
* **Deviations after the freeze** (`deviations_after_freeze.md`; changed files: `run_rater.py` (opt-in courtesy gate, operational), `test_raters.py`, `analyze_raters.py` (two changes, diff in `analyze_raters.post_freeze.diff`: family-only primary block so that the 4 invalid Qwen cells do not shrink the required comparisons; absolute output path for the unchanged audit). No threshold, status rule, statistic definition, prompt, cell or request changed. The committed `analyze_raters.py` is `c8328bf`; the working-tree version that produced these numbers is uncommitted, as instructed.
* The Qwen run was started with the frozen runner before the gate was added; its 4 invalid cells are listed in `raw/qwen.jsonl` (B:CQB09, B:CQB12, D:CQB12, E:CQB09).
* GLM and gpt-oss had no live dry-run before the freeze (shared-server calls had to wait for the judge agent); none was needed in the end (0 invalid GLM replies, 3 gpt-oss retries, all valid).
* The trailer of the plan commit is the text the brief specified (`Claude Opus 5.5`); the commit was authored by Claude Sonnet 5.5, which the commit body states. Amend if the attribution should read differently.
* Paraphrase equivalence is by hand; the 182 cells are 32 clusters; the raters saw the subgraph while the humans saw the full rendering; GLM ran with thinking off and gpt-oss at low reasoning effort, Qwen with thinking on (the gateway ignored the switch). These choices are in the plan; they may explain part of the low kappa with humans and are not separable here.
* Security and hygiene: no secret was printed or stored; no host address or port is recorded in any file of this directory.

## 9. Suggested manuscript text (not applied; .tex files untouched)

**VII-D(e)** (LaTeX, numbers from `results.json`; the Supplementary Section number S28 is a placeholder):

```latex
{VIID}
```

**Table 10 rows** (`Claim & Status & Where`):

```latex
{ROW1[0]} & {ROW1[1]} & {ROW1[2]} \\\\
{ROW2[0]} & {ROW2[1]} & {ROW2[2]} \\\\
```

Status per the pre-specified criteria: row 1 **{st1['status']}** (pooled alpha {S1['alpha:all7']['estimate']:.2f}, QWK {S1['qwk_mean_pairwise:all7']['estimate']:.2f}, pi-hat range {S1['pi_range_pp:all7']['estimate']:.0f} pp; the criteria need alpha and QWK lower bounds >= 0.80 and 0.70 and a range <= 5 pp; the temperature-0 pair alone meets the point criteria but not the alpha lower bound); row 2 **{st2['status']}** (point kappas {min(P2[k]['estimate'] for k in ('kappa:zhipu_glm-openai_open_gptoss','kappa:zhipu_glm-AH','kappa:zhipu_glm-IND','kappa:openai_open_gptoss-AH','kappa:openai_open_gptoss-IND')):.2f} to {max(P2[k]['estimate'] for k in ('kappa:zhipu_glm-openai_open_gptoss','kappa:zhipu_glm-AH','kappa:zhipu_glm-IND','kappa:openai_open_gptoss-AH','kappa:openai_open_gptoss-IND')):.2f} against a floor of 0.495, with two instead of three families). Neither "supported" nor "unresolved" is available for a row whose criteria fail on the point estimate. A weaker, accurate wording for the manuscript is that the S21 labels are a single-run, single-prompt sensitivity analysis whose instability and low agreement with humans are now measured.

## 10. Files

`PLAN.md`, `analyze_raters.py` (committed, `c8328bf`); `results.json` (all numbers, sources with sha256, token totals, wall time), `REPORT_auto.md` (all tables), `REPORT.md`, `raw/*.jsonl` and `raw/*.meta.jsonl` (per-call records, one meta line per invocation), `labels_for_analysis_majority.csv`, `holdout_results_majority.json` (aggregate output of the unchanged audit), `deviations_after_freeze.md`, `analyze_raters.post_freeze.diff`, `dryrun_notes.md`, helper scripts (`build_inputs.py`, `prompts.py`, `run_rater.py`, `test_raters.py`, `make_plan.py`, `make_report.py`, `shared_server_chain.sh`). The audit's per-cell file was written outside the repository.
"""
(HERE / "REPORT.md").write_text(report, encoding="utf-8")

# augment results.json with the report-level facts (numbers copied, not recomputed)
R["report"] = {
    "statuses": {"row1_llm_rater_labels_stable_across_runs_and_prompts": st1["status"],
                 "row2_independent_llm_rater_families_agree_at_human_human_level": st2["status"]},
    "plan_commit": "c8328bf",
    "amendments": ["luna (<internal-proxy> HTTP 402): Experiment 1 rater = GLM-4.7-Flash, S21 luna labels = separate label source, no luna call",
                   "Anthropic <internal-proxy> route needs re-authentication: no Claude run; Experiment 2 has two families",
                   "same-family contrast rater Qwen3.8-Flash-Next added (183 cells sent, 179 valid)",
                   "luna full-rendering auxiliary dropped"],
    "deviations_after_freeze": "deviations_after_freeze.md",
    "tokens_total": R["cost_totals"],
    "task_timeline_utc": {"first_live_call_qwen": "2026-10-17T09:44:41", "shared_server_runs": "2026-10-17T17:10:28 to 17:56:35",
                          "analysis_final": R["created_utc"]},
    "suggested_text": {"VII_D_e_latex": VIID, "table10_rows": [list(ROW1), list(ROW2)]},
}
(HERE / "results.json").write_text(json.dumps(R, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
print("REPORT.md", len(report), "chars")
