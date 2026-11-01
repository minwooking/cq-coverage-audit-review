"""Table bodies of the review-9 verbatim-span check, written from results.json (AI-generated; review before reuse).

Usage:  python3 make_tables.py           print the five table bodies (Appendix Table A8 and the Section S27 tables)
        python3 make_tables.py --check   exit 1 unless every row printed here occurs in ../../main.tex or ../../supplement.tex

Rounding rules (no double rounding):
  * counts-based rates (k/n)            -> exact k/n, half-up
  * A->B contrasts and their intervals  -> stored 4-dp lattice value snapped to the exact k/n (n = paired questions)
  * other interval endpoints (percent)  -> stored 4-dp value x 100, half-up (ties are listed and cross-checked)
"""
import json
import sys
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPER = HERE.parents[1]
d = json.load(open(HERE / 'results.json'))
TIES = []
OFF = []


def q(dec, dp):
    return dec.quantize(Decimal(1).scaleb(-dp), rounding=ROUND_HALF_UP)


def lat(v, n):
    k = round(v * n)
    if abs(v - k / n) > 6e-5:  # an interpolated BCa endpoint: not a lattice point, use the stored 4-dp value
        OFF.append((v, n))
        return Decimal(repr(v))
    return Decimal(k) / Decimal(n)


def sgn(dec, dp=3):
    x = q(dec, dp)
    return ('-' if x < 0 else '+') + str(abs(x))


def ab(v, n, dp=3):
    return sgn(lat(v, n), dp)


def cab(e, c, n):
    return '$%s$ $[%s,%s]$' % (ab(e, n), ab(c[0], n), ab(c[1], n))


def P(x, dp=1):
    dec = Decimal(repr(x)) * 100
    scaled = dec * 10 ** dp
    if scaled - scaled.to_integral_value(rounding='ROUND_FLOOR') == Decimal('0.5'):
        TIES.append(str(dec))
    return str(q(dec, dp))


def rate(k, n, dp=1):
    return str(q(Decimal(k) * 100 / Decimal(n), dp))


RUNS = [('gemini_primary', 'Holdout judge (Gemini), full view'),
        ('luna_full', '\\texttt{gpt-5.6-luna}, full view'),
        ('luna_subgraph', '\\texttt{gpt-5.6-luna}, subgraph'),
        ('gptoss_r1', '\\texttt{gpt-oss-20b}, repeat 1'), ('gptoss_r2', '\\texttt{gpt-oss-20b}, repeat 2'),
        ('gptoss_r3', '\\texttt{gpt-oss-20b}, repeat 3'),
        ('glm_r1', '\\texttt{GLM-4.7-Flash}, repeat 1'), ('glm_r2', '\\texttt{GLM-4.7-Flash}, repeat 2'),
        ('glm_r3', '\\texttt{GLM-4.7-Flash}, repeat 3')]


def lab(s, l):
    L = s['labels'][l]
    t = L['table_2x2_credited_cells']
    return L['events'], t['events_fail'], L['supported_credited'], t['supported_credited_fail'], L


def nq(a):
    return a['J']['n_paired_questions']


def appendix_table():
    o = []
    for r, name in RUNS:
        s = d['runs'][r]['strict']
        a = lab(s, 'AH')
        b = lab(s, 'second_rater')
        A = s['A_to_B']
        n = nq(A)
        o.append('%s & $%d$ & $%d$ & $%d/%d$ & $%d/%d$ & $%d/%d$ & $%d/%d$ & $%s$ & $%s$ \\\\' % (
            name, s['credited_J_ge2'], s['credited_verbatim'], a[1], a[0], b[1], b[0], a[3], a[2], b[3], b[2],
            ab(A['J']['est'], n), ab(A['Jstar_withdraw_to_min(J,1)']['est'], n)))
    return '\n'.join(o)


def s_primary():
    s = d['runs']['gemini_primary']['strict']
    A = s['labels']['AH']
    S2 = s['labels']['second_rater']
    o = []

    def row(label, fa, fs):
        o.append('%s & %s & %s \\\\' % (label, fa, fs))
    row('Credited cells ($J\\ge2$)', '$%d$' % s['credited_J_ge2'], '$%d$' % s['credited_J_ge2'])
    row('Credits with a verbatim span', '$%d$' % s['credited_verbatim'], '$%d$' % s['credited_verbatim'])
    row('Unsupported-credit events ($J\\ge2$, $S=0$)',
        '$%d$ in $%d$ clusters' % (A['events'], A['recall_cluster_level']['clusters_with_event']),
        '$%d$ in $%d$ clusters' % (S2['events'], S2['recall_cluster_level']['clusters_with_event']))

    def rec(L):
        r = L['recall_events_failing']
        rc = L['recall_cluster_level']
        return '$%d/%d$; Wilson $[%s,%s]$, clusters $%d/%d$, exact $[%s,%s]$' % (
            r['k'], r['n'], P(r['wilson95_cell_level'][0]), P(r['wilson95_cell_level'][1]),
            rc['of_which_with_a_failing_event'], rc['clusters_with_event'],
            P(rc['clopper_pearson95'][0]), P(rc['clopper_pearson95'][1]))
    row('Events with a non-verbatim span (caught; intervals in \\%)', rec(A), rec(S2))

    def ff(L):
        f = L['false_flag_supported_credited_failing']
        return '$%d/%d$ $=%s\\%%$, BCa $[%s,%s]$' % (f['k'], f['n'], rate(f['k'], f['n']),
                                                     P(f['cluster_bca95']['ci95'][0]), P(f['cluster_bca95']['ci95'][1]))
    row('Supported credits with a non-verbatim span (flagged)', ff(A), ff(S2))

    def pr(L):
        p = L['precision_flagged_that_are_events']
        b = L['base_rate_event_among_credited']
        return '$%d/%d$ (base rate $%d/%d$)' % (p['k'], p['n'], b['k'], b['n'])
    row('Flagged credits that are events', pr(A), pr(S2))

    def ph(L):
        return '$%s$ $[%s,%s]$ $\\to$ $%s$ $[%s,%s]$' % (
            rate(L['events'], 188), P(L['pi_hat_raw']['ci95'][0]), P(L['pi_hat_raw']['ci95'][1]),
            rate(L['pi_events_after'], 188), P(L['pi_hat_after_withdrawal']['ci95'][0]), P(L['pi_hat_after_withdrawal']['ci95'][1]))
    row('$\\hat\\pi$ (\\%), raw $\\to$ after withdrawal', ph(A), ph(S2))

    def abl(L):
        a = L['A_to_B']
        return '%s $\\to$ %s' % (cab(a['L1star']['est'], a['L1star']['ci95'], 23),
                                 cab(a['L1star_after_check']['est'], a['L1star_after_check']['ci95'], 23))
    row('$A\\!\\to\\!B$ on $L_1^{\\ast}$, raw $\\to$ with the check', abl(A), abl(S2))
    return '\n'.join(o)


def s_others():
    o = []
    for r, name in RUNS:
        s = d['runs'][r]['strict']
        row = [name, '$%d$' % s['n_cells'], '$%d$' % s['credited_J_ge2'], '$%d$' % s['credited_verbatim']]
        for l in ('AH', 'second_rater'):
            ev, k, sup, fl, L = lab(s, l)
            row += ['$%d/%d$' % (k, ev), '$%d/%d$' % (fl, sup),
                    '$%s\\to%s$' % (rate(L['events'], s['n_cells']), rate(L['pi_events_after'], s['n_cells']))]
        o.append(' & '.join(row) + ' \\\\')
    return '\n'.join(o)


def s_dwell():
    w = d['dwell_AH_vs_second_rater']
    o = []

    def line(label, blk):
        u = blk['under_20s']
        v = blk['at_or_over_20s']
        rd = blk['risk_difference_under_minus_over']
        lo, hi = blk['risk_difference_cluster_bootstrap_percentile95']
        return '%s & $%d/%d$ $=%s\\%%$ $[%s,%s]$ & $%d/%d$ $=%s\\%%$ $[%s,%s]$ & $%s$ $[%s,%s]$ & $%.2f$ \\\\' % (
            label, u['disagree'], u['n'], rate(u['disagree'], u['n']), P(u['wilson95'][0]), P(u['wilson95'][1]),
            v['disagree'], v['n'], rate(v['disagree'], v['n']), P(v['wilson95'][0]), P(v['wilson95'][1]),
            sgn(Decimal(repr(rd)) * 100, 1), sgn(Decimal(repr(lo)) * 100, 1), sgn(Decimal(repr(hi)) * 100, 1),
            blk['fisher_exact_p_cell_level_ignores_clustering'])
    o.append(line('$S$ differs, all $188$ cells', w['all_188_cells']['S_disagree']))
    o.append(line('$R$ differs exactly, all $188$ cells', w['all_188_cells']['R_disagree_exact']))
    o.append(line('$S$ differs, credited cells ($J\\ge2$)', w['credited_cells_J_ge2_only']['S_disagree']))
    o.append(line('$R$ differs exactly, credited cells', w['credited_cells_J_ge2_only']['R_disagree_exact']))
    return '\n'.join(o)


def s_ab_j():
    o = []
    for r, name in RUNS:
        s = d['runs'][r]['strict']
        a = s['A_to_B']
        n = nq(a)

        def c(x):
            return cab(x['est'], x['ci95'], n)
        o.append(' & '.join([name, '$%d$' % n, c(a['J']), c(a['Jstar_withdraw_to_min(J,1)']), c(a['Jstar_zero_sensitivity'])]) + ' \\\\')
    return '\n'.join(o)


def s_ab_l1():
    o = []
    for r, name in RUNS:
        s = d['runs'][r]['strict']
        n = nq(s['A_to_B'])
        ah = s['labels']['AH']['A_to_B']
        sr = s['labels']['second_rater']['A_to_B']

        def c(x):
            return cab(x['est'], x['ci95'], n)
        o.append(' & '.join([name, c(ah['L1star']), c(ah['L1star_after_check']), c(sr['L1star']), c(sr['L1star_after_check'])]) + ' \\\\')
    return '\n'.join(o)


TABLES = (appendix_table, s_primary, s_others, s_ab_j, s_ab_l1, s_dwell)


def check():
    """Every printed row must occur in the manuscript sources (appendix table in main.tex, the rest in supplement.tex)."""
    main = (PAPER / 'main.tex').read_text()
    supp = (PAPER / 'supplement.tex').read_text()
    bad = 0
    for f in TABLES:
        src = supp  # the appendix table moved to the supplement (Table S71) in the larger-bank round
        for row in f().split('\n'):
            if row not in src:
                bad += 1
                print('MISSING in %s: %s' % ('supplement.tex', row[:110]))
    print('rows checked, missing: %d' % bad)
    return bad


if __name__ == '__main__':
    if '--check' in sys.argv:
        sys.exit(1 if check() else 0)
    for f in TABLES:
        print('%%%%%% ' + f.__name__)
        print(f())
    print('%%% ties (value x100 with a .5 at the rounding digit):', TIES, 'off-lattice:', OFF, file=sys.stderr)
