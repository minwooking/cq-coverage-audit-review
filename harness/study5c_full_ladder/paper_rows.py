#!/usr/bin/env python3
"""Addendum 36 amendments B and C: LaTeX rows of the manuscript (Table A9 size-ladder block, Supplementary Section S36)
from ../study5b_small_judges/results.json and ./results.json.

AI-written helper; review before reuse. No model call. Writes .tex fragments to paper_tables/ and cross-checks every
delta and 95% interval against the two tables.tex files (two-decimal intervals). Exit status 1 on any mismatch.

The +-0.30 reading is the post hoc rule of addendum 34 amendment A3: an equivalent row (90% BCa inside +-0.50)
becomes unresolved where its 90% BCa interval is not inside (-0.30, +0.30); resolved and unresolved rows stay.

Usage: python3 -I paper_rows.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
C = json.load(open(os.path.join(HERE, 'results.json')))
B = json.load(open(os.path.join(HERE, '..', 'study5b_small_judges', 'results.json')))
OUT = os.path.join(HERE, 'paper_tables')
os.makedirs(OUT, exist_ok=True)
ERRORS = []

CN = {'glm': r'\texttt{GLM-4.7-Flash}', 'gptoss': r'\texttt{gpt-oss-20b}', 'q38': r'\texttt{Qwen3.8-Flash-Next}',
      'q80': r'\texttt{Qwen3-Next-80B-A3B}$^{\ddagger}$'}
CP = {'glm': 'GLM-4.7-Flash', 'gptoss': 'gpt-oss-20b', 'q38': 'Qwen3.8-Flash-Next', 'q80': "Qwen3-Next-80B-A3B (extractor's model id)"}
BN = {'q38_27b': r'\texttt{Qwen3.8-27B}', 'q35_9b': r'\texttt{Qwen3.5-9B}', 'q35_4b': r'\texttt{Qwen3.5-4B}'}
BP = {'q38_27b': 'Qwen3.8-27B', 'q35_9b': 'Qwen3.5-9B', 'q35_4b': 'Qwen3.5-4B'}
SCOPE = {'brick_pool': 'Brick banks pooled', 'holdout': 'Holdout bank', 'paraphrases': 'Paraphrases',
         'v2_extras': 'Version-2 extras', 'expansion': 'Expansion bank', 'dcat': 'DCAT 3', 'ssn': 'SOSA/SSN',
         'prov': 'PROV', 'new_domains_pooled': 'Three domains pooled'}
SCOPE_TEX = {'brick pool': 'brick_pool', 'new domains pooled': 'new_domains_pooled', 'dcat': 'dcat', 'ssn': 'ssn', 'prov': 'prov',
             'holdout': 'holdout', 'paraphrases': 'paraphrases', 'v2 extras': 'v2_extras', 'expansion': 'expansion'}
ARROW = {'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D', 'E': 'E', 'F': 'F'}


def f3(x):
    return f'{x:+.3f}'


def dec50(c):
    v = c['verdict']
    if v.startswith('resolved'):
        return 'resolved'
    return {'equivalent': 'equivalent', 'unresolved': 'unresolved', 'underpowered': 'underpowered'}[v]


def dec30(c):
    v = dec50(c)
    if v == 'equivalent':
        lo, hi = c['ci90']
        if not (lo > -0.30 and hi < 0.30):
            return 'unresolved'
    return v


def cell(c):
    return (f"${f3(c['delta'])}$ $[{f3(c['ci95'][0])},{f3(c['ci95'][1])}]$", dec50(c), dec30(c))


def arrow(k):
    a, b = k.split('->')
    return f'${a}\\!\\to\\!{b}$'


# ---- cross-check against both tables.tex ----------------------------------------------------------------------
pat = re.compile(r'^(?P<j>[^&%\n]+?) & (?P<k>[A-F](?:->|\$\\to\$)[A-F]) & (?P<s>[a-z0-9 ]+) & (?P<n>\d+) & \$(?P<d>[+-]\d\.\d+)\$ \[\$(?P<lo>[+-]\d\.\d+)\$, \$(?P<hi>[+-]\d\.\d+)\$\] & (?P<dec>[a-zA-Z ]+) \\\\$', re.M)
nchk = 0
for fn, per, names in (('study5b_small_judges', B['per_judge'], {v: k for k, v in BP.items()}),
                       ('study5c_full_ladder', C['per_judge'], {v: k for k, v in CP.items()})):
    T = open(os.path.join(HERE, '..', fn, 'tables.tex')).read().replace('$\\to$', '->')
    for m in pat.finditer(T):
        j = names[m['j']]
        c = per[j]['contrasts'][m['k'] + '|' + SCOPE_TEX[m['s']]]
        ok = (int(m['n']) == c['n_clusters'] and abs(float(m['d']) - c['delta']) < 5.1e-4 and
              abs(float(m['lo']) - c['ci95'][0]) < 5.1e-3 and abs(float(m['hi']) - c['ci95'][1]) < 5.1e-3 and
              m['dec'].lower().split(' ')[0] == c['verdict'].lower().split('_')[0])
        nchk += 1
        if not ok:
            ERRORS.append(('tables.tex mismatch', m.group(0), c['delta'], c['ci95'], c['verdict']))
print(f'cross-checked {nchk} rows of the two tables.tex files against results.json')


def write(name, s):
    open(os.path.join(OUT, name), 'w').write(s)


# ---- Table A9: size ladder block -------------------------------------------------------------------------------
def a9_block():
    L = [r'\midrule',
         r'5B & \multicolumn{2}{l}{\emph{same vendor, size ladder (addendum 36B)}} & \multicolumn{3}{c}{$A\!\to\!B$, Brick banks pooled ($n=58$)} & \multicolumn{3}{c}{$A\!\to\!B$, three domains pooled ($n=99$)} & \\',
         r'\cmidrule(lr){4-6}\cmidrule(lr){7-9}']
    for j in ['q38_27b', 'q35_9b', 'q35_4b']:
        c1, c2 = B['per_judge'][j]['contrasts']['A->B|brick_pool'], B['per_judge'][j]['contrasts']['A->B|new_domains_pooled']
        assert c1['n_clusters'] == 58 and c2['n_clusters'] == (98 if j == 'q35_4b' else 99)
        a, b = cell(c1), cell(c2)
        L.append(f" & {BN[j]}$^{{\\S}}$ & & {a[0]} & {a[1]} & {a[2]} & {b[0]} & {b[1]} & {b[2]} & --- \\\\")
    return '\n'.join(L) + '\n'


# ---- Supplement: size ladder, all scopes ------------------------------------------------------------------------
def size_rows():
    L = []
    for j in ['q38_27b', 'q35_9b', 'q35_4b']:
        for s in ['holdout', 'paraphrases', 'v2_extras', 'expansion', 'brick_pool', 'dcat', 'ssn', 'prov', 'new_domains_pooled']:
            c = B['per_judge'][j]['contrasts']['A->B|' + s]
            a = cell(c)
            L.append(f"{BN[j]} & {SCOPE[s]} & ${c['n_clusters']}$ & {a[0]} & {a[1]} & {a[2]} \\\\")
        L.append(r'\midrule')
    L.pop()
    return '\n'.join(L) + '\n'


def size_qwk_rows():
    P = {'glm': 'GLM-4.7-Flash', 'gptoss': 'gpt-oss-20b', 'q38': 'Qwen3.8-Flash-Next', 'q80': 'Qwen3-Next-80B-A3B', 'gw': 'gpt-5.6-luna'}
    q = B['agreement_qwk']['A_B_cells']
    L = []
    for pair, v in q.items():
        a, b = pair.split('~')
        L.append(f"{P.get(a, BP.get(a))} -- {P.get(b, BP.get(b))} & ${v['n_cells']}$ & ${v['qwk']:.3f}$ & ${v['exact_agreement']:.3f}$ \\\\")
    return '\n'.join(L) + '\n'


# ---- Supplement: stage ladder -----------------------------------------------------------------------------------
ORDER = ['glm', 'gptoss', 'q38', 'q80']
DOM = [('dcat', 'DCAT 3'), ('ssn', 'SOSA/SSN'), ('prov', 'PROV'), ('new_domains_pooled', 'Three domains pooled')]


def ladder_rows():
    L = []
    for j in ORDER:
        lad = C['per_judge'][j]['ladder']
        for s, nm in DOM:
            L.append(f"{CN[j]} & {nm} & " + ' & '.join(f"${lad[s][v]['mean_J']:.2f}$ ({lad[s][v]['n_cells']})" for v in 'ABCDEF') + r' \\')
        L.append(r'\midrule')
    L.pop()
    return '\n'.join(L) + '\n'


def stage_rows(keys, scopes):
    L = []
    for j in ORDER:
        for k in keys:
            for s, nm in scopes:
                c = C['per_judge'][j]['contrasts'][f'{k}|{s}']
                a = cell(c)
                L.append(f"{CN[j]} & {arrow(k)} & {nm} & ${c['n_clusters']}$ & {a[0]} & {a[1]} & {a[2]} \\\\")
        L.append(r'\midrule')
    L.pop()
    return '\n'.join(L) + '\n'


def monotone_rows():
    L = []
    for j in ORDER:
        m = C['per_judge'][j]['monotone_B_to_F']['new_domains_pooled']['all_eligible_cells']
        lad = C['per_judge'][j]['ladder']['new_domains_pooled']
        L.append(f"{CN[j]} & " + ' & '.join(f"${lad[v]['mean_J']:.2f}$" for v in 'BCDEF') + f" & ${m['steps_nondecreasing']}$ of ${m['steps']}$ & {'yes' if m['monotone_nondecreasing'] else 'no'} \\\\")
    return '\n'.join(L) + '\n'


# consistency of the monotone claim and of the two single-step exceptions at +-0.50
for j in ['glm', 'gptoss', 'q38', 'q80']:
    for dm in C['per_judge'][j]['monotone_B_to_F'].values():
        if dm['all_eligible_cells']['monotone_nondecreasing']:
            ERRORS.append(('monotone', j))
exc = []
for j in ['glm', 'gptoss', 'q38']:
    for k in ['B->C', 'C->D', 'D->E', 'E->F']:
        c = C['per_judge'][j]['contrasts'][k + '|new_domains_pooled']
        if dec50(c) != 'equivalent':
            exc.append((j, k, round(c['delta'], 3)))
print('pooled adjacent exceptions among independent judges:', exc)
if exc != [('glm', 'B->C', -0.078), ('q38', 'D->E', -0.093)]:
    ERRORS.append(('exceptions differ from the brief', exc))

write('a9_size_rows.tex', a9_block())
write('supp_size_ab_rows.tex', size_rows())
write('supp_size_qwk_rows.tex', size_qwk_rows())
write('supp_ladder_means_rows.tex', ladder_rows())
write('supp_stage_monotone_rows.tex', monotone_rows())
write('supp_stage_adj_pooled_rows.tex', stage_rows(['B->C', 'C->D', 'D->E', 'E->F'], DOM[3:]))
write('supp_stage_adj_domain_rows.tex', stage_rows(['B->C', 'C->D', 'D->E', 'E->F'], DOM[:3]))
write('supp_stage_vsA_rows.tex', stage_rows(['A->C', 'A->D', 'A->E', 'A->F'], DOM[3:]))
if ERRORS:
    for e in ERRORS:
        print('MISMATCH', e)
    sys.exit(1)
print('ok')
