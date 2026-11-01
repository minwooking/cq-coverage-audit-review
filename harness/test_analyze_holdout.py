"""Tests for the pre-registered holdout analysis.

ALL DATA HERE IS SYNTHETIC and exists only to exercise the statistics. None of
it is a study result, and none of it may be quoted as one.
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analyze_holdout as ah  # noqa: E402


# --- demotion is one-sided -------------------------------------------------
@pytest.mark.parametrize("j,a,expected", [
    (3, 1, 3), (2, 1, 2), (0, 1, 0),
    (3, 0, 1), (2, 0, 1), (1, 0, 1), (0, 0, 0),
])
def test_demotion_never_promotes(j, a, expected):
    assert ah.demote(j, a) == expected


def test_demote_rejects_out_of_range():
    with pytest.raises(ValueError):
        ah.demote(4, 1)
    with pytest.raises(ValueError):
        ah.demote(2, 2)


# --- the estimand must use the pre-demotion score --------------------------
def test_silent_over_credit_uses_raw_judge_score():
    """Regression guard for the vacuous-estimand bug.

    pi = Pr[J >= 2 AND A == 0]. Computing it from the demoted L1* instead would
    make it identically zero, since L1* >= 2 implies A == 1 by construction.
    """
    cells = [
        {"cluster_id": "c1", "J": 3, "A": 0},   # silent over-credit
        {"cluster_id": "c2", "J": 1, "A": 0},   # unsupported but modest: not an event
        {"cluster_id": "c3", "J": 3, "A": 1},   # supported: not an event
    ]
    events, n = ah.silent_over_credit(cells)
    assert (events, n) == (1, 3)
    assert all(ah.demote(c["J"], c["A"]) < 2 for c in cells if c["A"] == 0)


def test_silent_over_credit_counts_clusters_not_cells():
    cells = [
        {"cluster_id": "c1", "J": 3, "A": 0},
        {"cluster_id": "c1", "J": 2, "A": 0},   # same cluster: still one event
        {"cluster_id": "c2", "J": 0, "A": 1},
    ]
    assert ah.silent_over_credit(cells) == (1, 2)


# --- zero-event proportions take Clopper-Pearson, never a bootstrap --------
def test_clopper_pearson_exact_bounds_at_n36():
    """Exact bounds, not the rule-of-three approximation.

    3/36 = 8.3% is the rule of three; the exact Clopper-Pearson bound at zero
    events is 8.0% one-sided at 95% and 9.7% at 97.5%.
    """
    assert ah.clopper_pearson_upper(0, 36, alpha=0.05) == pytest.approx(0.0798, abs=0.001)
    assert ah.clopper_pearson_upper(1, 36, alpha=0.05) == pytest.approx(0.1251, abs=0.001)
    assert ah.clopper_pearson_upper(0, 36, alpha=0.025) == pytest.approx(0.0974, abs=0.001)
    assert ah.clopper_pearson_upper(1, 36, alpha=0.025) == pytest.approx(0.1453, abs=0.001)


def test_analyse_accepts_explicit_g1_confidence_level():
    cells = [{"variant": "A", "cq_id": f"q{i}", "cluster_id": f"c{i}",
              "J": 3 if i == 0 else 0, "A": 0 if i == 0 else 1}
             for i in range(36)]
    res_95 = ah.analyse(cells, seed=1, g1_alpha=0.05)
    res_975 = ah.analyse(cells, seed=1, g1_alpha=0.025)
    g1_95 = res_95["gates"]["G1_silent_over_credit"]
    g1_975 = res_975["gates"]["G1_silent_over_credit"]
    assert g1_95["confidence_level"] == pytest.approx(0.95)
    assert g1_975["confidence_level"] == pytest.approx(0.975)
    assert g1_95["upper_bound_one_sided"] < g1_975["upper_bound_one_sided"]


def test_one_event_breaches_the_ten_percent_gate_at_either_level():
    """G1 is effectively zero-tolerance at this sample size, under both readings
    of the confidence level that PREREG uses inconsistently."""
    for alpha in (0.05, 0.025):
        assert ah.clopper_pearson_upper(0, 36, alpha=alpha) < 0.10
        assert ah.clopper_pearson_upper(1, 36, alpha=alpha) > 0.10


# --- resampling unit -------------------------------------------------------
def test_bootstrap_resamples_clusters_not_questions():
    """Two clusters of very different size must not be weighted by question count."""
    big = {"c1": [1.0] * 20, "c2": [-1.0]}
    res = ah.cluster_bootstrap_delta(big, resamples=200, seed=1)
    assert res["n_clusters"] == 2
    assert res["unit"] == "semantic cluster"
    assert res["delta"] == pytest.approx(0.0)  # cluster means +1 and -1


def test_bootstrap_refuses_to_default_the_seed():
    with pytest.raises(ValueError):
        ah.cluster_bootstrap_delta({"c1": [1.0], "c2": [0.0]}, seed=None)


# --- rank companion --------------------------------------------------------
def test_wilcoxon_drops_zeros():
    res = ah.wilcoxon_zeros_dropped([0, 0, 1, 2, 3, 4, 5, 6, 0])
    assert res["n_nonzero"] == 6


def test_wilcoxon_all_zero_is_reported_not_crashed():
    assert ah.wilcoxon_zeros_dropped([0, 0, 0])["p"] is None


# --- multiplicity ----------------------------------------------------------
def test_holm_applies_to_exactly_the_two_confirmatory_contrasts():
    assert ah.CONFIRMATORY_CONTRASTS == (("A", "B"), ("B", "Bprime"))
    adj = ah.holm({"A->B": 0.01, "B->Bprime": 0.04})
    assert len(adj) == 2
    assert adj["A->B"] == pytest.approx(0.02)
    assert adj["B->Bprime"] == pytest.approx(0.04)


def test_holm_is_monotone():
    adj = ah.holm({"x": 0.5, "y": 0.001})
    assert adj["y"] <= adj["x"]


# --- unresolved is not equivalent -----------------------------------------
def test_wide_interval_containing_zero_is_unresolved_not_equivalent():
    assert ah.tost_decision(-0.9, 0.9) == "unresolved"


def test_equivalence_requires_the_interval_inside_the_margin():
    assert ah.tost_decision(-0.1, 0.1) == "equivalent"
    assert ah.tost_decision(-0.29, 0.29) == "equivalent"
    assert ah.tost_decision(-0.31, 0.29) == "unresolved"


def test_interval_excluding_zero_is_resolved():
    assert ah.tost_decision(0.2, 0.8) == "resolved"
    assert ah.tost_decision(-0.8, -0.2) == "resolved"


# --- coverage --------------------------------------------------------------
def test_coverage_denominator_is_three_points_per_question():
    assert ah.coverage([3, 3, 3, 3]) == 100.0
    assert ah.coverage([0, 0, 0, 0]) == 0.0
    assert ah.coverage([3, 0]) == pytest.approx(50.0)


def test_coverage_on_empty_set_is_an_error_not_zero():
    with pytest.raises(ValueError):
        ah.coverage([])



# --- human CSV wiring ------------------------------------------------------
def _write_label_csv(path: Path, rows: list[dict], *, source: str | None = None) -> Path:
    fieldnames = ["cell_id", "A", "rater_L1"]
    if source is not None:
        fieldnames.append("label_source")
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            output = {key: row.get(key, "") for key in fieldnames}
            if source is not None:
                output["label_source"] = source
            writer.writerow(output)
    return path


def _cells_for_label_join() -> list[dict]:
    return [
        {"cell_id": "cell-1", "cq_id": "q1", "cluster_id": "c1",
         "variant": "A", "J": 3, "A": 0},
        {"cell_id": "cell-2", "cq_id": "q2", "cluster_id": "c2",
         "variant": "A", "J": 1, "A": 0},
    ]


def test_human_labels_join_by_cell_id_and_record_coverage(tmp_path: Path):
    labels_path = _write_label_csv(
        tmp_path / "labels.csv",
        [{"cell_id": "cell-1", "A": "1"}, {"cell_id": "cell-2", "A": "0"}],
        source="human",
    )
    labels = ah.load_label_csv(labels_path)
    joined, metadata = ah.join_labels(_cells_for_label_join(), labels)
    assert [cell["L1_star"] for cell in joined] == [3, 1]
    assert metadata["source"] == "human"
    assert metadata["labeled_cells"] == 2
    assert metadata["coverage_denominator"] == {
        "n_cells": 2,
        "max_points": 6,
        "formula": "sum(L1_star) / (labeled_cells * 3) * 100",
    }


def test_label_cell_id_mismatch_fails_with_ids(tmp_path: Path):
    labels_path = _write_label_csv(
        tmp_path / "labels.csv",
        [{"cell_id": "cell-1", "A": "1"}, {"cell_id": "extra", "A": "0"}],
        source="human",
    )
    labels = ah.load_label_csv(labels_path)
    with pytest.raises(ValueError, match=r"extra"):
        ah.join_labels(_cells_for_label_join(), labels)

    cells_path = _write_label_csv(
        tmp_path / "labels_only_one.csv",
        [{"cell_id": "cell-1", "A": "1"}],
        source="human",
    )
    labels = ah.load_label_csv(cells_path)
    with pytest.raises(ValueError, match=r"cell-2"):
        ah.join_labels(_cells_for_label_join(), labels)


def test_invalid_or_blank_a_fails_and_names_invalid_id(tmp_path: Path):
    labels_path = _write_label_csv(
        tmp_path / "labels.csv",
        [{"cell_id": "cell-1", "A": "2"}],
        source="human",
    )
    with pytest.raises(ValueError, match=r"cell-1"):
        ah.load_label_csv(labels_path)

    blank_path = _write_label_csv(
        tmp_path / "blank.csv",
        [{"cell_id": "cell-1", "A": ""}],
        source="human",
    )
    with pytest.raises(ValueError, match=r"cell-1"):
        ah.load_label_csv(blank_path)


def test_demotion_rule_after_csv_join_never_promotes_score(tmp_path: Path):
    labels_path = _write_label_csv(
        tmp_path / "labels.csv",
        [{"cell_id": "cell-1", "A": "0"}, {"cell_id": "cell-2", "A": "1"}],
        source="human",
    )
    joined, _ = ah.join_labels(
        _cells_for_label_join(), ah.load_label_csv(labels_path)
    )
    assert joined[0]["J"] == 3
    assert joined[0]["L1_star"] == 1
    assert all(cell["L1_star"] <= cell["J"] for cell in joined)


def test_label_source_is_required_when_csv_does_not_mark_provenance(tmp_path: Path):
    labels_path = _write_label_csv(
        tmp_path / "labels.csv",
        [{"cell_id": "cell-1", "A": "1"}],
    )
    with pytest.raises(ValueError, match="label source"):
        ah.load_label_csv(labels_path)
    labels = ah.load_label_csv(labels_path, label_source="LLM, not human")
    assert labels.source == "LLM, not human"
    assert labels.simulated is True



def test_external_labels_supply_a_for_judge_only_jsonl(tmp_path: Path):
    cells_path = tmp_path / "cells.jsonl"
    cells_path.write_text(
        "\n".join(
            __import__("json").dumps({
                "cell_id": cell_id, "cq_id": cell_id, "cluster_id": cell_id,
                "variant": "A", "J": 3,
            })
            for cell_id in ("cell-1", "cell-2")
        ) + "\n",
        encoding="utf-8",
    )
    labels_path = _write_label_csv(
        tmp_path / "labels.csv",
        [{"cell_id": "cell-1", "A": "0"}, {"cell_id": "cell-2", "A": "1"}],
        source="human",
    )
    cells = ah.load_cells(cells_path, require_a=False)
    joined, _ = ah.join_labels(cells, ah.load_label_csv(labels_path))
    assert [cell["L1_star"] for cell in joined] == [1, 3]


def _run_main(ah, argv):
    """analyze_holdout.main() reads sys.argv; drive it the way the CLI does."""
    import sys as _sys
    old = _sys.argv
    _sys.argv = ["analyze_holdout.py", "--seed", "20260913", *argv]
    try:
        return ah.main()
    finally:
        _sys.argv = old


def _write_simulated_cells(path):
    """36 judge cells, every one marked SIMULATED, with no A field."""
    import json as _json
    rows = []
    for i in range(36):
        rows.append({
            "cell_id": f"CQB{i + 1:02d}",
            "variant": "BRICK_SOURCE",
            "cq_id": f"CQB{i + 1:02d}",
            "cluster_id": f"c{i % 6}",
            "J": 2,
            "SIMULATED": True,
        })
    path.write_text("\n".join(_json.dumps(r) for r in rows) + "\n")
    return path


def _write_labels(path, source):
    lines = ["cell_id,A,label_source"]
    for i in range(36):
        lines.append(f"CQB{i + 1:02d},1,{source}")
    path.write_text("\n".join(lines) + "\n")
    return path


def test_human_labels_over_simulated_judge_run_are_refused(tmp_path, capsys):
    """A human evidence pass over SIMULATED judge output must not be reportable."""
    import analyze_holdout as ah

    cells = _write_simulated_cells(tmp_path / "cells.jsonl")
    labels = _write_labels(tmp_path / "labels.csv", "human")
    out = tmp_path / "res.json"
    with pytest.raises(SystemExit) as excinfo:
        _run_main(ah, [str(cells), "--labels", str(labels), "--out", str(out)])
    assert "SIMULATED" in str(excinfo.value)
    assert not out.exists()


def test_rehearsal_flag_allows_it_but_stamps_the_result(tmp_path):
    """The escape hatch works and marks the output as a rehearsal."""
    import json as _json

    import analyze_holdout as ah

    cells = _write_simulated_cells(tmp_path / "cells.jsonl")
    labels = _write_labels(tmp_path / "labels.csv", "human")
    out = tmp_path / "res.json"
    _run_main(ah, [
        str(cells), "--labels", str(labels), "--out", str(out),
        "--allow-human-labels-on-simulated-run", "--allow-partial",
    ])
    res = _json.loads(out.read_text())
    assert res["rehearsal"] is True
    assert res["judge_simulated"] is True


def test_simulated_labels_over_simulated_run_are_fine(tmp_path):
    """Matching provenance needs no escape hatch."""
    import json as _json

    import analyze_holdout as ah

    cells = _write_simulated_cells(tmp_path / "cells.jsonl")
    labels = _write_labels(tmp_path / "labels.csv", "simulated")
    out = tmp_path / "res.json"
    _run_main(ah, [str(cells), "--labels", str(labels), "--out", str(out), "--allow-partial"])
    res = _json.loads(out.read_text())
    assert res["label_source"] == "LLM, not human"
    assert res.get("rehearsal") is None


# --- registered G1-G8 gate contract ----------------------------------------
def _base_gate_cells(n=6):
    rows = []
    for i in range(n):
        rows.append({"cell_id": f"A{i}", "variant": "A", "cq_id": f"q{i}",
                     "cluster_id": f"c{i}", "J": 0, "A": 1,
                     "rater_L1": 0})
        rows.append({"cell_id": f"B{i}", "variant": "B", "cq_id": f"q{i}",
                     "cluster_id": f"c{i}", "J": 3, "A": 1,
                     "rater_L1": 3})
    return rows


def test_all_gate_records_share_common_envelope_and_summary():
    res = ah.analyse(_base_gate_cells(), seed=7)
    assert len(res["gates"]) == 8
    for gate in res["gates"].values():
        assert set(("status", "value", "threshold", "reason")) <= set(gate)
    assert res["gates_summary"]["total"] == 8
    assert res["gates_summary"]["computed"] + res["gates_summary"]["not_computable"] == 8


def _ablated_controls(n_supported: int, n_total: int = 24, with_a: bool = True):
    """ablated_control cells whose A is the EVALUATOR's label (A=1 supported)."""
    rows = []
    for i in range(n_total):
        row = {"cell_id": f"N{i}", "variant": "A", "cq_id": f"n{i}", "cluster_id": f"n{i}",
               "J": 3, "cell_kind": "ablated_control"}
        if with_a:
            row["A"] = 1 if i < n_supported else 0
        rows.append(row)
    return rows


@pytest.mark.parametrize("n_supported,expected", [(0, "pass"), (2, "pass"), (3, "fail"),
                                                   (24, "fail")])
def test_g3_is_the_evaluators_A_on_the_24_ablated_controls(n_supported, expected):
    """22/24 unsupported (A=0) is the registered pass line (PREREG L345)."""
    res = ah.analyse(_base_gate_cells() + _ablated_controls(n_supported), seed=7,
                     controls_valid=True, bootstrap_resamples=50)
    gate = res["gates"]["G3_negative_control"]
    assert gate["status"] == expected
    assert gate["n_unsupported"] == 24 - n_supported and gate["n_supported"] == n_supported
    assert gate["value"] == pytest.approx((24 - n_supported) / 24)
    assert gate["threshold"] == pytest.approx(22 / 24)
    assert gate["evaluator_field"].startswith("A") and gate["controls_valid_asserted"] is True


def test_g3_by_default_is_not_computable_and_never_reads_the_control_a():
    cells = _base_gate_cells() + _ablated_controls(0)
    gate = ah.analyse(cells, seed=7, bootstrap_resamples=50)["gates"]["G3_negative_control"]
    assert gate["status"] == "not_computable" and gate["reasons"]
    flipped = _base_gate_cells() + _ablated_controls(24)  # every control A inverted
    other = ah.analyse(flipped, seed=7, bootstrap_resamples=50)["gates"]["G3_negative_control"]
    assert gate == other  # not a single number depends on the control labels


def test_g3_ignores_judge_json_verdict_keys():
    """The old reader took 'verdict'/'label'/'decision' keys from the judge's JSON."""
    cells = _base_gate_cells()
    controls = _ablated_controls(24, with_a=False)  # no evaluator A at all
    for c in controls:
        c["judge_response_parsed"] = {"verdict": "unsupported"}
        c["judge_response"] = {"label": "unsupported", "decision": "unsupported"}
    gate = ah.analyse(cells + controls, seed=7, controls_valid=True,
                      bootstrap_resamples=50)["gates"]["G3_negative_control"]
    assert gate["status"] == "not_computable"
    assert "only 0 of the 24 ablated cells carry an A" in gate["reason"]


def test_g3_needs_exactly_24_ablated_cells_all_labeled():
    gate = ah.analyse(_base_gate_cells() + _ablated_controls(0, n_total=23), seed=7,
                      controls_valid=True, bootstrap_resamples=50)["gates"]["G3_negative_control"]
    assert gate["status"] == "not_computable" and "exactly 24" in gate["reason"]
    half = _ablated_controls(0)
    for c in half[:5]:
        del c["A"]
    gate = ah.analyse(_base_gate_cells() + half, seed=7, controls_valid=True,
                      bootstrap_resamples=50)["gates"]["G3_negative_control"]
    assert gate["status"] == "not_computable" and "only 19 of the 24" in gate["reason"]


def test_g3_missing_controls_is_not_computable():
    gate = ah.analyse(_base_gate_cells(), seed=7)["gates"]["G3_negative_control"]
    assert gate["status"] == "not_computable"
    assert "ablated_control" in gate["reason"]


@pytest.mark.parametrize("rater,expected", [(0, "pass"), (3, "fail"), (None, "not_computable")])
def test_g5_mae_paths(rater, expected):
    cells = _base_gate_cells()
    for cell in cells:
        if rater is None:
            cell.pop("rater_L1")
        elif rater == 0:
            cell["rater_L1"] = cell["J"]
        else:
            cell["rater_L1"] = rater
    assert ah.analyse(cells, seed=7)["gates"]["G5_mae_judge_human"]["status"] == expected


def test_g6_requires_non_qwen_judge_and_fragility():
    cells = _base_gate_cells()
    gate = ah.analyse(cells, seed=7)["gates"]["G6_consistency"]
    assert gate["status"] == "not_computable"
    assert "non-Qwen" in gate["reason"]
    for cell in cells:
        cell["non_qwen_J"] = cell["J"]
    gate = ah.analyse(cells, seed=7)["gates"]["G6_consistency"]
    assert gate["status"] == "pass"
    assert gate["value"]["fragility_K"] >= 6


def test_g7_without_an_audit_is_not_computable_and_never_reads_judge_telemetry():
    """G7 now comes from the labeling audit (see the audit-based G7 tests at the
    end of this file); judge-run fields in the cells are not an audit trail."""
    cells = _base_gate_cells()
    for cell in cells:  # the old G7 would have passed on exactly these fields
        cell.update({"started_at_utc": "2026-09-13T00:00:00Z", "elapsed_s": 30.0,
                     "attempt": 1, "artifact_digest": "a" * 64})
    gate = ah.analyse(cells, seed=7)["gates"]["G7_audit_trail"]
    assert gate["status"] == "not_computable"
    assert "--label-audit" in gate["reason"]


def test_falsification_gates_never_claim_pass():
    res = ah.analyse(_base_gate_cells(), seed=7,
                     g4={"ci_hi": 0.8}, g8={"ci_hi": 0.1})
    assert res["gates"]["G4_human_judge_qwk"]["status"] == "not_falsified"
    assert res["gates"]["G8_external_spotcheck"]["status"] == "not_falsified"
    assert all(res["gates"][key]["status"] != "pass"
               for key in ("G4_human_judge_qwk", "G8_external_spotcheck"))


def test_gates_summary_counts_failure_and_not_computable():
    res = ah.analyse(_base_gate_cells(), seed=7)
    summary = res["gates_summary"]
    assert summary["not_computable"] >= 5
    assert summary["failed"] == 1  # G5 intentionally fails on the synthetic disagreement


# ==========================================================================
# Registered-analysis conformance: primary-only population, ONE cluster
# bootstrap, cell-level pi-hat, G1 achievability diagnostic, control-tolerant
# label ingestion.  ALL DATA SYNTHETIC; none of it is a study result.
# ==========================================================================
import hashlib  # noqa: E402
import json as _json  # noqa: E402
import math  # noqa: E402
from collections import Counter  # noqa: E402

import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402

SMALL_B = 150  # resamples for tests that do not assert on the registered B


def _legacy_bca_interval(theta_hat, boot, jack, alpha=0.05):
    """VERBATIM copy of the pre-round-3 BCa: z0 ignores ties (strict <)."""
    boot = np.asarray(boot, dtype=float)
    prop = np.mean(boot < theta_hat)
    prop = min(max(prop, 1.0 / len(boot)), 1.0 - 1.0 / len(boot))
    z0 = stats.norm.ppf(prop)
    jack = np.asarray(jack, dtype=float)
    d = jack.mean() - jack
    denom = 6.0 * (np.sum(d ** 2) ** 1.5)
    acc = 0.0 if denom == 0 else float(np.sum(d ** 3) / denom)
    zs = stats.norm.ppf([alpha / 2, 1 - alpha / 2])
    adj = stats.norm.cdf(z0 + (z0 + zs) / (1 - acc * (z0 + zs)))
    return tuple(float(np.percentile(boot, 100 * a)) for a in adj)


def _legacy_cluster_bootstrap_delta(deltas_by_cluster, resamples, seed):
    """VERBATIM copy of the pre-refactor implementation (regression reference)."""
    ids = sorted(deltas_by_cluster)
    per_cluster = [np.mean(deltas_by_cluster[c]) for c in ids]

    def stat(idx):
        return float(np.mean([per_cluster[i] for i in idx]))

    theta = stat(range(len(ids)))
    rng = np.random.default_rng(seed)
    boot = [stat(rng.integers(0, len(ids), len(ids))) for _ in range(resamples)]
    jack = [stat([i for i in range(len(ids)) if i != k]) for k in range(len(ids))]
    lo, hi = _legacy_bca_interval(theta, boot, jack)
    return theta, lo, hi


def test_unstratified_strict_bootstrap_is_bit_identical_to_the_legacy_implementation():
    rng = np.random.default_rng(11)
    for _ in range(4):
        n = int(rng.integers(3, 25))
        data = {f"c{i:02d}": [float(x) for x in rng.integers(-3, 4, int(rng.integers(1, 4)))]
                for i in range(n)}
        theta, lo, hi = _legacy_cluster_bootstrap_delta(data, 400, 20260913)
        new = ah.cluster_bootstrap_delta(data, resamples=400, seed=20260913, ties="strict")
        assert (new["delta"], new["ci_lo"], new["ci_hi"]) == (theta, lo, hi)


# --- the generic helper ----------------------------------------------------
def _cells_in_strata(sizes: dict, per_cluster: int = 1) -> list[dict]:
    out = []
    for stratum, n in sizes.items():
        for i in range(n):
            for j in range(per_cluster):
                out.append({"cluster_id": f"{stratum}{i}", "category": stratum,
                            "v": float(i + j)})
    return out


def _mean_v(sample):
    return float(np.mean([c["v"] for c in sample]))


def test_stratified_resampling_holds_each_stratum_cluster_count_fixed():
    cells = _cells_in_strata({"x": 3, "y": 4})
    seen = []

    def stat(sample):
        counts = Counter(c["category"] for c in sample)
        seen.append((len(sample), counts["x"], counts["y"]))
        return _mean_v(sample)

    ah.cluster_bootstrap_stat(cells, stat, "category", "cluster_id", B=60, seed=3)
    full = [s for s in seen if s[0] == 7]  # point estimate + bootstrap replicates
    assert len(full) == 61 and set(full) == {(7, 3, 4)}


def test_unstratified_resampling_does_not_hold_stratum_counts_fixed():
    """The contrast that shows the strata option does something."""
    cells = _cells_in_strata({"x": 3, "y": 4})
    seen = []

    def stat(sample):
        seen.append(Counter(c["category"] for c in sample)["x"])
        return _mean_v(sample)

    ah.cluster_bootstrap_stat(cells, stat, None, "cluster_id", B=60, seed=3)
    assert len(set(seen)) > 1


def test_statistics_over_the_same_clusters_see_identical_resamples():
    cells = _cells_in_strata({"x": 3, "y": 4}, per_cluster=2)
    first, second = [], []

    def rec(store):
        def stat(sample):
            store.append(tuple(c["cluster_id"] for c in sample))
            return _mean_v(sample)
        return stat

    ah.cluster_bootstrap_stat(cells, rec(first), "category", "cluster_id", B=40, seed=9)
    ah.cluster_bootstrap_stat(list(reversed(cells)), rec(second), "category",
                              "cluster_id", B=40, seed=9)
    # first[0] is the point estimate, evaluated on the cells in input order; the
    # 40 resamples and the jackknife do not depend on input row order
    assert len(first) == len(second) == 1 + 40 + 7
    assert first[1:] == second[1:]


def test_bootstrap_is_deterministic_in_the_seed():
    cells = _cells_in_strata({"x": 5, "y": 6})
    a = ah.cluster_bootstrap_stat(cells, _mean_v, None, "cluster_id", B=300, seed=5)
    b = ah.cluster_bootstrap_stat(cells, _mean_v, None, "cluster_id", B=300, seed=5)
    c = ah.cluster_bootstrap_stat(cells, _mean_v, None, "cluster_id", B=300, seed=6)
    assert (a["ci_lo"], a["ci_hi"]) == (b["ci_lo"], b["ci_hi"])
    assert (a["ci_lo"], a["ci_hi"]) != (c["ci_lo"], c["ci_hi"])


def test_bootstrap_resamples_clusters_so_the_interval_reflects_cluster_count_not_cell_count():
    """10 clusters of 6 IDENTICAL cells carry 10 independent observations, not 60.
    The percentile-style SE of the cluster bootstrap must match sd/sqrt(10)."""
    values = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
    cells = [{"cluster_id": f"c{i}", "v": v} for i, v in enumerate(values) for _ in range(6)]
    res = ah.cluster_bootstrap_stat(cells, _mean_v, None, "cluster_id", B=4000, seed=1)
    analytic_se = float(np.std(values, ddof=0)) / math.sqrt(len(values))
    half_width = (res["ci_hi"] - res["ci_lo"]) / 2
    assert res["n_clusters"] == 10 and res["n_cells"] == 60
    assert half_width == pytest.approx(1.96 * analytic_se, rel=0.25)
    # a cell-level bootstrap would give an SE ~sqrt(6) smaller
    assert half_width > 1.96 * analytic_se / math.sqrt(6) * 2


def test_bootstrap_refuses_defaulted_seed_and_degenerate_structure():
    cells = _cells_in_strata({"x": 3, "y": 3})
    with pytest.raises(ValueError, match="pre-registered"):
        ah.cluster_bootstrap_stat(cells, _mean_v, None, "cluster_id", B=10, seed=None)
    with pytest.raises(ValueError, match="at least two clusters"):
        ah.cluster_bootstrap_stat(cells[:1], _mean_v, None, "cluster_id", B=10, seed=1)
    with pytest.raises(ValueError, match="no 'cluster_id'"):
        ah.cluster_bootstrap_stat([{"v": 1.0}, {"v": 2.0}], _mean_v, None, "cluster_id",
                                  B=10, seed=1)
    with pytest.raises(ValueError, match="no 'category'"):
        ah.cluster_bootstrap_stat([{"cluster_id": "a", "v": 1.0}, {"cluster_id": "b", "v": 2.0}],
                                  _mean_v, "category", "cluster_id", B=10, seed=1)


def test_a_cluster_cannot_straddle_two_strata():
    cells = [{"cluster_id": "a", "category": "x", "v": 1.0},
             {"cluster_id": "a", "category": "y", "v": 2.0},
             {"cluster_id": "b", "category": "x", "v": 3.0}]
    with pytest.raises(ValueError, match="spans strata"):
        ah.cluster_bootstrap_stat(cells, _mean_v, "category", "cluster_id", B=10, seed=1)


def test_a_statistic_that_is_undefined_is_an_error_not_a_nan_interval():
    cells = _cells_in_strata({"x": 3, "y": 3})
    with pytest.raises(ValueError, match="not finite"):
        ah.cluster_bootstrap_stat(cells, lambda s: float("nan"), None, "cluster_id",
                                  B=10, seed=1)


def test_degenerate_constant_statistic_collapses_to_a_point_without_crashing():
    cells = _cells_in_strata({"x": 3, "y": 3})
    res = ah.cluster_bootstrap_stat(cells, lambda s: 2.0, None, "cluster_id", B=50, seed=1)
    assert (res["ci_lo"], res["ci_hi"], res["estimate"]) == (2.0, 2.0, 2.0)


# --- primary population: controls never reach a primary statistic ----------
def _mk_cell(cell_id, cq, cat, variant, kind, j, a=0):
    return {"cell_id": cell_id, "cq_id": cq, "cluster_id": cq, "category": cat,
            "variant": variant, "cell_kind": kind, "J": j, "A": a,
            "label_source": "pending human evidence", "SIMULATED": False}


def _true_a(j: int, cq: str) -> int:
    """Engineered silent over-credit on every third CQ."""
    return 0 if (j >= 2 and int(cq[1:]) % 3 == 0) else 1


_CATS = ["catA", "catB", "catC"]
_TWINS = [("ablated_control", "A", 0), ("ablated_control", "B", 1),
          ("ablated_control", "B", 2), ("ablated_control", "A", 3),
          ("preserved_control", "B", 4), ("preserved_control", "B", 5)]


def _mimic_cells() -> list[dict]:
    """Scaled-down real state: 3 categories x 4 CQs; variant A on 9 CQs, B on all
    12 (21 primary cells); control twins share (variant, cq_id) with a primary cell
    and carry an adversarially high J.  A is the judge-run placeholder (0)."""
    cells = []
    for i in range(12):
        cq = f"Q{i:02d}"
        for v in ("A", "B"):
            if v == "A" and i >= 9:
                continue
            j = (i * 5 + (0 if v == "A" else 2)) % 4
            cells.append(_mk_cell(f"primary:{v}:{cq}", cq, _CATS[i // 4], v, "primary", j))
    for kind, v, i in _TWINS:
        cq = f"Q{i:02d}"
        cells.append(_mk_cell(f"{kind}:{v}:{cq}", cq, _CATS[i // 4], v, kind, 3))
    return cells


def _with_labels(cells: list[dict], control_a: int = 1) -> list[dict]:
    """Attach the engineered A to primary cells; controls get ``control_a``."""
    out = []
    for c in cells:
        c = dict(c)
        c["A"] = _true_a(c["J"], c["cq_id"]) if c["cell_kind"] == "primary" else control_a
        out.append(c)
    return out


def _truth(cells: list[dict]) -> dict:
    """Independent primary-only expectations (does not call the code under test)."""
    prim = [c for c in cells if c["cell_kind"] == "primary"]
    per_variant: dict = {}
    for c in prim:
        a = _true_a(c["J"], c["cq_id"])
        per_variant.setdefault(c["variant"], []).append(c["J"] if a else min(c["J"], 1))
    events = [c for c in prim if c["J"] >= 2 and _true_a(c["J"], c["cq_id"]) == 0]
    return {
        "coverage": {v: 100.0 * sum(x) / (3 * len(x)) for v, x in per_variant.items()},
        "n_by_variant": {v: len(x) for v, x in per_variant.items()},
        "events": len(events), "n_cells": len(prim),
        "event_clusters": len({c["cq_id"] for c in events}),
        "n_clusters": len({c["cq_id"] for c in prim}),
    }


def _analyse_small(cells, **kw):
    return ah.analyse(cells, 20260913, bootstrap_resamples=SMALL_B, **kw)


def test_fixture_is_adversarial_mixing_controls_in_would_change_the_numbers():
    cells = _with_labels(_mimic_cells())
    truth = _truth(cells)
    mixed_b = [min(c["J"], 3) if c["A"] else min(c["J"], 1)
               for c in cells if c["variant"] == "B"]
    mixed_cov_b = 100.0 * sum(mixed_b) / (3 * len(mixed_b))
    assert abs(mixed_cov_b - truth["coverage"]["B"]) > 5.0
    assert truth["events"] >= 3 and truth["event_clusters"] >= 2


def test_controls_do_not_change_any_primary_statistic():
    all_cells = _with_labels(_mimic_cells(), control_a=1)
    primary_only = [c for c in all_cells if c["cell_kind"] == "primary"]
    truth = _truth(all_cells)
    mixed = _analyse_small([dict(c) for c in all_cells])
    clean = _analyse_small([dict(c) for c in primary_only])
    for v, expected in truth["coverage"].items():
        assert mixed["coverage_pct"][v] == pytest.approx(expected)
    for key in ("coverage_pct", "coverage_detail", "contrasts", "pi_hat"):
        assert mixed[key] == clean[key], key
    g1_mixed, g1_clean = (r["gates"]["G1_silent_over_credit"] for r in (mixed, clean))
    assert g1_mixed == g1_clean
    assert (g1_mixed["events"], g1_mixed["n_clusters"]) == (truth["event_clusters"],
                                                            truth["n_clusters"])
    assert mixed["pi_hat"]["events"] == truth["events"]
    assert mixed["pi_hat"]["n_cells"] == truth["n_cells"]
    assert mixed["analysis_population"]["control_cells_in_analyse_input"] == {
        "ablated_control": 4, "preserved_control": 2}
    assert mixed["analysis_population"]["n_primary_cells"] == truth["n_cells"]


def test_control_label_values_never_enter_a_statistic():
    base = _with_labels(_mimic_cells(), control_a=1)
    flipped = _with_labels(_mimic_cells(), control_a=0)
    a, b = _analyse_small(base), _analyse_small(flipped)
    for key in ("coverage_pct", "coverage_detail", "contrasts", "pi_hat", "gates", "n_used"):
        assert a[key] == b[key], key


def test_a_control_twin_cannot_overwrite_its_primary_cell_in_the_ab_pairing():
    """Regression for the dictionary-collision mechanism: with the control twin
    listed AFTER its primary cell and carrying L1* = 3, the A->B pairing used to
    pick up the twin instead of the primary cell."""
    cells = _with_labels(_mimic_cells())
    by = {(c["variant"], c["cq_id"]): c for c in cells if c["cell_kind"] == "primary"}
    expected = [
        (by[("B", q)]["J"] if by[("B", q)]["A"] else min(by[("B", q)]["J"], 1))
        - (by[("A", q)]["J"] if by[("A", q)]["A"] else min(by[("A", q)]["J"], 1))
        for q in sorted({c["cq_id"] for c in cells if c["variant"] == "A"
                         and c["cell_kind"] == "primary"})]
    res = _analyse_small(cells)
    assert res["contrasts"]["A->B"]["delta"] == pytest.approx(float(np.mean(expected)))
    assert res["contrasts"]["A->B"]["n_clusters"] == len(expected) == 9
    assert res["contrasts"]["A->B"]["n_questions"] == 9


def test_missing_cell_kind_is_primary_and_unknown_kind_is_an_error():
    cells = [{"cell_id": "x", "cq_id": "q", "cluster_id": "q", "variant": "A", "J": 3, "A": 1}]
    assert ah.split_primary_and_controls(cells)[0] == cells
    with pytest.raises(ValueError, match="unknown cell_kind"):
        ah.split_primary_and_controls([dict(cells[0], cell_kind="washout")])
    with pytest.raises(ValueError, match="unknown cell_kind"):
        ah.analyse([dict(cells[0], cell_kind="Primary ")], seed=1, bootstrap_resamples=20)


def test_duplicate_primary_cell_for_a_variant_and_cq_is_refused():
    cells = _with_labels(_mimic_cells())
    dup = dict(next(c for c in cells if c["cell_kind"] == "primary"), cell_id="dup")
    with pytest.raises(ValueError, match="more than one primary cell"):
        _analyse_small(cells + [dup])


def test_analysing_only_controls_is_an_error():
    controls = [c for c in _with_labels(_mimic_cells()) if c["cell_kind"] != "primary"]
    with pytest.raises(ValueError, match="no primary cells"):
        _analyse_small(controls)


def test_g3_with_controls_in_the_input_still_needs_the_flag_and_all_24():
    """Controls in the input are excluded from every statistic; G3 alone may use
    their A, and only under controls_valid (here 4 ablated cells, not 24)."""
    cells = _with_labels(_mimic_cells())
    default = _analyse_small(cells)["gates"]["G3_negative_control"]
    assert default["status"] == "not_computable"
    assert default["counts"]["ablated_control"]["n_in_run"] == 4
    valid = _analyse_small(cells, controls_valid=True)["gates"]["G3_negative_control"]
    assert valid["status"] == "not_computable" and "exactly 24" in valid["reason"]


# --- cell-level pi-hat ------------------------------------------------------
def _cluster_cells(per_cluster):
    """per_cluster: list of lists of (J, A); one cluster per list."""
    cells = []
    for ci, rows in enumerate(per_cluster):
        for k, (j, a) in enumerate(rows):
            cells.append({"cell_id": f"c{ci}-{k}", "cq_id": f"q{ci}", "cluster_id": f"c{ci}",
                          "variant": "ABCDEF"[k % 6], "J": j, "A": a})
    return cells


def test_pi_hat_is_cell_level_while_g1_counts_clusters():
    cells = _cluster_cells([
        [(3, 0), (3, 0), (2, 0)],   # one cluster, 3 event cells
        [(3, 1), (2, 0), (1, 0)],   # 1 event cell (J=1, A=0 is NOT an event)
        [(0, 0), (3, 1), (3, 1)],
        [(2, 1), (2, 1), (0, 1)],
        [(3, 1), (1, 1), (0, 0)],
    ])
    res = ah.silent_over_credit_rate(cells, B=300, seed=7)
    assert (res["events"], res["n_cells"]) == (4, 15)
    assert res["pi_hat"] == pytest.approx(4 / 15)
    assert (res["clusters_with_event"], res["n_clusters"]) == (2, 5)
    assert ah.silent_over_credit(cells) == (2, 5)  # G1 unit is unchanged
    assert res["ci_method"] == "BCa cluster bootstrap"
    assert 0.0 <= res["ci_lo"] <= res["ci_hi"] <= 1.0
    assert res["pi_hat_is_a_lower_bound"] is True


def test_pi_hat_with_zero_events_is_never_bootstrapped(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a zero-event proportion must not be bootstrapped")
    monkeypatch.setattr(ah, "cluster_bootstrap_stat", boom)
    cells = _cluster_cells([[(3, 1), (2, 1)], [(0, 0), (1, 0)], [(3, 1), (3, 1)]])
    res = ah.silent_over_credit_rate(cells, B=50, seed=1)
    assert res["events"] == 0 and res["pi_hat"] == 0.0
    assert res["ci_lo"] is None and res["ci_hi"] is None
    assert "zero observed events" in res["ci_reason"]


def test_zero_event_pi_hat_reports_the_clopper_pearson_cluster_bound():
    cells = [dict(c, A=1) for c in _with_labels(_mimic_cells()) if c["cell_kind"] == "primary"]
    res = _analyse_small(cells)
    assert res["pi_hat"]["events"] == 0
    n = res["gates"]["G1_silent_over_credit"]["n_clusters"]
    assert res["pi_hat"]["operative_upper_bound"] == pytest.approx(
        ah.clopper_pearson_upper(0, n, alpha=0.025))
    assert res["pi_hat"]["ci_lo"] is None


# --- G1: registered computation unchanged; achievability reported separately
def test_g1_is_unpassable_at_33_clusters_even_with_zero_events():
    diag = ah.g1_achievability(33, 0.025)
    assert diag["achievable"] is False
    assert diag["min_achievable_upper_bound"] == pytest.approx(1 - 0.025 ** (1 / 33))
    assert diag["min_achievable_upper_bound"] == pytest.approx(0.1058, abs=5e-4)
    assert diag["max_events_that_pass"] is None
    assert diag["min_clusters_for_zero_event_pass"] == 36
    assert diag["diagnostic_only"] is True and "unpassable" in diag["note"]


def test_g1_is_passable_at_36_clusters_only_with_zero_events():
    diag = ah.g1_achievability(36, 0.025)
    assert diag["achievable"] is True and diag["max_events_that_pass"] == 0
    assert diag["min_achievable_upper_bound"] == pytest.approx(0.0974, abs=5e-4)


def test_g1_achievability_depends_on_the_one_sided_level():
    """At n=33 the unresolved 95% vs 97.5% choice flips the outcome."""
    d95 = ah.g1_achievability(33, 0.05)
    assert d95["achievable"] is True and d95["max_events_that_pass"] == 0
    assert d95["min_achievable_upper_bound"] == pytest.approx(1 - 0.05 ** (1 / 33))
    assert d95["min_clusters_for_zero_event_pass"] == 29


def test_registered_g1_decision_is_not_altered_by_the_diagnostic():
    cells = [dict(c, A=1) for c in _with_labels(_mimic_cells()) if c["cell_kind"] == "primary"]
    # 12 clusters here; rebuild a 33-cluster, zero-event primary set instead
    cells = [{"cell_id": f"p{i}", "cq_id": f"q{i}", "cluster_id": f"q{i}", "variant": "B",
              "category": _CATS[i % 3], "J": 3, "A": 1} for i in range(33)]
    g1 = _analyse_small(cells)["gates"]["G1_silent_over_credit"]
    assert (g1["events"], g1["n_clusters"], g1["threshold"]) == (0, 33, 0.10)
    assert g1["upper_bound_one_sided"] == pytest.approx(ah.clopper_pearson_upper(0, 33, 0.025))
    assert g1["confidence_level_one_sided"] == pytest.approx(0.975)
    assert g1["status"] == "fail"  # registered computation kept
    assert g1["g1_achievable_at_registered_n"]["achievable"] is False
    g1_95 = ah.analyse(cells, 1, g1_alpha=0.05, bootstrap_resamples=SMALL_B)["gates"][
        "G1_silent_over_credit"]
    assert g1_95["status"] == "pass" and g1_95["g1_achievable_at_registered_n"]["achievable"]


# --- label ingestion on the real state (controls blank / mislabelled) -----
_SHEET_COLUMNS = ["cell_id", "cq_id", "cluster_id", "category", "variant",
                  "evidence_span_verbatim", "A", "rater_L1", "note"]


def _mimic_sheet_rows(cells, preserved_a=("1", "x")):
    """Primary rows labelled; ablated controls BLANK; preserved controls labelled
    (one with a malformed value, standing in for the display bug)."""
    rows, k = [], 0
    for c in cells:
        row = {key: c[key] for key in ("cell_id", "cq_id", "cluster_id", "category", "variant")}
        row["note"] = ""
        if c["cell_kind"] == "primary":
            a = _true_a(c["J"], c["cq_id"])
            row.update(A=str(a), rater_L1=str(c["J"] if a else min(c["J"], 1)))
        elif c["cell_kind"] == "ablated_control":
            row.update(A="", rater_L1="")
        else:
            row.update(A=preserved_a[k % len(preserved_a)], rater_L1="2")
            k += 1
        rows.append(row)
    return rows


def _write_sheet(path: Path, rows: list[dict]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_cells(path: Path, cells: list[dict]) -> Path:
    path.write_text("\n".join(_json.dumps(c) for c in cells) + "\n", encoding="utf-8")
    return path


def _control_ids(cells):
    return {c["cell_id"] for c in cells if c["cell_kind"] != "primary"}


def test_loader_tolerates_blank_and_malformed_control_rows_only_when_told_to(tmp_path):
    cells = _mimic_cells()
    sheet = _write_sheet(tmp_path / "labels.csv", _mimic_sheet_rows(cells))
    with pytest.raises(ValueError, match="blank|invalid"):
        ah.load_label_csv(sheet, label_source="human")
    ls = ah.load_label_csv(sheet, label_source="human", tolerate_ids=_control_ids(cells))
    assert ls.missing_a_ids == ()
    # presence only: both preserved rows have a non-blank A cell ("1" and "x");
    # no control VALUE is retained at all
    assert ls.tolerated_nonblank_ids == ("preserved_control:B:Q04", "preserved_control:B:Q05")
    assert all(ls.labels[cid] is None for cid in _control_ids(cells))
    assert all(ls.rater_l1[cid] is None for cid in _control_ids(cells))


def test_a_blank_primary_row_still_fails_even_when_controls_are_tolerated(tmp_path):
    cells = _mimic_cells()
    rows = _mimic_sheet_rows(cells)
    rows[0]["A"] = ""
    sheet = _write_sheet(tmp_path / "labels.csv", rows)
    with pytest.raises(ValueError, match=rows[0]["cell_id"]):
        ah.load_label_csv(sheet, label_source="human", tolerate_ids=_control_ids(cells))


def test_join_excludes_controls_and_reports_their_counts(tmp_path):
    cells = _mimic_cells()
    sheet = _write_sheet(tmp_path / "labels.csv", _mimic_sheet_rows(cells))
    ls = ah.load_label_csv(sheet, label_source="human", tolerate_ids=_control_ids(cells))
    scored, meta = ah.join_labels(cells, ls, exclude_controls=True)
    assert len(scored) == 21 and all(c["cell_kind"] == "primary" for c in scored)
    assert meta["mode"] == "complete" and meta["unlabeled_cells"] == 0
    assert (meta["total_cells"], meta["total_run_cells"], meta["labeled_cells"]) == (21, 27, 21)
    assert meta["control_cells"]["ablated_control"] == {
        "n_in_run": 4, "n_rows_in_label_csv": 4, "n_absent_from_label_csv": 0,
        "n_labeled_by_presence": 0, "n_unlabeled": 4}
    assert meta["control_cells"]["preserved_control"] == {
        "n_in_run": 2, "n_rows_in_label_csv": 2, "n_absent_from_label_csv": 0,
        "n_labeled_by_presence": 2, "n_unlabeled": 0}


def test_join_keeps_legacy_control_behaviour_by_default(tmp_path):
    """persona_pass.py joins without exclude_controls and expects control cells."""
    cells = _mimic_cells()
    rows = _mimic_sheet_rows(cells, preserved_a=("1", "0"))
    for row in rows:
        if row["A"] == "":
            row.update(A="1", rater_L1="3")
    ls = ah.load_label_csv(_write_sheet(tmp_path / "l.csv", rows), label_source="human")
    scored, meta = ah.join_labels(cells, ls)
    assert len(scored) == 27 and meta["total_cells"] == 27
    assert meta["controls_excluded_from_scored"] is False


def test_unlabelled_primary_rows_are_reported_not_silently_dropped(tmp_path):
    cells = _mimic_cells()
    rows = _mimic_sheet_rows(cells)
    blanked = [r["cell_id"] for r in rows[:2]]
    for r in rows[:2]:
        r["A"] = ""
    ids = _control_ids(cells)
    sheet = _write_sheet(tmp_path / "labels.csv", rows)
    with pytest.raises(ValueError, match=blanked[0]):
        ah.load_label_csv(sheet, label_source="human", tolerate_ids=ids)
    ls = ah.load_label_csv(sheet, label_source="human", tolerate_ids=ids, allow_partial=True)
    scored, meta = ah.join_labels(cells, ls, allow_partial=True, exclude_controls=True)
    assert meta["mode"] == "partial allowed"
    assert meta["unlabeled_cell_ids"] == sorted(blanked)
    assert meta["labeled_cells"] == len(scored) == 19 and meta["total_cells"] == 21
    res = _analyse_small(scored)
    assert res["n_used"]["primary_cells"] == 19
    assert sum(v["n_cells"] for v in res["n_used"]["coverage"].values()) == 19


def test_washout_qwk_drops_control_rows_and_says_how_many(tmp_path):
    cells = _mimic_cells()
    ids = _control_ids(cells)
    primary = ah.load_label_csv(
        _write_sheet(tmp_path / "p.csv", _mimic_sheet_rows(cells)),
        label_source="human", tolerate_ids=ids)
    prim_ids = [c["cell_id"] for c in cells if c["cell_kind"] == "primary"][:8]
    ctrl_ids = sorted(ids)[:2]
    keep = set(prim_ids) | set(ctrl_ids)
    rows = [dict(r, rater_L1=r["rater_L1"] or "") for r in _mimic_sheet_rows(cells)
            if r["cell_id"] in keep]
    washout = ah.load_label_csv(_write_sheet(tmp_path / "w.csv", rows),
                                label_source="human", tolerate_ids=ids)
    with pytest.raises(ValueError, match="rater_L1 is blank"):
        ah.washout_qwk(primary, washout)  # controls are NOT excluded by default
    res = ah.washout_qwk(primary, washout, exclude_ids=ids)
    assert res["n"] == 8 and res["n_control_excluded"] == 2
    assert res["intra_rater_qwk"] == pytest.approx(1.0)


# --- command line on the real-state mimic ---------------------------------
def _run_cli(ah_mod, argv, seed=20260913, partial=True):
    """Drive main().  ``partial`` appends --allow-partial: the synthetic fixtures are
    not the registered Q_v design (188 cells), which main() otherwise refuses."""
    old = sys.argv
    sys.argv = ["analyze_holdout.py", "--seed", str(seed), *argv,
                *(["--allow-partial"] if partial else [])]
    try:
        return ah_mod.main()
    finally:
        sys.argv = old


def _cli_fixture(tmp_path):
    cells = _mimic_cells()
    return (cells, _write_cells(tmp_path / "cells.jsonl", cells),
            _write_sheet(tmp_path / "labels.csv", _mimic_sheet_rows(cells)))


def test_cli_does_not_crash_on_the_real_state_and_reports_what_it_used(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    cells, cells_path, sheet = _cli_fixture(tmp_path)
    out = tmp_path / "res.json"
    assert _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                         "--out", str(out)]) == 0
    res = _json.loads(out.read_text())
    truth = _truth(cells)
    assert res["label_source"] == "human" and res["SIMULATED"] is False
    for v, expected in truth["coverage"].items():
        assert res["coverage_pct"][v] == pytest.approx(expected)
        assert res["n_used"]["coverage"][v]["n_cells"] == truth["n_by_variant"][v]
    assert res["n_used"]["primary_cells"] == 21
    assert res["pi_hat"]["events"] == truth["events"]
    assert res["gates"]["G1_silent_over_credit"]["events"] == truth["event_clusters"]
    ctrl = res["analysis_population"]["control_rows_in_label_join"]
    assert ctrl["ablated_control"]["n_in_run"] == 4 and ctrl["preserved_control"]["n_in_run"] == 2
    assert res["label_coverage"]["mode"] == "complete"
    assert res["label_coverage"]["controls_excluded_from_scored"] is True
    g3 = res["gates"]["G3_negative_control"]
    assert g3["status"] == "not_computable" and g3["reasons"]
    ab = g3["counts"]["ablated_control"]
    assert (ab["n_in_run"], ab["n_labeled_by_presence"], ab["n_unlabeled"]) == (4, 0, 4)
    assert g3["counts"]["preserved_control"]["n_labeled_by_presence"] == 2
    assert g3["counted_by"].startswith("presence")
    assert res["bootstrap"]["strata_key"] is None and res["bootstrap"]["seed_is_registered"]


def test_cli_stamps_provenance_hashes_of_the_label_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet = _cli_fixture(tmp_path)
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--out", str(out)])
    prov = _json.loads(out.read_text())["input_provenance"]
    assert prov["labels_csv"]["sha256"] == hashlib.sha256(sheet.read_bytes()).hexdigest()
    assert prov["cells_jsonl"]["sha256"] == hashlib.sha256(cells_path.read_bytes()).hexdigest()
    assert prov["analyzer_sha256"] == hashlib.sha256(
        Path(ah.__file__).read_bytes()).hexdigest()


def test_cli_blank_primary_row_is_a_label_validation_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    cells = _mimic_cells()
    rows = _mimic_sheet_rows(cells)
    rows[0]["A"] = ""
    cells_path = _write_cells(tmp_path / "cells.jsonl", cells)
    sheet = _write_sheet(tmp_path / "labels.csv", rows)
    with pytest.raises(SystemExit, match="label validation failed"):
        _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                      "--out", str(tmp_path / "o.json")], partial=False)


def test_cli_strata_option_is_opt_in_stamped_and_leaves_point_estimates_alone(
        tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", 300)
    _, cells_path, sheet = _cli_fixture(tmp_path)
    runs = {}
    for name in ("none", "category"):
        out = tmp_path / f"{name}.json"
        _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                      "--bootstrap-strata", name, "--out", str(out)])
        runs[name] = _json.loads(out.read_text())
    assert runs["none"]["bootstrap"]["strata_key"] is None
    assert runs["category"]["bootstrap"]["strata_key"] == "category"
    assert runs["category"]["bootstrap"]["registered_scheme"] is False
    assert runs["none"]["coverage_pct"] == runs["category"]["coverage_pct"]
    assert runs["none"]["pi_hat"]["pi_hat"] == runs["category"]["pi_hat"]["pi_hat"]
    ci = lambda r: (r["coverage_detail"]["B"]["ci_lo_pct"], r["coverage_detail"]["B"]["ci_hi_pct"])
    assert ci(runs["none"]) != ci(runs["category"])
    assert runs["category"]["coverage_detail"]["B"]["strata_sizes"] == {
        "catA": 4, "catB": 4, "catC": 4}
    assert runs["category"]["contrasts"]["A->B"]["strata_key"] == "category"


def test_cli_refuses_placeholder_cells_without_labels(tmp_path):
    cells = _mimic_cells()
    cells_path = _write_cells(tmp_path / "cells.jsonl", cells)
    with pytest.raises(SystemExit, match="placeholder A values"):
        _run_cli(ah, [str(cells_path), "--out", str(tmp_path / "o.json")])


def test_cli_warns_when_the_seed_is_not_the_registered_one(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet = _cli_fixture(tmp_path)
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--out", str(out)], seed=7)
    assert "not the registered seed" in capsys.readouterr().err
    assert _json.loads(out.read_text())["bootstrap"]["seed_is_registered"] is False


def test_cli_at_the_registered_resample_count_reports_the_registered_scheme(tmp_path):
    """No monkeypatching: B=10,000, seed 20260913, unstratified."""
    _, cells_path, sheet = _cli_fixture(tmp_path)
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--out", str(out)])
    boot = _json.loads(out.read_text())["bootstrap"]
    assert (boot["resamples"], boot["seed"], boot["strata_key"]) == (10_000, 20260913, None)
    assert boot["registered_scheme"] is True


def test_json_default_serialises_numpy_scalars():
    payload = {"a": np.bool_(True), "b": np.float64(1.5), "c": np.int64(3)}
    assert _json.loads(_json.dumps(payload, default=ah._json_default)) == {
        "a": True, "b": 1.5, "c": 3}
    with pytest.raises(TypeError):
        _json.dumps({"x": object()}, default=ah._json_default)


def test_g5_and_fragility_follow_the_strata_option():
    cells = _with_labels(_mimic_cells())
    for c in cells:
        c["rater_L1"] = c["J"]
    res = _analyse_small([c for c in cells], bootstrap_strata="category")
    assert res["bootstrap"]["strata_key"] == "category"
    g5 = res["gates"]["G5_mae_judge_human"]
    assert g5["strata_key"] == "category" and g5["n_cells"] == 21 and g5["n_clusters"] == 12
    assert res["gates"]["G6_consistency"]["status"] == "not_computable"
    assert res["contrasts"]["A->B"]["strata_key"] == "category"


def _with_gate_fields(cells: list[dict]) -> list[dict]:
    """Add the fields G5/G6 read.  Control rows are made ADVERSARIAL: if a
    control row leaked into any of these gates it would change the result."""
    out = []
    for c in cells:
        c = dict(c)
        primary = c["cell_kind"] == "primary"
        c.update(rater_L1=c["J"] if primary else 0, non_qwen_J=c["J"])
        out.append(c)
    return out


def test_every_gate_except_g3_ignores_control_rows(tmp_path):
    labelled = _with_gate_fields(_with_labels(_mimic_cells(), control_a=1))
    primary_only = [c for c in labelled if c["cell_kind"] == "primary"]
    # audit: well-behaved primary saves, ADVERSARIAL control saves (after the
    # boundary, 2 s dwell, re-saved) -- any leak into G7 would flip it
    lines = _primary_audit_lines(labelled) + [
        _audit_line(c["cell_id"], _ts(86400 + i), elapsed=2.0, edit_reason="x")
        for i, c in enumerate(labelled) if c["cell_kind"] != "primary"]
    kw = {"label_audit": _audit_from(lines, tmp_path), "unblind_boundary": BOUNDARY}
    mixed = _analyse_small([dict(c) for c in labelled], **kw)
    clean = _analyse_small([dict(c) for c in primary_only], **kw)
    for gate in ("G1_silent_over_credit", "G5_mae_judge_human", "G6_consistency",
                 "G7_audit_trail"):
        assert mixed["gates"][gate] == clean["gates"][gate], gate
    # the control saves (after the boundary, 2 s) would have failed G7 and the
    # control rater scores (0 vs J=3) would have failed G5 had they leaked
    assert mixed["gates"]["G7_audit_trail"]["status"] == "pass"
    assert mixed["gates"]["G5_mae_judge_human"]["status"] == "pass"
    assert mixed["gates"]["G5_mae_judge_human"]["n_cells"] == 21
    assert mixed["gates"]["G7_audit_trail"]["value"]["n_labeled_primary"] == 21


def test_blank_control_rows_are_not_reported_as_unlabeled_primary_cells(tmp_path):
    """allow_partial without tolerance puts blank control rows in missing_a_ids;
    the join must still keep them out of the unlabeled-PRIMARY accounting."""
    cells = _mimic_cells()
    sheet = _write_sheet(tmp_path / "labels.csv", _mimic_sheet_rows(cells, preserved_a=("1", "0")))
    ls = ah.load_label_csv(sheet, label_source="human", allow_partial=True)
    assert any(cid.startswith("ablated_control") for cid in ls.missing_a_ids)
    scored, meta = ah.join_labels(cells, ls, allow_partial=True, exclude_controls=True)
    assert meta["unlabeled_cells"] == 0 and meta["unlabeled_cell_ids"] == []
    assert meta["mode"] == "complete" and len(scored) == 21


def test_a_variant_with_a_single_cluster_gets_no_interval_but_no_crash():
    cells = [
        {"cell_id": "a0", "cq_id": "q0", "cluster_id": "q0", "variant": "A", "J": 3, "A": 1},
        {"cell_id": "b0", "cq_id": "q0", "cluster_id": "q0", "variant": "B", "J": 2, "A": 1},
        {"cell_id": "b1", "cq_id": "q1", "cluster_id": "q1", "variant": "B", "J": 1, "A": 0},
        {"cell_id": "b2", "cq_id": "q2", "cluster_id": "q2", "variant": "B", "J": 0, "A": 1},
    ]
    res = ah.analyse(cells, seed=3, bootstrap_resamples=50)
    assert res["coverage_detail"]["A"]["ci_lo_pct"] is None
    assert "fewer than two clusters" in res["coverage_detail"]["A"]["ci_reason"]
    assert res["coverage_detail"]["B"]["ci_lo_pct"] is not None
    assert "A->B" not in res["contrasts"]  # one paired cluster: nothing to resample


def test_stratified_bootstrap_reports_and_survives_a_single_cluster_stratum():
    """Variant A's 23 CQs split 6/6/2/2/1/6 over categories: a one-cluster
    stratum cannot vary, but must neither crash nor go unreported."""
    cells = _cells_in_strata({"slots_facets": 1, "methodology": 2, "taxonomy": 6})
    res = ah.cluster_bootstrap_stat(cells, _mean_v, "category", "cluster_id", B=200, seed=2)
    assert res["strata_sizes"] == {"methodology": 2, "slots_facets": 1, "taxonomy": 6}
    assert res["n_clusters"] == 9 and res["ci_lo"] <= res["estimate"] <= res["ci_hi"]


# ==========================================================================
# Round 2: G7 from the labeling audit, pooled G5, G3 counts, G1 levels,
# aggregates-only output, registered descriptive items.  SYNTHETIC DATA ONLY.
# ==========================================================================
import datetime as _dt  # noqa: E402
import re as _re  # noqa: E402

_JST = _dt.timezone(_dt.timedelta(hours=9))
_T0 = _dt.datetime(2026, 10, 8, 9, 0, 0, tzinfo=_JST)
BOUNDARY = "2026-10-09T00:00:00+09:00"  # == 2026-10-08T15:00:00Z


def _ts(seconds: int) -> str:
    """label_assist's now_iso() format: local offset, second resolution."""
    return (_T0 + _dt.timedelta(seconds=seconds)).isoformat(timespec="seconds")


def _audit_line(cell_id, ts, *, row=1, a=1, elapsed=30.0, session="s0", rater="2",
                edit_reason=None, draft=None):
    """One save record in label_assist's audit format.  ``A`` is an int, while
    ``rater_L1``, ``draft_A`` and ``draft_L1`` are STRINGS, as in the real file."""
    rec = {"ts": ts, "cell_id": cell_id, "row": row, "A": a, "span_chars": 12,
           "rater_L1": rater, "first_opened_ts": ts, "elapsed_s": elapsed,
           "session_id": session}
    if edit_reason is not None:
        rec["edit_reason"] = edit_reason
    if draft is not None:
        rec.update({"draft_A": draft.get("A"), "draft_L1": draft.get("L1", "2"),
                    "changed": draft.get("changed", False), "draft_model": "draft-model",
                    "draft_generated_at": ts})
    return _json.dumps(rec)


def _primary_audit_lines(cells, *, elapsed=30.0, per_session=8, step=90, draft=None):
    """One save per PRIMARY cell, in list order, all before BOUNDARY."""
    lines, i = [], 0
    for c in cells:
        if c["cell_kind"] != "primary":
            continue
        a = _true_a(c["J"], c["cq_id"])
        # the audit records what the label CSV holds: the cell's own rater_L1 if it
        # carries one, else the rule the sheet fixtures use
        rater = c["rater_L1"] if c.get("rater_L1") is not None else (c["J"] if a else min(c["J"], 1))
        lines.append(_audit_line(
            c["cell_id"], _ts(i * step), row=i + 1, a=a, elapsed=elapsed,
            session=f"s{i // per_session}", rater=str(rater),
            draft=draft(c) if draft else None))
        i += 1
    return lines


def _audit_from(lines, tmp_path, name="audit.jsonl"):
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ah.load_label_audit(path)


def _g7(primary, lines, tmp_path, boundary=BOUNDARY, detail=None):
    audit = _audit_from(lines, tmp_path) if lines is not None else None
    return ah._g7(primary, audit, boundary, detail)


def _labelled_primary():
    """Primary cells with the human A and rater_L1 the sheet fixtures would hold."""
    cells = [c for c in _with_labels(_mimic_cells()) if c["cell_kind"] == "primary"]
    for c in cells:
        c["rater_L1"] = c["J"] if c["A"] else min(c["J"], 1)
    return cells


# --- the audit parser ------------------------------------------------------
def test_audit_loader_reads_saves_events_and_the_string_int_mix(tmp_path):
    lines = [
        _json.dumps({"event": "session_start", "ts": _ts(0), "session_id": "s0"}),
        _audit_line("c1", _ts(10), a=0, session="s0", draft={"A": "1", "L1": "3",
                                                             "changed": True}),
        "this is not json",
        _json.dumps({"ts": "no-timezone", "cell_id": "c2", "A": 1}),   # unusable save
        _json.dumps({"ts": _ts(20), "something": "else"}),             # neither kind
        _json.dumps({"event": "session_end", "ts": _ts(30), "session_id": "s0"}),
    ]
    audit = _audit_from(lines, tmp_path)
    assert (audit.n_lines, audit.n_save_records, audit.n_event_records) == (6, 2, 2)
    assert audit.event_counts == {"session_end": 1, "session_start": 1}
    assert (audit.n_unparseable_lines, audit.n_save_records_unusable,
            audit.n_other_records) == (1, 1, 1)
    save = audit.saves["c1"][0]
    assert (save.a, save.draft_a, save.draft_l1, save.changed) == (0, 1, 3, True)
    assert isinstance(save.draft_a, int) and save.ts.utcoffset() == _dt.timedelta(0)
    assert audit.sha256 == hashlib.sha256((tmp_path / "audit.jsonl").read_bytes()).hexdigest()


def test_audit_loader_orders_saves_by_timestamp_then_file_order(tmp_path):
    lines = [_audit_line("c", _ts(300), a=1, edit_reason="late"),
             _audit_line("c", _ts(100), a=0)]
    saves = _audit_from(lines, tmp_path).saves["c"]
    assert [s.a for s in saves] == [0, 1] and saves[-1].has_edit_reason


# --- G7 --------------------------------------------------------------------
def test_g7_passes_when_all_three_conditions_hold(tmp_path):
    primary = _labelled_primary()
    gate = _g7(primary, _primary_audit_lines(primary), tmp_path)
    assert gate["status"] == "pass"
    assert gate["conditions"] == {"a_all_labeled_primary_saved_before_boundary": True,
                                  "b_no_primary_save_after_boundary": True,
                                  "c_elapsed_under_20s_share_below_3pct": True}
    v = gate["value"]
    assert (v["n_labeled_primary"], v["n_with_audit_record"], v["before_boundary_share"]) == (
        21, 21, 1.0)
    assert v["n_primary_saves_after_boundary"] == 0 and v["elapsed_under_20s_share"] == 0.0


def test_g7_a_label_with_no_audit_record_fails_condition_a(tmp_path):
    primary = _labelled_primary()
    sink: dict = {}
    gate = _g7(primary, _primary_audit_lines(primary)[1:], tmp_path, detail=sink)
    assert gate["status"] == "fail"
    assert gate["conditions"]["a_all_labeled_primary_saved_before_boundary"] is False
    assert gate["value"]["n_without_audit_record"] == 1
    assert gate["value"]["before_boundary_share"] == pytest.approx(20 / 21)
    assert sink["g7_cells_without_audit_record"] == [primary[0]["cell_id"]]


def test_g7_a_save_after_the_boundary_fails_and_resaves_are_reported(tmp_path):
    primary = _labelled_primary()
    lines = _primary_audit_lines(primary)
    victim = primary[3]["cell_id"]
    lines.append(_audit_line(victim, _ts(86400), edit_reason="post-hoc", a=primary[3]["A"],
                             rater=str(primary[3]["rater_L1"])))
    sink: dict = {}
    gate = _g7(primary, lines, tmp_path, detail=sink)
    assert gate["status"] == "fail"
    assert gate["conditions"]["b_no_primary_save_after_boundary"] is False
    assert gate["conditions"]["a_all_labeled_primary_saved_before_boundary"] is False
    v = gate["value"]
    assert v["n_primary_saves_after_boundary"] == 1 and v["n_cells_saved_after_boundary"] == 1
    assert v["n_cells_saved_more_than_once"] == 1 and v["n_cells_with_edit_reason_save"] == 1
    assert sink["g7_cells_saved_after_boundary"] == [victim]
    assert sink["g7_cells_saved_more_than_once"] == [victim]


def test_g7_resaves_before_the_boundary_are_reported_but_do_not_fail(tmp_path):
    primary = _labelled_primary()
    lines = _primary_audit_lines(primary)
    lines.append(_audit_line(primary[0]["cell_id"], _ts(5000), edit_reason="typo",
                             a=primary[0]["A"], rater=str(primary[0]["rater_L1"])))
    gate = _g7(primary, lines, tmp_path)
    assert gate["status"] == "pass"
    assert gate["value"]["n_cells_saved_more_than_once"] == 1
    assert gate["value"]["n_cells_with_edit_reason_save"] == 1


def test_g7_a_save_exactly_at_the_boundary_is_not_before_it(tmp_path):
    primary = _labelled_primary()
    lines = _primary_audit_lines(primary)
    lines[0] = _audit_line(primary[0]["cell_id"], "2026-10-09T00:00:00+09:00")
    gate = _g7(primary, lines, tmp_path)
    assert gate["status"] == "fail"
    assert gate["value"]["before_boundary_share"] == pytest.approx(20 / 21)
    assert gate["value"]["n_primary_saves_after_boundary"] == 1


def _hundred_primary_cells():
    # A=1 and rater_L1=2 match _audit_line's defaults (a=1, rater="2")
    return [{"cell_id": f"p{i}", "cell_kind": "primary", "cq_id": f"q{i}",
             "cluster_id": f"q{i}", "variant": "A", "J": 2, "A": 1, "rater_L1": 2}
            for i in range(100)]


@pytest.mark.parametrize("n_fast,expected", [(2, "pass"), (3, "fail")])
def test_g7_under_20s_share_must_be_below_three_percent(tmp_path, n_fast, expected):
    primary = _hundred_primary_cells()
    lines = [_audit_line(c["cell_id"], _ts(i * 60), row=i + 1,
                         elapsed=5.0 if i < n_fast else 45.0)
             for i, c in enumerate(primary)]
    gate = _g7(primary, lines, tmp_path)
    assert gate["status"] == expected  # 3/100 is NOT below 3%
    assert gate["value"]["n_under_20s"] == n_fast
    assert gate["conditions"]["c_elapsed_under_20s_share_below_3pct"] is (expected == "pass")


def test_g7_uses_the_last_save_for_the_timestamp_and_all_saves_for_dwell(tmp_path):
    primary = _hundred_primary_cells()
    lines = [_audit_line(c["cell_id"], _ts(i * 60), row=i + 1, elapsed=45.0)
             for i, c in enumerate(primary)]
    for i in range(5):  # first save fast, the stored (last) save deliberate
        lines.append(_audit_line(primary[i]["cell_id"], _ts(9000 + i), elapsed=60.0,
                                 edit_reason="reconsidered"))
        lines[i] = _audit_line(primary[i]["cell_id"], _ts(i * 60), elapsed=3.0)
    gate = _g7(primary, lines, tmp_path)
    assert gate["status"] == "pass" and gate["value"]["n_under_20s"] == 0


def test_g7_unknown_elapsed_is_not_computable_unless_already_failing(tmp_path):
    primary = _labelled_primary()
    lines = _primary_audit_lines(primary)
    rec = _json.loads(lines[0])
    rec["elapsed_s"] = None  # documented: None on a first save with no client timestamp
    lines[0] = _json.dumps(rec)
    gate = _g7(primary, lines, tmp_path)
    assert gate["status"] == "not_computable"
    assert gate["value"]["n_elapsed_unknown"] == 1
    assert "unknown total dwell" in gate["reason"]
    # one unknown dwell cannot rescue a share that is already at/over the limit
    many_fast = _primary_audit_lines(primary, elapsed=5.0)
    many_fast[0] = lines[0]
    assert _g7(primary, many_fast, tmp_path)["status"] == "fail"


def test_g7_needs_an_audit_and_an_explicit_offset_boundary(tmp_path):
    primary = _labelled_primary()
    none = ah._g7(primary, None, BOUNDARY)
    assert none["status"] == "not_computable" and "--label-audit" in none["reason"]
    lines = _primary_audit_lines(primary)
    absent = _g7(primary, lines, tmp_path, boundary=None)
    assert absent["status"] == "not_computable" and "--unblind-boundary" in absent["reason"]
    assert absent["value"]["elapsed_under_20s_share"] == 0.0  # parts that need no boundary
    naive = _g7(primary, lines, tmp_path, boundary="2026-10-09T00:00:00")
    assert naive["status"] == "not_computable" and "explicit UTC offset" in naive["reason"]


def test_g7_unreadable_audit_lines_prevent_a_pass(tmp_path):
    primary = _labelled_primary()
    lines = _primary_audit_lines(primary) + ["{broken"]
    gate = _g7(primary, lines, tmp_path)
    assert gate["status"] == "not_computable"
    assert "1 unparseable line" in gate["reason"]


def test_g7_ignores_control_saves_and_judge_run_telemetry(tmp_path):
    cells = _with_labels(_mimic_cells())
    primary = [c for c in cells if c["cell_kind"] == "primary"]
    for c in primary:  # the OLD G7 would have failed on every one of these
        c.update(started_at_utc="2026-09-21T05:00:00Z", elapsed_s=2.4, attempt=4,
                 artifact_digest="", rater_L1=c["J"] if c["A"] else min(c["J"], 1))
    lines = _primary_audit_lines(primary) + [
        _audit_line(c["cell_id"], _ts(86400 + i), elapsed=1.0, edit_reason="late")
        for i, c in enumerate(cells) if c["cell_kind"] != "primary"]
    audit = ah.audit_scope(_audit_from(lines, tmp_path), {c["cell_id"] for c in primary},
                           {c["cell_id"] for c in cells if c["cell_kind"] != "primary"},
                           {c["cell_id"] for c in cells})
    gate = ah._g7(primary, audit, BOUNDARY)
    assert gate["status"] == "pass"
    assert gate["value"]["audit"]["scope"] == {
        "n_cell_ids_in_audit": 27, "n_primary_cells_with_saves": 21,
        "n_control_cells_with_saves_ignored": 6, "n_cell_ids_not_in_run_ignored": 0}


def test_analyse_embeds_g7_and_counts_it_in_the_summary(tmp_path):
    primary = _labelled_primary()
    audit = _audit_from(_primary_audit_lines(primary), tmp_path)
    res = _analyse_small(primary, label_audit=audit, unblind_boundary=BOUNDARY)
    assert res["gates"]["G7_audit_trail"]["status"] == "pass"
    assert res["n_used"]["G7"] == {"n_cells": 21}
    assert res["gates_summary"]["passed"] >= 1


# --- G5: the interval bootstraps the SAME pooled statistic ------------------
def _unequal_cluster_cells():
    """Clusters of 1, 2, 6 cells with very different errors: the pooled mean of
    |J - H| differs from the mean of the per-cluster means."""
    spec = {"q0": [3], "q1": [0, 0], "q2": [2, 2, 2, 2, 2, 2], "q3": [1, 1], "q4": [0]}
    cells = []
    for cq, errs in spec.items():
        for k, e in enumerate(errs):
            cells.append({"cell_id": f"{cq}-{k}", "cq_id": cq, "cluster_id": cq,
                          "variant": "ABCDEF"[k], "category": "c", "J": 3,
                          "rater_L1": 3 - e, "A": 1})
    return cells


def test_g5_value_and_interval_describe_the_same_pooled_mean():
    cells = _unequal_cluster_cells()
    gate = ah._g5(cells, 20260913, None, 400)
    errs = [abs(c["J"] - c["rater_L1"]) for c in cells]
    pooled = float(np.mean(errs))
    cluster_means = float(np.mean([np.mean([abs(c["J"] - c["rater_L1"]) for c in cells
                                            if c["cq_id"] == q]) for q in
                                   {c["cq_id"] for c in cells}]))
    assert pooled != pytest.approx(cluster_means)  # the two statistics differ here
    assert gate["value"] == pooled
    direct = ah.cluster_bootstrap_stat(
        [{"cluster_id": c["cluster_id"], "err": e} for c, e in zip(cells, errs)],
        lambda rs: float(np.mean([r["err"] for r in rs])), None, "cluster_id", 400, 20260913)
    assert (gate["ci_lo"], gate["ci_hi"]) == (direct["ci_lo"], direct["ci_hi"])
    assert gate["estimator"] == "pooled mean of |J - rater_L1| over cells"
    assert (gate["n_cells"], gate["n_clusters"], gate["resamples"]) == (12, 5, 400)


def test_g5_compares_the_judge_J_with_the_human_rater_L1_only():
    """A and L1* must not feed G5: here A=0 (L1* = 1) while rater_L1 == J."""
    cells = [{"cell_id": f"c{i}", "cq_id": f"q{i}", "cluster_id": f"q{i}", "variant": "A",
              "J": 3, "A": 0, "rater_L1": 3, "L1_star": 1} for i in range(6)]
    gate = ah._g5(cells, 1, None, 100)
    assert gate["value"] == 0.0 and gate["status"] == "pass"
    assert (gate["judge_field"], gate["human_field"]) == ("J", "rater_L1")


def test_g5_missing_human_scores_are_counted_and_the_ids_stay_out_of_the_result():
    cells = _unequal_cluster_cells()
    del cells[0]["rater_L1"]
    sink: dict = {}
    gate = ah._g5(cells, 1, None, 50, sink)
    assert gate["status"] == "not_computable" and gate["n_missing_rater_L1"] == 1
    assert "missing_cell_ids" not in gate and sink["g5_cells_missing_rater_L1"] == ["q0-0"]


# --- fragility item 2 -------------------------------------------------------
def test_fragility_pi_interval_is_marked_not_implemented_with_reasons():
    res = _analyse_small(_labelled_primary())
    frag = res["fragility_pi_interval"]
    assert frag["status"] == "not_implemented"
    assert len(frag["reasons"]) == 3 and all(len(r) > 40 for r in frag["reasons"])
    assert "L574-584" in frag["registered_text"] and "item_1_a_to_b" in frag
    # item 1 (A->B) IS computed, inside G6; its CQ list is moved out of the result
    fragility = res["gates"]["G6_consistency"]["value"]["fragility"]
    assert "k" in fragility and "moved_cq_ids" not in fragility


# --- G3: not computable with explicit reasons and presence-only counts ------
def _real_shape_cells():
    """21 primary cells plus the registered control counts: 24 ablated + 12 preserved."""
    cells = _mimic_cells()[:21]
    for k in range(24):
        cells.append(_mk_cell(f"ablated_control:{'AB'[k // 12]}:Q{k % 12:02d}",
                              f"Q{k % 12:02d}", _CATS[(k % 12) // 4], "AB"[k // 12],
                              "ablated_control", 3))
    for k in range(12):
        cells.append(_mk_cell(f"preserved_control:{'AB'[k // 6]}:Q{k:02d}", f"Q{k:02d}",
                              _CATS[k // 4], "AB"[k // 6], "preserved_control", 3))
    return cells


def _real_shape_sheet(cells, tmp_path, values):
    """Primary rows labelled; 8 ablated + 4 preserved control rows carry a label
    cell whose content is taken from ``values`` (cycled); the other 24 are blank."""
    rows = _mimic_sheet_rows([c for c in cells if c["cell_kind"] == "primary"])
    seen = {"ablated_control": 0, "preserved_control": 0}
    quota = {"ablated_control": 8, "preserved_control": 4}
    for c in cells:
        if c["cell_kind"] == "primary":
            continue
        row = {key: c[key] for key in ("cell_id", "cq_id", "cluster_id", "category", "variant")}
        row.update(A="", rater_L1="", note="")
        if seen[c["cell_kind"]] < quota[c["cell_kind"]]:
            row["A"] = values[(sum(seen.values())) % len(values)]
            seen[c["cell_kind"]] += 1
        rows.append(row)
    return _write_sheet(tmp_path / "labels.csv", rows)


@pytest.mark.parametrize("values", [("1",), ("0", "1"), ("0",), ("x", "7", "1", "0", "yes")])
def test_g3_reports_the_real_state_counts_by_presence_never_by_value(tmp_path, values):
    cells = _real_shape_cells()
    sheet = _real_shape_sheet(cells, tmp_path, values)
    ids = _control_ids(cells)
    ls = ah.load_label_csv(sheet, label_source="human", tolerate_ids=ids)
    scored, meta = ah.join_labels(cells, ls, exclude_controls=True)
    res = _analyse_small(scored, label_metadata=meta)
    g3 = res["gates"]["G3_negative_control"]
    assert g3["status"] == "not_computable" and g3["counted_by"].startswith("presence")
    counts = g3["counts"]
    assert {k: counts["ablated_control"][k] for k in ("n_in_run", "n_labeled_by_presence",
                                                       "n_unlabeled")} == {
        "n_in_run": 24, "n_labeled_by_presence": 8, "n_unlabeled": 16}
    assert {k: counts["preserved_control"][k] for k in ("n_in_run", "n_labeled_by_presence",
                                                         "n_unlabeled")} == {
        "n_in_run": 12, "n_labeled_by_presence": 4, "n_unlabeled": 8}
    assert counts["all_controls"] == {"n_in_run": 36, "n_labeled_by_presence": 12,
                                      "n_unlabeled": 24}
    assert any("12 with a label cell" in reason and "24 unlabeled" in reason
               for reason in g3["reasons"])
    # no number anywhere depends on what the control cells contained: the same
    # run with every labelled control row set to "1" gives identical gates
    def gates_for(vals):
        sh = _real_shape_sheet(cells, tmp_path, vals)
        sc, mt = ah.join_labels(cells, ah.load_label_csv(
            sh, label_source="human", tolerate_ids=ids), exclude_controls=True)
        return _analyse_small(sc, label_metadata=mt)["gates"]

    assert gates_for(values) == gates_for(("1",))


# --- G1: both one-sided levels side by side, decision untouched -------------
def test_g1_shows_both_one_sided_levels_and_keeps_the_registered_decision():
    cells = [{"cell_id": f"p{i}", "cq_id": f"q{i}", "cluster_id": f"q{i}", "variant": "B",
              "J": 3, "A": 1} for i in range(33)]
    g1 = _analyse_small(cells)["gates"]["G1_silent_over_credit"]
    both = g1["upper_bound_both_levels"]
    assert both["level_status"] == "UNRESOLVED" and "L564" in both["note"]
    assert "L387-390" in both["note"]
    assert both["one_sided_97_5"]["upper_bound"] == pytest.approx(1 - 0.025 ** (1 / 33))
    assert both["one_sided_95"]["upper_bound"] == pytest.approx(1 - 0.05 ** (1 / 33))
    assert (both["one_sided_97_5"]["meets_threshold"], both["one_sided_95"]["meets_threshold"]) \
        == (False, True)
    # the registered decision is the one made at g1_alpha (default .025) and is unchanged
    assert g1["status"] == "fail" and g1["upper_bound_one_sided"] == pytest.approx(
        both["one_sided_97_5"]["upper_bound"])
    assert (both["one_sided_97_5"]["decides_g1"], both["one_sided_95"]["decides_g1"]) \
        == (True, False)
    g1_95 = ah.analyse(cells, 1, g1_alpha=0.05, bootstrap_resamples=SMALL_B)["gates"][
        "G1_silent_over_credit"]
    assert g1_95["status"] == "pass"
    assert g1_95["upper_bound_both_levels"]["one_sided_95"]["decides_g1"] is True
    assert g1_95["upper_bound_both_levels"]["one_sided_97_5"]["upper_bound"] == pytest.approx(
        both["one_sided_97_5"]["upper_bound"])


# --- item 8: which fields feed L1* -----------------------------------------
def test_l1_star_takes_a_from_the_human_label_not_the_cells_placeholder(tmp_path):
    """cells.jsonl carries a judge-run placeholder A (here the OPPOSITE of the human's)
    and the human's rater_L1; neither may leak into L1* = J if A==1 else min(J, 1)."""
    cells = [{"cell_id": f"c{i}", "cq_id": f"q{i}", "cluster_id": f"q{i}", "variant": "A",
              "cell_kind": "primary", "J": j, "A": 1 - human_a,
              "label_source": "pending human evidence"}
             for i, (j, human_a) in enumerate([(3, 0), (3, 1), (0, 0), (2, 1)])]
    rows = [{"cell_id": f"c{i}", "A": str(a), "rater_L1": "3"}
            for i, a in enumerate([0, 1, 0, 1])]
    sheet = _write_sheet(tmp_path / "l.csv", rows)
    scored, _ = ah.join_labels(cells, ah.load_label_csv(sheet, label_source="human"))
    assert [c["A"] for c in scored] == [0, 1, 0, 1]            # human A, not the placeholder
    assert [c["L1_star"] for c in scored] == [1, 3, 0, 2]      # 3 -> min(3,1); rater_L1=3 ignored


# --- aggregates only: identifiers and per-cell values stay out of the result --
def test_move_id_lists_replaces_any_ids_list_by_its_count_at_any_depth():
    node = {"a": {"x_ids": ["c1", "c2"], "keep": 3}, "rows": [{"y_ids": ["c3"]}],
            "n_z_ids": 5, "z_ids": 7}
    sink: dict = {}
    ah._move_id_lists(node, sink)
    assert node == {"a": {"keep": 3, "n_x_ids": 2}, "rows": [{"n_y_ids": 1}],
                    "n_z_ids": 5, "z_ids": 7}  # a non-list under *_ids is left alone
    assert sink == {"a.x_ids": ["c1", "c2"], "rows.y_ids": ["c3"]}


def test_find_cell_level_leaks_matches_whole_identifier_tokens_only():
    text = '{"k": "primary:A:Q00", "n": "Q001", "m": "xQ00", "ok": "Q01"}'
    # matches do not overlap: the "Q00" inside "primary:A:Q00" is part of the longer id
    assert ah.find_cell_level_leaks(text, ["primary:A:Q00", "Q00", "Q01"]) == [
        "Q01", "primary:A:Q00"]
    assert ah.find_cell_level_leaks('{"k": "A:Q00"}', ["primary:A:Q00", "Q00"]) == ["Q00"]
    assert ah.find_cell_level_leaks("{}", []) == []


def _engineered_ab_cells():
    """A scores 0, B scores 3 on every CQ: A->B is distinguishable, so the
    fragility analysis really moves CQs (and has ids to keep out of the result)."""
    cells = []
    for i in range(9):
        for v, j in (("A", 0), ("B", 3)):
            cells.append({"cell_id": f"p:{v}:{i}", "cq_id": f"Q{i:02d}", "cluster_id": f"Q{i:02d}",
                          "variant": v, "J": j, "A": 1, "category": "c"})
    return cells


def test_fragility_cq_ids_are_moved_out_of_the_main_result():
    sink: dict = {}
    res = ah.analyse(_engineered_ab_cells(), 3, bootstrap_resamples=120, cell_detail=sink)
    frag = res["gates"]["G6_consistency"]["value"]["fragility"]
    # every one-step demotion of the +3 deltas leaves A->B distinguishable, so K is
    # the documented lower bound n+1 and all 9 CQs were moved
    assert frag["lower_bound"] is True and frag["k"] == 10
    assert frag["n_moved_cq_ids"] == 9 and "moved_cq_ids" not in frag
    moved = sink["gates.G6_consistency.value.fragility.moved_cq_ids"]
    assert len(moved) == 9 and all(_re.fullmatch(r"Q\d\d", m) for m in moved)
    assert ah.find_cell_level_leaks(
        _json.dumps(res, default=ah._json_default),
        [c["cell_id"] for c in _engineered_ab_cells()]
        + [c["cq_id"] for c in _engineered_ab_cells()]) == []


def _cli_registered_fixture(tmp_path, spans=None, draft_rows=None):
    cells = _mimic_cells()
    cells_path = _write_cells(tmp_path / "cells.jsonl", cells)
    rows = _mimic_sheet_rows(cells)
    for r in rows:
        if spans and r["cell_id"] in spans:
            r["evidence_span_verbatim"] = spans[r["cell_id"]]
    sheet = _write_sheet(tmp_path / "labels.csv", rows)
    audit_path = tmp_path / "labels.csv.audit.jsonl"
    audit_path.write_text("\n".join(_primary_audit_lines(cells)) + "\n", encoding="utf-8")
    return cells, cells_path, sheet, audit_path


_REGISTERED_ARGS = ["--label-source", "human", "--unblind-boundary", BOUNDARY]


def test_main_results_are_aggregates_only_and_detail_goes_to_the_separate_file(
        tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    cells, cells_path, sheet, audit = _cli_registered_fixture(tmp_path)
    out, out_cells = tmp_path / "res.json", tmp_path / "per_cell.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-audit", str(audit),
                  *_REGISTERED_ARGS, "--out", str(out), "--out-cells", str(out_cells)])
    main_text = out.read_text()
    run_ids = [c["cell_id"] for c in cells] + [c["cq_id"] for c in cells]
    assert ah.find_cell_level_leaks(main_text, run_ids) == []
    for banned in ('"moved_cq_ids"', '"unlabeled_cell_ids"', '"missing_cell_ids"'):
        assert banned not in main_text  # the quoted KEYS (counts such as n_moved_cq_ids stay)
    res = _json.loads(main_text)
    assert res["output_policy"]["per_cell_detail"] == "written only to --out-cells"
    detail = _json.loads(out_cells.read_text())
    assert "sealed" in detail["WARNING"] and len(detail["primary_cells"]) == 21
    row = next(r for r in detail["primary_cells"] if r["cell_id"] == "primary:A:Q03")
    assert (row["J"], row["A"], row["L1_star"]) == (3, 0, 1)   # per-cell judge AND human values
    assert row["audit_n_saves"] == 1 and row["audit_elapsed_s"] == 30.0
    assert set(detail["id_lists"]) >= {"g7_cells_without_audit_record",
                                       "unlabeled_primary_cell_ids"}
    captured = capsys.readouterr()
    assert "primary:A:Q03" not in captured.out and "keep it sealed" in captured.err


def test_without_out_cells_no_per_cell_file_is_written(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet, audit = _cli_registered_fixture(tmp_path)
    before = set(tmp_path.iterdir())
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-audit", str(audit),
                  *_REGISTERED_ARGS, "--out", str(out)])
    assert set(tmp_path.iterdir()) - before == {out}
    assert _json.loads(out.read_text())["output_policy"]["per_cell_detail"] == "not written"


def test_unlabeled_primary_ids_are_kept_out_of_the_main_result(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    cells = _mimic_cells()
    cells_path = _write_cells(tmp_path / "cells.jsonl", cells)
    rows = _mimic_sheet_rows(cells)
    rows[0]["A"] = ""
    sheet = _write_sheet(tmp_path / "labels.csv", rows)
    out, out_cells = tmp_path / "res.json", tmp_path / "per_cell.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--allow-partial", "--out", str(out), "--out-cells", str(out_cells)])
    res = _json.loads(out.read_text())
    assert res["label_coverage"]["unlabeled_cells"] == 1
    assert rows[0]["cell_id"] not in out.read_text()
    assert _json.loads(out_cells.read_text())["id_lists"]["unlabeled_primary_cell_ids"] == [
        rows[0]["cell_id"]]


def test_cli_refuses_to_write_the_main_result_if_an_identifier_leaks(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet, audit = _cli_registered_fixture(tmp_path)
    real = ah.analyse

    def leaky(*args, **kwargs):
        res = real(*args, **kwargs)
        res["oops"] = {"which": "primary:A:Q00"}
        return res

    monkeypatch.setattr(ah, "analyse", leaky)
    out = tmp_path / "res.json"
    with pytest.raises(SystemExit, match="refusing to write the main results"):
        _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                      "--out", str(out)])
    assert not out.exists()


def test_cli_argument_validation_for_the_new_flags(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet, audit = _cli_registered_fixture(tmp_path)
    base = [str(cells_path), "--labels", str(sheet), "--label-source", "human"]
    with pytest.raises(SystemExit, match="requires --labels"):
        _run_cli(ah, [str(cells_path), "--label-audit", str(audit)])
    with pytest.raises(SystemExit, match="explicit UTC offset"):
        _run_cli(ah, [*base, "--unblind-boundary", "2026-10-09T00:00:00"])
    with pytest.raises(SystemExit, match="must differ"):
        _run_cli(ah, [*base, "--out", str(tmp_path / "x.json"),
                      "--out-cells", str(tmp_path / "x.json")])
    with pytest.raises(SystemExit, match="no label audit"):
        _run_cli(ah, [*base, "--label-audit", str(tmp_path / "missing.jsonl"),
                      "--out", str(tmp_path / "o.json")])


def test_cli_registered_run_computes_g7_and_the_descriptive_items(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet, audit = _cli_registered_fixture(tmp_path)
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-audit", str(audit),
                  *_REGISTERED_ARGS, "--out", str(out)])
    res = _json.loads(out.read_text())
    assert res["gates"]["G7_audit_trail"]["status"] == "pass"
    assert res["descriptive"]["order_drift"]["status"] == "computed"
    assert res["descriptive"]["ah_correction"]["status"] == "computed"   # draft_A absent -> 0 drafts
    assert res["descriptive"]["ah_correction"]["n_with_draft"] == 0
    prov = res["input_provenance"]
    assert prov["label_audit_jsonl"]["sha256"] == hashlib.sha256(audit.read_bytes()).hexdigest()
    assert prov["unblind_boundary"] == BOUNDARY


def test_cli_old_flag_name_is_an_alias_of_the_boundary(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet, audit = _cli_registered_fixture(tmp_path)
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--label-audit", str(audit), "--unblind-commit-time", BOUNDARY,
                  "--out", str(out)])
    assert _json.loads(out.read_text())["gates"]["G7_audit_trail"]["status"] == "pass"


def test_cli_without_an_audit_leaves_g7_and_order_drift_not_computable(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet, _ = _cli_registered_fixture(tmp_path)
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--out", str(out)])
    res = _json.loads(out.read_text())
    assert res["gates"]["G7_audit_trail"]["status"] == "not_computable"
    assert res["descriptive"]["order_drift"]["status"] == "not_computable"
    assert res["descriptive"]["ah_correction"]["status"] == "not_computable"


# --- registered descriptive item: order-drift diagnostic (PREREG L551) -------
def _drift_cells(n=21):
    """Labelled primary cells with NO judge score at all (a read of J would raise):
    A and rater_L1 fall after the 12th save, i.e. a planted drift."""
    return [{"cell_id": f"p{i:02d}", "cell_kind": "primary", "category": "c",
             "A": 1 if i < 12 else 0, "rater_L1": 3 if i < 12 else 1} for i in range(n)]


def _drift_audit(cells, tmp_path, *, per_session=8):
    lines = [_audit_line(c["cell_id"], _ts(i * 60), row=i + 1, session=f"s{i // per_session}")
             for i, c in enumerate(cells)]
    return _audit_from(lines, tmp_path), lines


def test_order_drift_describes_the_labels_by_save_order(tmp_path):
    cells = _drift_cells()
    audit, _ = _drift_audit(cells, tmp_path)
    out = ah.order_drift_diagnostic(cells, audit)
    assert out["status"] == "computed" and out["descriptive_only"] is True
    assert out["n_cells"] == 21 and out["n_primary_without_audit_record"] == 0
    assert "does not define it" in out["reading"] and "most literal" in out["reading"]
    a_values = [c["A"] for c in cells]
    rho = stats.spearmanr(range(1, 22), a_values).statistic
    assert out["spearman_rho"]["order_vs_A"] == pytest.approx(rho) and rho < -0.8
    assert out["spearman_rho"]["order_vs_rater_L1"] == pytest.approx(rho)  # same step shape
    # array_split(21, 5) -> sizes 5,4,4,4,4 over save order
    assert [b["n"] for b in out["by_order_quintile"]] == [5, 4, 4, 4, 4]
    assert [b["A_rate"] for b in out["by_order_quintile"]] == [1.0, 1.0, 0.75, 0.0, 0.0]
    assert [b["mean_rater_L1"] for b in out["by_order_quintile"]] == [3.0, 3.0, 2.5, 1.0, 1.0]
    assert [(s["n"], s["A_rate"]) for s in out["by_session"]] == [(8, 1.0), (8, 0.5), (5, 0.0)]
    assert [s["session_rank"] for s in out["by_session"]] == [1, 2, 3]


def test_order_drift_orders_by_the_last_save_of_a_cell(tmp_path):
    cells = _drift_cells()
    audit, lines = _drift_audit(cells, tmp_path)
    lines.append(_audit_line(cells[0]["cell_id"], _ts(99999), edit_reason="late edit"))
    audit = _audit_from(lines, tmp_path, "audit2.jsonl")
    out = ah.order_drift_diagnostic(cells, audit)
    # p00 (A=1) was last saved last, so it now sits in the final order position
    order = sorted(cells, key=lambda c: 99999 if c["cell_id"] == "p00" else
                   int(c["cell_id"][1:]) * 60)
    assert order[-1]["cell_id"] == "p00"
    expected_last_bin = [c["A"] for c in order[17:]]
    assert out["by_order_quintile"][-1]["A_rate"] == pytest.approx(
        sum(expected_last_bin) / len(expected_last_bin))
    assert out["spearman_rho"]["order_vs_A"] == pytest.approx(
        stats.spearmanr(range(1, 22), [c["A"] for c in order]).statistic)


def test_order_drift_without_an_audit_or_with_too_few_cells_is_not_computable(tmp_path):
    cells = _drift_cells()
    none = ah.order_drift_diagnostic(cells, None)
    assert none["status"] == "not_computable" and "--label-audit" in none["reason"]
    audit, _ = _drift_audit(cells[:3], tmp_path)
    few = ah.order_drift_diagnostic(cells[:3], audit)
    assert few["status"] == "not_computable" and few["n_cells"] == 3


def test_order_drift_constant_labels_give_no_rank_correlation(tmp_path):
    cells = [dict(c, A=1, rater_L1=2) for c in _drift_cells()]
    audit, _ = _drift_audit(cells, tmp_path)
    out = ah.order_drift_diagnostic(cells, audit)
    assert out["spearman_rho"] == {"order_vs_A": None, "order_vs_rater_L1": None}


# --- registered descriptive item: AH correction rate (PREREG sec.11) ---------
_X, _Y, _Z = "primary:B:Q05", "primary:A:Q03", "primary:B:Q10"


def _draft_a(cell) -> int:
    """The AI draft: equals the final human A except X (0 vs 1) and Y (1 vs 0)."""
    final = cell["A"]
    return {_X: 0, _Y: 1}.get(cell["cell_id"], final)


def _final_span(cell) -> str:
    if cell["A"] == 0:
        return ""  # label_assist clears the span when A=0
    return f"span {cell['cq_id']}" + (" (edited)" if cell["cell_id"] == _Z else "")


def _draft_span(cell) -> str:
    return f"span {cell['cq_id']}" if _draft_a(cell) == 1 else ""


def _ah_fixture(tmp_path, *, drop_audit_draft_for=(), file_a_override=None):
    primary = _labelled_primary()
    changed = {_X, _Y, _Z}
    lines = _primary_audit_lines(
        primary, draft=lambda c: None if c["cell_id"] in drop_audit_draft_for else
        {"A": str(_draft_a(c)), "L1": "2", "changed": c["cell_id"] in changed})
    audit = _audit_from(lines, tmp_path)
    path = tmp_path / "drafts.csv"
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cell_id", "A_draft", "rater_L1_draft", "span_draft", "note_draft",
                    "model", "generated_at"])
        for c in primary:
            a = (file_a_override or {}).get(c["cell_id"], _draft_a(c))
            w.writerow([c["cell_id"], a, 2, _draft_span(c), "n", "draft-model", _ts(0)])
    return (primary, ah.load_drafts_csv(path), audit,
            {c["cell_id"]: _final_span(c) for c in primary})


def test_ah_correction_rate_overall_by_category_and_span(tmp_path):
    primary, drafts, audit, spans = _ah_fixture(tmp_path)
    for c in primary:
        c.pop("J")  # the judge score must not be needed (and is not read)
    out = ah.ah_correction_rates(primary, drafts=drafts, audit=audit, label_spans=spans)
    assert out["status"] == "computed" and out["descriptive_only"] is True
    assert (out["n_primary_labeled"], out["n_with_draft"], out["n_without_draft"]) == (21, 21, 0)
    a = out["A_changed"]
    assert (a["n_A_changed"], a["A_1_to_0"], a["A_0_to_1"], a["A_kept"]) == (2, 1, 1, 19)
    assert a["share"] == pytest.approx(2 / 21)
    sp = out["span_edited"]
    assert (sp["n_compared"], sp["n_span_edited"]) == (21, 3)
    assert sp["share"] == pytest.approx(3 / 21)
    # 17 cells have final A=1; X had draft A=0, so 16 have draft A = final A = 1; only Z edited
    assert sp["among_A1_both"] == {"n": 16, "n_span_edited": 1, "share": pytest.approx(1 / 16)}
    assert out["any_field_changed_per_audit"] == {
        "n_with_flag": 21, "n_changed": 3, "share": pytest.approx(3 / 21)}
    assert out["by_category"] == {
        "catA": {"n_with_draft": 8, "A_changed_share": pytest.approx(1 / 8),
                 "span_edited_share": pytest.approx(1 / 8)},
        "catB": {"n_with_draft": 8, "A_changed_share": pytest.approx(1 / 8),
                 "span_edited_share": pytest.approx(1 / 8)},
        "catC": {"n_with_draft": 5, "A_changed_share": 0.0,
                 "span_edited_share": pytest.approx(1 / 5)}}
    assert out["draft_A_file_vs_audit_disagreements"] == 0 and out["draft_source"] == "draft file"


def test_ah_draft_a_string_in_the_audit_is_compared_as_an_int(tmp_path):
    """The audit stores draft_A as "0"/"1" and A as an int: a naive "1" != 1 would
    call every cell corrected."""
    primary, _, audit, _ = _ah_fixture(tmp_path)
    out = ah.ah_correction_rates(primary, audit=audit)
    assert out["draft_source"] == "audit draft_A"
    assert out["A_changed"]["n_A_changed"] == 2 and out["A_changed"]["n_with_draft"] == 21
    assert out["span_edited"]["status"] == "not_computable"
    assert "needs --drafts" in out["span_edited"]["reason"]
    assert all("span_edited_share" not in v for v in out["by_category"].values())


def test_ah_cells_without_any_draft_are_counted_and_excluded(tmp_path):
    drop = {_Z, "primary:A:Q00", "primary:B:Q00"}
    primary, drafts, audit, spans = _ah_fixture(tmp_path, drop_audit_draft_for=drop)
    drafts = {k: v for k, v in drafts.items() if k not in drop}
    sink: dict = {}
    out = ah.ah_correction_rates(primary, drafts=drafts, audit=audit, label_spans=spans,
                                 detail=sink)
    assert (out["n_with_draft"], out["n_without_draft"]) == (18, 3)
    assert out["A_changed"]["n_with_draft"] == 18 and out["span_edited"]["n_compared"] == 18
    assert sorted(sink["ah_cells_without_draft"]) == sorted(drop)
    assert set(sink["ah_per_cell"]) == {c["cell_id"] for c in primary} - drop


def test_ah_a_disagreement_between_the_draft_file_and_the_audit_is_counted(tmp_path):
    primary, drafts, audit, spans = _ah_fixture(
        tmp_path, file_a_override={"primary:A:Q00": 0})  # audit says draft_A=1 for this cell
    out = ah.ah_correction_rates(primary, drafts=drafts, audit=audit, label_spans=spans)
    assert out["draft_A_file_vs_audit_disagreements"] == 1
    assert out["A_changed"]["n_A_changed"] == 3  # the draft FILE wins (A=1 final vs 0)


def test_ah_without_drafts_or_audit_is_not_computable():
    out = ah.ah_correction_rates(_labelled_primary())
    assert out["status"] == "not_computable" and "--drafts" in out["reason"]


def test_cli_registered_run_with_drafts_reports_the_correction_rate(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    primary = _labelled_primary()
    spans = {c["cell_id"]: _final_span(c) for c in primary}
    cells, cells_path, sheet, audit_path = _cli_registered_fixture(tmp_path, spans=spans)
    changed = {_X, _Y, _Z}
    audit_path.write_text("\n".join(_primary_audit_lines(
        cells, draft=lambda c: {"A": str(_draft_a(dict(c, A=_true_a(c["J"], c["cq_id"])))),
                                "L1": "2", "changed": c["cell_id"] in changed})) + "\n")
    drafts_path = tmp_path / "drafts.csv"
    with drafts_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cell_id", "A_draft", "rater_L1_draft", "span_draft", "note_draft",
                    "model", "generated_at"])
        for c in primary:
            w.writerow([c["cell_id"], _draft_a(c), 2, _draft_span(c), "n", "m", _ts(0)])
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-audit", str(audit_path),
                  "--drafts", str(drafts_path), *_REGISTERED_ARGS, "--out", str(out)])
    res = _json.loads(out.read_text())
    ah_rates = res["descriptive"]["ah_correction"]
    assert ah_rates["A_changed"]["n_A_changed"] == 2 and ah_rates["span_edited"]["n_span_edited"] == 3
    assert res["input_provenance"]["drafts_csv"]["sha256"] == hashlib.sha256(
        drafts_path.read_bytes()).hexdigest()
    assert ah.find_cell_level_leaks(out.read_text(), [c["cell_id"] for c in cells]) == []


def test_cli_rejects_a_draft_file_with_the_wrong_header(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet, _ = _cli_registered_fixture(tmp_path)
    bad = tmp_path / "drafts.csv"
    bad.write_text("cell_id,A\nx,1\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="label validation failed"):
        _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                      "--drafts", str(bad), "--out", str(tmp_path / "o.json")])


# ==========================================================================
# Round 3: BCa tie rule, strict types, registered design, judge validity,
# Holm family, TOST level, G3 behind --controls-valid.  SYNTHETIC DATA ONLY.
# ==========================================================================
_REVIEWER_DELTAS = [0, 1, 2, 1, 0, -1, 1, 0, 1, 2, 0, 1, -1, 0, 1, 1, 0, 2, 1, 0, -1, 1, 0]


def _one_cell_per_cluster(values):
    return [{"cluster_id": f"c{i:02d}", "d": float(v)} for i, v in enumerate(values)]


def test_midrank_z0_is_scipys_percentile_of_score_mean():
    rng = np.random.default_rng(3)
    boot = rng.integers(0, 6, 5000) / 5.0  # a coarse grid: 17% of the mass sits on each value
    for theta in (0.0, 0.4, 0.8, 1.0):
        prop = stats.percentileofscore(boot, theta, kind="mean") / 100.0
        expected = stats.norm.ppf(min(max(prop, 1 / 5000), 1 - 1 / 5000))
        assert ah._bca_z0(theta, boot, "midrank") == pytest.approx(expected)
    strict = ah._bca_z0(0.4, boot, "strict")
    assert strict == pytest.approx(stats.norm.ppf(np.mean(boot < 0.4)))  # ties count as above
    assert strict < ah._bca_z0(0.4, boot, "midrank")


def test_midrank_ties_use_a_float_tolerance():
    boot = np.array([0.3, 0.3 + 5e-16, 0.3 - 5e-16, 0.5, 0.1])
    # three replicates are 'equal' to theta=0.3 up to rounding: half of them count as below
    assert ah._bca_z0(0.3, boot, "midrank") == pytest.approx(stats.norm.ppf((1 + 4) / 10))


def test_an_unknown_tie_rule_is_an_error_everywhere():
    cells = _one_cell_per_cluster([0, 1, 2, 1])
    with pytest.raises(ValueError, match="ties must be one of"):
        ah._bca_z0(0.5, [0.1, 0.9], "loose")
    with pytest.raises(ValueError, match="ties must be one of"):
        ah.cluster_bootstrap_stat(cells, ah._mean_d, None, "cluster_id", 20, 1, "loose")
    with pytest.raises(ValueError, match="bca_ties must be one of"):
        ah.analyse(_labelled_primary(), 1, bootstrap_resamples=20, bca_ties="loose")


def test_midrank_bca_matches_scipy_on_the_reviewers_dataset():
    """23 per-CQ deltas, one cell per cluster.  Strict z0 gave [0.087, 0.826]; scipy's
    BCa gives ~[0.17, 0.87].  The statistic lives on a 1/23 grid, so agreement is asked
    to within one grid step (Monte-Carlo noise moves a quantile by one step)."""
    data = np.array(_REVIEWER_DELTAS, dtype=float)
    cells = _one_cell_per_cluster(_REVIEWER_DELTAS)
    mine = ah.cluster_bootstrap_stat(cells, ah._mean_d, None, "cluster_id", 10_000, 20260913)
    sci = stats.bootstrap((data,), np.mean, method="BCa", n_resamples=10_000,
                          random_state=0, confidence_level=0.95).confidence_interval
    grid = 1 / 23
    assert mine["bca_ties"] == "midrank"
    assert abs(mine["ci_lo"] - sci.low) <= grid + 1e-9
    assert abs(mine["ci_hi"] - sci.high) <= grid + 1e-9
    strict = ah.cluster_bootstrap_stat(cells, ah._mean_d, None, "cluster_id", 10_000,
                                       20260913, "strict")
    assert (strict["ci_lo"], strict["ci_hi"]) == pytest.approx((0.087, 0.826), abs=0.002)
    assert abs(strict["ci_lo"] - sci.low) > grid  # the strict rule misses scipy's lower end
    assert 0.05 < mine["tie_share"] < 0.20  # the 5-20% of replicates tied with theta-hat


def test_midrank_restores_coverage_on_a_coarse_grid():
    """Rare binary events (n=33, p=.10) sit on a coarse grid.  The strict rule
    under-covered (~84-85% for a nominal 95%); the mid-rank rule is near nominal."""
    n, nsim, B, truth = 33, 300, 1000, 0.10
    hits = {"strict": 0, "midrank": 0}
    for sim in range(nsim):
        rng = np.random.default_rng(1000 + sim)
        x = (rng.random(n) < truth).astype(float)
        boot = x[rng.integers(0, n, (B, n))].mean(axis=1)
        jack = np.array([np.delete(x, k).mean() for k in range(n)])
        for ties in hits:
            lo, hi = ah._bca_interval(x.mean(), boot, jack, 0.05, ties)
            hits[ties] += lo <= truth <= hi
    strict, mid = hits["strict"] / nsim, hits["midrank"] / nsim
    assert strict < 0.90 and mid > 0.90 and mid - strict > 0.05


def _all_gates_cells():
    """A->B distinguishable (so fragility bootstraps), some silent over-credit
    (so pi-hat bootstraps) and a human rater_L1 (so G5 bootstraps)."""
    cells = _engineered_ab_cells()
    for i, c in enumerate(cells):
        c["rater_L1"] = c["J"] if i % 4 else max(0, c["J"] - 1)
    cells[1]["A"] = 0
    cells[3]["A"] = 0  # J=3 with A=0: silent over-credit events in two clusters
    return cells


@pytest.mark.parametrize("ties", ["midrank", "strict"])
def test_the_tie_rule_reaches_every_bca_interval(monkeypatch, ties):
    seen = []
    real = ah._bca_interval

    def spy(theta, boot, jack, alpha=0.05, ties=ah.DEFAULT_BCA_TIES):
        seen.append(ties)
        return real(theta, boot, jack, alpha, ties)

    monkeypatch.setattr(ah, "_bca_interval", spy)
    res = ah.analyse(_all_gates_cells(), 7, bootstrap_resamples=60, bca_ties=ties)
    # coverage (x1 variant... x2) + contrast + pi-hat + G5 + fragility, two levels each
    assert len(seen) >= 10 and set(seen) == {ties}
    assert res["bootstrap"]["bca_ties"] == ties
    assert res["contrasts"]["A->B"]["bca_ties"] == ties
    assert res["pi_hat"]["bca_ties"] == ties and res["gates"]["G5_mae_judge_human"]["bca_ties"] == ties


def test_cli_bca_ties_default_is_midrank_and_strict_is_a_stamped_sensitivity(tmp_path, monkeypatch):
    _, cells_path, sheet, _ = _cli_registered_fixture(tmp_path)
    base = [str(cells_path), "--labels", str(sheet), "--label-source", "human"]
    out_mid, out_strict = tmp_path / "mid.json", tmp_path / "strict.json"
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _run_cli(ah, [*base, "--out", str(out_mid)])
    _run_cli(ah, [*base, "--bca-ties", "strict", "--out", str(out_strict)])
    mid, strict = (_json.loads(o.read_text()) for o in (out_mid, out_strict))
    assert mid["bootstrap"]["bca_ties"] == "midrank" and strict["bootstrap"]["bca_ties"] == "strict"
    assert strict["bootstrap"]["registered_scheme"] is False
    assert mid["coverage_pct"] == strict["coverage_pct"]  # point estimates never depend on it


# --- item 7: strict types -----------------------------------------------------
@pytest.mark.parametrize("bad_a", [True, False, 1.0, 0.0, "1", "0", None, np.int64(1), 2, -1])
def test_demote_rejects_every_a_that_is_not_the_int_0_or_1(bad_a):
    with pytest.raises(ValueError, match="A must be the int 0 or 1"):
        ah.demote(2, bad_a)


@pytest.mark.parametrize("bad_j", [True, 2.0, "2", None, np.int64(2), 4, -1])
def test_demote_rejects_every_j_that_is_not_an_int_0_to_3(bad_j):
    with pytest.raises(ValueError, match="J must be an int in 0..3"):
        ah.demote(bad_j, 1)


def test_silent_over_credit_validates_both_values_even_when_j_is_low():
    with pytest.raises(ValueError, match="A must be"):
        ah.silent_over_credit([{"cluster_id": "c", "J": 0, "A": "0"}])
    with pytest.raises(ValueError, match="J must be"):
        ah.silent_over_credit([{"cluster_id": "c", "J": 2.0, "A": 0}])
    with pytest.raises(ValueError, match="A must be"):
        ah.silent_over_credit([{"cluster_id": "c", "J": 3, "A": True}])


def _jsonl(path, rows):
    path.write_text("\n".join(_json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


@pytest.mark.parametrize("bad", [2.0, "2", None, True, 5])
def test_load_cells_requires_an_int_j_on_primary_cells(tmp_path, bad):
    path = _jsonl(tmp_path / "c.jsonl", [{"cell_id": "c1", "cq_id": "q", "cluster_id": "q",
                                           "variant": "A", "J": bad}])
    with pytest.raises(ValueError, match="J in cell record 0"):
        ah.load_cells(path, require_a=False)


def test_load_cells_never_reads_a_of_controls_or_of_placeholders_when_labels_supply_a(tmp_path):
    rows = [{"cell_id": "p", "cq_id": "q1", "cluster_id": "q1", "variant": "A", "J": 3,
             "A": "garbage"},                                      # placeholder; labels supply A
            {"cell_id": "c", "cq_id": "q2", "cluster_id": "q2", "variant": "A", "J": None,
             "A": None, "cell_kind": "ablated_control"}]            # a control: not read at all
    path = _jsonl(tmp_path / "c.jsonl", rows)
    cells = ah.load_cells(path, require_a=False)
    assert "L1_star" not in cells[0] and "L1_star" not in cells[1]
    with pytest.raises(ValueError, match="A in cell record 0"):     # a PRIMARY A is read strictly
        ah.load_cells(path, require_a=True)
    rows[0]["A"] = 1
    cells = ah.load_cells(_jsonl(tmp_path / "d.jsonl", rows), require_a=True)
    assert cells[0]["L1_star"] == 3 and "L1_star" not in cells[1]


def test_join_refuses_a_label_that_is_not_the_int_0_or_1(tmp_path):
    cells = [{"cell_id": "c1", "cq_id": "q1", "cluster_id": "q1", "variant": "A", "J": 3}]
    ls = ah.LabelSet(path=tmp_path / "x.csv", labels={"c1": True}, rater_l1={"c1": None},
                     source="human", simulated=False, missing_a_ids=())
    with pytest.raises(ValueError, match="A of 'c1' must be the int 0 or 1"):
        ah.join_labels(cells, ls)


def test_analyse_never_reads_a_control_cells_a_or_j():
    cells = _with_labels(_mimic_cells())
    for c in cells:
        if c["cell_kind"] != "primary":
            c["A"], c["J"] = "garbage", None
    _analyse_small(cells)  # raises if any control value were read
    with pytest.raises(ValueError, match="A of"):
        _analyse_small(cells, controls_valid=True)  # only the G3 opt-in reads a control A


@pytest.mark.parametrize("bad", ["2.0", "+2", "²", "٢", " 2x", "4", "-1"])
def test_label_csv_rater_l1_must_be_exactly_0_to_3(tmp_path, bad):
    path = _write_label_csv(tmp_path / "l.csv", [{"cell_id": "c1", "A": "1", "rater_L1": bad}],
                            source="human")
    with pytest.raises(ValueError, match="rater_L1 must be exactly one of 0,1,2,3"):
        ah.load_label_csv(path)


def test_audit_digit_strings_outside_the_allowed_set_are_dropped_not_crashed():
    assert ah._small_int("²", {0, 1, 2, 3}) is None   # '²'.isdigit() is True
    assert ah._small_int("1", {0, 1}) == 1 and ah._small_int(" 0 ", {0, 1}) == 0
    assert ah._small_int(True, {0, 1}) is None and ah._small_int("2", {0, 1}) is None


# --- round-2 gap: a label with no audit record fails G7 even without a boundary -----
def test_g7_label_with_no_audit_record_fails_even_when_the_boundary_is_unknown(tmp_path):
    primary = _labelled_primary()
    gate = _g7(primary, _primary_audit_lines(primary)[1:], tmp_path, boundary=None)
    assert gate["status"] == "fail"
    assert gate["conditions"]["a_all_labeled_primary_saved_before_boundary"] is False
    assert gate["conditions"]["b_no_primary_save_after_boundary"] is None


# --- B2: invalid judge calls ---------------------------------------------------
def _judge_cells():
    return [{"cell_id": f"primary:{v}:{i}", "cell_kind": "primary", "variant": v,
             "cq_id": f"q{i}", "cluster_id": f"q{i}", "J": 2, "judge_response_parsed": True,
             "judge_response": {"score": 2, "evidence": "x"}}
            for v in "AB" for i in range(3)]


@pytest.mark.parametrize("mutate", [
    lambda c: c.update(judge_response_parsed=False, J=0),
    lambda c: c.update(judge_response_parsed="true"),   # not the bool True
    lambda c: c.update(judge_response_parsed=None),
    lambda c: c.update(judge_response_parsed=1),
    lambda c: c.update(judge_response={"_error": "HTTPError 429"}),
    lambda c: c.update(_error="boom"),
])
def test_an_invalid_judge_call_is_detected(mutate):
    cell = _judge_cells()[0]
    assert not ah._judge_call_invalid(cell)
    mutate(cell)
    assert ah._judge_call_invalid(cell)


def test_a_cell_without_any_judge_flag_is_taken_as_valid():
    assert not ah._judge_call_invalid({"J": 2})


def test_judge_validity_counts_primary_cells_per_variant_and_ignores_controls():
    cells = _judge_cells()
    cells[0]["judge_response_parsed"] = False
    cells[4]["judge_response"] = {"_error": "x"}
    control = {"cell_id": "ablated_control:A:0", "cell_kind": "ablated_control",
               "variant": "A", "judge_response_parsed": False}
    assert ah.judge_validity(cells + [control]) == {
        "n_primary": 6, "n_invalid": 2,
        "by_variant": {"A": {"n_primary": 3, "n_invalid": 1},
                       "B": {"n_primary": 3, "n_invalid": 1}}}


def _cli_with_invalid_judge(tmp_path):
    cells = _mimic_cells()
    for c in cells:
        c["judge_response_parsed"] = True
    cells[0].update(judge_response_parsed=False, judge_response={"_error": "HTTPError 429"})
    cells_path = _write_cells(tmp_path / "cells.jsonl", cells)
    sheet = _write_sheet(tmp_path / "labels.csv", _mimic_sheet_rows(cells))
    return cells, cells_path, sheet


def test_cli_refuses_a_run_with_invalid_judge_calls_and_reports_them_per_variant(
        tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet = _cli_with_invalid_judge(tmp_path)
    out = tmp_path / "res.json"
    with pytest.raises(SystemExit, match=r"1 of 21 primary cells have an invalid judge call"):
        _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                      "--out", str(out)])
    assert not out.exists()


def test_cli_allow_invalid_judge_proceeds_but_stamps_and_warns(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet = _cli_with_invalid_judge(tmp_path)
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--allow-invalid-judge", "--out", str(out)])
    jv = _json.loads(out.read_text())["judge_validity"]
    assert jv["n_invalid"] == 1 and jv["allow_invalid_judge"] is True
    assert jv["invalid_cells_included"] is True
    assert jv["by_variant"]["A"] == {"n_primary": 9, "n_invalid": 1}
    assert "analysed as recorded (J=0)" in capsys.readouterr().err


def test_cli_clean_judge_run_reports_zero_invalid(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    cells = _mimic_cells()
    for c in cells:
        c["judge_response_parsed"] = True
    cells_path = _write_cells(tmp_path / "cells.jsonl", cells)
    sheet = _write_sheet(tmp_path / "labels.csv", _mimic_sheet_rows(cells))
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--out", str(out)])
    jv = _json.loads(out.read_text())["judge_validity"]
    assert (jv["n_primary"], jv["n_invalid"], jv["invalid_cells_included"]) == (21, 0, False)


# --- items 3 and 6: Holm family and the TOST level -------------------------------
def test_holm_family_of_two_with_a_single_computable_member():
    assert ah.holm({"A->B": 0.01}, m=2)["A->B"] == pytest.approx(0.02)
    assert ah.holm({"A->B": 0.6}, m=2)["A->B"] == 1.0
    assert ah.holm({"A->B": 0.01}) == {"A->B": pytest.approx(0.01)}   # default: family = given
    both = ah.holm({"A->B": 0.01, "B->Bprime": 0.04}, m=2)
    assert both == {"A->B": pytest.approx(0.02), "B->Bprime": pytest.approx(0.04)}
    with pytest.raises(ValueError, match="smaller than"):
        ah.holm({"a": 0.1, "b": 0.2}, m=1)


def test_analyse_keeps_the_missing_contrast_in_the_registered_holm_family():
    res = ah.analyse(_engineered_ab_cells(), 3, bootstrap_resamples=120)
    contrast, family = res["contrasts"]["A->B"], res["contrasts_family"]
    p = contrast["wilcoxon"]["p"]
    assert p is not None and p < 0.5
    assert contrast["p_holm"] == pytest.approx(min(1.0, 2 * p))        # m = 2, not 1
    assert family["registered_m"] == 2
    assert family["members"]["B->Bprime"] == {
        "status": "not_computable", "reason": "variant(s) ['Bprime'] absent from this run"}
    assert family["members"]["A->B"] == {"status": "computed", "p": p, "p_holm": contrast["p_holm"]}
    assert "m=2" in res["contrasts_note"] and "min(1, 2p)" in res["contrasts_note"]
    assert "only" not in res["contrasts_note"].split("m=2")[0]          # the old wording is gone


def test_both_confirmatory_contrasts_computable_gives_the_standard_holm():
    cells = _engineered_ab_cells()
    for i in range(9):  # a B' variant that is a small, noisy step from B
        cells.append({"cell_id": f"p:Bprime:{i}", "cq_id": f"Q{i:02d}", "cluster_id": f"Q{i:02d}",
                      "variant": "Bprime", "J": 2 if i % 2 else 3, "A": 1, "category": "c"})
    res = ah.analyse(cells, 3, bootstrap_resamples=120)
    fam = res["contrasts_family"]["members"]
    assert fam["A->B"]["status"] == fam["B->Bprime"]["status"] == "computed"
    ps = {k: v["p"] for k, v in fam.items()}
    lo, hi = sorted(ps, key=ps.get)
    assert fam[lo]["p_holm"] == pytest.approx(min(1.0, 2 * ps[lo]))
    assert fam[hi]["p_holm"] == pytest.approx(max(fam[lo]["p_holm"], min(1.0, ps[hi])))


def test_tost_uses_the_90_percent_interval_for_equivalence_and_the_95_for_resolved():
    assert ah.tost_decision(-0.1, 0.35) == "unresolved"                     # one interval only
    assert ah.tost_decision(-0.1, 0.35, eq_lo=-0.08, eq_hi=0.28) == "equivalent"
    assert ah.tost_decision(-0.1, 0.35, eq_lo=-0.08, eq_hi=0.31) == "unresolved"
    assert ah.tost_decision(0.05, 0.4, eq_lo=0.08, eq_hi=0.28) == "resolved"  # resolved wins
    assert ah.tost_decision(-0.29, 0.29) == "equivalent"                      # legacy call


def test_the_contrast_decision_is_made_on_the_registered_90_percent_interval():
    res = ah.analyse(_engineered_ab_cells(), 3, bootstrap_resamples=200)
    c = res["contrasts"]["A->B"]
    eq = c["equivalence_interval"]
    assert (eq["level"], eq["margin"]) == (0.90, 0.30)
    assert eq["ci_hi"] - eq["ci_lo"] <= c["ci_hi"] - c["ci_lo"] + 1e-12     # narrower than 95%
    assert c["decision"] == ah.tost_decision(c["ci_lo"], c["ci_hi"],
                                             eq_lo=eq["ci_lo"], eq_hi=eq["ci_hi"])
    assert "L2205" in eq["basis"] and "L306" in eq["basis"]
    assert res["bootstrap"]["equivalence_ci_level"] == 0.90 and res["bootstrap"]["resolved_ci_level"] == 0.95


# --- the two decisions that the tie rule and the TOST level actually move -------
_K_FLIP_A = [1, 0, 1, 0, 3, 2, 1, 0, 3, 2, 3, 2, 3, 3, 2, 1, 3, 1, 3, 1, 0, 0, 1]
_K_FLIP_B = [2, 0, 2, 0, 3, 2, 2, 0, 3, 3, 3, 3, 3, 3, 3, 0, 3, 1, 3, 2, 1, 2, 2]
_TOST_DELTAS = [0, 0, 1, 0, 0, 0, 0, 1, -1, 0, -1, -1, 0, 0, 0, 0, -1, 0, 0, 0, -1, 0, -1, 0,
                0, 0, 0, 0, 1, 0, 0, -1, 0]


def test_the_tie_rule_moves_fragility_k_across_the_registered_line():
    """23 CQs: with the strict z0 the A->B interval loses zero-exclusion after 5 CQ
    moves (K=5 < 6, G6 'fragile'); with the mid-rank z0 after 6 (K=6, G6 holds)."""
    cells = []
    for i, (a, b) in enumerate(zip(_K_FLIP_A, _K_FLIP_B)):
        for v, score in (("A", a), ("B", b)):
            cells.append({"variant": v, "cq_id": f"Q{i:02d}", "cluster_id": f"Q{i:02d}",
                          "L1_star": score})
    strict = ah.fragility_k(cells, seed=20260913, resamples=1000, ties="strict")
    mid = ah.fragility_k(cells, seed=20260913, resamples=1000, ties="midrank")
    assert (strict["k"], mid["k"]) == (5, 6)
    assert strict["k"] < 6 <= mid["k"]


def test_the_90_percent_tost_interval_can_declare_equivalence_the_95_percent_one_refuses():
    """33 per-CQ deltas on the {-1,0,1} grid: the 95% interval reaches -0.303 (outside
    the +-0.30 margin) while the registered TOST (alpha=.05 per side = 90%) interval is inside."""
    cells = _one_cell_per_cluster(_TOST_DELTAS)
    r = ah.cluster_bootstrap_stat(cells, ah._mean_d, None, "cluster_id", 1500, 20260913)
    assert r["ci_lo"] < -0.30 and r["ci_hi"] < 0.30                 # 95%: pokes out of the margin
    assert r["ci90_lo"] > -0.30 and r["ci90_hi"] < 0.30             # 90%: wholly inside
    assert ah.tost_decision(r["ci_lo"], r["ci_hi"]) == "unresolved"
    assert ah.tost_decision(r["ci_lo"], r["ci_hi"], eq_lo=r["ci90_lo"],
                            eq_hi=r["ci90_hi"]) == "equivalent"


# --- R2: the registered primary design (A: 23 CQs, B-F: 33 each = 188 cells) ---
def test_registered_primary_set_is_188_cells_and_agrees_with_run_holdout_and_the_bank():
    import run_holdout as rh
    per_variant = {v: sum(1 for x, _ in ah.REGISTERED_PRIMARY_SET if x == v)
                   for v in ah.REGISTERED_VARIANTS}
    assert per_variant == {"A": 23, "B": 33, "C": 33, "D": 33, "E": 33, "F": 33}
    assert len(ah.REGISTERED_PRIMARY_SET) == 188
    excluded = {(e["variant"], e["cq_id"]) for e in rh.DOCUMENTED_EXCLUSIONS}
    everything = {(v, q) for v in ah.REGISTERED_VARIANTS for q in ah.REGISTERED_BANK_CQ_IDS}
    assert everything - excluded == set(ah.REGISTERED_PRIMARY_SET)
    bank = Path(__file__).resolve().parents[1] / "bank" / "cq_bank_brick_v1.csv"
    with bank.open(newline="", encoding="utf-8-sig") as fh:
        assert [r["cq_id"] for r in csv.DictReader(fh)] == list(ah.REGISTERED_BANK_CQ_IDS)


def _reg_a(j: int, q: str) -> int:
    """Engineered A for the registered-shape fixtures (silent over-credit on every 5th CQ)."""
    return 0 if (j >= 2 and int(q[3:]) % 5 == 0) else 1


def _registered_cells(drop=(), extra=()):
    cells = []
    for v, q in sorted(ah.REGISTERED_PRIMARY_SET):
        if (v, q) in drop:
            continue
        j = (int(q[3:]) * 7 + ord(v)) % 4
        cells.append({"cell_id": f"primary:{v}:{q}", "cell_kind": "primary", "cq_id": q,
                      "cluster_id": q, "category": f"cat{int(q[3:]) % 6}", "variant": v, "J": j,
                      "A": 0, "label_source": "pending human evidence", "SIMULATED": False,
                      "judge_response_parsed": True,
                      "judge_response": {"score": j, "evidence": "x"}})
    for v, q in extra:
        cells.append({"cell_id": f"primary:{v}:{q}", "cell_kind": "primary", "cq_id": q,
                      "cluster_id": q, "category": "catX", "variant": v, "J": 1, "A": 0,
                      "label_source": "pending human evidence", "SIMULATED": False})
    return cells


def test_check_registered_design_reports_missing_unexpected_and_duplicate_cells():
    ok, ids = ah.check_registered_design(_registered_cells())
    assert ok["conforms"] is True and (ok["observed_primary_cells"], ok["n_missing"]) == (188, 0)
    assert ok["by_variant"]["A"] == {"expected": 23, "observed": 23, "n_missing": 0,
                                     "n_unexpected": 0}
    assert ids == {"registered_design_missing_cells": [], "registered_design_unexpected_cells": []}
    short, ids = ah.check_registered_design(_registered_cells(drop={("B", "CQB01")}))
    assert short["conforms"] is False and short["n_missing"] == 1
    assert ids["registered_design_missing_cells"] == ["B:CQB01"]
    extra, ids = ah.check_registered_design(_registered_cells(extra={("A", "CQB15")}))
    assert extra["conforms"] is False and extra["n_unexpected"] == 1   # CQB15 is excluded from A
    assert ids["registered_design_unexpected_cells"] == ["A:CQB15"]
    dup = _registered_cells()
    dup.append(dict(dup[0], cell_id="dup"))
    assert ah.check_registered_design(dup)[0]["n_duplicate_cells"] == 1
    assert ah.check_registered_design(dup)[0]["conforms"] is False


def _registered_shape_run(tmp_path, ablated=None, preserved=None):
    """The real file shape: 188 primary (registered Q_v) + 24 ablated + 12 preserved
    controls, every control sharing (variant, cq_id) with a primary cell.  ``ablated`` and
    ``preserved`` are lists of A cells for the control rows ('' = blank; None = all blank)."""
    primary = _registered_cells()
    ablated = list(ablated) if ablated is not None else [""] * 24
    preserved = list(preserved) if preserved is not None else [""] * 12
    twins = [(c["variant"], c["cq_id"], c["category"]) for c in primary[:36]]
    controls = [_mk_cell(f"ablated_control:{v}:{q}", q, cat, v, "ablated_control", 3)
                for v, q, cat in twins[:24]]
    controls += [_mk_cell(f"preserved_control:{v}:{q}", q, cat, v, "preserved_control", 3)
                 for v, q, cat in twins[24:36]]
    cells = primary + controls
    rows = []
    for c in primary:
        a = _reg_a(c["J"], c["cq_id"])
        rows.append({"cell_id": c["cell_id"], "cq_id": c["cq_id"], "cluster_id": c["cluster_id"],
                     "category": c["category"], "variant": c["variant"], "A": str(a),
                     "rater_L1": str(c["J"] if a else min(c["J"], 1)), "note": ""})
    values = {**{c["cell_id"]: ablated[i] for i, c in enumerate(controls[:24])},
              **{c["cell_id"]: preserved[i] for i, c in enumerate(controls[24:])}}
    for c in controls:
        rows.append({"cell_id": c["cell_id"], "cq_id": c["cq_id"], "cluster_id": c["cluster_id"],
                     "category": c["category"], "variant": c["variant"],
                     "A": values[c["cell_id"]], "rater_L1": "", "note": ""})
    cells_path = _write_cells(tmp_path / "cells.jsonl", cells)
    sheet = _write_sheet(tmp_path / "labels.csv", rows)
    return cells, cells_path, sheet


def test_cli_refuses_a_primary_set_that_is_not_the_registered_design(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet, _ = _cli_registered_fixture(tmp_path)   # 21 cells, not 188
    out = tmp_path / "res.json"
    with pytest.raises(SystemExit, match=r"not the registered design.*21 cells"):
        _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                      "--out", str(out)], partial=False)
    assert not out.exists()


def test_cli_allow_partial_proceeds_and_reports_the_design_gap(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet, _ = _cli_registered_fixture(tmp_path)
    out, out_cells = tmp_path / "res.json", tmp_path / "cells_detail.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--out", str(out), "--out-cells", str(out_cells)])
    design = _json.loads(out.read_text())["analysis_population"]["registered_design"]
    assert design["conforms"] is False and design["observed_primary_cells"] == 21
    assert design["by_variant"]["C"] == {"expected": 33, "observed": 0, "n_missing": 33,
                                         "n_unexpected": 0}
    ids = _json.loads(out_cells.read_text())["id_lists"]
    assert len(ids["registered_design_missing_cells"]) == 188 - 0 and \
        len(ids["registered_design_unexpected_cells"]) == 21   # the ids live in the per-cell file


def test_cli_accepts_the_registered_shape_without_any_escape_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    cells, cells_path, sheet = _registered_shape_run(tmp_path)
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--out", str(out)], partial=False)
    res = _json.loads(out.read_text())
    design = res["analysis_population"]["registered_design"]
    assert design["conforms"] is True and design["observed_primary_cells"] == 188
    assert res["n_used"]["primary_cells"] == 188
    assert {v: d["n_cells"] for v, d in res["n_used"]["coverage"].items()} == {
        "A": 23, "B": 33, "C": 33, "D": 33, "E": 33, "F": 33}
    assert res["judge_validity"]["n_invalid"] == 0 and res["analysis_population"][
        "cluster_id_equals_cq_id"] is True
    assert ah.find_cell_level_leaks(out.read_text(), [c["cell_id"] for c in cells]
                                    + [c["cq_id"] for c in cells]) == []


# --- R3: G3 = the evaluator's A on the 24 ablated controls, behind --controls-valid ---
import platform as _platform  # noqa: E402
import scipy as _scipy  # noqa: E402

_REAL_STATE_ABLATED = ["0", "1", "0", "0", "x", "0", "1", "0"] + [""] * 16   # 8 labeled, 16 blank
_REAL_STATE_PRESERVED = ["1", "0", "x", "1"] + [""] * 8                        # 4 labeled, 8 blank


def _run_registered_cli(tmp_path, monkeypatch, *flags, ablated=None, preserved=None,
                        out_name="res.json"):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    cells, cells_path, sheet = _registered_shape_run(tmp_path, ablated, preserved)
    out = tmp_path / out_name
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--out", str(out), *flags], partial=False)
    return cells, out, _json.loads(out.read_text())


def test_cli_default_g3_is_not_computable_with_the_real_state_counts(tmp_path, monkeypatch):
    cells, out, res = _run_registered_cli(tmp_path, monkeypatch, ablated=_REAL_STATE_ABLATED,
                                          preserved=_REAL_STATE_PRESERVED)
    g3 = res["gates"]["G3_negative_control"]
    assert g3["status"] == "not_computable" and g3["counted_by"].startswith("presence")
    counts = g3["counts"]
    assert {k: counts["ablated_control"][k] for k in ("n_in_run", "n_labeled_by_presence",
                                                       "n_unlabeled")} == {
        "n_in_run": 24, "n_labeled_by_presence": 8, "n_unlabeled": 16}
    assert {k: counts["preserved_control"][k] for k in ("n_in_run", "n_labeled_by_presence",
                                                         "n_unlabeled")} == {
        "n_in_run": 12, "n_labeled_by_presence": 4, "n_unlabeled": 8}
    assert counts["all_controls"] == {"n_in_run": 36, "n_labeled_by_presence": 12,
                                      "n_unlabeled": 24}
    assert res["controls_valid_asserted"] is False
    cc = res["label_coverage"]["control_cells"]
    assert res["label_coverage"]["control_values_read"] is False
    assert all("n_label_A0" not in v and "n_label_A1" not in v for v in cc.values())  # not read


def test_cli_default_run_is_byte_identical_whatever_the_control_labels_say(tmp_path, monkeypatch):
    a_dir, b_dir = tmp_path / "a", tmp_path / "b"
    a_dir.mkdir(), b_dir.mkdir()
    _, _, one = _run_registered_cli(a_dir, monkeypatch, ablated=["0"] * 8 + [""] * 16,
                                    preserved=["1"] * 4 + [""] * 8)
    _, _, two = _run_registered_cli(b_dir, monkeypatch, ablated=["x", "7", "1", "z", "1", "0",
                                                                  "yes", "?"] + [""] * 16,
                                    preserved=["0", "0", "garbage", "0"] + [""] * 8)
    for res in (one, two):
        res.pop("input_provenance")  # the label file's own hash and path legitimately differ
        res["label_coverage"].pop("source_csv")
    assert one == two


@pytest.mark.parametrize("n_zero,expected", [(24, "pass"), (22, "pass"), (21, "fail"), (0, "fail")])
def test_cli_controls_valid_computes_g3_from_the_evaluators_a(tmp_path, monkeypatch, n_zero,
                                                               expected):
    ablated = ["0"] * n_zero + ["1"] * (24 - n_zero)
    cells, out, res = _run_registered_cli(tmp_path, monkeypatch, "--controls-valid",
                                          ablated=ablated, preserved=["1"] * 12)
    g3 = res["gates"]["G3_negative_control"]
    assert g3["status"] == expected
    assert (g3["n_unsupported"], g3["n_supported"], g3["n_controls"]) == (n_zero, 24 - n_zero, 24)
    assert g3["value"] == pytest.approx(n_zero / 24) and g3["threshold"] == pytest.approx(22 / 24)
    assert g3["evaluator_field"].startswith("A") and res["controls_valid_asserted"] is True
    pc = res["label_coverage"]["control_cells"]["preserved_control"]
    assert (pc["n_label_A0"], pc["n_label_A1"]) == (0, 12)          # aggregate counts only
    # nothing per-control leaks: the main JSON carries counts, never a control's own A
    assert ah.find_cell_level_leaks(out.read_text(), [c["cell_id"] for c in cells]) == []


def test_cli_controls_valid_with_unlabeled_ablated_cells_stays_not_computable(tmp_path, monkeypatch):
    ablated = ["0"] * 19 + [""] * 5
    _, _, res = _run_registered_cli(tmp_path, monkeypatch, "--controls-valid", ablated=ablated)
    g3 = res["gates"]["G3_negative_control"]
    assert g3["status"] == "not_computable" and "only 19 of the 24" in g3["reason"]
    assert g3["counts"]["n_unsupported_A0"] == 19


def test_cli_controls_valid_refuses_a_control_a_that_is_not_exactly_0_or_1(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet = _registered_shape_run(tmp_path, ablated=["0"] * 23 + ["x"])
    with pytest.raises(SystemExit, match="control A must be exactly 0 or 1 under --controls-valid"):
        _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                      "--controls-valid", "--out", str(tmp_path / "o.json")], partial=False)
    # the same file without the flag is fine: nothing is read
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--out", str(tmp_path / "ok.json")], partial=False)


# --- item 8: provenance --------------------------------------------------------------
def test_cli_stamps_python_numpy_and_scipy_versions(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet, _ = _cli_registered_fixture(tmp_path)
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--out", str(out)])
    env = _json.loads(out.read_text())["input_provenance"]["environment"]
    assert env["python"] == _platform.python_version() and env["numpy"] == np.__version__
    assert env["scipy"] == _scipy.__version__ and env["implementation"]


# --- item 9: the primary contrast is the pooled per-question mean ----------------------
def _cluster_layout_cells():
    """5 clusters holding 1,1,1,1,4 CQs; A->B delta +1 in the first four clusters, 0 in
    the big one: pooled mean 4/8 = 0.5, but the mean of the cluster means is 4/5 = 0.8."""
    spec = {"k0": ["q00"], "k1": ["q01"], "k2": ["q02"], "k3": ["q03"],
            "k4": ["q04", "q05", "q06", "q07"]}
    cells = []
    for cluster, qs in spec.items():
        for q in qs:
            for v, j in (("A", 1), ("B", 1 if cluster == "k4" else 2)):
                cells.append({"cell_id": f"p:{v}:{q}", "cq_id": q, "cluster_id": cluster,
                              "variant": v, "J": j, "A": 1, "category": "c"})
    return cells


def test_primary_contrast_is_the_pooled_mean_even_when_a_cluster_holds_several_cqs():
    res = ah.analyse(_cluster_layout_cells(), 3, bootstrap_resamples=300)
    contrast = res["contrasts"]["A->B"]
    assert contrast["delta"] == pytest.approx(0.5)        # not the cluster-mean form (0.8)
    assert (contrast["n_clusters"], contrast["n_questions"]) == (5, 8)
    assert contrast["estimator"].startswith("pooled mean of per-question differences")
    assert res["analysis_population"]["cluster_id_equals_cq_id"] is False


@pytest.mark.parametrize("layout", ["one_cq_per_cluster", "several_cqs_per_cluster"])
def test_fragility_and_the_primary_contrast_use_the_same_resampling(layout):
    cells = _engineered_ab_cells() if layout == "one_cq_per_cluster" else _cluster_layout_cells()
    res = ah.analyse(cells, 3, bootstrap_resamples=300)
    contrast = res["contrasts"]["A->B"]
    fragility = res["gates"]["G6_consistency"]["value"]["fragility"]
    assert fragility["initial_delta"] == pytest.approx(contrast["delta"])
    assert fragility["initial_ci_lo"] == pytest.approx(contrast["ci_lo"])
    assert res["analysis_population"]["cluster_id_equals_cq_id"] is (layout == "one_cq_per_cluster")


def test_invalid_judge_cell_ids_go_to_the_sealed_file_and_the_refusal_message(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    cells, cells_path, sheet = _cli_with_invalid_judge(tmp_path)
    bad = cells[0]["cell_id"]
    assert ah.invalid_judge_cell_ids(cells) == [bad]
    with pytest.raises(SystemExit, match=_re.escape(bad)):
        _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                      "--out", str(tmp_path / "res.json")])
    out, out_cells = tmp_path / "ok.json", tmp_path / "per_cell.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--allow-invalid-judge", "--out", str(out), "--out-cells", str(out_cells)])
    assert bad not in out.read_text()                      # the main result stays id-free
    assert _json.loads(out_cells.read_text())["id_lists"]["invalid_judge_cells"] == [bad]


# ==========================================================================
# Round 4: G4 (human-judge QWK, falsification-only) and the rank-test report.
# ==========================================================================
def _independent_qwk(j, h, k=4):
    """Textbook quadratic-weighted kappa from the normalised confusion matrix."""
    j, h = np.asarray(j), np.asarray(h)
    n = len(j)
    obs = np.zeros((k, k))
    for a, b in zip(j, h):
        obs[a, b] += 1
    obs /= n
    exp = np.outer(obs.sum(axis=1), obs.sum(axis=0))
    w = (np.arange(k)[:, None] - np.arange(k)[None, :]) ** 2 / (k - 1) ** 2
    return 1.0 - (w * obs).sum() / (w * exp).sum()


def test_qwk_from_values_is_cohens_kappa_on_two_levels_by_hand():
    # table [[1,1],[0,2]]: po=.75, pe=.5*.25+.5*.75=.5, kappa=(.75-.5)/(1-.5)=.5
    assert ah._qwk_from_values([0, 0, 1, 1], [0, 1, 1, 1]) == pytest.approx(0.5)


def test_qwk_from_values_agrees_with_the_textbook_formula_and_the_dict_version():
    rng = np.random.default_rng(4)
    for _ in range(6):
        n = int(rng.integers(8, 60))
        j = rng.integers(0, 4, n)
        h = np.clip(j + rng.integers(-1, 2, n), 0, 3)
        assert ah._qwk_from_values(j, h) == pytest.approx(_independent_qwk(j, h))
        ids = [f"c{i}" for i in range(n)]
        assert ah._qwk_from_values(j, h) == pytest.approx(ah.quadratic_weighted_kappa(
            dict(zip(ids, j.tolist())), dict(zip(ids, h.tolist()))))


def test_qwk_from_values_degenerate_and_extreme_cases():
    assert ah._qwk_from_values([0, 1, 2, 3], [0, 1, 2, 3]) == pytest.approx(1.0)
    assert ah._qwk_from_values([2, 2, 2], [2, 2, 2]) == 1.0          # both constant, equal
    assert ah._qwk_from_values([3, 3, 3], [0, 0, 0]) == 0.0          # constant but different
    assert ah._qwk_from_values([0, 1, 2, 3], [3, 2, 1, 0]) < 0       # reversed order disagrees
    with pytest.raises(ValueError):
        ah._qwk_from_values([], [])


def _g4_cells(n_cq=12, variants="ABC", noise=0, seed=0, ties_rate=0.0):
    """Primary cells for G4: judge J and the human's rater_L1 over ``n_cq`` clusters;
    ``noise`` flips the human score by +-1 with that probability."""
    rng = np.random.default_rng(seed)
    cells = []
    for q in range(n_cq):
        base = int(rng.integers(0, 4))
        for v in variants:
            j = int(np.clip(base + rng.integers(-1, 2) * (rng.random() < 0.3), 0, 3))
            h = j
            if rng.random() < noise:
                h = int(np.clip(j + rng.choice([-2, -1, 1, 2]), 0, 3))
            cells.append({"cell_id": f"p:{v}:{q}", "cq_id": f"q{q:02d}", "cluster_id": f"q{q:02d}",
                          "variant": v, "category": f"cat{q % 3}", "J": j, "rater_L1": h,
                          "A": 1})
    return cells


def test_g4_is_the_qwk_of_J_against_the_humans_rater_l1_with_an_aggregate_confusion():
    cells = _g4_cells(noise=0.4, seed=3)
    gate = ah._g4(cells, None, 20260913, None, 400)
    j = [c["J"] for c in cells]
    h = [c["rater_L1"] for c in cells]
    assert gate["qwk"] == pytest.approx(_independent_qwk(j, h))
    assert (gate["n_cells"], gate["n_clusters"], gate["resamples"]) == (36, 12, 400)
    assert (gate["judge_field"], gate["human_field"]) == ("J", "rater_L1")
    counts = gate["confusion"]["counts"]
    tally = [[sum(1 for a, b in zip(j, h) if (a, b) == (r, c)) for c in range(4)] for r in range(4)]
    assert counts == tally and sum(map(sum, counts)) == 36
    assert gate["confusion"]["rows"].startswith("J") and gate["confusion"]["cols"].startswith("rater_L1")
    assert gate["falsification_only"] is True and gate["status"] in {"fail", "not_falsified"}
    assert "L346" in gate["registered_text"] and "L606" in gate["consequence_if_failed"]
    assert gate["value"] == gate["ci_hi"] and gate["threshold"] == pytest.approx(0.60)


def test_g4_ci_is_the_cq_cluster_bca_of_the_pooled_qwk_not_a_cell_bootstrap():
    cells = _g4_cells(n_cq=16, variants="ABCDEF", noise=0.3, seed=5)
    gate = ah._g4(cells, None, 20260913, None, 600)
    records = [{"cluster_id": c["cluster_id"], "j": c["J"], "h": c["rater_L1"]} for c in cells]
    direct = ah.cluster_bootstrap_stat(records, ah._qwk_stat, None, "cluster_id", 600, 20260913)
    assert (gate["ci_lo"], gate["ci_hi"], gate["qwk"]) == (
        direct["ci_lo"], direct["ci_hi"], direct["estimate"])
    # the cells of a CQ are strongly correlated (six variants of one question): resampling
    # every cell on its own (the prohibited cell-level bootstrap) gives a narrower interval
    naive = ah.cluster_bootstrap_stat(
        [dict(r, cluster_id=f"cell{i}") for i, r in enumerate(records)], ah._qwk_stat, None,
        "cluster_id", 600, 20260913)
    assert gate["ci_hi"] - gate["ci_lo"] > naive["ci_hi"] - naive["ci_lo"]


def test_g4_can_only_fail_or_stay_not_falsified_never_pass():
    good = ah._g4(_g4_cells(n_cq=20, noise=0.0, seed=1), None, 7, None, 300)
    assert good["status"] == "not_falsified" and good["ci_hi"] >= 0.60
    # human scores drawn independently of the judge: agreement far below the line
    rng = np.random.default_rng(9)
    bad_cells = _g4_cells(n_cq=40, variants="AB", noise=0.0, seed=2)
    for c in bad_cells:
        c["rater_L1"] = int(rng.integers(0, 4))
    bad = ah._g4(bad_cells, None, 7, None, 300)
    assert bad["status"] == "fail" and bad["ci_hi"] < 0.60
    for status in (good["status"], bad["status"]):
        assert status != "pass"


@pytest.mark.parametrize("ci_hi,expected", [(0.5999, "fail"), (0.60, "not_falsified"), (0.9, "not_falsified")])
def test_g4_boundary_is_strictly_below_0_60(ci_hi, expected):
    gate = ah._g4([], {"ci_hi": ci_hi}, 1)
    assert gate["status"] == expected


def test_g4_uses_rater_l1_not_A_or_the_demoted_score():
    cells = []
    for q in range(10):
        for v in "AB":
            j = 3 if q % 2 else 0
            cells.append({"cell_id": f"p:{v}:{q}", "cq_id": f"q{q}", "cluster_id": f"q{q}",
                          "variant": v, "J": j, "rater_L1": j, "A": 0, "L1_star": min(j, 1)})
    gate = ah._g4(cells, None, 3, None, 200)
    assert gate["qwk"] == pytest.approx(1.0)  # J == rater_L1 even though A=0 demotes L1*


def test_g4_missing_rater_scores_make_it_not_computable_and_ids_stay_in_the_sink():
    cells = _g4_cells()
    del cells[0]["rater_L1"]
    sink: dict = {}
    gate = ah._g4(cells, None, 1, None, 100, detail=sink)
    assert gate["status"] == "not_computable" and gate["n_missing_rater_L1"] == 1
    assert cells[0]["cell_id"] not in _json.dumps(gate) and sink["g4_cells_missing_rater_L1"] == [
        cells[0]["cell_id"]]


def test_g4_refuses_a_human_score_that_is_not_an_int_0_to_3():
    cells = _g4_cells()
    cells[0]["rater_L1"] = 2.0
    with pytest.raises(ValueError, match="rater_L1 at cell 0 must be an int in 0..3"):
        ah._g4(cells, None, 1, None, 100)


def test_analyse_reports_g4_aggregates_only_and_counts_it_in_the_summary():
    cells = _g4_cells(noise=0.3, seed=8)
    res = ah.analyse(cells, 20260913, bootstrap_resamples=200)
    gate = res["gates"]["G4_human_judge_qwk"]
    assert gate["status"] in {"fail", "not_falsified"}
    assert res["n_used"]["G4"] == {"n_cells": 36, "n_clusters": 12}
    assert res["gates_summary"]["computed"] >= 2
    assert ah.find_cell_level_leaks(_json.dumps(res, default=ah._json_default),
                                    [c["cell_id"] for c in cells] + [c["cq_id"] for c in cells]) == []
    assert res["gates"]["G4_human_judge_qwk"]["bca_ties"] == "midrank"


def test_cli_registered_shape_run_reports_g4_over_188_cells(tmp_path, monkeypatch):
    cells, out, res = _run_registered_cli(tmp_path, monkeypatch)
    g4 = res["gates"]["G4_human_judge_qwk"]
    assert g4["status"] in {"fail", "not_falsified"} and g4["n_cells"] == 188
    assert g4["n_clusters"] == 33 and sum(map(sum, g4["confusion"]["counts"])) == 188
    assert -1.0 <= g4["ci_lo"] <= g4["qwk"] <= 1.0 and g4["ci_level"] == 0.95
    assert res["n_used"]["G4"] == {"n_cells": 188, "n_clusters": 33}
    assert ah.find_cell_level_leaks(out.read_text(), [c["cell_id"] for c in cells]
                                    + [c["cq_id"] for c in cells]) == []


# --- the rank test: reported, direction-aware, never decisive ----------------------------
def test_wilcoxon_reports_the_direction_of_the_signed_ranks():
    res = ah.wilcoxon_zeros_dropped([1, 2, 3, -1, 0])
    # |d| = 1,2,3,1 -> mid-ranks 1.5, 3, 4, 1.5: W+ = 1.5+3+4, W- = 1.5
    assert (res["w_plus"], res["w_minus"], res["sign"], res["n_nonzero"]) == (8.5, 1.5, 1, 4)
    assert stats.wilcoxon([1, 2, 3, -1], alternative="two-sided").statistic == min(8.5, 1.5)
    neg = ah.wilcoxon_zeros_dropped([-3, -2, -1, 1])
    assert neg["sign"] == -1 and neg["w_minus"] > neg["w_plus"]
    zero = ah.wilcoxon_zeros_dropped([0, 0, 0])
    assert (zero["p"], zero["sign"], zero["w_plus"], zero["w_minus"]) == (None, 0, 0.0, 0.0)


def test_rank_sign_agreement_helper_truth_table():
    assert ah._rank_agrees_in_sign(0.4, {"sign": 1}) is True
    assert ah._rank_agrees_in_sign(0.4, {"sign": -1}) is False
    assert ah._rank_agrees_in_sign(-0.4, {"sign": -1}) is True
    assert ah._rank_agrees_in_sign(0.0, {"sign": 1}) is None     # no estimated direction
    assert ah._rank_agrees_in_sign(0.4, {"sign": 0}) is None     # W+ == W-
    assert ah._rank_agrees_in_sign(0.4, {}) is None


def test_manuscript_rule_demotes_only_a_resolved_contrast_whose_rank_test_disagrees():
    assert ah._decision_with_rank_rule("resolved", True) == "resolved"
    assert ah._decision_with_rank_rule("resolved", False) == "unresolved"
    assert ah._decision_with_rank_rule("resolved", None) == "unresolved"
    assert ah._decision_with_rank_rule("equivalent", False) == "equivalent"
    assert ah._decision_with_rank_rule("unresolved", True) == "unresolved"


def test_contrasts_report_the_rank_test_but_it_never_changes_the_decision(monkeypatch):
    res = ah.analyse(_engineered_ab_cells(), 3, bootstrap_resamples=200)
    c = res["contrasts"]["A->B"]
    rt = c["rank_test"]
    assert c["decision"] == c["decision_if_manuscript_rule"] == "resolved"
    assert rt["agrees_in_sign_with_delta"] is True and rt["direction"] == 1
    assert (rt["registered_in_prereg"], rt["applied_to_decision"]) == (False, False)
    assert rt["n_questions"] == 9 and rt["p"] == c["wilcoxon"]["p"] and "PREREG.md registers no" in rt["source"]
    real = ah.wilcoxon_zeros_dropped
    monkeypatch.setattr(ah, "wilcoxon_zeros_dropped", lambda d: dict(
        real(d), sign=-1, w_plus=1.0, w_minus=44.0, p=0.5))
    flipped = ah.analyse(_engineered_ab_cells(), 3, bootstrap_resamples=200)["contrasts"]["A->B"]
    assert flipped["decision"] == "resolved"                     # the interval rule decides
    assert flipped["decision_if_manuscript_rule"] == "unresolved"
    assert flipped["rank_test"]["agrees_in_sign_with_delta"] is False
    assert flipped["p_holm"] == 1.0                              # Holm took the (mocked) rank-test p


def test_contrasts_note_says_the_rank_test_is_manuscript_only_and_not_decisive():
    note = ah.analyse(_engineered_ab_cells(), 3, bootstrap_resamples=100)["contrasts_note"]
    assert "does NOT change 'decision'" in note
    assert "PREREG.md registers no such rule" in note and "main.tex" in note
    assert "decision_if_manuscript_rule" in note and "m=2" in note
    assert "Holm's input p is the Wilcoxon p" in note


def test_rank_test_runs_over_the_paired_cq_intersection(tmp_path, monkeypatch):
    cells, out, res = _run_registered_cli(tmp_path, monkeypatch)
    rt = res["contrasts"]["A->B"]["rank_test"]
    assert rt["n_questions"] == 23  # Q_A is the intersection: every A CQ is also a B CQ


def test_analyse_still_honours_an_externally_supplied_g4_diagnostic():
    """The override bypasses the build: a supplied ci_hi < 0.60 fails the gate even
    though the cells themselves agree perfectly."""
    cells = _g4_cells(noise=0.0, seed=1)
    built = ah.analyse(cells, 7, bootstrap_resamples=100)["gates"]["G4_human_judge_qwk"]
    forced = ah.analyse(cells, 7, bootstrap_resamples=100,
                        g4={"ci_hi": 0.2})["gates"]["G4_human_judge_qwk"]
    assert built["status"] == "not_falsified" and forced["status"] == "fail"
    assert forced["value"] == 0.2 and "qwk" not in forced


# ==========================================================================
# Round 5 (hardening): judge-score validity, output paths, G7 dwell and CSV/audit
# check, AH provenance, line splitting, leak scan.  SYNTHETIC DATA ONLY.
# ==========================================================================
def _judge_record(score, j, parsed=True, **extra):
    return {"cell_id": "primary:A:CQB01", "cell_kind": "primary", "variant": "A",
            "cq_id": "CQB01", "cluster_id": "CQB01", "J": j,
            "judge_response": {"score": score, "evidence": "x"},
            "judge_response_parsed": parsed, **extra}


# --- item 1: a parsed response can still carry a bad score ----------------------
@pytest.mark.parametrize("score", [7, -1, 4, "2", None, [2], {"x": 1}, "3"])
def test_a_parsed_response_with_a_bad_score_is_an_invalid_judge_call(score):
    """run_holdout writes J=0 for these (call_judge reports parsed=True for any JSON)."""
    cell = _judge_record(score, 0)
    assert ah._judge_call_invalid(cell)
    assert ah.judge_validity([cell])["n_invalid"] == 1


def test_the_reviewers_verbatim_example_is_counted_invalid():
    verbatim = {"J": 0, "judge_response": {"score": 7}, "judge_response_parsed": True}
    assert ah.judge_validity([verbatim])["n_invalid"] == 1


def test_the_reviewers_example_is_counted_invalid():
    cell = {"cell_id": "c1", "cell_kind": "primary", "variant": "A", "J": 0,
            "judge_response": {"score": 7}, "judge_response_parsed": True}
    assert ah.judge_validity([cell]) == {
        "n_primary": 1, "n_invalid": 1, "by_variant": {"A": {"n_primary": 1, "n_invalid": 1}}}


@pytest.mark.parametrize("score,j,invalid", [
    (3, 0, True),      # a valid score of 3, but J says 0: J != the parsed score
    (0, 3, True),
    (2, 2, False),
    (2.0, 2, False),   # run_holdout accepts a float and truncates
    (2.5, 2, False),   # int(2.5) == 2 (run_holdout's rule)
    (2.5, 3, True),
    (0, 0, False),
])
def test_j_that_differs_from_the_parsed_score_is_an_invalid_call(score, j, invalid):
    assert ah._judge_call_invalid(_judge_record(score, j)) is invalid


def test_judge_score_validity_mirrors_run_holdout_valid_score():
    import run_holdout as rh
    scores = [0, 1, 2, 3, 4, -1, 7, 2.0, 2.5, 3.9, -0.5, True, False, "2", None, [], {}, [2]]
    parsed_values = [True, False, None, 1, 0, "true"]
    records = [{"judge_response": {"score": sc}, "judge_response_parsed": pv}
               for sc in scores for pv in parsed_values]
    records += [{"judge_response": {"evidence": "no score key"}, "judge_response_parsed": True},
                {"judge_response": "not a dict", "judge_response_parsed": True},
                {"judge_response": None, "judge_response_parsed": True},
                {"judge_response_parsed": True}, {}]
    for rec in records:
        assert ah._judge_score_valid(rec) == rh._valid_score(rec), rec


def test_a_nan_or_infinite_score_is_invalid_not_an_exception():
    for bad in (float("nan"), float("inf"), float("-inf")):
        cell = _judge_record(bad, 0)
        assert ah._judge_score_valid(cell) is False and ah._judge_call_invalid(cell)


def test_a_consistent_run_holdout_record_is_valid_and_legacy_cells_are_not_judged():
    assert not ah._judge_call_invalid(_judge_record(3, 3))
    assert not ah._judge_call_invalid({"J": 3})                                  # no judge fields
    assert not ah._judge_call_invalid({"J": 3, "judge_response": {"score": 3}})  # no parsed flag
    # response and flag present: the score must be valid even if the flag is True
    assert ah._judge_call_invalid({"J": 0, "judge_response": {}, "judge_response_parsed": True})


def test_cli_refuses_a_parsed_response_whose_score_is_out_of_range(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    cells = _mimic_cells()
    for c in cells:
        c["judge_response_parsed"] = True
        c["judge_response"] = {"score": c["J"], "evidence": "x"}
    cells[0]["judge_response"] = {"score": 7, "evidence": "x"}   # parsed=True, J=0 would be written
    cells[0]["J"] = 0
    cells_path = _write_cells(tmp_path / "cells.jsonl", cells)
    sheet = _write_sheet(tmp_path / "labels.csv", _mimic_sheet_rows(cells))
    args = [str(cells_path), "--labels", str(sheet), "--label-source", "human"]
    with pytest.raises(SystemExit, match=r"1 of 21 primary cells have an invalid judge call"):
        _run_cli(ah, [*args, "--out", str(tmp_path / "res.json")])
    out = tmp_path / "ok.json"
    _run_cli(ah, [*args, "--allow-invalid-judge", "--out", str(out)])
    assert _json.loads(out.read_text())["judge_validity"]["n_invalid"] == 1


# --- item 2: an output must never be an input --------------------------------------
def _guard_fixture(tmp_path):
    cells, cells_path, sheet, audit = _cli_registered_fixture(tmp_path)
    drafts = tmp_path / "drafts.csv"
    drafts.write_text("cell_id,A_draft,rater_L1_draft,span_draft,note_draft,model,generated_at\n")
    washout = _write_sheet(tmp_path / "washout.csv", _mimic_sheet_rows(cells)[:3])
    inputs = {"cells": cells_path, "--labels": sheet, "--label-audit": audit,
              "--drafts": drafts, "--labels-washout": washout}
    base = [str(cells_path), "--labels", str(sheet), "--label-source", "human",
            "--label-audit", str(audit), "--drafts", str(drafts),
            "--labels-washout", str(washout)]
    return inputs, base


@pytest.mark.parametrize("which", ["cells", "--labels", "--label-audit", "--drafts",
                                    "--labels-washout"])
@pytest.mark.parametrize("flag", ["--out", "--out-cells"])
def test_an_output_path_that_is_an_input_is_refused_and_the_input_survives(tmp_path, which, flag):
    inputs, base = _guard_fixture(tmp_path)
    target = inputs[which]
    before = target.read_bytes()
    argv = [*base, flag, str(target)]
    if flag == "--out-cells":
        argv += ["--out", str(tmp_path / "res.json")]
    with pytest.raises(SystemExit, match=rf"refusing to write {flag}.*same file as the input"):
        _run_cli(ah, argv, partial=False)
    assert target.read_bytes() == before


def test_the_output_guard_sees_through_symlinks_hardlinks_and_dot_dot(tmp_path):
    inputs, base = _guard_fixture(tmp_path)
    sheet = inputs["--labels"]
    before = sheet.read_bytes()
    sym = tmp_path / "link_to_labels.csv"
    sym.symlink_to(sheet)
    hard = tmp_path / "hard_labels.csv"
    os.link(sheet, hard)
    dotted = tmp_path / "sub" / ".." / sheet.name
    (tmp_path / "sub").mkdir()
    for alias in (sym, hard, dotted):
        with pytest.raises(SystemExit, match="same file as the input --labels"):
            _run_cli(ah, [*base, "--out", str(alias)], partial=False)
        assert sheet.read_bytes() == before


def test_distinct_output_paths_are_not_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet, audit = _cli_registered_fixture(tmp_path)
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--label-audit", str(audit), "--out", str(out),
                  "--out-cells", str(tmp_path / "per_cell.json")])
    assert out.exists()


# --- item 3: G7 (c) counts the TOTAL dwell over all saves of a cell --------------------
def _resaved(cell, elapsed_list, *, start=0):
    """Several saves of one cell (3000 s apart, all well before BOUNDARY), each
    carrying the cell's own A and rater_L1."""
    return [_audit_line(cell["cell_id"], _ts(start + 3000 * k), a=cell["A"],
                        rater=str(cell["rater_L1"]), elapsed=e,
                        edit_reason=None if k == 0 else "reconsidered")
            for k, e in enumerate(elapsed_list)]


def _g7_with_resaves(tmp_path, resaves):
    """100 cells, one 45 s save each, except those in ``resaves`` {index: [elapsed...]}."""
    primary = _hundred_primary_cells()
    lines = []
    for i, c in enumerate(primary):
        if i in resaves:
            lines += _resaved(c, resaves[i], start=i * 60)
        else:
            lines.append(_audit_line(c["cell_id"], _ts(i * 60), elapsed=45.0))
    return _g7(primary, lines, tmp_path)


def test_g7_dwell_adds_up_over_a_re_saved_cells_saves(tmp_path):
    # three cells re-saved as 12 s + 12 s: each save is < 20 s, the total (24 s) is not
    gate = _g7_with_resaves(tmp_path, {0: [12.0, 12.0], 1: [12.0, 12.0], 2: [12.0, 12.0]})
    v = gate["value"]
    assert v["n_under_20s"] == 0 and gate["status"] == "pass"
    assert v["n_under_20s_last_save_basis"] == 3          # the former basis would have failed (3%)
    assert "ALL saves" in v["elapsed_basis"] and "total dwell" in v["elapsed_basis"]
    assert "total dwell" in gate["source"]


def test_g7_a_cell_whose_total_dwell_is_short_counts_as_fast(tmp_path):
    gate = _g7_with_resaves(tmp_path, {i: [5.0, 6.0] for i in range(3)})   # 11 s total each
    assert gate["status"] == "fail" and gate["value"]["n_under_20s"] == 3
    assert "total dwell" in gate["reason"]


def test_g7_unknown_dwell_in_one_save_only_matters_if_the_known_part_is_under_20_s(tmp_path):
    # three cells (3% of 100) with a save lacking elapsed_s and a short known part: were they
    # all fast the share would reach the limit, so the gate cannot be decided
    shortish = _g7_with_resaves(tmp_path, {i: [None, 6.0] for i in range(3)})
    assert shortish["status"] == "not_computable" and shortish["value"]["n_elapsed_unknown"] == 3
    assert "unknown total dwell" in shortish["reason"]
    # a single such cell cannot reach 3%, so there is nothing left to decide
    one = _g7_with_resaves(tmp_path, {0: [None, 6.0]})
    assert one["status"] == "pass" and one["value"]["n_elapsed_unknown"] == 1
    # the known part alone is already >= 20 s: the cell is not fast and its dwell is not unknown
    long_enough = _g7_with_resaves(tmp_path, {i: [None, 25.0] for i in range(3)})
    assert long_enough["status"] == "pass" and long_enough["value"]["n_elapsed_unknown"] == 0


def test_g7_a_total_dwell_of_exactly_20_s_is_not_fast(tmp_path):
    exactly = _g7_with_resaves(tmp_path, {i: [10.0, 10.0] for i in range(3)})     # 20.0 s each
    assert exactly["value"]["n_under_20s"] == 0 and exactly["status"] == "pass"
    just_under = _g7_with_resaves(tmp_path, {i: [10.0, 9.9] for i in range(3)})   # 19.9 s each
    assert just_under["value"]["n_under_20s"] == 3 and just_under["status"] == "fail"


# --- item 4: the label CSV must equal the last audit save ------------------------------
def _g7_one_cell_off(tmp_path, *, csv_a=None, csv_rater=None, audit_a=None, audit_rater=None,
                     boundary=BOUNDARY, extra_lines=()):
    primary = _hundred_primary_cells()
    cell = primary[0]
    if csv_a is not None:
        cell["A"] = csv_a
    if csv_rater is not None:
        cell["rater_L1"] = csv_rater
    lines = [_audit_line(c["cell_id"], _ts(i * 60), elapsed=45.0,
                         a=audit_a if (i == 0 and audit_a is not None) else 1,
                         rater=audit_rater if (i == 0 and audit_rater is not None) else "2")
             for i, c in enumerate(primary)]
    lines += list(extra_lines)
    sink: dict = {}
    return _g7(primary, lines, tmp_path, boundary=boundary, detail=sink), sink, primary


def test_g7_a_csv_a_that_the_audit_never_recorded_is_a_post_hoc_edit(tmp_path):
    gate, sink, primary = _g7_one_cell_off(tmp_path, csv_a=0)           # CSV 0, audit saved 1
    assert gate["status"] == "fail" and gate["conditions"]["b_no_primary_save_after_boundary"] is False
    v = gate["value"]
    assert (v["n_csv_audit_mismatch"], v["n_csv_audit_mismatch_A"],
            v["n_csv_audit_mismatch_rater_L1"]) == (1, 1, 0)
    assert "post-hoc edit" in gate["reason"] and gate["threshold"]["csv_audit_mismatches"] == 0
    assert sink["g7_cells_csv_audit_mismatch"] == [primary[0]["cell_id"]]
    assert v["n_primary_saves_after_boundary"] == 0                       # not a late save


def test_g7_a_csv_rater_l1_that_the_audit_never_recorded_is_a_post_hoc_edit(tmp_path):
    gate, _, _ = _g7_one_cell_off(tmp_path, csv_rater=3)               # CSV 3, audit saved "2"
    assert gate["status"] == "fail"
    v = gate["value"]
    assert (v["n_csv_audit_mismatch"], v["n_csv_audit_mismatch_A"],
            v["n_csv_audit_mismatch_rater_L1"]) == (1, 0, 1)


def test_g7_a_cell_differing_in_both_fields_is_one_mismatched_cell(tmp_path):
    gate, _, _ = _g7_one_cell_off(tmp_path, csv_a=0, csv_rater=0)
    v = gate["value"]
    assert (v["n_csv_audit_mismatch"], v["n_csv_audit_mismatch_A"],
            v["n_csv_audit_mismatch_rater_L1"]) == (1, 1, 1)


def test_g7_a_csv_edit_fails_even_when_the_boundary_is_unknown(tmp_path):
    gate, _, _ = _g7_one_cell_off(tmp_path, csv_a=0, boundary=None)
    assert gate["status"] == "fail"
    assert gate["conditions"]["b_no_primary_save_after_boundary"] is False


def test_g7_only_the_last_save_is_compared_with_the_csv(tmp_path):
    cell_id = _hundred_primary_cells()[0]["cell_id"]
    # first save said A=0/rater "0", the last (a reconsidered edit) says A=1/rater "2" == the CSV
    ok, _, _ = _g7_one_cell_off(tmp_path, audit_a=0, audit_rater="0", extra_lines=[
        _audit_line(cell_id, _ts(500), a=1, rater="2", elapsed=45.0, edit_reason="fixed")])
    assert ok["value"]["n_csv_audit_mismatch"] == 0 and ok["status"] == "pass"
    # the CSV equals the FIRST save, but the last save says otherwise: an unrecorded change
    bad, _, _ = _g7_one_cell_off(tmp_path, extra_lines=[
        _audit_line(cell_id, _ts(500), a=0, rater="1", elapsed=45.0, edit_reason="fixed")])
    assert bad["value"]["n_csv_audit_mismatch"] == 1 and bad["status"] == "fail"


def test_g7_a_blank_rater_l1_matches_a_blank_audit_string(tmp_path):
    primary = _hundred_primary_cells()
    for c in primary:
        del c["rater_L1"]                     # the CSV left rater_L1 blank
    lines = [_audit_line(c["cell_id"], _ts(i * 60), elapsed=45.0, rater="")
             for i, c in enumerate(primary)]
    assert _g7(primary, lines, tmp_path)["value"]["n_csv_audit_mismatch"] == 0
    primary[0]["rater_L1"] = 2                # the CSV has a value the audit does not
    assert _g7(primary, lines, tmp_path)["value"]["n_csv_audit_mismatch"] == 1


def test_the_audit_loader_keeps_the_saved_rater_l1_as_an_int(tmp_path):
    lines = [_audit_line("c1", _ts(1), rater="3"), _audit_line("c2", _ts(2), rater=""),
             _audit_line("c3", _ts(3), rater="x")]
    saves = _audit_from(lines, tmp_path).saves
    assert saves["c1"][0].rater_l1 == 3 and saves["c2"][0].rater_l1 is None
    assert saves["c3"][0].rater_l1 is None


def test_cli_a_label_csv_edited_after_the_audit_fails_g7_with_the_mismatch_count(
        tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    cells = _mimic_cells()
    cells_path = _write_cells(tmp_path / "cells.jsonl", cells)
    rows = _mimic_sheet_rows(cells)
    audit = tmp_path / "labels.csv.audit.jsonl"
    audit.write_text("\n".join(_primary_audit_lines(cells)) + "\n", encoding="utf-8")
    victim = next(r for r in rows if r["cell_id"].startswith("primary:"))
    victim["rater_L1"] = str((int(victim["rater_L1"]) + 1) % 4)      # edited AFTER the last save
    sheet = _write_sheet(tmp_path / "labels.csv", rows)
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--label-audit", str(audit), "--unblind-boundary", BOUNDARY,
                  "--out", str(out), "--out-cells", str(tmp_path / "per_cell.json")])
    g7 = _json.loads(out.read_text())["gates"]["G7_audit_trail"]
    assert g7["status"] == "fail" and g7["value"]["n_csv_audit_mismatch"] == 1
    assert victim["cell_id"] not in out.read_text()
    assert _json.loads((tmp_path / "per_cell.json").read_text())["id_lists"][
        "g7_cells_csv_audit_mismatch"] == [victim["cell_id"]]


# --- item 5: AH provenance --------------------------------------------------------------
def test_label_provenance_helper_only_claims_ah_for_human_labels_with_drafts():
    ah_block = ah._label_provenance("human", False, True)
    assert ah_block["mode"] == "AH" and ah_block["independent_blind_human_judgement"] is False
    assert ah_block["inflation_direction"].startswith("upward")
    assert "L1160-1162" in ah_block["inflation_direction"] and "L1157-1159" in ah_block[
        "must_not_be_described_as"]
    plain = ah._label_provenance("human", False, False)
    assert plain["mode"] == "human" and "--drafts" in plain["note"]
    assert ah._label_provenance("LLM, not human", True, True) is None
    assert ah._label_provenance("unknown", False, True) is None
    # canonical_label_source never yields ("human", simulated=True); the helper still refuses it
    assert ah._label_provenance("human", True, True) is None


def _run_with_drafts(tmp_path, monkeypatch, *extra):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    primary = _labelled_primary()
    cells, cells_path, sheet, audit = _cli_registered_fixture(tmp_path)
    drafts = tmp_path / "drafts.csv"
    with drafts.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["cell_id", "A_draft", "rater_L1_draft", "span_draft", "note_draft",
                    "model", "generated_at"])
        for c in primary:
            w.writerow([c["cell_id"], c["A"], c["rater_L1"], "", "n", "m", _ts(0)])
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--drafts", str(drafts), "--out", str(out), *extra])
    return _json.loads(out.read_text())


def test_cli_with_drafts_records_the_labels_as_an_ah_pass(tmp_path, monkeypatch):
    res = _run_with_drafts(tmp_path, monkeypatch)
    assert res["label_source"] == "human-adjudicated AI draft (AH)"
    prov = res["label_provenance"]
    assert prov["mode"] == "AH" and prov["base_source"] == "human"
    assert prov["independent_blind_human_judgement"] is False
    assert "inflated" in prov["inflation_direction"] and prov["inflation_direction"].startswith("upward")
    assert "PREREG sec.11" in prov["meaning"] and prov["applies_to"].startswith("every label-based")
    assert res["SIMULATED"] is False                      # nothing else about the source changed


def test_cli_without_drafts_stays_plain_human_with_a_note(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet, _ = _cli_registered_fixture(tmp_path)
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                  "--out", str(out)])
    res = _json.loads(out.read_text())
    assert res["label_source"] == "human" and res["label_provenance"]["mode"] == "human"


def test_cli_simulated_labels_with_drafts_are_never_called_ah(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet, _ = _cli_registered_fixture(tmp_path)
    drafts = tmp_path / "drafts.csv"
    drafts.write_text("cell_id,A_draft,rater_L1_draft,span_draft,note_draft,model,generated_at\n")
    out = tmp_path / "res.json"
    _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "LLM, not human",
                  "--allow-human-labels-on-simulated-run", "--drafts", str(drafts),
                  "--out", str(out)])
    res = _json.loads(out.read_text())
    assert res["label_source"] == "LLM, not human" and "label_provenance" not in res


# --- item 6: records are split on "\n" only -------------------------------------------------
@pytest.mark.parametrize("sep", [" ", " ", "\u0085"])
def test_cells_jsonl_records_survive_unicode_line_separators_inside_strings(tmp_path, sep):
    row = {"cell_id": "c1", "cq_id": "q1", "cluster_id": "q1", "variant": "A", "J": 2,
           "judge_response": {"score": 2, "evidence": f"line one{sep}line two"},
           "judge_response_parsed": True}
    assert len(f"a{sep}b".splitlines()) == 2              # what str.splitlines() would have done
    path = tmp_path / "cells.jsonl"
    path.write_text(_json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    cells = ah.load_cells(path, require_a=False)
    assert len(cells) == 1 and cells[0]["judge_response"]["evidence"] == f"line one{sep}line two"


@pytest.mark.parametrize("sep", [" ", " ", "\u0085"])
def test_audit_records_survive_unicode_line_separators_inside_strings(tmp_path, sep):
    line = _json.loads(_audit_line("c1", _ts(5), edit_reason="x"))
    line["edit_reason"] = f"typo{sep}fixed"
    path = tmp_path / "audit.jsonl"
    path.write_text(_json.dumps(line, ensure_ascii=False) + "\n" + _audit_line("c2", _ts(9)) + "\n",
                    encoding="utf-8")
    audit = ah.load_label_audit(path)
    assert (audit.n_lines, audit.n_save_records, audit.n_unparseable_lines) == (2, 2, 0)
    assert audit.saves["c1"][0].has_edit_reason


def test_crlf_endings_and_blank_lines_still_load(tmp_path):
    path = tmp_path / "audit.jsonl"
    path.write_bytes((_audit_line("c1", _ts(1)) + "\r\n\r\n" + _audit_line("c2", _ts(2)) + "\r\n")
                     .encode("utf-8"))
    audit = ah.load_label_audit(path)
    assert (audit.n_lines, audit.n_save_records, audit.n_unparseable_lines) == (2, 2, 0)
    cells = _jsonl(tmp_path / "c.jsonl", [{"cell_id": "a", "cq_id": "q", "cluster_id": "q",
                                           "variant": "A", "J": 1}])
    cells.write_bytes(cells.read_bytes().replace(b"\n", b"\r\n") + b"\r\n")
    assert len(ah.load_cells(cells, require_a=False)) == 1


# --- item 7: the leak scan ---------------------------------------------------------------------
@pytest.mark.parametrize("text", ['"A:CQB13"', '"CQB13_x"', '"cqb13"', '"CqB13"', "x CQB13.", "(CQB13)",
                                  '"B:CQB13,C:CQB13"', '"primary:A:CQB13"', "cqb13_and_more",
                                  '"A_CQB13"', '"primary_A_CQB13_x"', "A-CQB13", "A/CQB13"])
def test_leak_scan_catches_pair_suffixed_and_lowercase_forms(text):
    assert ah.find_cell_level_leaks(text, ["CQB13"]) == ["CQB13"]


@pytest.mark.parametrize("text", ['"xCQB13"', '"CQB130"', '"CQB1"', '"aCQB13b"', '"cqb130"'])
def test_leak_scan_ignores_ids_that_are_part_of_a_longer_alphanumeric_run(text):
    assert ah.find_cell_level_leaks(text, ["CQB13"]) == []


def test_leak_scan_returns_the_canonical_spelling_and_each_id_once():
    found = ah.find_cell_level_leaks('["cqb13", "CQB13_x", "A:CQB14"]', ["CQB13", "CQB14", "CQB15"])
    assert found == ["CQB13", "CQB14"]


def test_cli_refuses_to_write_when_a_pair_or_lowercase_leak_appears(tmp_path, monkeypatch):
    monkeypatch.setattr(ah, "BOOTSTRAP_RESAMPLES", SMALL_B)
    _, cells_path, sheet, _ = _cli_registered_fixture(tmp_path)
    real = ah.analyse
    for leak in ("A:Q03", "q03", "Q03_x"):
        def leaky(*args, _leak=leak, **kwargs):
            res = real(*args, **kwargs)
            res["oops"] = {"which": _leak}
            return res
        monkeypatch.setattr(ah, "analyse", leaky)
        out = tmp_path / f"res_{leak.replace(':', '_')}.json"
        with pytest.raises(SystemExit, match="refusing to write the main results"):
            _run_cli(ah, [str(cells_path), "--labels", str(sheet), "--label-source", "human",
                          "--out", str(out)])
        assert not out.exists()
