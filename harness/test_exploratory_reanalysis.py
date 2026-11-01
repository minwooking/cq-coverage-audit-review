"""Tests for real_run/results_human_pass/exploratory_reanalysis.py.

ALL DATA HERE IS SYNTHETIC and exists only to exercise the code. None of it is a study
result, and none of it may be quoted as one. Bootstrap tests use a small B so they run in
seconds; the registered B = 10,000 is exercised only by the real run.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import itertools
import json
import math
import random
import re
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze_holdout as ah  # noqa: E402

SCRIPT = HERE / "real_run" / "results_human_pass" / "exploratory_reanalysis.py"
_spec = importlib.util.spec_from_file_location("exploratory_reanalysis", SCRIPT)
er = importlib.util.module_from_spec(_spec)
sys.modules["exploratory_reanalysis"] = er
_spec.loader.exec_module(er)

B = 200
SEED = 20260913
FORBIDDEN = re.compile(r"sensitivity|specificity|accuracy|ground[- ]truth", re.I)


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------
def row(cq, variant, J, ah_, draft=None, aux=None, cluster=None, edited=False):
    return {"cell_id": f"{variant}:{cq}", "cq_id": cq, "cluster_id": cluster or cq, "variant": variant,
            "J": J, "span_edited": edited,
            "A": {"AH": ah_, "draft": ah_ if draft is None else draft, "aux": ah_ if aux is None else aux}}


def cells_of(rows, src="AH"):
    return er._cells_for(rows, src)


def exact_2x2_rows():
    """12 cells, one per cluster: J>=2&A=1: 6, J>=2&A=0: 2, J<=1&A=1: 1, J<=1&A=0: 3."""
    spec = [(3, 1)] * 6 + [(2, 0)] * 2 + [(1, 1)] * 1 + [(0, 0), (1, 0), (0, 0)]
    return [row(f"Q{i:02d}", "C", j, a) for i, (j, a) in enumerate(spec)]


def contrast_rows():
    """Six CQs with a variant-A and a variant-B cell (plus a variant-C cell that must not matter)."""
    spec = [  # (J_A, A_A, J_B, A_B)
        (3, 1, 3, 1), (2, 0, 3, 1), (3, 1, 2, 1), (1, 1, 3, 1), (2, 1, 2, 0), (3, 0, 3, 1)]
    out = []
    for i, (ja, aa, jb, ab) in enumerate(spec):
        q = f"Q{i:02d}"
        out += [row(q, "A", ja, aa), row(q, "B", jb, ab), row(q, "C", 3, 0)]
    return out


def write_fixture(tmp_path, rows, n_controls=2):
    """Files shaped like the real inputs, with SECRET text in every field that must not leak."""
    per_cell = {"WARNING": "w", "schema": "s", "id_lists": {}, "primary_cells": [
        {"cell_id": r["cell_id"], "cq_id": r["cq_id"], "cluster_id": r["cluster_id"], "category": "x",
         "variant": r["variant"], "J": r["J"], "A": r["A"]["AH"],
         "L1_star": er.l1_star(r["J"], r["A"]["AH"]), "rater_L1": 2, "draft_A": r["A"]["draft"],
         "A_changed": r["A"]["draft"] != r["A"]["AH"], "span_edited": r["span_edited"]} for r in rows]}
    p_cell = tmp_path / "per_cell.json"
    p_cell.write_text(json.dumps(per_cell), encoding="utf-8")
    lines = []
    for r in rows:
        lines.append(json.dumps({"cell_id": r["cell_id"], "cq_id": r["cq_id"], "cluster_id": r["cluster_id"],
                                 "variant": r["variant"], "cell_kind": "primary", "J": r["J"], "A": 0,
                                 "judge_response": {"score": r["J"], "evidence": "SECRET_EVIDENCE"}}))
    for k in range(n_controls):
        lines.append(json.dumps({"cell_id": f"ablated_control:D:CTRL{k}", "cq_id": f"CTRL{k}",
                                 "cluster_id": f"CTRL{k}", "variant": "D", "cell_kind": "ablated_control",
                                 "J": 2, "A": 1}))
    p_run = tmp_path / "cells.jsonl"
    p_run.write_text("\n".join(lines) + "\n", encoding="utf-8")
    p_draft = tmp_path / "draft.csv"
    with open(p_draft, "w", newline="", encoding="utf-8") as h:
        w = csv.writer(h)
        w.writerow(["cell_id", "A_draft", "rater_L1_draft", "span_draft", "note_draft", "model", "generated_at"])
        for r in rows:
            w.writerow([r["cell_id"], r["A"]["draft"], 2, "SECRET_SPAN", "SECRET_NOTE", "draft-model", "t"])
        for k in range(n_controls):
            w.writerow([f"ablated_control:D:CTRL{k}", 1, 2, "SECRET_SPAN", "SECRET_NOTE", "draft-model", "t"])
    p_aux = tmp_path / "aux.jsonl"
    with open(p_aux, "w", encoding="utf-8") as h:
        for r in rows:
            h.write(json.dumps({"cell_id": r["cell_id"], "cq_id": r["cq_id"], "J": r["J"],
                                "A_auxiliary": r["A"]["aux"], "rationale": "SECRET_RATIONALE",
                                "model": "aux-model"}) + "\n")
        for k in range(n_controls):
            h.write(json.dumps({"cell_id": f"ablated_control:D:CTRL{k}", "cq_id": f"CTRL{k}", "J": 2,
                                "A_auxiliary": 1, "rationale": "SECRET_RATIONALE", "model": "aux-model"}) + "\n")
    return p_cell, p_run, p_draft, p_aux


def random_rows(n_cq=10, seed=4):
    rng = random.Random(seed)
    rows = []
    for i in range(n_cq):
        q = f"Q{i:02d}"
        for v in ("A", "B", "C") if i < 7 else ("B", "C"):
            j = rng.choice([0, 1, 2, 3, 3])
            a = rng.choice([0, 1, 1])
            d = a if rng.random() > 0.25 else 1 - a
            x = a if rng.random() > 0.25 else 1 - a
            rows.append(row(q, v, j, a, draft=d, aux=x, edited=rng.random() < 0.3))
    return rows


# --------------------------------------------------------------------------
# 1. the 2x2 table and the neutral rate names
# --------------------------------------------------------------------------
def test_2x2_counts_and_hand_computed_kappa():
    cells = cells_of(exact_2x2_rows())
    t = er.table_of(cells)
    assert tuple(t) == (6, 2, 1, 3)
    assert er.kappa_of(*t) == pytest.approx(8 / 17)  # po=.75, pe=76/144
    blk = er.table_block(cells, B, SEED)
    assert blk["counts"] == {"Jge2_A1": 6, "Jge2_A0": 2, "Jle1_A1": 1, "Jle1_A0": 3, "n": 12}
    m = blk["metrics"]
    expected = {
        "raw_agreement": 9 / 12, "agreement_among_A1_cells": 6 / 7, "agreement_among_A0_cells": 3 / 5,
        "agreement_among_Jge2_cells": 6 / 8, "agreement_among_Jle1_cells": 3 / 4,
        "positive_agreement_both_credit": 12 / 15, "negative_agreement_both_no_credit": 6 / 9,
        "judge_credit_rate_Jge2": 8 / 12, "A1_rate": 7 / 12, "net_marginal_difference_Jge2_minus_A1": 1 / 12,
    }
    for name, value in expected.items():
        assert m[name]["estimate"] == pytest.approx(value), name
    assert m["cohen_kappa"]["estimate"] == pytest.approx(8 / 17)
    for v in m.values():
        assert v["ci_lo"] is None or v["ci_lo"] <= v["estimate"] <= v["ci_hi"] + 1e-12


def test_kappa_undefined_when_chance_agreement_is_one():
    assert math.isnan(er.kappa_of(5, 0, 0, 0))
    assert er.kappa_of(3, 0, 0, 3) == pytest.approx(1.0)
    assert er.kappa_of(2, 2, 2, 2) == pytest.approx(0.0)


def test_rate_names_are_neutral():
    blk = er.table_block(cells_of(exact_2x2_rows()), B, SEED)
    credit = er.credit_block(cells_of(exact_2x2_rows()), B, SEED)
    text = json.dumps([blk, credit])
    assert not FORBIDDEN.search(text)
    assert "agreement_among_A1_cells" in text and "over_credit_among_judge_credited_cells" in text


def test_l1_star_is_the_analyzers_demote_rule():
    for j, a in itertools.product(range(4), (0, 1)):
        assert er.l1_star(j, a) == ah.demote(j, a)


# --------------------------------------------------------------------------
# 2. over-credit and under-credit
# --------------------------------------------------------------------------
def test_credit_rates_hand_computed():
    rows = [row(f"Q{i:02d}", "C", j, a) for i, (j, a) in enumerate(
        [(3, 1), (3, 1), (2, 0), (3, 0), (2, 1), (0, 1), (0, 1), (0, 0), (0, 0), (1, 1), (1, 0), (3, 1)])]
    cells = cells_of(rows)
    blk = er.credit_block(cells, B, SEED)
    r = blk["rates"]
    # J>=2: 6 cells (3,1)(3,1)(2,0)(3,0)(2,1)(3,1); A=0 among them: 2
    assert (r["over_credit_among_judge_credited_cells"]["numerator"],
            r["over_credit_among_judge_credited_cells"]["denominator"]) == (2, 6)
    # J=0: 4 cells; A=1 among them: 2
    assert (r["under_credit_among_J0_cells"]["numerator"], r["under_credit_among_J0_cells"]["denominator"]) == (2, 4)
    # J<=1: 6 cells (0,1)(0,1)(0,0)(0,0)(1,1)(1,0); A=1: 3
    assert (r["under_credit_among_Jle1_cells"]["numerator"], r["under_credit_among_Jle1_cells"]["denominator"]) == (3, 6)
    # A=1: (3,1)(3,1)(2,1)(0,1)(0,1)(1,1)(3,1) = 7 cells; J<=1 among them: 3
    assert (r["under_credit_among_A1_cells"]["numerator"], r["under_credit_among_A1_cells"]["denominator"]) == (3, 7)
    assert r["two_sided_disagreement_rate"]["estimate"] == pytest.approx(5 / 12)
    assert r["balanced_two_sided_disagreement"]["estimate"] == pytest.approx(0.5 * (2 / 6 + 3 / 6))
    assert r["two_sided_disagreement_rate"]["estimate"] == pytest.approx(
        1 - er.table_block(cells, B, SEED)["metrics"]["raw_agreement"]["estimate"])


def test_pi_hat_is_the_analyzers_registered_estimate():
    rows = random_rows()
    cells = cells_of(rows)
    blk = er.credit_block(cells, B, SEED)["pi_hat_J_ge2_and_A0"]
    direct = ah.silent_over_credit_rate(cells, B=B, seed=SEED)
    assert blk["events"] == direct["events"] == sum(c["J"] >= 2 and c["A"] == 0 for c in cells)
    assert blk["estimate"] == direct["pi_hat"]
    assert (blk["ci_lo"], blk["ci_hi"]) == (direct["ci_lo"], direct["ci_hi"])


def test_degenerate_interval_is_not_reported_as_zero_width():
    rows = [row(f"Q{i:02d}", "C", 0, 0) for i in range(8)] + [row("Q08", "C", 3, 1), row("Q09", "C", 3, 1)]
    blk = er.credit_block(cells_of(rows), B, SEED)
    res = blk["rates"]["under_credit_among_J0_cells"]  # 0 of 8, every resample is 0
    assert res["estimate"] == 0.0 and res["ci_lo"] is None and "degenerate" in res["ci_reason"]


# --------------------------------------------------------------------------
# 3. label sources: contrast, agreement, paired differences
# --------------------------------------------------------------------------
def test_contrast_equals_the_analyzers_cluster_bootstrap_delta():
    rows = contrast_rows()
    for src in er.SOURCES:
        blk = er.contrast_block(cells_of(rows, src), B, SEED)
        by_q = {}
        for r in rows:
            if r["variant"] in "AB":
                by_q.setdefault(r["cq_id"], {})[r["variant"]] = er.l1_star(r["J"], r["A"][src])
        deltas = {q: [v["B"] - v["A"]] for q, v in by_q.items()}
        direct = ah.cluster_bootstrap_delta(deltas, B, SEED)
        assert blk["n_paired_cqs"] == 6
        assert blk["delta"] == pytest.approx(direct["delta"])
        assert blk["ci_lo"] == pytest.approx(direct["ci_lo"]) and blk["ci_hi"] == pytest.approx(direct["ci_hi"])
    # hand value for the AH labels: d = 0, 2, -1, 2, -1, 2 -> mean 2/3
    assert er.contrast_block(cells_of(rows), B, SEED)["delta"] == pytest.approx(4 / 6)


def test_contrast_only_pairs_cqs_with_both_variants_and_ignores_other_variants():
    rows = contrast_rows() + [row("Q99", "B", 3, 1)]  # a B cell with no A partner
    assert er.contrast_block(cells_of(rows), B, SEED)["n_paired_cqs"] == 6
    with pytest.raises(er.InputRefused):
        er.paired_records(cells_of(contrast_rows() + [row("Q00", "A", 2, 1, cluster="Q00")]))


def test_agreement_counts_and_direction():
    # draft -> AH: two 1->0, one 0->1, three both-1, two both-0
    spec = [(1, 1), (1, 1), (1, 1), (1, 0), (1, 0), (0, 1), (0, 0), (0, 0)]
    rows = [row(f"Q{i:02d}", "C", 3 if i % 2 else 0, aH, draft=d) for i, (d, aH) in enumerate(spec)]
    blk = er.agreement_block(rows, "draft", "AH", B, SEED)
    assert (blk["both_1"], blk["changed_1_to_0"], blk["changed_0_to_1"], blk["both_0"]) == (3, 2, 1, 2)
    assert blk["cohen_kappa"]["estimate"] == pytest.approx(er.kappa_of(3, 2, 1, 2))
    assert blk["raw_agreement"]["estimate"] == pytest.approx(5 / 8)
    assert sum(v["1_to_0"] for v in blk["changes_by_judge_score"].values()) == 2
    assert sum(v["0_to_1"] for v in blk["changes_by_judge_score"].values()) == 1
    rev = er.agreement_block(rows, "AH", "draft", B, SEED)  # the direction flips the two counts
    assert (rev["changed_1_to_0"], rev["changed_0_to_1"]) == (1, 2)


def test_paired_difference_is_second_minus_first():
    rows = contrast_rows()
    rows[0]["A"]["aux"] = 0  # variant-A cell of Q00 (J=3): L1* 3 -> 1 under the aux source
    blk = er.paired_difference_block(rows, "AH", "aux", B, SEED)
    assert blk["difference"] == "aux minus AH"
    # d_Q00 rises by 2 (A's L1* falls by 2); mean over 6 CQs: +2/6; pi-hat: the cell also adds an event (J=3, A=0)
    assert blk["variant_A_to_B_contrast_difference"]["estimate"] == pytest.approx(2 / 6)
    n_events = lambda s: sum(r["J"] >= 2 and r["A"][s] == 0 for r in rows)
    assert blk["pi_hat_difference"]["estimate"] == pytest.approx((n_events("aux") - n_events("AH")) / len(rows))


# --------------------------------------------------------------------------
# 4. the bootstrap replay and the flip search
# --------------------------------------------------------------------------
@pytest.mark.parametrize("n", [6, 23, 33])
def test_replay_equals_the_analyzers_helper(n):
    rng = np.random.default_rng(n)
    rp = er.Replay(n, B, SEED)
    for _ in range(5):
        num = rng.integers(0, 4, n)
        den = rng.integers(2, 7, n)
        recs = [{"cluster_id": f"C{i:03d}", "num": int(num[i]), "den": int(den[i])} for i in range(n)]
        helper = ah.cluster_bootstrap_stat(
            recs, lambda s: sum(r["num"] for r in s) / sum(r["den"] for r in s), None, "cluster_id", B, SEED)
        theta, lo, hi = rp.ratio_interval(num, den)
        assert theta == pytest.approx(helper["estimate"], abs=1e-12)
        assert lo == pytest.approx(helper["ci_lo"], abs=1e-12) and hi == pytest.approx(helper["ci_hi"], abs=1e-12)


def _brute_min(caps, bound, crossed):
    for k in range(1, sum(caps) + 1):
        if any(crossed(bound(x)) for x in er._iter_states(caps, k)):
            return k
    return None


def test_state_enumeration_counts():
    caps = [2, 1, 3]
    for k in range(0, 7):
        states = list(er._iter_states(caps, k))
        assert len(states) == er._count_states(caps, k) == len(set(states))
        assert all(sum(x) == k and all(0 <= v <= c for v, c in zip(x, caps)) for x in states)


@pytest.mark.parametrize("seed", range(6))
def test_search_equals_brute_force(seed):
    rng = random.Random(seed)
    caps = [rng.randint(1, 3) for _ in range(5)]
    w = [rng.randint(-3, 6) for _ in caps]
    bound = lambda x: sum(a * b for a, b in zip(w, x)) + (x[0] * x[1]) * 0.5
    for prefer in ("max", "min"):
        thr = rng.randint(2, 12)
        crossed = (lambda b: b >= thr) if prefer == "max" else (lambda b: b <= -thr)
        got = er.search_min_flips(caps, bound, crossed, prefer)
        want = _brute_min(caps, bound, crossed)
        assert got["min_flips_witness"] == want
        assert got["exact"] is True
        if want is None:
            assert got["reachable"] is False
        else:
            assert crossed(bound(got["state"]))


def test_greedy_fallback_gives_a_valid_witness_and_a_certified_lower_bound():
    caps = [1] * 8
    w = [5, 4, 4, 3, 2, 2, 1, 1]
    bound = lambda x: sum(a * b for a, b in zip(w, x))
    crossed = lambda b: b >= 12
    exact = er.search_min_flips(caps, bound, crossed, "max")
    forced = er.search_min_flips(caps, bound, crossed, "max", max_states_per_k=3)
    assert exact["min_flips_witness"] == 3 and exact["exact"]
    assert forced["method"].startswith("greedy")
    assert forced["min_flips_lower_bound"] <= exact["min_flips_witness"] <= forced["min_flips_witness"]
    assert crossed(bound(forced["state"]))
    partial = er.search_min_flips(caps, bound, crossed, "max", max_states_per_k=30)  # exhaustive through k=2
    assert partial["min_flips_lower_bound"] == 3 and partial["exact"]


def test_search_reports_unreachable():
    res = er.search_min_flips([1, 1, 1], lambda x: float(sum(x)), lambda b: b >= 10, "max")
    assert res["reachable"] is False and res["min_flips_witness"] is None


# --------------------------------------------------------------------------
# 4. tipping points against brute force through the analyzer's own helper
# --------------------------------------------------------------------------
def _flipped(rows, picks, src="AH"):
    out = [dict(r, A=dict(r["A"])) for r in rows]
    for i in picks:
        out[i]["A"][src] = 1 - out[i]["A"][src]
    return out


def _contrast_effect(rows, i):
    """Signed effect on d of flipping row i's AH label (0 if it cannot move L1*)."""
    r = rows[i]
    if r["variant"] not in ("A", "B") or r["J"] < 2:
        return 0
    delta = er.l1_star(r["J"], 1 - r["A"]["AH"]) - er.l1_star(r["J"], r["A"]["AH"])
    return delta if r["variant"] == "B" else -delta


def _brute_contrast(rows):
    """Fewest flips (per direction) that reverse the sign of delta / change the CI status, found by
    trying every flip set through ``contrast_block``, which calls the analyzer's helper directly."""
    base = er.contrast_block(cells_of(rows), B, SEED)
    out = {}
    for direction in ("down", "up"):
        idx = [i for i in range(len(rows)) if _contrast_effect(rows, i) != 0
               and (_contrast_effect(rows, i) < 0) == (direction == "down")]
        sign_k = ci_k = None
        for k in range(1, len(idx) + 1):
            for picks in itertools.combinations(idx, k):
                blk = er.contrast_block(cells_of(_flipped(rows, picks)), B, SEED)
                if sign_k is None and blk["delta"] * base["delta"] < 0:
                    sign_k = k
                if ci_k is None and blk["ci_status"] != base["ci_status"]:
                    ci_k = k
        out[direction] = (sign_k, ci_k)
    return base, out


def test_contrast_tipping_matches_brute_force():
    rows = contrast_rows()
    base, brute = _brute_contrast(rows)
    tip = er.tipping_contrast(rows, B, SEED)
    assert tip["baseline"]["delta"] == pytest.approx(base["delta"])
    assert tip["baseline"]["ci_status"] == base["ci_status"]
    # sign reversal: only in the direction that moves the delta toward 0, exact through sorting
    sign = tip["sign_reversal"]
    assert sign["up"]["applicable"] is False
    assert sign["down"]["min_flips_delta_strictly_reversed"] == brute["down"][0]
    # CI-status change in each applicable direction
    ci = tip["ci_status_change"]
    for direction in ("down", "up"):
        rec = ci[direction]
        if rec["applicable"] and rec["reachable"]:
            assert rec["min_flips_witness"] == brute[direction][1], direction
            assert rec["witness"]["ci_status"] != base["ci_status"]
            assert rec["witness"]["replay_matches_analyzer"] is True
        elif rec["applicable"]:
            assert brute[direction][1] is None
    reached = [ci[d]["min_flips_witness"] for d in ("down", "up") if ci[d].get("reachable")]
    assert reached, "the fixture should let at least one CI status change"


def test_contrast_tipping_witness_and_composition_have_no_identifiers():
    tip = er.tipping_contrast(contrast_rows(), B, SEED)
    text = json.dumps(tip)
    assert "Q0" not in text and "cell_id" not in text
    comp = tip["sign_reversal"]["down"]["witness_composition"]
    assert sum(c["count"] for c in comp) == tip["sign_reversal"]["down"]["min_flips_delta_strictly_reversed"]


def _pi_rows(n_clusters, per_cluster, events_per_cluster, candidates):
    """Clusters of identical shape: ``events_per_cluster`` lists each cluster's J>=2&A=0 cells,
    ``candidates`` its J>=2&A=1 cells; the rest are J=0&A=0."""
    rows = []
    for c in range(n_clusters):
        q = f"Q{c:03d}"
        ne, nc = events_per_cluster.get(c, 0), candidates.get(c, 0)
        for k in range(per_cluster):
            if k < ne:
                rows.append(row(q, "C", 3, 0))
            elif k < ne + nc:
                rows.append(row(q, "C", 3, 1))
            else:
                rows.append(row(q, "C", 0, 0))
    return rows


def _pi_ub(rows, n_clusters):
    res = ah.silent_over_credit_rate(cells_of(rows), B=B, seed=SEED)
    if res["events"] == 0:
        return ah.clopper_pearson_upper(0, n_clusters, 0.025)
    return res["ci_hi"]


def test_pi_tipping_down_matches_brute_force():
    K = 36
    rows = _pi_rows(K, 2, {0: 2, 1: 1, 2: 1, 3: 1}, {c: 1 for c in range(4, 12)})
    base_ub = _pi_ub(rows, K)
    assert base_ub > 0.10
    events = [i for i, r in enumerate(rows) if r["J"] >= 2 and r["A"]["AH"] == 0]
    want = None
    for k in range(1, len(events) + 1):
        if any(_pi_ub(_flipped(rows, p), K) <= 0.10 + 1e-12 for p in itertools.combinations(events, k)):
            want = k
            break
    tip = er.tipping_pi(rows, B, SEED)
    assert tip["baseline"]["above_threshold"] is True
    assert tip["up"]["applicable"] is False
    assert tip["down"]["applicable"] is True
    assert tip["down"]["min_flips_witness"] == want
    assert want is not None and want >= 2, "the fixture should need more than one flip"
    assert tip["down"]["statistic_at_witness"]["ci_hi"] <= 0.10 + 1e-12


def test_pi_tipping_up_from_a_zero_event_baseline_matches_brute_force():
    K = 60
    rows = _pi_rows(K, 1, {}, {c: 1 for c in range(10)})  # 10 J>=2&A=1 cells, no event anywhere
    base_ub = _pi_ub(rows, K)
    assert base_ub == pytest.approx(ah.clopper_pearson_upper(0, K, 0.025)) and base_ub <= 0.10
    cand = [i for i, r in enumerate(rows) if r["J"] >= 2 and r["A"]["AH"] == 1]
    want = None
    for k in range(1, len(cand) + 1):
        if any(_pi_ub(_flipped(rows, p), K) > 0.10 + 1e-12 for p in itertools.combinations(cand, k)):
            want = k
            break
    tip = er.tipping_pi(rows, B, SEED)
    assert tip["baseline"]["above_threshold"] is False and tip["baseline"]["events"] == 0
    assert tip["down"]["applicable"] is False and tip["up"]["applicable"] is True
    assert tip["up"].get("min_flips_witness") == want
    assert want is not None


def test_pi_tipping_is_unreachable_when_only_a_zero_event_state_would_pass():
    """At 10 clusters a zero-event state is scored with the Clopper-Pearson bound (30.8%), not 0."""
    K = 10
    rows = _pi_rows(K, 2, {0: 1, 1: 1}, {c: 1 for c in range(2, 6)})
    assert _pi_ub(rows, K) > 0.10
    events = [i for i, r in enumerate(rows) if r["J"] >= 2 and r["A"]["AH"] == 0]
    assert all(_pi_ub(_flipped(rows, p), K) > 0.10
               for k in (1, 2) for p in itertools.combinations(events, k))
    down = er.tipping_pi(rows, B, SEED)["down"]
    assert down["applicable"] is True and down["reachable"] is False and down["exact"] is True


def test_zero_event_states_are_scored_with_the_cluster_level_bound():
    K = 36  # 1 - 0.025**(1/36) = 9.74% < 10%, so a zero-event state at 36 clusters passes ...
    rows = _pi_rows(K, 2, {0: 1}, {c: 1 for c in range(1, 6)})
    tip = er.tipping_pi(rows, B, SEED)
    assert tip["registered_G1_cluster_level_cp"]["crossable_by_flips"] is True
    K = 33  # ... and at 33 clusters it does not (10.58%)
    tip33 = er.tipping_pi(_pi_rows(K, 2, {0: 1}, {c: 1 for c in range(1, 6)}), B, SEED)
    assert tip33["registered_G1_cluster_level_cp"]["crossable_by_flips"] is False
    assert tip33["registered_G1_cluster_level_cp"]["bound_at_zero_event_clusters"] == pytest.approx(
        1 - 0.025 ** (1 / 33))


# --------------------------------------------------------------------------
# 5. the G1 design fact
# --------------------------------------------------------------------------
def test_g1_design_fact_33_clusters():
    g = er.g1_design_fact(33)
    assert g["zero_event_upper_bound"] == pytest.approx(1 - 0.025 ** (1 / 33))
    assert g["zero_event_upper_bound_pct_2dp"] == 10.58
    assert g["passable_at_this_n"] is False and g["min_clusters_for_a_zero_event_pass"] == 36
    assert er.g1_design_fact(36)["passable_at_this_n"] is True


# --------------------------------------------------------------------------
# input handling, guards, end to end
# --------------------------------------------------------------------------
def test_end_to_end_is_deterministic_aggregate_only_and_records_hashes(tmp_path):
    rows = random_rows()
    p = write_fixture(tmp_path, rows)
    first = er.build_report(*p, B=B, seed=SEED)
    second = er.build_report(*p, B=B, seed=SEED)
    text = json.dumps(first, indent=1, allow_nan=False)
    assert text == json.dumps(second, indent=1, allow_nan=False)
    # aggregates only: no ids, no span, note, evidence or rationale text
    for r in rows:
        assert r["cell_id"] not in text and r["cq_id"] not in text
    assert "ablated_control" not in text and "CTRL" not in text
    assert "SECRET" not in text
    assert not FORBIDDEN.search(text)
    # every analysis block carries the flag, and the status line says so
    assert first["status"].startswith("EXPLORATORY AND POST-HOC")
    for key in ("item3_label_source_comparison", "item4_rater_error_tipping_points_AH", "item5_g1_design_fact"):
        assert first[key]["exploratory_post_hoc"] is True
    for src in er.SOURCES:
        assert first["item3_label_source_comparison"]["sources"][src]["exploratory_post_hoc"] is True
    # input hashes
    for role, path in zip(("per_cell", "cells", "drafts", "aux"), p):
        assert first["inputs"][role]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
        assert first["inputs"][role]["file"] == path.name
    assert first["code"]["exploratory_reanalysis.py"] == hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    assert first["code"]["analyze_holdout.py"] == hashlib.sha256((HERE / "analyze_holdout.py").read_bytes()).hexdigest()
    assert first["design"]["registered_scheme"] is False  # B=200 is not the registered 10,000
    assert first["design"]["n_primary_cells"] == len(rows)
    assert all(v is True for k, v in first["checks"].items() if k != "n_primary_cells" and k != "n_clusters"
               and isinstance(v, bool))
    # no NaN anywhere (allow_nan=False above would have raised)
    assert first["inputs"]["drafts"]["model_field_values"] == {"draft-model": len(rows) + 2}


def test_end_to_end_ignores_control_rows_and_the_placeholder_a(tmp_path):
    rows = random_rows()
    p = write_fixture(tmp_path, rows, n_controls=3)
    rep = er.build_report(*p, B=B, seed=SEED)
    assert rep["design"]["n_primary_cells"] == len(rows)  # the 3 control rows in every file are dropped
    # the placeholder A=0 written into cells.jsonl never reaches a label
    assert rep["item1_table_2x2_AH"]["counts"]["n"] == len(rows)
    t = er.table_of(cells_of(rows))
    assert rep["item1_table_2x2_AH"]["counts"]["Jge2_A1"] == t.n11


@pytest.mark.parametrize("bad", ["aux_value", "missing_draft", "id_mismatch", "draft_value"])
def test_strict_inputs(tmp_path, bad):
    rows = random_rows(6)
    p_cell, p_run, p_draft, p_aux = write_fixture(tmp_path, rows)
    if bad == "aux_value":
        lines = [json.loads(l) for l in p_aux.read_text().splitlines()]
        lines[0]["A_auxiliary"] = 2
        p_aux.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    elif bad == "missing_draft":
        text = p_draft.read_text().splitlines()
        p_draft.write_text("\n".join(text[:1] + text[2:]) + "\n")
    elif bad == "id_mismatch":
        lines = [json.loads(l) for l in p_run.read_text().splitlines()]
        lines[0]["cell_id"] = "primary:Z:ZZZ"
        p_run.write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    else:
        with open(p_draft, newline="", encoding="utf-8") as h:
            table = list(csv.reader(h))
        table[1][1] = "1.0"  # A_draft must be exactly '0' or '1'
        with open(p_draft, "w", newline="", encoding="utf-8") as h:
            csv.writer(h).writerows(table)
    with pytest.raises(er.InputRefused):
        er.load_inputs(p_cell, p_run, p_draft, p_aux)


def test_path_guards(tmp_path):
    with pytest.raises(er.InputRefused):
        er.refuse_input(tmp_path / "persona_pass" / "x.json")
    with pytest.raises(er.InputRefused):
        er.refuse_output(tmp_path / "persona_pass_results" / "o.json", [])
    with pytest.raises(er.InputRefused):
        er.refuse_output(Path("<labels>/locked/out.json"), [])
    with pytest.raises(er.InputRefused):
        er.refuse_output(Path("<labels>/new/out.json"), [])
    src = tmp_path / "in.json"
    with pytest.raises(er.InputRefused):
        er.refuse_output(src, [src])
    assert er.refuse_output(tmp_path / "ok.json", [src]) == (tmp_path / "ok.json").resolve()
    p_cell, p_run, p_draft, p_aux = write_fixture(tmp_path, random_rows(5))
    hidden = tmp_path / "persona_pass"
    hidden.mkdir()
    moved = hidden / "draft.csv"
    moved.write_bytes(p_draft.read_bytes())
    with pytest.raises(er.InputRefused):  # refused before the file is opened
        er.load_inputs(p_cell, p_run, moved, p_aux)


def test_cli_writes_the_file_and_refuses_an_input_as_output(tmp_path, capsys):
    p_cell, p_run, p_draft, p_aux = write_fixture(tmp_path, random_rows(6))
    out = tmp_path / "out.json"
    args = ["--per-cell", str(p_cell), "--cells", str(p_run), "--drafts", str(p_draft), "--aux", str(p_aux),
            "--resamples", str(B)]
    assert er.main(args + ["--out", str(out)]) == 0
    first = out.read_bytes()
    assert er.main(args + ["--out", str(out)]) == 0
    assert out.read_bytes() == first  # byte-identical on a re-run
    printed = capsys.readouterr().out
    assert hashlib.sha256(first).hexdigest() in printed
    with pytest.raises(er.InputRefused):
        er.main(args + ["--out", str(p_aux)])


def test_committed_artifacts_are_consistent_with_the_code():
    """If the JSON and README section are committed, the recorded hashes must match the files."""
    results = SCRIPT.parent
    js = results / "exploratory_reanalysis.json"
    if not js.exists():
        pytest.skip("exploratory_reanalysis.json not generated yet")
    rep = json.loads(js.read_text(encoding="utf-8"))
    assert rep["code"]["exploratory_reanalysis.py"] == hashlib.sha256(SCRIPT.read_bytes()).hexdigest()
    assert rep["code"]["analyze_holdout.py"] == hashlib.sha256((HERE / "analyze_holdout.py").read_bytes()).hexdigest()
    assert rep["design"]["registered_scheme"] is True
    assert not FORBIDDEN.search(js.read_text(encoding="utf-8"))
    readme = (results / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Exploratory re-analysis", 1)
    assert len(section) == 2, "README section missing"
    body = section[1].split("\n## ", 1)[0]
    assert hashlib.sha256(js.read_bytes()).hexdigest() in body
    assert hashlib.sha256(SCRIPT.read_bytes()).hexdigest() in body
    assert not FORBIDDEN.search(body)
    for role in ("per_cell", "cells", "drafts", "aux"):
        assert rep["inputs"][role]["sha256"] in body
