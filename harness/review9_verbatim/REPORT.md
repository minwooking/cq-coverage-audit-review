REVIEW 9 REPORT
Post hoc, exploratory. No model call, network or server access. AI-generated; review and test before reuse and before any number goes into an external text.
Reproduce: python3 harness/review9_verbatim/analyze.py (about 5 s; self-test first; pytest analyze.py collects the same 4 tests).
Rounding: the tables below were printed from the four-decimal values stored in results.json and can differ by one unit in the last digit from the exact values (for example +1.044 for the lattice value 24/23 = +1.043, and 3.9 for 7/182 = 3.8%). The manuscript and make_tables.py use the exact values (counts, or k/n for a contrast over n questions).

1. DATA
- The primary holdout judge (gemini-3.6-flash, harness/real_run/cells.jsonl, 188 primary cells, 33 question clusters, A 23, B-F 33) DID emit spans: the registered rubric asks for {"score","evidence":"<verbatim span, or empty>"}; every J>=1 cell has non-empty evidence (185 strings, 3 lists), every J=0 cell an empty one. Fallback to other judges (step 2) not needed; they were added as extra rows.
- Rendering the judge saw: harness/variants/<V>/rendered_view.txt sent as "ARTIFACT:\n<view>"; sha256 equals artifact_digest of all cells (asserted).
- Labels (de-identified files read by review6_reanalysis/common.py): AH = real_run/results_human_pass/unsealed_2026-10-09/per_cell.rerun_0dbe6e9.json; second rater v3 = annotation/second_pass_2026-10-13/v3/results_v3_cells.json (S equals labels_for_analysis.csv on 188/188). Reproduced: events (J>=2, S=0) 14 AH / 26 second rater; pi-hat 7.4% [2.2,18.5] / 13.8% [5.9,26.3], identical to analyze_holdout.silent_over_credit_rate.
- Other judges on the same cells: gpt-5.6-luna on full views (188), subgraph (179 valid), 60k truncation (188); gpt-oss-20b and GLM-4.7-Flash on subgraph views (182, 3 temperature-0 repeats each); 48-cell panel (luna, sonnet). Raw-J A->B of these loaders equals review6_reanalysis r4 and review6_judges/results.json (diff 0).

2. MATCHER
norm and verbatim are IMPORTED from harness/review6_natural/analyze_natural.py: whitespace runs collapse, ends stripped, case sensitive, substring test against the whitespace-normalised view; a list passes only if every non-empty string element does; empty/missing/non-string fails. Credit = J>=2 (paper's pi event; the brief's "J>0" would give 20 events on AH and 33 on the second rater, 1 failing each). Withdrawal J* = J if J<2 or verbatim, else min(J,1); L1* with check = demote(J*,S). Sensitivities: J*=0; elision-tolerant matcher (split at "..."; fragments >=12 chars verbatim). Intervals: question-cluster BCa 95%, B=10000, seed 20260913, analyzer's draws (fast_ci equals the analyzer, diff 0, on pi-hat raw, pi-hat withdrawn and A->B).

3. PRIMARY JUDGE
Credits 132 (J=2: 36, J=3: 96). Verbatim 118/132 = 0.894 [0.736, 0.968]. By variant A 11/13, B 23/26, C 23/25, D 20/22, E 20/22, F 21/24. The 14 failing credits (7 J=2, 7 J=3) are in 6 clusters (CQB07,08,12,21,30,34); 4 contain "...", 10 do not; longest verbatim prefix median 18% of the span (4% to 75%): stitched or edited quotes (p_subclass vs p_class-schema, datatype-property vs object-property, Class_artifact vs Class_class). Elision-tolerant matcher rescues 1.

                                   AH                                   second rater v3
events (J>=2,S=0)                  14 (4 clusters)                      26 (8 clusters)
events failing (recall)            0/14; Wilson [0,21.5%]; clusters     0/26; Wilson [0,12.9%]; clusters 0/8,
                                   0/4, exact [0,60%]                   exact [0,37%]
supported credits failing          14/118 = 11.9%, BCa [3.6,28.7]       14/106 = 13.2%, BCa [4.0,31.5]
precision of flags                 0/14 (base rate 14/132)              0/14 (base rate 26/132)
pi-hat raw -> withdrawn            7.4 [2.2,18.5] -> same               13.8 [5.9,26.3] -> same
A->B L1* -> with check             +0.478 [-0.087,+1.044] -> same       +0.435 [-0.130,+1.044] -> +0.435 [-0.087,+0.957]
Label-free A->B: J +0.565 [+0.043,+1.130] -> J* +0.565 [+0.087,+1.087]; full withdrawal +0.522 [0.000,+1.087].
Cluster BCa for recall is degenerate (all resamples 0); Wilson ignores clustering (too narrow).
Reading: zero recall on both label sources; 14 flagged credits that both raters judged supported; pi-hat and the A->B contrast do not move. Inference: the check measures quote fidelity, not support.

4. OTHER JUDGES (credit J>=2; recall = events failing / events; false flag = supported credits failing / supported credits)
run             cells credits verbatim   AH recall   AH false flag  pi AH raw->withdrawn             2nd recall  2nd false flag  pi 2nd raw->withdrawn
gemini_primary  188   132     118        0/14        14/118         7.4 -> 7.4                       0/26        14/106          13.8 -> 13.8
luna_full       188   156     97         15/24       44/132         12.8[5.7,25.0]->4.8[1.6,12.6]    18/39       41/117          20.7[10.8,34.9]->11.2[4.3,23.7]
luna_subgraph   179   97      70         12/21       15/76          11.7[4.5,24.3]->5.0[1.2,13.1]    13/32       14/65           17.9[8.5,32.8]->10.6[4.1,23.2]
gptoss r1/r2/r3 182   96/97/99 51/44/48  12/14,13/15,11/15  33/82,40/82,40/84  7.7/8.2/8.2->1.1/1.1/2.2  14/22,16/23,13/22  31/74,37/74,38/77  12.1/12.6/12.1->4.4/3.9/5.0
glm r1/r2/r3    182   121/117/113 55/55/52 17/27,14/26,15/25 49/94,48/91,46/88 14.8/14.3/13.7->5.5/6.6/5.5  18/31,14/29,17/32  48/90,48/88,44/81  17.0/15.9/17.6->7.1/8.2/8.2
luna_limited60k 188   19      17         0/1         2/18           0.5 -> 0.5                       0/1         2/18            0.5 -> 0.5
panel48_luna    48    39      23         5/6         11/33          12.5 -> 2.1                      9/17        7/22            35.4 -> 16.7
panel48_sonnet  48    26      16         0/0         10/26          0.0 -> 0.0                       3/6         7/20            12.5 -> 6.2
Reading: for loosely quoting judges (luna_full, luna_subgraph, gpt-oss, GLM; both label sources) the check catches 41%-87% of unsupported credits and lowers pi-hat by a factor of 1.7 to 7.5, but flags 20%-55% of supported credits; flagged credits are events in 25%-27% of cases on AH (luna_full 15/59, gptoss r1 12/45, glm r1 17/66) vs base rates 15%, 15%, 22% (cell-level Fisher p 0.011, 0.003, 0.38 AH; 0.25, 0.09, 0.68 second rater; clustering ignored): a screen with modest lift. Subgraph judges saw less than the raters (S refers to the full rendering). luna_limited60k (19 credits) and panel48 (0-6 AH events) support no reading.

A->B after the check (score points; 23 questions full view, 22 subgraph)
run             J                       J*                      L1* AH                  L1* AH+check            L1* 2nd                 L1* 2nd+check
gemini_primary  +0.565[+0.043,+1.130]   +0.565[+0.087,+1.087]   +0.478[-0.087,+1.044]   +0.478[-0.087,+1.044]   +0.435[-0.130,+1.044]   +0.435[-0.087,+0.957]
luna_full       -0.043[-0.217,+0.261]   -0.391[-0.826,+0.000]   -0.043[-0.478,+0.391]   -0.304[-0.739,+0.130]   -0.043[-0.435,+0.391]   -0.348[-0.783,+0.087]
luna_subgraph   +0.091[-0.500,+0.682]   -0.182[-0.727,+0.455]   -0.182[-0.682,+0.364]   -0.273[-0.773,+0.318]   -0.136[-0.545,+0.273]   -0.273[-0.727,+0.182]
gptoss r1       +0.500[-0.318,+1.273]   +0.045[-0.591,+0.682]   +0.591[-0.182,+1.318]   +0.136[-0.500,+0.727]   +0.500[-0.227,+1.182]   +0.136[-0.500,+0.727]
gptoss r2       +0.455[-0.273,+1.227]   -0.182[-0.818,+0.409]   +0.364[-0.364,+1.046]   -0.182[-0.818,+0.409]   +0.273[-0.273,+0.818]   -0.182[-0.727,+0.273]
gptoss r3       +0.273[-0.409,+0.955]   -0.091[-0.818,+0.591]   +0.273[-0.364,+0.818]   +0.091[-0.591,+0.727]   +0.182[-0.409,+0.636]   +0.000[-0.636,+0.500]
glm r1          +0.636[-0.045,+1.273]   +0.591[+0.000,+1.136]   +0.364[-0.273,+1.000]   +0.500[-0.045,+1.091]   +0.364[-0.227,+0.909]   +0.500[+0.045,+0.955]
glm r2          +0.364[-0.364,+1.046]   +0.227[-0.409,+0.864]   +0.136[-0.545,+0.818]   +0.136[-0.455,+0.773]   +0.136[-0.500,+0.682]   +0.136[-0.409,+0.636]
glm r3          +0.636[-0.045,+1.318]   +0.455[-0.136,+1.091]   +0.455[-0.136,+1.000]   +0.409[-0.046,+0.955]   +0.409[-0.136,+0.909]   +0.409[-0.045,+0.864]
Primary judge: no movement. luna (full) and gpt-oss fall to or below zero because B-F credits fail more often than A credits (luna_full verbatim A 16/19, B 17/29, C 18/27, D 13/28, E 17/26, F 16/27); GLM stays positive. The elision-tolerant matcher changes none of this for the primary judge.

5. DWELL (AH rater vs second rater)
Per-cell AH dwell exists in the unsealed AH per-cell file (audit_elapsed_s, 188 cells, one save each; median 9.3 s; 171 under 20 s, 17 at or above; max 3,482 s). Second rater dwell is blank for all cells.
S disagrees, all 188: under 20 s 28/171 = 16.4% [11.6,22.7]; >=20 s 4/17 = 23.5% [9.6,47.3]; difference -7.2 points [-29.1,+12.1] (cluster bootstrap percentile); Fisher p 0.50 (cell level).
R differs exactly, all 188: 46/171 = 26.9% vs 7/17 = 41.2%; difference -14.3 points [-38.8,+11.7]; p 0.26.
S disagrees, credited cells (J>=2): 20/121 = 16.5% vs 2/11 = 18.2%; -1.7 points [-24.0,+17.2]; p 1.0.
Fast cells do not disagree more than slow cells: opposite sign, intervals include zero (17 slow cells, little power).

6. CAVEATS
Post hoc, no multiplicity correction; few events (AH 14 in 4 clusters) so recall for the primary judge is bounded only to 0-21.5% (cell level) or 0-60% (cluster level). The check tests string identity, not support; both label sources are imperfect (AH model-drafted; 171 of 188 cells saved in under 20 s). The AH file is in unsealed_2026-10-09/ (seal lifted by the author, PREREG section 14; review6_reanalysis reads the same file). Not opened: SEALED_until_washout/, site_key*, labeling_sheet_key*, human_labels_export*, views_for_raters.zip, .env, employee CSVs. results.json holds aggregates and label-free per-cell judge flags only. 6 primary cells have no subgraph; invalid repeat records dropped, nothing imputed; the 3 gpt-oss/GLM repeats are shown separately. pi-hat is a cell-level lower bound; ratio statistics drop resamples with a zero denominator (counts in results.json).
