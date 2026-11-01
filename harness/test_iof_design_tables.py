"""§15.7-5: synthetic fixtures reproducing the PREREG §15.3.2 and §15.4.3 tables.

SYNTHETIC REFERENCE DATA ONLY — the expected values below are transcribed from the
PREREG addendum's printed tables (the registered arithmetic), and every cell input
is synthetic; nothing here reads IOF labels, judge scores or any research data. The
addendum demands (§15.7-5) that the analysis code REPRODUCE these tables before the
labels are read, that two runs of the same input hash to the same output sha256,
and that the python/numpy/scipy versions be recorded (they are: printed into the
test report and written to a small JSON file the report names).
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import pytest
import scipy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import design_iof  # noqa: E402
import pooled_g1 as pg  # noqa: E402

# PREREG.md §15.3.2 (scipy beta.ppf, one-sided CP upper bound in %): each N row
# lists (97.5, 95) for k=0..4, then the reference max-k under the 10% line.
TABLE_15_3_2 = {
    60: ([(5.96, 4.87), (8.94, 7.66), (11.53, 10.12), (13.92, 12.42), (16.20, 14.61)], (1, 1)),
    63: ([(5.69, 4.64), (8.53, 7.31), (11.00, 9.66), (13.29, 11.85), (15.47, 13.94)], (1, 2)),
    66: ([(5.44, 4.44), (8.16, 6.99), (10.52, 9.23), (12.71, 11.33), (14.80, 13.33)], (1, 2)),
    69: ([(5.21, 4.25), (7.81, 6.69), (10.08, 8.84), (12.18, 10.86), (14.18, 12.78)], (1, 2)),
    72: ([(4.99, 4.08), (7.50, 6.42), (9.68, 8.49), (11.70, 10.42), (13.62, 12.26)], (2, 2)),
}
MIN_N_PASSING_15_3_2 = {1: (54, 46), 2: (70, 61), 3: (85, 76), 4: (100, 89)}
BRICK_FACTS_15_3_2 = {  # single-domain reference values printed by the addendum
    (4, 33): (28.20, 25.63), (0, 33): (10.58, 8.68),
}

# PREREG.md §15.4.3: m -> (n, MDE normal 1.155, coverage pt, MDE t 1.155,
# MDE normal 1.336 sensitivity, 90% half-width 1.155, half-width 1.336)
TABLE_15_4_3 = {
    0: (23, 0.675, 22.5, 0.706, 0.780, 0.414, 0.478),
    10: (33, 0.563, 18.8, 0.581, 0.652, 0.341, 0.394),
    15: (38, 0.525, 17.5, 0.539, 0.607, 0.316, 0.366),
    20: (43, 0.493, 16.4, 0.505, 0.571, 0.296, 0.343),
    23: (46, 0.477, 15.9, 0.488, 0.552, 0.286, 0.331),
    26: (49, 0.462, 15.4, 0.472, 0.535, 0.277, 0.320),
    30: (53, 0.444, 14.8, 0.453, 0.514, 0.266, 0.307),
    33: (56, 0.432, 14.4, 0.440, 0.500, 0.258, 0.299),
    36: (59, 0.421, 14.0, 0.428, 0.487, 0.251, 0.291),
}


def test_15_3_2_table_reproduced_by_the_committed_arithmetic():
    for n, (cells, (max975, max95)) in TABLE_15_3_2.items():
        row = design_iof.cp_row(n)
        assert row["n_clusters"] == n
        for k, (b975, b95) in enumerate(cells):
            got = row["events_upper_bound_pct"][k]
            assert got["one_sided_97.5%"] == pytest.approx(b975, abs=0.011), (n, k)
            assert got["one_sided_95%"] == pytest.approx(b95, abs=0.011), (n, k)
        assert row["max_events_below_10pct_reference_line_one_sided_97.5%"] == max975
        assert row["max_events_below_10pct_reference_line_one_sided_95%"] == max95


def test_15_3_2_reference_values_min_n_and_brick_single_domain():
    import analyze_holdout as ah

    def min_n(k, alpha):
        n = k + 1
        while ah.clopper_pearson_upper(k, n, alpha) > 0.10:
            n += 1
        return n

    for k, (n975, n95) in MIN_N_PASSING_15_3_2.items():
        assert min_n(k, 0.025) == n975 and min_n(k, 0.05) == n95
    for (k, n), (b975, b95) in BRICK_FACTS_15_3_2.items():
        assert round(100 * ah.clopper_pearson_upper(k, n, 0.025), 2) == pytest.approx(b975, abs=0.011)
        assert round(100 * ah.clopper_pearson_upper(k, n, 0.05), 2) == pytest.approx(b95, abs=0.011)


def test_15_3_2_at_the_iof_design_pooled_n_the_a_priori_fact_holds():
    # §15.1/§15.3.2: with Brick's 4 known event clusters, four events at ANY IOF
    # design N in range leave the pooled estimate above the 10% reference line —
    # a numeric fact about the design path's N (no verdict is attached to it).
    d = design_iof.load_iof_design()
    assert (d.brick_n_clusters, d.n_clusters, d.pooled_n_clusters) == (33, 8, 41)
    row = design_iof.cp_row(d.pooled_n_clusters)
    four = row["events_upper_bound_pct"][4]
    assert four["one_sided_97.5%"] > 10.0 and four["one_sided_95%"] > 10.0


def test_15_4_3_table_reproduced_by_the_committed_arithmetic():
    for m, (n, mde, cov, mde_t, mde_s, half, half_s) in TABLE_15_4_3.items():
        row = design_iof.mde_row(m)
        assert row["pooled_pairs"] == n
        assert row["mde_normal_approx_sigma_1_155"] == pytest.approx(mde, abs=0.0011)
        assert row["coverage_points"] == pytest.approx(cov, abs=0.051)
        assert row["mde_t_approx_sigma_1_155"] == pytest.approx(mde_t, abs=0.0011)
        assert row["mde_normal_approx_sigma_1_336_sensitivity"] == pytest.approx(mde_s, abs=0.0011)
        assert row["ci90_half_width_sigma_1_155"] == pytest.approx(half, abs=0.0011)
        assert row["ci90_half_width_sigma_1_336"] == pytest.approx(half_s, abs=0.0011)


def test_15_4_3_at_the_iof_design_pair_count():
    d = design_iof.load_iof_design()
    assert d.m_ab_pairs == 6 and d.pooled_ab_pairs == 29
    row = design_iof.mde_row(d.m_ab_pairs)
    assert row["pooled_pairs"] == 29
    # monotone in m and bracketed by the registered table's m=0 and m=10 rows
    lo, hi = design_iof.mde_row(0), design_iof.mde_row(10)
    assert lo["mde_normal_approx_sigma_1_155"] > row["mde_normal_approx_sigma_1_155"] > \
        hi["mde_normal_approx_sigma_1_155"]


def _cell(cluster, j, a):
    return {"cluster_id": cluster, "J": j, "A": a, "cell_kind": "primary", "variant": "A",
            "cq_id": cluster, "cell_id": f"A:{cluster}:primary"}


def _synthetic_pooled():
    # synthetic cells shaped like the design (33 brick clusters / 4 events,
    # 8 iof clusters / 0 events -> pooled (4, 41)); synthetic, not research data
    brick = [_cell(f"CQB{i:02d}", 3 if i <= 4 else 0, 0 if i <= 4 else 1)
             for i in range(1, 34)]
    iof = [_cell(f"CQI{i:02d}", 0, 1) for i in range(1, 9)]
    return pg.pooled_g1({"brick": brick, "iof": iof}, bootstrap_resamples=200)


def _payload():
    d = design_iof.load_iof_design()
    return {
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "iof_design": {
            "manifest_sha256": d.manifest_sha256,
            "checked": d.checked_primary_cells, "excluded": d.excluded_primary_cells,
            "eligible": d.eligible_primary_cells, "per_variant": d.per_variant_counts,
            "n_iof": d.n_clusters, "m_ab": d.m_ab_pairs,
            "pooled_n": d.pooled_n_clusters, "pooled_pairs": d.pooled_ab_pairs,
        },
        "table_15_3_2": {str(n): design_iof.cp_row(n)
                        for n in (*sorted(TABLE_15_3_2), d.pooled_n_clusters)},
        "table_15_4_3": {str(m): design_iof.mde_row(m)
                        for m in (*sorted(TABLE_15_4_3), d.m_ab_pairs)},
        "pooled_g1_synthetic": _synthetic_pooled(),
    }


def test_determinism_output_sha256_and_version_record(tmp_path):
    first = json.dumps(_payload(), sort_keys=True, default=str)
    second = json.dumps(_payload(), sort_keys=True, default=str)
    sha1, sha2 = (hashlib.sha256(t.encode()).hexdigest() for t in (first, second))
    payload = json.loads(first)
    env = payload["environment"]
    assert all(env[k] for k in ("python", "implementation", "numpy", "scipy"))
    record = tmp_path / "iof_design_env.json"
    record.write_text(json.dumps({"environment": env, "output_sha256": sha1}, indent=2))
    print(f"\n§15.7-5 determinism artifact: sha256={sha1} env={env} file={record}")
    assert sha1 == sha2
    assert sha1 in record.read_text()  # recorded into the small file and the -s report
