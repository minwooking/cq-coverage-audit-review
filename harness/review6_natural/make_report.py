#!/usr/bin/env python3
"""Write REPORT.md of the natural-document check (addendum 27) from results.json.

AI-written script: review and test before reuse. It reads only files of this directory (results.json, corpus_stats.json,
grounding_check.json, jobs_summary.json), makes no model call and prints no secret. Re-run: python3 make_report.py
"""
import json, os

D = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(D, 'results.json')))
CS = json.load(open(os.path.join(D, 'corpus_stats.json')))
NAMES = {'gptoss': 'gpt-oss-20b (primary, non-Qwen)', 'glm': 'GLM-4.7-Flash (primary, non-Qwen)',
         'qwenflash': 'Qwen3.8-Flash-Next (same-family contrast)'}
ORDER = ['gptoss', 'glm', 'qwenflash']


def f3(x):
    return ('%+.3f' % x) if abs(x) >= 0.0005 else '0.000'


def iv(lo, hi):
    return '[%s, %s]' % (f3(lo), f3(hi))


def ab(sets, key):
    a = sets[key]['A_to_B']
    return '%s %s' % (f3(a['mean_diff_score']), iv(*a['ci95_score']))


out = []
w = out.append
w('# REPORT -- addendum 27 (exploratory): natural-document Brick corpus, A and B scored by three judges\n')
w('> AI-generated report from `results.json` (written by `make_report.py`); the author must review it before use. Exploratory and post hoc; descriptive only, no decision rule and no multiplicity correction (PLAN.md 27.1, 27.A1.8). Intervals are question-clustered BCa 95%% (B = %d, seed %d). Code and commands in this directory are AI-generated and must be reviewed and tested before reuse; nothing here is applied to a production system. Before external use, check the numbers for internal addresses and unpublished data (none are intended; the corpus is public documentation).\n' % (R['B'], R['seed']))

w('## 0. What was done and what it shows\n')
nat = {j: R['per_judge'][j]['natural']['sets']['S_full'] for j in ORDER}
w('**Question.** When baseline A and the pipeline\'s base build B are built from hand-written Brick documentation (no schema file) and scored with the frozen 36-question bank on question-relevant subgraph views, does the A -> B contrast behave as on the template-corpus holdout, and what does a deterministic verbatim-span check change? (PLAN 27.1, 27.A1.)\n')
w('**Run.** Corpus: %d files, %d atomic chunks, %s characters (`corpus_stats.json`). Grounding check before any build: the analyst read (not blind) finds the answer present in full for %d, in part for %d and not at all for %d of 36 questions, so %d of 36 (%.1f%%) are answerable; the stop rule (< 20%%) did not fire. A and B were built with the unchanged pipeline commands on one server (%d extractor calls, no failure). The planned judge (gpt-5.6-luna) was blocked (HTTP 402) and no luna score exists; the scoring judges are gpt-oss-20b and GLM-4.7-Flash (primary, non-Qwen) and Qwen3.8-Flash-Next (same-family contrast), three repeats each, 72 natural cells; the template A/B subgraph cells (54, 22 paired questions) were scored by the same judges (records of addendum 26 reused where the prompt checksum matched).\n' % (
    CS['files_included'], CS['atomic_chunks'], format(CS['atomic_chars_total'], ','), R['grounding']['analyst_counts']['full'], R['grounding']['analyst_counts']['partial'], R['grounding']['analyst_counts']['none'],
    R['grounding']['analyst_counts']['full'] + R['grounding']['analyst_counts']['partial'], 100 * R['grounding']['answerable_share'], R['extractor_usage']['total_calls']))
w('**Result (descriptive).** A -> B over all 36 questions: ' + '; '.join('%s %s' % (j, ab({'S': nat[j]}, 'S')) for j in ORDER) + ' (score points). Every interval includes zero, as on the template corpus. With the verbatim-span demotion the contrast moves to ' + '; '.join('%s %s' % (j, ab(R['per_judge'][j]['natural']['machine_adjusted'], 'S_full')) for j in ORDER) + '. The share of credits (J >= 2) whose quoted span occurs verbatim in the view is lower on B views than on A views for all three judges (table 3).\n')

w('## 1. Table for the manuscript (as written into `results.json`)\n')
for i, line in enumerate(R['text_table']):
    w('| ' + line + ' |')
    if i == 0:
        w('|' + '---|' * len(line.split(' | ')))
w('')
w('Columns: judge | family | natural S_full A->B | natural S_elig A->B | template (22 q) A->B | natural minus template (22 q) | share of J >= 2 records with a verbatim span, natural A/B.\n')

w('## 2. A -> B by question set (score points; BCa 95%)\n')
w('| judge | set | n | coverage A, B (%) | share J >= 2 A, B (%) | A -> B | B>A / = / < |')
w('|---|---|---|---|---|---|---|')
for j in ORDER:
    ss = R['per_judge'][j]['natural']['sets']
    for k in ['S_full', 'S_elig', 'S_elig_L1', 'S_art']:
        s = ss[k]
        a = s['A_to_B']
        w('| %s | %s | %d | %.1f, %.1f | %.1f, %.1f | %s | %d / %d / %d |' % (
            j, k, s['n_paired'], s['coverage_A']['estimate'], s['coverage_B']['estimate'], s['share_ge2_A']['estimate'], s['share_ge2_B']['estimate'],
            ab(ss, k), a['B_gt_A'], a['B_eq_A'], a['B_lt_A']))
w('')
w('Sets: S_full = all 36 questions; S_elig = questions rated full or partial by the analyst read (24); S_elig_L1 = questions passing the automated section tier (28); S_art = questions whose anchors appear in both views (16).\n')

w('## 3. Verbatim-span check (descriptive; a string test, not an evidence label)\n')
w('| judge | corpus | A: J >= 2 records, verbatim | B: J >= 2 records, verbatim | A -> B raw | A -> B after demotion |')
w('|---|---|---|---|---|---|')
for j in ORDER:
    for corp, key in [('natural (36 q)', 'natural'), ('template (22 q)', 'template')]:
        pj = R['per_judge'][j][corp.split()[0]]
        me = pj['machine_evidence']
        sk = 'S_full' if key == 'natural' else 'tpl_paired'
        w('| %s | %s | %d of %d (%.2f) | %d of %d (%.2f) | %s | %s |' % (
            j, corp, me['A']['verbatim'], me['A']['J_ge2_records'], me['A']['verbatim_share'], me['B']['verbatim'], me['B']['J_ge2_records'], me['B']['verbatim_share'],
            ab(pj['sets'], sk), ab(pj['machine_adjusted'], sk)))
w('')
w('Rule (PLAN 27.7-4, 27.A1.8-4): a record with J >= 2 keeps its score only if its `evidence` string occurs verbatim in the view that was sent (whitespace normalized, case sensitive; a list counts only if every non-empty element does); otherwise J* = min(J, 1). Records, not cells, are counted (three repeats per cell).\n')

w('## 4. Natural against template, same judge (22 questions in both corpora)\n')
w('| judge | natural A -> B | template A -> B | natural minus template |')
w('|---|---|---|---|')
for j in ORDER:
    nt = R['per_judge'][j]['natural_vs_template']
    w('| %s | %s %s | %s %s | %s %s |' % (j, f3(nt['natural_A_to_B']['mean']), iv(*nt['natural_A_to_B']['ci95']), f3(nt['template_A_to_B']['mean']), iv(*nt['template_A_to_B']['ci95']),
                                      f3(nt['natural_minus_template']['mean']), iv(*nt['natural_minus_template']['ci95'])))
w('')
lc = R['luna_402_context']['reference_template_luna_subgraph']
w('Historical context only (not part of the comparison): the template A -> B under the substitute judge gpt-5.6-luna on subgraph views was %s %s on 22 questions (`harness/length_experiment`).\n' % (f3(lc['template_A_to_B']['mean_diff_J']), iv(*lc['template_A_to_B']['ci95_J'])))

w('## 5. Agreement, stability and cost\n')
w('| judge | repeat pairwise exact agreement, natural / template | all three identical, natural / template | prompt tokens (natural) | completion tokens |')
w('|---|---|---|---|---|')
for j in ORDER:
    pj = R['per_judge'][j]
    w('| %s | %.3f / %.3f | %.3f / %.3f | %s | %s |' % (j, pj['natural']['run_to_run']['mean_pairwise_exact_agreement'], pj['template']['run_to_run']['mean_pairwise_exact_agreement'],
                                                  pj['natural']['run_to_run']['share_identical_across_3'], pj['template']['run_to_run']['share_identical_across_3'],
                                                  format(pj['natural']['usage']['prompt_tokens'], ','), format(pj['natural']['usage']['completion_tokens'], ',')))
w('')
cj = R['cross_judge_natural']
w('Cross-judge agreement on the natural cells (mean over repeats): ' + '; '.join('%s QWK %.3f, exact %.3f' % (k.replace('_', ' '), v['qwk_per_repeat_mean'], v['exact_agreement_per_repeat_mean']) for k, v in cj.items()) + '. The sign of the natural A -> B (S_full) is positive for all three judges.\n')

w('## 6. Artifacts and extractor\n')
a = R['artifacts']['variants']
w('| variant | triples | OWL classes | named individuals | rendered view (lines, characters) |')
w('|---|---|---|---|---|')
for v in ['A', 'B']:
    w('| %s | %s | %d | %s | %s, %s |' % (v, format(a[v]['triples'], ','), a[v]['owl_classes'], format(a[v]['named_individuals'], ','), format(a[v]['rendered_view_lines'], ','), format(a[v]['rendered_view_chars'], ',')))
w('')
ar = R['artifact_anchor_retention']['all_36']
w('Artifact preflight (anchor terms present in the full rendered view): both A and B for %d questions, A only for %d, B only for %d, neither for %d (A %d, B %d of 36). Extractor: %d calls, %s prompt and %s completion tokens, no failure. The full views were not scored (B\'s view cannot fit the 65,536-token window and the estimate exceeded the budget).\n' % (
    ar['both'], ar['only_A'], ar['only_B'], ar['neither'], ar['A_anchor_pass'], ar['B_anchor_pass'], R['extractor_usage']['total_calls'], format(R['extractor_usage']['total_prompt_tokens'], ','), format(R['extractor_usage']['total_completion_tokens'], ',')))

w('## 7. Deviations, cautions and what was not done\n')
w('* **Planned judge blocked.** gpt-5.6-luna through the local proxy answered HTTP 429 and then 402 on the three in-flight calls (B:CQB01, B:CQB10, B:CQB29); by PLAN 27.6 the run stopped, the three invalid records were discarded (kept in `luna_402_discarded/` as evidence of the block), and **no luna score exists for the natural corpus** (amendment 1, commit `7500f27`). The replacement judges are not the registered holdout judge and not luna; their scores are not comparable to registered-judge or luna scores.')
w('* **Same-family contrast judge** (amendment 2, commit `248129f`, at the author\'s request): Qwen3.8-Flash-Next (NVFP4 weights) shares a model line with the extractor but is a different checkpoint and quantization, so "same family" means shared lineage. It is a contrast, never a headline.')
w('* **Extractor weights.** The extractor is addressed by the holdout build\'s served name, but the container behind it now serves NVFP4 weights and was started after the holdout build; the weights may differ from those of the holdout build. A and B here are matched with each other, not provably with the holdout.')
w('* **Analyst read is not blind** (the reader had the bank\'s expected answers), so the 24 of 36 answerable questions are an analyst judgment; S_elig depends on it. The grounding record is frozen before any build (`grounding_check.json`).')
w('* One corpus draw, 36 questions, three repeats per cell at temperature 0 (serving nondeterminism): an interval, not a demonstration. Judge servers were used request-only (at most three concurrent requests); nothing was installed or changed on them.')
w('* The verbatim check is a string test: it substitutes for no human evidence label and says nothing about whether a verbatim span answers the question.')
w('* Not done: the full-view condition (budget and window), a second natural corpus, a natural-document bank written independently of the schema, human labels on the natural cells.\n')

w('## 8. Files\n')
w('`PLAN.md` (committed before any build or call, with amendments 27.A1 and 27.A2), `SOURCES.md`, `GROUNDING.md`, `grounding_check.json`, `corpus/` (fetched files with checksums, cleaned text, `natural_corpus.json`), `corpus_stats.json`, `variants/{A,B}/`, `inputs/` (subgraph texts and manifest), `jobs_natural.jsonl`, `raw/` (per-call records), `results.json`, `analyze_natural.py`, `make_report.py`, `REPORT.md`. Re-run the analysis: `python3 analyze_natural.py` (reads `raw/` and the frozen inputs), then `python3 make_report.py`.\n')
open(os.path.join(D, 'REPORT.md'), 'w').write('\n'.join(out))
print('wrote REPORT.md', len('\n'.join(out)), 'chars')
