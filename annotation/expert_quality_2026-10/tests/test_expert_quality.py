import csv
import itertools
import json
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import analyze_expert_quality as A  # noqa: E402


def sim_sheet(path, key_rows, quality, rng, noise):
    """quality: dict (set,variant)->latent; writes a filled sheet for one rater."""
    sets = {}
    for aid, st, var, grp, batch, pos in key_rows:
        sets.setdefault(st, []).append((aid, st, var, quality[(st, var)] + rng.gauss(0, noise)))
    out = []
    for st, items in sets.items():
        order = sorted(items, key=lambda t: -t[3])
        rk = {t[0]: i + 1 for i, t in enumerate(order)}
        for aid, _, var, q in items:
            row = {"artifact_id": aid, "overall_rank": rk[aid]}
            for c in A.CRITERIA:
                row[c] = max(1, min(5, round(3 + q + rng.gauss(0, 0.5))))
            out.append(row)
    cols = ["artifact_id"] + A.CRITERIA + ["overall_rank"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(out)


class Basics(unittest.TestCase):
    def test_tau_known(self):
        self.assertAlmostEqual(A.strat_tau_b([1, 2, 3, 4], [1, 2, 3, 4]), 1.0)
        self.assertAlmostEqual(A.strat_tau_b([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        # scipy.stats.kendalltau([1,2,3,4,5],[1,3,2,5,4]) = 0.6
        self.assertAlmostEqual(A.strat_tau_b([1, 2, 3, 4, 5], [1, 3, 2, 5, 4]), 0.6)
        # tau-b with ties: x=[1,1,2,3], y=[1,2,3,3] -> C=4,D=0,tx=1,ty=1,n0=6 -> 4/5
        self.assertAlmostEqual(A.strat_tau_b([1, 1, 2, 3], [1, 2, 3, 3]), 4 / 5)

    def test_exact_distribution(self):
        self.assertAlmostEqual(A.kendall_no_ties_p(4, 1.0), 1 / 24)
        self.assertAlmostEqual(A.kendall_no_ties_p(5, 0.8), 5 / 120)
        self.assertAlmostEqual(A.critical_tau(5), 0.8)
        self.assertAlmostEqual(A.critical_tau(6), 1 - 4 / 15)  # P(D<=2)=20/720=0.0278
        self.assertAlmostEqual(A.kendall_no_ties_p(6, 1 - 4 / 15), 20 / 720)

    def test_permutation_matches_dp(self):
        x, y = [3, 1, 4, 2, 5], [1, 2, 3, 4, 5]
        t = A.perm_pvalues(lambda xs: A.strat_tau_b(xs, y), x)
        tau = A.strat_tau_b(x, y)
        self.assertAlmostEqual(t["p_one_sided"], A.kendall_no_ties_p(5, tau))
        self.assertTrue(t["exact"])

    def test_spearman(self):
        self.assertAlmostEqual(A.spearman([1, 2, 3, 4], [1, 3, 2, 4]), 0.8)

    def test_stratified_uses_within_pairs_only(self):
        x = [1, 2, 10, 20]
        y = [1, 2, 20, 10]
        st = [0, 0, 1, 1]
        self.assertAlmostEqual(A.strat_tau_b(x, y, st), 0.0)  # +1 and -1 cancel

    def test_kendall_w(self):
        self.assertAlmostEqual(A.kendall_w([[1, 2, 3], [1, 2, 3], [1, 2, 3]]), 1.0)
        self.assertAlmostEqual(A.kendall_w([[1, 2, 3], [1, 3, 2]]), 0.75)
        self.assertLess(A.kendall_w([[1, 2, 3], [3, 2, 1]]), 1e-9)

    def test_w_pvalue_perfect_agreement(self):
        r = A.w_pvalue([[1, 2, 3, 4, 5]] * 3)
        self.assertEqual(r["W"], 1.0)
        self.assertLess(r["p"], 0.001)
        self.assertTrue(r["exact"])

    def test_icc_shrout_fleiss(self):
        m = [[9, 2, 5, 8], [6, 1, 3, 2], [8, 4, 6, 8], [7, 1, 2, 6], [10, 5, 6, 9], [6, 2, 4, 7]]
        r = A.icc_2(m)
        self.assertAlmostEqual(r["ICC2_1"], 0.29, places=2)
        self.assertAlmostEqual(r["ICC2_k"], 0.62, places=2)

    def test_alpha_interval(self):
        self.assertAlmostEqual(A.krippendorff_alpha_interval([[1, 1], [2, 2], [3, 3]]), 1.0)
        # brute-force definition
        units = [[1, 2], [2, 2], [3, 5], [4, 4]]
        vals = [v for u in units for v in u]
        N = len(vals)
        do = sum((a - b) ** 2 for u in units for a, b in itertools.permutations(u, 2)) / N
        de = sum((a - b) ** 2 for a, b in itertools.permutations(vals, 2)) / (N * (N - 1))
        self.assertAlmostEqual(A.krippendorff_alpha_interval(units), 1 - do / de)

    def test_alpha_interval_equals_icc_like_for_two_raters(self):
        # for complete data, alpha_interval ~ ICC(2? no) -> check bounds only
        a = A.krippendorff_alpha_interval([[1, 5], [5, 1], [3, 3], [2, 4]])
        self.assertLess(a, 0.2)


class EndToEnd(unittest.TestCase):
    def make(self, tmp, noise, sets=("holdout", "dev"), reverse=False, seed=3):
        rng = random.Random(seed)
        variants = ["A", "B", "C", "D", "E+F"]
        base = {"A": -1.2, "B": 0.4, "C": 0.5, "D": -0.2, "E+F": 0.45}
        q = {(s, v): (-base[v] if reverse else base[v]) for s in sets for v in variants}
        kd = Path(tmp) / "keys"
        kd.mkdir()
        filled = {}
        for rid in ("R1", "R2", "R3"):
            rows, i = [], 0
            for si, s in enumerate(sets):
                order = variants[:]
                rng.shuffle(order)
                for pos, v in enumerate(order, 1):
                    i += 1
                    rows.append([f"{rid}{i:03d}", s, v, f"{s}:g{v}", f"Batch {si+1}", pos])
            with open(kd / f"key_{rid}.csv", "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["artifact_id", "set", "variant", "group_id", "batch", "position"])
                w.writerows(rows)
            sim_sheet(Path(tmp) / f"{rid}.csv", rows, q, rng, noise)
            filled[rid] = str(Path(tmp) / f"{rid}.csv")
        cov = {(s, v): {"J_pct": c, "L1star_pct": c if s == "holdout" else None}
               for s in sets for v, c in {"A": 58, "B": 69, "C": 69, "D": 60, "E": 66, "F": 68}.items()}
        return kd, filled, cov

    def run_it(self, **kw):
        with tempfile.TemporaryDirectory() as tmp:
            kd, filled, cov = self.make(tmp, **kw)
            rows = A.load_ratings(kd, filled)
            self.assertEqual(A.validate(rows), [])
            # E/F merged in key -> coverage averaged
            return A.analyze(rows, {**cov, **{(s, "E+F"): {"J_pct": 67.0, "L1star_pct": 64.5 if s == "holdout" else None}
                                              for s in ("holdout", "dev")}}, n_boot=300, n_mc=3000)

    def test_low_noise_positive_tau_and_adoption(self):
        r = self.run_it(noise=0.1)
        self.assertTrue(r["decision"]["reference_ranking_adopted"])
        self.assertGreater(r["pooled"]["J_pct|rank_score"]["tau_b_stratified"]["obs"], 0.5)
        self.assertIn("W_by_set", r["decision"])

    def test_reversed_gives_negative_tau(self):
        r = self.run_it(noise=0.1, reverse=True)
        self.assertLess(r["pooled"]["J_pct|rank_score"]["tau_b_stratified"]["obs"], 0)
        self.assertIn("inconsistent", r["decision"]["classification"])

    def test_pure_noise_not_adopted(self):
        # no latent structure: every rater random
        with tempfile.TemporaryDirectory() as tmp:
            kd, filled, cov = self.make(tmp, noise=50.0, seed=11)
            rows = A.load_ratings(kd, filled)
            r = A.analyze(rows, {**cov, **{(s, "E+F"): {"J_pct": 67.0, "L1star_pct": 64.5} for s in ("holdout", "dev")}},
                          n_boot=100, n_mc=1000)
            self.assertLess(max(r["decision"]["W_by_set"].values()), 0.9)

    def test_validate_catches_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            kd, filled, cov = self.make(tmp, noise=0.1)
            rows = A.load_ratings(kd, filled)
            rows[0]["Q1_concept_accuracy"] = 7
            rows[1]["rank"] = rows[2]["rank"]
            self.assertGreaterEqual(len(A.validate(rows)), 2)


class Power(unittest.TestCase):
    def test_power_monotone(self):
        pt = A.power_table([6], [0.3, 0.9], n_sim=800)
        self.assertLess(pt["power"][0.3], pt["power"][0.9])
        self.assertAlmostEqual(pt["critical_tau_b"], 1 - 4 / 15)

    def test_more_strata_more_power(self):
        a = A.power_table([5], [0.7], n_sim=800)["power"][0.7]
        b = A.power_table([5, 5], [0.7], n_sim=800)["power"][0.7]
        self.assertGreater(b, a)


if __name__ == "__main__":
    unittest.main()
