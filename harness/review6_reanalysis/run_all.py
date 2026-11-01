#!/usr/bin/env python3
"""Run R1-R9 in order, merge parts/*.json into results.json, and write REPORT.md.

    python3 run_all.py            # re-run everything (about 2 minutes), then assemble
    python3 run_all.py --assemble # assemble from the existing parts/ only

POST HOC / EXPLORATORY.  No LLM call, no new label, no sealed file.  Seed 20260913, B = 10,000, question-clustered
BCa (the analyzer's own interval code).  REVIEW BEFORE USE: this is analysis code written for a reviewer response; it
was checked against the analyzer's recorded numbers (selfcheck.py) and has not been independently audited.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
STEPS = ["selfcheck.py", "provenance.py", "r1_over_under.py", "r2_symmetric.py", "r3_fullbank.py",
         "r4_same_question_set.py", "r5_human_human.py", "r6_panel.py", "r7_gate_mc.py", "r8_mde.py", "r9_loco.py", "crosscheck_with_analyzer.py"]

if "--assemble" not in sys.argv:
    (HERE / "parts").mkdir(exist_ok=True)
    for s in STEPS:
        print("running", s, flush=True)
        r = subprocess.run([sys.executable, str(HERE / s)], capture_output=True, text=True, cwd=HERE)
        (HERE / "parts" / (s.replace(".py", "") + ".log")).write_text(r.stdout + r.stderr)
        if r.returncode != 0:
            print(r.stdout[-2000:], r.stderr[-2000:])
            raise SystemExit(f"{s} failed")

P = {k: json.load(open(HERE / "parts" / f"{k}.json")) for k in
     ("r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "provenance")}
SELF = json.load(open(HERE / "selfcheck.json"))
XC = json.load(open(HERE / "crosscheck.json"))
results = {"status": "POST HOC / EXPLORATORY; no LLM call, no new label; no sealed file opened",
           "seed": 20260913, "B": 10000, "interval": "question(CQ)-clustered BCa 95% (analyzer code), unless stated",
           "selfcheck": {"n_checks": len(SELF["checks"]), "n_fail": SELF["n_fail"]},
           "provenance": P["provenance"], "R1": P["r1"], "R2": P["r2"], "R3": P["r3"], "R4": P["r4"], "R5": P["r5"],
           "R6": P["r6"], "R7": P["r7"], "R8": P["r8"], "R9": P["r9"]}


def e(r, nd=3, pct=False):
    if pct:
        return f"{r['est']*100:.1f}% [{r['lo']*100:.1f}, {r['hi']*100:.1f}]"
    return f"{r['est']:.{nd}f} [{r['lo']:.{nd}f}, {r['hi']:.{nd}f}]"


def p3(x):
    return f"{x:.3f}"


def pp_(r):
    return f"{r['est']*100:+.1f} pp [{r['lo']*100:+.1f}, {r['hi']*100:+.1f}]"


r1, r2, r3, r4, r5, r6, r7, r8, r9 = (P[k] for k in ("r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9"))
AH, S2 = r1["AH"]["overall"], r1["second_rater"]["overall"]
ab = lambda src, est: r2[src]["contrast_A_to_B_23_questions"][est]
EST = ["J", "L1* (withdraw-only)", "L_flip (two-sided support)", "L_R (rater score)"]

# ---------------------------------------------------------------- summary rows (every headline number)
rows = []


def row(i, q, v, interp, claim):
    rows.append((i, q, v, interp, claim))


b = AH["binary_support"]
row("R1", "Over-credit (J>=2, S=0) vs under-credit (J<=1, S=1), AH, 188 cells",
    f"{b['n_over_J_ge2_S0']} ({e(b['rate_over'], pct=True)}) vs {b['n_under_J_le1_S1']} ({e(b['rate_under'], pct=True)}); "
    f"net over-under {pp_(b['net_rate_over_minus_under'])}; exact sign p {b['exact_sign_p_cell_level_two_sided']:.3f} (cell), "
    f"{b['cluster_level_sign_test']['questions_net_over']} vs {b['cluster_level_sign_test']['questions_net_under']} questions p {b['cluster_level_sign_test']['p_two_sided']:.3f}",
    "Disagreement is two-sided and slightly under-credit-dominated; the judge is not net generous.",
    "WEAKENS the premise that only over-credit needs correcting (withdraw-only L1*, main L432/L466); pi-hat value and its 'lower bound' reading (L517) UNCHANGED")
b2 = S2["binary_support"]
row("R1", "Same, second rater",
    f"{b2['n_over_J_ge2_S0']} ({e(b2['rate_over'], pct=True)}) vs {b2['n_under_J_le1_S1']} ({e(b2['rate_under'], pct=True)}); net {pp_(b2['net_rate_over_minus_under'])}; sign p {b2['exact_sign_p_cell_level_two_sided']:.3f}",
    "Sign of the net flips with the label source; neither net excludes 0.", "QUALIFIES the over-credit framing; SUPPORTS 'estimate is label-source sensitive'")
row("R1", "Mean J vs mean R (AH); J-R",
    f"J {e(AH['ordinal']['mean_J'])}; R {e(AH['ordinal']['mean_R'])}; J-R {e(AH['ordinal']['mean_J_minus_R'])}; ordinal over/under/equal "
    f"{AH['ordinal']['n_over_J_gt_R']}/{AH['ordinal']['n_under_J_lt_R']}/{AH['ordinal']['n_equal']}; second rater J-R {e(S2['ordinal']['mean_J_minus_R'])}",
    "On the 0-3 scale the judge is no more generous than either rater (stingier than the second rater).",
    "QUALIFIES 'hidden over-credit' as the judge's dominant error; the unsupported-credit rates are UNCHANGED")
va = r1["AH"]["by_variant"]["A"]
row("R1", "Variant A (23 cells): J-R; over/under",
    f"{e(va['ordinal']['mean_J_minus_R'])}; {va['binary_support']['n_over_J_ge2_S0']} vs {va['binary_support']['n_under_J_le1_S1']}; B-F J-R within +-0.27 (CIs contain 0)",
    "Judge under-credit sits in the text-chunk variant A, the baseline of the A->B contrast.",
    "WEAKENS the A->B reading as a graph effect (see R2)")
row("R1", "Under-credit split J=0 / J=1 (AH)",
    f"{b['n_under_J0_S1']} / {b['n_under_J1_S1']}; mean(J-L1*) withdrawn per cell {e(P['r1']['withdrawn_mass_J_minus_L1star']['AH'])} (second rater {e(P['r1']['withdrawn_mass_J_minus_L1star']['second_rater'])})",
    "17 of 20 under-credit cells are J=0 (judge cited no span); L1* can only remove, so it never repairs these.", "LEAVES UNCHANGED (descriptive)")
row("R2", "A->B J / L1* / L_flip / L_R (AH), n=23",
    "; ".join(f"{k.split(' ')[0]} {e(ab('AH', k))}" for k in EST),
    "Delta shrinks +0.565 -> +0.478 -> +0.174 -> -0.087 as correction becomes two-sided; sign reverses under the rater's own scores.",
    "SUPPORTS 'A->B unresolved'; WEAKENS positive A->B direction")
row("R2", "A->B same, second rater",
    "; ".join(f"{k.split(' ')[0]} {e(ab('second_rater', k))}" for k in EST[1:]), "Same ordering.", "SUPPORTS 'unresolved'; WEAKENS direction")
row("R2", "Exact sign-flip permutation p, A->B (AH): J / L1* / L_flip / L_R",
    " / ".join(f"{ab('AH', k)['signflip']['p_two_sided']:.3f}" for k in EST) + f"; second rater L1* {ab('second_rater', EST[1])['signflip']['p_two_sided']:.3f}",
    "No version reaches 0.05; judge-only J is 0.079 under the exact sign-flip test (bootstrap-free), against Wilcoxon 0.044 and a BCa lower limit one lattice step above 0.",
    "SUPPORTS 'unresolved'; qualifies the J descriptive 'clears zero' (exact p 0.079)")
rg = r2["rogan_gladen"]["AH"]["in_sample_all_188_cells"]
oc23 = r2["rogan_gladen"]["AH"]["operating_characteristics_on_23_shared_questions"]
row("R2", "Rogan-Gladen corrected support-share contrast B-A (23 q)",
    f"RG {e(rg['RG_corrected_contrast_support_share'])} vs raw J>=2 {e(rg['uncorrected_judge_contrast_Jge2_share'])} vs direct AH labels {e(rg['direct_label_contrast_support_share'])}; Se+Sp-1 {rg['Se_plus_Sp_minus_1']:.3f}",
    f"On the 23 shared questions the AH support share is {oc23['A']['share_S1']*100:.1f}% (A) and {oc23['B']['share_S1']*100:.1f}% (B), but J>=2 is {oc23['A']['share_Jge2']*100:.1f}% vs {oc23['B']['share_Jge2']*100:.1f}%: judge Se {oc23['A']['Se']:.2f}/Sp {oc23['A']['Sp']:.2f} on A vs Se {oc23['B']['Se']:.2f}/Sp {oc23['B']['Sp']:.2f} on B (counts Se {oc23['A']['TP']}/{oc23['A']['TP']+oc23['A']['FN']} vs {oc23['B']['TP']}/{oc23['B']['TP']+oc23['B']['FN']}; Sp {oc23['A']['TN']}/{oc23['A']['TN']+oc23['A']['FP']} vs {oc23['B']['TN']}/{oc23['B']['TN']+oc23['B']['FP']}, so small-n). The judge's operating point moves between A and B, so pooled Se/Sp cannot correct A->B.",
    "WEAKENS reading J's A->B as a graph effect; calls for per-variant calibration")
pp = r2["ppi_label_budget_scenario"]
row("R2", "PPI-style label saving for A->B", f"corr(dJ,dR) {pp['corr_dJ_dR']:.2f}; SD ratio PPI/labelled-only {pp['scenarios'][2]['sd_ratio_ppi_over_labelled_only']:.2f} (PPI++ {pp['scenarios'][2]['sd_ratio_ppi_pp_over_labelled_only']:.2f}) at m=12",
    "J is nearly uninformative about question-level A->B differences, so partial labelling would not cut cost.", "LEAVES UNCHANGED")
fb = r3["J"]["A_to_B"]
fbl = r3["L1star_AH"]["A_to_B"]
row("R3", "A->B full-bank (36 q, ineligible=0) vs eligible-only: J / L1* AH",
    f"J {e(fb['full_bank_36_ineligible_0'])} vs {e(fb['eligible_only_23_registered'])}; L1* {e(fbl['full_bank_36_ineligible_0'])} vs {e(fbl['eligible_only_23_registered'])}; second rater L1* {e(r3['L1star_second_rater']['A_to_B']['full_bank_36_ineligible_0'])}",
    "Full-bank CI excludes 0 only because A is set to 0 on its 13 ineligible questions (10 where B is eligible).",
    "QUALIFIES Supplementary S25 ('order unchanged'): a full-bank A->B CI excludes 0 only under ineligible=0; registered eligible-only UNCHANGED")
row("R3", "Same with ineligible=3 (matching upper bound)",
    f"J {e(fb['full_bank_36_ineligible_3_upper_bound'])}; L1* {e(fbl['full_bank_36_ineligible_3_upper_bound'])}",
    "Bracket across the two fills spans -0.11..+0.72 (L1*): the full-bank contrast is not identified.", "SUPPORTS 'unresolved' (conditional on fill rule)")
pj = r4["per_judge_question_set"]
row("R4", "A->B same questions: Gemini J / luna full / luna 60k / luna subgraph",
    "; ".join(f"{k.split(' (')[0]} {e(v)} (n={v['n_questions']})" for k, v in pj.items()),
    "Direction is judge/condition dependent (2 up, 2 down); luna full is ceilinged (19 ties of 23) and its 90% CI lies in +-0.30.",
    "WEAKENS judge-robustness of positive A->B; SUPPORTS 'procedure-sensitive measurand'")
o = r5["ordinal_0_3"]
row("R5", "Human-human (AH vs 2nd rater R), 188 cells",
    f"MAE {e(o['HH']['mae'])}; exact {e(o['HH']['exact'], pct=True)}; QWK {e(o['HH']['qwk'])}; support kappa {e(r5['binary_support']['bin_AH_2']['kappa'])}",
    "G5 bar (CI upper <=0.50) is reachable by a human pair (upper 0.447); G4 bar 0.60 is below the human-human QWK.",
    "SUPPORTS supplement A4 ('G5 can pass'); gate statuses UNCHANGED")
row("R5", "Judge-human, same cells (AH / 2nd rater)",
    f"MAE {o['JH_AH']['mae']['est']:.3f} / {o['JH_2']['mae']['est']:.3f}; exact {o['JH_AH']['exact']['est']*100:.1f}% / {o['JH_2']['exact']['est']*100:.1f}%; QWK {o['JH_AH']['qwk']['est']:.3f} / {o['JH_2']['qwk']['est']:.3f}; MAE gap vs HH {e(r5['paired_differences']['mae: judge-AH minus human-human'])}",
    "On the 0-3 scale the judge is clearly farther from a rater than raters are from each other (gap CI excludes 0).", "SUPPORTS G5 fail (judge-rater gap is real)")
bsp = r5["binary_support"]
row("R5", "Binary support call [J>=2] vs S: kappa / Gwet AC1 / PABAK (judge-AH)",
    f"{e(bsp['bin_J_AH']['kappa'])} / {e(bsp['bin_J_AH']['ac1'])} / {e(bsp['bin_J_AH']['pabak'])}; judge-2nd {bsp['bin_J_2']['kappa']['est']:.3f} / {bsp['bin_J_2']['ac1']['est']:.3f} / {bsp['bin_J_2']['pabak']['est']:.3f}; human-human {bsp['bin_AH_2']['kappa']['est']:.3f} / {bsp['bin_AH_2']['ac1']['est']:.3f} / {bsp['bin_AH_2']['pabak']['est']:.3f}",
    "AC1 (0.70) and PABAK (0.64) sit above kappa (0.55) at 70% prevalence; judge-human minus human-human kappa -0.04 [-0.36, +0.25]: indistinguishable.",
    "QUALIFIES judge-AH kappa 0.554: human-human kappa 0.595 is the same size; no gate status changes")
row("R6", "48-cell panel: A-B paired questions; pooled graph-A (unpaired, 28 clusters)",
    f"{r6['A_B_paired_questions']} paired A-B questions; A->{{C,E}} on 2; pooled graph-A: " + "; ".join(f"{k.split(' (')[0]} {e(v, 2)}" for k, v in r6['pooled_graph_minus_A_unpaired'].items()),
    "The frozen panel cannot estimate A->B (0 pairs); the three judges agree on direction (graph>A) but intervals span +-1.9.", "LEAVES UNCHANGED (non-estimable)")
g1 = r7["G1"]
row("R7", "G1 pass probability at n=33 (97.5% level; 95% level)",
    f"0.000 (0 events gives {g1['n33_level97.5']['cp_upper_at_zero_events']*100:.2f}%); 95%: {g1['plug_in_mc_AH']['mc_P_pass_level95']:.3f} at observed 4/33 event clusters (exact {g1['plug_in_mc_AH']['exact_P_zero_events_in_33_draws']:.3f}); n=36: P={g1['exact_pass_probability']['n36_level97.5']['p_0.01']:.2f} at 1% per-cluster event rate",
    "G1 was unpassable at the realised design by arithmetic, before any data.", "SUPPORTS 'design defect, not a judge finding'")
g5 = r7["G5"]["worlds"]
g4 = r7["G4"]["worlds"]
row("R7", "G5 pass probability vs true MAE", "; ".join(f"MAE {w['true_MAE']:.2f}: {w['P_pass']:.2f}" for w in g5),
    "At the observed truth (0.79) P(pass)=0; 80% power needs true MAE about 0.30 (near the human-human MAE 0.29).", "SUPPORTS G5 fail as informative; bar is demanding")
row("R7", "G4 P(falsified) vs true QWK", "; ".join(f"QWK {w['true_QWK']:.2f}: {w['P_falsified']:.2f}" for w in g4[:3]),
    "Even if the true QWK were the observed 0.50, G4 would falsify only about 1 time in 4 at n=33.", "QUALIFIES 'G4 not falsified on AH labels' (low-power test); status UNCHANGED")
g2 = r7["G2_analogue"]["worlds"]
row("R7", "G2 analogue (72 cells, lower CI >= 0.70) vs true QWK", "; ".join(f"{w['true_QWK']:.2f}: {w['P_pass']:.2f}" for w in g2[:5]),
    "Even at the human-human QWK (0.73) a same-size washout passes about 5% of the time; 80% needs true QWK about 0.89.", "SUPPORTS 'G2 was hard to pass'; no gate status changed")
g6 = r7["G6_A_to_B_resolved"]["worlds"]
row("R7", "P(A->B CI excludes 0) at n=23 vs true delta (L1*, sd 1.47)", "; ".join(f"{w['true_delta']:.2f}: {w['P_ci_excludes_0']:.2f}" for w in g6),
    "Power at the observed delta is about 1/3; BCa's false-resolution rate under delta=0 is about 6%; G6 pass probability is at most this.", "SUPPORTS 'A->B underpowered'")
g3 = r7["G3_judge_side_analogue"]
row("R7", "G3 judge-side analogue / G7", f"G3 analogue: P(pass) at the observed 21/24 = {g3['exact_P_pass_at_observed_rate']:.2f}; 80% pass needs a true rate of {g3['p_needed_for_80pct_pass']:.2f}; G7 observed 171/188 under 20 s, P(pass)~0",
    "G3 (analogue) was a coin flip at the observed rate; G7 is a process outcome, not a design property.", "UNCHANGED")
m = r8
row("R8", "Realised sigma (A->B per-question SD) and MDE (80% power, two-sided .05)",
    f"sigma J {m['J']['sigma']:.3f}, L1* {m['L1star_AH']['sigma']:.3f} ({m['L1star_second_rater']['sigma']:.3f} second), L_R {m['L_R_AH']['sigma']:.3f}; MDE n=23: {m['J']['MDE_normal_n23']:.3f}-{m['L1star_AH']['MDE_normal_n23']:.3f}; n=36: {m['J']['MDE_normal_n36']:.3f}-{m['L1star_AH']['MDE_normal_n36']:.3f} (t-exact {m['J']['MDE_t_n23']:.3f}-{m['L1star_AH']['MDE_t_n23']:.3f}; {m['J']['MDE_t_n36']:.3f}-{m['L1star_AH']['MDE_t_n36']:.3f})",
    "Realised sigma exceeds the design 1.155; at n=23 the MDE is 0.78-0.86 (>= observed delta 0.48-0.57); at n=36 0.63-0.69 (design said 0.54).", "SUPPORTS 'underpowered'; consistent with main L759")
row("R8", "n for 80%-power equivalence (TOST, true diff 0)",
    f"+-0.30: {m['J']['n_equivalence_pm0.30_exact_tost']}-{m['L1star_AH']['n_equivalence_pm0.30_exact_tost']} questions; +-0.50: {m['J']['n_equivalence_pm0.50_exact_tost']}-{m['L1star_AH']['n_equivalence_pm0.50_exact_tost']} (normal {m['J']['n_equivalence_pm0.30_normal_approx']:.0f}-{m['L1star_AH']['n_equivalence_pm0.30_normal_approx']:.0f}; {m['J']['n_equivalence_pm0.50_normal_approx']:.0f}-{m['L1star_AH']['n_equivalence_pm0.50_normal_approx']:.0f}); TOST power at n=36, +-0.50: {m['L1star_AH']['tost_power_n36_pm0.50']:.2f}-{m['J']['tost_power_n36_pm0.50']:.2f}",
    "The 36-question bank cannot show equivalence even at +-0.50 (needs 62-76); +-0.30 needs 170-210.", "SUPPORTS main L541/L984 (equivalence needs a larger bank)")
a9 = r9["AH"]
row("R9", "pi-hat leave-one-cluster-out (AH)",
    f"all 33 drops: {a9['leave_one_cluster_out_all_33']['pi_hat_range_pp'][0]:.2f}-{a9['leave_one_cluster_out_all_33']['pi_hat_range_pp'][1]:.2f}%; event clusters hold {', '.join(str(v) for v in a9['events_by_event_cluster'].values())} of 14 events; drop 3 largest: {a9['drop_two_or_more_event_clusters'][-3]['events']}/{a9['drop_two_or_more_event_clusters'][-3]['cells']}; drop all 4: 0/164 (G1 bound {a9['drop_two_or_more_event_clusters'][-1]['G1_cp_upper_97_5']*100:.1f}% at 29 clusters)",
    "The 7.4% rests on four questions; three of them carry 13 of the 14 events. Even with all four removed G1 stays above 10%.", "WEAKENS precision of the 7.4% point; G1 fail UNCHANGED")
a9s = r9["second_rater"]
row("R9", "pi-hat leave-one-cluster-out (second rater)", f"{a9s['leave_one_cluster_out_all_33']['pi_hat_range_pp'][0]:.2f}-{a9s['leave_one_cluster_out_all_33']['pi_hat_range_pp'][1]:.2f}%; 8 event clusters, largest holds {a9s['largest_single_cluster_share_of_events']*100:.0f}% of events",
    "The 13.8% is spread over eight questions and is stable to any single drop.", "SUPPORTS second-rater estimate's robustness")

results["summary_rows"] = [dict(zip(("id", "quantity", "value", "interpretation", "manuscript_claim"), r)) for r in rows]
json.dump(results, open(HERE / "results.json", "w"), indent=1, default=float)

# ---------------------------------------------------------------- REPORT.md
L = []
L.append("# Review-6 zero-cost reanalyses (R1-R9)\n")
L.append("**Status: POST HOC / EXPLORATORY.** No LLM call, no new label, no `.tex` edit, no commit. All intervals are "
         "question(CQ)-clustered BCa 95% from the analyzer's own interval code (seed 20260913, B = 10,000, mid-rank ties) unless stated. "
         "Nothing here is adjusted for multiplicity (about 150 intervals reported across R1-R9); every statement is descriptive. "
         "Generated by `run_all.py`; numbers come from `results.json` (parts in `parts/`). **AI-written analysis code: review and test before use; "
         "it is checked against recorded analyzer output (`selfcheck.py`) but has not been independently audited.**\n")
L.append(f"**Reproduction gate.** `selfcheck.py` reproduces {len(SELF['checks'])} recorded values bit-for-bit before any new number is used "
         f"(failures: {SELF['n_fail']}): the 2x2 counts, pi-hat 14/188 [0.0215, 0.1852], A->B L1* +0.478 [-0.087, +1.043] with its 90% interval, G4 QWK "
         "0.500 [0.345, 0.642], G5 MAE 0.793 [0.644, 0.947], the second rater's pi-hat 26/188 [5.9, 26.3] and A->B +0.435, judge-only A->B +0.565 [0.043, 1.130], "
         f"the round-31 QWK 0.728 [0.567, 0.859], sigma 1.343/1.473 and MDE 0.784/0.861, plus unit tests of the exact sign-flip routine. `crosscheck_with_analyzer.py` then recomputes four new quantities (R1 net rate, R2 L_R A->B, R3 full-bank A->B, R5 AC1) with the analyzer's own python-loop bootstrap: {len(XC['checks'])} checks, failures {XC['n_fail']}.\n")
L.append("**Inputs (read-only, none sealed).** `harness/real_run/results_human_pass/unsealed_2026-10-09/per_cell.rerun_0dbe6e9.json` (J, AH A and rater_L1; unsealed by PREREG sec.14.1), "
         "`annotation/second_pass_2026-10-13/v3/results_v3_cells.json` (second rater S and R), `harness/real_run/cells.jsonl`, `harness/length_experiment/cells_length.jsonl` and "
         "`luna_full_r35/cells_luna_full_r35.jsonl`, `harness/real_run/paired_ai_audit_48/*/cells.jsonl`, `second_annotator/cell_list_48.txt`. "
         "Not opened: site_key*, labeling_sheet_key*, human_labels_export*, views_for_raters.zip, .env, persona_pass, raw label CSVs with spans or notes. "
         "SHA-256 of every input: `results.json` -> `provenance`.\n")
L.append("**Label provenance (carried into every row).** AH labels are AI-drafted and first-author-revised (the rater consulted an LLM on about half the cells); "
         "the second rater (a co-author) saw the judge's quoted span; no rater ever scored R=0; the second rater's R is a function of S. "
         "S and R are therefore label-source statistics, not error rates against a reference.\n")
L.append("## Summary: every headline number, its reading, and the manuscript claim it touches\n")
L.append("| ID | Quantity | Value (95% CI) | Interpretation | Manuscript claim |\n|---|---|---|---|---|")
for r in rows:
    L.append("| " + " | ".join(str(x).replace("|", "/") for x in r) + " |")
L.append("")

# ---- detail sections
L.append("## R1. Over- vs under-credit (`r1_over_under.py` -> `parts/r1.json`)\n")
L.append("Definitions fixed before the run: S = binary support label, R = rater 0-3 score. Ordinal over = [J>R], under = [J<R]. Binary over = [J>=2 and S=0] "
         "(the registered pi events), under = [J<=1 and S=1]. Denominator: all cells of the stratum.\n")
L.append("| Stratum | n | mean J | mean R | J-R | over/under/equal (ordinal) | binary over | binary under | net over-under |\n|---|---|---|---|---|---|---|---|---|")
for src, lab in (("AH", "AH"), ("second_rater", "2nd")):
    blocks = [("all", r1[src]["overall"])] + [(v, r1[src]["by_variant"][v]) for v in "ABCDEF"]
    for nm, bl in blocks:
        bb, oo = bl["binary_support"], bl["ordinal"]
        L.append(f"| {lab} {nm} | {bl['n_cells']} | {oo['mean_J']['est']:.2f} | {oo['mean_R']['est']:.2f} | {e(oo['mean_J_minus_R'], 2)} | "
                 f"{oo['n_over_J_gt_R']}/{oo['n_under_J_lt_R']}/{oo['n_equal']} | {bb['n_over_J_ge2_S0']} | {bb['n_under_J_le1_S1']} | {pp_(bb['net_rate_over_minus_under'])} |")
L.append("\nInterpretation: the net rate is a signed difference of two rates and its interval contains 0 on both label sources; variant A is the only stratum where the ordinal J-R interval excludes 0 "
         "(judge below the rater). 17 of the 20 AH under-credit cells are J=0 cells where the judge quoted no span; there the rater's S refers to the rendering, not to the judge's span (BRIEF T4c).\n")

L.append("## R2. Symmetric corrections and A->B (`r2_symmetric.py` -> `parts/r2.json`)\n")
L.append("Estimators (0-3 scale): J; L1* = J if S=1 else min(J,1) (registered, withdraw-only); **L_flip** = max(J,2) if S=1 else min(J,1) (two-sided support correction; my construction, post hoc); "
         "**L_R** = rater score where labelled (all 188). A->B over the 23 shared questions; exact two-sided sign-flip permutation p (statistic = sum of per-question differences, signs flipped, exact by dynamic programming).\n")
L.append("| Source | Estimator | cov A / B on 23 (%) | Delta B-A | 95% CI | 90% CI | up/down/tie | Wilcoxon p | sign-flip p |\n|---|---|---|---|---|---|---|---|---|")
for src in ("AH", "second_rater"):
    for k in EST:
        if src == "second_rater" and k == "J":
            continue
        r = ab(src, k)
        L.append(f"| {src} | {k} | {r['coverage_A_pct_on_23']:.1f} / {r['coverage_B_pct_on_23']:.1f} | {r['est']:+.3f} | [{r['lo']:+.3f}, {r['hi']:+.3f}] | [{r['lo90']:+.3f}, {r['hi90']:+.3f}] | "
                 f"{r['n_up']}/{r['n_down']}/{r['n_tie']} | {r['wilcoxon_p']:.3f} | {r['signflip']['p_two_sided']:.4f} |")
L.append("\nShift of the A->B delta relative to L1* (same resamples): " + "; ".join(
    f"{k} {e(v)}" for k, v in r2["AH"]["A_to_B_shift_vs_L1star"].items()) + " (AH). ")
L.append("\nPer-variant coverage (%) under each estimator, AH: " + "; ".join(
    f"{k}: " + " ".join(f"{v}={r2['AH']['coverage_by_variant_pct'][k][v]['est']:.1f}" for v in "ABCDEF") for k in EST) + ".\n")
L.append("**Rogan-Gladen** (binary support share, [J>=2] as the test, S as the reference-like label): per-variant operating characteristics, AH: " + "; ".join(
    f"{v}: Se {x['Se']:.2f} Sp {x['Sp']:.2f}" for v, x in r2["rogan_gladen"]["AH"]["per_variant_operating_characteristics"].items()) +
    f". In-sample pooled Se+Sp-1 = {rg['Se_plus_Sp_minus_1']:.3f}; calibrating on C-F only gives RG {e(r2['rogan_gladen']['AH']['calibrated_on_C_to_F_only']['RG_corrected_contrast_support_share'])}. "
    "The RG interval has 1-2 of 10,000 undefined resamples (excluded). Second rater: RG "
    f"{e(r2['rogan_gladen']['second_rater']['in_sample_all_188_cells']['RG_corrected_contrast_support_share'])}.\n")
L.append("**PPI-style label-budget scenario** (target: mean of R_B-R_A over 23 questions = " f"{pp['full_label_value']:+.3f}" "; prediction J_B-J_A): " + "; ".join(
    f"m={s['m_labelled_questions']}: labelled-only SD {s['labelled_only_sd']:.3f}, PPI SD {s['ppi_sd']:.3f}, PPI++ (oracle lambda {s['ppi_plus_plus_oracle_lambda']:.2f}) SD {s['ppi_pp_sd']:.3f}"
    for s in pp["scenarios"]) + ". With every cell labelled, PPI equals the labelled mean.\n")

L.append("## R3. Full-bank vs eligible-only (`r3_fullbank.py` -> `parts/r3.json`)\n")
L.append("Eligibility is the registered one (A: 23 of 36; B-F: 33 of 36). Full-bank-0 counts ineligible cells as 0; full-bank-3 is the matching upper bound (ineligible = 3). "
         "Per-variant coverage reproduces Supplementary Table S25 exactly (e.g. A 57.97/37.04 on J).\n")
L.append("| Score | Reading | Delta B-A | 95% CI | up/down/tie | sign-flip p |\n|---|---|---|---|---|---|")
for nm in ("J", "L1star_AH", "L1star_second_rater"):
    for k, lab in (("eligible_only_23_registered", "eligible-only (23 q)"), ("full_bank_36_ineligible_0", "full-bank-0 (36 q)"),
                   ("full_bank_36_ineligible_3_upper_bound", "full-bank-3 (36 q, upper bound)")):
        r = r3[nm]["A_to_B"][k]
        L.append(f"| {nm} | {lab} | {r['est']:+.3f} | [{r['lo']:+.3f}, {r['hi']:+.3f}] | {r['n_up']}/{r['n_down']}/{r['n_tie']} | {r['signflip']['p_two_sided']:.4f} |")
dc = r3["L1star_AH"]["decomposition_full_bank_0_sum_of_differences"]
L.append(f"\nDecomposition (L1*, AH, full-bank-0): the 23 shared questions contribute a summed difference of {dc['sum_diff_on_23_shared']:.0f}; the {dc['questions_ineligible_in_A_only']} questions "
         f"ineligible only in A contribute {dc['sum_diff_on_A_only_ineligible']:.0f} (B's whole score there, mean {dc['mean_B_score_on_A_only_ineligible_questions']:.2f}); "
         f"{dc['questions_ineligible_in_all_variants']} questions are ineligible everywhere and contribute 0.\n")

L.append("## R4. Same-question-set A->B across judges (`r4_same_question_set.py` -> `parts/r4.json`)\n")
L.append("| Judge / condition | n questions | mean J on A / B | Delta B-A | 95% CI | 90% CI | up/down/tie | sign-flip p |\n|---|---|---|---|---|---|---|---|")
for k, r in r4["per_judge_question_set"].items():
    L.append(f"| {k} | {r['n_questions']} | {r['mean_A_on_set']:.2f} / {r['mean_B_on_set']:.2f} | {r['est']:+.3f} | [{r['lo']:+.3f}, {r['hi']:+.3f}] | [{r['lo90']:+.3f}, {r['hi90']:+.3f}] | "
             f"{r['n_up']}/{r['n_down']}/{r['n_tie']} | {r['signflip']['p_two_sided']:.4f} |")
sc = r4["strict_common_set"]
L.append(f"\nStrict common set ({sc['n_questions']} questions valid in every condition; dropped: {sc['questions_not_common']}): " + "; ".join(
    f"{k.split(' (')[0]} {r['est']:+.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}]" for k, r in sc["contrasts"].items()) + ". "
    "Valid-score rule as in the length experiment (parse ok, 0-3; last valid record wins). luna 'limited' truncates the view to 60,000 characters, which cuts B-F (about 2 M characters) far more than A (0.29 M); "
    "the registered Gemini J reads the untruncated views.\n")

L.append("## R5. Human-human reference and judge-AH agreement indices (`r5_human_human.py` -> `parts/r5.json`)\n")
L.append("| Pair (188 cells) | MAE | exact agreement | QWK |\n|---|---|---|---|")
for k, v in o.items():
    L.append(f"| {v['label']} | {e(v['mae'])} | {e(v['exact'], pct=True)} | {e(v['qwk'])} |")
L.append("\n| Binary support call | raw agreement | Cohen kappa | Gwet AC1 | PABAK | table n00/n01/n10/n11 |\n|---|---|---|---|---|---|")
for k, v in bsp.items():
    L.append(f"| {v['label']} | {e(v['agreement'], pct=True)} | {e(v['kappa'])} | {e(v['ac1'])} | {e(v['pabak'])} | {v['table_n00_n01_n10_n11']} |")
L.append("\nPaired differences (same resamples):\n")
L.append("| Contrast | Estimate | 95% CI |\n|---|---|---|")
for k, v in r5["paired_differences"].items():
    L.append(f"| {k} | {v['est']:+.3f} | [{v['lo']:+.3f}, {v['hi']:+.3f}] |")
L.append("\nDescriptives: " + json.dumps(r5["descriptives"]) + ". Registered bars shown for orientation only: G4 falsified if the QWK upper limit < 0.60; G5 needs the MAE upper limit <= 0.50. "
         "Human-human ordinal agreement is inflated by the S-R coupling and was produced by raters of unequal independence (second rater saw the judge's span; AH rater consulted an LLM); it is a different-rater statistic, not the registered same-rater G2.\n")

L.append("## R6. Cross-family panel, 48 cells (`r6_panel.py` -> `parts/r6.json`)\n")
L.append(f"Composition {r6['cells_by_variant']}, {r6['n_clusters']} questions. Paired questions per variant pair: {r6['paired_questions_matrix']}. "
         f"**A-B paired questions: {r6['A_B_paired_questions']}** (A: {r6['A_cqs']}; B: {r6['B_cqs']}), so the registered paired A->B contrast is not estimable per judge on this panel. "
         "A vs the same-question graph cell (C or E): 3 pairs on 2 questions, graph>A for every judge (mean differences "
         + ", ".join(f"{k.split(' (')[0]} {v['mean_diff']:+.2f}" for k, v in r6['A_vs_same_question_graph_cells'].items()) + "). Pooled unpaired graph-minus-A (3 A cells vs 45 graph cells; "
         "resamples that drop all three A clusters, 4.2%, are excluded): " + "; ".join(f"{k.split(' (')[0]} {e(v, 2)}" for k, v in r6['pooled_graph_minus_A_unpaired'].items()) +
         ". Judge means by variant (Gemini): " + ", ".join(f"{v} {x:.2f}" for v, x in r6['variant_means_J']['Gemini J (registered)'].items()) +
         ". The cross-judge direction check that has a usable n is R4 (Gemini and luna, 23 pairs).\n")

L.append("## R7. Monte Carlo gate pass probability at the realised design (`r7_gate_mc.py` -> `parts/r7.json`)\n")
L.append("Plug-in world: 33 clusters redrawn with replacement from the observed 33 (all of a cluster's cells together), registered CI computed on each draw (inner B = 1000), S = 2000 draws per row. "
         "Improvement worlds replace each second score, with probability q, by the best attainable value (R' = max(J,1) for judge-rater; R2' = R_AH for the human pair); the true MAE/QWK of each world "
         "is computed from the expected confusion matrix. Seed 20260913.\n")
L.append("| Gate | World (truth) | P(pass) or P(falsified) |\n|---|---|---|")
L.append(f"| G1 n=33, 97.5% | any | 0 (0 events -> {g1['n33_level97.5']['cp_upper_at_zero_events']*100:.2f}% > 10%) |")
L.append(f"| G1 n=33, 95% | observed 4/33 event clusters (MC 100,000; exact binomial) | {g1['plug_in_mc_AH']['mc_P_pass_level95']:.4f} ({g1['plug_in_mc_AH']['exact_P_zero_events_in_33_draws']:.4f}) |")
for k, v in g1["exact_pass_probability"]["n36_level97.5"].items():
    L.append(f"| G1 n=36, 97.5% | {k} | {v:.3f} |")
for w in g5:
    L.append(f"| G5 pass | true MAE {w['true_MAE']:.3f} | {w['P_pass']:.3f} |")
for w in g4:
    L.append(f"| G4 falsified | true QWK {w['true_QWK']:.3f} | {w['P_falsified']:.3f} |")
for w in g2:
    L.append(f"| G2 analogue pass | true QWK {w['true_QWK']:.3f} | {w['P_pass']:.3f} |")
for w in g6:
    L.append(f"| A->B CI excludes 0 (G6 necessary part) | true delta {w['true_delta']:.3f} | {w['P_ci_excludes_0']:.3f} |")
for k, v in g3["exact_P_pass_at_p"].items():
    L.append(f"| G3 judge-side analogue | {k} | {v:.3f} |")
L.append(f"| G7 | 171/188 under 20 s | {r7['G7']['exact_P_pass_at_observed_rate']:.1e} |")
L.append("\nG8 and the registered same-rater G2 were not run and are not simulated. The MC type-I rate of the BCa 'resolved' rule at n=23 (delta 0) is the first G6 row; Monte Carlo error is about +-0.5 points at 2000 draws.\n")

L.append("## R8. MDE with the realised sigma; n for equivalence (`r8_mde.py` -> `parts/r8.json`)\n")
L.append("MDE_normal = 2.8016 sigma/sqrt(n) (the manuscript formula); MDE_t exact noncentral-t power; TOST power by exact quadrature over the sample SD (alpha .05 per side, true difference 0). "
         "sigma = SD (ddof=1) of the 23 per-question A->B differences.\n")
L.append("| Score | sigma [95% chi2] | MDE n=23 (normal / t) | MDE n=36 (normal / t) | n for +-0.30 (normal / exact) | n for +-0.50 (normal / exact) | TOST power n=36 +-0.50 | power at observed delta, n=23 |\n|---|---|---|---|---|---|---|---|")
for k in ("J", "L1star_AH", "L1star_second_rater", "L_flip_AH", "L_R_AH"):
    v = m[k]
    L.append(f"| {k} | {v['sigma']:.3f} [{v['sigma_ci95_chi2'][0]:.3f}, {v['sigma_ci95_chi2'][1]:.3f}] | {v['MDE_normal_n23']:.3f} / {v['MDE_t_n23']:.3f} | {v['MDE_normal_n36']:.3f} / {v['MDE_t_n36']:.3f} | "
             f"{v['n_equivalence_pm0.30_normal_approx']:.0f} / {v['n_equivalence_pm0.30_exact_tost']} | {v['n_equivalence_pm0.50_normal_approx']:.0f} / {v['n_equivalence_pm0.50_exact_tost']} | {v['tost_power_n36_pm0.50']:.2f} | {v['power_normal_at_observed_delta_n23']:.2f} |")
dv = m["design_sigma_1.155"]
L.append(f"| design 1.155 | - | {dv['MDE_normal_n23']:.3f} / {dv['MDE_t_n23']:.3f} | {dv['MDE_normal_n36']:.3f} / {dv['MDE_t_n36']:.3f} | {dv['n_equivalence_pm0.30_normal_approx']:.0f} / {dv['n_equivalence_pm0.30_exact_tost']} | {dv['n_equivalence_pm0.50_normal_approx']:.0f} / {dv['n_equivalence_pm0.50_exact_tost']} | {dv['tost_power_n36_pm0.50']:.2f} | - |")
L.append("\nThe 'power at observed delta' column is descriptive only (observed power is a monotone function of the p value). The sigma interval (about 1.04-1.9 for J) means each MDE has a +-30% band.\n")

L.append("## R9. Leave-one-cluster-out sensitivity of pi-hat (`r9_loco.py` -> `parts/r9.json`)\n")
for src, lab in (("AH", "AH labels"), ("second_rater", "Second rater")):
    a = r9[src]
    L.append(f"**{lab}:** {a['events']}/{a['cells']} = {a['pi_hat']*100:.2f}%, event clusters {a['events_by_event_cluster']}. Dropping any one of the 33 clusters: "
             f"{a['leave_one_cluster_out_all_33']['pi_hat_range_pp'][0]:.2f}-{a['leave_one_cluster_out_all_33']['pi_hat_range_pp'][1]:.2f}%. Cluster jackknife SE of pi-hat {a['cluster_jackknife_se_pi_hat']:.4f}.\n")
    L.append("| Dropped event clusters | events/cells | pi-hat | event clusters/total | G1 CP upper 97.5% (95%) |\n|---|---|---|---|---|")
    for x in a["leave_one_event_cluster_out"]:
        L.append(f"| {x['dropped']} | {x['events']}/{x['cells']} | {x['pi_hat']*100:.2f}% | {x['event_clusters']}/32 | {x['G1_cp_upper_97_5']*100:.1f}% ({x['G1_cp_upper_95']*100:.1f}%) |")
    combos = a["drop_two_or_more_event_clusters"]
    for x in combos[-3:]:
        L.append(f"| {', '.join(x['dropped'])} | {x['events']}/{x['cells']} | {x['pi_hat']*100:.2f}% | {x['event_clusters']}/{x['of_clusters']} | {x['G1_cp_upper_97_5']*100:.1f}% ({x['G1_cp_upper_95']*100:.1f}%) |")
    L.append("")
L.append("Bonus (same logic): leave-one-question-out A->B delta, L1* AH " + f"{r9['A_to_B_leave_one_question_out']['L1star_AH']['min']:+.3f} to {r9['A_to_B_leave_one_question_out']['L1star_AH']['max']:+.3f}, "
         f"J {r9['A_to_B_leave_one_question_out']['J']['min']:+.3f} to {r9['A_to_B_leave_one_question_out']['J']['max']:+.3f} (no single question moves it near 0).\n")

L.append("## Threats and limits of these reanalyses\n")
L.append("- Post hoc, unadjusted, descriptive; no result here changes a registered gate status or the registered A->B decision (unresolved).\n"
         "- AH labels are LLM-assisted and partly shaped by the AI draft; the second rater saw the judge's span. R1, R2, R5 therefore compare label sources; they do not measure error against a truth.\n"
         "- L_flip is my construction (raises J to 2 where the label source finds support); L_R uses the rater score, whose floor R>=1 and coupling to S (R determined by S for the second rater) make it a coarse scale.\n"
         "- R3 'ineligible = 0' is a convention, not a measurement; the ineligible questions are corpus-rare for the variant, so 0 and 3 are the two extreme fills.\n"
         "- R4 luna is a substitute judge (D28) and its 'limited' condition truncates views; conditions differ in input length, not only in judge. luna full is ceilinged.\n"
         "- R6: the frozen 48-cell list was chosen for the second-annotator design and holds no A-B pair; nothing can be concluded about A->B on it.\n"
         "- R7 plug-in worlds resample 33 observed clusters, so they inherit the observed cluster structure; BCa on small discrete data is slightly liberal (6% false-resolution under delta=0 at n=23). "
         "G2 and G6 rows are analogues, not evaluations of the registered gates.\n"
         "- R8 uses one sigma per contrast; the 23-question sigma has a wide interval, so n for equivalence is uncertain by roughly +-40%.\n"
         f"- All {len(SELF['checks'])} reproduction checks pass, but the scripts have not had an independent code audit.\n")
L.append("## Files\n")
L.append("`common.py` (loaders, vectorised BCa identical to the analyzer's draws, agreement statistics, exact sign-flip), `selfcheck.py` (+`selfcheck.json`), `provenance.py`, "
         "`r1_over_under.py`, `r2_symmetric.py`, `r3_fullbank.py`, `r4_same_question_set.py`, `r5_human_human.py`, `r6_panel.py`, `r7_gate_mc.py`, `r8_mde.py`, `r9_loco.py`, "
         "`crosscheck_with_analyzer.py` (+`crosscheck.json`), `run_all.py`, `parts/*.json` (+ logs), `results.json`, `REPORT.md`. Re-run: `python3 run_all.py` from this directory (about 2 minutes).")
(HERE / "REPORT.md").write_text("\n".join(L) + "\n")
print("wrote results.json and REPORT.md;", len(rows), "summary rows")
