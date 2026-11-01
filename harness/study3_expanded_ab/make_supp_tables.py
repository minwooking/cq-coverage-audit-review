#!/usr/bin/env python3
"""Writes the LaTeX tables of Supplementary Sections S32 and S33 (addenda 34 and 35) from the committed results files.
AI-written helper (review before reuse). No model call. Usage: make_supp_tables.py OUT.tex"""
import json, os, sys
H = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
A = json.load(open(os.path.join(H, 'study3_expanded_ab', 'results_all.json')))['judges']
S = json.load(open(os.path.join(H, 'study3_expanded_ab', 'results_sensitivity.json')))['judges']
B = json.load(open(os.path.join(H, 'study4_domains', 'results.json')))
JN = {'glm': '\\texttt{GLM-4.7-Flash}', 'gptoss': '\\texttt{gpt-oss-20b}'}


def f(x, d=3):
    return ('%+.*f' % (d, x))


def ci(d):
    return '$%s$ $[%s,%s]$' % (f(d['delta']), f(d['ci95'][0]), f(d['ci95'][1]))


def mde(d):
    return '%.2f' % d['prospective_mde']['holdout_J_1.343']


def fm(n):
    return '{:,}'.format(n).replace(',', '{,}')


def pv(d):
    return '%.3f / %.3f' % (d['sign_test']['p'], d['wilcoxon']['p'])


BANKS = [('holdout', 'Holdout (frozen)'), ('paraphrases', 'Paraphrases of the holdout'), ('v2_extras', 'Version-2 extras'),
         ('expansion', 'Expansion bank (frozen)'), ('dev_summary', 'Development, summary view'), ('dev_ext_subgraph', 'Development, subgraph view'),
         ('natural_docs', 'Natural Brick documentation'), ('second_domain_mfg', 'Second domain (aggregate)')]
POOLS = [('brick_frozen_only (holdout)', 'Brick holdout alone'), ('brick_frozen (holdout + expansion; expansion unreviewed)', 'Holdout and expansion'),
         ('brick_all (+ paraphrases, v2 extras; AI-draft)', 'All Brick banks')]
DOMS = [('development corpus (summary + ext subgraph, clustered by question)', 'Development corpus'), ('natural Brick documentation', 'Natural Brick documentation'),
        ('second domain (aggregate only)', 'Second domain (aggregate)')]
out = []
w = out.append


def tab(label, caption, cols, header, rows, size='footnotesize'):
    w('\\begin{table}[tbp]\n\\centering\n\\caption{%s}\n\\label{%s}\n\\%s\n\\setlength{\\tabcolsep}{2.5pt}\n\\begin{tabular}{@{}%s@{}}\n\\toprule\n%s \\\\\n\\midrule' % (caption, label, size, cols, header))
    for r in rows:
        w(r + ' \\\\')
    w('\\bottomrule\n\\end{tabular}\n\\end{table}\n')


# ---- Study 3 per bank
rows = []
for j in ('glm', 'gptoss'):
    for k, name in BANKS:
        d = A[j]['banks'][k]
        rows.append('%s & %s & $%d$ & $%.3f$ & $%.3f$ & %s & %s & %s' % (JN[j], name, d['n_clusters'], d['mean_J_A'], d['mean_J_B'], ci(d), mde(d), d['decision']))
tab('tab:s-s3-banks', 'Study 3 (addendum 34), $A\\!\\to\\!B$ judge-score contrast per bank (post hoc, exploratory; no human label; subgraph views; substitute judges, each analyzed on its own). $n$: clusters with a scored $A$ cell and a scored $B$ cell (question-clustered). $J(A)$, $J(B)$: mean judge score. $\\Delta$: mean $B-A$ in rubric points with a BCa $95\\%$ interval (seed $20260913$, $10{,}000$ resamples). MDE: minimum detectable effect at $\\sigma=1.343$. Decision: resolved (interval excludes $0$), equivalent (not resolved, the $90\\%$ interval lies inside $\\pm0.50$), otherwise unresolved. Frozen banks: holdout and expansion; the others are AI drafts.',
    'llccccrl', 'Judge & Bank & $n$ & $J(A)$ & $J(B)$ & $\\Delta$ [95\\% BCa] & MDE & Decision', rows)
# ---- pools and domains
rows = []
for j in ('glm', 'gptoss'):
    for k, name in POOLS:
        d = A[j]['pools'][k]
        rows.append('%s & %s & $%d$ & $%.3f$ & $%.3f$ & %s & %s & %s & %s' % (JN[j], name, d['n_clusters'], d['mean_J_A'], d['mean_J_B'], ci(d), mde(d), pv(d), d['decision']))
    for k, name in DOMS:
        d = A[j]['domains'][k]
        rows.append('%s & %s & $%d$ & $%.3f$ & $%.3f$ & %s & %s & %s & %s' % (JN[j], name, d['n_clusters'], d['mean_J_A'], d['mean_J_B'], ci(d), mde(d), pv(d), d['decision']))
tab('tab:s-s3-pools', 'Study 3, Brick banks pooled by source question (a paraphrase shares the cluster of its source question) and the contrast per domain (post hoc, exploratory; no human label). Columns as in Table~\\ref{tab:s-s3-banks}; $p$: exact sign test / Wilcoxon signed-rank test (zeros dropped). The development row combines the summary and subgraph views by question; the second-domain row is the manufacturing manual, whose variant $B$ is the build with the deduplication defect (Section~S7). \\emph{Holdout and expansion} and \\emph{all Brick banks} add AI-draft banks.',
    'llccccrcl', 'Judge & Row & $n$ & $J(A)$ & $J(B)$ & $\\Delta$ [95\\% BCa] & MDE & $p$ & Decision', rows)
# ---- sensitivity
rows = []
for j in ('glm', 'gptoss'):
    for k, name in BANKS:
        d = S[j]['banks'][k]; m = A[j]['banks'][k]
        rows.append('%s & %s & $%d$ & $%d$ / $%d$ & $%s$ & %s & %s $\\to$ %s' % (JN[j], name, d['n_clusters'], d['missing_A'], d['missing_B'], f(m['delta']), ci(d), m['decision'], d['decision']))
    for k, name in POOLS:
        d = S[j]['pools'][k.split(' (')[0] + (' (' + k.split(' (')[1].replace('; expansion unreviewed', '') if ' (' in k else '')]; m = A[j]['pools'][k]
        rows.append('%s & %s & $%d$ & --- & $%s$ & %s & %s $\\to$ %s' % (JN[j], name, d['n_clusters'], f(m['delta']), ci(d), m['decision'], d['decision']))
tab('tab:s-s3-floor', 'Study 3, floor sensitivity (addendum 34, amendment A2; post hoc; no human label). A missing $A$ or $B$ cell of an eligible cluster (no scored cell: ineligible by the paper\'s rule or without a view) is set to $J=0$, the judge\'s floor. Universe: all eligible clusters of the bank ($70$ for the expansion bank). Missing $A$ / $B$: cells missing of the universe. Main $\\Delta$: the analysis of Table~\\ref{tab:s-s3-banks}. Sensitivity $\\Delta$: with the floor, BCa $95\\%$. Decision: main $\\to$ sensitivity. The floor is an assumption and favors the variant whose graph holds more matching content.',
    'llcccll', 'Judge & Bank & $n$ & Missing $A$ / $B$ & Main $\\Delta$ & Sensitivity $\\Delta$ [95\\% BCa] & Decision', rows)
open(sys.argv[1] + '.s3', 'w').write('\n'.join(out))
del out[:]
# ---- Study 4
rows = []
for dm, name in (('dcat', 'DCAT 3'), ('ssn', 'SOSA/SSN'), ('prov', 'PROV')):
    for j in ('glm', 'gptoss'):
        d = B['domains'][dm][j]['mean_of_repeats']; e = B['domains'][dm][j]
        rows.append('%s & %s & $%d$ & $%.3f$ & $%.3f$ & %s & %s & %s & %s' % (name, JN[j], d['n_clusters'], d['mean_J_A'], d['mean_J_B'], ci(d), mde(d), pv(d), d['decision']))
for j in ('glm', 'gptoss'):
    d = B['pooled'][j]['mean_of_repeats']
    rows.append('Pooled & %s & $%d$ & --- & --- & %s & %s & %s & %s' % (JN[j], d['n_clusters'], ci(d), mde(d), pv(d), d['decision']))
tab('tab:s-s4-results', 'Study 4 (addendum 35), $A\\!\\to\\!B$ judge-score contrast on three W3C domains (post hoc, exploratory; no human label; AI-draft banks; question-only subgraph views). $n$: questions eligible in $A$ and $B$ (PROV: one of the $38$ lacks a valid score). Columns as in Table~\\ref{tab:s-s3-banks}; $p$: exact sign test / Wilcoxon test. The pooled rows cluster by question within domain.',
    'llccccrcl', 'Domain & Judge & $n$ & $J(A)$ & $J(B)$ & $\\Delta$ [95\\% BCa] & MDE & $p$ & Decision', rows)
rows = []
for dm, name in (('dcat', 'DCAT 3'), ('ssn', 'SOSA/SSN'), ('prov', 'PROV')):
    b = B['builds'][dm]; g = B['domains'][dm]['glm']
    rows.append('%s & $%d$ & $%s$ & $%s$ & $%s$ & $%s$ & $%d$ & $%d$ & \\texttt{%s}' % (name, g['n_questions'], fm(b['atomic_chunks']), fm(b['corpus_chars']), fm(b['triples']['A']), fm(b['triples']['B']), b['build_a_sections_skipped'], b['llm_failures'], g['bank_sha256'][:12]))
tab('tab:s-s4-builds', 'Study 4, corpora, builds and frozen banks. Chunks and characters: the cleaned documentation corpus. Triples: of the baseline $A$ and the base build $B$. Skipped: top-level sections the baseline command left out because its Turtle did not parse. Failed: extractor calls that failed. Bank: first $12$ characters of the SHA-256 of the frozen bank file (git tag \\texttt{access2026-study4-<domain>-bank-freeze}).',
    'lcccccccl', 'Domain & Questions & Chunks & Characters & Triples $A$ & Triples $B$ & Skipped & Failed & Bank', rows, 'footnotesize')
open(sys.argv[1] + '.s4', 'w').write('\n'.join(out))
