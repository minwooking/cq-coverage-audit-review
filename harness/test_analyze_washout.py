"""Tests for analyze_washout.py (PREREG sec.12.3-12.4 statistics).

ALL DATA HERE IS SYNTHETIC and exists only to exercise the statistics.  None of it is a study
result, none of it comes from a real label file, and none of it may be quoted as one.

Where a value is checked against a hand computation the arithmetic is in the comment next to it; where
it is checked against an oracle the oracle is written here independently of the module (exact
fractions, a numeric delta-method gradient, a re-derivation of the bootstrap draws, scipy).
"""
from __future__ import annotations

import csv
import dataclasses
import datetime
import hashlib
import json
import os
import random
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analyze_holdout as ah  # noqa: E402
import analyze_washout as aw  # noqa: E402

SMALL_B = 200
SEED = 20260913


# ---------------------------------------------------------------------------
# independent oracles
# ---------------------------------------------------------------------------
def frac_qwk(x, y, w=None, k=4) -> Fraction:
    """QWK in exact arithmetic: 1 - O/E with M the table of summed weights."""
    w = [1] * len(x) if w is None else w
    total = sum(Fraction(v) for v in w)
    m = [[Fraction(0)] * k for _ in range(k)]
    for xi, yi, wi in zip(x, y, w):
        m[xi][yi] += Fraction(wi)
    obs = sum((i - j) ** 2 * m[i][j] for i in range(k) for j in range(k))
    rows = [sum(m[i]) for i in range(k)]
    cols = [sum(m[i][j] for i in range(k)) for j in range(k)]
    exp = sum((i - j) ** 2 * rows[i] * cols[j] for i in range(k) for j in range(k)) / total
    return 1 - obs / exp


def columns(n11, n10, n01, n00):
    """Two 0/1 columns with the 2x2 counts: rows = first column (AH), columns = second."""
    ref = [1] * n11 + [1] * n10 + [0] * n01 + [0] * n00
    cand = [1] * n11 + [0] * n10 + [1] * n01 + [0] * n00
    return ref, cand


def delta_method_se(table):
    """SE of the quadratic-weighted kappa by the multinomial delta method with a numeric gradient."""
    t = np.asarray(table, float)
    n = t.sum()
    p = t / n
    k = len(t)
    lv = np.arange(k)
    d = (lv[:, None] - lv[None, :]) ** 2

    def kappa(pm):
        pm = pm / pm.sum()
        return 1 - (d * pm).sum() / (d * np.outer(pm.sum(1), pm.sum(0))).sum()

    g = np.zeros((k, k))
    h = 1e-6
    for i in range(k):
        for j in range(k):
            up, dn = p.copy(), p.copy()
            up[i, j] += h
            dn[i, j] -= h
            g[i, j] = (kappa(up) - kappa(dn)) / (2 * h)
    return float(np.sqrt(((p * g ** 2).sum() - (p * g).sum() ** 2) / n))


def textbook_unweighted_kappa_se(table):
    """Fleiss-Cohen-Everitt (1969) variance of the UNWEIGHTED kappa, as printed in the textbooks."""
    t = np.asarray(table, float)
    n = t.sum()
    p = t / n
    pr, pc = p.sum(1), p.sum(0)
    po, pe = np.trace(p), (pr * pc).sum()
    kap = (po - pe) / (1 - pe)
    k = len(t)
    a = sum(p[i, i] * (1 - (pr[i] + pc[i]) * (1 - kap)) ** 2 for i in range(k))
    b = (1 - kap) ** 2 * sum(p[i, j] * (pc[i] + pr[j]) ** 2 for i in range(k) for j in range(k) if i != j)
    c = (kap - pe * (1 - kap)) ** 2
    return float(np.sqrt((a + b - c) / (n * (1 - pe) ** 2)))


def independent_draws(n_clusters, seed, B):
    """The bootstrap draws of the registered helper for ONE stratum: one rng.integers call per resample."""
    rng = np.random.default_rng(seed)
    return [rng.integers(0, n_clusters, n_clusters) for _ in range(B)]


def exact_qwk_or_none(pairs):
    """QWK of (x, y) pairs in exact arithmetic; None where E = 0."""
    try:
        return float(frac_qwk([p[0] for p in pairs], [p[1] for p in pairs]))
    except ZeroDivisionError:
        return None


def oracle_bca(theta, boot, jack=None, alpha=0.05):
    """The BCa interval re-derived from its definition: z0 from the share of replicates below theta (replicates
    within 1e-12 of theta count half: the mid-rank rule), the acceleration from the leave-one-out values (0 when
    ``jack`` is None), then the adjusted percentiles of the replicates (linear interpolation)."""
    boot = np.asarray(boot, float)
    n = len(boot)
    tol = 1e-12 * max(1.0, abs(theta))
    prop = (np.sum(boot < theta - tol) + np.sum(boot <= theta + tol)) / (2.0 * n)
    z0 = stats.norm.ppf(min(max(prop, 1.0 / n), 1.0 - 1.0 / n))
    acc = 0.0
    if jack is not None:
        d = np.mean(jack) - np.asarray(jack, float)
        den = 6.0 * np.sum(d ** 2) ** 1.5
        acc = 0.0 if den == 0 else float(np.sum(d ** 3) / den)
    z = stats.norm.ppf([alpha / 2, 1 - alpha / 2])
    adj = stats.norm.cdf(z0 + (z0 + z) / (1 - acc * (z0 + z)))
    return tuple(float(np.percentile(boot, 100 * a)) for a in adj)


def oracle_dropping_interval(clusters, stat, seed, B):
    """The sec.12.4 policy re-derived: the registered draws (default_rng(seed), one integers call per resample over
    the sorted clusters); a resample on which ``stat`` is undefined (None) is dropped and counted; the
    leave-one-cluster-out jackknife on the full data; an undefined jackknife sample sets the acceleration to 0.
    ``clusters``: one list of items per cluster in sorted cluster order; ``stat``: list of items -> float | None."""
    n = len(clusters)
    theta = stat([x for cl in clusters for x in cl])
    values, n_undef = [], 0
    for idx in independent_draws(n, seed, B):
        v = stat([x for i in idx for x in clusters[int(i)]])
        if v is None:
            n_undef += 1
        else:
            values.append(v)
    jack = [stat([x for j, cl in enumerate(clusters) if j != k for x in cl]) for k in range(n)]
    n_jack_undef = sum(v is None for v in jack)
    lo, hi = oracle_bca(theta, values, None if n_jack_undef else jack)
    return {"theta": theta, "lo": lo, "hi": hi, "n_undefined": n_undef, "n_jack_undefined": n_jack_undef}


# ---------------------------------------------------------------------------
# small builders
# ---------------------------------------------------------------------------
def wcell(cid, cluster, stratum, w, x, y, a0=1, a1=1):
    return aw.WashoutCell(cell_id=cid, source_cell_id="src-" + cid, cluster_id=cluster, stratum=stratum,
                          pi=1.0 / w, w=float(w), ah_a=a0, ah_l1=x, wo_a=a1, wo_l1=y)


# x = AH rater_L1, y = washout rater_L1; the ten pairs of the hand example (QWK 94/109 unweighted).
HAND_X = [0, 1, 2, 3, 3, 2, 1, 0, 2, 3]
HAND_Y = [0, 1, 2, 2, 3, 3, 1, 1, 2, 3]
HAND_W = [1, 1, 1, 2, 1, 1, 1, 1, 1, 1]          # the fourth cell counts double
HAND_CL = ["c1", "c1", "c2", "c2", "c3", "c3", "c4", "c4", "c5", "c5"]
HAND_STRATUM = ["proportional"] * 6 + ["enriched"] * 4


def hand_cells():
    return [wcell(f"h{i}", HAND_CL[i], HAND_STRATUM[i], HAND_W[i], HAND_X[i], HAND_Y[i]) for i in range(10)]


def control(i, kind, a, reason=None):
    return aw.ControlCell(cell_id=f"w-{kind[:3]}-{i:02d}", source_cell_id=f"{kind[:3]}-{i:02d}", kind=kind,
                          excluded_reason=reason, a=a)


def ablated_controls(n_a0=24, n=24, excluded=0, unlabeled=0):
    """n ablated controls: the first ``excluded`` not presented, then ``unlabeled`` without an A, the
    rest labeled, ``n_a0`` of those labeled A=0 and the others A=1."""
    out = []
    k = 0
    for i in range(n):
        if i < excluded:
            out.append(control(i, "ablated_control", None, "artifact_digest_mismatch"))
        elif i < excluded + unlabeled:
            out.append(control(i, "ablated_control", None))
        else:
            out.append(control(i, "ablated_control", 0 if k < n_a0 else 1))
            k += 1
    return out


def preserved_controls(n_a1=11, n=12):
    return [control(i, "preserved_control", 1 if i < n_a1 else 0) for i in range(n)]


# ---------------------------------------------------------------------------
# 1. the module reuses the registered analyzer and documents its inputs
# ---------------------------------------------------------------------------
def test_registered_helpers_are_imported_not_copied():
    assert aw.cluster_bootstrap_stat is ah.cluster_bootstrap_stat
    assert aw._bca_interval is ah._bca_interval          # the mid-rank z0 lives inside it
    assert aw.silent_over_credit_rate is ah.silent_over_credit_rate
    assert aw.silent_over_credit is ah.silent_over_credit
    assert aw.clopper_pearson_upper is ah.clopper_pearson_upper
    assert aw.load_label_csv is ah.load_label_csv
    assert aw.load_label_audit is ah.load_label_audit
    assert aw.load_cells is ah.load_cells
    assert aw._refuse_outputs_that_are_inputs is ah._refuse_outputs_that_are_inputs
    assert aw.REGISTERED_SEED == ah.REGISTERED_SEED == 20260913
    assert aw.BOOTSTRAP_RESAMPLES == ah.BOOTSTRAP_RESAMPLES == 10_000
    assert aw.DEFAULT_BCA_TIES == ah.DEFAULT_BCA_TIES == "midrank"


def test_module_docstring_defines_the_input_schemas():
    doc = aw.__doc__
    for token in ("INPUT SCHEMAS", "--design", "source_cell_id", "inclusion_prob", "stratum",
                  "excluded_reason", "--ah-labels", "--washout-labels", "--audit", "ai_used",
                  "AI_USE", "--session-log", "--sample-list", "--id-map", "--exclude-controls", "--cells",
                  "OUTPUT AND GUARDS", "default_rng(20260913)", "E = 0"):
        assert token in doc, token


def test_module_docstring_is_current_about_the_registration_and_the_design_columns():
    doc = aw.__doc__
    for stale in ("not yet in PREREG", "not yet registered", "not recorded per cell", "self-reported per session"):
        assert stale not in doc, stale
    for token in ("sec.12.3", "sec.12.4", "sec.13.1", "exploratory"):
        assert token in doc, token
    # the design columns that are READ, and the builder keys that are not (``w`` is not among the columns read,
    # ``excluded_reason`` is; ``category_stratum`` is not read)
    read_part = doc.split("Columns read, and only these:")[1].split("The sealed ``washout_mapping.json``")[0]
    for col in ("cell_id", "source_cell_id", "cell_kind", "stratum", "inclusion_prob", "excluded_reason"):
        assert col in read_part, col
    for unread in ("category_stratum", "``w``", "position", "view_ref", "selection"):
        assert unread not in read_part, unread
    mapping_part = doc.split("The sealed ``washout_mapping.json``")[1].split("``--ah-labels``")[0]
    for unread in ("``w``", "``position``", "``selection``", "``category_stratum``", "``view_ref``",
                   "``cq_text_source``", "``cq_shown_differs_from_judge_input``"):
        assert unread in mapping_part, unread
    assert "``excluded_reason``, is" in mapping_part


def test_module_docstring_describes_the_14_column_packet_sheets():
    doc = " ".join(aw.__doc__.split())                      # the line breaks do not matter
    assert "it carries the 13th column" not in doc and "also carries the 13th column" not in doc
    for token in ("has 12 columns (the AH layout) or, in ``--packet`` mode, 14: the 13th is ``ai_used``",
                  "the 14th ``dwell_ms`` (a running total in ms over the row's saves, not read here: the audit holds every save)",
                  "The first packet layout, 13 columns without ``dwell_ms``, is read alike; columns are found by name",
                  "``--packet`` mode it has 14 columns: the 13th is ``ai_used``",
                  "the 14th ``dwell_ms`` (a running total in ms, not read: the audit holds every save); the 13-column layout "
                  "without ``dwell_ms`` is read alike"):
        assert token in doc, token


def test_stale_ai_recording_claims_are_gone_from_the_source():
    source = Path(aw.__file__).read_text(encoding="utf-8")
    for stale in ("not recorded per cell", "self-reported per session", "not yet in PREREG",
                  "not stratified by AI use", "counts-only block"):
        assert stale not in source, stale


def test_design_loader_reads_inclusion_prob_and_ignores_the_builders_w_and_category_stratum(tmp_path):
    rows = [design_row("a", "sa", stratum="proportional", prob="0.32"),
            design_row("b", "sb", stratum="enriched", prob="0.6316")]
    plain = builder_style_mapping(rows)
    odd = builder_style_mapping(rows)
    for r in odd["rows"]:
        r["w"] = 999.0                                  # a weight the loader must not read
        r["category_stratum"] = "anything|J9"
        r["position"], r["selection"], r["view_ref"] = 7, "x", "views/x.html"
    (tmp_path / "a.json").write_text(json.dumps(plain))
    (tmp_path / "b.json").write_text(json.dumps(odd))
    assert aw.load_washout_design(tmp_path / "a.json") == aw.load_washout_design(tmp_path / "b.json")
    assert [r.inclusion_prob for r in aw.load_washout_design(tmp_path / "b.json")] == [0.32, 0.6316]


# ---------------------------------------------------------------------------
# 2. agreement statistics against hand computations
# ---------------------------------------------------------------------------
def test_binary_agreement_hand_values():
    # rows = AH, columns = second: n11=30 n10=6 n01=4 n00=10, n=50
    # raw = 40/50 = 4/5.  AH positive rate 36/50, second 34/50.
    # kappa: pe = .72*.68 + .28*.32 = .5792, (0.8-.5792)/(1-.5792) = 138/263.
    # AC1:   pi = (.72+.68)/2 = .7, pe = 2*.7*.3 = .42, (0.8-.42)/(1-.42) = 19/29.
    # PPA = 30/(30+6) = 5/6;  NPA = 10/(10+4) = 5/7.
    out = aw.binary_agreement(*columns(30, 6, 4, 10))
    assert out["raw_agreement"] == pytest.approx(4 / 5, abs=1e-15)
    assert out["cohen_kappa"] == pytest.approx(138 / 263, abs=1e-15)
    assert out["gwet_ac1"] == pytest.approx(19 / 29, abs=1e-15)
    assert out["ppa"] == pytest.approx(5 / 6, abs=1e-15)
    assert out["npa"] == pytest.approx(5 / 7, abs=1e-15)
    assert out["table"] == {"n11": 30.0, "n10": 6.0, "n01": 4.0, "n00": 10.0}


def test_ppa_npa_use_rows_equal_the_ah_column():
    ref, cand = columns(30, 6, 4, 10)
    straight = aw.binary_agreement(ref, cand)
    swapped = aw.binary_agreement(cand, ref)            # the second annotator as the comparison column
    # rows = candidate: PPA' = 30/(30+4) = 15/17, NPA' = 10/(10+6) = 5/8
    assert swapped["ppa"] == pytest.approx(15 / 17, abs=1e-15)
    assert swapped["npa"] == pytest.approx(5 / 8, abs=1e-15)
    assert straight["ppa"] != pytest.approx(swapped["ppa"])
    for symmetric in ("raw_agreement", "cohen_kappa", "gwet_ac1"):
        assert straight[symmetric] == pytest.approx(swapped[symmetric], abs=1e-15)


def test_gwet_ac1_uses_pe_equal_2_pi_one_minus_pi_and_resists_the_kappa_paradox():
    # n11=45 n10=5 n01=0 n00=0: AH positives 50/50, second 45/50, raw = .9.
    # kappa: pe = 1*.9 + 0 = .9 -> kappa = 0.   AC1: pi = (1+.9)/2 = .95, pe = 2*.95*.05 = .095,
    # (0.9-.095)/(1-.095) = 161/181.
    out = aw.binary_agreement(*columns(45, 5, 0, 0))
    assert out["cohen_kappa"] == pytest.approx(0.0, abs=1e-15)
    assert out["gwet_ac1"] == pytest.approx(161 / 181, abs=1e-15)
    assert out["ppa"] == pytest.approx(0.9)
    assert out["npa"] is None                            # the AH column has no negative


@pytest.mark.parametrize("counts,expect", [
    ((20, 0, 0, 0), dict(raw=1.0, kappa=None, ac1=1.0, ppa=1.0, npa=None)),   # all positive, both
    ((0, 0, 0, 20), dict(raw=1.0, kappa=None, ac1=1.0, ppa=None, npa=1.0)),   # all negative, both
    ((15, 5, 0, 0), dict(raw=0.75, kappa=0.0, ac1=0.68, ppa=0.75, npa=None)),  # AH constant positive
])
def test_binary_statistics_at_prevalence_extremes(counts, expect):
    # (15,5,0,0): pe = 1*.75 = .75 = po -> kappa 0; AC1: pi = (1+.75)/2 = .875, pe = .21875,
    # (.75-.21875)/(.78125) = .68
    out = aw.binary_agreement(*columns(*counts))
    assert out["raw_agreement"] == pytest.approx(expect["raw"])
    for key, name in (("kappa", "cohen_kappa"), ("ac1", "gwet_ac1"), ("ppa", "ppa"), ("npa", "npa")):
        if expect[key] is None:
            assert out[name] is None, name
        else:
            assert out[name] == pytest.approx(expect[key], abs=1e-12), name


def test_qwk_hand_values():
    # 10 pairs: three disagreements of squared distance 1,1,1 -> O = 3/10; marginals give E = 2.18;
    # QWK = 1 - 0.3/2.18 = 94/109
    assert aw.weighted_qwk(HAND_X, HAND_Y) == pytest.approx(94 / 109, abs=1e-14)
    assert frac_qwk(HAND_X, HAND_Y) == Fraction(94, 109)


def test_weighted_qwk_hand_value_equals_the_duplicated_cell():
    # a weight of 2 on the fourth pair is the same as listing it twice: 11 pairs, O = 4/11, E = 256/121,
    # QWK = 1 - (4/11)/(256/121) = 1 - 484/2816 = 53/64
    q = aw.weighted_qwk(HAND_X, HAND_Y, HAND_W)
    assert q == pytest.approx(53 / 64, abs=1e-14)
    dup = aw.weighted_qwk(HAND_X + [HAND_X[3]], HAND_Y + [HAND_Y[3]])
    assert q == pytest.approx(dup, abs=1e-14)
    assert frac_qwk(HAND_X, HAND_Y, HAND_W) == Fraction(53, 64)


def test_qwk_is_one_minus_o_over_e_of_the_unnormalised_weighted_table():
    # the pinned form: O = sum (j-k)^2 M_jk, E = sum (j-k)^2 M_j+ M_+k / M_++ on the table of summed weights
    rng = np.random.default_rng(3)
    x = rng.integers(0, 4, 60)
    y = np.clip(x + rng.integers(-1, 2, 60), 0, 3)
    w = rng.uniform(1.0, 6.0, 60)
    m = aw.confusion_table(x.tolist(), y.tolist(), w.tolist())
    lv = np.arange(4)
    d = (lv[:, None] - lv[None, :]) ** 2
    obs = (d * m).sum()
    exp = (d * np.outer(m.sum(1), m.sum(0))).sum() / m.sum()
    assert aw.qwk_from_table(m) == pytest.approx(1 - obs / exp, abs=1e-13)
    # scale free: no renormalisation of the weights changes the estimate
    assert aw.weighted_qwk(x.tolist(), y.tolist(), (w * 37.0).tolist()) == pytest.approx(
        aw.weighted_qwk(x.tolist(), y.tolist(), w.tolist()), abs=1e-13)


def test_qwk_with_unit_weights_is_the_registered_quantity():
    rng = np.random.default_rng(8)
    x = rng.integers(0, 4, 50).tolist()
    y = np.clip(np.array(x) + rng.integers(-1, 2, 50), 0, 3).tolist()
    assert aw.weighted_qwk(x, y) == pytest.approx(ah._qwk_from_values(x, y), abs=1e-13)
    assert aw.weighted_qwk(x, y) == pytest.approx(ah.quadratic_weighted_kappa(
        {str(i): v for i, v in enumerate(x)}, {str(i): v for i, v in enumerate(y)}), abs=1e-13)


def test_qwk_with_expected_disagreement_zero_is_undefined_not_one():
    # both raters use the single level 2: E = 0.  The registered helper maps this to 1.0; here it is None.
    assert aw.weighted_qwk([2, 2, 2], [2, 2, 2]) is None
    assert ah._qwk_from_values([2, 2, 2], [2, 2, 2]) == 1.0
    assert aw.qwk_from_table(np.zeros((4, 4))) is None
    # one rater constant, the other not: E > 0, defined
    assert aw.weighted_qwk([2, 2, 2, 2], [1, 2, 3, 2]) is not None


def test_qwk_when_all_raters_agree_and_use_several_levels_is_exactly_one():
    assert aw.weighted_qwk([0, 1, 2, 3, 3], [0, 1, 2, 3, 3]) == pytest.approx(1.0, abs=1e-15)


def test_confusion_table_rejects_bad_values_and_weights():
    for bad in ([4], [-1], [1.0], [True], ["1"]):
        with pytest.raises(ValueError):
            aw.confusion_table(bad, [0])
    with pytest.raises(ValueError):
        aw.confusion_table([1, 2], [1])
    with pytest.raises(ValueError):
        aw.confusion_table([1], [1], [0.0])
    with pytest.raises(ValueError):
        aw.confusion_table([1], [1], [float("nan")])


def test_kish_effective_n():
    # weights 1,1,2: (4)^2 / (1+1+4) = 16/6
    assert aw.kish_effective_n([1, 1, 2]) == pytest.approx(16 / 6)
    assert aw.kish_effective_n([3.0] * 7) == pytest.approx(7.0)
    with pytest.raises(ValueError):
        aw.kish_effective_n([])


def test_fleiss_cohen_se_matches_the_delta_method():
    rng = np.random.default_rng(7)
    table = rng.integers(0, 9, size=(4, 4)).astype(float) + np.eye(4) * 6
    assert aw.fleiss_cohen_se(table) == pytest.approx(delta_method_se(table), rel=1e-7)
    # n only rescales the variance
    assert aw.fleiss_cohen_se(table, n=table.sum() * 4) == pytest.approx(delta_method_se(table) / 2, rel=1e-7)


def test_fleiss_cohen_se_on_a_2x2_table_is_the_textbook_unweighted_formula():
    # a 2x2 table: the quadratic weights are the identity, so this is the unweighted kappa variance
    table = np.array([[30.0, 6.0], [4.0, 10.0]])
    assert aw.fleiss_cohen_se(table) == pytest.approx(textbook_unweighted_kappa_se(table), rel=1e-12)


def test_fleiss_cohen_se_is_none_when_kappa_is_undefined():
    assert aw.fleiss_cohen_se(np.diag([0, 0, 5.0, 0])) is None
    assert aw.fleiss_cohen_se(np.zeros((4, 4))) is None


def test_clopper_pearson_two_sided_matches_scipy():
    for k, n in ((0, 12), (11, 12), (5, 24), (24, 24)):
        lo, hi = aw.clopper_pearson_two_sided(k, n)
        ci = stats.binomtest(k, n).proportion_ci(confidence_level=0.95, method="exact")
        assert lo == pytest.approx(ci.low, abs=1e-12) and hi == pytest.approx(ci.high, abs=1e-12)


# ---------------------------------------------------------------------------
# 3. resampling: the registered helper, determinism, E = 0, undefined replicates
# ---------------------------------------------------------------------------
def tiny_clusters():
    """Four clusters; c1 and c2 are constant-and-equal (x=y=1), c3 and c4 carry the disagreement."""
    spec = {"c1": [(1, 1), (1, 1)], "c2": [(1, 1), (1, 1)], "c3": [(0, 1), (2, 3), (3, 3)],
            "c4": [(1, 0), (2, 2)]}
    cells = [{"cluster_id": cl, "x": a, "y": b} for cl, pairs in spec.items() for a, b in pairs]
    return spec, cells


QWK_STAT = aw.table_stat(aw.qwk_from_table, "x", "y")


def test_cluster_bca_is_the_registered_helper_when_the_statistic_is_defined(monkeypatch):
    rng = np.random.default_rng(5)
    cells = []
    for c in range(25):
        base = int(rng.integers(0, 4))
        for _ in range(3):
            cells.append({"cluster_id": f"k{c:02d}", "x": base,
                          "y": int(np.clip(base + rng.choice([-1, 0, 0, 1]), 0, 3))})
    mine = aw.cluster_bca(cells, QWK_STAT, seed=SEED, B=1000)
    direct = ah.cluster_bootstrap_stat(cells, QWK_STAT, None, "cluster_id", 1000, SEED, "midrank")
    assert (mine["estimate"], mine["ci_lo"], mine["ci_hi"]) == (
        direct["estimate"], direct["ci_lo"], direct["ci_hi"])      # bit-identical
    assert mine["ci_status"] == "computed" and mine["n_undefined_replicates"] == 0

    calls = []
    real = ah.cluster_bootstrap_stat

    def spy(*args, **kwargs):
        calls.append(args or kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(aw, "cluster_bootstrap_stat", spy)
    aw.cluster_bca(cells, QWK_STAT, seed=SEED, B=77)
    (args,) = calls
    # (cells, stat, strata_key, cluster_key, B, seed, ties): unstratified, whole CQ clusters, mid-rank
    assert args[2] is None and args[3] == "cluster_id" and args[4] == 77 and args[5] == SEED
    assert args[6] == "midrank"


def correlated_cells(n_clusters=25, per_cluster=3, seed=5):
    """Cells in clusters whose two raters mostly agree (a statistic on a fine enough lattice)."""
    rng = np.random.default_rng(seed)
    cells = []
    for c in range(n_clusters):
        base = int(rng.integers(0, 4))
        for _ in range(per_cluster):
            cells.append({"cluster_id": f"k{c:02d}", "x": base,
                          "y": int(np.clip(base + rng.choice([-1, 0, 0, 1]), 0, 3))})
    return cells


def test_cluster_bca_is_deterministic_for_a_fixed_seed_and_depends_on_it():
    cells = correlated_cells()
    first = aw.cluster_bca(cells, QWK_STAT, seed=SEED, B=500)
    again = aw.cluster_bca(cells, QWK_STAT, seed=SEED, B=500)
    assert first == again                                   # every field, not just the interval
    other = aw.cluster_bca(cells, QWK_STAT, seed=SEED + 1, B=500)
    assert (first["ci_lo"], first["ci_hi"]) != (other["ci_lo"], other["ci_hi"])
    assert first["estimate"] == other["estimate"]           # the estimate does not depend on the seed
    # the registered B and seed, twice: the same interval again
    a = aw.cluster_bca(cells, QWK_STAT, seed=SEED, B=10_000)
    b = aw.cluster_bca(cells, QWK_STAT, seed=SEED, B=10_000)
    assert a == b and a["resamples"] == 10_000


def test_cluster_bca_refuses_a_missing_seed():
    _, cells = tiny_clusters()
    with pytest.raises(ValueError, match="seed"):
        aw.cluster_bca(cells, QWK_STAT, seed=None, B=50)


def test_cluster_bca_resamples_whole_clusters_like_an_independent_cluster_bca():
    rng = np.random.default_rng(5)
    cells = []
    for c in range(30):
        base = int(rng.integers(0, 4))
        for _ in range(3):
            cells.append({"cluster_id": f"k{c:02d}", "x": base,
                          "y": int(np.clip(base + rng.choice([-1, 0, 0, 1]), 0, 3))})
    mine = aw.cluster_bca(cells, QWK_STAT, seed=11, B=10_000)
    by = {}
    for c in cells:
        by.setdefault(c["cluster_id"], []).append(c)
    keys = sorted(by)

    def over_clusters(idx, axis=-1):
        sample = [c for i in idx for c in by[keys[int(i)]]]
        return aw.qwk_from_table(aw.confusion_table([c["x"] for c in sample], [c["y"] for c in sample]))

    def over_cells(idx, axis=-1):
        sample = [cells[int(i)] for i in idx]
        return aw.qwk_from_table(aw.confusion_table([c["x"] for c in sample], [c["y"] for c in sample]))

    kw = dict(vectorized=False, method="BCa", n_resamples=10_000, confidence_level=0.95)
    cluster_ci = stats.bootstrap((np.arange(len(keys)),), over_clusters,
                                 random_state=np.random.default_rng(99), **kw).confidence_interval
    cell_ci = stats.bootstrap((np.arange(len(cells)),), over_cells,
                              random_state=np.random.default_rng(99), **kw).confidence_interval
    # agrees with the cluster-level BCa (Monte Carlo error only) ...
    assert abs(mine["ci_lo"] - cluster_ci.low) < 0.01 and abs(mine["ci_hi"] - cluster_ci.high) < 0.01
    # ... and is wider than a cell-level bootstrap would give (the cells of a cluster are not independent)
    assert (mine["ci_hi"] - mine["ci_lo"]) > (cell_ci.high - cell_ci.low) + 0.01


def test_e_zero_replicates_count_as_zero_not_one_and_are_counted():
    spec, cells = tiny_clusters()
    names = sorted(spec)
    B = 10_000
    # independent count: a resample has E = 0 iff both raters use the same single level in it
    n_e0 = 0
    for idx in independent_draws(len(names), SEED, B):
        pairs = [p for i in idx for p in spec[names[i]]]
        xs, ys = {a for a, _ in pairs}, {b for _, b in pairs}
        if len(xs) == 1 and xs == ys:
            n_e0 += 1
    assert n_e0 > 0
    res = aw.cluster_bca(cells, QWK_STAT, seed=SEED, B=B, undefined_replicate_value=0.0)
    assert res["n_undefined_replicates"] == n_e0
    assert res["undefined_replicate_share"] == pytest.approx(n_e0 / B)
    assert res["n_undefined_jackknife_samples"] == 0
    assert res["undefined_replicate_policy"] == "set_to_0"

    def helper_with(value):
        def stat(sample):
            q = QWK_STAT(sample)
            return value if q is None else q
        return ah.cluster_bootstrap_stat(cells, stat, None, "cluster_id", B, SEED, "midrank")

    as_zero, as_one = helper_with(0.0), helper_with(1.0)
    assert (res["ci_lo"], res["ci_hi"]) == (as_zero["ci_lo"], as_zero["ci_hi"])   # E = 0 counted as 0
    assert as_one["ci_hi"] > res["ci_hi"] + 0.05                                   # 1.0 would differ


def test_e_zero_is_counted_separately_for_jackknife_samples():
    # three clusters; leaving out c3 leaves two constant-equal clusters: that jackknife sample has E = 0
    cells = [{"cluster_id": "c1", "x": 1, "y": 1}, {"cluster_id": "c2", "x": 1, "y": 1},
             {"cluster_id": "c3", "x": 0, "y": 2}, {"cluster_id": "c3", "x": 3, "y": 3}]
    res = aw.cluster_bca(cells, QWK_STAT, seed=SEED, B=300, undefined_replicate_value=0.0)
    assert res["n_undefined_jackknife_samples"] == 1
    assert res["n_undefined_replicates"] is not None


def test_undefined_replicates_are_excluded_and_counted():
    # NPA is undefined when a resample holds no AH-negative cell.  One negative cluster out of eight.
    cells = []
    for c in range(8):
        for r in range(3):
            cells.append({"cluster_id": f"k{c}", "a_ah": 0 if (c == 0 and r == 0) else 1,
                          "a_s": 0 if (c == 0 and r < 2) else 1})
    stat = aw.table_stat(aw.npa_from_table, "a_ah", "a_s", k=2)
    B = 4000
    n_undef = 0
    for idx in independent_draws(8, SEED, B):
        if 0 not in set(int(i) for i in idx):          # cluster k0 (sorted first) never drawn
            n_undef += 1
    assert 0 < n_undef < B / 2
    res = aw.cluster_bca(cells, stat, seed=SEED, B=B)
    assert res["n_undefined_replicates"] == n_undef
    assert res["undefined_replicate_policy"] == "dropped"
    assert res["ci_status"] == "computed_without_undefined_replicates"
    assert res["estimate"] == pytest.approx(1.0)       # the one AH negative is also called negative
    assert res["ci_lo"] is not None and res["ci_lo"] <= res["estimate"] <= res["ci_hi"] + 1e-12


def test_undefined_point_estimate_gets_no_interval_and_a_reason():
    cells = [{"cluster_id": f"k{c}", "a_ah": 1, "a_s": 1} for c in range(6)]       # no AH negative at all
    res = aw.cluster_bca(cells, aw.table_stat(aw.npa_from_table, "a_ah", "a_s", k=2), seed=SEED, B=100,
                         undefined_reason=aw.UNDEFINED_REASONS["npa"])
    assert res["estimate"] is None and res["ci_lo"] is None and res["ci_hi"] is None
    assert res["ci_status"] == "undefined_estimate" and "no negative" in res["ci_reason"]


def test_too_many_undefined_replicates_give_no_interval():
    # undefined unless the resample is as large as the data: most resamples are not
    cells = [{"cluster_id": f"k{c}", "x": c % 4, "y": c % 4} for c in range(6) for _ in range(1 + c)]
    n = len(cells)

    def stat(sample):
        return None if len(sample) != n else float(len(sample))

    res = aw.cluster_bca(cells, stat, seed=SEED, B=400)
    assert res["ci_status"] == "too_many_undefined_replicates"
    assert res["ci_lo"] is None and res["undefined_replicate_share"] > 0.5


def test_undefined_jackknife_sample_sets_the_acceleration_to_zero_and_says_so():
    cells = [{"cluster_id": f"k{c}", "x": c % 4, "y": (c + 1) % 4} for c in range(6) for _ in range(2)]

    def stat(sample):                                  # undefined without cluster k0
        ids = {c["cluster_id"] for c in sample}
        return None if "k0" not in ids else float(len(sample))

    res = aw.cluster_bca(cells, stat, seed=SEED, B=300)
    assert res["acceleration_defined"] is False
    assert res["n_undefined_jackknife_samples"] == 1
    assert res["ci_lo"] is not None


def mostly_constant_spec(n_const=8):
    """Eight CQ clusters on which both annotators say level 1 and two on which they disagree: a resample that
    misses both disagreeing clusters has E = 0 (about one resample in ten)."""
    spec = {f"c{i:02d}": [(1, 1)] for i in range(n_const)}
    spec["d00"] = [(0, 1), (2, 3), (3, 3)]
    spec["d01"] = [(1, 0), (2, 2), (3, 2)]
    return spec


def test_second_qwk_drops_e_zero_replicates_and_counts_them_where_g2_counts_them_as_zero():
    spec = mostly_constant_spec()
    clusters = [spec[k] for k in sorted(spec)]
    pairs = [(cl, a, b) for cl in sorted(spec) for a, b in spec[cl]]
    cells = [sec_cell(i, cl, l0=a, l1=b) for i, (cl, a, b) in enumerate(pairs)]
    B = 3000
    want = oracle_dropping_interval(clusters, exact_qwk_or_none, SEED, B)
    assert B * 0.05 < want["n_undefined"] < B / 2 and want["n_jack_undefined"] == 0
    qwk = aw.second_annotation_block(cells, seed=SEED, B=B)["L1_agreement_AH_vs_second"]["qwk"]
    assert qwk["undefined_replicate_policy"] == "dropped"
    assert qwk["n_undefined_replicates"] == want["n_undefined"]
    assert qwk["undefined_replicate_share"] == pytest.approx(want["n_undefined"] / B)
    assert qwk["n_undefined_jackknife_samples"] == 0 and qwk["acceleration_defined"] is True
    assert qwk["ci_status"] == "computed_without_undefined_replicates"
    assert qwk["estimate"] == pytest.approx(want["theta"], abs=1e-12)
    assert (qwk["ci_lo"], qwk["ci_hi"]) == pytest.approx((want["lo"], want["hi"]), abs=1e-9)
    assert qwk["ci_lo"] > 0.5                    # the undefined resamples are not in the lower tail
    # the G2 convention on the same data: the same resamples, but E = 0 counts as 0 and fills the lower tail
    xy = [{"cluster_id": cl, "x": a, "y": b} for cl, a, b in pairs]
    g2 = aw.cluster_bca(xy, QWK_STAT, seed=SEED, B=B, undefined_replicate_value=0.0)
    assert g2["undefined_replicate_policy"] == "set_to_0" and g2["n_undefined_replicates"] == want["n_undefined"]
    assert g2["ci_lo"] == 0.0 and g2["estimate"] == pytest.approx(want["theta"], abs=1e-12)


def test_second_qwk_with_an_undefined_point_estimate_is_reported_as_undefined():
    cells = [sec_cell(i, f"cq{i:02d}", l0=2, l1=2) for i in range(8)]          # both L1 columns constant: E = 0
    block = aw.second_annotation_block(cells, seed=SEED, B=SMALL_B)
    for qwk in (block["L1_agreement_AH_vs_second"]["qwk"],
                block["judge_vs_second_annotator"]["all_cells"]["L1_scale"]["qwk"]):
        assert qwk["estimate"] is None and qwk["ci_lo"] is None and qwk["ci_hi"] is None
        assert qwk["ci_status"] == "undefined_estimate" and "E = 0" in qwk["ci_reason"]
    assert block["L1_agreement_AH_vs_second"]["exact_agreement"]["estimate"] == 1.0      # still defined


def test_second_npa_interval_is_the_independent_bca_of_the_defined_replicates():
    # 12 clusters of one cell: three AH-negative (the second annotator: negative, positive, negative), nine AH-positive
    spec = [(0, 0), (0, 1), (0, 0)] + [(1, 1)] * 9
    cells = [sec_cell(i, f"cq{i:02d}", a0=a, a1=b) for i, (a, b) in enumerate(spec)]
    B = 4000

    def npa(pairs):
        n0 = sum(1 for a, _ in pairs if a == 0)
        return None if n0 == 0 else sum(1 for a, b in pairs if a == 0 and b == 0) / n0

    want = oracle_dropping_interval([[p] for p in spec], npa, SEED, B)
    assert want["theta"] == pytest.approx(2 / 3) and 0 < want["n_undefined"] < B / 2
    got = aw.second_annotation_block(cells, seed=SEED, B=B)["A_agreement_AH_vs_second"]["npa"]
    assert got["undefined_replicate_policy"] == "dropped" and got["n_undefined_replicates"] == want["n_undefined"]
    assert got["estimate"] == pytest.approx(2 / 3)
    assert (got["ci_lo"], got["ci_hi"]) == pytest.approx((want["lo"], want["hi"]), abs=1e-9)


def test_dropping_policy_with_an_undefined_jackknife_sample_matches_the_oracle_with_zero_acceleration():
    # six clusters of two cells; the statistic needs cluster 0 in the sample, so the sample without it is undefined
    cells = [{"cluster_id": f"k{c}", "idx": c, "v": float(c * c)} for c in range(6) for _ in range(2)]

    def stat(sample):
        return None if all(s["idx"] != 0 for s in sample) else sum(s["v"] for s in sample) / len(sample)

    B = 1500
    want = oracle_dropping_interval([[{"idx": c, "v": float(c * c)}] * 2 for c in range(6)], stat, SEED, B)
    assert want["n_jack_undefined"] == 1 and 0 < want["n_undefined"] < B / 2
    res = aw.cluster_bca(cells, stat, seed=SEED, B=B)
    assert res["acceleration_defined"] is False and res["n_undefined_jackknife_samples"] == 1
    assert res["n_undefined_replicates"] == want["n_undefined"]
    assert res["estimate"] == pytest.approx(want["theta"])
    assert (res["ci_lo"], res["ci_hi"]) == pytest.approx((want["lo"], want["hi"]), abs=1e-9)


def test_a_agreement_between_passes_drops_undefined_replicates_too():
    # kappa is undefined on a resample whose two label columns are constant and equal (here: without cluster c0)
    cells = [wcell(f"d{i}", f"c{i}", "proportional", 1, 2, 2, a0=1, a1=(0 if i == 0 else 1)) for i in range(10)]
    out = aw.a_agreement_between_passes(cells, seed=SEED, B=2000)
    kap = out["per_stratum"]["proportional"]["cohen_kappa"]
    n_undef = sum(0 not in {int(i) for i in idx} for idx in independent_draws(10, SEED, 2000))
    assert 0 < n_undef < 1000 and kap["undefined_replicate_policy"] == "dropped"
    assert kap["n_undefined_replicates"] == n_undef and kap["estimate"] == pytest.approx(0.0)


def test_fewer_than_two_clusters_gives_no_interval():
    cells = [{"cluster_id": "only", "x": 1, "y": 2}, {"cluster_id": "only", "x": 3, "y": 3}]
    res = aw.cluster_bca(cells, QWK_STAT, seed=SEED, B=50)
    assert res["ci_status"] == "fewer_than_two_clusters" and res["ci_lo"] is None
    assert res["estimate"] == pytest.approx(aw.weighted_qwk([1, 3], [2, 3]))


def test_the_mid_rank_tie_rule_is_the_default_and_strict_is_a_different_interval():
    cells = [{"cluster_id": f"k{c}", "x": c % 2, "y": (c % 2) if c % 5 else 1 - c % 2} for c in range(20)]
    stat = aw.table_stat(aw.raw_agreement_from_table, "x", "y", k=2)
    default = aw.cluster_bca(cells, stat, seed=SEED, B=2000)
    mid = ah.cluster_bootstrap_stat(cells, stat, None, "cluster_id", 2000, SEED, "midrank")
    strict = ah.cluster_bootstrap_stat(cells, stat, None, "cluster_id", 2000, SEED, "strict")
    assert default["bca_ties"] == "midrank"
    assert (default["ci_lo"], default["ci_hi"]) == (mid["ci_lo"], mid["ci_hi"])
    assert (strict["ci_lo"], strict["ci_hi"]) != (mid["ci_lo"], mid["ci_hi"])


# ---------------------------------------------------------------------------
# 4. washout design and the join
# ---------------------------------------------------------------------------
def read_rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in cols})
    return path


DESIGN_COLS = ["cell_id", "source_cell_id", "cell_kind", "stratum", "inclusion_prob", "excluded_reason"]


def design_row(cid, src, kind="primary", stratum="proportional", prob="0.5", reason=""):
    return {"cell_id": cid, "source_cell_id": src, "cell_kind": kind, "stratum": stratum,
            "inclusion_prob": prob, "excluded_reason": reason}


@pytest.mark.parametrize("mutate,message", [
    (lambda r: r[0].update(inclusion_prob="0"), "inclusion_prob"),
    (lambda r: r[0].update(inclusion_prob="1.2"), "inclusion_prob"),
    (lambda r: r[0].update(inclusion_prob="abc"), "inclusion_prob"),
    (lambda r: r[0].update(inclusion_prob=""), "inclusion_prob"),
    (lambda r: r[0].update(stratum="other"), "stratum"),
    (lambda r: r[0].update(stratum=""), "stratum"),
    (lambda r: r[0].update(cell_kind=""), "cell_kind"),
    (lambda r: r[0].update(cell_kind="control"), "cell_kind"),
    (lambda r: r[1].update(cell_id="a"), "duplicate cell_id"),
    (lambda r: r[1].update(source_cell_id="sa"), "duplicate source_cell_id"),
    (lambda r: r[0].update(excluded_reason="artifact_digest_mismatch"), "never excluded"),
])
def test_design_validation_rejects(tmp_path, mutate, message):
    rows = [design_row("a", "sa"), design_row("b", "sb", stratum="enriched")]
    mutate(rows)
    path = write_csv(tmp_path / "design.csv", rows, DESIGN_COLS)
    with pytest.raises(ValueError, match=message):
        aw.load_washout_design(path)


def test_design_loads_csv_and_json_alike_and_reads_controls(tmp_path):
    rows = [design_row("a", "sa"), design_row("b", "sb", stratum="enriched", prob="0.25"),
            design_row("c", "sc", kind="ablated_control", stratum="", prob="", reason="artifact_digest_mismatch"),
            design_row("d", "sd", kind="preserved_control", stratum="", prob="")]
    csv_path = write_csv(tmp_path / "d.csv", rows, DESIGN_COLS)
    json_path = tmp_path / "d.json"
    json_path.write_text(json.dumps(rows))
    assert aw.load_washout_design(csv_path) == aw.load_washout_design(json_path)
    got = aw.load_washout_design(csv_path)
    assert got[1].inclusion_prob == 0.25 and got[1].stratum == "enriched"
    assert got[2].excluded_reason == "artifact_digest_mismatch" and got[2].stratum is None
    assert got[3].excluded_reason is None


def test_check_washout_design_counts_and_conformity():
    def rows(n_prop, n_enr, n_abl, n_pre):
        out = [aw.DesignRow(f"p{i}", f"sp{i}", "primary", "proportional", 0.5, None) for i in range(n_prop)]
        out += [aw.DesignRow(f"e{i}", f"se{i}", "primary", "enriched", 0.5, None) for i in range(n_enr)]
        out += [aw.DesignRow(f"a{i}", f"sa{i}", "ablated_control", None, None, None) for i in range(n_abl)]
        out += [aw.DesignRow(f"r{i}", f"sr{i}", "preserved_control", None, None, None) for i in range(n_pre)]
        return out

    ok = aw.check_washout_design(rows(48, 24, 24, 12))
    assert ok["conforms"] and ok["strata_sizes_as_registered"] and ok["n_primary"] == 72
    # DN-4a: fewer than 24 mismatch cells move the strata sizes, not the total
    shifted = aw.check_washout_design(rows(60, 12, 24, 12))
    assert shifted["conforms"] and not shifted["strata_sizes_as_registered"]
    short = aw.check_washout_design(rows(48, 23, 24, 12))
    assert not short["conforms"] and "71 primary" in short["problems"][0]
    assert not aw.check_washout_design(rows(48, 24, 23, 12))["conforms"]
    assert not aw.check_washout_design(rows(48, 24, 24, 11))["conforms"]


def builder_style_mapping(design_rows):
    """The sealed ``washout_mapping.json`` of build_washout_packet.py as it documents itself: a JSON object with
    a ``rows`` list; controls carry stratum 'control' and inclusion_prob 1.0; extra keys are present."""
    rows = []
    for pos, r in enumerate(design_rows, start=1):
        primary = r["cell_kind"] == "primary"
        prob = float(r["inclusion_prob"]) if primary else 1.0
        rows.append({"cell_id": r["cell_id"], "source_cell_id": r["source_cell_id"], "cell_kind": r["cell_kind"],
                     "stratum": r["stratum"] if primary else "control", "inclusion_prob": round(prob, 4),
                     "w": 1.0 / prob, "excluded_reason": r["excluded_reason"],
                     "position": None if r["excluded_reason"] else pos, "selection": r["stratum"] or "control",
                     "category_stratum": "cat|J2" if primary else "", "view_ref": None,
                     "cq_text_source": "paraphrase", "cq_shown_differs_from_judge_input": None})
    return {"kind": "washout_mapping", "sealed": True, "warning": "SEALED until the washout labels are locked",
            "schema": {"cell_id": "opaque id"}, "seed": 20260913, "rows": rows}


def test_design_accepts_the_washout_builders_sealed_mapping_json(tmp_path):
    rows = [design_row("a", "sa", stratum="proportional", prob="0.32"),
            design_row("b", "sb", stratum="enriched", prob="0.6316"),
            design_row("c", "sc", kind="ablated_control", stratum="", prob="", reason="artifact_digest_mismatch"),
            design_row("d", "sd", kind="preserved_control", stratum="", prob="")]
    path = tmp_path / "washout_mapping.json"
    path.write_text(json.dumps(builder_style_mapping(rows)))
    got = aw.load_washout_design(path)
    assert [(r.cell_id, r.cell_kind, r.stratum, r.inclusion_prob, r.excluded_reason) for r in got] == [
        ("a", "primary", "proportional", 0.32, None), ("b", "primary", "enriched", 0.6316, None),
        ("c", "ablated_control", None, None, "artifact_digest_mismatch"),
        ("d", "preserved_control", None, None, None)]


class FakeLabels:
    """Stand-in for ``ah.LabelSet`` in the join tests."""

    def __init__(self, labels, rater_l1, tolerated_nonblank_ids=()):
        self.labels, self.rater_l1 = labels, rater_l1
        self.tolerated_nonblank_ids = tolerated_nonblank_ids


def test_join_washout_joins_by_source_id_and_uses_the_ah_cluster():
    design = [aw.DesignRow("w1", "s1", "primary", "enriched", 0.25, None)]
    ah_l = FakeLabels({"s1": 1}, {"s1": 2})
    wo_l = FakeLabels({"w1": 0}, {"w1": 3})
    primary, controls = aw.join_washout(design, ah_l, {"s1": {"cluster_id": "cq9"}}, wo_l)
    (cell,) = primary
    assert (cell.cluster_id, cell.stratum, cell.w) == ("cq9", "enriched", 4.0)
    assert (cell.ah_a, cell.ah_l1, cell.wo_a, cell.wo_l1) == (1, 2, 0, 3)
    assert controls == []


@pytest.mark.parametrize("ah_l,wo_l,fields,message", [
    (FakeLabels({}, {}), FakeLabels({"w1": 1}, {"w1": 1}), {"s1": {"cluster_id": "c"}}, "AH labels lack source cell"),
    (FakeLabels({"s1": 1}, {"s1": None}), FakeLabels({"w1": 1}, {"w1": 1}), {"s1": {"cluster_id": "c"}}, "AH labels lack A or rater_L1"),
    (FakeLabels({"s1": 1}, {"s1": 1}), FakeLabels({}, {}), {"s1": {"cluster_id": "c"}}, "washout labels lack cell"),
    (FakeLabels({"s1": 1}, {"s1": 1}), FakeLabels({"w1": None}, {"w1": 1}), {"s1": {"cluster_id": "c"}}, "washout labels lack A or rater_L1"),
    (FakeLabels({"s1": 1}, {"s1": 1}), FakeLabels({"w1": 1}, {"w1": 1}), {}, "no cluster_id"),
    (FakeLabels({"s1": 1}, {"s1": 1}), FakeLabels({"w1": 1, "zzz": 1}, {"w1": 1, "zzz": 1}), {"s1": {"cluster_id": "c"}}, "absent from the design"),
])
def test_join_washout_refuses_incomplete_primary_data(ah_l, wo_l, fields, message):
    design = [aw.DesignRow("w1", "s1", "primary", "proportional", 0.5, None)]
    with pytest.raises(ValueError, match=message):
        aw.join_washout(design, ah_l, fields, wo_l)


def test_join_washout_keeps_an_unlabeled_presented_control_as_not_valid_and_refuses_a_labeled_excluded_one():
    design = [aw.DesignRow("c1", "sc1", "ablated_control", None, None, None),
              aw.DesignRow("c2", "sc2", "ablated_control", None, None, "artifact_digest_mismatch"),
              aw.DesignRow("c3", "sc3", "ablated_control", None, None, None)]
    wo_l = FakeLabels({"c1": None, "c2": None, "c3": 0}, {})
    _, controls = aw.join_washout(design, FakeLabels({}, {}), {}, wo_l)
    by = {c.cell_id: c for c in controls}
    assert not by["c1"].valid and by["c1"].presented and by["c1"].a is None
    assert not by["c2"].presented and not by["c2"].valid
    assert by["c3"].valid and by["c3"].a == 0
    with pytest.raises(ValueError, match="cannot be labeled"):
        aw.join_washout(design, FakeLabels({}, {}), {}, FakeLabels({"c2": None}, {}, ("c2",)))


# ---------------------------------------------------------------------------
# 5. G2
# ---------------------------------------------------------------------------
def test_g2_hand_dataset_pooled_and_per_stratum_values():
    res = aw.g2_analysis(hand_cells(), seed=SEED, B=SMALL_B)
    est = res["estimates"]
    # pooled, weights 1,1,1,2,1,...: 53/64 (hand value above)
    assert est["reweighted_pooled"]["qwk"] == pytest.approx(53 / 64, abs=1e-14)
    assert res["value"] == pytest.approx(53 / 64, abs=1e-14)
    # proportional = first six pairs: O = 2/6, E = 82/36 -> 1 - 12/82 = 35/41
    assert est["per_stratum"]["proportional"]["qwk"] == pytest.approx(35 / 41, abs=1e-14)
    # enriched = last four pairs: O = 1/4, E = 2 -> 7/8
    assert est["per_stratum"]["enriched"]["qwk"] == pytest.approx(7 / 8, abs=1e-14)
    assert frac_qwk(HAND_X[:6], HAND_Y[:6]) == Fraction(35, 41)
    assert frac_qwk(HAND_X[6:], HAND_Y[6:]) == Fraction(7, 8)
    # the per-stratum estimators are unweighted: the weight of cell 3 does not enter
    assert est["per_stratum"]["proportional"]["estimator"].startswith("plain QWK")
    assert est["per_stratum"]["proportional"]["n_cells"] == 6 and est["per_stratum"]["enriched"]["n_cells"] == 4


def test_g2_pooled_estimate_uses_the_inverse_probability_weights():
    base = aw.g2_analysis(hand_cells(), seed=SEED, B=SMALL_B)
    heavier = [wcell(f"h{i}", HAND_CL[i], HAND_STRATUM[i], 6 if i == 3 else 1, HAND_X[i], HAND_Y[i]) for i in range(10)]
    moved = aw.g2_analysis(heavier, seed=SEED, B=SMALL_B)
    assert moved["value"] != pytest.approx(base["value"])
    assert moved["value"] == pytest.approx(float(frac_qwk(HAND_X, HAND_Y, [1, 1, 1, 6, 1, 1, 1, 1, 1, 1])))
    for s in aw.WASHOUT_STRATA:                               # strata do not move with the weights
        assert moved["estimates"]["per_stratum"][s]["qwk"] == base["estimates"]["per_stratum"][s]["qwk"]
    # weights come from pi, and a common factor leaves the estimate alone
    scaled = [wcell(f"h{i}", HAND_CL[i], HAND_STRATUM[i], HAND_W[i] * 5.0, HAND_X[i], HAND_Y[i]) for i in range(10)]
    assert aw.g2_analysis(scaled, seed=SEED, B=SMALL_B)["value"] == pytest.approx(base["value"], abs=1e-13)


def test_g2_weights_summary_reports_kish_n_eff_and_the_frame_check():
    res = aw.g2_analysis(hand_cells(), seed=SEED, B=SMALL_B)
    w = np.array(HAND_W, float)
    pooled = res["estimates"]["reweighted_pooled"]
    assert pooled["kish_n_eff"] == pytest.approx(w.sum() ** 2 / (w ** 2).sum())
    assert res["weights_summary"]["kish_n_eff"] == pytest.approx(pooled["kish_n_eff"])
    assert res["weights_summary"]["ht_frame_size_estimate"] == pytest.approx(w.sum())
    assert res["weights_summary"]["registered_frame_size"] == 188
    assert pooled["n_replicates_with_E_zero"] is not None and pooled["E_zero_convention"].endswith("not 1.0")
    assert res["cluster_structure"] == {"n_cq_clusters": 5, "n_cq_clusters_in_both_strata": 0}


def test_g2_fleiss_cohen_se_is_reported_for_the_two_strata_only_and_never_decides():
    res = aw.g2_analysis(hand_cells(), seed=SEED, B=SMALL_B)
    strata = res["estimates"]["per_stratum"]
    for s in aw.WASHOUT_STRATA:
        check = strata[s]["fleiss_cohen_everitt"]
        assert check["decision_input"] is False and check["se"] is not None
        tab = np.array(strata[s]["confusion_table_AH_rows_washout_cols"], float)
        assert check["se"] == pytest.approx(aw.fleiss_cohen_se(tab))
        assert check["n_for_se"] == strata[s]["n_cells"]
    pooled_text = json.dumps(res["estimates"]["reweighted_pooled"])
    for token in ("fleiss", "analytic", "wald", "se\""):
        assert token not in pooled_text.lower()


def e_zero_g2_cells():
    """Washout cells in four CQ clusters: c1 and c2 hold only x=y=1 (a resample made of them alone has E=0)."""
    spec = {"c1": [(1, 1), (1, 1)], "c2": [(1, 1), (1, 1)], "c3": [(0, 1), (2, 3), (3, 3)], "c4": [(1, 0), (2, 2)]}
    cells, n = [], 0
    for cl, pairs in spec.items():
        for x, y in pairs:
            cells.append(wcell(f"e{n}", cl, "proportional" if n % 2 else "enriched", 2.0 if cl == "c3" else 1.0, x, y))
            n += 1
    return spec, cells


def test_g2_counts_an_e_zero_resample_as_zero_not_one_and_reports_how_many():
    spec, cells = e_zero_g2_cells()
    names, B = sorted(spec), 10_000
    n_e0 = 0
    for idx in independent_draws(len(names), SEED, B):            # re-derived draws of the registered helper
        pairs = [p for i in idx for p in spec[names[i]]]
        xs, ys = {a for a, _ in pairs}, {b for _, b in pairs}
        n_e0 += int(len(xs) == 1 and xs == ys)
    assert n_e0 > 0
    res = aw.g2_analysis(cells, seed=SEED, B=B)
    pooled = res["estimates"]["reweighted_pooled"]
    assert pooled["n_replicates_with_E_zero"] == n_e0 and pooled["n_jackknife_samples_with_E_zero"] == 0
    records = aw._records(cells)
    stat = aw.table_stat(aw.qwk_from_table, "x", "y", kw="w")

    def helper_with(value):
        def f(sample):
            q = stat(sample)
            return value if q is None else q
        return ah.cluster_bootstrap_stat(records, f, None, "cluster_id", B, SEED, "midrank")

    zero, one = helper_with(0.0), helper_with(1.0)
    assert (res["ci_lo"], res["ci_hi"]) == (zero["ci_lo"], zero["ci_hi"])
    assert (one["ci_lo"], one["ci_hi"]) != (zero["ci_lo"], zero["ci_hi"])      # the convention is not cosmetic
    # the same rule for the per-stratum intervals (the strata resample their own clusters)
    for s_ in aw.WASHOUT_STRATA:
        entry = res["estimates"]["per_stratum"][s_]
        assert entry["undefined_replicate_policy"] == "set_to_0"
        assert entry["n_replicates_with_E_zero"] is not None


def test_g2_gate_counts_e_zero_resamples_as_zero_so_a_sparse_sample_is_not_flattered():
    spec = mostly_constant_spec()                 # eight CQ clusters where both passes say 1, two where they disagree
    cells, n = [], 0
    for cl in sorted(spec):
        for x, y in spec[cl]:
            cells.append(wcell(f"m{n:02d}", cl, "proportional" if n % 2 else "enriched", 1.0, x, y))
            n += 1
    B = 3000
    res = aw.g2_analysis(cells, seed=SEED, B=B)
    pooled = res["estimates"]["reweighted_pooled"]
    assert pooled["undefined_replicate_policy"] == "set_to_0" and pooled["ci_status"] == "computed"
    assert pooled["n_replicates_with_E_zero"] > B * 0.05          # about one resample in ten has E = 0
    # they count as 0, so they fill the lower tail: the lower end is 0 and the gate fails ...
    assert pooled["ci_lo"] == 0.0 and res["status"] == "fail"
    # ... where dropping them (the sec.12.4 policy, which is NOT G2's) would have given a lower end above 0.70
    stat = aw.table_stat(aw.qwk_from_table, "x", "y", kw="w")
    assert aw.cluster_bca(aw._records(cells), stat, seed=SEED, B=B)["ci_lo"] > 0.70
    for s_ in aw.WASHOUT_STRATA:
        assert res["estimates"]["per_stratum"][s_]["undefined_replicate_policy"] == "set_to_0"


def test_g2_gate_is_the_lower_bound_of_the_pooled_interval_at_least_070(monkeypatch):
    def make_fake(pooled_lo, stratum_lo=0.95):
        def fake(cells, stat, **kw):
            lo = pooled_lo if len(cells) == 10 else stratum_lo
            return {"estimate": 0.9, "ci_lo": lo, "ci_hi": 0.99, "ci_level": 0.95, "ci_status": "computed",
                    "n_cells": len(cells), "n_clusters": 5, "resamples": 7, "n_undefined_replicates": 0,
                    "n_undefined_jackknife_samples": 0}
        return fake

    for lo, status in ((0.70, "pass"), (0.7000001, "pass"), (0.6999999, "fail"), (0.0, "fail"), (-0.3, "fail")):
        monkeypatch.setattr(aw, "cluster_bca", make_fake(lo))
        res = aw.g2_analysis(hand_cells(), seed=SEED, B=7)
        assert res["status"] == status, lo
        assert res["threshold"] == 0.70 and res["ci_lo"] == lo and res["gate_input"] == "reweighted_pooled"
    # the per-stratum intervals do not decide: pooled fails while both strata would pass, and the reverse
    monkeypatch.setattr(aw, "cluster_bca", make_fake(0.5, stratum_lo=0.99))
    assert aw.g2_analysis(hand_cells(), seed=SEED, B=7)["status"] == "fail"
    monkeypatch.setattr(aw, "cluster_bca", make_fake(0.8, stratum_lo=0.0))
    assert aw.g2_analysis(hand_cells(), seed=SEED, B=7)["status"] == "pass"


def test_g2_gate_does_not_depend_on_the_analytic_se(monkeypatch):
    baseline = aw.g2_analysis(hand_cells(), seed=SEED, B=SMALL_B)
    monkeypatch.setattr(aw, "fleiss_cohen_se", lambda *a, **k: 1e9)
    changed = aw.g2_analysis(hand_cells(), seed=SEED, B=SMALL_B)
    assert (changed["status"], changed["value"], changed["ci_lo"], changed["ci_hi"]) == (
        baseline["status"], baseline["value"], baseline["ci_lo"], baseline["ci_hi"])


def test_g2_not_computable_when_the_estimate_or_the_interval_is_missing(monkeypatch):
    # both raters constant and equal on all cells: E = 0 on the observed data
    constant = [wcell(f"k{i}", f"c{i % 4}", "proportional", 2, 2, 2) for i in range(8)]
    res = aw.g2_analysis(constant, seed=SEED, B=SMALL_B)
    assert res["status"] == "not_computable" and res["value"] is None
    assert "E = 0" in res["reason"]
    # one CQ cluster: no interval
    one = [wcell(f"o{i}", "c1", "proportional", 2, i % 4, (i + 1) % 4) for i in range(5)]
    res = aw.g2_analysis(one, seed=SEED, B=SMALL_B)
    assert res["status"] == "not_computable" and "fewer_than_two_clusters" in res["reason"]
    assert aw.g2_analysis([], seed=SEED, B=SMALL_B)["status"] == "not_computable"


def test_g2_when_all_raters_agree_the_interval_collapses_on_one_and_the_gate_passes():
    cells = [wcell(f"a{i}", f"c{i % 6}", "proportional" if i < 12 else "enriched", 2.0, i % 4, i % 4)
             for i in range(18)]
    res = aw.g2_analysis(cells, seed=SEED, B=SMALL_B)
    assert res["value"] == pytest.approx(1.0) and res["ci_lo"] == pytest.approx(1.0)
    assert res["status"] == "pass"


def test_g2_with_an_empty_stratum_reports_it_and_pools_the_other():
    cells = [c for c in hand_cells() if c.stratum == "proportional"]
    res = aw.g2_analysis(cells, seed=SEED, B=SMALL_B)
    enriched = res["estimates"]["per_stratum"]["enriched"]
    assert enriched["n_cells"] == 0 and enriched["qwk"] is None and enriched["ci_status"] == "empty_stratum"
    assert res["empty_strata"] == ["enriched"] and res["strata_present"] == ["proportional"]
    assert res["value"] == pytest.approx(float(frac_qwk(HAND_X[:6], HAND_Y[:6], HAND_W[:6])))
    assert res["status"] in ("pass", "fail", "not_computable")
    # and the other way round
    res2 = aw.g2_analysis([c for c in hand_cells() if c.stratum == "enriched"], seed=SEED, B=SMALL_B)
    assert res2["empty_strata"] == ["proportional"]


def test_g2_resampling_is_unstratified_whole_cq_clusters_with_fixed_weights(monkeypatch):
    seen = []
    real = ah.cluster_bootstrap_stat

    def spy(cells, stat_fn, strata_key=None, cluster_key="cluster_id", B=None, seed=None, ties=None):
        seen.append((len(cells), strata_key, cluster_key, B, seed, ties,
                     sorted({c["cluster_id"] for c in cells})))
        return real(cells, stat_fn, strata_key, cluster_key, B, seed, ties)

    monkeypatch.setattr(aw, "cluster_bootstrap_stat", spy)
    aw.g2_analysis(hand_cells(), seed=SEED, B=SMALL_B)
    pooled = [s for s in seen if s[0] == 10]
    assert len(pooled) == 1
    n, strata_key, cluster_key, B, seed, ties, clusters = pooled[0]
    assert strata_key is None and cluster_key == "cluster_id" and (B, seed, ties) == (SMALL_B, SEED, "midrank")
    assert clusters == ["c1", "c2", "c3", "c4", "c5"]
    # the weight of a cell is a property of the cell: the statistic sees the same w in every resample
    seen_w = set()
    real_stat = aw.table_stat

    def watch_table(fn, kx, ky, **kw):
        stat = real_stat(fn, kx, ky, **kw)

        def wrapped(sample):
            if kw.get("kw") == "w":
                seen_w.update(r["w"] for r in sample)
            return stat(sample)
        return wrapped

    monkeypatch.setattr(aw, "table_stat", watch_table)
    aw.g2_analysis(hand_cells(), seed=SEED, B=SMALL_B)
    assert seen_w == {1.0, 2.0}


def stratum_cells(n_clusters, stratum, seed, w=1.0, prefix=None):
    """Three cells per CQ cluster in one stratum, the two passes mostly agreeing."""
    prefix = prefix or stratum[:3]
    rng = np.random.default_rng(seed)
    out = []
    for c in range(n_clusters):
        base = int(rng.integers(0, 4))
        for r in range(3):
            y = int(np.clip(base + rng.choice([-1, 0, 0, 1]), 0, 3))
            out.append(wcell(f"{prefix}-{c:02d}-{r}", f"{prefix}{c:02d}", stratum, w, base, y))
    return out


def test_g2_per_stratum_interval_resamples_that_strata_own_cq_clusters_unweighted(monkeypatch):
    prop, enr = stratum_cells(20, "proportional", 1, w=3.125), stratum_cells(12, "enriched", 2, w=1.583)
    cells = prop + enr
    calls = []
    real = ah.cluster_bootstrap_stat

    def spy(sample_cells, stat_fn, strata_key, cluster_key, B, seed, ties):
        calls.append({"clusters": {c["cluster_id"] for c in sample_cells}, "strata_key": strata_key,
                      "cluster_key": cluster_key, "B": B, "seed": seed})
        return real(sample_cells, stat_fn, strata_key, cluster_key, B, seed, ties)

    monkeypatch.setattr(aw, "cluster_bootstrap_stat", spy)
    aw.g2_analysis(cells, seed=SEED, B=77)
    monkeypatch.undo()
    # three registered-helper calls: the proportional stratum, the enriched stratum, the pool: each over whole CQ
    # clusters, unstratified, and the stratum calls see only that stratum's own clusters
    assert [len(c["clusters"]) for c in calls] == [20, 12, 32]
    assert calls[0]["clusters"] == {c.cluster_id for c in prop} and calls[1]["clusters"] == {c.cluster_id for c in enr}
    assert all(c["strata_key"] is None and c["cluster_key"] == "cluster_id" and c["B"] == 77 and c["seed"] == SEED
               for c in calls)

    base = aw.g2_analysis(cells, seed=SEED, B=SMALL_B)
    per = base["estimates"]["per_stratum"]
    # the interval is an independent BCa of the stratum's own clusters, with the plain (weight-free) QWK
    by = {}
    for c in prop:
        by.setdefault(c.cluster_id, []).append((c.ah_l1, c.wo_l1))
    want = oracle_dropping_interval([by[k] for k in sorted(by)], exact_qwk_or_none, SEED, SMALL_B)
    assert want["n_undefined"] == 0
    assert per["proportional"]["qwk"] == pytest.approx(want["theta"], abs=1e-12)
    assert (per["proportional"]["ci_lo"], per["proportional"]["ci_hi"]) == pytest.approx(
        (want["lo"], want["hi"]), abs=1e-9)
    assert "own CQ clusters" in per["proportional"]["resampling"] and "no weights" in per["proportional"]["resampling"]
    assert "unweighted" in per["proportional"]["estimator"]
    # reweighting one stratum changes the pooled value and leaves both per-stratum blocks bit-identical ...
    skewed = [dataclasses.replace(c, w=c.w * 7.0, pi=c.pi / 7.0) if c.stratum == "proportional" else c for c in cells]
    out = aw.g2_analysis(skewed, seed=SEED, B=SMALL_B)
    assert out["estimates"]["per_stratum"] == per
    assert out["estimates"]["reweighted_pooled"]["qwk"] != base["estimates"]["reweighted_pooled"]["qwk"]
    # ... and so does replacing the other stratum's data altogether
    other = aw.g2_analysis(prop + stratum_cells(9, "enriched", 99), seed=SEED, B=SMALL_B)
    assert other["estimates"]["per_stratum"]["proportional"] == per["proportional"]
    assert other["estimates"]["per_stratum"]["enriched"] != per["enriched"]


def test_g2_docstrings_state_the_per_stratum_resampling():
    assert "OWN CQ" in aw.g2_analysis.__doc__ and "no weights" in aw.g2_analysis.__doc__
    assert "THAT STRATUM'S OWN CQ CLUSTERS" in aw.__doc__ and "UNWEIGHTED" in aw.__doc__


def two_stage_population(seed=12345):
    """A synthetic 188-cell population in 33 CQ clusters (23 of 6 cells, 10 of 5) with a cluster effect on both
    the level and the AH-washout agreement, 24 (category x J) strata and a 'discordant' flag that is likelier
    where the two passes disagree.  Returns arrays x, y, cluster, stratum-index, discordant."""
    rng = np.random.default_rng(seed)
    x, y, cl, st, dis = [], [], [], [], []
    for c, size in enumerate([6] * 23 + [5] * 10):
        u = rng.normal(0, 1.0)
        for _ in range(size):
            base = int(np.clip(round(1.5 + 0.8 * u + rng.normal(0, 0.9)), 0, 3))
            agree = rng.random() < 1 / (1 + np.exp(-(0.9 + 0.8 * u)))
            x.append(base)
            y.append(base if agree else int(np.clip(base + rng.choice([-1, 1]), 0, 3)))
            cl.append(c)
            st.append(int(rng.integers(0, 24)))
            dis.append(bool(rng.random() < (0.55 if x[-1] != y[-1] else 0.12)))
    return np.array(x), np.array(y), np.array(cl), np.array(st), np.array(dis)


def two_stage_draw(st, dis, seed, n_prop=48, n_enr=24):
    """The selection of build_washout_packet.py in outline: n_prop cells allocated proportionally over the
    strata (largest remainder, at least one each), then n_enr cells drawn from the discordant cells that
    stage one left over (topped up from the rest when there are fewer)."""
    r = random.Random(seed)
    by = {}
    for i, s in enumerate(st.tolist()):
        by.setdefault(s, []).append(i)
    keys = sorted(by)
    n = len(st)
    quota = {k: Fraction(n_prop * len(by[k]), n) for k in keys}
    alloc = {k: quota[k].numerator // quota[k].denominator for k in keys}
    for k in sorted(keys, key=lambda k: (-(quota[k] - alloc[k]), k))[: n_prop - sum(alloc.values())]:
        alloc[k] += 1
    for k in keys:
        alloc[k] = max(1, alloc[k])
    while sum(alloc.values()) > n_prop:
        big = max(alloc.values())
        alloc[min(k for k in keys if alloc[k] == big)] -= 1
    stage1 = [i for k in keys for i in r.sample(by[k], alloc[k])]
    pool = sorted(set(np.flatnonzero(dis).tolist()) - set(stage1))
    stage2 = r.sample(pool, n_enr) if len(pool) >= n_enr else pool + r.sample(
        sorted(set(range(n)) - set(stage1) - set(pool)), n_enr - len(pool))
    return stage1, stage2


def test_pooled_weighted_estimator_recovers_the_population_qwk_where_the_unweighted_pool_does_not():
    """Design-based check of the whole G2 path.  A fixed synthetic population, repeated two-stage draws, pi from
    reruns of the draw (as the builder does), the estimate taken from ``g2_analysis``: the 1/pi-weighted
    pooled QWK is close to the population QWK, the plain pool of the 72 cells (enriched on disagreement) is
    biased down, and the 95% interval is not anti-conservative."""
    x, y, cl, st, dis = two_stage_population()
    truth = aw.weighted_qwk(x.tolist(), y.tolist())
    runs = 8000
    hits = np.zeros(len(x))
    for r in range(1, runs + 1):
        s1, s2 = two_stage_draw(st, dis, 20260913 + r)
        hits[s1 + s2] += 1
    pi = np.round(hits / runs, 4)
    assert (pi > 0).all() and 0.15 < pi.min() < pi.max() <= 1.0
    weighted, plain, covered, n_ci = [], [], 0, 0
    for rep in range(70):
        s1, s2 = two_stage_draw(st, dis, 777000 + rep)
        cells = [wcell(f"r{rep}-{i}", f"c{cl[i]:02d}", "proportional" if i in set(s1) else "enriched",
                       1.0 / pi[i], int(x[i]), int(y[i])) for i in s1 + s2]
        res = aw.g2_analysis(cells, seed=SEED, B=SMALL_B)
        weighted.append(res["value"])
        plain.append(aw.weighted_qwk([int(x[i]) for i in s1 + s2], [int(y[i]) for i in s1 + s2]))
        if res["ci_lo"] is not None:
            n_ci += 1
            covered += res["ci_lo"] <= truth <= res["ci_hi"]
    weighted, plain = np.array(weighted), np.array(plain)
    assert abs(weighted.mean() - truth) < 0.012                      # unbiased up to Monte Carlo error
    assert plain.mean() < truth - 0.03                               # range restriction: the plain pool is too low
    assert abs(weighted.mean() - truth) < abs(plain.mean() - truth) / 3
    assert covered / n_ci > 0.90                                     # the interval does not under-cover


def test_g2_pooled_interval_is_a_cq_cluster_bca_of_the_weighted_qwk_not_a_cell_bootstrap():
    cells = []
    rng = np.random.default_rng(21)
    for c in range(24):
        base = int(rng.integers(0, 4))
        for r in range(3):
            stratum = "proportional" if r < 2 else "enriched"
            cells.append(wcell(f"x{c}-{r}", f"cq{c:02d}", stratum, 3.0 if r < 2 else 1.5, base,
                               int(np.clip(base + rng.choice([-1, 0, 0, 1]), 0, 3))))
    res = aw.g2_analysis(cells, seed=SEED, B=1000)
    records = aw._records(cells)
    stat = aw.table_stat(aw.qwk_from_table, "x", "y", kw="w")
    direct = ah.cluster_bootstrap_stat(records, stat, None, "cluster_id", 1000, SEED, "midrank")
    assert (res["value"], res["ci_lo"], res["ci_hi"]) == (direct["estimate"], direct["ci_lo"], direct["ci_hi"])
    assert res["cluster_structure"]["n_cq_clusters_in_both_strata"] == 24      # CQs span both strata


def test_a_agreement_between_passes_is_descriptive_and_reweighted():
    cells = []
    # proportional: 10 cells, AH A=1 for all but 2, washout agrees on 8 of 10
    for i in range(10):
        cells.append(wcell(f"p{i}", f"c{i % 5}", "proportional", 4.0, 1, 1,
                           a0=0 if i < 2 else 1, a1=(0 if i < 1 else (1 if i < 2 else 1)) if i != 9 else 0))
    for i in range(6):
        cells.append(wcell(f"e{i}", f"c{i % 3}", "enriched", 1.0, 1, 1, a0=i % 2, a1=(i + (i == 5)) % 2))
    out = aw.a_agreement_between_passes(cells, seed=SEED, B=SMALL_B)
    assert out["descriptive_only"] is True and "gate" not in json.dumps(out).lower()
    prop = out["per_stratum"]["proportional"]
    t = prop["table"]
    assert t["n11"] + t["n10"] + t["n01"] + t["n00"] == 10
    assert prop["raw_agreement"]["estimate"] == pytest.approx((t["n11"] + t["n00"]) / 10)
    pooled = out["reweighted_pooled"]
    wt = pooled["weighted_table"]
    assert sum(wt.values()) == pytest.approx(10 * 4.0 + 6 * 1.0)
    assert pooled["raw_agreement"]["estimate"] == pytest.approx((wt["n11"] + wt["n00"]) / sum(wt.values()))
    assert "unweighted pooled" not in out and "pooled_unweighted" not in out
    # kappa is undefined when a pass is constant: reported as undefined, with a reason
    constant = [wcell(f"q{i}", f"c{i % 4}", "proportional", 2.0, 1, 1, a0=1, a1=1) for i in range(8)]
    k = aw.a_agreement_between_passes(constant, seed=SEED, B=SMALL_B)["per_stratum"]["proportional"]["cohen_kappa"]
    assert k["estimate"] is None and k["ci_status"] == "undefined_estimate"
    assert aw.a_agreement_between_passes(constant, seed=SEED, B=SMALL_B)["per_stratum"]["proportional"][
        "raw_agreement"]["estimate"] == 1.0


# ---------------------------------------------------------------------------
# 6. G3-W
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n_a0,status", [(24, "pass"), (23, "pass"), (22, "pass"), (21, "fail"), (0, "fail")])
def test_g3w_gives_a_verdict_when_all_24_are_presented_and_labeled(n_a0, status):
    res = aw.g3_w(ablated_controls(n_a0=n_a0) + preserved_controls())["ablated"]
    assert res["status"] == status and res["n_valid"] == 24 and res["n_unsupported_A0"] == n_a0
    assert res["value"] == pytest.approx(n_a0 / 24) and res["threshold"] == pytest.approx(22 / 24)


@pytest.mark.parametrize("kwargs", [
    dict(excluded=1), dict(excluded=2), dict(unlabeled=1), dict(excluded=1, unlabeled=1), dict(excluded=8),
])
def test_g3w_gives_no_verdict_unless_all_24_are_presented_and_labeled(kwargs):
    # every valid control carries A=0: a proportional rule would pass; the pinned rule gives no verdict
    controls = ablated_controls(n_a0=24, **kwargs)
    n_valid = sum(c.valid for c in controls)
    res = aw.g3_w(controls + preserved_controls())["ablated"]
    assert res["status"] == "not_computable" and res["value"] is None
    assert res["n_valid"] == n_valid < 24
    assert res["n_unsupported_A0"] == n_valid and res["A0_over_valid"] == f"{n_valid}/{n_valid}"
    assert res["n_in_design"] == 24 and res["n_presented"] == 24 - kwargs.get("excluded", 0)
    assert "no verdict" in res["reason"]


def test_g3w_counts_what_was_excluded_and_why():
    out = aw.g3_w(ablated_controls(n_a0=20, excluded=2, unlabeled=1) + preserved_controls())
    assert out["excluded_by_design_reasons"] == {"artifact_digest_mismatch": 2}
    assert out["ablated"]["n_not_presented_by_design"] == 2 and out["ablated"]["n_presented_not_labeled"] == 1
    assert out["ablated"]["A0_over_valid"] == "20/21"


def test_g3w_with_fewer_or_more_than_24_in_the_design_has_no_verdict():
    assert aw.g3_w(ablated_controls(n_a0=23, n=23) + preserved_controls())["ablated"]["status"] == "not_computable"
    assert aw.g3_w(ablated_controls(n_a0=25, n=25) + preserved_controls())["ablated"]["status"] == "not_computable"
    assert aw.g3_w(preserved_controls())["ablated"]["status"] == "not_computable"


def test_g3w_rerun_excluding_listed_controls_never_gives_a_verdict():
    controls = ablated_controls(n_a0=24) + preserved_controls()
    listed = [c.source_cell_id for c in controls if c.kind == "ablated_control"][:8] + [
        controls[-1].source_cell_id]                      # eight ablated and one preserved
    out = aw.g3_w(controls, listed_exclusions=listed)
    sens = out["sensitivity_excluding_listed_controls"]
    assert out["ablated"]["status"] == "pass"             # the unrestricted rule is untouched
    assert sens["ablated"]["status"] == "not_computable" and sens["ablated"]["value"] is None
    assert sens["ablated"]["n_valid"] == 16 and sens["ablated"]["n_unsupported_A0"] == 16
    assert sens["ablated"]["A0_over_valid"] == "16/16" and "no verdict" in sens["ablated"]["reason"]
    assert sens["n_listed"] == 9 and sens["n_listed_matched_ablated"] == 8 and sens["n_listed_matched_preserved"] == 1
    assert sens["preserved"]["n_valid"] == 11
    # even a failing-looking count gets no verdict
    mixed = aw.g3_w(ablated_controls(n_a0=10) + preserved_controls(),
                    listed_exclusions=[f"abl-{i:02d}" for i in range(8)])
    assert mixed["sensitivity_excluding_listed_controls"]["ablated"]["status"] == "not_computable"


def test_g3w_rerun_gives_no_verdict_even_when_it_excludes_no_ablated_control():
    # the list names only preserved controls: all 24 ablated controls are still valid and carry A=0, so the
    # unrestricted rule passes -- but the rerun never gives a verdict
    controls = ablated_controls(n_a0=24) + preserved_controls()
    out = aw.g3_w(controls, listed_exclusions=["pre-00", "pre-01"])
    assert out["ablated"]["status"] == "pass"
    sens = out["sensitivity_excluding_listed_controls"]
    assert sens["n_listed_matched_ablated"] == 0 and sens["n_listed_matched_preserved"] == 2
    assert sens["ablated"]["n_valid"] == 24 and sens["ablated"]["A0_over_valid"] == "24/24"
    assert sens["ablated"]["status"] == "not_computable" and sens["ablated"]["value"] is None
    assert sens["preserved"]["n_valid"] == 10


def test_g3w_listed_ids_may_be_source_or_washout_ids_and_must_match():
    controls = ablated_controls() + preserved_controls()
    by_source = aw.g3_w(controls, listed_exclusions=["abl-00", "abl-01"])
    by_washout = aw.g3_w(controls, listed_exclusions=["w-abl-00", "w-abl-01"])
    assert by_source == by_washout
    with pytest.raises(ValueError, match="match no control"):
        aw.g3_w(controls, listed_exclusions=["abl-00", "nope"])
    already = aw.g3_w(ablated_controls(excluded=2) + preserved_controls(), listed_exclusions=["abl-00", "abl-05"])
    assert already["sensitivity_excluding_listed_controls"]["n_listed_not_presented_anyway"] == 1


def test_g3w_preserved_controls_report_the_a1_count_only():
    out = aw.g3_w(ablated_controls() + preserved_controls(n_a1=9))["preserved"]
    assert out["descriptive_only"] is True and out["n_supported_A1"] == 9 and out["n_unsupported_A0"] == 3
    assert out["A1_over_valid"] == "9/12" and out["n_valid"] == 12
    assert "status" not in out


# ---------------------------------------------------------------------------
# 6b. the washout by AI use (PREREG D20): descriptive, never a gate
# ---------------------------------------------------------------------------
def d20_fixture():
    """Fourteen primary cells with a hand-made AI-use classification.  Columns: id, CQ cluster, design stratum,
    weight, AH L1, washout L1, AH A, washout A, group, ticked, tool."""
    spec = [
        ("y1", "k1", "proportional", 1, 0, 0, 0, 0, "yes", True, "chatgpt"),
        ("y2", "k1", "proportional", 1, 1, 1, 1, 1, "yes", False, "chatgpt"),
        ("y3", "k2", "proportional", 2, 2, 3, 1, 1, "yes", False, "chatgpt"),
        ("y4", "k3", "enriched", 4, 3, 3, 1, 0, "yes", False, "chatgpt"),
        ("y5", "k2", "enriched", 1, 1, 0, 0, 0, "yes", True, "claude"),
        ("y6", "k4", "proportional", 1, 2, 2, 1, 1, "yes", False, "claude"),
        ("y7", "k4", "proportional", 1, 3, 2, 1, 1, "yes", False, "claude"),
        ("y8", "k5", "enriched", 2, 2, 2, 1, 1, "yes", True, aw.TOOL_NO_YES_REPORT),
        ("n1", "k6", "proportional", 1, 0, 1, 0, 1, "no", False, None),
        ("n2", "k7", "proportional", 1, 1, 1, 0, 0, "no", False, None),
        ("n3", "k8", "enriched", 2, 2, 2, 1, 1, "no", False, None),
        ("n4", "k9", "proportional", 1, 3, 2, 1, 1, "no", False, None),
        ("r1", "k10", "proportional", 1, 1, 1, 1, 1, "not recorded", False, None),
        ("r2", "k11", "enriched", 2, 1, 1, 0, 0, "not recorded", False, None),
    ]
    cells = [wcell(i, cl, st, w, x, y, a0, a1) for i, cl, st, w, x, y, a0, a1, *_ in spec]
    ai = {i: aw.AiUse(g, tick, tool, "tick" if tick else ("none" if g == "not recorded" else "sitting_report"))
          for i, *_, g, tick, tool in spec}
    return cells, ai


def exact_group_qwk(cells, weighted):
    """QWK of a group's cells in exact arithmetic (None where E = 0)."""
    try:
        return float(frac_qwk([c.ah_l1 for c in cells], [c.wo_l1 for c in cells],
                              [c.w for c in cells] if weighted else None))
    except ZeroDivisionError:
        return None


def oracle_group_interval(cells, weighted, B):
    """The independent BCa interval (sec.12.4 policy) of a group's QWK over the group's own CQ clusters."""
    by = {}
    for c in cells:
        by.setdefault(c.cluster_id, []).append((c.ah_l1, c.wo_l1, c.w))

    def stat(items):
        try:
            return float(frac_qwk([i[0] for i in items], [i[1] for i in items],
                                  [i[2] for i in items] if weighted else None))
        except ZeroDivisionError:
            return None

    return oracle_dropping_interval([by[k] for k in sorted(by)], stat, SEED, B)


def test_ai_use_stratified_qwk_by_hand_and_against_exact_fractions():
    cells, ai = d20_fixture()
    res = aw.ai_use_stratified_results(cells, ai, seed=SEED, B=SMALL_B)
    # group "no", worked by hand.  Pairs (AH, washout): (0,1) w1, (1,1) w1, (2,2) w2, (3,2) w1.
    #   unweighted: O = 1 + 1 = 2; row sums 1,1,1,1 and column sums 0,2,2,0 give E = 24/4 = 6; QWK = 1 - 2/6 = 2/3
    #   weighted:   O = 2; row sums 1,1,2,1 and column sums 0,2,3,0 over W = 5 give E = 32/5; QWK_w = 1 - 2/(32/5) = 11/16
    no = res["by_ai_use"]["no"]
    assert (no["n_cells"], no["n_clusters"]) == (4, 4)
    assert no["G2_quantity"]["qwk_unweighted"]["qwk"] == pytest.approx(2 / 3, abs=1e-14)
    assert no["G2_quantity"]["qwk_weighted"]["qwk"] == pytest.approx(11 / 16, abs=1e-14)
    assert no["weights"]["sum_of_weights"] == 5.0 and no["weights"]["kish_n_eff"] == pytest.approx(25 / 7)
    # tool "chatgpt" (y1..y4): pairs (0,0) w1, (1,1) w1, (2,3) w2, (3,3) w4: unweighted 1 - 1/12 = 11/12,
    # weighted O = 2, E = 154/8: 1 - 8/77 = 69/77
    chat = {x["tool"]: x for x in res["by_tool_among_yes_cells"]}["chatgpt"]["block"]
    assert chat["G2_quantity"]["qwk_unweighted"]["qwk"] == pytest.approx(11 / 12, abs=1e-14)
    assert chat["G2_quantity"]["qwk_weighted"]["qwk"] == pytest.approx(69 / 77, abs=1e-14)
    # tool "claude" (y5..y7): pairs (1,0), (2,2), (3,2), all weight 1: O = 2, E = 18/3 = 6, QWK = 2/3 either way
    claude = {x["tool"]: x for x in res["by_tool_among_yes_cells"]}["claude"]["block"]
    assert claude["G2_quantity"]["qwk_unweighted"]["qwk"] == pytest.approx(2 / 3, abs=1e-14)
    assert claude["G2_quantity"]["qwk_weighted"]["qwk"] == pytest.approx(2 / 3, abs=1e-14)
    assert (claude["n_cells"], claude["n_clusters"]) == (3, 2)
    # tick only, the ticked cells y1 (0,0) w1, y5 (1,0) w1, y8 (2,2) w2: unweighted O = 1, E = 15/3: 4/5;
    # weighted O = 1, E = 28/4 = 7: 6/7
    tk = res["by_ai_use_tick_only"]["ticked"]
    assert (tk["n_cells"], tk["n_clusters"]) == (3, 3)
    assert tk["G2_quantity"]["qwk_unweighted"]["qwk"] == pytest.approx(4 / 5, abs=1e-14)
    assert tk["G2_quantity"]["qwk_weighted"]["qwk"] == pytest.approx(6 / 7, abs=1e-14)

    # every other group against the exact-fraction restatement of the definition
    parts = {("by_ai_use", g): [c for c in cells if ai[c.cell_id].group == g] for g in ("yes", "no", "not recorded")}
    parts.update({("by_ai_use_tick_only", "ticked"): [c for c in cells if ai[c.cell_id].ticked],
                  ("by_ai_use_tick_only", "not ticked"): [c for c in cells if not ai[c.cell_id].ticked]})
    n_computed = 0
    for (family, g), sub in parts.items():
        block = res[family][g]
        assert (block["n_cells"], block["n_clusters"]) == (len(sub), len({c.cluster_id for c in sub})), (family, g)
        q = block["G2_quantity"]
        want_w, want_u = exact_group_qwk(sub, True), exact_group_qwk(sub, False)
        if want_w is None or block["n_clusters"] < 2:
            assert q["status"] == "not_computable" and "qwk_weighted" not in q, (family, g)
            continue
        assert q["status"] == "computed", (family, g)
        assert q["qwk_weighted"]["qwk"] == pytest.approx(want_w, abs=1e-12), (family, g)
        assert q["qwk_unweighted"]["qwk"] == pytest.approx(want_u, abs=1e-12), (family, g)
        n_computed += 1
    assert n_computed == 4                       # yes, no, ticked, not ticked; "not recorded" has E = 0


def test_ai_use_stratified_intervals_are_the_independent_bca_over_the_groups_own_clusters():
    cells, ai = d20_fixture()
    B = 600
    res = aw.ai_use_stratified_results(cells, ai, seed=SEED, B=B)
    checked = 0
    groups = [("yes", [c for c in cells if ai[c.cell_id].group == "yes"], res["by_ai_use"]["yes"]),
              ("no", [c for c in cells if ai[c.cell_id].group == "no"], res["by_ai_use"]["no"]),
              ("ticked", [c for c in cells if ai[c.cell_id].ticked], res["by_ai_use_tick_only"]["ticked"]),
              ("not ticked", [c for c in cells if not ai[c.cell_id].ticked], res["by_ai_use_tick_only"]["not ticked"])]
    for tool in ("chatgpt", "claude"):
        groups.append((tool, [c for c in cells if ai[c.cell_id].tool == tool],
                       {x["tool"]: x for x in res["by_tool_among_yes_cells"]}[tool]["block"]))
    for name, sub, block in groups:
        for key, weighted in (("qwk_weighted", True), ("qwk_unweighted", False)):
            got = block["G2_quantity"][key]
            want = oracle_group_interval(sub, weighted, B)
            assert got["resamples"] == B and got["n_clusters"] == len({c.cluster_id for c in sub}), (name, key)
            assert got["undefined_replicate_policy"] == "dropped", (name, key)
            assert got["n_undefined_replicates"] == want["n_undefined"], (name, key)
            assert got["n_undefined_jackknife_samples"] == want["n_jack_undefined"], (name, key)
            assert (got["ci_lo"], got["ci_hi"]) == pytest.approx((want["lo"], want["hi"]), abs=1e-9), (name, key)
            checked += 1
    assert checked == 12                         # six groups, the weighted and the unweighted QWK each


def test_ai_use_stratified_group_too_small_to_estimate_is_not_computable_with_its_n():
    assert aw.D20_MIN_CLUSTERS == 2
    cells, ai = d20_fixture()
    res = aw.ai_use_stratified_results(cells, ai, seed=SEED, B=SMALL_B)
    # "not recorded": two cells in two clusters that both sit on level 1 in both passes, so E = 0: the QWK is 0/0
    nr = res["by_ai_use"]["not recorded"]
    assert (nr["n_cells"], nr["n_clusters"]) == (2, 2)
    assert nr["G2_quantity"] == {"status": "not_computable", "reason": aw.UNDEFINED_REASONS["qwk"],
                                 "n_cells": 2, "n_clusters": 2}
    # its binary A agreement is still reported: two cells, both agreeing
    a = nr["A_agreement_between_passes"]
    assert a["status"] == "computed" and a["reweighted_pooled"]["raw_agreement"]["estimate"] == 1.0
    # a one-cell group is not computable even where its QWK is defined: y5 alone is (AH 1, washout 0), E = 1, QWK = 0
    assert exact_group_qwk([c for c in cells if c.cell_id == "y5"], False) == 0.0
    cl = "the group covers 1 CQ cluster: the cluster resampling needs at least 2"
    ticked_claude = {x["tool"]: x for x in res["by_tool_among_ticked_cells"]}["claude"]["block"]
    assert ticked_claude["G2_quantity"] == {"status": "not_computable", "reason": cl, "n_cells": 1, "n_clusters": 1}
    assert ticked_claude["A_agreement_between_passes"] == {"status": "not_computable", "reason": cl,
                                                           "n_cells": 1, "n_clusters": 1}
    assert [(x["tool"], x["n_cells"], x["block"]["G2_quantity"]["status"]) for x in res["by_tool_among_ticked_cells"]] == [
        (aw.TOOL_NO_YES_REPORT, 1, "not_computable"), ("chatgpt", 1, "not_computable"), ("claude", 1, "not_computable")]
    one = {x["tool"]: x for x in res["by_tool_among_yes_cells"]}[aw.TOOL_NO_YES_REPORT]
    assert one["n_cells"] == 1 and one["block"]["G2_quantity"]["reason"] == cl
    # one CQ cluster with several cells is not computable either: y1 and y2 are both in k1, and their QWK is 1
    ai2 = {i: aw.AiUse("yes" if i in ("y1", "y2") else "no", False, "x" if i in ("y1", "y2") else None, "sitting_report")
           for i in ai}
    two = aw.ai_use_stratified_results(cells, ai2, seed=SEED, B=SMALL_B)
    assert exact_group_qwk([c for c in cells if c.cell_id in ("y1", "y2")], False) == 1.0
    assert two["by_ai_use"]["yes"]["G2_quantity"] == {
        "status": "not_computable", "n_cells": 2, "n_clusters": 1,
        "reason": "the group covers 1 CQ cluster: the cluster resampling needs at least 2"}
    assert two["by_ai_use"]["no"]["G2_quantity"]["status"] == "computed"        # the other twelve cells
    # a group with no cell at all
    empty = aw.ai_use_stratified_results(cells, {i: aw.AiUse("yes", False, "x", "sitting_report") for i in ai},
                                         seed=SEED, B=SMALL_B)
    stub = {"status": "not_computable", "reason": "no cell in this group", "n_cells": 0, "n_clusters": 0}
    assert empty["by_ai_use"]["no"] == {"n_cells": 0, "n_clusters": 0, "G2_quantity": stub,
                                        "A_agreement_between_passes": stub}
    assert empty["by_ai_use"]["yes"]["n_cells"] == 14 and empty["by_ai_use_tick_only"]["ticked"]["n_cells"] == 0
    # a group of two clusters is computed: point estimates, and an interval where one can be made
    claude = {x["tool"]: x for x in res["by_tool_among_yes_cells"]}["claude"]["block"]["G2_quantity"]
    assert claude["status"] == "computed" and (claude["n_cells"], claude["n_clusters"]) == (3, 2)
    assert claude["qwk_weighted"]["ci_status"] in ("computed", "computed_without_undefined_replicates")


def test_ai_use_stratified_binary_a_agreement_by_group_by_hand():
    cells, ai = d20_fixture()
    res = aw.ai_use_stratified_results(cells, ai, seed=SEED, B=SMALL_B)
    a = res["by_ai_use"]["no"]["A_agreement_between_passes"]
    # group "no": n1 (prop, AH 0, washout 1), n2 (prop, 0, 0), n3 (enr, 1, 1) with weight 2, n4 (prop, 1, 1)
    assert a["per_stratum"]["proportional"]["table"] == {"n11": 1, "n10": 0, "n01": 1, "n00": 1}
    assert a["per_stratum"]["enriched"]["table"] == {"n11": 1, "n10": 0, "n01": 0, "n00": 0}
    pooled = a["reweighted_pooled"]
    assert pooled["weighted_table"] == {"n11": 3.0, "n10": 0.0, "n01": 1.0, "n00": 1.0}
    # raw agreement 4/5; kappa: p_o = 4/5, p_e = (3/5)(4/5) + (2/5)(1/5) = 14/25, kappa = (4/5 - 14/25)/(11/25) = 6/11
    assert pooled["raw_agreement"]["estimate"] == pytest.approx(4 / 5, abs=1e-14)
    assert pooled["cohen_kappa"]["estimate"] == pytest.approx(6 / 11, abs=1e-14)
    assert "unweighted_pooled" not in a and set(a) == {"status", "descriptive_only", "table_orientation",
                                                       "per_stratum", "reweighted_pooled"}
    # it is the main block's function on the group's cells
    sub = [c for c in cells if ai[c.cell_id].group == "no"]
    assert a["status"] == "computed"
    assert {k: v for k, v in a.items() if k != "status"} == aw.a_agreement_between_passes(sub, seed=SEED, B=SMALL_B)
    # the group "not recorded": both agree in their own stratum: weighted pooled kappa 1
    nr = res["by_ai_use"]["not recorded"]["A_agreement_between_passes"]
    assert nr["per_stratum"]["proportional"]["table"] == {"n11": 1, "n10": 0, "n01": 0, "n00": 0}
    assert nr["reweighted_pooled"]["weighted_table"] == {"n11": 1.0, "n10": 0.0, "n01": 0.0, "n00": 2.0}
    assert nr["reweighted_pooled"]["cohen_kappa"]["estimate"] == pytest.approx(1.0)
    # the same function gives the tool and tick-only groups their blocks
    def without_status(block):
        return {k: v for k, v in block.items() if k != "status"}

    chat = [c for c in cells if ai[c.cell_id].tool == "chatgpt"]
    assert without_status({x["tool"]: x for x in res["by_tool_among_yes_cells"]}["chatgpt"]["block"][
        "A_agreement_between_passes"]) == aw.a_agreement_between_passes(chat, seed=SEED, B=SMALL_B)
    ticked = [c for c in cells if ai[c.cell_id].ticked]
    assert without_status(res["by_ai_use_tick_only"]["ticked"]["A_agreement_between_passes"]) == \
        aw.a_agreement_between_passes(ticked, seed=SEED, B=SMALL_B)


def test_ai_use_stratified_groups_partition_the_cells_and_the_tool_groups_partition_their_group():
    cells, ai = d20_fixture()
    res = aw.ai_use_stratified_results(cells, ai, seed=SEED, B=SMALL_B)
    assert [res["by_ai_use"][g]["n_cells"] for g in ("yes", "no", "not recorded")] == [8, 4, 2]
    assert [res["by_ai_use"][g]["n_clusters"] for g in ("yes", "no", "not recorded")] == [5, 4, 2]
    assert sum(res["by_ai_use"][g]["n_cells"] for g in res["by_ai_use"]) == len(cells)
    assert [res["by_ai_use_tick_only"][g]["n_cells"] for g in ("ticked", "not ticked")] == [3, 11]
    assert res["by_ai_use_tick_only"]["not ticked"]["n_clusters"] == 10
    assert [(x["tool"], x["n_cells"]) for x in res["by_tool_among_yes_cells"]] == [
        (aw.TOOL_NO_YES_REPORT, 1), ("chatgpt", 4), ("claude", 3)]
    assert sum(x["n_cells"] for x in res["by_tool_among_yes_cells"]) == res["by_ai_use"]["yes"]["n_cells"]
    assert sum(x["n_cells"] for x in res["by_tool_among_ticked_cells"]) == res["by_ai_use_tick_only"]["ticked"]["n_cells"]
    for x in res["by_tool_among_yes_cells"] + res["by_tool_among_ticked_cells"]:
        assert x["block"]["n_cells"] == x["n_cells"]
    # a cell with no classification is "not recorded" and "not ticked"; no information at all: no tool groups
    none = aw.ai_use_stratified_results(cells, None, seed=SEED, B=SMALL_B)
    assert [none["by_ai_use"][g]["n_cells"] for g in ("yes", "no", "not recorded")] == [0, 0, 14]
    assert [none["by_ai_use_tick_only"][g]["n_cells"] for g in ("ticked", "not ticked")] == [0, 14]
    assert none["by_tool_among_yes_cells"] == [] and none["by_tool_among_ticked_cells"] == []


def test_ai_use_stratified_group_qwk_excludes_e_zero_resamples_where_g2_counts_them_as_zero():
    spec = mostly_constant_spec()
    cells, n = [], 0
    for cl in sorted(spec):
        for x, y in spec[cl]:
            cells.append(wcell(f"m{n:02d}", cl, "proportional" if n % 2 else "enriched", 1.0, x, y))
            n += 1
    ai = {c.cell_id: aw.AiUse("yes", False, "chatgpt", "sitting_report") for c in cells}
    B = 3000
    res = aw.ai_use_stratified_results(cells, ai, seed=SEED, B=B)
    q = res["by_ai_use"]["yes"]["G2_quantity"]["qwk_weighted"]
    want = oracle_group_interval(cells, True, B)
    assert B * 0.05 < want["n_undefined"] < B / 2
    assert q["undefined_replicate_policy"] == "dropped" and q["n_undefined_replicates"] == want["n_undefined"]
    assert q["ci_status"] == "computed_without_undefined_replicates" and q["ci_lo"] > 0.5
    assert (q["ci_lo"], q["ci_hi"]) == pytest.approx((want["lo"], want["hi"]), abs=1e-9)
    # G2's own rule on the same cells puts the undefined resamples at 0 and the lower end at 0: not used for a group
    g2 = aw.g2_analysis(cells, seed=SEED, B=B)["estimates"]["reweighted_pooled"]
    assert g2["undefined_replicate_policy"] == "set_to_0" and g2["ci_lo"] == 0.0


def test_ai_use_stratified_block_is_labelled_d20_and_descriptive_and_carries_no_verdict():
    cells, ai = d20_fixture()
    res = aw.ai_use_stratified_results(cells, ai, seed=SEED, B=SMALL_B)
    assert res["label"] == "descriptive; not a gate" and res["decision_input"] is False
    assert "D20" in res["prereg"] and "by tool" in res["prereg"] and "not recorded" in res["prereg"]
    assert "not a gate" in res["notes"][0]
    assert any("sec.12.4 rule" in s and "NOT set to 0" in s for s in res["notes"])
    assert any("1/pi_i" in s and "domain estimate" in s for s in res["notes"])
    assert any("no minimum group size" in s for s in res["notes"])
    assert set(res["quantities"]) == {"G2_quantity", "A_agreement_between_passes"}
    assert set(res["group_meaning"]) == {"yes", "no", "not recorded"} and set(res["tick_only_meaning"]) == {"ticked", "not ticked"}
    text = json.dumps(res)
    assert '"pass"' not in text and '"fail"' not in text and "meets" not in text      # no gate verdict anywhere
    assert aw.scan_forbidden_wording(aw._text_for_wording_scan({"ai_use_stratified": res})) == []
    # the inputs are not changed and G2 does not depend on this block
    before = aw.g2_analysis(cells, seed=SEED, B=SMALL_B)
    aw.ai_use_stratified_results(cells, ai, seed=SEED, B=SMALL_B)
    assert aw.g2_analysis(cells, seed=SEED, B=SMALL_B) == before


def test_module_docstring_describes_the_washout_by_ai_use():
    doc = aw.__doc__
    for token in ("ai_use_stratified", "descriptive; not a gate", "D20", "THE GROUP'S OWN CQ clusters",
                  "EXCLUDED and counted (the sec.12.4 rule), NOT set to 0", "not_computable"):
        assert token in doc, token
    assert "counts-only block" not in doc


# ---------------------------------------------------------------------------
# 7. dwell check and sessions
# ---------------------------------------------------------------------------
T0 = datetime.datetime(2026, 11, 8, 9, 0, 0, tzinfo=datetime.timezone(datetime.timedelta(hours=9)))


def write_audit(path, saves):
    """saves: dicts with cell_id, elapsed_s (None allowed), session_id[, minutes or ts][, extra]."""
    lines = []
    for n, s in enumerate(saves):
        rec = {"ts": s.get("ts") or (T0 + datetime.timedelta(minutes=s.get("minutes", n))).isoformat(timespec="seconds"),
               "cell_id": s["cell_id"], "row": n + 1, "A": 1, "span_chars": 0, "rater_L1": "2",
               "first_opened_ts": None, "elapsed_s": s.get("elapsed_s"),
               "session_id": s.get("session_id", "S1"), **s.get("extra", {})}
        if s.get("blank_before"):
            lines.append("")                      # a blank line: the audit line index still counts it
        lines.append(json.dumps(rec))
    path.write_text("\n".join(lines) + "\n")
    return ah.load_label_audit(path)


def test_dwell_hand_values_median_iqr_and_the_share(tmp_path):
    # totals 10, 20, ..., 90: only 10 is under 20 s (20 is not).  Linear quartiles: 30, 50, 70.
    ids = [f"d{i}" for i in range(9)]
    audit = write_audit(tmp_path / "a.jsonl", [{"cell_id": c, "elapsed_s": 10.0 * (i + 1)} for i, c in enumerate(ids)])
    out = aw.dwell_stats(ids, audit)
    assert out["n_under_20s"] == 1 and out["share_under_20s"] == pytest.approx(1 / 9)
    assert (out["q1_s"], out["median_s"], out["q3_s"], out["iqr_s"]) == (30.0, 50.0, 70.0, 40.0)
    assert out["fast_share_limit"] == 0.03 and out["meets_fast_share_limit"] is False
    assert out["cells_dropped"] == 0 and out["n_cells"] == 9 and out["n_unknown_dwell"] == 0


def test_dwell_uses_the_total_over_all_saves_of_a_cell(tmp_path):
    audit = write_audit(tmp_path / "a.jsonl", [
        {"cell_id": "a", "elapsed_s": 12.0}, {"cell_id": "a", "elapsed_s": 11.0},     # 23 s in total: not fast
        {"cell_id": "b", "elapsed_s": 8.0}, {"cell_id": "b", "elapsed_s": 9.0}])      # 17 s in total: fast
    out = aw.dwell_stats(["a", "b"], audit)
    assert out["n_under_20s"] == 1 and out["share_under_20s"] == 0.5 and out["median_s"] == pytest.approx(20.0)


def test_dwell_keeps_cells_with_unknown_dwell_and_widens_the_bounds(tmp_path):
    audit = write_audit(tmp_path / "a.jsonl", [
        {"cell_id": "known_fast", "elapsed_s": 5.0},
        {"cell_id": "partial_short", "elapsed_s": 15.0}, {"cell_id": "partial_short", "elapsed_s": None},
        {"cell_id": "partial_long", "elapsed_s": 25.0}, {"cell_id": "partial_long", "elapsed_s": None},
        {"cell_id": "slow", "elapsed_s": 60.0}])
    ids = ["known_fast", "partial_short", "partial_long", "slow", "no_record"]
    out = aw.dwell_stats(ids, audit)
    assert out["n_cells"] == 5 and out["cells_dropped"] == 0
    assert out["n_under_20s"] == 1 and out["n_unknown_dwell"] == 2          # partial_short, no_record
    assert out["n_without_audit_record"] == 1 and out["n_20s_or_more"] == 2  # partial_long (>= 20 s known), slow
    assert out["share_under_20s"] is None and out["share_under_20s_bounds"] == [0.2, 0.6]
    assert out["meets_fast_share_limit"] is False
    assert out["n_cells_with_known_total"] == 2 and out["median_s"] == pytest.approx(32.5)


@pytest.mark.parametrize("n_cells,n_fast,meets", [
    (72, 2, True),        # 2/72 = 2.78% < 3%
    (72, 3, False),       # 3/72 = 4.17%
    (100, 2, True),
    (100, 3, False),      # exactly 3% is not strictly below
    (72, 0, True),
])
def test_dwell_limit_is_strictly_below_three_percent(tmp_path, n_cells, n_fast, meets):
    ids = [f"c{i}" for i in range(n_cells)]
    saves = [{"cell_id": c, "elapsed_s": 5.0 if i < n_fast else 40.0, "minutes": i} for i, c in enumerate(ids)]
    out = aw.dwell_stats(ids, write_audit(tmp_path / "a.jsonl", saves))
    assert out["n_under_20s"] == n_fast and out["meets_fast_share_limit"] is meets
    assert out["n_cells"] == n_cells and out["cells_dropped"] == 0


def test_dwell_cannot_be_computed_without_an_audit_and_never_silently_zero():
    out = aw.dwell_stats(["a", "b"], None)
    assert out["status"] == "not_computable" and "share_under_20s" not in out and out["cells_dropped"] == 0


def test_dwell_report_does_not_change_g2_and_drops_nothing(tmp_path):
    cells = hand_cells()
    ids = [c.cell_id for c in cells]
    audit = write_audit(tmp_path / "a.jsonl", [{"cell_id": c, "elapsed_s": 3.0} for c in ids])      # all fast
    before = aw.g2_analysis(cells, seed=SEED, B=SMALL_B)
    check = aw.dwell_check(ids, audit)
    after = aw.g2_analysis(cells, seed=SEED, B=SMALL_B)
    assert check["primary_cells"]["meets_fast_share_limit"] is False and check["primary_cells"]["n_cells"] == 10
    assert before == after and after["n_primary_cells"] == 10


def audit_and_extras(tmp_path, saves, name="p.jsonl"):
    audit = write_audit(tmp_path / name, saves)
    return audit, aw.load_audit_extras(tmp_path / name)


def test_audit_extras_read_sitting_ids_ticks_and_dwell_by_line_index(tmp_path):
    saves = [{"cell_id": "a", "extra": {"sitting_id": "S1-s1", "ai_used": True, "dwell_ms": 1500}},       # line 0
             {"cell_id": "b", "blank_before": True, "extra": {"sitting_id": 7, "dwell_ms": 0}},            # line 1 blank, 2
             {"cell_id": "c", "extra": {"sitting_id": "", "ai_used": ""}},                                 # line 3: blank = absent
             {"cell_id": "d", "extra": {"sitting_id": True, "ai_used": None}}]                             # line 4: a bool is no id
    _, extras = audit_and_extras(tmp_path, saves)
    assert extras.sitting_ids == {0: "S1-s1", 2: "7"}
    assert extras.ai_flags == {0: "yes"} and extras.dwell_ms == {0: 1500, 2: 0} and extras.n_dwell_ms_unusable == 0


def test_dwell_prefers_dwell_ms_to_elapsed_s_and_records_the_basis(tmp_path):
    saves = [{"cell_id": c, "elapsed_s": 500.0, "extra": {"dwell_ms": ms}}
             for c, ms in (("a", 12_345), ("b", 45_000), ("c", 19_999), ("d", 20_000))]
    audit, extras = audit_and_extras(tmp_path, saves)
    out = aw.dwell_stats(["a", "b", "c", "d"], audit, extras)
    # elapsed_s (500 s on every save: a clock skew) is not used; dwell_ms / 1000 is: 12.345, 45, 19.999 and 20.000 s
    assert out["basis_used"] == "dwell_ms" and out["saves_by_basis"] == {"dwell_ms": 4, "elapsed_s": 0, "none": 0}
    assert (out["n_under_20s"], out["n_20s_or_more"], out["share_under_20s"]) == (2, 2, 0.5)
    assert out["median_s"] == pytest.approx(float(np.median([12.345, 45.0, 19.999, 20.0])))
    assert "dwell_ms" in out["basis"] and out["n_dwell_ms_unusable"] == 0
    # an AH-mode audit (no extras) falls back to elapsed_s, and says so
    plain = aw.dwell_stats(["a", "b", "c", "d"], audit)
    assert plain["basis_used"] == "elapsed_s" and plain["n_under_20s"] == 0 and plain["median_s"] == 500.0
    assert plain["saves_by_basis"] == {"dwell_ms": 0, "elapsed_s": 4, "none": 0}


def test_dwell_total_is_the_sum_over_saves_with_the_basis_chosen_per_save(tmp_path):
    saves = [
        {"cell_id": "a", "elapsed_s": 900.0, "extra": {"dwell_ms": 10_000}},
        {"cell_id": "a", "elapsed_s": 900.0, "extra": {"dwell_ms": 9_999}},        # 19.999 s in total: fast
        {"cell_id": "b", "elapsed_s": 900.0, "extra": {"dwell_ms": 10_000}},
        {"cell_id": "b", "elapsed_s": 900.0, "extra": {"dwell_ms": 10_000}},       # 20.000 s in total: not fast
        {"cell_id": "c", "elapsed_s": 25.0},                                       # an AH-mode save: elapsed_s
        {"cell_id": "d", "elapsed_s": 800.0, "extra": {"dwell_ms": 4_000}},
        {"cell_id": "d", "elapsed_s": 11.0},                                       # mixed within a cell: 4 + 11 = 15 s
    ]
    audit, extras = audit_and_extras(tmp_path, saves)
    out = aw.dwell_stats(list("abcd"), audit, extras)
    assert out["saves_by_basis"] == {"dwell_ms": 5, "elapsed_s": 2, "none": 0} and out["basis_used"] == "mixed"
    assert (out["n_under_20s"], out["n_20s_or_more"]) == (2, 2)                    # a, d fast; b (20.0), c (25) not
    assert out["median_s"] == pytest.approx(float(np.median([19.999, 20.0, 25.0, 15.0])))


def test_unusable_dwell_ms_falls_back_to_elapsed_s_and_is_counted(tmp_path):
    bad = [-5, 12.5, "9000", True, [1]]
    saves = [{"cell_id": f"c{i}", "elapsed_s": 30.0, "extra": {"dwell_ms": v}} for i, v in enumerate(bad)]
    saves += [{"cell_id": "ok", "elapsed_s": 30.0, "extra": {"dwell_ms": 40_000}},
              {"cell_id": "absent", "elapsed_s": 30.0, "extra": {"dwell_ms": None}}]
    audit, extras = audit_and_extras(tmp_path, saves)
    assert extras.dwell_ms == {5: 40_000} and extras.n_dwell_ms_unusable == 5
    out = aw.dwell_stats([f"c{i}" for i in range(5)] + ["ok", "absent"], audit, extras)
    assert out["n_dwell_ms_unusable"] == 5 and out["saves_by_basis"] == {"dwell_ms": 1, "elapsed_s": 6, "none": 0}
    assert out["basis_used"] == "mixed" and out["n_under_20s"] == 0


def test_a_save_with_neither_dwell_ms_nor_elapsed_s_is_unknown_not_zero(tmp_path):
    saves = [{"cell_id": "x", "elapsed_s": None, "extra": {"dwell_ms": None}},
             {"cell_id": "y", "elapsed_s": None, "extra": {"dwell_ms": 30_000}}]
    audit, extras = audit_and_extras(tmp_path, saves)
    out = aw.dwell_stats(["x", "y"], audit, extras)
    assert out["saves_by_basis"] == {"dwell_ms": 1, "elapsed_s": 0, "none": 1} and out["n_unknown_dwell"] == 1
    assert out["share_under_20s"] is None and out["share_under_20s_bounds"] == [0.0, 0.5]
    assert out["meets_fast_share_limit"] is None and out["cells_dropped"] == 0


AH_LAST = "2026-10-08T23:58:55+09:00"        # = 2026-10-08T14:58:55Z, the registered last save of the AH pass


@pytest.mark.parametrize("first_save,days,minimum,target", [
    ("2026-11-05T14:58:55+00:00", 28.0, True, True),                  # exactly the 28-day target
    ("2026-11-05T23:58:55+09:00", 28.0, True, True),                  # the same instant written in +09:00
    ("2026-11-05T14:58:54+00:00", 28 - 1 / 86400, True, False),       # one second short of the target
    ("2026-10-29T14:58:55+00:00", 21.0, True, False),                 # exactly the 21-day minimum
    ("2026-10-29T14:58:54+00:00", 21 - 1 / 86400, False, False),      # one second short of the minimum
    ("2026-10-09T14:58:55+00:00", 1.0, False, False),                 # a gap far under the minimum is still reported
])
def test_washout_gap_days_are_exact_and_flag_the_21_and_28_day_boundaries(tmp_path, first_save, days, minimum, target):
    audit = write_audit(tmp_path / "a.jsonl", [{"cell_id": "w1", "ts": first_save, "elapsed_s": 5.0}])
    out = aw.washout_gap_report(audit, ["w1"])
    assert out["status"] == "computed" and out["gap_days"] == pytest.approx(days, abs=1e-12)
    assert out["meets_registered_minimum"] is minimum and out["meets_target"] is target
    assert out["ah_last_save"] == AH_LAST and out["ah_last_save_utc"] == "2026-10-08T14:58:55+00:00"
    assert (out["registered_minimum_days"], out["target_days"]) == (21, 28)


def test_washout_gap_uses_the_earliest_save_of_any_design_row_and_ignores_other_cells(tmp_path):
    audit = write_audit(tmp_path / "a.jsonl", [
        {"cell_id": "p1", "ts": "2026-11-20T10:00:00+09:00", "elapsed_s": 5.0},
        {"cell_id": "ctl", "ts": "2026-11-15T10:00:00+09:00", "elapsed_s": 5.0},
        {"cell_id": "ctl", "ts": "2026-11-12T10:00:00+09:00", "elapsed_s": 5.0},      # a control, an earlier save: counts
        {"cell_id": "ah_cell", "ts": "2026-10-09T10:00:00+09:00", "elapsed_s": 5.0}])  # not a design row: ignored
    out = aw.washout_gap_report(audit, ["p1", "ctl"])
    assert out["first_washout_save_utc"] == "2026-11-12T01:00:00+00:00"
    # 2026-10-08T14:58:55Z -> 2026-11-12T01:00:00Z = 34 days 10:01:05
    assert out["gap_days"] == pytest.approx(34 + (10 * 3600 + 60 + 5) / 86400, abs=1e-12)
    assert out["ah_last_save_source"].startswith("registered")


def test_washout_gap_can_be_measured_from_another_last_save_and_refuses_a_time_without_an_offset(tmp_path):
    audit = write_audit(tmp_path / "a.jsonl", [{"cell_id": "w1", "ts": "2026-11-08T09:00:00+09:00", "elapsed_s": 5.0}])
    out = aw.washout_gap_report(audit, ["w1"], ah_last_save="2026-10-20T00:00:00+00:00", source="--ah-last-save")
    assert out["gap_days"] == pytest.approx(19.0) and out["meets_registered_minimum"] is False
    assert out["ah_last_save_source"] == "--ah-last-save"
    for bad in ("2026-10-20T00:00:00", "yesterday", ""):
        with pytest.raises(ValueError, match="explicit UTC offset"):
            aw.washout_gap_report(audit, ["w1"], ah_last_save=bad)


def test_washout_gap_is_not_computable_without_an_audit_or_a_save_of_a_design_row(tmp_path):
    out = aw.washout_gap_report(None, ["w1"])
    assert out["status"] == "not_computable" and "no --audit" in out["reason"] and "gap_days" not in out
    audit = write_audit(tmp_path / "a.jsonl", [{"cell_id": "other", "elapsed_s": 5.0}])
    out = aw.washout_gap_report(audit, ["w1"])
    assert out["status"] == "not_computable" and "no save" in out["reason"] and "gap_days" not in out


def write_log(path, lines):
    path.write_text("\n".join(lines) + "\n")
    records, meta = aw.load_session_log(path)
    return records, meta


def test_sessions_counts_start_and_end_times_in_utc(tmp_path):
    records, meta = write_log(tmp_path / "log.txt", [
        "SESSION start=2026-11-08T09:00:00+09:00 pid=11 session_id=S1",
        "EDIT x 1->0 reason=typo ts=2026-11-08T09:30:00+09:00",
        "SESSION end=2026-11-08T10:00:00+09:00 pid=11 saved=3",
        "SESSION start=2026-11-09T09:00:00+09:00 pid=22 session_id=S2",       # never ended
        "SESSION start=2026-11-10T09:00:00+09:00 pid=33 session_id=S3",       # no saves
        "SESSION end=2026-11-10T09:05:00+09:00 pid=33 saved=0",
        "SESSION end=2026-11-11T09:05:00+09:00 pid=99 saved=0",               # an end line without a start
        "garbage line"])
    assert meta["n_session_starts"] == 3 and meta["n_edit_lines"] == 1 and meta["n_unparsed_lines"] == 1
    assert meta["n_end_lines_without_start"] == 1 and meta["n_starts_without_end"] == 1
    audit = write_audit(tmp_path / "a.jsonl", [
        {"cell_id": "a", "elapsed_s": 30.0, "session_id": "S1", "minutes": 5},
        {"cell_id": "b", "elapsed_s": 30.0, "session_id": "S1", "minutes": 10},
        {"cell_id": "c", "elapsed_s": 30.0, "session_id": "S2", "minutes": 24 * 60 + 5},
        {"cell_id": "z", "elapsed_s": 30.0, "session_id": "S1", "minutes": 11}])        # not one of ours
    out = aw.session_summary(["a", "b", "c"], audit, records)
    assert out["n_sessions"] == 3 and out["n_session_starts_in_log"] == 3 and out["n_sessions_with_saves"] == 2
    assert out["n_sessions_basis"].startswith("SESSION start lines")
    assert out["first_session_start_utc"] == "2026-11-08T00:00:00+00:00"
    assert out["last_session_end_utc"] == "2026-11-10T00:05:00+00:00"
    by = {s["session_id"]: s for s in out["sessions"]}
    assert by["S1"]["end_utc"] == "2026-11-08T01:00:00+00:00" and by["S1"]["n_saves_on_these_cells"] == 2
    assert by["S2"]["end_utc"] is None and by["S2"]["n_saves_on_these_cells"] == 1
    assert by["S3"]["n_saves_on_these_cells"] == 0 and by["S3"]["first_save_utc"] is None
    assert out["first_save_utc"] == "2026-11-08T00:05:00+00:00"


def test_sessions_without_a_log_come_from_the_audit(tmp_path):
    audit = write_audit(tmp_path / "a.jsonl", [{"cell_id": "a", "session_id": "S1", "elapsed_s": 1.0},
                                              {"cell_id": "b", "session_id": "S2", "elapsed_s": 1.0}])
    out = aw.session_summary(["a", "b"], audit, None)
    assert out["n_sessions"] == 2 and out["n_session_starts_in_log"] is None
    assert "audit" in out["n_sessions_basis"] and out["first_session_start_utc"] is None
    assert all(s["in_session_log"] is False for s in out["sessions"])


# ---------------------------------------------------------------------------
# 8. second annotation
# ---------------------------------------------------------------------------
def sec_cell(i, cluster, j=2, a0=1, l0=2, a1=1, l1=2, cat="cat_a"):
    return aw.SecondCell(cell_id=f"s{i:03d}", cluster_id=cluster, category=cat, j=j, ah_a=a0, ah_l1=l0,
                         s_a=a1, s_l1=l1)


def test_registered_sample_constants():
    assert aw.SECOND_SAMPLE_SHA256 == "bd2333d427971fb182add2e3735e1d81fd3fe343640d736eea2b612819854b7e"
    assert (aw.SECOND_N, aw.SECOND_PER_CATEGORY) == (48, 8)


def test_second_annotator_sample_is_the_registered_draw():
    rng = random.Random(0)
    cells = []
    for cat, size in (("zeta", 11), ("alpha", 20), ("mid", 9), ("beta", 15), ("omega", 8), ("delta", 30)):
        for i in range(size):
            cells.append({"cell_id": f"{cat}-{i:02d}", "cell_kind": "primary", "category": cat,
                          "J": rng.randint(0, 3), "A": 1, "cluster_id": "x"})
    for i in range(10):                                   # controls are never drawn
        cells.append({"cell_id": f"ctl-{i}", "cell_kind": "ablated_control", "category": "alpha"})
    # the procedure of PREREG sec.12.4, written out independently
    ids = {}
    for c in cells:
        if c["cell_kind"] == "primary":
            ids.setdefault(c["category"], []).append(c["cell_id"])
    r = random.Random(20260913)
    picked = []
    for cat in sorted(ids):
        picked += r.sample(sorted(ids[cat]), 8)
    expected = ("\n".join(sorted(picked)) + "\n").encode("utf-8")
    got = aw.second_annotator_sample(cells)
    assert aw.sample_list_bytes(got) == expected
    assert len(got) == 48 and got == sorted(got) and not any(g.startswith("ctl") for g in got)
    assert aw.second_annotator_sample(list(reversed(cells))) == got               # row order is irrelevant
    # only cell_id, cell_kind and category are read
    thin = [{k: c[k] for k in ("cell_id", "cell_kind", "category") if k in c} for c in cells]
    assert aw.second_annotator_sample(thin) == got
    with pytest.raises(ValueError, match="fewer than"):
        aw.second_annotator_sample([c for c in cells if c["cell_id"] != "omega-03"])     # 7 left in 'omega'
    with pytest.raises(ValueError, match="no category"):
        aw.second_annotator_sample([{"cell_id": "x", "cell_kind": "primary"}])


def pairs_cells(n11, n10, n01, n00, per_cluster=1):
    """Cells with the 2x2 counts (rows = AH, columns = second); ``per_cluster`` cells per CQ cluster."""
    ref, cand = columns(n11, n10, n01, n00)
    out = []
    for i, (a, b) in enumerate(zip(ref, cand)):
        out.append(sec_cell(i, f"cq{i // per_cluster:03d}", j=2 if a else 1, a0=a, l0=3 if a else 0,
                            a1=b, l1=3 if b else 0))
    return out


def test_second_block_hand_values_for_the_binary_statistics():
    block = aw.second_annotation_block(pairs_cells(30, 6, 4, 10), seed=SEED, B=SMALL_B)
    a = block["A_agreement_AH_vs_second"]
    assert a["table"] == {"n11": 30, "n10": 6, "n01": 4, "n00": 10}
    expect = dict(raw_agreement=4 / 5, cohen_kappa=138 / 263, gwet_ac1=19 / 29, ppa=5 / 6, npa=5 / 7)
    for name, value in expect.items():
        assert a[name]["estimate"] == pytest.approx(value, abs=1e-14), name
        assert a[name]["ci_lo"] <= value <= a[name]["ci_hi"], name
        assert a[name]["resamples"] == SMALL_B and a[name]["n_clusters"] == 50
    assert "AH labels (rows)" in a["comparison_column"]
    assert block["gates"].startswith("none")


def test_second_block_has_no_symmetric_specific_agreement_and_no_accuracy_vocabulary():
    block = aw.second_annotation_block(pairs_cells(30, 6, 4, 10), seed=SEED, B=SMALL_B)
    text = json.dumps(block).lower()
    for banned in ("specific_agreement", "positive_specific", "negative_specific", "sensitivity", "specificity"):
        assert banned not in text
    assert not [n for n in dir(aw) if "specific_agreement" in n.lower()]
    assert set(block["A_agreement_AH_vs_second"]) >= {"raw_agreement", "cohen_kappa", "gwet_ac1", "ppa", "npa"}


def test_second_binary_statistics_at_extreme_prevalence_exclude_undefined_replicates_and_count_them():
    # one AH-negative cell (in its own cluster) among 12 clusters, called negative by the second annotator too
    cells = [sec_cell(i, f"cq{i:02d}", a0=0 if i == 0 else 1, a1=0 if i == 0 else 1) for i in range(12)]
    a = aw.second_annotation_block(cells, seed=SEED, B=2000)["A_agreement_AH_vs_second"]
    n_undef = sum(0 not in set(int(i) for i in idx) for idx in independent_draws(12, SEED, 2000))
    assert 0 < n_undef < 1000
    assert a["npa"]["estimate"] == 1.0 and a["npa"]["n_undefined_replicates"] == n_undef
    assert a["npa"]["undefined_replicate_policy"] == "dropped"
    assert a["cohen_kappa"]["n_undefined_replicates"] >= n_undef       # kappa also fails on all-positive resamples
    assert a["raw_agreement"]["n_undefined_replicates"] == 0 and a["gwet_ac1"]["n_undefined_replicates"] == 0
    # all positive in both: kappa and NPA are undefined, with a reason, and AC1 is 1
    flat = aw.second_annotation_block([sec_cell(i, f"cq{i:02d}") for i in range(10)], seed=SEED, B=SMALL_B)
    f = flat["A_agreement_AH_vs_second"]
    assert f["cohen_kappa"]["estimate"] is None and f["npa"]["estimate"] is None
    assert f["gwet_ac1"]["estimate"] == pytest.approx(1.0) and f["ppa"]["estimate"] == 1.0
    assert "0/0" in f["cohen_kappa"]["ci_reason"] and "no negative" in f["npa"]["ci_reason"]


def test_second_l1_agreement_has_qwk_and_exact_agreement_and_no_analytic_se():
    rng = np.random.default_rng(4)
    cells = []
    for i in range(40):
        l0 = int(rng.integers(0, 4))
        cells.append(sec_cell(i, f"cq{i // 2:02d}", l0=l0, l1=int(np.clip(l0 + rng.choice([-1, 0, 0, 1]), 0, 3))))
    block = aw.second_annotation_block(cells, seed=SEED, B=SMALL_B)
    l1 = block["L1_agreement_AH_vs_second"]
    x, y = [c.ah_l1 for c in cells], [c.s_l1 for c in cells]
    assert l1["qwk"]["estimate"] == pytest.approx(float(frac_qwk(x, y)), abs=1e-14)
    assert l1["exact_agreement"]["estimate"] == pytest.approx(sum(a == b for a, b in zip(x, y)) / 40)
    assert l1["qwk"]["undefined_replicate_policy"] == "dropped"          # sec.12.4: nothing is substituted
    assert l1["exact_agreement"]["undefined_replicate_policy"] == "dropped"
    assert "fleiss" not in json.dumps(block).lower() and "analytic" not in json.dumps(block).lower()


def event_cells():
    """40 cells in 20 clusters (two each).  AH events (J >= 2 and A = 0): cells 0, 1 (cluster 0) and 2
    (cluster 1) -> 3 event cells in 2 clusters.  Two decoys that are NOT events: cell 3 (A = 0 but J = 1) and
    cell 4 (A = 0, J = 0), both with rater_L1 = 3 so that using rater_L1 in place of J would count them (2
    events, not 3).  Second annotator: A = 1 everywhere except cell 20 (J = 2): its only event, cluster 10."""
    cells = []
    for i in range(40):
        cl = f"cq{i // 2:02d}"
        if i in (0, 1, 2):
            cells.append(sec_cell(i, cl, j=3, a0=0, l0=0, a1=1))               # AH events (rater_L1 0 < 2)
        elif i == 3:
            cells.append(sec_cell(i, cl, j=1, a0=0, l0=3, a1=1))               # A = 0 but J = 1: not an event
        elif i == 4:
            cells.append(sec_cell(i, cl, j=0, a0=0, l0=3, a1=1))               # A = 0, J = 0: not an event
        elif i == 20:
            cells.append(sec_cell(i, cl, j=2, a0=1, l0=3, a1=0))               # an event for the second set only
        else:
            cells.append(sec_cell(i, cl, j=1, a0=1, l0=3, a1=1))
    return cells


def test_pi_hat_event_cluster_definition_and_the_cluster_clopper_pearson_bounds():
    block = aw.second_annotation_block(event_cells(), seed=SEED, B=SMALL_B)
    ahb = block["pi_hat"]["AH"]
    # pi uses the judge's J (not rater_L1) and each label set's own A
    assert ahb["events"] == 3 and ahb["n_cells"] == 40 and ahb["pi_hat"] == pytest.approx(3 / 40)
    cp = ahb["cluster_level_clopper_pearson"]
    # an event cluster has at least one cell with J >= 2 and A = 0: two clusters, not three cells
    assert cp["events_clusters"] == 2 and cp["n_clusters"] == 20 and ahb["clusters_with_event"] == 2
    # one-sided upper bounds, exact: beta(1-alpha; k+1, n-k)
    assert cp["one_sided_97_5"]["upper_bound"] == pytest.approx(stats.beta.ppf(0.975, 3, 18), abs=1e-12)
    assert cp["one_sided_95"]["upper_bound"] == pytest.approx(stats.beta.ppf(0.95, 3, 18), abs=1e-12)
    ci2 = stats.binomtest(2, 20).proportion_ci(confidence_level=0.95, method="exact")
    assert cp["one_sided_97_5"]["upper_bound"] == pytest.approx(ci2.high, abs=1e-12)
    ci90 = stats.binomtest(2, 20).proportion_ci(confidence_level=0.90, method="exact")
    assert cp["one_sided_95"]["upper_bound"] == pytest.approx(ci90.high, abs=1e-12)
    # the second annotator's own labels give their own event: cell 20, one cluster
    s_ = block["pi_hat"]["second_annotator"]
    assert s_["events"] == 1 and s_["pi_hat"] == pytest.approx(1 / 40)
    assert s_["cluster_level_clopper_pearson"]["events_clusters"] == 1
    assert s_["cluster_level_clopper_pearson"]["one_sided_97_5"]["upper_bound"] == pytest.approx(
        stats.beta.ppf(0.975, 2, 19), abs=1e-12)
    assert "G1 decision" in block["pi_hat"]["note"] and "pass" not in json.dumps(block["pi_hat"]).lower()
    # with no event at all: no bootstrap, a stated reason, and the zero-event bound
    clean = [sec_cell(i, f"cq{i // 2:02d}", j=3, a0=1, a1=1) for i in range(40)]
    z = aw.second_annotation_block(clean, seed=SEED, B=SMALL_B)["pi_hat"]["AH"]
    assert z["events"] == 0 and z["ci_lo"] is None and "bootstrap" in z["ci_reason"]
    assert "reported by G1" not in z["ci_reason"]
    assert z["cluster_level_clopper_pearson"]["events_clusters"] == 0
    assert z["cluster_level_clopper_pearson"]["one_sided_97_5"]["upper_bound"] == pytest.approx(
        1 - 0.025 ** (1 / 20), abs=1e-12)


def test_pi_hat_n_is_the_number_of_clusters_the_cells_cover():
    cells = [sec_cell(i, f"cq{i % 7}", j=3, a0=0) for i in range(30)]          # 30 cells in 7 clusters, all events
    cp = aw.second_annotation_block(cells, seed=SEED, B=SMALL_B)["pi_hat"]["AH"]["cluster_level_clopper_pearson"]
    assert cp["n_clusters"] == 7 and cp["events_clusters"] == 7
    assert cp["one_sided_97_5"]["upper_bound"] == 1.0


@pytest.mark.parametrize("n,cannot_975,cannot_95", [
    (20, True, True), (28, True, True), (29, True, False), (35, True, False), (36, False, False),
    (48, False, False)])
def test_zero_event_note_is_true_for_the_cluster_count(n, cannot_975, cannot_95):
    # zero-event one-sided bound 1 - alpha^(1/n): above 10% at 97.5% for n <= 35, at 95% for n <= 28
    note = aw.zero_event_bound_note(n)
    b975, b95 = 1 - 0.025 ** (1 / n), 1 - 0.05 ** (1 / n)
    assert note["zero_event_upper_bound_one_sided_97_5"] == pytest.approx(b975, abs=1e-12)
    assert note["zero_event_upper_bound_one_sided_95"] == pytest.approx(b95, abs=1e-12)
    assert note["cannot_go_below_10pct_even_with_zero_events_one_sided_97_5"] is cannot_975 is (b975 > 0.10)
    assert note["cannot_go_below_10pct_even_with_zero_events_one_sided_95"] is cannot_95 is (b95 > 0.10)
    claim = "cannot go below 10% even with zero events"
    if cannot_975 and cannot_95:
        assert claim in note["note"] and "97.5%" in note["note"] and "95%" in note["note"]
    elif cannot_975:
        assert claim in note["note"] and "at the 97.5% level" in note["note"]
        assert "reachable" not in note["note"]
    else:
        assert claim not in note["note"] and "reachable at both levels" in note["note"]
    assert "Not a G1 decision" in note["note"]


def test_zero_event_boundaries_are_exactly_28_29_and_35_36():
    assert aw.zero_event_bound_note(28)["cannot_go_below_10pct_even_with_zero_events_one_sided_95"] is True
    assert aw.zero_event_bound_note(29)["cannot_go_below_10pct_even_with_zero_events_one_sided_95"] is False
    assert aw.zero_event_bound_note(35)["cannot_go_below_10pct_even_with_zero_events_one_sided_97_5"] is True
    assert aw.zero_event_bound_note(36)["cannot_go_below_10pct_even_with_zero_events_one_sided_97_5"] is False


def judge_cells():
    """Twelve cells with known J, second-annotator rater_L1 and A.  J=0 cells are 3 of them."""
    spec = [  # (J, second rater_L1, second A)
        (0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 2, 0), (1, 1, 1),
        (2, 2, 1), (2, 3, 1), (2, 1, 0), (3, 3, 1), (3, 2, 1), (3, 3, 0)]
    return [sec_cell(i, f"cq{i // 2:02d}", j=j, l1=lv, a1=a) for i, (j, lv, a) in enumerate(spec)], spec


def test_judge_vs_second_gives_three_values_each_also_restricted_to_j_1_2_3():
    cells, spec = judge_cells()
    block = aw.second_annotation_block(cells, seed=SEED, B=SMALL_B)["judge_vs_second_annotator"]
    allc, res = block["all_cells"], block["restricted_to_J_in_1_2_3"]
    js, ls, as_ = [s[0] for s in spec], [s[1] for s in spec], [s[2] for s in spec]
    assert allc["n_cells"] == 12 and res["n_cells"] == 9
    assert allc["L1_scale"]["qwk"]["estimate"] == pytest.approx(float(frac_qwk(js, ls)), abs=1e-14)
    assert allc["L1_scale"]["exact_agreement"]["estimate"] == pytest.approx(sum(j == lv for j, lv in zip(js, ls)) / 12)
    # binary kappa of 1[J >= 2] against A, by hand: table rows = judge, columns = second A
    jb = [int(j >= 2) for j in js]
    n11 = sum(a and b for a, b in zip(jb, as_))
    n10 = sum(a and not b for a, b in zip(jb, as_))
    n01 = sum((not a) and b for a, b in zip(jb, as_))
    n00 = sum((not a) and (not b) for a, b in zip(jb, as_))
    assert allc["binary_scale"]["table"] == {"n11": n11, "n10": n10, "n01": n01, "n00": n00}
    po = Fraction(n11 + n00, 12)
    pe = Fraction(n11 + n10, 12) * Fraction(n11 + n01, 12) + Fraction(n01 + n00, 12) * Fraction(n10 + n00, 12)
    assert allc["binary_scale"]["cohen_kappa"]["estimate"] == pytest.approx(float((po - pe) / (1 - pe)), abs=1e-14)
    # the restricted set drops the three J=0 cells and nothing else
    rj, rl, ra = js[3:], ls[3:], as_[3:]
    assert res["L1_scale"]["qwk"]["estimate"] == pytest.approx(float(frac_qwk(rj, rl)), abs=1e-14)
    assert res["L1_scale"]["exact_agreement"]["estimate"] == pytest.approx(sum(j == lv for j, lv in zip(rj, rl)) / 9)
    rb = [int(j >= 2) for j in rj]
    t = (sum(a and b for a, b in zip(rb, ra)), sum(a and not b for a, b in zip(rb, ra)),
         sum((not a) and b for a, b in zip(rb, ra)), sum((not a) and (not b) for a, b in zip(rb, ra)))
    assert res["binary_scale"]["table"] == dict(zip(("n11", "n10", "n01", "n00"), t))
    assert allc["L1_scale"]["qwk"]["estimate"] != pytest.approx(res["L1_scale"]["qwk"]["estimate"])
    assert "J = 0" in res["why"] and block["descriptive_only"] is True
    for part in (allc, res):
        assert part["L1_scale"]["qwk"]["undefined_replicate_policy"] == "dropped"
        assert part["L1_scale"]["exact_agreement"]["undefined_replicate_policy"] == "dropped"
        assert part["binary_scale"]["cohen_kappa"]["undefined_replicate_policy"] == "dropped"


def test_judge_vs_second_restricted_block_is_empty_when_every_j_is_zero():
    cells = [sec_cell(i, f"cq{i:02d}", j=0) for i in range(6)]
    res = aw.second_annotation_block(cells, seed=SEED, B=SMALL_B)["judge_vs_second_annotator"]
    assert res["restricted_to_J_in_1_2_3"]["n_cells"] == 0 and "L1_scale" not in res["restricted_to_J_in_1_2_3"]
    assert res["all_cells"]["n_cells"] == 6


def test_empty_cell_set_gives_an_empty_block():
    assert aw.second_annotation_block([], seed=SEED, B=SMALL_B) == {"n_cells": 0, "n_clusters": 0}


def test_ai_use_values_are_parsed_strictly():
    for raw, want in (("yes", "yes"), ("YES", "yes"), (True, "yes"), ("true", "yes"),
                      ("no", "no"), ("No", "no"), (False, "no"), ("false", "no")):
        assert aw.parse_ai_use(raw) == want
    for bad in ("maybe", "", "1", 1, None):
        with pytest.raises(ValueError):
            aw.parse_ai_use(bad)


def ai_use_line(session_id, used, tool="chat", approx=None, how="answered", sitting_id=None):
    """One ``AI_USE {json}`` session-log line, as label_assist --packet writes it (``sitting_id``: packet mode)."""
    entry = {"phase": "end", "used": used, "tool": tool, "approx_cells": approx, "how": how,
             "ts": "2026-11-08T11:00:00+09:00", "session_id": session_id}
    if sitting_id is not None:
        entry["sitting_id"] = sitting_id
    return "AI_USE " + json.dumps(entry, separators=(",", ":"))


def typed_tool(raw):
    """A tool name as the analyzer should normalize it, restated plainly (every input here is ASCII)."""
    return " ".join(str(raw or "").split()).strip(" .,;:/|").casefold()


def expected_ai_class(ticked, report):
    """The AI-use rule of PREREG sec.13.1 (7), restated plainly for one cell: ``ticked`` is the labeler's tick,
    ``report`` the ``(used, tool as typed)`` of the cell's sitting, or None.  Returns (group, ticked, tool)."""
    used, tool = report if report else (None, "")
    if used == "yes":
        return "yes", ticked, typed_tool(tool) or aw.TOOL_NOT_GIVEN
    if ticked:
        return "yes", True, aw.TOOL_NO_YES_REPORT
    return ("no" if used == "no" else "not recorded"), False, None


def load_ai_inputs(tmp_path, saves, log_lines):
    """Write an audit and a session log and load them the way the CLI does: (audit, extras, reports)."""
    audit = write_audit(tmp_path / "a.jsonl", saves)
    log = tmp_path / "log.txt"
    log.write_text("\n".join(log_lines) + "\n")
    return audit, aw.load_audit_extras(tmp_path / "a.jsonl"), aw.load_ai_use_reports(log)


def test_ai_use_tick_wins_then_the_session_report_then_not_recorded(tmp_path):
    saves = [
        {"cell_id": "a", "session_id": "S1", "extra": {"ai_used": True}},                  # line 0: a, ticked
        {"cell_id": "a", "session_id": "S2", "extra": {"ai_used": None}, "blank_before": True},   # 1 blank, 2: a, unticked
        {"cell_id": "a2", "session_id": "S1", "extra": {"ai_used": None}},                 # line 3
        {"cell_id": "a2", "session_id": "S2", "extra": {"ai_used": True}},                 # line 4: last save ticked
        {"cell_id": "b", "session_id": "S1"},                                              # line 5: session S1 says yes
        {"cell_id": "c", "session_id": "S3"},                                              # line 6: S3 has no report
        {"cell_id": "e", "session_id": "S1", "extra": {"ai_used": False}},                 # line 7: an explicit false is no tick
        {"cell_id": "g", "session_id": "S4"},                                              # line 8: S4 skipped the form
    ]
    log = [ai_use_line("S1", "yes", tool="Chat", approx=4), ai_use_line("S2", "no", tool="", approx=0),
           ai_use_line("S4", "not recorded", tool="", how="skipped")]
    audit, extras, reports = load_ai_inputs(tmp_path, saves, log)
    assert extras.ai_flags == {0: "yes", 4: "yes", 7: "no"}   # the index is the audit line index, a blank line included
    assert aw.load_audit_ai_flags(tmp_path / "a.jsonl") == extras.ai_flags
    assert {s.cell_id: s.seq for s in audit.saves["a"]} == {"a": 2}                       # same numbering as the registered loader
    shown = {k: k for k in ("a", "a2", "b", "c", "d", "e", "g")}                        # d has no audit record
    res, counts = aw.classify_ai_use(shown, audit, extras, reports)
    # a: the LAST save carries no tick -> the report of S2 (no); a2: its last save is ticked, S2 said no; b: S1 said yes;
    # e: an explicit false is not a tick, S1 said yes; c: S3 has no report; g: S4 skipped the form
    assert res["a"] == aw.AiUse("no", False, None, "session_report")
    assert res["a2"] == aw.AiUse("yes", True, aw.TOOL_NO_YES_REPORT, "tick")
    assert res["b"] == aw.AiUse("yes", False, "chat", "session_report")
    assert res["e"] == aw.AiUse("yes", False, "chat", "session_report")
    assert res["c"] == res["d"] == res["g"] == aw.NOT_RECORDED_AI
    assert counts["by_group"] == {"yes": 3, "no": 1, "not recorded": 3}
    # a session report that says "not recorded" is no information: g counts under none
    assert counts["by_source"] == {"tick": 1, "sitting_report": 0, "session_report": 3, "none": 3}
    assert counts["tick_only"]["by_group"] == {"ticked": 1, "not ticked": 6}
    assert (counts["join"]["by_sitting_id"], counts["join"]["by_session_id"], counts["join"]["no_report"]) == (0, 5, 2)
    assert counts["n_ticks_in_sittings_reporting_no"] == 1 and counts["n_explicit_no_flags"] == 1
    assert counts["tools_among_yes_cells"] == [{"tool": aw.TOOL_NO_YES_REPORT, "n_cells": 1},
                                               {"tool": "chat", "n_cells": 2}]


def test_sheet_ai_column_is_a_per_cell_flag_and_a_missing_column_is_not_a_blank_one(tmp_path):
    rows = [{"cell_id": "a", "ai_used": "yes"}, {"cell_id": "b", "ai_used": ""}, {"cell_id": "c", "ai_used": "Yes"},
            {"cell_id": "d", "ai_used": "no"}]
    with_col = write_csv(tmp_path / "w.csv", rows, ["cell_id", "ai_used"])
    assert aw.load_sheet_ai_flags(with_col) == {"a": "yes", "c": "yes", "d": "no"}       # blank = not recorded, skipped
    without = write_csv(tmp_path / "n.csv", [{"cell_id": "a"}], ["cell_id"])
    assert aw.load_sheet_ai_flags(without) is None                                         # no column at all
    bad = write_csv(tmp_path / "b.csv", [{"cell_id": "a", "ai_used": "maybe"}], ["cell_id", "ai_used"])
    with pytest.raises(ValueError, match="ai_used"):
        aw.load_sheet_ai_flags(bad)


def test_ai_use_sheet_column_and_audit_tick_both_count_and_a_disagreement_is_counted(tmp_path):
    saves = [
        {"cell_id": "both", "session_id": "S1", "extra": {"ai_used": True}},            # audit yes, sheet yes
        {"cell_id": "audit_only", "session_id": "S1", "extra": {"ai_used": True}},      # audit yes, sheet blank
        {"cell_id": "sheet_only", "session_id": "S1", "extra": {"ai_used": None}},      # audit blank, sheet yes
        {"cell_id": "neither", "session_id": "S1", "extra": {"ai_used": None}},         # blank both: the session report
        {"cell_id": "contra", "session_id": "S1", "extra": {"ai_used": False}},         # audit no, sheet yes
        {"cell_id": "contra2", "session_id": "S1", "extra": {"ai_used": True}},         # audit yes, sheet no
    ]
    audit, extras, reports = load_ai_inputs(tmp_path, saves, [ai_use_line("S1", "no", tool="", approx=0)])
    shown = {k: k for k in ("both", "audit_only", "sheet_only", "neither", "contra", "contra2", "no_audit_record")}
    sheet = {"both": "yes", "sheet_only": "yes", "contra": "yes", "contra2": "no", "no_audit_record": "yes"}
    res, counts = aw.classify_ai_use(shown, audit, extras, reports, sheet)
    assert {k: v.group for k, v in res.items()} == {
        "both": "yes", "audit_only": "yes", "sheet_only": "yes", "neither": "no",
        "contra": "yes", "contra2": "yes", "no_audit_record": "yes"}               # a tick in either source counts
    assert {k for k, v in res.items() if v.ticked} == set(shown) - {"neither"}
    assert counts["by_source"] == {"tick": 6, "sitting_report": 0, "session_report": 1, "none": 0}
    # disagreements: audit_only (yes vs blank), sheet_only (blank vs yes), contra (no vs yes), contra2 (yes vs no);
    # a cell with no audit record is not compared, and a cell where both agree is not a conflict
    assert counts["n_sheet_audit_conflicts"] == 4 and counts["sheet_column_present"] is True
    assert counts["n_explicit_no_flags"] == 2          # the audit's false (contra) and the sheet's no (contra2)
    # a tick in a sitting that reported no is still a tick, and it is counted (five cells have an audit record)
    assert counts["n_ticks_in_sittings_reporting_no"] == 5
    # without a sheet column nothing is compared and the audit alone decides
    res2, counts2 = aw.classify_ai_use(shown, audit, extras, reports, None)
    assert res2["sheet_only"].group == "no" and res2["audit_only"].group == "yes"      # sheet_only falls to the report
    assert res2["contra"].group == "no" and res2["contra2"].group == "yes"
    assert res2["no_audit_record"] == aw.NOT_RECORDED_AI
    assert counts2["n_sheet_audit_conflicts"] == 0 and counts2["sheet_column_present"] is False
    assert counts2["n_explicit_no_flags"] == 1


def test_ai_use_flags_refuse_values_that_are_not_yes_or_no(tmp_path):
    bad = tmp_path / "a.jsonl"
    write_audit(bad, [{"cell_id": "a", "session_id": "S1", "extra": {"ai_used": "sometimes"}}])
    with pytest.raises(ValueError, match="ai_used"):
        aw.load_audit_ai_flags(bad)
    with pytest.raises(ValueError, match="no label audit"):
        aw.load_audit_ai_flags(tmp_path / "missing.jsonl")


def test_ai_use_reports_come_from_the_session_log_and_the_last_line_of_a_session_wins(tmp_path):
    log = tmp_path / "log.txt"
    log.write_text("\n".join([
        "SESSION start=2026-11-08T09:00:00+09:00 pid=11 session_id=S1 mode=packet sheet_sha256=abc",
        ai_use_line("S1", "no", tool="", approx=0),
        ai_use_line("S1", "yes", tool="A Chat  Assistant.", approx=7),                       # supersedes
        ai_use_line("S2", "not recorded", tool="", how="unanswered"),
        ai_use_line("S3", "yes", tool="x", approx=None),
        'AI_USE {"session_id": "S4", "used": "maybe"}',                                     # unusable value
        "AI_USE not json",                                                                   # unusable line
        'AI_USE {"used": "yes"}',                                                            # no session id
        ai_use_line("S5", "no", tool="", approx=0),
        "SESSION end=2026-11-08T10:00:00+09:00 pid=11 saved=3"]) + "\n")
    reports = aw.load_ai_use_reports(log)
    assert reports.has_sitting_ids is False and reports.by_sitting == {}
    assert reports.by_session == {
        "S1": {"used": "yes", "approx_cells": 7, "how": "answered", "tool": "a chat assistant",
               "session_id": "S1", "sitting_id": None},
        "S2": {"used": "not recorded", "approx_cells": None, "how": "unanswered", "tool": "",
               "session_id": "S2", "sitting_id": None},
        "S3": {"used": "yes", "approx_cells": None, "how": "answered", "tool": "x",
               "session_id": "S3", "sitting_id": None},
        "S5": {"used": "no", "approx_cells": 0, "how": "answered", "tool": "",
               "session_id": "S5", "sitting_id": None}}
    assert reports.meta == {"n_ai_use_lines": 8, "n_unusable": 3, "n_superseded": 1, "n_lines_with_sitting_id": 0}
    summary = aw.ai_use_session_summary(reports)
    assert summary["n_reports"] == 4 and summary["by_declared_use"] == {"yes": 2, "no": 1, "not recorded": 1}
    assert summary["tools_in_yes_reports"] == [{"tool": "a chat assistant", "n_reports": 1},
                                               {"tool": "x", "n_reports": 1}]
    assert summary["approx_cells_declared_in_yes_reports"] == 7
    assert summary["n_yes_reports_without_approx_cells"] == 1 and "however few" in summary["note"]
    assert summary["n_ai_use_lines"] == 8 and summary["n_superseded"] == 1
    # the session-log reader does not count those lines as unparsed, and the SESSION lines still parse
    records, log_meta = aw.load_session_log(log)
    assert log_meta["n_ai_use_lines"] == 8 and log_meta["n_unparsed_lines"] == 0
    assert [r.session_id for r in records] == ["S1"] and records[0].end is not None
    with pytest.raises(ValueError, match="no session log"):
        aw.load_ai_use_reports(tmp_path / "missing.txt")


def test_second_report_is_given_overall_and_by_ai_use_with_three_groups():
    cells = pairs_cells(14, 3, 2, 5, per_cluster=1)                       # 24 cells
    spec = ([("yes", i < 4, "chatgpt" if i % 2 == 0 else "claude") for i in range(10)]     # 4 ticked, 6 unticked
            + [("no", False, None)] * 10 + [("not recorded", False, None)] * 4)
    ai = {c.cell_id: aw.AiUse(g, tick, tool, "tick" if tick else "sitting_report")
          for c, (g, tick, tool) in zip(cells, spec)}
    rep = aw.second_annotation_report(cells, ai, seed=SEED, B=SMALL_B)
    assert set(rep["by_ai_use"]) == {"yes", "no", "not recorded"}
    assert [rep["by_ai_use"][g]["n_cells"] for g in ("yes", "no", "not recorded")] == [10, 10, 4]
    assert rep["all_cells"]["n_cells"] == 24
    sub_yes = [c for c in cells if ai[c.cell_id].group == "yes"]
    direct = aw.second_annotation_block(sub_yes, seed=SEED, B=SMALL_B)
    assert rep["by_ai_use"]["yes"] == direct                              # same statistics, same resampling
    # every statistic of the overall block is present in each group that has cells
    for g in ("yes", "no", "not recorded"):
        assert set(rep["by_ai_use"][g]) == set(rep["all_cells"])
    # the sensitivity: the labeler's tick only (the unticked cells of the yes group fall under "not ticked")
    assert set(rep["by_ai_use_tick_only"]) == {"ticked", "not ticked"}
    assert [rep["by_ai_use_tick_only"][g]["n_cells"] for g in ("ticked", "not ticked")] == [4, 20]
    assert rep["by_ai_use_tick_only"]["ticked"] == aw.second_annotation_block(
        [c for c in cells if ai[c.cell_id].ticked], seed=SEED, B=SMALL_B)
    # tools among the yes cells only: one block per normalized tool, the same statistics on that subset
    tools = rep["by_tool_among_yes_cells"]
    assert [(x["tool"], x["n_cells"]) for x in tools] == [("chatgpt", 5), ("claude", 5)]
    for x in tools:
        sub = [c for c in sub_yes if ai[c.cell_id].tool == x["tool"]]
        assert x["block"] == aw.second_annotation_block(sub, seed=SEED, B=SMALL_B)
    assert "by_ai_use is the primary" in rep["notes"] and "tick" in rep["notes"]
    # no information at all: everything is "not recorded" / "not ticked", the other groups are empty
    none = aw.second_annotation_report(cells, None, seed=SEED, B=SMALL_B)
    assert none["by_ai_use"]["not recorded"]["n_cells"] == 24
    assert none["by_ai_use"]["yes"] == {"n_cells": 0, "n_clusters": 0} == none["by_ai_use"]["no"]
    assert none["by_ai_use_tick_only"]["not ticked"]["n_cells"] == 24
    assert none["by_ai_use_tick_only"]["ticked"] == {"n_cells": 0, "n_clusters": 0}
    assert none["by_tool_among_yes_cells"] == []


@pytest.mark.parametrize("raw,want", [
    ("ChatGPT ", "chatgpt"),
    ("  Claude.ai. ", "claude.ai"),                  # the ends are trimmed of . , ; : / | and space, the inside is kept
    ("CLAUDE", "claude"),
    ("ＧＰＴ－４", "gpt-4"),                         # full-width forms: NFKC
    ("chat   gpt\t4", "chat gpt 4"),
    ("GPT-4 / Claude", "gpt-4 / claude"),           # several tools are ONE group, not split
    ("Copilot;", "copilot"),
    ("Gemini 2.5", "gemini 2.5"),
    ("  ;; ", ""),
    ("", ""),
    (None, ""),
])
def test_normalize_tool(raw, want):
    assert aw.normalize_tool(raw) == want


def test_ai_use_reports_with_sitting_ids_are_keyed_by_sitting_and_append_only(tmp_path):
    log = tmp_path / "log.txt"
    log.write_text("\n".join([
        "SESSION start=2026-11-08T09:00:00+09:00 pid=11 session_id=S1 sitting_id=S1-s1 mode=packet",
        ai_use_line("S1", "yes", tool="ChatGPT ", approx=3, sitting_id="S1-s1"),
        ai_use_line("S1", "no", tool="", approx=0, sitting_id="S1-s2"),               # the next sitting of the session
        ai_use_line("S1", "yes", tool="Claude", approx=9, sitting_id="S1-s1"),        # a second line of s1: supersedes it
        ai_use_line("S2", "yes", tool="x"),                                             # an older-format line
        "SESSION end=2026-11-08T10:00:00+09:00 pid=11 saved=3"]) + "\n")
    reports = aw.load_ai_use_reports(log)
    assert reports.has_sitting_ids is True and set(reports.by_sitting) == {"S1-s1", "S1-s2"}
    assert reports.by_sitting["S1-s1"]["tool"] == "claude" and reports.by_sitting["S1-s1"]["approx_cells"] == 9
    assert reports.by_sitting["S1-s2"]["used"] == "no"
    assert reports.by_session["S1"]["sitting_id"] == "S1-s1" and reports.by_session["S2"]["tool"] == "x"
    assert reports.meta == {"n_ai_use_lines": 4, "n_unusable": 0, "n_superseded": 1, "n_lines_with_sitting_id": 3}
    summary = aw.ai_use_session_summary(reports)
    assert (summary["n_reports"], summary["n_reports_with_sitting_id"]) == (3, 2)
    assert summary["by_declared_use"] == {"yes": 2, "no": 1, "not recorded": 0}
    records, _ = aw.load_session_log(log)
    assert records[0].sitting_id == "S1-s1"


def test_ai_use_join_is_on_the_sitting_id_and_falls_back_to_the_session_id_when_it_is_absent(tmp_path):
    saves = [
        {"cell_id": "c1", "session_id": "S1", "extra": {"sitting_id": "S1-s1"}},
        {"cell_id": "c2", "session_id": "S1", "extra": {"sitting_id": "S1-s2"}},
        {"cell_id": "c3", "session_id": "S1"},                                          # an audit line without a sitting_id
        {"cell_id": "c4", "session_id": "S9", "extra": {"sitting_id": "S9-s1"}},        # its sitting has no report ...
        {"cell_id": "c5", "session_id": "S1", "extra": {"sitting_id": "S1-s1"}},
        {"cell_id": "c5", "session_id": "S1", "extra": {"sitting_id": "S1-s2"}},        # two saves: the LAST one decides
    ]
    log = [ai_use_line("S1", "yes", tool="ChatGPT", approx=3, sitting_id="S1-s1"),
           ai_use_line("S1", "no", tool="", approx=0, sitting_id="S1-s2"),
           ai_use_line("S9", "yes", tool="Claude", approx=1, sitting_id="S9-s2")]       # ... another sitting of S9 has one
    audit, extras, reports = load_ai_inputs(tmp_path, saves, log)
    shown = {k: k for k in ("c1", "c2", "c3", "c4", "c5")}
    res, counts = aw.classify_ai_use(shown, audit, extras, reports)
    assert res["c1"] == aw.AiUse("yes", False, "chatgpt", "sitting_report")
    assert res["c2"] == aw.AiUse("no", False, None, "sitting_report")
    # c1 and c2 share a session: a session-level join would give both the last report of S1 (no); the sitting keeps them apart
    assert res["c3"] == aw.AiUse("no", False, None, "session_report")        # no sitting_id: the older rule, S1's last report
    assert res["c4"] == aw.NOT_RECORDED_AI              # the report of ANOTHER sitting of S9 is not borrowed
    assert res["c5"].group == "no" and res["c5"].source == "sitting_report"
    assert (counts["join"]["by_sitting_id"], counts["join"]["by_session_id"], counts["join"]["no_report"]) == (3, 1, 1)
    assert counts["by_source"] == {"tick": 0, "sitting_report": 3, "session_report": 1, "none": 1}
    # the log of an older label_assist: its reports carry no sitting_id, so the session decides although the audit
    # names sittings
    (tmp_path / "old").mkdir()
    audit2, extras2, reports2 = load_ai_inputs(
        tmp_path / "old", saves, [ai_use_line("S1", "yes", tool="ChatGPT"), ai_use_line("S9", "no", tool="")])
    assert reports2.has_sitting_ids is False
    res2, counts2 = aw.classify_ai_use(shown, audit2, extras2, reports2)
    assert {k: v.group for k, v in res2.items()} == {"c1": "yes", "c2": "yes", "c3": "yes", "c4": "no", "c5": "yes"}
    assert counts2["join"]["by_session_id"] == 5 and counts2["join"]["by_sitting_id"] == 0


def test_a_ticked_cell_is_yes_whatever_its_sitting_reported_and_tools_are_grouped_by_normalized_name(tmp_path):
    saves = [{"cell_id": f"c{i}", "session_id": f"S{i}", "extra": {"sitting_id": f"S{i}-s1"}} for i in range(5)]
    saves += [{"cell_id": "t_no", "session_id": "S5", "extra": {"sitting_id": "S5-s1", "ai_used": True}},
              {"cell_id": "t_none", "session_id": "S6", "extra": {"sitting_id": "S6-s1", "ai_used": True}},
              {"cell_id": "t_yes", "session_id": "S0", "extra": {"sitting_id": "S0-s1", "ai_used": True}}]
    log = [ai_use_line("S0", "yes", tool="ChatGPT", sitting_id="S0-s1"),
           ai_use_line("S1", "yes", tool=" chatgpt. ", sitting_id="S1-s1"),
           ai_use_line("S2", "yes", tool="Claude + GPT-4", sitting_id="S2-s1"),
           ai_use_line("S3", "yes", tool="", sitting_id="S3-s1"),
           ai_use_line("S4", "no", tool="", approx=0, sitting_id="S4-s1"),
           ai_use_line("S5", "no", tool="", approx=0, sitting_id="S5-s1")]            # S6 has no report at all
    audit, extras, reports = load_ai_inputs(tmp_path, saves, log)
    shown = {s["cell_id"]: s["cell_id"] for s in saves}
    res, counts = aw.classify_ai_use(shown, audit, extras, reports)
    assert counts["by_group"] == {"yes": 7, "no": 1, "not recorded": 0}
    # two spellings of one tool are one group; several tools in one field are one group, not split
    assert counts["tools_among_yes_cells"] == [
        {"tool": aw.TOOL_NO_YES_REPORT, "n_cells": 2},        # ticked in a sitting that reported no, and in one with no report
        {"tool": aw.TOOL_NOT_GIVEN, "n_cells": 1},
        {"tool": "chatgpt", "n_cells": 3},                    # c0, c1 and the ticked t_yes
        {"tool": "claude + gpt-4", "n_cells": 1}]
    assert res["t_no"] == aw.AiUse("yes", True, aw.TOOL_NO_YES_REPORT, "tick")
    assert res["t_none"] == aw.AiUse("yes", True, aw.TOOL_NO_YES_REPORT, "tick")
    assert res["t_yes"] == aw.AiUse("yes", True, "chatgpt", "tick")
    assert res["c4"] == aw.AiUse("no", False, None, "sitting_report")
    # only a ticked cell is a ticked cell; the rest of the yes group is "of a sitting that reported AI use"
    assert counts["tick_only"]["by_group"] == {"ticked": 3, "not ticked": 5}
    assert counts["n_ticks_in_sittings_reporting_no"] == 1
    # a no-tool cell never carries a tool, and the tool counts cover the yes cells only
    assert all(v.tool is None for v in res.values() if v.group != "yes")
    assert sum(x["n_cells"] for x in counts["tools_among_yes_cells"]) == counts["by_group"]["yes"]


def test_ai_use_group_meanings_never_call_an_unticked_cell_a_cell_that_used_ai():
    meaning = aw.GROUP_MEANING["yes"]
    assert "ticked" in meaning and "reported" in meaning and "not cells shown to have used it" in meaning
    assert set(aw.GROUP_MEANING) == {"yes", "no", "not recorded"} and set(aw.TICK_ONLY_MEANING) == {"ticked", "not ticked"}
    for text in (*aw.GROUP_MEANING.values(), *aw.TICK_ONLY_MEANING.values(), aw.AI_RECORDING_NOTE):
        assert aw.scan_forbidden_wording(text) == [], text
    assert "ticked as AI use" in aw.TICK_ONLY_MEANING["ticked"]


# ---------------------------------------------------------------------------
# 9. wording, provenance and output-path guards
# ---------------------------------------------------------------------------
def test_label_source_strings_are_the_registered_wording():
    assert aw.LABEL_SOURCE_AH == "LLM-assisted (AI-drafted, author-revised) labels"
    assert aw.LABEL_SOURCE_WASHOUT == "same-rater washout pass"
    assert aw.LABEL_SOURCE_SECOND == "second, non-author annotator (AI tools permitted, self-reported)"
    for s in (aw.LABEL_SOURCE_AH, aw.LABEL_SOURCE_WASHOUT, aw.LABEL_SOURCE_SECOND):
        assert aw.scan_forbidden_wording(s) == []


@pytest.mark.parametrize("text,name", [
    ("these labels are verified", "verified"),
    ("Verified by the author", "verified"),
    ("an AH reference standard", "reference"),
    ("the reference_share key", "reference"),
    ("references", "reference"),
    ("an independent human annotator", "independent human/annotator/rater"),
    ("Independent blind human judgement", "independent human/annotator/rater"),
    ("an independent annotator", "independent human/annotator/rater"),
    ("test-retest reliability", "test-retest"),
    ("test–retest", "test-retest"),
    ("Test Retest", "test-retest"),
    ("PPA is the specificity", "specificity"),
    ("the cells that used AI", "cells that used AI"),
    ("a cell used an AI assistant", "cells that used AI"),
    ("these cells used chat tools", "cells that used AI"),
])
def test_forbidden_wording_scan_catches_each_word(text, name):
    assert name in aw.scan_forbidden_wording(text)


@pytest.mark.parametrize("text", [
    "same-rater agreement between the AH pass and the washout pass",
    "LLM-assisted (AI-drafted, author-revised) labels", "second, non-author annotator",
    "unverifiable", "the human pass", "sensitivity rerun excluding listed controls",
    "ticked cells", "cells of sittings that reported AI use", "the cells the labeler ticked as AI use",
    "cells shown to have used it",
])
def test_forbidden_wording_scan_leaves_the_registered_wording_alone(text):
    assert aw.scan_forbidden_wording(text) == []


def test_input_paths_are_masked_before_the_wording_scan():
    payload = {"provenance": {"inputs": {"design": {"path": "/data/reference/verified/design.csv", "sha256": "ab"}}},
               "x": 1}
    assert aw.scan_forbidden_wording(aw._text_for_wording_scan(payload)) == []
    payload["note"] = "a reference"
    assert aw.scan_forbidden_wording(aw._text_for_wording_scan(payload)) == ["reference"]


def test_tool_names_are_data_and_are_masked_before_the_wording_scan():
    payload = {"x": {"tools_among_yes_cells": [{"tool": "reference manager", "n_cells": 2}], "ai_tool": "verified-gpt"},
               "cells": [{"ai_tool": "independent human annotator bot"}]}
    assert aw.scan_forbidden_wording(aw._text_for_wording_scan(payload)) == []
    payload["x"]["note"] = "a reference manager"                  # the same words outside a tool key are our wording
    assert aw.scan_forbidden_wording(aw._text_for_wording_scan(payload)) == ["reference"]


def test_module_source_strings_that_reach_an_output_contain_no_forbidden_wording():
    for name in ("PINNED_WASHOUT", "UNPINNED_WASHOUT", "PINNED_SECOND", "UNPINNED_SECOND"):
        assert aw.scan_forbidden_wording(" ".join(getattr(aw, name))) == [], name
    assert aw.scan_forbidden_wording(json.dumps(aw.UNDEFINED_REASONS)) == []


# ---------------------------------------------------------------------------
# 10. synthetic end-to-end fixtures
# ---------------------------------------------------------------------------
SHEET_COLS = ["cell_id", "cq_id", "cluster_id", "category", "variant", "cq_text", "judge_evidence_span",
              "rendered_view_path", "evidence_span_verbatim", "A", "rater_L1", "note", "label_source"]
CATS = ["cat_a", "cat_b", "cat_c", "cat_d", "cat_e", "cat_f"]


def sheet_row(cid, cluster, cat, a, l1, source):
    return {"cell_id": cid, "cq_id": cluster, "cluster_id": cluster, "category": cat, "variant": "V",
            "cq_text": "synthetic", "A": a, "rater_L1": l1, "label_source": source}


def make_washout(tmp, *, seed=1, source="synthetic", ablated_a0=24, excluded=0, unlabeled=0, noise=0.3,
                 frame=100, drop_primary=0, packet=False):
    """A synthetic washout: AH sheet (frame primary cells + 36 controls whose values are garbage, so
    that any attempt to read them fails), sealed design (72 primary + 36 controls), washout sheet,
    audit and session log.  ``packet=True`` writes the label_assist --packet interface: the sheet's 13th and
    14th columns ``ai_used`` (every 5th row ticked) and ``dwell_ms`` (the running total in ms), audit lines with
    ``dwell_ms`` (the true dwell, while
    ``elapsed_s`` carries a clock skew of +100 s), ``sitting_id`` and ``ai_used``, SESSION lines with a
    ``sitting_id`` and one AI_USE report per sitting (sessions 1-3: yes with a tool, no, not recorded)."""
    rng = random.Random(seed)
    tmp.mkdir(parents=True, exist_ok=True)
    clusters = [f"cq{i:02d}" for i in range(1, 34)]
    ah_rows, pool = [], []
    for i in range(frame):
        cid, cl = f"P{i:03d}", clusters[i % len(clusters)]
        l1 = rng.choice([0, 1, 2, 3, 3, 2])
        a = 1 if l1 >= 2 else rng.choice([0, 0, 1])
        ah_rows.append(sheet_row(cid, cl, CATS[i % 6], a, l1, source))
        pool.append((cid, a, l1))
    ctl = [(f"abl-{i:02d}", "ablated_control") for i in range(24)] + [(f"pre-{i:02d}", "preserved_control") for i in range(12)]
    for n, (cid, _) in enumerate(ctl):
        ah_rows.append(sheet_row(cid, "cqX", "cat_a", "not-a-label" if n % 3 == 0 else "", "", source))
    ah_path = write_csv(tmp / "ah.csv", ah_rows, SHEET_COLS)

    design, wo_rows = [], []
    picked = rng.sample(pool, 72)
    for n, (cid, a, l1) in enumerate(picked):
        wid = f"w-{n:04d}"
        stratum = "proportional" if n < 48 else "enriched"
        prob = 0.32 if stratum == "proportional" else 24 / 38          # sum of 1/pi = 150 + 38 = 188
        design.append(design_row(wid, cid, "primary", stratum, repr(prob)))
        l1w = l1 if rng.random() > noise else min(3, max(0, l1 + rng.choice([-1, 1])))
        aw_ = a if rng.random() > noise else 1 - a
        wo_rows.append(sheet_row(wid, "cqY", "cat_a", aw_, l1w, source))
    k = 0
    for cid, kind in ctl:
        wid = f"w-c{k:03d}"
        k += 1
        reason, a_val = "", ""
        idx = int(cid.split("-")[1])
        if kind == "ablated_control":
            if idx < excluded:
                reason = "artifact_digest_mismatch"
            elif idx >= excluded + unlabeled:
                a_val = 0 if idx - excluded - unlabeled < ablated_a0 else 1
        else:
            a_val = 1 if idx < 11 else 0
        design.append(design_row(wid, cid, kind, "", "", reason))
        if not reason:
            wo_rows.append(sheet_row(wid, "cqY", "cat_a", a_val, 2 if a_val != "" else "", source))
    if drop_primary:                              # a design with fewer primary cells (and no sheet row for them)
        dropped = {r["cell_id"] for r in design[:drop_primary]}
        design = design[drop_primary:]
        wo_rows = [r for r in wo_rows if r["cell_id"] not in dropped]
    design_path = write_csv(tmp / "design.csv", design, DESIGN_COLS)
    ticked = {r["cell_id"] for i, r in enumerate(wo_rows) if i % 5 == 0} if packet else set()
    if packet:
        for r in wo_rows:
            r["ai_used"] = "yes" if r["cell_id"] in ticked else ""
    wo_path = write_csv(tmp / "washout.csv", wo_rows, SHEET_COLS + (["ai_used"] if packet else []))

    lines, log = [], []
    sids = ["1762560000-111-aaaaaa", "1762646400-222-bbbbbb", "1762732800-333-cccccc"]
    wids = [r["cell_id"] for r in wo_rows]
    per = (len(wids) + 2) // 3
    true_dwell, sitting_of, reports = {}, {}, {}
    packet_reports = [("yes", "Claude "), ("no", ""), ("not recorded", "")]
    for s, sid in enumerate(sids):
        start = T0 + datetime.timedelta(days=s)
        sitting = f"{sid}-s1"
        log.append(f"SESSION start={start.isoformat(timespec='seconds')} pid={111 * (s + 1)} session_id={sid}"
                   + (f" sitting_id={sitting} mode=packet" if packet else ""))
        chunk = wids[s::3] if packet else wids[s * per:(s + 1) * per]     # packet: every sitting sees every kind of row
        for j, wid in enumerate(chunk):
            ts = start + datetime.timedelta(seconds=60 * (j + 1))
            el = round(rng.uniform(6, 80), 1) if rng.random() > 0.05 else round(rng.uniform(2, 15), 1)
            true_dwell[wid] = el
            rec = {"ts": ts.isoformat(timespec="seconds"), "cell_id": wid, "row": j + 1, "A": 1,
                   "span_chars": 0, "rater_L1": "2", "first_opened_ts": None, "elapsed_s": el,
                   "session_id": sid}
            if packet:
                rec.update(elapsed_s=round(el + 100.0, 1), dwell_ms=int(round(el * 1000)), sitting_id=sitting,
                           ai_used=True if wid in ticked else None)
                sitting_of[wid] = sitting
            lines.append(json.dumps(rec))
        if packet:
            used, tool = packet_reports[s]
            reports[sitting] = (used, tool)
            log.append(ai_use_line(sid, used, tool=tool, approx=5 if used == "yes" else None,
                                   how="unanswered" if used == "not recorded" else "answered",
                                   sitting_id=sitting))
        end = start + datetime.timedelta(seconds=60 * (len(chunk) + 2))
        log.append(f"SESSION end={end.isoformat(timespec='seconds')} pid={111 * (s + 1)} saved={len(chunk)}")
    if packet:                    # the 14-column working CSV: ai_used, then dwell_ms (a running total, in ms)
        for r in wo_rows:
            r["dwell_ms"] = int(round(true_dwell[r["cell_id"]] * 1000))
        write_csv(wo_path, wo_rows, SHEET_COLS + ["ai_used", "dwell_ms"])
    audit_path = tmp / "washout.audit.jsonl"
    audit_path.write_text("\n".join(lines) + "\n")
    log_path = tmp / "washout.session_log.txt"
    log_path.write_text("\n".join(log) + "\n")
    expected_ai = ({wid: expected_ai_class(wid in ticked, reports[sitting_of[wid]]) for wid in wids}
                   if packet else {})
    return dict(design=design_path, ah=ah_path, washout=wo_path, audit=audit_path, log=log_path,
                design_rows=design, ablated_ids=[c for c, k in ctl if k == "ablated_control"],
                primary_sources=[r["source_cell_id"] for r in design if r["cell_kind"] == "primary"],
                primary_ids=[r["cell_id"] for r in design if r["cell_kind"] == "primary"],
                control_ids=[r["cell_id"] for r in design if r["cell_kind"] != "primary" and not r["excluded_reason"]],
                ticked=ticked, true_dwell=true_dwell, sitting_of=sitting_of, expected_ai=expected_ai)


def washout_argv(fx, out, *extra, cells=None):
    argv = ["washout", "--design", str(fx["design"]), "--ah-labels", str(fx["ah"]),
            "--washout-labels", str(fx["washout"]), "--audit", str(fx["audit"]),
            "--session-log", str(fx["log"]), "--seed", str(SEED), "--out", str(out)]
    if cells is not None:
        argv += ["--out-cells", str(cells)]
    return argv + list(extra)


SECOND_SITTINGS = ["sessA-s1", "sessA-s2", "sessB-s1", "sessB-s2", "sessC-s1", "sessC-s2"]
# what each sitting reported at its end: (used, the tool as typed); sessC-s2 filed no report at all
SECOND_REPORTS = {"sessA-s1": ("yes", "ChatGPT "), "sessA-s2": ("no", ""), "sessB-s1": ("yes", "Claude.ai"),
                  "sessB-s2": ("yes", ""), "sessC-s1": ("not recorded", "")}


def make_second(tmp, *, seed=3, opaque=False, source="synthetic", ai_flags=True, session_report=True,
                sheet_ai_column=True, packet=False):
    """A synthetic second-annotation fixture: judge run, AH sheet, the 48-cell list, the annotator's sheet, an
    audit in which every 4th cell carries an ``ai_used: true`` tick, and a session log whose sessions sessA
    (k % 3 == 0) and sessB (k % 3 == 1) declare AI use yes and no, and sessC declares nothing.

    ``packet=True`` writes the label_assist --packet interface instead: six sittings (cell k belongs to
    ``SECOND_SITTINGS[k % 6]``), audit lines with ``sitting_id`` and ``dwell_ms`` (the true dwell, while
    ``elapsed_s`` carries a clock skew of +100 s), SESSION lines with a ``sitting_id`` and one AI_USE report
    per sitting (``SECOND_REPORTS``).  The returned ``expected_ai`` is the classification worked out here, by a
    plain re-statement of the rule, for every sample cell: (group, ticked, normalized tool)."""
    rng = random.Random(seed)
    tmp.mkdir(parents=True, exist_ok=True)
    cells, ah_rows = [], []
    n = 0
    for cat in CATS:
        for i in range(20):
            cid, cluster = f"{cat}-{i:02d}", f"cq{(n % 30) + 1:02d}"
            j = rng.choice([0, 1, 2, 3, 3, 2, 1])
            cells.append({"cell_id": cid, "cq_id": cluster, "cluster_id": cluster, "variant": "V",
                          "category": cat, "J": j})
            l1 = max(0, min(3, j + rng.choice([-1, 0, 0, 0, 1])))
            ah_rows.append(sheet_row(cid, cluster, cat, 1 if l1 >= 2 else rng.choice([0, 0, 1]), l1, source))
            n += 1
    for i in range(12):
        cid = f"ctl-{i:02d}"
        cells.append({"cell_id": cid, "cq_id": "cqX", "cluster_id": "cqX", "variant": "V", "category": "cat_a",
                      "cell_kind": "ablated_control" if i < 8 else "preserved_control", "J": 1})
        ah_rows.append(sheet_row(cid, "cqX", "cat_a", "not-a-label", "", source))
    cells_path = tmp / "cells.jsonl"
    cells_path.write_text("\n".join(json.dumps(c) for c in cells) + "\n")
    ah_path = write_csv(tmp / "ah.csv", ah_rows, SHEET_COLS)
    sample = aw.second_annotator_sample(cells)
    list_path = tmp / "sample48.txt"
    list_path.write_bytes(aw.sample_list_bytes(sample))
    by_id = {r["cell_id"]: r for r in ah_rows}
    id_map, s_rows, shown = {}, [], {}
    for k, sid in enumerate(sample):
        oid = f"s-{k:03d}" if opaque else sid
        id_map[oid], shown[sid] = sid, oid
        r = by_id[sid]
        l1 = max(0, min(3, int(r["rater_L1"]) + rng.choice([-1, 0, 0, 1])))
        a = int(r["A"]) if rng.random() > 0.2 else 1 - int(r["A"])
        row = sheet_row(oid, "cqZ", "cat_a", a, l1, source)
        row["ai_used"] = "yes" if (ai_flags and k % 4 == 0) else ""             # the --packet working CSV, 13th column
        s_rows.append(row)
    second_path = write_csv(tmp / "second.csv", s_rows, SHEET_COLS + (["ai_used"] if sheet_ai_column else []))
    map_path = (write_csv(tmp / "idmap.csv", [{"cell_id": o, "source_cell_id": s} for o, s in id_map.items()],
                          ["cell_id", "source_cell_id"]) if opaque else None)
    lines = []
    true_dwell, sitting_of, expected_ai = {}, {}, {}
    for k, sid in enumerate(sample):
        el = round(rng.uniform(5, 70), 1)
        true_dwell[shown[sid]] = el
        ticked = bool(ai_flags and k % 4 == 0)
        sitting = SECOND_SITTINGS[k % 6] if packet else None
        session = sitting.split("-")[0] if packet else ["sessA", "sessB", "sessC"][k % 3]
        rec = {"ts": (T0 + datetime.timedelta(seconds=90 * k)).isoformat(timespec="seconds"),
               "cell_id": shown[sid], "row": k + 1, "A": 1, "span_chars": 0, "rater_L1": "2",
               "first_opened_ts": None, "elapsed_s": el, "session_id": session}
        if packet:
            rec.update(elapsed_s=round(el + 100.0, 1), dwell_ms=int(round(el * 1000)), sitting_id=sitting)
            sitting_of[sid] = sitting
        rec["ai_used"] = True if ticked else None                                   # label_assist --packet
        lines.append(json.dumps(rec))
        if packet:
            expected_ai[sid] = expected_ai_class(ticked, SECOND_REPORTS.get(sitting) if session_report else None)
    if packet:                    # the 14-column working CSV: ai_used (optional here), then dwell_ms (running total, ms)
        for r in s_rows:
            r["dwell_ms"] = int(round(true_dwell[r["cell_id"]] * 1000))
        write_csv(second_path, s_rows, SHEET_COLS + (["ai_used"] if sheet_ai_column else []) + ["dwell_ms"])
    audit_path = tmp / "second.audit.jsonl"
    audit_path.write_text("\n".join(lines) + "\n")
    log = []
    if packet:
        for n, sit in enumerate(SECOND_SITTINGS):
            sid = sit.split("-")[0]
            start = T0 + datetime.timedelta(days=n)
            log.append(f"SESSION start={start.isoformat(timespec='seconds')} pid={50 + n} session_id={sid} "
                       f"sitting_id={sit} mode=packet sheet_sha256=0123456789abcdef")
            if session_report and sit in SECOND_REPORTS:
                used, tool = SECOND_REPORTS[sit]
                log.append(ai_use_line(sid, used, tool=tool, approx=4 if used == "yes" else None,
                                       how="unanswered" if used == "not recorded" else "answered",
                                       sitting_id=sit))
            log.append(f"SESSION end={(start + datetime.timedelta(hours=1)).isoformat(timespec='seconds')} "
                       f"pid={50 + n} saved=8")
    else:
        for n, sid in enumerate(["sessA", "sessB", "sessC"]):
            start = T0 + datetime.timedelta(days=n)
            log.append(f"SESSION start={start.isoformat(timespec='seconds')} pid={50 + n} session_id={sid} "
                       "mode=packet sheet_sha256=0123456789abcdef")
            if session_report and sid == "sessA":
                log.append(ai_use_line(sid, "no", tool="", approx=0))
                log.append(ai_use_line(sid, "yes", tool="a chat assistant", approx=9))     # the later line wins
            elif session_report and sid == "sessB":
                log.append(ai_use_line(sid, "no", tool="", approx=0))
            log.append(f"SESSION end={(start + datetime.timedelta(hours=1)).isoformat(timespec='seconds')} "
                       f"pid={50 + n} saved=16")
    log_path = tmp / "second.session_log.txt"
    log_path.write_text("\n".join(log) + "\n")
    return dict(cells=cells_path, ah=ah_path, second=second_path, sample=list_path, idmap=map_path,
                audit=audit_path, log=log_path, sample_ids=sample, cell_rows=cells, true_dwell=true_dwell,
                sitting_of=sitting_of, expected_ai=expected_ai)


def second_argv(fx, out, *extra, cells=None, unregistered=True):
    argv = ["second", "--cells", str(fx["cells"]), "--ah-labels", str(fx["ah"]),
            "--second-labels", str(fx["second"]), "--sample-list", str(fx["sample"]),
            "--seed", str(SEED), "--audit", str(fx["audit"]), "--washout-locked", "--out", str(out)]
    if unregistered:
        argv.append("--allow-unregistered-sample")
    if fx["idmap"] is not None:
        argv += ["--id-map", str(fx["idmap"])]
    if fx["log"] is not None:
        argv += ["--session-log", str(fx["log"])]
    if cells is not None:
        argv += ["--out-cells", str(cells)]
    return argv + list(extra)


@pytest.fixture
def small_b(monkeypatch):
    monkeypatch.setattr(aw, "BOOTSTRAP_RESAMPLES", SMALL_B)


def load(path):
    return json.loads(Path(path).read_text())


# ---- washout command ------------------------------------------------------
def test_washout_cli_end_to_end_structure_provenance_and_no_identifiers(tmp_path, small_b, capsys):
    fx = make_washout(tmp_path / "in")
    out, cells = tmp_path / "out.json", tmp_path / "cells.json"
    assert aw.main(washout_argv(fx, out, cells=cells)) == 0
    err = capsys.readouterr().err
    assert "lock-manifest check was not performed" in err and "keep it sealed" in err
    res, per_cell = load(out), load(cells)

    assert res["label_sources"] == {"ah_pass": "LLM-assisted (AI-drafted, author-revised) labels",
                                    "washout_pass": "same-rater washout pass"}
    assert res["rehearsal"] is True and "rehearsal_note" in res               # synthetic source marker
    assert res["design_check"]["conforms"] is True
    g2 = res["G2"]
    assert g2["gate_input"] == "reweighted_pooled" and g2["threshold"] == 0.70 and g2["resamples"] == SMALL_B
    assert g2["status"] in ("pass", "fail") and set(g2["estimates"]) == {"per_stratum", "reweighted_pooled"}
    assert set(g2["estimates"]["per_stratum"]) == {"proportional", "enriched"}
    assert g2["weights_summary"]["ht_frame_size_estimate"] == pytest.approx(188.0)
    assert res["G3_W"]["ablated"]["status"] == "pass" and res["G3_W"]["ablated"]["A0_over_valid"] == "24/24"
    assert res["G3_W"]["preserved"]["A1_over_valid"] == "11/12"
    assert res["dwell_check"]["primary_cells"]["n_cells"] == 72
    assert res["dwell_check"]["all_presented_rows"]["n_cells"] == 108
    assert res["dwell_check"]["sessions"]["n_sessions"] == 3
    assert res["pinned_choices"] and res["unpinned_choices"] and res["limitations"]
    assert res["A_agreement_between_passes"]["descriptive_only"] is True

    # provenance, in the main file and in the per-cell file
    for doc in (res, per_cell):
        p = doc["provenance"]
        assert p["analyzer"]["sha256"] == hashlib.sha256(Path(aw.__file__).read_bytes()).hexdigest()
        assert p["analyzer"]["registered_helpers_sha256"] == hashlib.sha256(Path(ah.__file__).read_bytes()).hexdigest()
        assert set(p["inputs"]) == {"design", "ah_labels", "washout_labels", "audit", "session_log"}
        assert p["inputs"]["washout_labels"]["sha256"] == hashlib.sha256(fx["washout"].read_bytes()).hexdigest()
        assert p["bootstrap"]["seed"] == SEED and p["bootstrap"]["registered_seed_used"] is True
        assert p["bootstrap"]["resamples"] == SMALL_B and p["bootstrap"]["registered_resamples"] == 10_000
        assert p["bootstrap"]["bca_ties"] == "midrank"
        assert p["label_sources"] == res["label_sources"]
        assert p["assertions"]["ah_control_label_values_read"] is False
        assert "self-reported" in p["ai_assistance"]
        assert "git" in p["analyzer"]
    assert per_cell["provenance"] == res["provenance"]

    # aggregates only: no washout id, AH id, control id or CQ id in the main file
    text = out.read_text()
    ids = [r["cell_id"] for r in fx["design_rows"]] + [r["source_cell_id"] for r in fx["design_rows"]]
    ids += [f"cq{i:02d}" for i in range(1, 34)] + ["cqX", "cqY"]
    assert ah.find_cell_level_leaks(text, ids) == []
    assert ah.find_cell_level_leaks(cells.read_text(), ids)                     # the sealed file does hold them
    assert len(per_cell["primary_cells"]) == 72 and len(per_cell["controls"]) == 36
    assert aw.scan_forbidden_wording(aw._text_for_wording_scan(res)) == []
    assert aw.scan_forbidden_wording(aw._text_for_wording_scan(per_cell)) == []
    # the AH control values (garbage in the sheet) were never read
    assert "not-a-label" not in text and "not-a-label" not in cells.read_text()


def test_washout_cli_is_deterministic_and_does_not_depend_on_row_order(tmp_path, small_b):
    fx = make_washout(tmp_path / "in")
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    aw.main(washout_argv(fx, a))
    aw.main(washout_argv(fx, b))
    assert a.read_bytes() == b.read_bytes()                                       # no timestamps, same bytes
    aw.main(washout_argv(fx, a, "--overwrite"))
    assert a.read_bytes() == b.read_bytes()
    # shuffle the design rows and the washout sheet rows: the numbers do not change
    rows = list(fx["design_rows"])
    random.Random(9).shuffle(rows)
    shuffled = write_csv(tmp_path / "in" / "design_shuffled.csv", rows, DESIGN_COLS)
    fx2 = {**fx, "design": shuffled}
    c = tmp_path / "c.json"
    aw.main(washout_argv(fx2, c))
    ra, rc = load(a), load(c)
    for key in ("G2", "A_agreement_between_passes", "G3_W"):
        assert ra[key] == rc[key], key


def test_washout_cli_reads_the_builders_mapping_as_the_design_and_gets_the_same_numbers(tmp_path, small_b):
    fx = make_washout(tmp_path / "in")
    mapping = tmp_path / "in" / "washout_mapping.json"
    mapping.write_text(json.dumps(builder_style_mapping(fx["design_rows"])))
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    aw.main(washout_argv(fx, a))
    aw.main(washout_argv({**fx, "design": mapping}, b))
    ra, rb = load(a), load(b)
    # 4-decimal pi (the builder rounds half-up) changes the weights a little; the structure is identical
    assert set(ra) == set(rb) and rb["design_check"]["conforms"] is True
    assert ra["G3_W"] == rb["G3_W"] and rb["G2"]["gate_input"] == "reweighted_pooled"
    assert rb["G2"]["estimates"]["reweighted_pooled"]["kish_n_eff"] == pytest.approx(
        ra["G2"]["estimates"]["reweighted_pooled"]["kish_n_eff"], rel=1e-3)
    assert rb["provenance"]["inputs"]["design"]["path"].endswith("washout_mapping.json")


def test_washout_cli_never_reads_an_ah_control_row_even_if_the_design_lacks_that_control(tmp_path, small_b):
    fx = make_washout(tmp_path / "in")
    rows = read_rows(fx["ah"])
    # two control rows with the real id format (kind:variant:CQ) and values that would be read as labels
    rows.append(sheet_row("ablated_control:F:CQB05", "CQB05", "cat_a", "1", "3", "synthetic"))
    rows.append(sheet_row("preserved_control:C:CQB09", "CQB09", "cat_a", "bad-value", "7", "synthetic"))
    write_csv(fx["ah"], rows, SHEET_COLS)
    out = tmp_path / "o.json"
    assert aw.main(washout_argv(fx, out, cells=tmp_path / "c.json")) == 0      # neither is in the design, neither is read
    text = out.read_text() + (tmp_path / "c.json").read_text()
    assert "bad-value" not in text and "CQB05" not in text and "CQB09" not in text
    # an ordinary non-control id with an invalid A is still an error (the tolerance is for controls only)
    rows.append(sheet_row("P999", "cq01", "cat_a", "bad-value", "1", "synthetic"))
    write_csv(fx["ah"], rows, SHEET_COLS)
    with pytest.raises(SystemExit, match="A must be exactly 0 or 1"):
        aw.main(washout_argv(fx, tmp_path / "o2.json"))


def test_washout_cli_g3w_without_all_24_gives_no_verdict_and_counts(tmp_path, small_b):
    fx = make_washout(tmp_path / "in", excluded=2)
    out = tmp_path / "out.json"
    aw.main(washout_argv(fx, out))
    abl = load(out)["G3_W"]["ablated"]
    assert abl["status"] == "not_computable" and abl["n_valid"] == 22 and abl["A0_over_valid"] == "22/22"
    assert load(out)["G3_W"]["excluded_by_design_reasons"] == {"artifact_digest_mismatch": 2}
    fx = make_washout(tmp_path / "in2", unlabeled=1)
    out2 = tmp_path / "out2.json"
    aw.main(washout_argv(fx, out2))
    abl2 = load(out2)["G3_W"]["ablated"]
    assert abl2["status"] == "not_computable" and abl2["n_presented_not_labeled"] == 1 and abl2["n_valid"] == 23


def test_washout_cli_g3w_fails_below_22_of_24(tmp_path, small_b):
    fx = make_washout(tmp_path / "in", ablated_a0=21)
    out = tmp_path / "out.json"
    aw.main(washout_argv(fx, out))
    assert load(out)["G3_W"]["ablated"]["status"] == "fail"


def test_washout_cli_rerun_excluding_a_listed_set_of_controls(tmp_path, small_b):
    fx = make_washout(tmp_path / "in")
    listed = tmp_path / "seen.txt"
    listed.write_text("# the eight seen with the prefix\n" + "\n".join(fx["ablated_ids"][:8]) + "\n")
    out = tmp_path / "out.json"
    aw.main(washout_argv(fx, out, "--exclude-controls", str(listed)))
    res = load(out)
    sens = res["G3_W"]["sensitivity_excluding_listed_controls"]
    assert res["G3_W"]["ablated"]["status"] == "pass"
    assert sens["ablated"]["status"] == "not_computable" and sens["ablated"]["n_valid"] == 16
    assert sens["ablated"]["A0_over_valid"] == "16/16" and sens["n_listed_matched_ablated"] == 8
    assert "exclude_controls" in res["provenance"]["inputs"]
    # an id that matches nothing, and a primary id, are errors
    bad = tmp_path / "bad.txt"
    bad.write_text("abl-00\nnope\n")
    with pytest.raises(SystemExit, match="match no control"):
        aw.main(washout_argv(fx, tmp_path / "o2.json", "--exclude-controls", str(bad)))
    prim = tmp_path / "prim.txt"
    prim.write_text(fx["primary_sources"][0] + "\n")
    with pytest.raises(SystemExit, match="primary"):
        aw.main(washout_argv(fx, tmp_path / "o3.json", "--exclude-controls", str(prim)))


def test_washout_cli_refuses_a_design_that_is_not_the_registered_one_unless_told(tmp_path, small_b):
    fx = make_washout(tmp_path / "in", drop_primary=1)                              # 71 primary cells
    with pytest.raises(SystemExit, match="not the registered one"):
        aw.main(washout_argv(fx, tmp_path / "o.json"))
    assert not (tmp_path / "o.json").exists()
    assert aw.main(washout_argv(fx, tmp_path / "o2.json", "--allow-design-deviation")) == 0
    res = load(tmp_path / "o2.json")
    assert res["design_check"]["conforms"] is False and res["design_check"]["allow_design_deviation"] is True
    assert res["G2"]["n_primary_cells"] == 71


def test_washout_cli_refuses_incomplete_primary_labels_and_unknown_label_rows(tmp_path, small_b):
    fx = make_washout(tmp_path / "in")
    rows = read_rows(fx["washout"])
    rows[0]["rater_L1"] = ""
    write_csv(fx["washout"], rows, SHEET_COLS)
    with pytest.raises(SystemExit, match="washout labels lack A or rater_L1"):
        aw.main(washout_argv(fx, tmp_path / "o.json"))
    fx = make_washout(tmp_path / "in2")
    rows = read_rows(fx["washout"])
    rows.append(sheet_row("w-9999", "cqY", "cat_a", 1, 2, "synthetic"))
    write_csv(fx["washout"], rows, SHEET_COLS)
    with pytest.raises(SystemExit, match="absent from the design"):
        aw.main(washout_argv(fx, tmp_path / "o2.json"))


def test_washout_cli_label_source_rules(tmp_path, small_b):
    fx = make_washout(tmp_path / "in", source="")                                   # no marker in the sheets
    with pytest.raises(SystemExit, match="no label source"):
        aw.main(washout_argv(fx, tmp_path / "o.json"))
    assert aw.main(washout_argv(fx, tmp_path / "o2.json", "--label-source", "synthetic")) == 0
    assert load(tmp_path / "o2.json")["rehearsal"] is True
    fx_h = make_washout(tmp_path / "in_h", source="human")      # synthetic fixture that carries the 'human' marker
    assert aw.main(washout_argv(fx_h, tmp_path / "o3.json")) == 0
    res = load(tmp_path / "o3.json")
    assert res["rehearsal"] is False and "rehearsal_note" not in res
    assert res["label_sources"]["ah_pass"] == aw.LABEL_SOURCE_AH
    # one sheet human, the other simulated: refused
    fx_m = make_washout(tmp_path / "in_m", source="human")
    rows = read_rows(fx_m["washout"])
    for r in rows:
        r["label_source"] = "synthetic"
    write_csv(fx_m["washout"], rows, SHEET_COLS)
    with pytest.raises(SystemExit, match="label sources"):
        aw.main(washout_argv(fx_m, tmp_path / "o4.json"))


def test_washout_cli_expected_sha256_must_match_the_locked_file(tmp_path, small_b, capsys):
    fx = make_washout(tmp_path / "in")
    good = hashlib.sha256(fx["washout"].read_bytes()).hexdigest()
    out = tmp_path / "o.json"
    assert aw.main(washout_argv(fx, out, "--expect-sha256", f"washout_labels={good}",
                                "--expect-sha256", f"ah-labels={hashlib.sha256(fx['ah'].read_bytes()).hexdigest()}")) == 0
    res = load(out)
    assert res["provenance"]["input_hash_assertions"]["washout_labels"] == {"expected": good, "matched": True}
    assert res["provenance"]["assertions"]["washout_lock_manifest_sha256_checked"] is True
    assert "lock-manifest check was not performed" not in capsys.readouterr().err
    with pytest.raises(SystemExit, match="not the locked file"):
        aw.main(washout_argv(fx, tmp_path / "o2.json", "--expect-sha256", "washout_labels=" + "0" * 64))
    assert not (tmp_path / "o2.json").exists()
    for bad in ("washout_labels=xyz", "nonsense=" + "0" * 64, "washout_labels"):
        with pytest.raises(SystemExit, match="NAME=<64 hex>"):
            aw.main(washout_argv(fx, tmp_path / "o3.json", "--expect-sha256", bad))
    with pytest.raises(SystemExit, match="not given"):
        aw.main(washout_argv(fx, tmp_path / "o4.json", "--expect-sha256", "cells=" + "0" * 64))


def test_washout_cli_warns_about_a_seed_that_is_not_the_registered_one(tmp_path, small_b, capsys):
    fx = make_washout(tmp_path / "in")
    argv = washout_argv(fx, tmp_path / "o.json")
    argv[argv.index("--seed") + 1] = "7"
    aw.main(argv)
    assert "not the registered seed" in capsys.readouterr().err
    assert load(tmp_path / "o.json")["provenance"]["bootstrap"]["registered_seed_used"] is False


def test_washout_cli_seed_is_required(tmp_path, small_b):
    fx = make_washout(tmp_path / "in")
    argv = washout_argv(fx, tmp_path / "o.json")
    i = argv.index("--seed")
    del argv[i:i + 2]
    with pytest.raises(SystemExit):
        aw.main(argv)


def test_washout_cli_reports_a_counts_only_ai_use_block_and_the_per_cell_fields(tmp_path, small_b):
    fx = make_washout(tmp_path / "in", packet=True)
    out, cells = tmp_path / "o.json", tmp_path / "c.json"
    assert aw.main(washout_argv(fx, out, cells=cells)) == 0
    res, per_cell = load(out), load(cells)
    block = res["ai_use_classification"]
    assert block["counts_only"] is True and "ai_use_stratified" in block["note"] and "D20" in block["note"]
    prim, ctl = block["primary_cells"], block["presented_controls"]
    # worked out by hand from make_washout: row i is in the sitting i % 3 (reports yes/Claude, no, not recorded) and
    # every 5th row is ticked; rows 0-71 are the primary cells, 72-107 the presented controls
    assert prim["by_group"] == {"yes": 34, "no": 19, "not recorded": 19}
    assert prim["tick_only"]["by_group"] == {"ticked": 15, "not ticked": 57}
    assert {x["tool"]: x["n_cells"] for x in prim["tools_among_yes_cells"]} == {"claude": 24, aw.TOOL_NO_YES_REPORT: 10}
    assert prim["by_source"] == {"tick": 15, "sitting_report": 38, "session_report": 0, "none": 19}
    assert (prim["join"]["by_sitting_id"], prim["join"]["by_session_id"], prim["join"]["no_report"]) == (72, 0, 0)
    assert prim["n_ticks_in_sittings_reporting_no"] == 5
    assert prim["sheet_column_present"] is True and prim["n_sheet_audit_conflicts"] == 0
    assert ctl["by_group"] == {"yes": 16, "no": 10, "not recorded": 10}
    assert ctl["tick_only"]["by_group"] == {"ticked": 7, "not ticked": 29}
    assert {x["tool"]: x["n_cells"] for x in ctl["tools_among_yes_cells"]} == {"claude": 12, aw.TOOL_NO_YES_REPORT: 4}
    sr = block["session_reports"]
    assert (sr["n_reports"], sr["n_reports_with_sitting_id"]) == (3, 3)
    assert sr["by_declared_use"] == {"yes": 1, "no": 1, "not recorded": 1}
    assert sr["tools_in_yes_reports"] == [{"tool": "claude", "n_reports": 1}]
    assert sr["approx_cells_declared_in_yes_reports"] == 5
    # counts only: no statistic in the block, and G2 is not split by AI use or tool
    assert "qwk" not in json.dumps(block).lower() and "ci_lo" not in json.dumps(block)
    assert set(res["G2"]["estimates"]) == {"per_stratum", "reweighted_pooled"}
    # the sealed per-cell file carries the classification of every cell, the aggregates file no identifier
    assert {r["cell_id"] for r in per_cell["primary_cells"]} == set(fx["primary_ids"])
    assert {r["cell_id"] for r in per_cell["controls"]} == set(fx["control_ids"])
    for row in per_cell["primary_cells"] + per_cell["controls"]:
        assert (row["ai_use"], row["ai_ticked"], row["ai_tool"]) == fx["expected_ai"][row["cell_id"]]
    ids = fx["primary_ids"] + fx["control_ids"] + fx["primary_sources"]
    assert ah.find_cell_level_leaks(out.read_text(), ids) == []
    assert aw.scan_forbidden_wording(aw._text_for_wording_scan(res)) == []
    assert aw.scan_forbidden_wording(aw._text_for_wording_scan(per_cell)) == []


def test_washout_cli_without_any_ai_information_reports_everything_as_not_recorded(tmp_path, small_b):
    fx = make_washout(tmp_path / "in")                         # an AH-mode audit and log: no tick, no sitting, no report
    out = tmp_path / "o.json"
    assert aw.main(washout_argv(fx, out)) == 0
    block = load(out)["ai_use_classification"]
    assert block["primary_cells"]["by_group"] == {"yes": 0, "no": 0, "not recorded": 72}
    assert block["primary_cells"]["sheet_column_present"] is False
    assert block["primary_cells"]["tick_only"]["by_group"] == {"ticked": 0, "not ticked": 72}
    assert block["primary_cells"]["tools_among_yes_cells"] == [] and block["session_reports"]["n_reports"] == 0
    assert block["presented_controls"]["by_group"] == {"yes": 0, "no": 0, "not recorded": 36}


def test_washout_cli_with_neither_audit_nor_log_still_counts_the_sheets_ticks(tmp_path, small_b):
    fx = make_washout(tmp_path / "in", packet=True)
    argv = washout_argv(fx, tmp_path / "o.json")
    for flag in ("--audit", "--session-log"):
        i = argv.index(flag)
        del argv[i:i + 2]
    assert aw.main(argv) == 0
    res = load(tmp_path / "o.json")
    prim = res["ai_use_classification"]["primary_cells"]
    assert prim["by_group"] == {"yes": 15, "no": 0, "not recorded": 57}               # the ticks of the sheet, nothing else
    assert prim["tools_among_yes_cells"] == [{"tool": aw.TOOL_NO_YES_REPORT, "n_cells": 15}]
    assert prim["join"]["no_report"] == 72
    assert res["dwell_check"]["primary_cells"]["status"] == "not_computable"
    assert res["G2"]["washout_gap"]["status"] == "not_computable"


def test_washout_cli_dwell_check_uses_dwell_ms_in_packet_mode_and_elapsed_s_otherwise(tmp_path, small_b):
    fx = make_washout(tmp_path / "in", packet=True)
    out = tmp_path / "o.json"
    assert aw.main(washout_argv(fx, out)) == 0
    d = load(out)["dwell_check"]
    prim = [fx["true_dwell"][w] for w in fx["primary_ids"]]
    n_fast = sum(v < 20 for v in prim)
    assert 0 < n_fast < 72
    # the fixture's elapsed_s carries a +100 s clock skew: read instead of dwell_ms it would show nobody under 20 s
    assert min(json.loads(line)["elapsed_s"] for line in fx["audit"].read_text().splitlines()) > 100
    p = d["primary_cells"]
    assert p["basis_used"] == "dwell_ms" and p["saves_by_basis"] == {"dwell_ms": 72, "elapsed_s": 0, "none": 0}
    assert p["n_under_20s"] == n_fast and p["share_under_20s"] == pytest.approx(n_fast / 72)
    assert [p["q1_s"], p["median_s"], p["q3_s"]] == pytest.approx(list(np.percentile(prim, [25, 50, 75])))
    assert "dwell_ms" in p["basis"] and p["n_dwell_ms_unusable"] == 0
    assert d["all_presented_rows"]["basis_used"] == "dwell_ms" and d["all_presented_rows"]["n_cells"] == 108
    assert d["sessions"]["n_sessions"] == 3 and d["sessions"]["n_sittings_in_log"] == 3
    assert d["sessions"]["n_sittings_with_saves"] == 3
    assert {s["sitting_id"] for s in d["sessions"]["sessions"]} == set(fx["sitting_of"].values())
    # an AH-mode audit (no dwell_ms) is measured on elapsed_s, and the output says so
    fx2 = make_washout(tmp_path / "in2")
    out2 = tmp_path / "o2.json"
    assert aw.main(washout_argv(fx2, out2)) == 0
    p2 = load(out2)["dwell_check"]["primary_cells"]
    want = [fx2["true_dwell"][w] for w in fx2["primary_ids"]]
    assert p2["basis_used"] == "elapsed_s" and p2["saves_by_basis"] == {"dwell_ms": 0, "elapsed_s": 72, "none": 0}
    assert p2["n_under_20s"] == sum(v < 20 for v in want)
    assert load(out2)["dwell_check"]["sessions"]["n_sittings_with_saves"] is None


def test_washout_cli_reports_the_washout_gap_in_the_g2_output(tmp_path, small_b, capsys):
    fx = make_washout(tmp_path / "in")
    out = tmp_path / "o.json"
    assert aw.main(washout_argv(fx, out)) == 0
    res = load(out)
    gap = res["G2"]["washout_gap"]
    # the first washout save is T0 + 60 s = 2026-11-08T09:01:00+09:00; the AH pass's last save is
    # 2026-10-08T23:58:55+09:00: 30 days and 9 h 02 min 05 s apart
    assert gap["ah_last_save"] == "2026-10-08T23:58:55+09:00" and gap["ah_last_save_source"].startswith("registered")
    assert gap["first_washout_save_utc"] == "2026-11-08T00:01:00+00:00"
    assert gap["gap_days"] == pytest.approx(30 + 32525 / 86400, abs=1e-9)
    assert gap["meets_registered_minimum"] is True and gap["meets_target"] is True
    assert (gap["registered_minimum_days"], gap["target_days"]) == (21, 28)
    assert res["provenance"]["assertions"]["ah_last_save"] == "2026-10-08T23:58:55+09:00"
    assert res["provenance"]["assertions"]["ah_last_save_is_the_registered_value"] is True
    summary = json.loads(capsys.readouterr().out)
    assert summary["washout_gap_days"] == pytest.approx(gap["gap_days"])
    # measured from another last save (an explicit flag): a gap under the 21 days is reported with its length
    out2 = tmp_path / "o2.json"
    assert aw.main(washout_argv(fx, out2, "--ah-last-save", "2026-10-20T00:00:00+00:00")) == 0
    res2 = load(out2)
    gap2 = res2["G2"]["washout_gap"]
    assert gap2["gap_days"] == pytest.approx(19 + 60 / 86400, abs=1e-9) and gap2["meets_registered_minimum"] is False
    assert gap2["ah_last_save_source"] == "--ah-last-save"
    assert res2["provenance"]["assertions"]["ah_last_save_is_the_registered_value"] is False
    assert res2["G2"]["estimates"] == res["G2"]["estimates"] and res2["G2"]["status"] == res["G2"]["status"]
    # the same value written in another offset is the registered one
    out3 = tmp_path / "o3.json"
    assert aw.main(washout_argv(fx, out3, "--ah-last-save", "2026-10-08T14:58:55+00:00")) == 0
    assert load(out3)["G2"]["washout_gap"]["gap_days"] == pytest.approx(gap["gap_days"], abs=1e-12)
    # a time without an offset, or no time at all, is refused before anything is written
    for bad in ("2026-10-20T00:00:00", "yesterday"):
        with pytest.raises(SystemExit, match="explicit UTC offset"):
            aw.main(washout_argv(fx, tmp_path / "bad.json", "--ah-last-save", bad))
    assert not (tmp_path / "bad.json").exists()


def test_washout_cli_gap_counts_the_first_save_of_a_control_too(tmp_path, small_b):
    fx = make_washout(tmp_path / "in")
    lines = fx["audit"].read_text().splitlines()
    last = json.loads(lines[-1])                          # a save of the last control row
    assert last["cell_id"] in fx["control_ids"]
    last["ts"] = "2026-11-01T09:00:00+09:00"              # earlier than every other save of the pass
    lines[-1] = json.dumps(last)
    fx["audit"].write_text("\n".join(lines) + "\n")
    out = tmp_path / "o.json"
    assert aw.main(washout_argv(fx, out)) == 0
    gap = load(out)["G2"]["washout_gap"]
    # 2026-10-08T14:58:55Z -> 2026-11-01T00:00:00Z = 23 days 09:01:05
    assert gap["first_washout_save_utc"] == "2026-11-01T00:00:00+00:00"
    assert gap["gap_days"] == pytest.approx(23 + 32465 / 86400, abs=1e-9)


def test_washout_cli_ai_block_counts_only_the_presented_controls(tmp_path, small_b):
    fx = make_washout(tmp_path / "in", packet=True, excluded=2)          # two ablated controls were never shown
    out, cells = tmp_path / "o.json", tmp_path / "c.json"
    assert aw.main(washout_argv(fx, out, cells=cells)) == 0
    res, per_cell = load(out), load(cells)
    ctl = res["ai_use_classification"]["presented_controls"]
    assert len(fx["control_ids"]) == 34 and sum(ctl["by_group"].values()) == 34
    want = Counter(fx["expected_ai"][w][0] for w in fx["control_ids"])
    assert ctl["by_group"] == {g: want.get(g, 0) for g in ("yes", "no", "not recorded")}
    rows = {r["cell_id"]: r for r in per_cell["controls"]}
    assert len(rows) == 36 and sum(1 for r in rows.values() if r["excluded_reason"]) == 2
    for r in rows.values():
        got = (r["ai_use"], r["ai_ticked"], r["ai_tool"])
        assert got == ((None, None, None) if r["excluded_reason"] else fx["expected_ai"][r["cell_id"]])


def test_washout_cli_gap_is_not_computable_without_an_audit(tmp_path, small_b):
    fx = make_washout(tmp_path / "in")
    argv = washout_argv(fx, tmp_path / "o.json")
    i = argv.index("--audit")
    del argv[i:i + 2]
    assert aw.main(argv) == 0
    gap = load(tmp_path / "o.json")["G2"]["washout_gap"]
    assert gap["status"] == "not_computable" and "gap_days" not in gap and gap["ah_last_save"] == aw.AH_LAST_SAVE


def test_every_output_is_stamped_exploratory_in_the_provenance_and_at_the_top(tmp_path, small_b, capsys):
    fx = make_washout(tmp_path / "in")
    out, cells = tmp_path / "o.json", tmp_path / "c.json"
    assert aw.main(washout_argv(fx, out, cells=cells)) == 0
    res, per_cell = load(out), load(cells)
    for doc in (res, per_cell):
        prov = doc["provenance"]
        assert prov["evidence_status"] == "exploratory"
        assert "exploratory" in prov["evidence_status_note"] and "12.2" in prov["evidence_status_note"]
    assert res["evidence_status"] == "exploratory"
    assert json.loads(capsys.readouterr().out)["evidence_status"] == "exploratory"
    assert any("exploratory" in s for s in res["pinned_choices"])
    # a run on labels that carry the human marker is just as exploratory (the stamp does not depend on the rehearsal flag)
    fx_h = make_washout(tmp_path / "in_h", source="human")
    assert aw.main(washout_argv(fx_h, tmp_path / "oh.json", cells=tmp_path / "ch.json")) == 0
    res_h = load(tmp_path / "oh.json")
    assert res_h["rehearsal"] is False
    assert res_h["evidence_status"] == "exploratory" and res_h["provenance"]["evidence_status"] == "exploratory"
    assert load(tmp_path / "ch.json")["provenance"]["evidence_status"] == "exploratory"
    capsys.readouterr()                                           # drop the stdout of that run
    # and the second-annotation output
    sx = make_second(tmp_path / "in2")
    assert aw.main(second_argv(sx, tmp_path / "s.json", cells=tmp_path / "sc.json")) == 0
    for doc in (load(tmp_path / "s.json"), load(tmp_path / "sc.json")):
        assert doc["provenance"]["evidence_status"] == "exploratory"
    assert load(tmp_path / "s.json")["evidence_status"] == "exploratory"
    assert json.loads(capsys.readouterr().out)["evidence_status"] == "exploratory"
    assert any("exploratory" in s for s in aw.PINNED_WASHOUT)
    # the provenance builder itself carries the stamp
    prov = aw.build_provenance("washout", {"design": fx["design"]}, seed=SEED, B=SMALL_B, ties="midrank",
                               label_sources={}, csv_source_marker="synthetic", simulated=True)
    assert prov["evidence_status"] == "exploratory" and prov["evidence_status_note"] == aw.EVIDENCE_STATUS_NOTE


def test_washout_limitations_and_choices_describe_the_ai_recording_as_it_is(tmp_path, small_b):
    fx = make_washout(tmp_path / "in", packet=True)
    assert aw.main(washout_argv(fx, tmp_path / "o.json")) == 0
    res = load(tmp_path / "o.json")
    joined = " ".join(res["limitations"] + res["pinned_choices"] + res["unpinned_choices"]
                      + [res["provenance"]["ai_assistance"]])
    for stale in ("not recorded per cell", "self-reported per session", "per session and"):
        assert stale not in joined, stale
    assert any("per sitting" in s and "tick on each row" in s for s in res["limitations"])
    assert "not stratified" not in joined and "only counted" not in joined             # the washout is stratified now (D20)
    assert any("D20" in s and "descriptive, not a gate" in s for s in res["pinned_choices"])
    assert any("1/pi weights" in s and "domain estimate" in s for s in res["unpinned_choices"])
    assert any("no minimum size beyond the method" in s and "D20_MIN_CLUSTERS" in s for s in res["unpinned_choices"])
    assert any("AI-use groups" in s and "small" in s for s in res["limitations"])
    assert any("sitting reported AI use" in s and "tick" in s for s in res["pinned_choices"])
    assert "sitting" in res["provenance"]["ai_assistance"] and "tick" in res["provenance"]["ai_assistance"]


def fixture_washout_cells(fx):
    """The primary cells of a make_washout fixture, read back from the fixture's own files (not through the module)."""
    ah_rows = {r["cell_id"]: r for r in read_rows(fx["ah"])}
    wo_rows = {r["cell_id"]: r for r in read_rows(fx["washout"])}
    out = []
    for d in fx["design_rows"]:
        if d["cell_kind"] != "primary":
            continue
        a, w = ah_rows[d["source_cell_id"]], wo_rows[d["cell_id"]]
        out.append(wcell(d["cell_id"], a["cluster_id"], d["stratum"], 1.0 / float(d["inclusion_prob"]),
                         int(a["rater_L1"]), int(w["rater_L1"]), int(a["A"]), int(w["A"])))
    return out


def test_washout_cli_reports_g2_and_a_agreement_by_ai_use_group_tool_and_tick(tmp_path, small_b):
    fx = make_washout(tmp_path / "in", packet=True)
    out, cells_path = tmp_path / "o.json", tmp_path / "c.json"
    assert aw.main(washout_argv(fx, out, cells=cells_path)) == 0
    res = load(out)
    blk = res["ai_use_stratified"]
    assert blk["label"] == "descriptive; not a gate" and blk["decision_input"] is False and "D20" in blk["prereg"]
    cells = fixture_washout_cells(fx)
    exp = fx["expected_ai"]
    # the groups of the primary stratification worked out in the fixture: 34 / 19 / 19 cells
    parts = {g: [c for c in cells if exp[c.cell_id][0] == g] for g in ("yes", "no", "not recorded")}
    assert [len(parts[g]) for g in ("yes", "no", "not recorded")] == [34, 19, 19]
    ticked = [c for c in cells if exp[c.cell_id][1]]
    assert len(ticked) == 15
    cases = [(f"by_ai_use/{g}", sub, blk["by_ai_use"][g]) for g, sub in parts.items()]
    cases += [("tick/ticked", ticked, blk["by_ai_use_tick_only"]["ticked"]),
              ("tick/not ticked", [c for c in cells if not exp[c.cell_id][1]], blk["by_ai_use_tick_only"]["not ticked"])]
    yes_tools = {x["tool"]: x for x in blk["by_tool_among_yes_cells"]}
    assert set(yes_tools) == {"claude", aw.TOOL_NO_YES_REPORT}
    for tool, x in yes_tools.items():
        cases.append((f"yes tool {tool}", [c for c in parts["yes"] if exp[c.cell_id][2] == tool], x["block"]))
    ticked_tools = {x["tool"]: x for x in blk["by_tool_among_ticked_cells"]}
    assert set(ticked_tools) == {"claude", aw.TOOL_NO_YES_REPORT}
    for tool, x in ticked_tools.items():
        cases.append((f"ticked tool {tool}", [c for c in ticked if exp[c.cell_id][2] == tool], x["block"]))
    assert [yes_tools[t]["n_cells"] for t in ("claude", aw.TOOL_NO_YES_REPORT)] == [24, 10]
    assert [ticked_tools[t]["n_cells"] for t in ("claude", aw.TOOL_NO_YES_REPORT)] == [5, 10]
    for name, sub, block in cases:
        assert (block["n_cells"], block["n_clusters"]) == (len(sub), len({c.cluster_id for c in sub})), name
        q = block["G2_quantity"]
        assert q["status"] == "computed", name
        for key, weighted in (("qwk_weighted", True), ("qwk_unweighted", False)):
            assert q[key]["qwk"] == pytest.approx(exact_group_qwk(sub, weighted), abs=1e-12), (name, key)
            want = oracle_group_interval(sub, weighted, SMALL_B)
            assert q[key]["undefined_replicate_policy"] == "dropped", (name, key)
            assert q[key]["n_undefined_replicates"] == want["n_undefined"], (name, key)
            assert (q[key]["ci_lo"], q[key]["ci_hi"]) == pytest.approx((want["lo"], want["hi"]), abs=1e-9), (name, key)
        # the binary A tables read straight from the two sheets: per design stratum and weighted pool
        a = block["A_agreement_between_passes"]
        for s_ in aw.WASHOUT_STRATA:
            ss = [c for c in sub if c.stratum == s_]
            assert a["per_stratum"][s_]["n_cells"] == len(ss), (name, s_)
            if ss:
                assert a["per_stratum"][s_]["table"] == {
                    "n11": sum(c.ah_a == 1 and c.wo_a == 1 for c in ss), "n10": sum(c.ah_a == 1 and c.wo_a == 0 for c in ss),
                    "n01": sum(c.ah_a == 0 and c.wo_a == 1 for c in ss), "n00": sum(c.ah_a == 0 and c.wo_a == 0 for c in ss)}
        wt = a["reweighted_pooled"]["weighted_table"]
        assert wt["n11"] == pytest.approx(sum(c.w for c in sub if c.ah_a == 1 and c.wo_a == 1)), name
        assert wt["n00"] == pytest.approx(sum(c.w for c in sub if c.ah_a == 0 and c.wo_a == 0)), name
    # the groups of each family add up to the 72 primary cells; the counts block agrees with the results
    assert sum(blk["by_ai_use"][g]["n_cells"] for g in blk["by_ai_use"]) == 72
    assert sum(blk["by_ai_use_tick_only"][g]["n_cells"] for g in blk["by_ai_use_tick_only"]) == 72
    counts = res["ai_use_classification"]["primary_cells"]
    assert {g: blk["by_ai_use"][g]["n_cells"] for g in blk["by_ai_use"]} == counts["by_group"]
    assert {g: blk["by_ai_use_tick_only"][g]["n_cells"] for g in blk["by_ai_use_tick_only"]} == counts["tick_only"]["by_group"]
    assert {x["tool"]: x["n_cells"] for x in blk["by_tool_among_yes_cells"]} == {
        x["tool"]: x["n_cells"] for x in counts["tools_among_yes_cells"]}
    # aggregates only, and no wording the registration rules out
    ids = fx["primary_ids"] + fx["control_ids"] + fx["primary_sources"]
    assert ah.find_cell_level_leaks(out.read_text(), ids) == []
    assert aw.scan_forbidden_wording(aw._text_for_wording_scan(res)) == []


def test_washout_cli_group_estimates_are_the_pooled_g2_estimator_when_the_group_is_every_cell(tmp_path, small_b):
    fx = make_washout(tmp_path / "in")                    # no AI information: every cell is not recorded and not ticked
    out = tmp_path / "o.json"
    assert aw.main(washout_argv(fx, out)) == 0
    res = load(out)
    blk = res["ai_use_stratified"]
    g2 = res["G2"]["estimates"]["reweighted_pooled"]
    for whole in (blk["by_ai_use"]["not recorded"], blk["by_ai_use_tick_only"]["not ticked"]):
        w = whole["G2_quantity"]["qwk_weighted"]
        # the same estimator, the same clusters, the same draws: the pooled G2 interval, bit for bit (nothing undefined)
        assert w["n_undefined_replicates"] == 0 and g2["n_replicates_with_E_zero"] == 0
        assert (w["qwk"], w["ci_lo"], w["ci_hi"]) == (g2["qwk"], g2["ci_lo"], g2["ci_hi"])
        assert whole["weights"]["kish_n_eff"] == g2["kish_n_eff"]
        assert whole["A_agreement_between_passes"]["status"] == "computed"
        assert {k: v for k, v in whole["A_agreement_between_passes"].items() if k != "status"} == \
            res["A_agreement_between_passes"]
        assert (whole["n_cells"], whole["n_clusters"]) == (72, res["G2"]["cluster_structure"]["n_cq_clusters"])
    for empty in (blk["by_ai_use"]["yes"], blk["by_ai_use"]["no"], blk["by_ai_use_tick_only"]["ticked"]):
        assert empty["n_cells"] == 0 and empty["G2_quantity"]["status"] == "not_computable"
        assert empty["G2_quantity"]["reason"] == "no cell in this group"
    assert blk["by_tool_among_yes_cells"] == [] and blk["by_tool_among_ticked_cells"] == []


def sheet_header(path):
    return Path(path).read_text(encoding="utf-8").splitlines()[0].split(",")


def without_input_hashes(doc):
    doc = json.loads(json.dumps(doc))
    doc["provenance"].pop("inputs")
    return doc


LABEL_ASSIST_COLUMNS = SHEET_COLS[:12]          # label_assist's own 12 sheet columns (the fixtures add label_source)


def test_washout_cli_reads_the_14_column_packet_sheet_and_the_csv_dwell_ms_is_not_used(tmp_path, small_b):
    fx = make_washout(tmp_path / "in", packet=True)
    assert LABEL_ASSIST_COLUMNS[-1] == "note" and len(LABEL_ASSIST_COLUMNS) == 12
    rows = read_rows(fx["washout"])
    # the working CSV as label_assist --packet writes it: the 12 sheet columns, then ai_used, then dwell_ms (a running
    # total in ms); it has no label_source column, so the source is given on the command line
    packet_cols = LABEL_ASSIST_COLUMNS + ["ai_used", "dwell_ms"]
    write_csv(fx["washout"], rows, packet_cols)
    header = sheet_header(fx["washout"])
    assert header[-2:] == ["ai_used", "dwell_ms"] and len(header) == 14
    assert [r["dwell_ms"] for r in rows[:3]] == [str(int(round(fx["true_dwell"][r["cell_id"]] * 1000))) for r in rows[:3]]

    def run(name, cols):
        write_csv(fx["washout"], rows, cols)
        out = tmp_path / name
        assert aw.main(washout_argv(fx, out, "--label-source", "synthetic")) == 0
        return load(out)

    a = run("a.json", packet_cols)
    assert a["ai_use_classification"]["primary_cells"]["sheet_column_present"] is True
    assert a["dwell_check"]["primary_cells"]["basis_used"] == "dwell_ms"
    # the CSV's dwell_ms is a running total that the audit also holds: made nonsense, nothing changes
    for r in rows:
        r["dwell_ms"] = "1"
    b = run("b.json", packet_cols)
    # the first packet layout (13 columns, no dwell_ms) is read alike
    c = run("c.json", LABEL_ASSIST_COLUMNS + ["ai_used"])
    assert without_input_hashes(a) == without_input_hashes(b) == without_input_hashes(c)
    # the AH layout (12 columns: no ai_used either): the ticks then come from the audit alone, which holds the same ticks
    d = run("d.json", LABEL_ASSIST_COLUMNS)
    assert d["ai_use_classification"]["primary_cells"]["sheet_column_present"] is False
    assert d["dwell_check"] == a["dwell_check"] and d["G2"]["estimates"] == a["G2"]["estimates"]
    assert d["ai_use_classification"]["primary_cells"]["by_group"] == a["ai_use_classification"]["primary_cells"]["by_group"]


def test_second_cli_reads_the_14_column_packet_sheet_and_the_csv_dwell_ms_is_not_used(tmp_path, small_b):
    fx = make_second(tmp_path / "in", packet=True)
    rows = read_rows(fx["second"])
    packet_cols = LABEL_ASSIST_COLUMNS + ["ai_used", "dwell_ms"]

    def run(name, cols):
        write_csv(fx["second"], rows, cols)
        out = tmp_path / name
        assert aw.main(second_argv(fx, out, "--label-source", "synthetic")) == 0
        return load(out)

    a = run("a.json", packet_cols)
    header = sheet_header(fx["second"])
    assert header[-2:] == ["ai_used", "dwell_ms"] and len(header) == 14
    assert a["ai_use_classification"]["sheet_column_present"] is True
    assert a["dwell_check"]["primary_cells"]["basis_used"] == "dwell_ms"
    for r in rows:
        r["dwell_ms"] = "not a number"
    b = run("b.json", packet_cols)
    c = run("c.json", LABEL_ASSIST_COLUMNS + ["ai_used"])                      # the 13-column layout
    assert without_input_hashes(a) == without_input_hashes(b) == without_input_hashes(c)


def test_washout_cli_ai_use_inputs_cannot_change_g2_the_binary_a_agreement_or_g3w(tmp_path, small_b):
    fx = make_washout(tmp_path / "in", packet=True)
    with_ai, without_ai = tmp_path / "a.json", tmp_path / "b.json"
    assert aw.main(washout_argv(fx, with_ai)) == 0
    argv = washout_argv(fx, without_ai)
    for flag in ("--audit", "--session-log"):
        i = argv.index(flag)
        del argv[i:i + 2]
    assert aw.main(argv) == 0
    ra, rb = load(with_ai), load(without_ai)
    assert ra["ai_use_stratified"] != rb["ai_use_stratified"]                    # the groups differ ...
    assert ra["ai_use_stratified"]["by_ai_use"]["no"]["n_cells"] == 19 and rb["ai_use_stratified"]["by_ai_use"]["no"]["n_cells"] == 0
    for key in ("A_agreement_between_passes", "G3_W"):                            # ... and nothing the decisions read does
        assert ra[key] == rb[key], key
    ga, gb = dict(ra["G2"]), dict(rb["G2"])
    ga.pop("washout_gap"), gb.pop("washout_gap")                                  # (the gap is read from the audit)
    assert ga == gb


# ---- second command -------------------------------------------------------
def test_second_cli_end_to_end(tmp_path, small_b, capsys):
    fx = make_second(tmp_path / "in", opaque=True)
    out, cells = tmp_path / "out.json", tmp_path / "cells.json"
    assert aw.main(second_argv(fx, out, cells=cells)) == 0
    err = capsys.readouterr().err
    assert "not what the registered draw" not in err and "washout-locked" not in err
    res, per_cell = load(out), load(cells)
    assert res["label_sources"] == {"ah_pass": aw.LABEL_SOURCE_AH, "second_annotation": aw.LABEL_SOURCE_SECOND}
    assert res["sample_check"]["matches_registered_sha256"] is False and res["rehearsal"] is True
    assert res["sample_check"]["reproduced_by_registered_draw_on_cells"] is True
    assert res["sample_check"]["cells_per_category"] == {c: 8 for c in CATS}
    so = res["second_annotation"]
    assert so["all_cells"]["n_cells"] == 48
    assert sum(so["by_ai_use"][g]["n_cells"] for g in ("yes", "no", "not recorded")) == 48
    # k % 4 == 0 carries a tick (12 cells, yes).  Of the other 36, sessA (declared yes) puts 12 more into the yes
    # group, sessB (declared no) 12 into no, and sessC (declared nothing) 12 into not recorded.  The ticks sit 4 in
    # each session, so 4 of them sit in the session that reported no
    ai = res["ai_use_classification"]
    assert ai["sheet_column_present"] is True and ai["n_sheet_audit_conflicts"] == 0
    assert ai["by_source"] == {"tick": 12, "sitting_report": 0, "session_report": 24, "none": 12}
    assert ai["by_group"] == {"yes": 24, "no": 12, "not recorded": 12}
    assert ai["tick_only"]["by_group"] == {"ticked": 12, "not ticked": 36}
    assert ai["n_ticks_in_sittings_reporting_no"] == 4
    assert (ai["join"]["by_session_id"], ai["join"]["by_sitting_id"], ai["join"]["no_report"]) == (32, 0, 16)
    assert [so["by_ai_use"][g]["n_cells"] for g in ("yes", "no", "not recorded")] == [24, 12, 12]
    assert [so["by_ai_use_tick_only"][g]["n_cells"] for g in ("ticked", "not ticked")] == [12, 36]
    by_tool = {x["tool"]: x["n_cells"] for x in ai["tools_among_yes_cells"]}
    assert by_tool == {"a chat assistant": 16, aw.TOOL_NO_YES_REPORT: 8}
    assert {x["tool"]: x["n_cells"] for x in so["by_tool_among_yes_cells"]} == by_tool
    sr = ai["session_reports"]
    assert sr["by_declared_use"] == {"yes": 1, "no": 1, "not recorded": 0} and sr["n_superseded"] == 1
    assert sr["n_reports"] == 2 and sr["approx_cells_declared_in_yes_reports"] == 9
    # a tool name is data: normalized, in the aggregates and in the per-cell file under its tool keys
    assert {r["ai_tool"] for r in per_cell["cells"] if r["ai_use"] == "yes"} == {"a chat assistant", aw.TOOL_NO_YES_REPORT}
    assert [r["ai_ticked"] for r in per_cell["cells"]].count(True) == 12
    block = so["all_cells"]
    assert set(block["judge_vs_second_annotator"]) == {"descriptive_only", "all_cells", "restricted_to_J_in_1_2_3"}
    assert block["judge_vs_second_annotator"]["restricted_to_J_in_1_2_3"]["n_cells"] < 48
    assert block["pi_hat"]["AH"]["cluster_level_clopper_pearson"]["zero_event_note"]["n_clusters"] <= 30
    assert res["dwell_check"]["primary_cells"]["n_cells"] == 48 and res["dwell_check"]["sessions"]["n_sessions"] == 3
    # provenance in both files
    assert per_cell["provenance"] == res["provenance"]
    assert set(res["provenance"]["inputs"]) == {"cells", "ah_labels", "second_labels", "sample_list", "id_map",
                                                "audit", "session_log"}
    assert res["provenance"]["assertions"]["washout_locked_asserted"] is True
    # aggregates only (the second annotator's opaque ids, the AH ids and the CQ ids stay out)
    text = out.read_text()
    ids = list(fx["sample_ids"]) + [f"s-{k:03d}" for k in range(48)] + [f"cq{i:02d}" for i in range(1, 31)] + ["cqX", "cqZ"]
    assert ah.find_cell_level_leaks(text, ids) == [] and ah.find_cell_level_leaks(cells.read_text(), ids)
    assert aw.scan_forbidden_wording(aw._text_for_wording_scan(res)) == []
    assert "not-a-label" not in text                                              # AH control values never read
    assert [r["ai_use"] for r in per_cell["cells"]].count("yes") == 24


def test_second_cli_uses_the_same_ids_when_no_id_map_is_given(tmp_path, small_b):
    fx = make_second(tmp_path / "in", opaque=False)
    out = tmp_path / "out.json"
    assert aw.main(second_argv(fx, out)) == 0
    assert "id_map" not in load(out)["provenance"]["inputs"]
    assert load(out)["second_annotation"]["all_cells"]["n_cells"] == 48


def test_second_cli_without_ai_use_information_reports_everything_as_not_recorded(tmp_path, small_b):
    fx = make_second(tmp_path / "in", ai_flags=False, session_report=False)
    out = tmp_path / "out.json"
    assert aw.main(second_argv(fx, out)) == 0
    res = load(out)
    assert res["ai_use_classification"]["by_group"] == {"yes": 0, "no": 0, "not recorded": 48}
    assert res["ai_use_classification"]["session_reports"]["n_reports"] == 0
    assert res["ai_use_classification"]["tick_only"]["by_group"] == {"ticked": 0, "not ticked": 48}
    assert res["ai_use_classification"]["tools_among_yes_cells"] == []
    assert res["second_annotation"]["by_ai_use"]["yes"] == {"n_cells": 0, "n_clusters": 0}
    assert res["second_annotation"]["by_tool_among_yes_cells"] == []


def test_second_cli_refuses_an_unregistered_sample_list_unless_told(tmp_path, small_b):
    fx = make_second(tmp_path / "in")
    with pytest.raises(SystemExit, match="not the registered"):
        aw.main(second_argv(fx, tmp_path / "o.json", unregistered=False))
    assert not (tmp_path / "o.json").exists()
    assert aw.main(second_argv(fx, tmp_path / "o2.json")) == 0                       # with the rehearsal flag


def test_second_cli_checks_the_shape_of_a_list_that_carries_the_registered_hash(tmp_path, small_b, monkeypatch):
    fx = make_second(tmp_path / "in")
    ids = fx["sample_ids"]
    spare = next(c["cell_id"] for c in fx["cell_rows"] if c["cell_id"] not in ids and c["category"] == "cat_a"
                 and c.get("cell_kind") is None)
    skew = tmp_path / "in" / "skew.txt"                                  # 9 cells in cat_a, 7 in another category
    other = next(i for i in ids if not i.startswith("cat_a"))
    skew.write_bytes(aw.sample_list_bytes([i for i in ids if i != other] + [spare]))
    monkeypatch.setattr(aw, "SECOND_SAMPLE_SHA256", hashlib.sha256(skew.read_bytes()).hexdigest())
    with pytest.raises(SystemExit, match="per category"):
        aw.main(second_argv({**fx, "sample": skew}, tmp_path / "o.json", unregistered=False))
    short = tmp_path / "in" / "short.txt"
    short.write_bytes(aw.sample_list_bytes(ids[:47]))
    monkeypatch.setattr(aw, "SECOND_SAMPLE_SHA256", hashlib.sha256(short.read_bytes()).hexdigest())
    with pytest.raises(SystemExit, match="47 ids, registered 48"):
        aw.main(second_argv({**fx, "sample": short}, tmp_path / "o2.json", unregistered=False))
    # a list that really has the registered hash and shape passes both checks
    monkeypatch.setattr(aw, "SECOND_SAMPLE_SHA256", hashlib.sha256(fx["sample"].read_bytes()).hexdigest())
    assert aw.main(second_argv(fx, tmp_path / "o3.json", unregistered=False)) == 0
    res = load(tmp_path / "o3.json")
    assert res["sample_check"]["matches_registered_sha256"] is True and res["rehearsal"] is True   # simulated labels


def test_second_cli_warns_when_the_list_is_not_the_registered_draw_and_when_the_washout_lock_is_unasserted(
        tmp_path, small_b, capsys):
    fx = make_second(tmp_path / "in")
    # a different 48-cell list (still 8 per category): allowed with the flag, flagged as not the registered draw
    cells = fx["cell_rows"]
    other = []
    for cat in CATS:
        pool = sorted(c["cell_id"] for c in cells if c["category"] == cat and c.get("cell_kind") is None)
        other += pool[:8]
    other_path = tmp_path / "in" / "other.txt"
    other_path.write_bytes(aw.sample_list_bytes(other))
    by_ah = {r["cell_id"]: r for r in read_rows(fx["ah"])}
    write_csv(fx["second"], [sheet_row(o, "cqZ", "cat_a", by_ah[o]["A"], by_ah[o]["rater_L1"], "synthetic") for o in other],
              SHEET_COLS)
    # the audit refers to the old ids; the run still works (dwell is then partly unknown)
    argv = second_argv({**fx, "sample": other_path}, tmp_path / "o.json")
    argv.remove("--washout-locked")
    aw.main(argv)
    err = capsys.readouterr().err
    assert "not what the registered draw gives" in err and "--washout-locked was not asserted" in err
    res = load(tmp_path / "o.json")
    assert res["sample_check"]["reproduced_by_registered_draw_on_cells"] is False
    assert res["provenance"]["assertions"]["washout_locked_asserted"] is False


def test_second_cli_warns_when_the_session_reports_cannot_be_linked_without_an_audit(tmp_path, small_b, capsys):
    fx = make_second(tmp_path / "in")
    argv = second_argv(fx, tmp_path / "o.json")
    i = argv.index("--audit")
    del argv[i:i + 2]
    assert aw.main(argv) == 0
    assert "cannot be linked" in capsys.readouterr().err
    res = load(tmp_path / "o.json")
    # no audit: no session id per cell, so only the sheet's own ticks (12 cells) classify anything
    assert res["ai_use_classification"]["by_group"] == {"yes": 12, "no": 0, "not recorded": 36}
    assert res["ai_use_classification"]["by_source"] == {"tick": 12, "sitting_report": 0, "session_report": 0, "none": 36}
    assert res["dwell_check"]["sessions"]["n_session_starts_in_log"] == 3          # the log still gives sessions
    # neither audit nor log, but the sheet column: no warning, the ticks still count
    argv = second_argv(fx, tmp_path / "o2.json")
    for flag in ("--audit", "--session-log"):
        i = argv.index(flag)
        del argv[i:i + 2]
    assert aw.main(argv) == 0
    assert "cannot be determined" not in capsys.readouterr().err
    assert load(tmp_path / "o2.json")["ai_use_classification"]["by_group"] == {"yes": 12, "no": 0, "not recorded": 36}
    assert load(tmp_path / "o2.json")["dwell_check"]["status"] == "not_computable"
    # a sheet without the column, no audit, no log: nothing to go on
    bare = make_second(tmp_path / "in2", sheet_ai_column=False)
    argv = second_argv(bare, tmp_path / "o3.json")
    for flag in ("--audit", "--session-log"):
        i = argv.index(flag)
        del argv[i:i + 2]
    assert aw.main(argv) == 0
    assert "AI use cannot be determined" in capsys.readouterr().err
    r3 = load(tmp_path / "o3.json")["ai_use_classification"]
    assert r3["by_group"] == {"yes": 0, "no": 0, "not recorded": 48} and r3["sheet_column_present"] is False


def test_second_cli_in_packet_mode_stratifies_by_the_sitting_report_the_tick_and_the_tool(tmp_path, small_b, capsys):
    fx = make_second(tmp_path / "in", opaque=True, packet=True)
    out, cells = tmp_path / "o.json", tmp_path / "c.json"
    assert aw.main(second_argv(fx, out, cells=cells)) == 0
    res, per_cell = load(out), load(cells)
    ai, so = res["ai_use_classification"], res["second_annotation"]
    # worked out by hand: cell k is in sitting k % 6 (A1 yes/ChatGPT, A2 no, B1 yes/Claude.ai, B2 yes with no tool,
    # C1 not recorded, C2 filed no report) and k % 4 == 0 is ticked: the 12 ticks sit 4 each in A1, B1 and C1
    assert ai["by_group"] == {"yes": 28, "no": 8, "not recorded": 12}
    assert ai["tick_only"]["by_group"] == {"ticked": 12, "not ticked": 36}
    assert ai["by_source"] == {"tick": 12, "sitting_report": 24, "session_report": 0, "none": 12}
    assert (ai["join"]["by_sitting_id"], ai["join"]["by_session_id"], ai["join"]["no_report"]) == (40, 0, 8)
    assert ai["n_ticks_in_sittings_reporting_no"] == 0 and ai["n_sheet_audit_conflicts"] == 0
    want_tools = {"chatgpt": 8, "claude.ai": 8, aw.TOOL_NOT_GIVEN: 8, aw.TOOL_NO_YES_REPORT: 4}
    assert {x["tool"]: x["n_cells"] for x in ai["tools_among_yes_cells"]} == want_tools
    assert [so["by_ai_use"][g]["n_cells"] for g in ("yes", "no", "not recorded")] == [28, 8, 12]
    assert [so["by_ai_use_tick_only"][g]["n_cells"] for g in ("ticked", "not ticked")] == [12, 36]
    assert {x["tool"]: x["n_cells"] for x in so["by_tool_among_yes_cells"]} == want_tools
    assert [x["tool"] for x in so["by_tool_among_yes_cells"]] == sorted(want_tools)
    for x in so["by_tool_among_yes_cells"]:
        assert x["block"]["n_cells"] == x["n_cells"]
    sr = ai["session_reports"]
    assert (sr["n_reports"], sr["n_reports_with_sitting_id"]) == (5, 5)
    assert sr["by_declared_use"] == {"yes": 3, "no": 1, "not recorded": 1}
    assert {x["tool"] for x in sr["tools_in_yes_reports"]} == {"chatgpt", "claude.ai", aw.TOOL_NOT_GIVEN}
    assert sr["approx_cells_declared_in_yes_reports"] == 12 and sr["n_yes_reports_without_approx_cells"] == 0
    # the per-cell file agrees with the classification worked out in the fixture, cell by cell
    assert {r["cell_id"] for r in per_cell["cells"]} == set(fx["sample_ids"])
    for row in per_cell["cells"]:
        assert (row["ai_use"], row["ai_ticked"], row["ai_tool"]) == fx["expected_ai"][row["cell_id"]]
    # dwell: the client's dwell_ms, not the (skewed) elapsed_s; sessions are the SESSION start lines, sittings counted
    d = res["dwell_check"]
    vals = list(fx["true_dwell"].values())
    n_fast = sum(v < 20 for v in vals)
    assert 0 < n_fast < 48
    assert d["primary_cells"]["basis_used"] == "dwell_ms" and d["primary_cells"]["n_under_20s"] == n_fast
    assert d["primary_cells"]["median_s"] == pytest.approx(float(np.median(vals)))
    assert d["sessions"]["n_sessions"] == 6 and d["sessions"]["n_sittings_in_log"] == 6
    assert d["sessions"]["n_sittings_with_saves"] == 6
    assert aw.scan_forbidden_wording(aw._text_for_wording_scan(res)) == []
    assert json.loads(capsys.readouterr().out)["second_annotation"]["ai_use"] == ai["by_group"]


def test_second_cli_tool_names_are_data_and_cannot_trip_the_wording_guard(tmp_path, small_b):
    fx = make_second(tmp_path / "in", packet=True)
    fx["log"].write_text(fx["log"].read_text().replace("Claude.ai", "reference manager (verified)"))
    out, cells = tmp_path / "o.json", tmp_path / "c.json"
    assert aw.main(second_argv(fx, out, cells=cells)) == 0
    res = load(out)
    tools = {x["tool"] for x in res["ai_use_classification"]["tools_among_yes_cells"]}
    assert "reference manager (verified)" in tools
    assert "reference manager (verified)" in {r["ai_tool"] for r in load(cells)["cells"]}
    assert aw.scan_forbidden_wording(aw._text_for_wording_scan(res)) == []
    # the guard still covers every other string of the output
    assert aw.scan_forbidden_wording("labels from a reference standard") == ["reference"]


def test_second_cli_limitations_and_choices_describe_the_ai_recording_as_it_is(tmp_path, small_b):
    fx = make_second(tmp_path / "in", packet=True)
    assert aw.main(second_argv(fx, tmp_path / "o.json")) == 0
    res = load(tmp_path / "o.json")
    joined = " ".join(res["limitations"] + res["pinned_choices"] + res["unpinned_choices"]
                      + [res["provenance"]["ai_assistance"]])
    for stale in ("not recorded per cell", "self-reported per session", "per session and"):
        assert stale not in joined, stale
    assert any("per sitting" in s and "tick on each row" in s for s in res["limitations"])
    assert any("yes group" in s and "sittings that reported AI use" in s for s in res["limitations"])
    assert any("by AI use" in s and "tick-only" in s and "tools" in s for s in res["pinned_choices"])


def test_second_cli_join_errors(tmp_path, small_b):
    fx = make_second(tmp_path / "in")
    rows = read_rows(fx["second"])
    rows[0]["rater_L1"] = ""
    write_csv(fx["second"], rows, SHEET_COLS)
    with pytest.raises(SystemExit, match="second-annotator labels lack A or rater_L1"):
        aw.main(second_argv(fx, tmp_path / "o.json"))
    fx = make_second(tmp_path / "in2")
    rows = read_rows(fx["second"])
    rows.append(sheet_row("zzz", "cqZ", "cat_a", 1, 1, "synthetic"))
    write_csv(fx["second"], rows, SHEET_COLS)
    with pytest.raises(SystemExit, match="outside the sample"):
        aw.main(second_argv(fx, tmp_path / "o2.json"))
    fx = make_second(tmp_path / "in3", opaque=True)
    rows = read_rows(fx["idmap"])[:-1]
    write_csv(fx["idmap"], rows, ["cell_id", "source_cell_id"])
    with pytest.raises(SystemExit, match="id map lacks"):
        aw.main(second_argv(fx, tmp_path / "o3.json"))


# ---- output-path guards ---------------------------------------------------
def test_guard_an_output_may_not_be_an_input(tmp_path, small_b):
    fx = make_washout(tmp_path / "in")
    before = fx["design"].read_bytes()
    with pytest.raises(SystemExit, match="same file"):
        aw.main(washout_argv(fx, fx["design"], "--overwrite"))
    with pytest.raises(SystemExit, match="same file"):
        aw.main(washout_argv(fx, tmp_path / "o.json", cells=fx["ah"]))
    assert fx["design"].read_bytes() == before
    # a symlink to an input, and a hard link to an input
    link = tmp_path / "link.json"
    link.symlink_to(fx["washout"])
    with pytest.raises(SystemExit, match="same file"):
        aw.main(washout_argv(fx, link, "--overwrite"))
    hard = tmp_path / "hard.json"
    os.link(fx["audit"], hard)
    with pytest.raises(SystemExit, match="same file"):
        aw.main(washout_argv(fx, hard, "--overwrite"))
    # the same for the second command
    sx = make_second(tmp_path / "in2")
    with pytest.raises(SystemExit, match="same file"):
        aw.main(second_argv(sx, sx["sample"], "--overwrite"))


def test_guard_out_and_out_cells_must_differ_and_existing_files_are_not_overwritten(tmp_path, small_b):
    fx = make_washout(tmp_path / "in")
    same = tmp_path / "same.json"
    with pytest.raises(SystemExit, match="must differ"):
        aw.main(washout_argv(fx, same, cells=same))
    out = tmp_path / "o.json"
    assert aw.main(washout_argv(fx, out)) == 0
    first = out.read_bytes()
    with pytest.raises(SystemExit, match="exists"):
        aw.main(washout_argv(fx, out))
    assert out.read_bytes() == first
    cells = tmp_path / "c.json"
    cells.write_text("sealed already")
    with pytest.raises(SystemExit, match="exists"):
        aw.main(washout_argv(fx, tmp_path / "o2.json", cells=cells))
    assert cells.read_text() == "sealed already" and not (tmp_path / "o2.json").exists()
    assert aw.main(washout_argv(fx, out, "--overwrite")) == 0


def test_guard_the_output_directory_must_exist_and_is_not_created(tmp_path, small_b):
    fx = make_washout(tmp_path / "in")
    with pytest.raises(SystemExit, match="directory does not exist"):
        aw.main(washout_argv(fx, tmp_path / "nope" / "o.json"))
    with pytest.raises(SystemExit, match="directory does not exist"):
        aw.main(washout_argv(fx, tmp_path / "o.json", cells=tmp_path / "nope2" / "c.json"))
    assert not (tmp_path / "nope").exists() and not (tmp_path / "nope2").exists()
    assert not (tmp_path / "o.json").exists()


def test_cli_prints_an_aggregates_only_summary_to_stdout(tmp_path, small_b, capsys):
    fx = make_washout(tmp_path / "in")
    assert aw.main(washout_argv(fx, tmp_path / "o.json")) == 0
    out = capsys.readouterr().out
    summary = json.loads(out)
    assert summary["G2"]["status"] in ("pass", "fail") and summary["G2"]["threshold"] == 0.70
    assert summary["G3_W"]["ablated"] == {"status": "pass", "A0_over_valid": "24/24"}
    assert summary["evidence_status"] == "exploratory"
    assert summary["washout_gap_days"] == pytest.approx(30 + 32525 / 86400, abs=1e-9)
    assert summary["ai_use_primary_cells"] == {"yes": 0, "no": 0, "not recorded": 72}
    ids = [r["cell_id"] for r in fx["design_rows"]] + [r["source_cell_id"] for r in fx["design_rows"]]
    assert ah.find_cell_level_leaks(out, ids) == []
    sx = make_second(tmp_path / "in2")
    assert aw.main(second_argv(sx, tmp_path / "o2.json")) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["second_annotation"]["n_cells"] == 48 and summary["second_annotation"]["ai_use"]["yes"] == 24


def test_guard_the_sealed_per_cell_file_never_goes_into_a_rater_readable_directory(tmp_path, small_b):
    fx = make_washout(tmp_path / "in")
    for name in ("annotation_pending", "packet", "views"):
        d = tmp_path / name
        d.mkdir()
        with pytest.raises(SystemExit, match="rater can read"):
            aw.main(washout_argv(fx, tmp_path / "o.json", cells=d / "cells.json"))
        assert not (d / "cells.json").exists() and not (tmp_path / "o.json").exists()
    ok = tmp_path / "SEALED_until_washout"
    ok.mkdir()
    assert aw.main(washout_argv(fx, tmp_path / "o.json", cells=ok / "cells.json")) == 0


def test_guard_nothing_is_written_when_the_output_would_carry_forbidden_wording(tmp_path, small_b, monkeypatch):
    fx = make_washout(tmp_path / "in")
    monkeypatch.setattr(aw, "LABEL_SOURCE_WASHOUT", "an independent human pass")
    with pytest.raises(SystemExit, match="forbidden wording"):
        aw.main(washout_argv(fx, tmp_path / "o.json", cells=tmp_path / "c.json"))
    assert not (tmp_path / "o.json").exists() and not (tmp_path / "c.json").exists()
    monkeypatch.setattr(aw, "LABEL_SOURCE_WASHOUT", "same-rater washout pass")
    monkeypatch.setattr(aw, "LABEL_SOURCE_AH", "verified reference labels")
    with pytest.raises(SystemExit, match="forbidden wording"):
        aw.main(washout_argv(fx, tmp_path / "o.json"))
    sx = make_second(tmp_path / "in2")
    monkeypatch.setattr(aw, "LABEL_SOURCE_AH", aw.LABEL_SOURCE_AH)
    monkeypatch.setattr(aw, "LABEL_SOURCE_SECOND", "an independent human annotator")
    with pytest.raises(SystemExit, match="forbidden wording"):
        aw.main(second_argv(sx, tmp_path / "o2.json"))
    assert not (tmp_path / "o2.json").exists()


def test_guard_an_identifier_in_the_aggregates_blocks_the_write(tmp_path, small_b, monkeypatch):
    fx = make_washout(tmp_path / "in")
    real = aw.g2_analysis

    def leaky(*args, **kwargs):
        res = real(*args, **kwargs)
        res["note"] = "see cell w-0001"
        return res

    monkeypatch.setattr(aw, "g2_analysis", leaky)
    with pytest.raises(SystemExit, match="identifiers"):
        aw.main(washout_argv(fx, tmp_path / "o.json"))
    assert not (tmp_path / "o.json").exists()


def test_cli_at_the_registered_resample_count_and_seed_is_stamped_registered(tmp_path):
    fx = make_washout(tmp_path / "in")
    out = tmp_path / "o.json"
    aw.main(washout_argv(fx, out))                       # no monkeypatch: B = 10,000
    res = load(out)
    assert res["G2"]["resamples"] == 10_000 and res["provenance"]["bootstrap"]["resamples"] == 10_000
    assert res["provenance"]["bootstrap"]["registered_seed_used"] is True
    assert res["G2"]["estimates"]["reweighted_pooled"]["ci_status"] == "computed"
