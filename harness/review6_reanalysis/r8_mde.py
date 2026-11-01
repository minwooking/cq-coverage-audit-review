#!/usr/bin/env python3
"""R8  MDE recomputed with the REALISED per-question sigma, and the sample size needed for equivalence.

sigma = sample SD (ddof = 1) of the per-question A->B differences on the 23 shared questions, for the scores
J, L1* (AH), L1* (second rater), L_flip (AH) and L_R (AH).  The manuscript quotes 1.343 (J) and 1.473 (L1*, AH).
Formulas (stated before the run):
  MDE_normal(n, sigma) = (z_.975 + z_.80) * sigma / sqrt(n)        (the manuscript's formula, 2.8016 sigma/sqrt n)
  MDE_t(n, sigma)      : smallest delta whose two-sided one-sample t-test (alpha .05, df n-1) has power .80
                         (noncentral t, exact)
  Equivalence (TOST, alpha .05 per side = 90% interval inside +-m), true difference 0, sigma known up to the
  sample SD: power(n) = P(|xbar| + t_{.95,n-1} s/sqrt(n) < m), xbar ~ N(0, sigma^2/n), s^2 ~ sigma^2 chi2_{n-1}/(n-1)
  (exact numerical integration); n_needed = smallest n with power >= .80.  Normal approximation
  n = ((z_.95 + z_.90) sigma / m)^2 is also reported.
sigma uncertainty: chi-square 95% interval for sigma, carried through to the MDE and n.
Design sigma (development study, 16 questions): 1.155.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import integrate, optimize, stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C

d = C.load_188()
OUT: dict = {"post_hoc": True, "formula_z": C.Z_MDE, "design_sigma_registered": 1.155}


def per_q_diffs(col):
    x = d[d.variant == "A"].set_index("cq_id")[col]
    y = d[d.variant == "B"].set_index("cq_id")[col]
    sh = sorted(set(x.index) & set(y.index))
    return (y.loc[sh] - x.loc[sh]).to_numpy(float)


d["L_flip_AH"] = np.where(d.S_AH == 1, np.maximum(d.J, 2), np.minimum(d.J, 1))
SC = {"J": "J", "L1star_AH": "L1star_AH", "L1star_second_rater": "L1star_2", "L_flip_AH": "L_flip_AH", "L_R_AH": "R_AH"}


def mde_normal(n, s):
    return C.Z_MDE * s / math.sqrt(n)


def t_power(n, s, delta):
    """power of the two-sided one-sample t test (alpha .05, df n-1) at true mean delta, by quadrature over s_hat."""
    df = n - 1
    tc = stats.t.ppf(0.975, df)
    sd_x = s / math.sqrt(n)

    def integrand(u):
        shat = s * math.sqrt(u / df)
        c = tc * shat / math.sqrt(n)
        return (stats.norm.sf((c - delta) / sd_x) + stats.norm.cdf((-c - delta) / sd_x)) * stats.chi2.pdf(u, df)

    val, _ = integrate.quad(integrand, 0, stats.chi2.ppf(0.99999, df), limit=400)
    return float(val)


def mde_t(n, s):
    return float(optimize.brentq(lambda dl: t_power(n, s, dl) - 0.80, 1e-6, 4.0 * s))


def tost_power(n, s, m):
    df = n - 1
    tc = stats.t.ppf(0.95, df)
    sd_x = s / math.sqrt(n)

    def integrand(u):  # u = chi2 variate; s_hat = s*sqrt(u/df)
        shat = s * math.sqrt(u / df)
        lim = m - tc * shat / math.sqrt(n)
        if lim <= 0:
            return 0.0
        p = stats.norm.cdf(lim / sd_x) - stats.norm.cdf(-lim / sd_x)
        return p * stats.chi2.pdf(u, df)

    val, _ = integrate.quad(integrand, 0, stats.chi2.ppf(0.99999, df), limit=400)
    return float(val)


def n_needed_tost(s, m, target=0.80):
    n = 3
    while tost_power(n, s, m) < target:
        n += 1
        if n > 5000:
            return None
    return n


def n_needed_normal(s, m):
    return ((stats.norm.ppf(0.95) + stats.norm.ppf(0.90)) * s / m) ** 2


def sigma_ci(sd, n):
    lo = sd * math.sqrt((n - 1) / stats.chi2.ppf(0.975, n - 1))
    hi = sd * math.sqrt((n - 1) / stats.chi2.ppf(0.025, n - 1))
    return lo, hi


def block(s, n_ref):
    out = {"sigma": s}
    for n in (23, 36):
        out[f"MDE_normal_n{n}"] = mde_normal(n, s)
        out[f"MDE_t_n{n}"] = mde_t(n, s)
        out[f"MDE_normal_n{n}_coverage_pts"] = mde_normal(n, s) / 3 * 100
    for m in (0.30, 0.50):
        out[f"n_equivalence_pm{m:.2f}_normal_approx"] = n_needed_normal(s, m)
        out[f"n_equivalence_pm{m:.2f}_exact_tost"] = n_needed_tost(s, m)
    # TOST power at the realised designs, true difference 0
    for n in (23, 36):
        for m in (0.30, 0.50):
            out[f"tost_power_n{n}_pm{m:.2f}"] = tost_power(n, s, m)
    # expected half-width of the 90% interval
    for n in (23, 36):
        out[f"expected_halfwidth_90_n{n}"] = float(stats.t.ppf(0.95, n - 1) * s / math.sqrt(n))
    return out


for name, col in SC.items():
    dif = per_q_diffs(col)
    n = len(dif)
    sd = float(dif.std(ddof=1))
    lo, hi = sigma_ci(sd, n)
    b = block(sd, n)
    b.update({"n_questions": n, "mean_delta_A_to_B": float(dif.mean()), "sigma_ci95_chi2": [lo, hi],
              "at_sigma_lower": {k: v for k, v in block(lo, n).items() if k.startswith(("MDE_normal", "n_equiv"))},
              "at_sigma_upper": {k: v for k, v in block(hi, n).items() if k.startswith(("MDE_normal", "n_equiv"))},
              # power to detect the observed delta, two-sided alpha .05, normal approx (descriptive; observed power is a
              # monotone function of p and adds no information beyond it)
              "power_normal_at_observed_delta_n23": float(stats.norm.cdf(abs(dif.mean()) * math.sqrt(n) / sd - 1.959964))})
    OUT[name] = b

# the design sigma for comparison
OUT["design_sigma_1.155"] = block(1.155, 16)
# a loop-up table of n for MDE targets (normal): n = (Z sigma / target)^2
OUT["n_for_detectable_effect_normal"] = {
    f"sigma_{s:.3f}": {f"delta_{t:.2f}": (C.Z_MDE * s / t) ** 2 for t in (0.30, 0.50, 0.675)}
    for s in (1.155, OUT["J"]["sigma"], OUT["L1star_AH"]["sigma"])}

json.dump(OUT, open(Path(__file__).resolve().parent / "parts/r8.json", "w"), indent=1, default=float)
for name in list(SC) + ["design_sigma_1.155"]:
    b = OUT[name]
    print(f"{name:22s} sigma {b['sigma']:.3f} MDE n23 {b['MDE_normal_n23']:.3f} (t {b['MDE_t_n23']:.3f}) n36 {b['MDE_normal_n36']:.3f} (t {b['MDE_t_n36']:.3f}) "
          f"| n eq +-.30 {b['n_equivalence_pm0.30_normal_approx']:.0f}/{b['n_equivalence_pm0.30_exact_tost']} +-.50 {b['n_equivalence_pm0.50_normal_approx']:.0f}/{b['n_equivalence_pm0.50_exact_tost']} "
          f"| TOST power n36 +-.5 {b['tost_power_n36_pm0.50']:.3f} n23 +-.5 {b['tost_power_n23_pm0.50']:.3f}")
    if "power_normal_at_observed_delta_n23" in b:
        print("    sigma CI", [round(x, 3) for x in b["sigma_ci95_chi2"]], "power at observed delta", round(b["power_normal_at_observed_delta_n23"], 3),
              "MDE range n23", round(b["at_sigma_lower"]["MDE_normal_n23"], 3), round(b["at_sigma_upper"]["MDE_normal_n23"], 3))
