"""Pre-registered analysis for the Brick holdout study.

Implements PREREG.md. Nothing here invents data: it consumes the per-cell
records written by run_holdout.py and, when supplied, a validated evidence-label
CSV joined by ``cell_id``. Omitting the CSV preserves the legacy JSONL-only
behaviour for compatibility with synthetic probes (a JSONL whose rows carry the
placeholder ``label_source`` 'pending human evidence' is refused without
``--labels``); unknown provenance is never reported as human.

Notation (PREREG.md sec.1, rubric/RUBRIC_L1.md):
    J(v,q)    raw judge Layer-1 score, 0..3
    A(v,q)    rater evidence verdict, 1 if a verbatim supporting span exists
    L1*(v,q)  = J if A == 1 else min(J, 1)   -- one-sided: never promotes
    Coverage  = sum(L1*) / (|Q| * 3) * 100

Prohibited by pre-registration and therefore refused in code:
  * bootstrapping a proportion with zero observed events (use Clopper-Pearson);
  * resampling questions rather than semantic clusters.

Population (PREREG sec.1, sec.3): every primary estimand -- Coverage, the
confirmatory contrasts, the cell-level pi-hat, G1, G2, G5, G6, G7 and the
fragility analysis -- is computed over cells with ``cell_kind == "primary"``
ONLY.  Seeded ``ablated_control`` / ``preserved_control`` cells are separate
instruments: they are excluded structurally (``split_primary_and_controls``),
their counts are reported, and their human-label values are never read.  A cell
with no ``cell_kind`` is a primary cell (legacy JSONL).

Resampling: every interval comes from ONE helper, ``cluster_bootstrap_stat``
(BCa, B=10,000, pre-registered seed, unit = semantic cluster).  Stratification
is opt-in (``--bootstrap-strata category``); the registered text (PREREG sec.4)
specifies an unstratified semantic-cluster bootstrap, so that is the default.
BCa's bias correction counts bootstrap replicates tied with the estimate by the
mid-rank rule (the scipy convention; ``--bca-ties strict`` is the former rule,
a sensitivity output only).  "Resolved" uses the 95% interval; the equivalence
(TOST) decision uses the 90% interval.  The primary contrast is the pooled mean
of per-question differences, clusters resampled.

Types and guards: A is the int 0/1, J an int 0..3, rater_L1 exactly "0".."3";
nothing is coerced.  A control row's A is never read unless ``--controls-valid``.
The run is refused unless the primary set is the registered design (A: 23 CQs,
B-F: 33 each = 188; ``--allow-partial`` overrides, reported) and every primary
judge call is valid (``--allow-invalid-judge`` overrides, reported).  The main
results JSON holds aggregates only; cell-level values and identifier lists go to
the optional ``--out-cells`` file.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import json
import math
import os
import platform
import re
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

import numpy as np
import scipy
from scipy import stats

BOOTSTRAP_RESAMPLES = 10_000
REGISTERED_SEED = 20260913  # PREREG freeze block; recorded in the output, never defaulted
TOST_MARGIN_L1 = 0.30
CONFIRMATORY_CONTRASTS = (("A", "B"), ("B", "Bprime"))
G1_UPPER_BOUND_THRESHOLD = 0.10
# BCa bias-correction z0: how bootstrap replicates TIED with theta-hat are counted.
# "midrank" (default) is the scipy.stats.bootstrap(method="BCa") convention,
# z0 = ndtri(((boot < theta) + (boot <= theta)) / (2 B)); "strict" is the former
# z0 = ndtri(mean(boot < theta)), kept only as a sensitivity switch because it
# under-covers when the statistic sits on a coarse grid (L1* means, 0/1 events).
BCA_TIES_CHOICES = ("midrank", "strict")
DEFAULT_BCA_TIES = "midrank"
RESOLVE_CI_LEVEL = 0.95        # "resolved" = this interval excludes 0
EQUIVALENCE_CI_LEVEL = 0.90    # TOST at alpha=.05 per side = the 90% two-sided interval
RESOLVE_ALPHA = round(1.0 - RESOLVE_CI_LEVEL, 10)
EQUIVALENCE_ALPHA = round(1.0 - EQUIVALENCE_CI_LEVEL, 10)
CELL_KIND_PRIMARY = "primary"
CONTROL_CELL_KINDS = ("ablated_control", "preserved_control")
# --bootstrap-strata choices -> cell field used as the stratum.  None is the
# registered (unstratified) resampling; see the module docstring.
BOOTSTRAP_STRATA_CHOICES = {"none": None, "category": "category"}


# --------------------------------------------------------------------------
# scoring
# --------------------------------------------------------------------------
def _strict_a(value, what: str = "A") -> int:
    """A is the int 0 or 1.  A bool, a float (1.0), a string ("1") or None is an
    error: nothing is coerced, because a silently coerced A is a silently wrong
    adjudication."""
    if type(value) is not int or value not in (0, 1):
        raise ValueError(f"{what} must be the int 0 or 1, got {value!r} "
                         f"({type(value).__name__})")
    return value


def _strict_j(value, what: str = "J") -> int:
    """J (the judge's Layer-1 score) is an int in 0..3, with the same rule."""
    if type(value) is not int or not 0 <= value <= 3:
        raise ValueError(f"{what} must be an int in 0..3, got {value!r} "
                         f"({type(value).__name__})")
    return value


def demote(j: int, a: int) -> int:
    """L1* = J if A == 1 else min(J, 1). Adjudication may only withdraw credit.
    A must be the int 0/1 and J an int 0..3; anything else raises."""
    a = _strict_a(a)
    j = _strict_j(j)
    return j if a == 1 else min(j, 1)


def coverage(l1_star: list[int]) -> float:
    if not l1_star:
        raise ValueError("coverage over an empty cell set is undefined")
    return sum(l1_star) / (len(l1_star) * 3) * 100.0


def silent_over_credit(cells: list[dict]) -> tuple[int, int]:
    """pi = Pr[J >= 2 AND A == 0], counted over CQ-clusters (PREREG sec.4).

    Uses the PRE-demotion judge score J. Using the demoted L1* here would make
    the estimand identically zero, since L1* >= 2 implies A == 1 by construction.
    Returns (events, n_clusters). pi-hat is a LOWER bound; the CI upper bound is
    the reported quantity.
    """
    by_cluster: dict[str, bool] = {}
    for c in cells:
        j, a = _strict_j(c["J"]), _strict_a(c["A"])
        hit = j >= 2 and a == 0
        by_cluster[c["cluster_id"]] = by_cluster.get(c["cluster_id"], False) or hit
    return sum(by_cluster.values()), len(by_cluster)


# --------------------------------------------------------------------------
# primary population: controls are a separate instrument, never a primary cell
# --------------------------------------------------------------------------
def _cell_kind(cell: dict) -> str:
    """``primary`` | ``ablated_control`` | ``preserved_control``.

    A missing/blank kind is a primary cell (legacy JSONL probes).  Any OTHER
    value is an error: guessing would either contaminate the primary estimands
    with an unknown kind or silently drop primary rows.
    """
    raw = cell.get("cell_kind")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return CELL_KIND_PRIMARY
    kind = str(raw).strip()
    if kind != CELL_KIND_PRIMARY and kind not in CONTROL_CELL_KINDS:
        raise ValueError(
            f"unknown cell_kind {kind!r} on cell "
            f"{cell.get('cell_id', cell.get('cq_id', '?'))!r}; expected "
            f"{CELL_KIND_PRIMARY!r} or one of {list(CONTROL_CELL_KINDS)}"
        )
    return kind


def split_primary_and_controls(cells: list[dict]) -> tuple[list[dict], dict[str, list[dict]]]:
    """Partition into the primary population and the per-kind control cells."""
    primary: list[dict] = []
    controls: dict[str, list[dict]] = {kind: [] for kind in CONTROL_CELL_KINDS}
    for cell in cells:
        kind = _cell_kind(cell)
        (primary if kind == CELL_KIND_PRIMARY else controls[kind]).append(cell)
    return primary, controls


def _assert_unique_primary_pairing(primary: list[dict]) -> None:
    """Contrasts pair B to A by cq_id, so a (variant, cq_id) must be unique.

    A duplicate would be silently overwritten in the pairing dictionary -- the
    exact mechanism by which a control twin used to replace its primary cell.
    """
    seen: set[tuple[str, str]] = set()
    for cell in primary:
        key = (str(cell.get("variant")), str(cell.get("cq_id")))
        if key in seen:
            raise ValueError(
                f"more than one primary cell for (variant, cq_id)={key}; "
                "paired contrasts require exactly one"
            )
        seen.add(key)


def _is_silent_over_credit(cell: dict) -> bool:
    j, a = _strict_j(cell["J"]), _strict_a(cell["A"])
    return j >= 2 and a == 0


def _pi_stat(cells: list[dict]) -> float:
    return sum(_is_silent_over_credit(c) for c in cells) / len(cells)


def silent_over_credit_rate(
    cells: list[dict],
    *,
    strata_key: str | None = None,
    B: int = BOOTSTRAP_RESAMPLES,
    seed: int | None = None,
    ties: str = DEFAULT_BCA_TIES,
) -> dict:
    """Cell-level pi-hat = #(J >= 2 and A == 0) / #primary cells (PREREG sec.1.1).

    The interval resamples semantic clusters (``cluster_bootstrap_stat``), so
    the cells of one CQ stay together.  With ZERO observed events no bootstrap
    is run (PREREG sec.4 item 3: a bootstrap cannot resample an event it has
    never seen); the operative bound is then the cluster-level
    Clopper-Pearson limit of G1.  pi-hat is a lower bound on the judge's true
    silent over-credit (the evaluator's residual bias favours the judge), so
    the interval's UPPER end is the honest headline.  Fractions in [0, 1].
    """
    cells = list(cells)
    if not cells:
        raise ValueError("silent over-credit rate over an empty cell set is undefined")
    events = sum(_is_silent_over_credit(c) for c in cells)
    clusters = {str(c["cluster_id"]) for c in cells}
    with_event = {str(c["cluster_id"]) for c in cells if _is_silent_over_credit(c)}
    out = {
        "estimand": "pi = Pr[J >= 2 AND A == 0] over primary cells (cell level)",
        "events": events,
        "n_cells": len(cells),
        "pi_hat": events / len(cells),
        "n_clusters": len(clusters),
        "clusters_with_event": len(with_event),
        "pi_hat_is_a_lower_bound": True,
        "ci_lo": None,
        "ci_hi": None,
        "ci_method": None,
    }
    if events == 0:
        out["ci_reason"] = (
            "zero observed events: bootstrap refused (PREREG sec.4 item 3); "
            "use the cluster-level Clopper-Pearson upper bound reported by G1"
        )
        return out
    if len(clusters) < 2:
        out["ci_reason"] = "fewer than two clusters: nothing to resample"
        return out
    boot = cluster_bootstrap_stat(cells, _pi_stat, strata_key, "cluster_id", B, seed, ties)
    out.update(
        ci_lo=boot["ci_lo"], ci_hi=boot["ci_hi"], ci_method="BCa cluster bootstrap",
        bca_ties=ties, resamples=boot["B"], seed=boot["seed"], strata_key=boot["strata_key"],
        strata_sizes=boot["strata_sizes"],
    )
    return out


# --------------------------------------------------------------------------
# interval estimation
# --------------------------------------------------------------------------
def clopper_pearson_upper(events: int, n: int, alpha: float = 0.025) -> float:
    """One-sided upper bound. Required whenever events == 0: a bootstrap cannot
    resample an event it has never observed. Exact values at n=36 (alpha=.025):
    0 events -> 0.0974, 1 event -> 0.1453 (alpha=.05: 0.0798 / 0.1251; the
    rule-of-three 3/36 = 0.083 is only an approximation), so a 10% gate is
    effectively zero-tolerance."""
    if n <= 0:
        raise ValueError("n must be positive")
    if events < 0 or events > n:
        raise ValueError("events out of range")
    if events == n:
        return 1.0
    return float(stats.beta.ppf(1 - alpha, events + 1, n - events))


def g1_achievability(
    n_clusters: int,
    alpha: float,
    threshold: float = G1_UPPER_BOUND_THRESHOLD,
) -> dict:
    """DIAGNOSTIC ONLY -- can G1 be passed at all with this many clusters?

    The registered G1 decision (Clopper-Pearson upper bound <= 10% at the
    registered one-sided level) is computed elsewhere and is NOT altered by
    this function.  With zero events the bound is 1 - alpha**(1/n), which can
    already exceed the threshold when n is small: at n=33, alpha=.025 it is
    10.58%, so no outcome passes.  Reporting that fact is not a relaxation of
    the gate; it tells the reader the gate was unpassable by construction.
    """
    if n_clusters <= 0:
        raise ValueError("n_clusters must be positive")
    min_upper = clopper_pearson_upper(0, n_clusters, alpha)
    max_passing = None
    for events in range(n_clusters + 1):
        if clopper_pearson_upper(events, n_clusters, alpha) <= threshold:
            max_passing = events
        else:
            break  # the bound is increasing in the event count
    needed = max(1, math.ceil(math.log(alpha) / math.log(1.0 - threshold)))
    while clopper_pearson_upper(0, needed, alpha) > threshold:
        needed += 1
    while needed > 1 and clopper_pearson_upper(0, needed - 1, alpha) <= threshold:
        needed -= 1
    achievable = max_passing is not None
    return {
        "diagnostic_only": True,
        "achievable": achievable,
        "n_clusters": n_clusters,
        "alpha_one_sided": alpha,
        "threshold": threshold,
        "min_achievable_upper_bound": min_upper,
        "max_events_that_pass": max_passing,
        "min_clusters_for_zero_event_pass": needed,
        "note": (
            "Registered G1 decision above is unchanged. "
            + ("G1 can be passed at this n only with at most "
               f"{max_passing} cluster event(s)." if achievable else
               "Even with 0 events the one-sided Clopper-Pearson bound exceeds "
               "the threshold at this n: G1 is unpassable by construction.")
        ),
    }


def _g1_both_levels(events: int, n: int, g1_alpha: float,
                    threshold: float = G1_UPPER_BOUND_THRESHOLD) -> dict:
    """The one-sided Clopper-Pearson upper bound at BOTH candidate levels, side
    by side, for the same (events, n).  INFORMATIONAL: the registered G1
    decision is the one computed at ``g1_alpha`` and is not changed by this.

    The level is an unresolved registration inconsistency: PREREG sec.4 (L564)
    names the one-sided 97.5% Clopper-Pearson bound for zero-event proportions,
    while the sec.2 G1 wording/arithmetic (L343, L378-390) speaks of a 95%
    one-sided bound; L387-390 records the mismatch as undecided."""
    out = {
        "level_status": "UNRESOLVED",
        "note": ("PREREG L564 (sec.4) specifies one-sided 97.5%; the sec.2 G1 "
                 "table/prose wording uses 95%; L387-390 flags the mismatch as "
                 "unresolved. Both bounds are shown; only the level named in "
                 "decision_uses decides G1."),
        "decision_uses": f"one-sided {1.0 - g1_alpha:.3f} (g1_alpha={g1_alpha})",
        "events": events, "n_clusters": n, "threshold": threshold,
    }
    for label, alpha in (("one_sided_97_5", 0.025), ("one_sided_95", 0.05)):
        upper = clopper_pearson_upper(events, n, alpha=alpha)
        out[label] = {"alpha": alpha, "upper_bound": upper,
                      "meets_threshold": bool(upper <= threshold),
                      "decides_g1": bool(alpha == g1_alpha)}
    return out


def _bca_z0(theta_hat, boot, ties: str = DEFAULT_BCA_TIES) -> float:
    """BCa bias correction.  Replicates equal to theta-hat (within a float
    tolerance) are ties: ``midrank`` counts half of them as below, exactly like
    scipy.stats.bootstrap(method="BCa"); ``strict`` counts none (the former
    rule)."""
    boot = np.asarray(boot, dtype=float)
    n_boot = len(boot)
    if ties == "strict":
        prop = float(np.mean(boot < theta_hat))
    elif ties == "midrank":
        tol = 1e-12 * max(1.0, abs(float(theta_hat)))
        below = float(np.sum(boot < theta_hat - tol))
        at_or_below = float(np.sum(boot <= theta_hat + tol))
        prop = (below + at_or_below) / (2.0 * n_boot)
    else:
        raise ValueError(f"ties must be one of {BCA_TIES_CHOICES}, got {ties!r}")
    prop = min(max(prop, 1.0 / n_boot), 1.0 - 1.0 / n_boot)
    return float(stats.norm.ppf(prop))


def _bca_interval(theta_hat, boot, jack, alpha=0.05, ties: str = DEFAULT_BCA_TIES):
    boot = np.asarray(boot, dtype=float)
    z0 = _bca_z0(theta_hat, boot, ties)
    jack = np.asarray(jack, dtype=float)
    d = jack.mean() - jack
    denom = 6.0 * (np.sum(d ** 2) ** 1.5)
    acc = 0.0 if denom == 0 else float(np.sum(d ** 3) / denom)
    zs = stats.norm.ppf([alpha / 2, 1 - alpha / 2])
    adj = stats.norm.cdf(z0 + (z0 + zs) / (1 - acc * (z0 + zs)))
    return tuple(float(np.percentile(boot, 100 * a)) for a in adj)


def _finite(value, what: str) -> float:
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{what} is not finite ({out!r}); the statistic is undefined")
    return out


def _group_clusters(cells: list, strata_key: str | None, cluster_key: str) -> list[list[list]]:
    """cells -> [stratum][cluster] -> list of that cluster's cells, both levels
    in sorted order so the resampling is independent of input row order."""
    members: dict[str, dict[str, list]] = {}
    stratum_of: dict[str, str] = {}
    for cell in cells:
        cluster = cell.get(cluster_key)
        if cluster is None or not str(cluster).strip():
            raise ValueError(
                f"a cell has no {cluster_key!r} value; every cell must belong to "
                "a resampling cluster"
            )
        cluster = str(cluster)
        if strata_key is None:
            stratum = "all"
        else:
            raw = cell.get(strata_key)
            if raw is None or not str(raw).strip():
                raise ValueError(
                    f"a cell in cluster {cluster!r} has no {strata_key!r} value; "
                    "stratified resampling needs exactly one stratum per cluster"
                )
            stratum = str(raw)
        known = stratum_of.setdefault(cluster, stratum)
        if known != stratum:
            raise ValueError(
                f"cluster {cluster!r} spans strata {known!r} and {stratum!r}; "
                "a cluster cannot be split across strata"
            )
        members.setdefault(stratum, {}).setdefault(cluster, []).append(cell)
    return [[members[s][c] for c in sorted(members[s])] for s in sorted(members)]


def cluster_bootstrap_stat(
    cells: list,
    stat_fn,
    strata_key: str | None = None,
    cluster_key: str = "cluster_id",
    B: int = BOOTSTRAP_RESAMPLES,
    seed: int | None = None,
    ties: str = DEFAULT_BCA_TIES,
) -> dict:
    """THE resampling routine: BCa 95% interval (plus the 90% interval that
    decides equivalence) for ``stat_fn(cells)`` from a cluster bootstrap.  Coverage, every contrast delta, the cell-level pi-hat,
    the G5 MAE and the fragility analysis all call this (directly or through
    ``cluster_bootstrap_delta``), so they share one resampling scheme.

    * resample unit: whole clusters (``cluster_key``), with replacement; all
      cells of a drawn cluster travel together (PREREG sec.4 item 2);
    * ``strata_key=None`` (the registered scheme) draws n clusters from the
      pooled set; a key draws within each stratum, holding the per-stratum
      cluster counts fixed in every resample;
    * ``stat_fn`` receives the resampled cell list (cells of a cluster drawn
      twice appear twice) and must return a finite number;
    * the draw sequence depends only on ``seed`` and the sorted (stratum,
      cluster) structure, so statistics over the same cluster set are
      evaluated on the SAME resamples (common random numbers);
    * BCa acceleration uses the leave-one-cluster-out jackknife; the bias
      correction counts replicates tied with the estimate by the mid-rank rule
      (``ties="midrank"``, the scipy convention; ``"strict"`` is the former
      rule, a sensitivity switch);
    * the pre-registered seed is never defaulted.
    """
    if seed is None:
        raise ValueError(
            "the randomization seed is pre-registered; refusing to default it"
        )
    if B < 2:
        raise ValueError("B must be at least 2")
    if ties not in BCA_TIES_CHOICES:
        raise ValueError(f"ties must be one of {BCA_TIES_CHOICES}, got {ties!r}")
    cells = list(cells)
    groups = _group_clusters(cells, strata_key, cluster_key)
    clusters = [cluster for stratum in groups for cluster in stratum]
    if len(clusters) < 2:
        raise ValueError("need at least two clusters to resample")
    theta = _finite(stat_fn(cells), "point estimate")
    rng = np.random.default_rng(seed)
    boot = np.empty(B, dtype=float)
    for b in range(B):
        sample: list = []
        for stratum in groups:
            n_s = len(stratum)
            for i in rng.integers(0, n_s, n_s).tolist():
                sample.extend(stratum[i])
        boot[b] = _finite(stat_fn(sample), "bootstrap statistic")
    jack = [
        _finite(stat_fn([cell for j, cl in enumerate(clusters) if j != k for cell in cl]),
                "jackknife statistic")
        for k in range(len(clusters))
    ]
    lo, hi = _bca_interval(theta, boot, jack, RESOLVE_ALPHA, ties)
    lo90, hi90 = _bca_interval(theta, boot, jack, EQUIVALENCE_ALPHA, ties)
    tol = 1e-12 * max(1.0, abs(theta))
    return {
        "estimate": theta, "ci_lo": lo, "ci_hi": hi,
        "ci90_lo": lo90, "ci90_hi": hi90,
        "tie_share": float(np.mean(np.abs(boot - theta) <= tol)),
        "n_cells": len(cells), "n_clusters": len(clusters),
        "B": B, "seed": seed, "method": "BCa", "bca_ties": ties,
        "unit": "semantic cluster", "cluster_key": cluster_key,
        "strata_key": strata_key,
        "strata_sizes": {("all" if strata_key is None else str(
            stratum[0][0].get(strata_key))): len(stratum) for stratum in groups},
    }


def _mean_d(records: list[dict]) -> float:
    return float(np.mean([r["d"] for r in records]))


def cluster_bootstrap_delta(
    deltas_by_cluster: dict[str, list[float]],
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int | None = None,
    strata: dict[str, str] | None = None,
    ties: str = DEFAULT_BCA_TIES,
):
    """Paired BCa bootstrap on the mean of the per-cluster mean differences,
    resampling SEMANTIC CLUSTERS. Questions inside a cluster probe the same
    capability and are not independent; resampling questions would treat
    correlated cells as fresh evidence and produce intervals that are too
    narrow.  A thin adapter over ``cluster_bootstrap_stat`` (one record per
    cluster); ``strata`` optionally maps cluster -> stratum."""
    if seed is None:
        raise ValueError(
            "the randomization seed is pre-registered; refusing to default it"
        )
    ids = sorted(deltas_by_cluster)
    if len(ids) < 2:
        raise ValueError("need at least two clusters to resample")
    if strata is not None:
        missing = [c for c in ids if c not in strata]
        if missing:
            raise ValueError(f"no stratum for cluster(s) {missing}")
    records = [{"cluster_id": c, "stratum": None if strata is None else strata[c],
                "d": float(np.mean(deltas_by_cluster[c]))} for c in ids]
    res = cluster_bootstrap_stat(
        records, _mean_d, "stratum" if strata is not None else None,
        "cluster_id", resamples, seed, ties)
    return {"delta": res["estimate"], "ci_lo": res["ci_lo"], "ci_hi": res["ci_hi"],
            "ci90_lo": res["ci90_lo"], "ci90_hi": res["ci90_hi"], "bca_ties": ties,
            "n_clusters": res["n_clusters"], "resamples": res["B"], "seed": seed,
            "unit": "semantic cluster", "method": "BCa",
            "strata_key": None if strata is None else "stratum",
            "strata_sizes": res["strata_sizes"]}


def wilcoxon_zeros_dropped(deltas: list[float]):
    """Method-robust companion to the bootstrap, so the interval-scale reading
    of an ordinal rubric is never the sole support for a conclusion."""
    nz = [d for d in deltas if d != 0]
    if not nz:
        return {"p": None, "n_nonzero": 0, "w_plus": 0.0, "w_minus": 0.0, "sign": 0,
                "note": "all differences zero"}
    res = stats.wilcoxon(nz, zero_method="wilcox", alternative="two-sided")
    arr = np.asarray(nz, dtype=float)
    ranks = stats.rankdata(np.abs(arr))  # mid-ranks of |d|, zeros already dropped
    w_plus, w_minus = float(ranks[arr > 0].sum()), float(ranks[arr < 0].sum())
    return {"p": float(res.pvalue), "n_nonzero": len(nz), "w_plus": w_plus,
            "w_minus": w_minus, "sign": int(np.sign(w_plus - w_minus))}


def _rank_agrees_in_sign(delta: float, wil: dict) -> bool | None:
    """Does the signed-rank statistic lean the same way as the estimate?  None when
    either has no direction (zero estimate, or W+ == W-)."""
    direction, estimate = wil.get("sign", 0), float(np.sign(delta))
    if direction == 0 or estimate == 0:
        return None
    return bool(direction == estimate)


def _decision_with_rank_rule(decision: str, agrees: bool | None) -> str:
    """The MANUSCRIPT's three-decision rule (main.tex "Three decisions" paragraph
    and decision table): "resolved" also needs the rank test to agree in sign,
    otherwise it is unresolved.  PREREG.md registers no such rule, so this value
    is reported next to ``decision`` and never replaces it."""
    if decision != "resolved":
        return decision
    return "resolved" if agrees is True else "unresolved"


HOLM_FAMILY_SIZE = len(CONFIRMATORY_CONTRASTS)  # the registered family: A->B and B->B'


def holm(pvalues: dict[str, float], m: int | None = None) -> dict[str, float]:
    """Holm step-down over the confirmatory contrasts ONLY, for a family of size
    ``m`` (default: the number of p-values supplied).  A family member WITHOUT
    a p-value (not computable) stays in the family and ranks last, so a lone
    computable contrast in a family of 2 gets min(1, 2p)."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items) if m is None else m
    if m < len(items):
        raise ValueError(f"family size {m} is smaller than the {len(items)} p-values given")
    out, running = {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


def tost_decision(ci_lo: float, ci_hi: float, margin: float = TOST_MARGIN_L1, *,
                  eq_lo: float | None = None, eq_hi: float | None = None) -> str:
    """resolved / equivalent / unresolved.

    ``ci_lo, ci_hi`` is the interval that decides *resolved* (the 95% BCa
    interval excludes zero).  Equivalence is decided on the TOST interval
    ``eq_lo, eq_hi`` (the 90% two-sided interval = alpha .05 per side) lying
    entirely inside +-margin; when it is not supplied the first interval is
    used (legacy call).

    A CI that merely contains zero is UNRESOLVED, never 'equivalent' and never a
    'tie': a wide interval centred near zero is what insufficient resolution
    looks like as well as what a genuine null looks like."""
    if ci_lo > 0 or ci_hi < 0:
        return "resolved"
    lo_e = ci_lo if eq_lo is None else eq_lo
    hi_e = ci_hi if eq_hi is None else eq_hi
    if lo_e > -margin and hi_e < margin:
        return "equivalent"
    return "unresolved"


# --------------------------------------------------------------------------
# label ingestion and joining


@dataclass(frozen=True)
class LabelSet:
    """Validated labels from one packet export."""

    path: Path
    labels: dict[str, int | None]
    rater_l1: dict[str, int | None]
    source: str
    simulated: bool
    missing_a_ids: tuple[str, ...]
    # Tolerated (control) rows: the A/rater_L1 VALUE is never retained
    # (``labels`` holds None); only the fact that the A cell was non-blank
    # (``tolerated_nonblank_ids``) is kept, so counts are by presence.
    tolerated_nonblank_ids: tuple[str, ...] = ()
    # Final stored ``evidence_span_verbatim`` of every NON-tolerated row, kept
    # only for the AH span-edit share (never copied into a result).
    spans: dict[str, str] = field(default_factory=dict)
    # Control A values, read ONLY when the loader was told the controls are valid
    # (--controls-valid); otherwise empty and ``controls_read`` is False.
    control_a: dict[str, int] = field(default_factory=dict)
    controls_read: bool = False


_SIMULATED_SOURCES = frozenset({
    "llm, not human",
    "llm smoke probe",
    "llm-generated",
    "llm generated",
    "simulated",
    "simulation",
    "synthetic",
})


def canonical_label_source(value: str) -> tuple[str, bool]:
    """Canonicalise closed-world provenance markers.

    An unknown source is an error rather than an implicit human label. This is
    deliberately strict because provenance is part of the estimand's audit
    trail, not presentation metadata.
    """
    raw = str(value).strip()
    key = raw.casefold()
    if key in {"human", "human annotation", "human annotator"}:
        return "human", False
    if key in _SIMULATED_SOURCES:
        return "LLM, not human", True
    raise ValueError(
        "label source must be 'human' or an explicit simulation marker "
        "such as 'LLM, not human'; got " + repr(raw)
    )


def _cell_id_for_record(cell: dict, index: int) -> str:
    """Match ``build_label_packet.py``'s stable fallback ID."""
    raw = f"{cell['cq_id']}|{cell.get('variant', '')}|{index}".encode("utf-8")
    return "cell-" + hashlib.sha256(raw).hexdigest()[:16]


def _normalise_cell_ids(cells: list[dict]) -> list[dict]:
    by_id: dict[str, int] = {}
    normalised: list[dict] = []
    for index, original in enumerate(cells):
        if not isinstance(original, dict):
            raise ValueError(f"cell record {index} is not a JSON object")
        cell = dict(original)
        if not str(cell.get("cell_id", "")).strip():
            if "cq_id" not in cell:
                raise ValueError(f"cell record {index} lacks both cell_id and cq_id")
            cell["cell_id"] = _cell_id_for_record(cell, index)
        else:
            cell["cell_id"] = str(cell["cell_id"]).strip()
        if cell["cell_id"] in by_id:
            previous = by_id[cell["cell_id"]]
            raise ValueError(
                f"duplicate cell_id in cells JSONL: {cell['cell_id']!r} "
                f"(records {previous} and {index})"
            )
        by_id[cell["cell_id"]] = index
        normalised.append(cell)
    return normalised


def load_cells(path: Path, *, require_a: bool = True) -> list[dict]:
    # split on "\n" ONLY: str.splitlines() also breaks on U+2028/U+2029/U+0085 and
    # \x0b/\x0c/\x1c-\x1e, which may sit unescaped inside a JSON string and
    # would cut a valid record in two.  A trailing "\r" is JSON whitespace.
    cells = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").split("\n")
        if line.strip()
    ]
    cells = _normalise_cell_ids(cells)
    if not cells:
        raise ValueError(f"no cell records in {path}")
    for index, cell in enumerate(cells):
        if _cell_kind(cell) != CELL_KIND_PRIMARY:
            continue  # control rows: no judge/placeholder A is read here
        if "J" not in cell:
            raise ValueError(f"cell record {index} lacks J")
        _strict_j(cell["J"], f"J in cell record {index}")
        if not require_a:
            continue  # the label CSV supplies A; a placeholder A is never read
        if "A" not in cell:
            raise ValueError(f"cell record {index} lacks A; supply --labels")
        _strict_a(cell["A"], f"A in cell record {index}")
        cell["L1_star"] = demote(cell["J"], cell["A"])
    return cells


def _source_columns(fieldnames: list[str]) -> list[str]:
    return [name for name in ("label_source", "source") if name in fieldnames]


def load_label_csv(
    path: Path,
    *,
    label_source: str | None = None,
    allow_partial: bool = False,
    tolerate_ids=(),
    read_control_a: bool = False,
) -> LabelSet:
    """Read one packet CSV and validate every A value and cell identifier.

    ``tolerate_ids`` are the ``cell_id``s of control cells.  Their A/rater_L1
    cells may be blank or malformed without raising, and their VALUE is never
    retained: ``labels``/``rater_l1`` hold ``None`` and only the fact that the
    A cell was non-blank is kept (``tolerated_nonblank_ids``), so every control
    count is by presence.  Structural checks (duplicate/missing ``cell_id``)
    still apply to every row, and every NON-tolerated row is validated exactly
    as before.

    ``read_control_a=True`` (``--controls-valid``): the operator asserts that the
    control labels are valid, so a tolerated row's A cell IS read -- blank stays
    "unlabeled", ``0``/``1`` is kept in ``control_a``, anything else raises.
    """
    tolerate = frozenset(str(x) for x in tolerate_ids)
    if not path.exists():
        raise ValueError(f"no label CSV at {path}")
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = [str(name).strip() for name in (reader.fieldnames or [])]
        if "cell_id" not in fieldnames or "A" not in fieldnames:
            raise ValueError(f"{path} must contain cell_id and A columns")
        rows = []
        for raw_row in reader:
            rows.append({
                str(key).strip(): (value if value is not None else "")
                for key, value in raw_row.items()
                if key is not None
            })
    if not rows:
        raise ValueError(f"label CSV has no rows: {path}")

    source_values = []
    for row in rows:
        for column in _source_columns(fieldnames):
            value = str(row.get(column, "")).strip()
            if value:
                source_values.append(value)
    source_from_csv: tuple[str, bool] | None = None
    if source_values:
        canonical = [canonical_label_source(value) for value in source_values]
        if len(set(canonical)) != 1:
            raise ValueError(f"label source is inconsistent in {path}")
        source_from_csv = canonical[0]
    source_from_cli = (
        canonical_label_source(label_source) if label_source is not None else None
    )
    if source_from_csv is None and source_from_cli is None:
        raise ValueError(
            f"{path} has no label source; provide --label-source explicitly "
            "(source must never be inferred as human)"
        )
    if (
        source_from_csv is not None
        and source_from_cli is not None
        and source_from_csv != source_from_cli
    ):
        raise ValueError(
            f"label source conflict for {path}: CSV={source_from_csv[0]!r}, "
            f"CLI={source_from_cli[0]!r}"
        )
    source, simulated = source_from_csv or source_from_cli  # type: ignore[misc]

    labels: dict[str, int | None] = {}
    rater_l1: dict[str, int | None] = {}
    missing_a: list[str] = []
    invalid_a: list[str] = []
    tolerated_nonblank: list[str] = []
    control_a: dict[str, int] = {}
    spans: dict[str, str] = {}
    for row_number, row in enumerate(rows, start=2):
        cell_id = str(row.get("cell_id", "")).strip()
        if not cell_id:
            raise ValueError(f"missing cell_id in {path} at CSV row {row_number}")
        if cell_id in labels:
            raise ValueError(f"duplicate cell_id in {path}: {cell_id!r}")
        raw_a = str(row.get("A", "")).strip()
        raw_l1 = str(row.get("rater_L1", "")).strip()
        if cell_id in tolerate:
            # control row: PRESENCE of an A cell is all that is recorded; the
            # value (valid or not) is discarded unread.  Nothing here can raise.
            labels[cell_id] = None
            rater_l1[cell_id] = None
            if raw_a:
                tolerated_nonblank.append(cell_id)
                if read_control_a:
                    if raw_a not in {"0", "1"}:
                        raise ValueError(
                            f"control A must be exactly 0 or 1 under --controls-valid in "
                            f"{path}, cell {cell_id!r}")
                    control_a[cell_id] = int(raw_a)
            continue
        if "evidence_span_verbatim" in row:
            spans[cell_id] = str(row.get("evidence_span_verbatim") or "")
        if not raw_a:
            value_a: int | None = None
            missing_a.append(cell_id)
        elif raw_a in {"0", "1"}:
            value_a = int(raw_a)
        else:
            invalid_a.append(cell_id)
            value_a = None
        labels[cell_id] = value_a

        if not raw_l1:
            rater_l1[cell_id] = None
        else:
            if raw_l1 not in {"0", "1", "2", "3"}:
                raise ValueError(
                    f"rater_L1 must be exactly one of 0,1,2,3 in {path}, "
                    f"cell {cell_id!r}"
                )
            rater_l1[cell_id] = int(raw_l1)
    if invalid_a:
        raise ValueError(
            f"A must be exactly 0 or 1 in {path}; invalid cell_id(s): "
            f"{sorted(invalid_a)}"
        )
    if missing_a and not allow_partial:
        raise ValueError(
            f"A is blank in {path}; missing cell_id(s): {sorted(missing_a)}. "
            "Use --allow-partial to omit them from the scored denominator."
        )
    return LabelSet(
        path=path,
        labels=labels,
        rater_l1=rater_l1,
        source=source,
        simulated=simulated,
        missing_a_ids=tuple(sorted(missing_a)),
        tolerated_nonblank_ids=tuple(sorted(tolerated_nonblank)),
        spans=spans,
        control_a=control_a,
        controls_read=read_control_a,
    )


def join_labels(
    cells: list[dict],
    labels: LabelSet,
    *,
    allow_partial: bool = False,
    registered_subset: bool = False,
    exclude_controls: bool = False,
) -> tuple[list[dict], dict]:
    """Join A by cell_id, refusing label-only and unexpected cell-only IDs.

    ``exclude_controls=True`` (the registered CLI path): ablated/preserved
    control cells are never required to carry a label, never returned in the
    scored list and never counted in the primary denominators; the metadata
    reports, per control kind, how many rows the run holds and how many carry
    a label cell (by presence).  Their label VALUES are not read.  The
    default (False) keeps the legacy behaviour for other callers --
    ``analyse`` excludes controls from every statistic regardless.
    """
    cell_by_id = {str(cell["cell_id"]): cell for cell in cells}
    kinds = {cid: _cell_kind(cell) for cid, cell in cell_by_id.items()}
    cell_ids = set(cell_by_id)
    label_ids = set(labels.labels)
    only_labels = sorted(label_ids - cell_ids)
    only_cells = sorted(cell_ids - label_ids)
    if only_labels:
        raise ValueError(
            f"label CSV {labels.path} contains cell_id(s) absent from cells JSONL: "
            f"{only_labels}"
        )

    def _skipped_control(cell_id: str) -> bool:
        return exclude_controls and kinds.get(cell_id, CELL_KIND_PRIMARY) != CELL_KIND_PRIMARY

    required_only_cells = [cid for cid in only_cells if not _skipped_control(cid)]
    if required_only_cells and not (allow_partial or registered_subset):
        raise ValueError(
            f"cells JSONL contains cell_id(s) absent from label CSV {labels.path}: "
            f"{required_only_cells}"
        )

    scored: list[dict] = []
    omitted: set[str] = set(required_only_cells)
    omitted.update(cid for cid in labels.missing_a_ids if not _skipped_control(cid))
    for cell in cells:
        cell_id = str(cell["cell_id"])
        if _skipped_control(cell_id):
            continue
        if cell_id not in labels.labels or labels.labels[cell_id] is None:
            omitted.add(cell_id)
            continue
        scored_cell = dict(cell)
        scored_cell["A"] = _strict_a(labels.labels[cell_id], f"A of {cell_id!r}")
        if labels.rater_l1.get(cell_id) is not None:
            scored_cell["rater_L1"] = labels.rater_l1[cell_id]
        scored_cell["L1_star"] = demote(scored_cell["J"], scored_cell["A"])
        scored.append(scored_cell)
    if not scored:
        raise ValueError(f"no labeled cells remain after joining {labels.path}")

    # Control rows are counted BY PRESENCE ONLY: "labeled" means the A cell was
    # non-blank, whatever it held.  No count may depend on a control label's
    # value, and no control value is ever read.
    control_cells: dict[str, dict] = {}
    nonblank_tolerated = set(labels.tolerated_nonblank_ids)
    for kind in CONTROL_CELL_KINDS:
        ids = [cid for cid in cell_by_id if kinds[cid] == kind]
        if not ids:
            continue
        in_csv = [cid for cid in ids if cid in labels.labels]
        labeled = [cid for cid in in_csv
                   if cid in nonblank_tolerated or labels.labels[cid] is not None]
        control_cells[kind] = {
            "n_in_run": len(ids),
            "n_rows_in_label_csv": len(in_csv),
            "n_absent_from_label_csv": len(ids) - len(in_csv),
            "n_labeled_by_presence": len(labeled),
            "n_unlabeled": len(ids) - len(labeled),
        }
        if labels.controls_read:  # --controls-valid: aggregate counts only, never per cell
            control_cells[kind]["n_label_A0"] = sum(
                labels.control_a.get(cid) == 0 for cid in ids)
            control_cells[kind]["n_label_A1"] = sum(
                labels.control_a.get(cid) == 1 for cid in ids)
    n_primary = sum(kind == CELL_KIND_PRIMARY for kind in kinds.values())
    total = n_primary if exclude_controls else len(cells)
    return scored, {
        "source_csv": str(labels.path),
        "source": labels.source,
        "simulated": labels.simulated,
        "mode": "registered subset" if registered_subset else (
            "partial allowed" if omitted else "complete"
        ),
        "total_cells": total,
        "total_run_cells": len(cells),
        "labeled_cells": len(scored),
        "unlabeled_cells": len(omitted),
        "unlabeled_cell_ids": sorted(omitted),
        "coverage_fraction": len(scored) / total if total else None,
        "coverage_denominator": {
            "n_cells": len(scored),
            "max_points": len(scored) * 3,
            "formula": "sum(L1_star) / (labeled_cells * 3) * 100",
        },
        "controls_excluded_from_scored": bool(exclude_controls),
        "control_values_read": bool(labels.controls_read),
        "control_cells": control_cells,
    }


def _infer_legacy_source(cells: list[dict]) -> tuple[str, bool]:
    """Infer provenance only from explicit JSONL markers; unknown stays unknown."""
    if cells and all(bool(cell.get("SIMULATED")) for cell in cells):
        return "LLM, not human", True
    values = []
    for cell in cells:
        raw = cell.get("label_source")
        if not raw:
            continue
        try:
            values.append(canonical_label_source(str(raw)))
        except ValueError:
            continue
    if values and len(set(values)) == 1:
        return values[0]
    return "unknown", False


def quadratic_weighted_kappa(
    left: dict[str, int], right: dict[str, int], maximum: int = 3
) -> float:
    """Point estimate for the preregistered washout G2 diagnostic."""
    if set(left) != set(right):
        raise ValueError("rater_L1 cell_id sets differ; G2 requires matched cells")
    ids = sorted(left)
    if not ids:
        raise ValueError("no matched rater_L1 scores for G2")
    if any(value < 0 or value > maximum for value in (*left.values(), *right.values())):
        raise ValueError("rater_L1 scores must be in 0..3")
    n = len(ids)
    observed = sum((left[cell] - right[cell]) ** 2 for cell in ids) / n
    left_counts = [sum(value == score for value in left.values()) for score in range(maximum + 1)]
    right_counts = [sum(value == score for value in right.values()) for score in range(maximum + 1)]
    expected = sum(
        left_counts[i] * right_counts[j] * (i - j) ** 2
        for i in range(maximum + 1)
        for j in range(maximum + 1)
    ) / (n * n)
    if expected == 0:
        return 1.0 if observed == 0 else 0.0
    return 1.0 - observed / expected


def _qwk_from_values(left, right, maximum: int = 3) -> float:
    """Quadratic-weighted kappa of two integer score vectors (the statistic that
    the G4 bootstrap recomputes on every resample; same formula as
    ``quadratic_weighted_kappa``): 1 - observed / expected with weights (i-j)^2.
    When the expected disagreement is 0 (both raters constant) it is 1.0 if they
    agree and 0.0 otherwise, as in ``quadratic_weighted_kappa``."""
    left = np.asarray(left, dtype=int)
    right = np.asarray(right, dtype=int)
    n = len(left)
    if n == 0 or n != len(right):
        raise ValueError("QWK needs two equally long, non-empty score vectors")
    levels = np.arange(maximum + 1)
    observed = float(np.mean((left - right) ** 2))
    lc = np.bincount(left, minlength=maximum + 1)[: maximum + 1].astype(float)
    rc = np.bincount(right, minlength=maximum + 1)[: maximum + 1].astype(float)
    expected = float(np.sum(lc[:, None] * rc[None, :]
                            * (levels[:, None] - levels[None, :]) ** 2)) / (n * n)
    if expected == 0:
        return 1.0 if observed == 0 else 0.0
    return 1.0 - observed / expected


def washout_qwk(primary: LabelSet, washout: LabelSet, *, exclude_ids=()) -> dict:
    """Compute G2 on the washout IDs using matched primary rater_L1 scores.

    ``exclude_ids`` are control cells: a washout sheet drawn from the full run
    can contain them, and a control row is never part of a primary statistic.
    They are dropped from the matched set and counted in ``n_control_excluded``
    (so ``n`` is the number of PRIMARY washout cells actually used).
    """
    exclude = frozenset(str(x) for x in exclude_ids)
    washout_ids = [cid for cid in washout.rater_l1 if cid not in exclude]
    n_excluded = len(washout.rater_l1) - len(washout_ids)
    extra = sorted(set(washout_ids) - set(primary.rater_l1))
    if extra:
        raise ValueError(
            f"washout CSV contains cell_id(s) absent from primary labels: {extra}"
        )
    missing = sorted(
        cell_id
        for cell_id in washout_ids
        if primary.rater_l1[cell_id] is None or washout.rater_l1[cell_id] is None
    )
    if missing:
        raise ValueError(
            f"rater_L1 is blank for G2 cell_id(s): {missing}. "
            "Both primary and washout scores are required."
        )
    ids = sorted(washout_ids)
    left = {cell_id: int(primary.rater_l1[cell_id]) for cell_id in ids}  # type: ignore[arg-type]
    right = {cell_id: int(washout.rater_l1[cell_id]) for cell_id in ids}  # type: ignore[arg-type]
    return {
        "intra_rater_qwk": quadratic_weighted_kappa(left, right),
        "n": len(ids),
        "n_control_excluded": n_excluded,
        "score_column": "rater_L1",
        "metric": "G2 preregistered intra-rater quadratic-weighted kappa",
        "ci_note": "Report the preregistered clustered CI separately; this utility reports the point estimate only.",
    }


def _gate(status: str, value=None, threshold=None, reason: str = "", **extra) -> dict:
    """Build the common gate result envelope."""
    if status not in {"pass", "fail", "not_computable", "not_falsified"}:
        raise ValueError(f"invalid gate status: {status!r}")
    out = {"status": status, "value": value, "threshold": threshold,
           "reason": reason}
    out.update(extra)
    return out


def _numeric(value, *, minimum=None, maximum=None):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if minimum is not None and number < minimum:
        return None
    if maximum is not None and number > maximum:
        return None
    return number


G3_REGISTERED_N = 24
G3_MIN_UNSUPPORTED = 22


def _g3_registered(ablated: dict | None) -> dict:
    """G3 as registered (PREREG L345 "evaluator negative control: the ablated
    cells marked unsupported, >= 22/24"; L991 reports the same quantity as
    "ablated-control cells with A=0"): the EVALUATOR's A on the 24 ablated
    controls, where A=0 means the evaluator judged the cell unsupported.  It is
    NOT read from any judge-JSON verdict key.  It is computed only when the
    operator asserted ``--controls-valid`` (the control labels were produced
    blind and may be used); ``ablated`` holds the aggregate counts from the
    label CSV (``n_in_run``, ``n_label_A0``, ``n_label_A1``)."""
    threshold = G3_MIN_UNSUPPORTED / G3_REGISTERED_N
    ab = ablated or {}
    n_run = ab.get("n_in_run", 0)
    a0, a1 = ab.get("n_label_A0"), ab.get("n_label_A1")
    counts = {"n_in_run": n_run, "n_unsupported_A0": a0, "n_supported_A1": a1}
    if n_run != G3_REGISTERED_N:
        return _gate("not_computable", None, threshold,
                     f"registered G3 needs exactly {G3_REGISTERED_N} ablated_control cells; "
                     f"the run has {n_run}", counts=counts, controls_valid_asserted=True)
    if a0 is None or a1 is None:
        return _gate("not_computable", None, threshold,
                     "the control A values were not read", counts=counts,
                     controls_valid_asserted=True)
    if a0 + a1 != G3_REGISTERED_N:
        return _gate("not_computable", None, threshold,
                     f"only {a0 + a1} of the {G3_REGISTERED_N} ablated cells carry an A "
                     "(the registered gate needs all of them)", counts=counts,
                     controls_valid_asserted=True)
    status = "pass" if a0 >= G3_MIN_UNSUPPORTED else "fail"
    return _gate(status, a0 / G3_REGISTERED_N, threshold,
                 f"{a0}/{G3_REGISTERED_N} ablated controls were marked unsupported (A=0) "
                 f"by the evaluator (need >= {G3_MIN_UNSUPPORTED})",
                 n_unsupported=a0, n_supported=a1, n_controls=G3_REGISTERED_N,
                 registered_n=G3_REGISTERED_N, evaluator_field="A (human label CSV)",
                 controls_valid_asserted=True)


def _g3_controls_excluded(control_cells: dict, *, controls_valid: bool = False) -> dict:
    """G3 when it cannot be computed: the default (control labels are never read
    without ``--controls-valid``), or the control rows are excluded and the
    needed counts are absent.  The result is ``not_computable`` with explicit
    reasons and the control counts.  Counts are BY PRESENCE of a label cell
    only: no control label value is read and none of the numbers depends on
    one."""
    threshold = G3_MIN_UNSUPPORTED / G3_REGISTERED_N
    unknown = {"n_in_run": 0, "n_labeled_by_presence": None, "n_unlabeled": None}
    kinds = {kind: dict(control_cells.get(kind) or unknown) for kind in CONTROL_CELL_KINDS}

    def fmt(value):
        return "unknown" if value is None else value

    def total(key):
        values = [kinds[k].get(key) for k in kinds]
        return None if any(v is None for v in values) else sum(values)

    all_c = {"n_in_run": total("n_in_run"), "n_labeled_by_presence": total("n_labeled_by_presence"),
             "n_unlabeled": total("n_unlabeled")}
    ab, pr = kinds["ablated_control"], kinds["preserved_control"]
    reasons = [
        "analysis rule: ablated_control and preserved_control rows are excluded "
        "from every human-label-based statistic, and their label values are not "
        "read unless --controls-valid asserts that they are valid",
        f"registered G3 needs the evaluator's A on all {G3_REGISTERED_N} ablated cells "
        f"and >= {G3_MIN_UNSUPPORTED}/{G3_REGISTERED_N} unsupported; ablated_control rows in "
        f"the run: {fmt(ab.get('n_in_run'))}, with a label cell: "
        f"{fmt(ab.get('n_labeled_by_presence'))}, unlabeled: {fmt(ab.get('n_unlabeled'))}",
        f"preserved_control rows in the run: {fmt(pr.get('n_in_run'))}, with a label cell: "
        f"{fmt(pr.get('n_labeled_by_presence'))}, unlabeled: {fmt(pr.get('n_unlabeled'))}",
        f"all control rows: {fmt(all_c['n_in_run'])} in the run, "
        f"{fmt(all_c['n_labeled_by_presence'])} with a label cell, "
        f"{fmt(all_c['n_unlabeled'])} unlabeled (counted by presence; no value was read)",
    ]
    if controls_valid:
        reasons.insert(0, "--controls-valid was given but the control A values are "
                          "not available to this call")
    return _gate("not_computable", None, threshold, "; ".join(reasons[:2]),
                 reasons=reasons, counted_by="presence of a label cell, never by value",
                 counts={"ablated_control": ab, "preserved_control": pr, "all_controls": all_c},
                 registered_n_ablated=G3_REGISTERED_N,
                 registered_min_unsupported=G3_MIN_UNSUPPORTED)


def _key_strata(cells: list[dict], key_field: str, strata_key: str | None):
    """Map ``str(cell[key_field])`` -> ``str(cell[strata_key])`` for stratified
    resampling (None when unstratified).  Every key must have exactly one
    stratum; a missing value or a key split across strata is an error."""
    if strata_key is None:
        return None
    out: dict[str, str] = {}
    for c in cells:
        key = str(c.get(key_field, ""))
        raw = c.get(strata_key)
        if raw is None or not str(raw).strip():
            raise ValueError(f"cell {key!r} has no {strata_key!r} value for stratified resampling")
        if out.setdefault(key, str(raw)) != str(raw):
            raise ValueError(f"{key_field} {key!r} spans strata {out[key]!r} and {str(raw)!r}")
    return out


def _mean_err(records: list[dict]) -> float:
    return float(np.mean([r["err"] for r in records]))


def _g5(cells: list[dict], seed: int, strata_key: str | None = None,
        resamples: int = BOOTSTRAP_RESAMPLES, detail: dict | None = None,
        ties: str = DEFAULT_BCA_TIES) -> dict:
    """G5 = MAE(J, H) over the primary cells.

    H is the HUMAN's fresh 0..3 score ``rater_L1`` from the label CSV and J the
    judge's raw score; neither A nor L1* is involved.  The point estimate is the
    POOLED mean of |J - rater_L1| over cells, and the interval bootstraps that
    same statistic (whole-cluster resampling of the pooled mean) through
    ``cluster_bootstrap_stat``: the reported value is the bootstrap's own point
    estimate, so value and interval cannot describe different quantities.
    """
    threshold = 0.50
    missing = [str(c.get("cell_id", c.get("cq_id", i)))
               for i, c in enumerate(cells) if "rater_L1" not in c]
    if missing:
        if detail is not None:
            detail["g5_cells_missing_rater_L1"] = missing
        return _gate("not_computable", None, threshold,
                     f"rater_L1 is missing for {len(missing)} cell(s)",
                     n_missing_rater_L1=len(missing))
    if not cells:
        return _gate("not_computable", None, threshold, "no cells")
    records = []
    for i, c in enumerate(cells):
        j = _strict_j(c.get("J"), f"J at cell {i}")
        h = _strict_j(c.get("rater_L1"), f"rater_L1 at cell {i}")  # same int 0..3 rule
        record = {"cluster_id": str(c.get("cluster_id", "")), "err": abs(j - h)}
        if strata_key is not None:
            record[strata_key] = c.get(strata_key)
        records.append(record)
    clusters = {r["cluster_id"] for r in records}
    if "" in clusters or len(clusters) < 2:
        return _gate("not_computable", None, threshold,
                     "MAE CI requires at least two non-empty CQ clusters")
    boot = cluster_bootstrap_stat(records, _mean_err, strata_key, "cluster_id",
                                  resamples, seed, ties)
    value = boot["estimate"]
    status = "pass" if boot["ci_hi"] <= threshold else "fail"
    return _gate(status, value, threshold,
                 f"MAE={value:.6g}; BCa upper CI={boot['ci_hi']:.6g}",
                 ci_lo=boot["ci_lo"], ci_hi=boot["ci_hi"],
                 n_cells=len(records), n_clusters=boot["n_clusters"],
                 resamples=boot["B"], seed=boot["seed"], bca_ties=ties,
                 strata_key=strata_key, judge_field="J", human_field="rater_L1",
                 estimator="pooled mean of |J - rater_L1| over cells",
                 method="CQ-cluster BCa bootstrap of the pooled mean "
                        "(cluster_bootstrap_stat)")


def _secondary_score(cell: dict):
    keys = ("non_qwen_J", "non_qwen_score", "J_non_qwen", "secondary_J",
            "secondary_judge_score", "judge2_J", "J_secondary")
    for key in keys:
        if key in cell:
            return _numeric(cell[key], minimum=0, maximum=3)
    for key in ("non_qwen_judge", "secondary_judge", "judge_2",
                "judge_response_non_qwen", "non_qwen_judge_response",
                "secondary_judge_response", "judge2_response"):
        nested = cell.get(key)
        if isinstance(nested, dict):
            for score_key in ("J", "score", "value"):
                if score_key in nested:
                    return _numeric(nested[score_key], minimum=0, maximum=3)
    return None


def _direction(cells: list[dict], score_key: str | None = None) -> float | None:
    by_variant: dict[str, dict[str, list[float]]] = {}
    # Controls and other variants are irrelevant to the registered A->B
    # direction and must not make a secondary judge look incomplete.
    relevant = [c for c in cells if str(c.get("variant")) in {"A", "B"}]
    for c in relevant:
        score = (_numeric(c.get("L1_star"), minimum=0, maximum=3)
                 if score_key is None else _secondary_score(c))
        if score is None:
            return None
        by_variant.setdefault(str(c.get("variant")), {}).setdefault(
            str(c.get("cq_id")), []).append(score)
    if "A" not in by_variant or "B" not in by_variant:
        return None
    qids = sorted(set(by_variant["A"]) & set(by_variant["B"]))
    if not qids:
        return None
    deltas = [np.mean(by_variant["B"][q]) - np.mean(by_variant["A"][q])
              for q in qids]
    return float(np.mean(deltas))


def _paired_ab_deltas(cells: list[dict]) -> tuple[dict[str, float], dict[str, str]] | None:
    """(delta per CQ, cluster of each CQ) for the CQs that have both an A and a B cell."""
    by_q: dict[str, dict[str, list[float]]] = {}
    cluster_of: dict[str, str] = {}
    for c in cells:
        variant = str(c.get("variant"))
        if variant not in {"A", "B"}:
            continue
        score = _numeric(c.get("L1_star"), minimum=0, maximum=3)
        if score is None:
            return None
        q = str(c.get("cq_id"))
        by_q.setdefault(q, {}).setdefault(variant, []).append(score)
        cluster = str(c.get("cluster_id", q))
        if cluster_of.setdefault(q, cluster) != cluster:
            raise ValueError(f"CQ {q!r} appears in more than one cluster")
    qids = sorted(q for q, vals in by_q.items() if "A" in vals and "B" in vals)
    if not qids:
        return None
    return ({q: float(np.mean(by_q[q]["B"]) - np.mean(by_q[q]["A"])) for q in qids},
            {q: cluster_of[q] for q in qids})


def _ab_distinguishable(deltas: dict[str, float], cluster_of: dict[str, str], seed: int,
                        strata=None, resamples: int = BOOTSTRAP_RESAMPLES,
                        ties: str = DEFAULT_BCA_TIES) -> tuple[bool, dict]:
    """Is the A->B interval above zero?  One record per CQ; the cluster is
    resampled and the statistic is the POOLED mean of the per-CQ deltas, the
    same form as the primary contrast.  ``strata`` maps cluster -> stratum."""
    records = []
    for q in sorted(deltas):
        rec = {"cluster_id": cluster_of[q], "d": deltas[q]}
        if strata is not None:
            rec["stratum"] = strata[cluster_of[q]]
        records.append(rec)
    boot = cluster_bootstrap_stat(records, _mean_d, "stratum" if strata is not None else None,
                                  "cluster_id", resamples, seed, ties)
    return boot["ci_lo"] > 0, {"delta": boot["estimate"], "ci_lo": boot["ci_lo"],
                               "ci_hi": boot["ci_hi"], "n_clusters": boot["n_clusters"]}


def fragility_k(cells: list[dict], *, seed: int = 20260913,
                low: str = "A", high: str = "B",
                strata_key: str | None = None,
                resamples: int = BOOTSTRAP_RESAMPLES,
                ties: str = DEFAULT_BCA_TIES) -> dict:
    """Minimum CQ-level one-step demotions making A->B unresolved.

    The demotions are applied to the CQs most favourable to the positive A->B
    direction first.  ``K`` is the first step at which the clustered BCa CI
    includes zero; if no available one-step CQ move does so, the reported value
    is ``n_cq + 1`` and marked as a lower bound.
    """
    paired = _paired_ab_deltas(cells)
    if paired is None:
        return {"k": None, "reason": "no paired A/B CQs or invalid L1_star"}
    deltas, cluster_of = paired
    strata = _key_strata([c for c in cells if str(c.get("variant")) in {"A", "B"}],
                         "cluster_id", strata_key)
    current = float(np.mean(list(deltas.values())))
    distinguishable, initial_boot = _ab_distinguishable(
        deltas, cluster_of, seed, strata, resamples, ties)
    if not distinguishable:
        return {"k": 0, "n_cq": len(deltas), "initial_delta": current,
                "initial_ci_lo": initial_boot["ci_lo"], "moved_cq_ids": [],
                "criterion": "A->B BCa CI includes zero"}
    moved: list[str] = []
    working = dict(deltas)
    for q in sorted(deltas, key=lambda q: (deltas[q], q), reverse=True):
        # One label step cannot reduce a score below the rubric floor.  The
        # delta is capped to preserve the registered 0..3 Layer-1 scale.
        working[q] = max(-3.0, working[q] - 1.0)
        moved.append(q)
        distinguishable, boot = _ab_distinguishable(
            working, cluster_of, seed, strata, resamples, ties)
        if not distinguishable:
            return {"k": len(moved), "n_cq": len(deltas),
                    "initial_delta": current, "initial_ci_lo": initial_boot["ci_lo"],
                    "moved_cq_ids": moved, "ci_lo": boot["ci_lo"],
                    "criterion": "A->B BCa CI includes zero"}
    return {"k": len(deltas) + 1, "n_cq": len(deltas),
            "initial_delta": current, "initial_ci_lo": initial_boot["ci_lo"],
            "moved_cq_ids": moved, "lower_bound": True,
            "criterion": "A->B BCa CI remained above zero after all CQ moves"}

def _fragility_pi_not_implemented() -> dict:
    """PREREG sec.4 L574-584 item 2 ("how many before the pi interval exceeds
    10%") is NOT implemented: the registered text leaves its definition open.
    Item 1 (A->B) is implemented inside G6."""
    return {
        "status": "not_implemented",
        "registered_text": ("PREREG sec.4 L574-584, item 2: adversarially demote labels "
                            "one step until the pi interval exceeds 10%, and report how "
                            "many"),
        "reasons": [
            "unit of a move is undefined for pi: item 1 moves a CQ by lowering its paired "
            "A->B delta one step, but the text does not say whether a move for pi flips "
            "one cell's A (1->0), every J>=2 cell of a CQ, or a CQ-level quantity",
            "'the pi interval' is not pinned to one interval: sec.1.1 headlines the "
            "cell-level 95% BCa upper limit, G1 gates the cluster-level one-sided "
            "Clopper-Pearson bound, and the level of the latter is itself unresolved "
            "(L387-390)",
            "'the cells most favourable to the hypothesis' has no order or tie rule for pi "
            "(every flip adds exactly one event) and no K threshold is registered for "
            "item 2 (K=6 is the G6 threshold, attached to item 1)",
        ],
        "item_1_a_to_b": "computed inside G6 (gates.G6_consistency.value.fragility)",
    }


def _g6(cells: list[dict], contrasts: dict, *, seed: int,
        strata_key: str | None = None,
        resamples: int = BOOTSTRAP_RESAMPLES,
        ties: str = DEFAULT_BCA_TIES) -> dict:
    threshold = {"fragility_K": 6, "a_to_b": "consistent",
                 "non_qwen_direction": "agrees"}
    primary = contrasts.get("A->B")
    if primary is None:
        return _gate("not_computable", None, threshold,
                     "A->B contrast is not computable")
    a_to_b = bool(primary.get("delta", 0) > 0 and primary.get("ci_lo", 0) > 0)
    primary_direction = _direction(cells)
    non_qwen_direction = _direction(cells, score_key="non_qwen")
    fragility = fragility_k(cells, seed=seed, strata_key=strata_key,
                            resamples=resamples, ties=ties)
    if non_qwen_direction is None:
        return _gate("not_computable", {
            "a_to_b_consistent": a_to_b,
            "non_qwen_direction_agrees": None,
            "fragility": fragility,
        }, threshold,
                     "non-Qwen judge scores are absent or incomplete; G6 cannot pass")
    direction_agrees = bool(primary_direction is not None and
                            np.sign(primary_direction) == np.sign(non_qwen_direction) and
                            primary_direction != 0 and non_qwen_direction != 0)
    k = fragility.get("k")
    if k is None:
        return _gate("not_computable", {
            "a_to_b_consistent": a_to_b,
            "non_qwen_direction_agrees": direction_agrees,
            "fragility": fragility,
        }, threshold, fragility.get("reason", "fragility K is not computable"))
    value = {"a_to_b_consistent": a_to_b,
             "non_qwen_direction_agrees": direction_agrees,
             "fragility_K": k, "fragility": fragility}
    status = "pass" if a_to_b and direction_agrees and k >= 6 else "fail"
    return _gate(status, value, threshold,
                 "all G6 consistency components satisfied" if status == "pass"
                 else "one or more G6 consistency components failed")


def _parse_utc(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(datetime.timezone.utc)


# --------------------------------------------------------------------------
# labeling audit trail: the SOURCE of G7 (PREREG L349) and of the registered
# descriptive items.  It is label_assist's ``<out>.audit.jsonl``: one JSON
# object per line, either a save record (top-level ``cell_id`` and ``A``) or an
# event record (``event``, ``ts``, ``session_id``).  Judge-run telemetry in
# cells.jsonl is NOT an audit trail and is never read for G7.
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class AuditSave:
    """One save record.  Draft fields are normalised to ints (the audit stores
    ``draft_A``/``draft_L1`` as strings and ``A`` as an int)."""

    cell_id: str
    ts: datetime.datetime  # tz-aware UTC
    row: int | None
    a: int | None
    rater_l1: int | None  # the audit stores rater_L1 as a string ("" when none)
    elapsed_s: float | None
    session_id: str | None
    has_edit_reason: bool
    draft_a: int | None
    draft_l1: int | None
    changed: bool | None
    seq: int  # position in the file; breaks ts ties


@dataclass(frozen=True)
class AuditLog:
    path: str
    sha256: str
    saves: dict[str, tuple[AuditSave, ...]]  # cell_id -> saves in (ts, file) order
    n_lines: int
    n_save_records: int
    n_event_records: int
    event_counts: dict[str, int]
    n_unparseable_lines: int
    n_other_records: int
    n_save_records_unusable: int  # save-shaped, but no cell_id or no tz-aware ts
    scope: dict | None = None


def _small_int(value, allowed) -> int | None:
    """int from an int or a digit string; None otherwise.  bool is not an int."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        out = value
    elif isinstance(value, str) and value.strip() in {str(a) for a in allowed}:
        out = int(value.strip())
    else:
        return None
    return out if out in allowed else None


def load_label_audit(path: Path) -> AuditLog:
    """Parse a label_assist audit .jsonl.  Never raises on a bad LINE (it is
    counted, and G7 then refuses to pass); raises only if the file is absent."""
    if not path.is_file():
        raise ValueError(f"no label audit at {path}")
    raw = path.read_bytes()
    saves: dict[str, list[AuditSave]] = {}
    events: dict[str, int] = {}
    n_lines = n_save = n_event = n_bad = n_other = n_unusable = 0
    # "\n" only, as for the cells file: a U+2028 inside e.g. edit_reason must not split a record
    for seq, line in enumerate(raw.decode("utf-8").split("\n")):
        if not line.strip():
            continue
        n_lines += 1
        try:
            rec = json.loads(line)
        except ValueError:
            n_bad += 1
            continue
        if not isinstance(rec, dict):
            n_other += 1
            continue
        if "event" in rec and "cell_id" not in rec:
            n_event += 1
            name = str(rec["event"])
            events[name] = events.get(name, 0) + 1
            continue
        if "cell_id" not in rec or "A" not in rec:
            n_other += 1
            continue
        n_save += 1
        cell_id = str(rec["cell_id"]).strip()
        ts = _parse_utc(rec.get("ts"))
        if not cell_id or ts is None:
            n_unusable += 1
            continue
        row = rec.get("row")
        saves.setdefault(cell_id, []).append(AuditSave(
            cell_id=cell_id, ts=ts,
            row=row if isinstance(row, int) and not isinstance(row, bool) else None,
            a=_small_int(rec.get("A"), {0, 1}),
            rater_l1=_small_int(rec.get("rater_L1"), {0, 1, 2, 3}),
            elapsed_s=_numeric(rec.get("elapsed_s"), minimum=0),
            session_id=(str(rec["session_id"]) if rec.get("session_id") is not None else None),
            has_edit_reason=bool(str(rec.get("edit_reason") or "").strip()),
            draft_a=_small_int(rec.get("draft_A"), {0, 1}),
            draft_l1=_small_int(rec.get("draft_L1"), {0, 1, 2, 3}),
            changed=rec.get("changed") if isinstance(rec.get("changed"), bool) else None,
            seq=seq))
    return AuditLog(
        path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
        saves={cid: tuple(sorted(v, key=lambda s: (s.ts, s.seq))) for cid, v in saves.items()},
        n_lines=n_lines, n_save_records=n_save, n_event_records=n_event,
        event_counts=dict(sorted(events.items())), n_unparseable_lines=n_bad,
        n_other_records=n_other, n_save_records_unusable=n_unusable)


def audit_scope(audit: AuditLog, primary_ids, control_ids, run_ids) -> AuditLog:
    """Attach counts of how the audit's cell ids relate to the run (counts only)."""
    primary_ids, control_ids, run_ids = set(primary_ids), set(control_ids), set(run_ids)
    ids = set(audit.saves)
    return replace(audit, scope={
        "n_cell_ids_in_audit": len(ids),
        "n_primary_cells_with_saves": len(ids & primary_ids),
        "n_control_cells_with_saves_ignored": len(ids & control_ids),
        "n_cell_ids_not_in_run_ignored": len(ids - run_ids),
    })


G7_FAST_SECONDS = 20.0
G7_FAST_SHARE_BELOW = 0.03


def _g7(primary: list[dict], audit: AuditLog | None, unblind_boundary: str | None,
        detail: dict | None = None) -> dict:
    """G7 audit-trail integrity (PREREG L349), computed on LABELED PRIMARY cells
    from the labeling audit; judge-run telemetry is never read.

    (a) every labeled primary cell's save precedes the unblind boundary
        (share must be 100%; a labeled cell with no audit record counts as
        not-before);
    (b) no post-hoc edit: no primary-cell save at/after the boundary (count
        must be 0), AND the label CSV's A and rater_L1 equal those of the
        cell's LAST audit save -- a CSV value the audit never recorded was
        edited outside the tool.  Cells saved more than once are reported;
    (c) share of cells whose TOTAL dwell is < 20 s must be below 3%.  The total
        is the sum of ``elapsed_s`` over ALL saves of the cell (a re-save adds
        its time), so re-saving does not reset the clock.  Summing does not
        double-count: label_assist leaves the row page after every successful
        save, so each save's ``elapsed_s`` measures its own visit.  A cell with
        any save lacking a usable ``elapsed_s`` is not fast when the known part
        alone is already >= 20 s -- otherwise its dwell is unknown.
    For (a) the LAST save is the one that produced the stored label (its ts is
    used); (b) counts every save.  ``pass`` needs all three; any definite
    violation is ``fail``; otherwise anything unknowable (missing boundary,
    unknown elapsed_s, unreadable audit lines) is ``not_computable``.
    """
    threshold = {"before_boundary_share": 1.0, "primary_saves_after_boundary": 0,
                 "csv_audit_mismatches": 0,
                 "elapsed_under_20s_share_lt": G7_FAST_SHARE_BELOW}
    if audit is None:
        return _gate("not_computable", None, threshold,
                     "--label-audit is required: G7 is computed from the labeling audit "
                     "trail (PREREG L349), never from judge-run telemetry")
    boundary = _parse_utc(unblind_boundary) if unblind_boundary else None
    boundary_problem = None
    if not unblind_boundary:
        boundary_problem = "--unblind-boundary is required for conditions (a) and (b)"
    elif boundary is None:
        boundary_problem = ("--unblind-boundary must be ISO-8601 with an explicit UTC "
                            "offset; conditions (a) and (b) cannot be evaluated")

    n = len(primary)
    no_record, after_ids, multi_ids, edit_ids = [], [], [], []
    unknown_ids, fast_ids, mismatch_ids = [], [], []
    n_with = n_before = n_after_saves = n_fast = n_fast_last_save = 0
    n_mismatch_a = n_mismatch_h = 0
    for c in primary:
        cid = str(c.get("cell_id", ""))
        recs = audit.saves.get(cid, ())
        if not recs:
            no_record.append(cid)
            continue
        n_with += 1
        last = recs[-1]
        if len(recs) > 1:
            multi_ids.append(cid)
        if any(r.has_edit_reason for r in recs):
            edit_ids.append(cid)
        if boundary is not None:
            late = [r for r in recs if r.ts >= boundary]
            n_after_saves += len(late)
            if late:
                after_ids.append(cid)
            if last.ts < boundary:
                n_before += 1
        # (b) the CSV must say what the audit's last save said
        a_differs = last.a != c.get("A")
        h_differs = last.rater_l1 != c.get("rater_L1")
        if a_differs or h_differs:
            mismatch_ids.append(cid)
            n_mismatch_a += int(a_differs)
            n_mismatch_h += int(h_differs)
        # (c) TOTAL dwell over every save of the cell
        known = [r.elapsed_s for r in recs if r.elapsed_s is not None]
        if sum(known) < G7_FAST_SECONDS:
            if len(known) == len(recs):
                n_fast += 1
                fast_ids.append(cid)
            else:
                unknown_ids.append(cid)
        if last.elapsed_s is not None and last.elapsed_s < G7_FAST_SECONDS:
            n_fast_last_save += 1  # the former (last-save) basis, for comparison only

    n_mismatch = len(mismatch_ids)
    ok_a = ok_b = None
    if boundary is not None:
        ok_a = n_before == n
    if n_mismatch:
        ok_b = False  # a post-hoc edit, whether or not the boundary is known
    elif boundary is not None:
        ok_b = n_after_saves == 0
    lower = n_fast / n_with if n_with else None
    upper = (n_fast + len(unknown_ids)) / n_with if n_with else None
    if lower is None:
        ok_c = None
    elif lower >= G7_FAST_SHARE_BELOW:
        ok_c = False
    elif upper < G7_FAST_SHARE_BELOW:
        ok_c = True
    else:
        ok_c = None
    if no_record:
        ok_a = False  # a label with no audit record cannot be shown to precede the boundary
    integrity_gap = audit.n_unparseable_lines + audit.n_save_records_unusable

    conditions = {"a_all_labeled_primary_saved_before_boundary": ok_a,
                  "b_no_primary_save_after_boundary": ok_b,
                  "c_elapsed_under_20s_share_below_3pct": ok_c}
    if any(v is False for v in conditions.values()):
        status = "fail"
    elif any(v is None for v in conditions.values()) or integrity_gap:
        status = "not_computable"
    else:
        status = "pass"
    reasons = []
    if boundary_problem:
        reasons.append(boundary_problem)
    if ok_a is False:
        reasons.append(f"(a) {n_before}/{n} labeled primary cells saved before the boundary "
                       f"({len(no_record)} with no audit record)")
    if ok_b is False:
        parts = []
        if n_after_saves:
            parts.append(f"{n_after_saves} primary-cell save(s) at/after the boundary")
        if n_mismatch:
            parts.append(f"{n_mismatch} cell(s) whose CSV A/rater_L1 differ from the last "
                         "audit save (a post-hoc edit)")
        reasons.append("(b) " + "; ".join(parts))
    if ok_c is False:
        reasons.append(f"(c) {n_fast}/{n_with} cells under {G7_FAST_SECONDS:g} s total dwell "
                       f"(limit < {G7_FAST_SHARE_BELOW:.0%})")
    if ok_c is None and n_with:
        reasons.append(f"(c) {len(unknown_ids)} cell(s) have an unknown total dwell (a save "
                       "without a usable elapsed_s)")
    if integrity_gap and status != "fail":
        reasons.append(f"audit has {audit.n_unparseable_lines} unparseable line(s) and "
                       f"{audit.n_save_records_unusable} unusable save record(s)")
    value = {
        "n_labeled_primary": n,
        "n_with_audit_record": n_with,
        "n_without_audit_record": len(no_record),
        "before_boundary_share": (n_before / n) if boundary is not None and n else None,
        "n_primary_saves_after_boundary": n_after_saves if boundary is not None else None,
        "n_cells_saved_after_boundary": len(after_ids) if boundary is not None else None,
        "n_csv_audit_mismatch": n_mismatch,
        "n_csv_audit_mismatch_A": n_mismatch_a,
        "n_csv_audit_mismatch_rater_L1": n_mismatch_h,
        "n_cells_saved_more_than_once": len(multi_ids),
        "n_cells_with_edit_reason_save": len(edit_ids),
        "elapsed_basis": ("total dwell: the sum of elapsed_s over ALL saves of a cell (a "
                          "re-save adds its time); a cell is counted under 20 s only if "
                          "every save has a usable elapsed_s and the total is < 20 s"),
        "elapsed_under_20s_share": (n_fast / n_with) if n_with and not unknown_ids else None,
        "elapsed_under_20s_share_bounds": [lower, upper],
        "n_under_20s": n_fast,
        "n_under_20s_last_save_basis": n_fast_last_save,
        "n_elapsed_unknown": len(unknown_ids),
        "boundary_utc": boundary.isoformat() if boundary is not None else None,
        "audit": {"n_lines": audit.n_lines, "n_save_records": audit.n_save_records,
                  "n_event_records": audit.n_event_records,
                  "event_counts": audit.event_counts,
                  "n_unparseable_lines": audit.n_unparseable_lines,
                  "n_other_records": audit.n_other_records,
                  "n_save_records_unusable": audit.n_save_records_unusable,
                  "scope": audit.scope},
    }
    if detail is not None:
        detail.update({"g7_cells_without_audit_record": no_record,
                       "g7_cells_saved_after_boundary": after_ids,
                       "g7_cells_saved_more_than_once": multi_ids,
                       "g7_cells_with_edit_reason_save": edit_ids,
                       "g7_cells_elapsed_unknown": unknown_ids,
                       "g7_cells_under_20s": fast_ids,
                       "g7_cells_csv_audit_mismatch": mismatch_ids})
    return _gate(status, value, threshold,
                 "; ".join(reasons) if reasons else
                 "all three audit-trail conditions hold",
                 conditions=conditions,
                 source="labeling audit trail (label_assist .audit.jsonl), labeled "
                        "primary cells only; judge-run telemetry is not read; (b) also "
                        "compares the label CSV with the last audit save; (c) uses the "
                        "total dwell over all saves of a cell")


G4_FAILS_IF_CI_UPPER_BELOW = 0.60
G4_REGISTERED_TEXT = (
    "PREREG L346: human-judge QWK, falsification-only -- FAIL if the CI upper bound is "
    "< 0.60, and the gate can never pass (L353-359); on failure the judge is declared "
    "uncalibrated and quantitative conclusions are restricted to the ASK-oracle track "
    "(L606); the CI is a CQ-cluster BCa, never a cell-level bootstrap (L569-572)")


def _qwk_stat(records: list[dict]) -> float:
    return _qwk_from_values([r["j"] for r in records], [r["h"] for r in records])


def _g4(primary: list[dict], override: dict | None, seed: int,
        strata_key: str | None = None, resamples: int = BOOTSTRAP_RESAMPLES,
        ties: str = DEFAULT_BCA_TIES, detail: dict | None = None) -> dict:
    """G4 = human-judge QWK: the QWK of the judge's J against the HUMAN's fresh 0..3
    score ``rater_L1``, pooled over the primary cells, with a 95% CQ-cluster BCa
    interval (B and the seed as registered; ``cluster_bootstrap_stat``).  The
    gate is falsification-only: ``fail`` when the CI upper bound is below 0.60,
    otherwise ``not_falsified`` -- it can never be ``pass``.  The 4x4 J x
    rater_L1 confusion counts are reported as an aggregate (no cell ids).
    ``override`` (an externally supplied diagnostic dict) bypasses the build."""
    name = "G4 human-judge QWK"

    def failed(data, value):
        return float(value) < G4_FAILS_IF_CI_UPPER_BELOW

    if override is not None:
        return _falsification_gate(override, name=name, threshold=G4_FAILS_IF_CI_UPPER_BELOW,
                                   value_key="ci_hi", failure_predicate=failed)
    missing = [str(c.get("cell_id", c.get("cq_id", i)))
               for i, c in enumerate(primary) if "rater_L1" not in c]
    if missing:
        if detail is not None:
            detail["g4_cells_missing_rater_L1"] = missing
        return _gate("not_computable", None, G4_FAILS_IF_CI_UPPER_BELOW,
                     f"rater_L1 is missing for {len(missing)} cell(s); G4 needs the human "
                     "score on every primary cell", falsification_only=True,
                     n_missing_rater_L1=len(missing), registered_text=G4_REGISTERED_TEXT)
    records = []
    confusion = [[0] * 4 for _ in range(4)]
    for i, c in enumerate(primary):
        j = _strict_j(c.get("J"), f"J at cell {i}")
        h = _strict_j(c.get("rater_L1"), f"rater_L1 at cell {i}")  # same int 0..3 rule
        confusion[j][h] += 1
        record = {"cluster_id": str(c.get("cluster_id", "")), "j": j, "h": h}
        if strata_key is not None:
            record[strata_key] = c.get(strata_key)
        records.append(record)
    clusters = {r["cluster_id"] for r in records}
    if not records or "" in clusters or len(clusters) < 2:
        return _gate("not_computable", None, G4_FAILS_IF_CI_UPPER_BELOW,
                     "the QWK CI needs at least two non-empty CQ clusters",
                     falsification_only=True, registered_text=G4_REGISTERED_TEXT)
    boot = cluster_bootstrap_stat(records, _qwk_stat, strata_key, "cluster_id",
                                  resamples, seed, ties)
    gate = _falsification_gate(
        {"ci_hi": boot["ci_hi"]}, name=name, threshold=G4_FAILS_IF_CI_UPPER_BELOW,
        value_key="ci_hi", failure_predicate=failed)
    gate.update(
        qwk=boot["estimate"], ci_lo=boot["ci_lo"], ci_hi=boot["ci_hi"], ci_level=RESOLVE_CI_LEVEL,
        n_cells=len(records), n_clusters=boot["n_clusters"], resamples=boot["B"],
        seed=boot["seed"], bca_ties=ties, strata_key=strata_key,
        judge_field="J", human_field="rater_L1",
        method="CQ-cluster BCa bootstrap of the pooled QWK (cluster_bootstrap_stat); "
               "a cell-level bootstrap is not used",
        confusion={"rows": "J (judge)", "cols": "rater_L1 (human)", "levels": [0, 1, 2, 3],
                   "counts": confusion, "n_cells": len(records)},
        registered_text=G4_REGISTERED_TEXT,
        consequence_if_failed="judge declared uncalibrated; quantitative conclusions "
                              "restricted to the ASK-oracle track (PREREG L606)")
    return gate


def _falsification_gate(data: dict | None, *, name: str, threshold, value_key: str,
                        failure_predicate) -> dict:
    if data is None:
        return _gate("not_computable", None, threshold,
                     f"{name} has no registered diagnostic result; not_falsified is not claimed",
                     falsification_only=True)
    value = data.get(value_key, data.get("value")) if isinstance(data, dict) else None
    if value is None:
        return _gate("not_computable", None, threshold,
                     f"{name} diagnostic is missing its confidence bound",
                     falsification_only=True)
    failed = bool(failure_predicate(data, value))
    return _gate("fail" if failed else "not_falsified", value, threshold,
                 f"{name} falsification condition {'observed' if failed else 'not observed'}",
                 falsification_only=True)


# --------------------------------------------------------------------------
# registered DESCRIPTIVE items.  They use only the human labels, the AI drafts
# and the labeling audit -- never a judge score -- and are aggregates: no test,
# no p-value, no gate.
# --------------------------------------------------------------------------
def load_drafts_csv(path: Path) -> dict[str, dict[str, str]]:
    """cell_id -> draft record from the AH draft CSV (the 7-field header contract
    owned by validate_draft.py; the first occurrence of a cell wins, exactly as
    label_assist treats it)."""
    import validate_draft as vd  # sibling module; only needed when --drafts is used
    try:
        records = vd.load_draft_records(path)
    except vd.DraftContractError as exc:
        raise ValueError(str(exc)) from None
    out: dict[str, dict[str, str]] = {}
    for rec in records:
        out.setdefault(rec["cell_id"], rec)
    return out


def _rate(values) -> float | None:
    values = list(values)
    return float(np.mean(values)) if values else None


def _spearman(order, values) -> float | None:
    """Spearman rho (a descriptive statistic; no p-value is used or reported)."""
    values = np.asarray(values, dtype=float)
    if len(values) < 3 or float(np.std(values)) == 0.0:
        return None
    rho = stats.spearmanr(np.asarray(order, dtype=float), values).statistic
    return None if not math.isfinite(float(rho)) else float(rho)


ORDER_DRIFT_BINS = 5


def order_drift_diagnostic(primary: list[dict], audit: AuditLog | None) -> dict:
    """PREREG L551: "the order-drift diagnostic of the labels is pre-registered
    and reported".  The text names it and defines nothing else, so this is the
    MOST LITERAL reading, stated in the output: how the labels (A, rater_L1) of
    the labeled primary cells vary with the order in which they were saved.
    Order = rank of each cell's LAST save timestamp in the labeling audit (ties:
    sheet row, then cell_id).  Descriptive only: a rank correlation, per-
    quintile and per-session means.  No judge score is read."""
    reading = ("PREREG L551 names an order-drift diagnostic but does not define it; "
               "most literal reading: labels (A, rater_L1) of labeled primary cells vs "
               "the order in which they were saved (rank of the last save timestamp "
               "in the labeling audit); descriptive only, no test, no p-value")
    if audit is None:
        return {"status": "not_computable", "reading": reading,
                "reason": "--label-audit is required: the order comes from the audit "
                          "save timestamps"}
    entries = []
    for c in primary:
        recs = audit.saves.get(str(c.get("cell_id", "")), ())
        if recs:
            last = recs[-1]
            entries.append((last.ts, last.row if last.row is not None else 10 ** 9,
                            str(c["cell_id"]), c, last))
    entries.sort(key=lambda e: (e[0], e[1], e[2]))
    n = len(entries)
    if n < ORDER_DRIFT_BINS:
        return {"status": "not_computable", "reading": reading,
                "reason": f"{n} labeled primary cell(s) with an audit record; at least "
                          f"{ORDER_DRIFT_BINS} are needed for {ORDER_DRIFT_BINS} order bins",
                "n_cells": n}

    def summarise(idx) -> dict:
        members = [entries[i][3] for i in idx]
        h = [_strict_j(m["rater_L1"], "rater_L1") for m in members
             if m.get("rater_L1") is not None]
        return {"n": len(members), "A_rate": _rate(_strict_a(m["A"]) for m in members),
                "mean_rater_L1": _rate(h), "n_rater_L1": len(h)}

    order = list(range(1, n + 1))
    a_all = [_strict_a(e[3]["A"]) for e in entries]
    h_pairs = [(i + 1, _strict_j(e[3]["rater_L1"], "rater_L1")) for i, e in enumerate(entries)
               if e[3].get("rater_L1") is not None]
    bins = []
    for k, idx in enumerate(np.array_split(np.arange(n), ORDER_DRIFT_BINS), start=1):
        bins.append({"quintile": k, **summarise(idx.tolist())})
    by_session: dict[str, list[int]] = {}
    for i, e in enumerate(entries):
        by_session.setdefault(e[4].session_id or "unknown", []).append(i)
    ordered = sorted(by_session.values(), key=lambda idx: min(entries[i][0] for i in idx))
    return {
        "status": "computed",
        "reading": reading,
        "descriptive_only": True,
        "order_basis": "rank of the last save ts per cell (ties: sheet row, cell_id)",
        "n_cells": n,
        "n_primary_without_audit_record": len(primary) - n,
        "spearman_rho": {
            "order_vs_A": _spearman(order, a_all),
            "order_vs_rater_L1": _spearman([o for o, _ in h_pairs], [h for _, h in h_pairs]),
        },
        "n_order_bins": ORDER_DRIFT_BINS,
        "by_order_quintile": bins,
        "n_sessions": len(ordered),
        "by_session": [{"session_rank": k, **summarise(idx)}
                       for k, idx in enumerate(ordered, start=1)],
    }


def ah_correction_rates(primary: list[dict], *, drafts: dict | None = None,
                        audit: AuditLog | None = None,
                        label_spans: dict | None = None,
                        detail: dict | None = None) -> dict:
    """PREREG sec.11 (L1166-1167): the AH correction rate -- how often the human
    overturned the AI draft -- and its category distribution, as DESCRIPTIVE
    statistics only (no test, no bootstrap, no gate).

    * A changed: final human A (label CSV) != draft A.  The draft A comes from
      the draft file when given, else from the audit's ``draft_A`` (stored as a
      string "0"/"1"; compared as an int).  Reported overall, by CQ category
      and by direction (1->0, 0->1, kept).
    * span edited: the final stored ``evidence_span_verbatim`` != the draft
      ``span_draft`` (raw string comparison, the same rule label_assist uses
      for its ``changed`` flag); needs the draft file and the label CSV span
      column.  label_assist clears the span when A=0, so an A flip is itself a
      span edit; ``among_A1_both`` restricts to cells with draft A = final A = 1.
    * ``any_field_changed_per_audit``: the audit's own ``changed`` flag (any of
      A, L1, span or note differs from the draft).
    """
    definition = ("share of labeled primary cells (that have a draft) whose human A "
                  "differs from the AI draft's A, plus the share whose span was edited, "
                  "overall and by CQ category; descriptive only (PREREG sec.11, "
                  "L1166-1167)")
    if drafts is None and audit is None:
        return {"status": "not_computable", "definition": definition,
                "reason": "needs --drafts (draft file) and/or --label-audit (draft_A)"}
    rows = []
    disagree = 0
    for c in primary:
        cid = str(c.get("cell_id", ""))
        d_rec = drafts.get(cid) if drafts is not None else None
        a_file = _small_int(d_rec.get("A_draft"), {0, 1}) if d_rec else None
        recs = audit.saves.get(cid, ()) if audit is not None else ()
        a_audit = recs[-1].draft_a if recs else None
        if a_file is not None and a_audit is not None and a_file != a_audit:
            disagree += 1
        draft_a = a_file if a_file is not None else a_audit
        rows.append({"cell_id": cid, "category": str(c.get("category") or "unknown"),
                     "final_a": _strict_a(c["A"]), "draft_a": draft_a, "draft": d_rec,
                     "changed_flag": recs[-1].changed if recs else None})
    with_draft = [r for r in rows if r["draft_a"] is not None]
    span_ok = drafts is not None and label_spans is not None
    for r in with_draft:
        r["a_changed"] = r["final_a"] != r["draft_a"]
        r["span_edited"] = None
        if span_ok and r["draft"] is not None and r["cell_id"] in label_spans:
            r["span_edited"] = label_spans[r["cell_id"]] != r["draft"].get("span_draft", "")
    if detail is not None:
        detail["ah_cells_without_draft"] = [r["cell_id"] for r in rows
                                            if r["draft_a"] is None]
        detail["ah_per_cell"] = {r["cell_id"]: {"draft_A": r["draft_a"],
                                                "A_changed": r["a_changed"],
                                                "span_edited": r["span_edited"]}
                                 for r in with_draft}

    def a_block(rs) -> dict:
        k = sum(r["a_changed"] for r in rs)
        return {"n_with_draft": len(rs), "n_A_changed": k,
                "share": (k / len(rs)) if rs else None,
                "A_1_to_0": sum(r["draft_a"] == 1 and r["final_a"] == 0 for r in rs),
                "A_0_to_1": sum(r["draft_a"] == 0 and r["final_a"] == 1 for r in rs),
                "A_kept": len(rs) - k}

    def span_block(rs) -> dict:
        known = [r for r in rs if r["span_edited"] is not None]
        both = [r for r in known if r["draft_a"] == 1 and r["final_a"] == 1]
        return {"n_compared": len(known),
                "n_span_edited": sum(r["span_edited"] for r in known),
                "share": _rate(r["span_edited"] for r in known),
                "among_A1_both": {"n": len(both),
                                  "n_span_edited": sum(r["span_edited"] for r in both),
                                  "share": _rate(r["span_edited"] for r in both)}}

    flags = [r["changed_flag"] for r in with_draft if r["changed_flag"] is not None]
    out = {
        "status": "computed",
        "definition": definition,
        "descriptive_only": True,
        "draft_source": "draft file" if drafts is not None else "audit draft_A",
        "n_primary_labeled": len(rows),
        "n_with_draft": len(with_draft),
        "n_without_draft": len(rows) - len(with_draft),
        "draft_A_file_vs_audit_disagreements": disagree if (drafts and audit) else None,
        "A_changed": a_block(with_draft),
        "span_edited": (span_block(with_draft) if span_ok else {
            "status": "not_computable",
            "reason": "needs --drafts (draft span) and a label CSV with an "
                      "evidence_span_verbatim column"}),
        "any_field_changed_per_audit": ({
            "n_with_flag": len(flags), "n_changed": sum(flags),
            "share": _rate(flags)} if flags else {
            "status": "not_computable",
            "reason": "no audit save record carries a changed flag"}),
        "by_category": {},
    }
    for cat in sorted({r["category"] for r in with_draft}):
        rs = [r for r in with_draft if r["category"] == cat]
        entry = {"n_with_draft": len(rs), "A_changed_share": a_block(rs)["share"]}
        if span_ok:
            entry["span_edited_share"] = span_block(rs)["share"]
        out["by_category"][cat] = entry
    return out


def find_cell_level_leaks(text: str, ids) -> list[str]:
    """Cell/CQ identifiers that occur in ``text`` (used on the main results JSON
    before it is written; it must hold aggregates only).

    Matching is case-insensitive and an id counts wherever it is not part of a
    longer alphanumeric run, so ``A:CQB13`` (a variant:cq pair), ``CQB13_x`` and
    ``cqb13`` are all caught, while ``xCQB13`` and ``CQB130`` are not.  The
    canonical spelling of each leaked id is returned."""
    canonical: dict[str, str] = {}
    for raw in ids:
        text_id = str(raw)
        if text_id:
            canonical.setdefault(text_id.lower(), text_id)
    if not canonical:
        return []
    wanted = sorted(canonical, key=len, reverse=True)
    pattern = re.compile(r"(?<![A-Za-z0-9])(" + "|".join(re.escape(i) for i in wanted)
                         + r")(?![A-Za-z0-9])", re.IGNORECASE)
    return sorted({canonical[found.lower()] for found in pattern.findall(text)})


# --------------------------------------------------------------------------
# run-level guards: judge validity (B2) and the registered primary design (R2)
# --------------------------------------------------------------------------
def _judge_score_valid(cell: dict) -> bool:
    """Mirror of ``run_holdout._valid_score``: the judge JSON was parsed AND carries
    a numeric ``score`` whose integer part is 0..3.  (``call_judge`` reports
    parsed=True for ANY JSON, so a parsed response can still hold a bad score;
    ``score_cell`` then writes J=0.)  Unlike run_holdout, a NaN/inf score is
    invalid rather than an exception."""
    response = cell.get("judge_response")
    raw = response.get("score") if isinstance(response, dict) else None
    try:
        return (bool(cell.get("judge_response_parsed")) and isinstance(raw, (int, float))
                and int(raw) in range(4))
    except (ValueError, OverflowError):
        return False


def _judge_call_invalid(cell: dict) -> bool:
    """True when this cell's judge call did not produce a valid score.  run_holdout
    records a failed call with J=0, ``judge_response_parsed`` false and
    ``{"_error": ...}``, and an unparsable score as J=0 inside a parsed response --
    a score that does not exist, indistinguishable from a real 0 unless it is
    checked.  For a record in run_holdout's schema (both ``judge_response`` and
    ``judge_response_parsed`` present) the parsed score must be valid
    (``_judge_score_valid``) and J must equal it.  A cell without these keys
    (legacy/synthetic) is taken as valid."""
    if "judge_response_parsed" in cell and cell["judge_response_parsed"] is not True:
        return True
    response = cell.get("judge_response")
    if isinstance(response, dict) and "_error" in response:
        return True
    if "_error" in cell:
        return True
    if "judge_response" in cell and "judge_response_parsed" in cell:
        if not _judge_score_valid(cell):
            return True
        return cell.get("J") != int(cell["judge_response"]["score"])
    return False


def judge_validity(cells: list[dict]) -> dict:
    """Per-variant count of PRIMARY cells whose judge call is invalid."""
    by_variant: dict[str, dict] = {}
    for c in cells:
        if _cell_kind(c) != CELL_KIND_PRIMARY:
            continue
        slot = by_variant.setdefault(str(c.get("variant")), {"n_primary": 0, "n_invalid": 0})
        slot["n_primary"] += 1
        slot["n_invalid"] += int(_judge_call_invalid(c))
    return {
        "n_primary": sum(v["n_primary"] for v in by_variant.values()),
        "n_invalid": sum(v["n_invalid"] for v in by_variant.values()),
        "by_variant": {k: by_variant[k] for k in sorted(by_variant)},
    }


def invalid_judge_cell_ids(cells: list[dict]) -> list[str]:
    """Ids of the PRIMARY cells with an invalid judge call (for the sealed per-cell
    file and a refusal message; never part of the main results)."""
    return [str(c.get("cell_id", "")) for c in cells
            if _cell_kind(c) == CELL_KIND_PRIMARY and _judge_call_invalid(c)]


REGISTERED_VARIANTS = ("A", "B", "C", "D", "E", "F")
REGISTERED_BANK_CQ_IDS = tuple(f"CQB{i:02d}" for i in range(1, 37))
# PREREG sec.6-2 (L794-795): Q_A = Q minus 13 CQs (23 left); Q_v = Q minus 3 (33 left).
REGISTERED_EXCLUDED_CQS = {
    "A": frozenset(f"CQB{i:02d}" for i in (13, 14, 15, 18, 19, 20, 22, 23, 24, 32, 33, 35, 36)),
    **{v: frozenset(f"CQB{i:02d}" for i in (15, 22, 23)) for v in REGISTERED_VARIANTS[1:]},
}
REGISTERED_PRIMARY_SET = frozenset(
    (v, q) for v in REGISTERED_VARIANTS for q in REGISTERED_BANK_CQ_IDS
    if q not in REGISTERED_EXCLUDED_CQS[v])  # 23 + 5 * 33 = 188 cells


def check_registered_design(primary: list[dict]) -> tuple[dict, dict]:
    """Does the PRIMARY cell set equal the registered {A: Q_A (23), B-F: Q_v (33)}
    = 188 cells?  Returns (aggregate summary, cell-id lists for the per-cell file)."""
    observed = [(str(c.get("variant")), str(c.get("cq_id"))) for c in primary]
    observed_set = set(observed)
    missing = sorted(REGISTERED_PRIMARY_SET - observed_set)
    unexpected = sorted(observed_set - REGISTERED_PRIMARY_SET)
    by_variant = {}
    for v in sorted({v for v, _ in REGISTERED_PRIMARY_SET} | {v for v, _ in observed_set}):
        exp = {q for vv, q in REGISTERED_PRIMARY_SET if vv == v}
        obs = {q for vv, q in observed_set if vv == v}
        by_variant[v] = {"expected": len(exp), "observed": len(obs),
                         "n_missing": len(exp - obs), "n_unexpected": len(obs - exp)}
    n_dup = len(observed) - len(observed_set)
    summary = {
        "conforms": not missing and not unexpected and n_dup == 0,
        "expected_primary_cells": len(REGISTERED_PRIMARY_SET),
        "observed_primary_cells": len(observed),
        "n_missing": len(missing), "n_unexpected": len(unexpected),
        "n_duplicate_cells": n_dup, "by_variant": by_variant,
        "source": "PREREG sec.6-2 L789-795: Q_A = Q minus 13 documented corpus-rare CQs "
                  "(23 left); Q_B..F = Q minus 3 of them (33 left); 23 + 5*33 = 188 "
                  "primary cells (the CQ lists are in PREREG, not repeated here)",
    }
    ids = {"registered_design_missing_cells": [f"{v}:{q}" for v, q in missing],
           "registered_design_unexpected_cells": [f"{v}:{q}" for v, q in unexpected]}
    return summary, ids


def _move_id_lists(node, detail: dict, path: str = "") -> None:
    """Replace every identifier list (any key ending in ``_ids`` that holds a list)
    by its count, in place; the list itself goes to ``detail``.  This is what
    keeps the main results free of cell/CQ identifiers whatever a gate adds."""
    if isinstance(node, dict):
        for key in list(node):
            value = node[key]
            if isinstance(key, str) and key.endswith("_ids") and isinstance(value, list):
                detail[f"{path}{key}"] = value
                node[f"n_{key}"] = len(value)
                del node[key]
            else:
                _move_id_lists(value, detail, f"{path}{key}.")
    elif isinstance(node, list):
        for item in node:
            _move_id_lists(item, detail, path)


def analyse(
    cells: list[dict],
    seed: int,
    g1_alpha: float = 0.025,
    *,
    label_source: str | None = None,
    simulated: bool | None = None,
    label_metadata: dict | None = None,
    g2: dict | None = None,
    g4: dict | None = None,
    g8: dict | None = None,
    label_audit: AuditLog | None = None,
    unblind_boundary: str | None = None,
    bootstrap_strata: str | None = None,
    bootstrap_resamples: int = BOOTSTRAP_RESAMPLES,
    bca_ties: str = DEFAULT_BCA_TIES,
    controls_valid: bool = False,
    cell_detail: dict | None = None,
) -> dict:
    """All pre-registered statistics over the PRIMARY cells of ``cells``.

    Control cells (``cell_kind`` ablated/preserved) may be present in
    ``cells``; they are counted and reported, never analysed -- except that G3
    (the registered negative control) still receives them.  ``bootstrap_strata``
    is the cell field to stratify the cluster bootstrap by (None = registered
    unstratified scheme); ``bootstrap_resamples`` is B (registered: 10,000;
    lower only in tests).

    The returned dict holds AGGREGATES ONLY: no cell-level judge or human value
    and no cell/CQ identifier.  Identifier lists (unlabeled cells, G7 cells,
    fragility CQs, ...) are written into ``cell_detail`` when a dict is passed
    -- the registered CLI sends that to the separate ``--out-cells`` file.
    G7 needs ``label_audit`` (the labeling audit) and ``unblind_boundary``.
    G3 (the evaluator's A on the 24 ablated controls) is computed only with
    ``controls_valid=True``; by default it is not_computable and no control
    label is read.
    """
    id_sink: dict = cell_detail if cell_detail is not None else {}
    if g1_alpha not in (0.05, 0.025):
        raise ValueError("g1_alpha must be 0.05 (95%) or 0.025 (97.5%)")
    if bca_ties not in BCA_TIES_CHOICES:
        raise ValueError(f"bca_ties must be one of {BCA_TIES_CHOICES}, got {bca_ties!r}")
    primary, controls = split_primary_and_controls(cells)
    if not primary:
        raise ValueError(
            "no primary cells to analyse: control cells never enter a primary statistic"
        )
    for c in primary:  # controls' A is never read here
        if "L1_star" not in c:
            c["L1_star"] = (demote(c["J"], c["A"]) if "A" in c else _strict_j(c["J"]))
    _assert_unique_primary_pairing(primary)
    B = bootstrap_resamples
    cluster_strata = _key_strata(primary, "cluster_id", bootstrap_strata)
    variants = sorted({c["variant"] for c in primary})
    by_variant = {v: [c for c in primary if c["variant"] == v] for v in variants}
    result = {
        "primary_endpoint": "Layer-1 coverage on adjudicated L1*",
        "coverage_pct": {v: coverage([c["L1_star"] for c in cs])
                         for v, cs in by_variant.items()},
        "contrasts": {}, "gates": {},
        "label_source": label_source if label_source is not None else "unknown",
        "SIMULATED": bool(simulated) if simulated is not None else False,
    }
    result["bootstrap"] = {
        "method": "BCa cluster bootstrap (one helper: cluster_bootstrap_stat)",
        "resamples": B,
        "seed": seed,
        "registered_seed": REGISTERED_SEED,
        "seed_is_registered": seed == REGISTERED_SEED,
        "resample_unit": "semantic cluster (cluster_id)",
        "strata_key": bootstrap_strata,
        "bca_ties": bca_ties,
        "resolved_ci_level": RESOLVE_CI_LEVEL,
        "equivalence_ci_level": EQUIVALENCE_CI_LEVEL,
        "registered_scheme": (bootstrap_strata is None and B == BOOTSTRAP_RESAMPLES
                              and bca_ties == DEFAULT_BCA_TIES),
        "note": (
            "PREREG sec.4 registers BCa, 10,000 resamples, a pre-registered seed "
            "and the semantic cluster as the unit; it does not register "
            "stratification by category. strata_key=null is the registered scheme. "
            "bca_ties=midrank is the scipy BCa convention; strict is the former "
            "z0 rule, kept only as a sensitivity switch."
        ),
    }
    result["analysis_population"] = {
        "rule": ("primary cells only (cell_kind == 'primary'); ablated_control and "
                 "preserved_control rows never enter Coverage, contrasts, pi-hat, "
                 "G1, G2, G5, G6, G7 or fragility"),
        "n_primary_cells": len(primary),
        "n_primary_clusters": len({str(c["cluster_id"]) for c in primary}),
        "n_cells_by_variant": {v: len(cs) for v, cs in by_variant.items()},
        "control_cells_in_analyse_input": {k: len(v) for k, v in controls.items() if v},
        "cluster_id_equals_cq_id": all(
            str(c.get("cluster_id")) == str(c.get("cq_id")) for c in primary),
    }
    if label_metadata is not None:
        # aggregates only: the id list goes to the per-cell detail, the count stays
        result["label_coverage"] = {k: v for k, v in label_metadata.items()
                                    if k != "unlabeled_cell_ids"}
        id_sink["unlabeled_primary_cell_ids"] = list(
            label_metadata.get("unlabeled_cell_ids") or [])
        if label_metadata.get("control_cells"):
            result["analysis_population"]["control_rows_in_label_join"] = (
                label_metadata["control_cells"])

    result["coverage_detail"] = {}
    for v, cs in by_variant.items():
        detail = {"coverage_pct": result["coverage_pct"][v], "n_cells": len(cs),
                  "n_clusters": len({str(c["cluster_id"]) for c in cs}),
                  "ci_lo_pct": None, "ci_hi_pct": None}
        if detail["n_clusters"] >= 2:
            boot = cluster_bootstrap_stat(
                cs, lambda sample: coverage([c["L1_star"] for c in sample]),
                bootstrap_strata, "cluster_id", B, seed, bca_ties)
            detail.update(ci_lo_pct=boot["ci_lo"], ci_hi_pct=boot["ci_hi"],
                          ci_method="BCa cluster bootstrap", strata_key=boot["strata_key"],
                          strata_sizes=boot["strata_sizes"])
        else:
            detail["ci_reason"] = "fewer than two clusters: nothing to resample"
        result["coverage_detail"][v] = detail

    raw_p: dict[str, float] = {}
    members: dict[str, dict] = {}
    for lo, hi in CONFIRMATORY_CONTRASTS:
        name = f"{lo}->{hi}"
        absent = [v for v in (lo, hi) if v not in by_variant]
        if absent:
            members[name] = {"status": "not_computable",
                             "reason": f"variant(s) {absent} absent from this run"}
            continue
        lo_by_q = {c["cq_id"]: c for c in by_variant[lo]}  # primary only; one cell per cq
        records: list[dict] = []
        flat: list[float] = []
        for c in by_variant[hi]:
            if c["cq_id"] not in lo_by_q:
                continue
            d = c["L1_star"] - lo_by_q[c["cq_id"]]["L1_star"]
            record = {"cluster_id": c["cluster_id"], "d": float(d)}  # one record per question
            if bootstrap_strata is not None:
                record[bootstrap_strata] = c.get(bootstrap_strata)
            records.append(record)
            flat.append(d)
        if len({r["cluster_id"] for r in records}) < 2 or not flat:
            members[name] = {"status": "not_computable",
                             "reason": "fewer than two paired clusters"}
            continue
        # THE primary-contrast statistic: the POOLED mean of the per-question
        # differences (main.tex: "paired bootstrap on the mean per-question
        # difference"), clusters resampled; with cluster_id == cq_id it equals the
        # mean of the cluster means.
        boot = cluster_bootstrap_stat(records, _mean_d, bootstrap_strata, "cluster_id",
                                      B, seed, bca_ties)
        wil = wilcoxon_zeros_dropped(flat)
        agrees = _rank_agrees_in_sign(boot["estimate"], wil)
        decision = tost_decision(boot["ci_lo"], boot["ci_hi"],
                                 eq_lo=boot["ci90_lo"], eq_hi=boot["ci90_hi"])
        out = {
            "delta": boot["estimate"], "ci_lo": boot["ci_lo"], "ci_hi": boot["ci_hi"],
            "n_clusters": boot["n_clusters"], "n_questions": len(flat),
            "resamples": B, "seed": seed, "unit": "semantic cluster", "method": "BCa",
            "bca_ties": bca_ties, "strata_key": bootstrap_strata,
            "strata_sizes": boot["strata_sizes"],
            "estimator": "pooled mean of per-question differences, clusters resampled",
            "equivalence_interval": {
                "level": EQUIVALENCE_CI_LEVEL, "ci_lo": boot["ci90_lo"],
                "ci_hi": boot["ci90_hi"], "margin": TOST_MARGIN_L1,
                "basis": "TOST at alpha=.05 per side = the 90% two-sided interval "
                         "(main.tex L2205-2206: t_{0.95,35}*SD/sqrt(36)); PREREG.md "
                         "L306/L591-593 name the TOST interval without a level"},
            "wilcoxon": wil,
            "rank_test": {
                "test": "Wilcoxon signed-rank, zeros dropped, two-sided, on the per-question "
                        "differences over the paired CQs (the variants' CQ intersection)",
                "p": wil["p"], "n_nonzero": wil["n_nonzero"], "n_questions": len(flat),
                "w_plus": wil["w_plus"], "w_minus": wil["w_minus"],
                "direction": wil["sign"], "agrees_in_sign_with_delta": agrees,
                "registered_in_prereg": False, "applied_to_decision": False,
                "source": "main.tex (Three decisions paragraph and decision table); "
                          "PREREG.md registers no rank-test or sign-agreement rule",
            },
            "decision": decision,
            "decision_if_manuscript_rule": _decision_with_rank_rule(decision, agrees),
        }
        result["contrasts"][name] = out
        members[name] = {"status": "computed", "p": wil["p"]}
        if wil["p"] is not None:
            raw_p[name] = wil["p"]
    for name, adj in holm(raw_p, m=HOLM_FAMILY_SIZE).items():
        result["contrasts"][name]["p_holm"] = adj
        members[name]["p_holm"] = adj
    result["contrasts_family"] = {
        "registered_m": HOLM_FAMILY_SIZE,
        "rule": ("Holm over the registered family of m=2 (A->B, B->B'). A member that is "
                 "not computable stays in the family, so a lone computable contrast is "
                 "adjusted by m=2: p_holm = min(1, 2p)."),
        "members": members,
    }
    result["contrasts_note"] = (
        f"Holm applied over the registered family of m={HOLM_FAMILY_SIZE} confirmatory "
        "contrasts; a not-computable member (see contrasts_family) remains a member, so "
        "A->B alone gets min(1, 2p). 'resolved' means the 95% BCa interval excludes 0. The "
        "Wilcoxon signed-rank test is computed and reported (rank_test) but does NOT change "
        "'decision': the manuscript (main.tex) additionally requires the rank test to agree "
        "in sign, PREREG.md registers no such rule, and decision_if_manuscript_rule shows "
        "that variant. Holm's input p is the Wilcoxon p (PREREG.md registers the Holm "
        "family, not the p-value source). Everything else is exploratory and takes BH-FDR."
    )

    events, n = silent_over_credit(primary)
    g1_upper = clopper_pearson_upper(events, n, alpha=g1_alpha)
    g1_status = "pass" if g1_upper <= G1_UPPER_BOUND_THRESHOLD else "fail"
    result["pi_hat"] = silent_over_credit_rate(
        primary, strata_key=bootstrap_strata, B=B, seed=seed, ties=bca_ties)
    if result["pi_hat"]["events"] == 0:
        result["pi_hat"]["operative_upper_bound"] = g1_upper
        result["pi_hat"]["operative_upper_bound_method"] = (
            f"cluster-level one-sided Clopper-Pearson at {1.0 - g1_alpha:.3f} (the G1 bound)")
    result["gates"]["G1_silent_over_credit"] = _gate(
        g1_status, g1_upper, G1_UPPER_BOUND_THRESHOLD,
        f"Clopper-Pearson upper bound {'does' if g1_status == 'pass' else 'does not'} meet 10%",
        estimand="pi = Pr[J >= 2 AND A == 0]", events=events, n_clusters=n,
        n_cells=len(primary),
        pi_hat_is_a_lower_bound=events / n if n else None,
        upper_bound_one_sided=g1_upper, confidence_level=1.0 - g1_alpha,
        confidence_level_one_sided=1.0 - g1_alpha,
        method="Clopper-Pearson (bootstrap is prohibited for this quantity)",
        g1_achievable_at_registered_n=g1_achievability(n, g1_alpha),
        upper_bound_both_levels=_g1_both_levels(events, n, g1_alpha))

    if g2 is None:
        result["gates"]["G2_intra_rater_qwk"] = _gate(
            "not_computable", None, 0.70,
            "washout rater_L1 scores and a clustered CI are required")
    else:
        ci_lo = g2.get("ci_lo", g2.get("ci_lower"))
        if ci_lo is None:
            g2_gate = _gate("not_computable", g2.get("intra_rater_qwk"), 0.70,
                            "G2 point estimate is present but its preregistered CI lower bound is absent",
                            **g2)
        else:
            g2_extra = dict(g2)
            g2_extra["ci_lo"] = ci_lo
            g2_gate = _gate("pass" if ci_lo >= 0.70 else "fail",
                            g2.get("intra_rater_qwk", g2.get("value")), 0.70,
                            f"G2 CI lower bound={ci_lo}", **g2_extra)
        result["gates"]["G2_intra_rater_qwk"] = g2_gate

    # G3 is the registered negative control ON the ablated cells, so it is the
    # one gate that receives them (it reads a recorded verdict, never A).
    control_meta = (label_metadata or {}).get("control_cells") or {}
    if label_metadata is not None and label_metadata.get("controls_excluded_from_scored"):
        if controls_valid and label_metadata.get("control_values_read"):
            g3 = _g3_registered(control_meta.get("ablated_control"))
        else:
            g3 = _g3_controls_excluded(control_meta, controls_valid=controls_valid)
    elif controls_valid and controls["ablated_control"]:
        ablated = controls["ablated_control"]
        values = [_strict_a(c["A"], f"A of {c.get('cell_id')!r}")
                  for c in ablated if c.get("A") is not None]
        g3 = _g3_registered({"n_in_run": len(ablated),
                             "n_label_A0": sum(v == 0 for v in values),
                             "n_label_A1": sum(v == 1 for v in values)})
    else:
        g3 = _g3_controls_excluded(
            {k: {"n_in_run": len(v), "n_labeled_by_presence": None, "n_unlabeled": None}
             for k, v in controls.items() if v}, controls_valid=controls_valid)
    result["gates"]["G3_negative_control"] = g3
    result["controls_valid_asserted"] = bool(controls_valid)
    result["gates"]["G4_human_judge_qwk"] = _g4(
        primary, g4, seed, bootstrap_strata, B, bca_ties, id_sink)
    result["gates"]["G5_mae_judge_human"] = _g5(primary, seed, bootstrap_strata, B, id_sink, bca_ties)
    result["gates"]["G6_consistency"] = _g6(
        primary, result["contrasts"], seed=seed, strata_key=bootstrap_strata,
        resamples=B, ties=bca_ties)
    result["gates"]["G7_audit_trail"] = _g7(primary, label_audit, unblind_boundary, id_sink)
    result["fragility_pi_interval"] = _fragility_pi_not_implemented()
    def _g8_failure(data, value):
        if "lenient_direction_excluded" in data:
            return bool(data["lenient_direction_excluded"])
        direction = str(data.get("lenient_direction", "positive")).casefold()
        ci_lo = data.get("ci_lo")
        ci_hi = data.get("ci_hi")
        if ci_lo is None or ci_hi is None:
            return False
        return (float(ci_lo) > 0 if direction in {"positive", "upper", "over"}
                else float(ci_hi) < 0)
    result["gates"]["G8_external_spotcheck"] = _falsification_gate(
        g8, name="G8 external spotcheck", threshold="mean signed-difference CI includes 0",
        value_key="ci_hi", failure_predicate=_g8_failure)

    gate_keys = ("G1_silent_over_credit", "G2_intra_rater_qwk",
                 "G3_negative_control", "G4_human_judge_qwk",
                 "G5_mae_judge_human", "G6_consistency", "G7_audit_trail",
                 "G8_external_spotcheck")
    statuses = [result["gates"][key]["status"] for key in gate_keys]
    computed = sum(status != "not_computable" for status in statuses)
    failed = sum(status == "fail" for status in statuses)
    result["gates_summary"] = {
        "total": 8, "computed": computed, "calculated": computed,
        "not_computable": statuses.count("not_computable"),
        "failed": failed, "fail": failed,
        "passed": statuses.count("pass"),
        "not_falsified": statuses.count("not_falsified"),
    }
    gates = result["gates"]
    g7_value = gates["G7_audit_trail"].get("value")
    result["n_used"] = {
        "primary_cells": len(primary),
        "coverage": {v: {"n_cells": d["n_cells"], "n_clusters": d["n_clusters"]}
                     for v, d in result["coverage_detail"].items()},
        "contrasts": {k: {"n_clusters": c["n_clusters"], "n_questions": c["n_questions"]}
                      for k, c in result["contrasts"].items()},
        "pi_hat": {"n_cells": result["pi_hat"]["n_cells"],
                   "n_clusters": result["pi_hat"]["n_clusters"]},
        "G1": {"n_clusters": gates["G1_silent_over_credit"]["n_clusters"]},
        "G2": ({"n": g2.get("n"), "n_control_excluded": g2.get("n_control_excluded")}
               if g2 is not None else None),
        "G4": {"n_cells": gates["G4_human_judge_qwk"].get("n_cells"),
               "n_clusters": gates["G4_human_judge_qwk"].get("n_clusters")},
        "G5": {"n_cells": gates["G5_mae_judge_human"].get("n_cells"),
               "n_clusters": gates["G5_mae_judge_human"].get("n_clusters")},
        "G7": {"n_cells": g7_value.get("n_labeled_primary") if isinstance(g7_value, dict) else None},
    }
    _move_id_lists(result, id_sink)
    return result


def _json_default(obj):
    """Make numpy scalars and sets serialisable; anything else is a bug."""
    if isinstance(obj, np.generic):
        return obj.item()
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"{type(obj).__name__} is not JSON serialisable")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


AH_LABEL_SOURCE = "human-adjudicated AI draft (AH)"


def _label_provenance(source: str, simulated: bool, drafts_given: bool) -> dict | None:
    """How the labels behind every label-based number were produced.

    With a draft file the labels are an AH pass: AI-drafted, rater-revised
    (PREREG sec.11), reported as ``human-adjudicated AI draft (AH)`` and never as
    an independent blind human judgement; the direction of the resulting bias,
    which sec.11 requires to be stated with the numbers, is recorded here.
    Simulated (LLM) labels and unknown sources get no AH claim."""
    if simulated or source != "human":
        return None
    if not drafts_given:
        return {"mode": "human",
                "note": "no --drafts: recorded as plain human. The registered primary pass "
                        "is an AH pass (PREREG sec.11 L1132-1172) and must be run with "
                        "--drafts; the blind second-annotator subsample is plain human."}
    return {
        "mode": "AH",
        "base_source": source,
        "meaning": "human-adjudicated AI draft: AI-drafted, rater-revised (PREREG sec.11, "
                   "L1144-1172)",
        "independent_blind_human_judgement": False,
        "must_not_be_described_as": "independent blind human judgement (PREREG sec.11, "
                                    "L1157-1159)",
        "inflation_direction": "upward: AH-vs-judge agreement is inflated by the anchoring of "
                               "the AI draft (PREREG sec.11, L1160-1162, which requires the "
                               "direction to be stated with the numbers)",
        "implied_for_statistics": "derived, not PREREG text: disagreement-based statistics "
                                  "(pi-hat, G1) are biased down and agreement-based ones "
                                  "(G4 QWK, G5 MAE) toward agreement",
        "applies_to": "every label-based statistic in this file",
    }


def _same_file(left: Path, right: Path) -> bool:
    """True if two paths are the same file: equal after resolving symlinks and
    ``..``, or (when both exist) the same inode, which also catches hard links."""
    try:
        if left.resolve() == right.resolve():
            return True
        return left.exists() and right.exists() and os.path.samefile(left, right)
    except OSError:
        return False


def _refuse_outputs_that_are_inputs(outputs: dict, inputs: dict) -> None:
    """A results file written over an input would destroy the evidence it was
    computed from (the cells, a locked label snapshot, the audit, the drafts)."""
    for out_flag, out_path in outputs.items():
        if out_path is None:
            continue
        for in_flag, in_path in inputs.items():
            if in_path is not None and _same_file(out_path, in_path):
                raise SystemExit(
                    f"refusing to write {out_flag} {out_path}: it is the same file as the "
                    f"input {in_flag} {in_path}")


def _cell_detail_rows(primary: list[dict], audit: AuditLog | None, detail: dict) -> list[dict]:
    """Per-cell rows for the optional --out-cells file (judge AND human values)."""
    ah_cells = detail.get("ah_per_cell") or {}
    rows = []
    for c in primary:
        cid = str(c.get("cell_id", ""))
        recs = audit.saves.get(cid, ()) if audit is not None else ()
        last = recs[-1] if recs else None
        rows.append({
            "cell_id": cid, "cq_id": c.get("cq_id"), "cluster_id": c.get("cluster_id"),
            "category": c.get("category"), "variant": c.get("variant"),
            "J": c.get("J"), "A": c.get("A"), "L1_star": c.get("L1_star"),
            "rater_L1": c.get("rater_L1"),
            "audit_n_saves": len(recs),
            "audit_last_save_utc": last.ts.isoformat() if last else None,
            "audit_elapsed_s": last.elapsed_s if last else None,
            "audit_session_id": last.session_id if last else None,
            "audit_has_edit_reason_save": any(r.has_edit_reason for r in recs),
            **{k: ah_cells[cid][k] for k in ("draft_A", "A_changed", "span_edited")
               if cid in ah_cells},
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cells", type=Path, help="JSONL written by run_holdout.py")
    ap.add_argument("--seed", type=int, required=True,
                    help="pre-registered randomization seed (PREREG.md)")
    ap.add_argument("--out", type=Path, default=Path("holdout_results.json"),
                    help="main results JSON: AGGREGATES ONLY (no cell-level judge or "
                         "human value, no cell/CQ identifier)")
    ap.add_argument("--out-cells", type=Path,
                    help="optional separate per-cell detail file (judge and human values "
                         "per cell, identifier lists). Keep it sealed: the labeler must not "
                         "see per-cell judge/human disagreement before the washout")
    ap.add_argument("--g1-alpha", type=float, default=0.025, choices=(0.05, 0.025),
                    help="one-sided G1 alpha: 0.05 (95%%) or 0.025 (97.5%%); default preserves current behavior")
    ap.add_argument("--labels", type=Path,
                    help="primary-pass CSV with cell_id and A")
    ap.add_argument("--labels-washout", type=Path,
                    help="washout reassessment CSV; used for G2 rater_L1")
    ap.add_argument("--label-source",
                    help="provenance when CSV has no source column: human or explicit simulation marker")
    ap.add_argument("--allow-partial", action="store_true",
                    help="allow unlabeled cells and a primary cell set that is not the "
                         "registered Q_v design (A: 23 CQs, B-F: 33 each = 188 cells); "
                         "both are reported, not hidden")
    ap.add_argument("--allow-invalid-judge", action="store_true",
                    help="proceed although some primary cells have an invalid judge call "
                         "(judge_response_parsed false or an _error): such a cell carries "
                         "J=0 that is not a score. Reported per variant and stamped; "
                         "without this flag the run is refused")
    ap.add_argument("--controls-valid", action="store_true",
                    help="assert that the control rows' labels were produced under the "
                         "blind protocol and may be read: enables G3 (the evaluator's A on "
                         "the 24 ablated controls). Default: control labels are never "
                         "read and G3 is not_computable")
    ap.add_argument("--bca-ties", choices=BCA_TIES_CHOICES, default=DEFAULT_BCA_TIES,
                    help="how BCa's bias correction counts bootstrap replicates tied with "
                         "the estimate: 'midrank' (default, the scipy convention) or "
                         "'strict' (the former rule; under-covers on coarse grids; kept as a "
                         "sensitivity output only)")
    ap.add_argument("--allow-human-labels-on-simulated-run", action="store_true",
                    help="rehearsal escape hatch: permit human-sourced labels over a "
                         "SIMULATED judge run; the result is stamped rehearsal=true "
                         "and must never be reported as a manuscript result")
    ap.add_argument("--label-audit", type=Path,
                    help="label_assist <out>.audit.jsonl: the source of G7 and of the "
                         "order-drift / AH-correction descriptive items")
    ap.add_argument("--unblind-boundary", "--unblind-commit-time", dest="unblind_boundary",
                    help="ISO-8601 time WITH an explicit offset: every primary-cell save "
                         "must precede it (G7 (a)/(b)). --unblind-commit-time is the "
                         "former name of this flag")
    ap.add_argument("--drafts", type=Path,
                    help="AI-draft CSV (7-field header) for the AH correction rate "
                         "(descriptive; adds the span-edited share)")
    ap.add_argument("--bootstrap-strata", choices=tuple(BOOTSTRAP_STRATA_CHOICES),
                    default="none",
                    help="stratify the cluster bootstrap by this cell field. 'none' (default) "
                         "is the scheme PREREG sec.4 registers (unstratified semantic "
                         "clusters); 'category' is an UNREGISTERED sensitivity variant and "
                         "is stamped as such in the output")
    a = ap.parse_args()
    if not a.cells.exists():
        raise SystemExit(f"no cell file at {a.cells}: the holdout has not been run")
    if a.labels_washout is not None and a.labels is None:
        raise SystemExit("--labels-washout requires --labels for the primary pass")
    for flag, value in (("--label-audit", a.label_audit), ("--drafts", a.drafts),
                        ("--unblind-boundary", a.unblind_boundary)):
        if value is not None and a.labels is None:
            raise SystemExit(f"{flag} requires --labels")
    if a.unblind_boundary is not None and _parse_utc(a.unblind_boundary) is None:
        raise SystemExit("--unblind-boundary must be ISO-8601 with an explicit UTC offset "
                         "(e.g. 2026-10-09T12:00:00+09:00 or ...Z)")
    if a.out_cells is not None and _same_file(a.out_cells, a.out):
        raise SystemExit("--out-cells must differ from --out")
    _refuse_outputs_that_are_inputs(
        {"--out": a.out, "--out-cells": a.out_cells},
        {"cells": a.cells, "--labels": a.labels, "--labels-washout": a.labels_washout,
         "--label-audit": a.label_audit, "--drafts": a.drafts})
    if a.seed != REGISTERED_SEED:
        print(f"WARNING: --seed {a.seed} is not the registered seed {REGISTERED_SEED}; "
              "this output is not the registered analysis", file=sys.stderr)

    try:
        cells = load_cells(a.cells, require_a=a.labels is None)
    except ValueError as exc:
        raise SystemExit(f"cells JSONL: {exc}") from exc
    run_cells = list(cells)  # the whole run, before the join drops controls
    judge = judge_validity(run_cells)
    if judge["n_invalid"] and not a.allow_invalid_judge:
        per_variant = {v: d["n_invalid"] for v, d in judge["by_variant"].items() if d["n_invalid"]}
        bad_ids = invalid_judge_cell_ids(run_cells)
        raise SystemExit(
            f"{judge['n_invalid']} of {judge['n_primary']} primary cells have an invalid judge "
            f"call (parsed=false or _error), per variant {per_variant}: their J=0 is not a "
            f"score (e.g. {bad_ids[:5]}). Re-run those cells, or pass --allow-invalid-judge "
            "to proceed and report it.")
    if judge["n_invalid"]:
        print(f"WARNING: --allow-invalid-judge: {judge['n_invalid']} primary cells with an "
              "invalid judge call are analysed as recorded (J=0)", file=sys.stderr)
    try:
        control_ids = frozenset(str(c["cell_id"]) for c in cells
                                if _cell_kind(c) != CELL_KIND_PRIMARY)
    except ValueError as exc:
        raise SystemExit(f"cells JSONL: {exc}") from exc
    if a.labels is None and any(
            str(c.get("label_source", "")).strip().casefold() == "pending human evidence"
            for c in cells):
        raise SystemExit(
            "cells JSONL carries placeholder A values (label_source 'pending human "
            "evidence'); analysing them would score every cell A=0. Supply --labels."
        )
    judge_simulated = bool(cells) and all(bool(cell.get("SIMULATED")) for cell in cells)
    source, simulated = _infer_legacy_source(cells)
    label_metadata = None
    g2 = None
    audit = drafts = primary_labels = None
    if a.labels is not None:
        try:
            primary_labels = load_label_csv(
                a.labels, label_source=a.label_source, allow_partial=a.allow_partial,
                tolerate_ids=control_ids, read_control_a=a.controls_valid,
            )
            cells, label_metadata = join_labels(
                cells, primary_labels, allow_partial=a.allow_partial,
                exclude_controls=True,
            )
            source, simulated = primary_labels.source, primary_labels.simulated
            if a.label_audit is not None:
                audit = audit_scope(
                    load_label_audit(a.label_audit),
                    primary_ids={str(c["cell_id"]) for c in run_cells} - control_ids,
                    control_ids=control_ids,
                    run_ids={str(c["cell_id"]) for c in run_cells})
            if a.drafts is not None:
                drafts = load_drafts_csv(a.drafts)
            if a.labels_washout is not None:
                washout_labels = load_label_csv(
                    a.labels_washout,
                    label_source=a.label_source,
                    allow_partial=False,
                    tolerate_ids=control_ids,
                )
                if (washout_labels.source, washout_labels.simulated) != (source, simulated):
                    raise ValueError(
                        "primary and washout label sources disagree: "
                        f"{source!r} vs {washout_labels.source!r}"
                    )
                g2 = washout_qwk(primary_labels, washout_labels, exclude_ids=control_ids)
            if judge_simulated and not simulated and not a.allow_human_labels_on_simulated_run:
                raise ValueError(
                    "every judge cell is marked SIMULATED, but the labels claim "
                    f"source {source!r}. A human evidence pass over simulated judge "
                    "output cannot be reported as a human-labelled result. Re-run "
                    "the holdout against the registered judge, or mark the labels "
                    "with an explicit simulation marker; pass "
                    "--allow-human-labels-on-simulated-run only for a rehearsal "
                    "whose output is never used as a manuscript result."
                )
        except ValueError as exc:
            raise SystemExit(f"label validation failed: {exc}") from exc
    elif a.label_source is not None:
        raise SystemExit("--label-source requires --labels")

    detail: dict = {}
    if judge["n_invalid"]:
        detail["invalid_judge_cells"] = invalid_judge_cell_ids(run_cells)
    design = None
    if a.labels is not None:
        primary_for_design, _ = split_primary_and_controls(cells)
        design, design_ids = check_registered_design(primary_for_design)
        detail.update(design_ids)
        if not design["conforms"] and not a.allow_partial:
            short = {v: f"{d['observed']}/{d['expected']}" for v, d in design["by_variant"].items()}
            raise SystemExit(
                f"the primary cell set is not the registered design (A: 23 CQs, B-F: 33 "
                f"each = 188 cells): {design['observed_primary_cells']} cells, by variant "
                f"{short}, {design['n_missing']} missing, {design['n_unexpected']} "
                f"unexpected, {design['n_duplicate_cells']} duplicate. Pass --allow-partial "
                "to analyse it anyway (reported in analysis_population.registered_design).")
    res = analyse(
        cells,
        a.seed,
        g1_alpha=a.g1_alpha,
        label_source=source,
        simulated=simulated,
        label_metadata=label_metadata,
        g2=g2,
        label_audit=audit,
        unblind_boundary=a.unblind_boundary,
        bootstrap_strata=BOOTSTRAP_STRATA_CHOICES[a.bootstrap_strata],
        bootstrap_resamples=BOOTSTRAP_RESAMPLES,  # registered B; looked up at call time
        bca_ties=a.bca_ties,
        controls_valid=a.controls_valid,
        cell_detail=detail,
    )
    res["analysis_population"]["registered_design"] = design
    res["judge_validity"] = {**judge, "allow_invalid_judge": bool(a.allow_invalid_judge),
                             "invalid_cells_included": bool(judge["n_invalid"])}
    label_provenance = _label_provenance(source, simulated, a.drafts is not None)
    if label_provenance is not None:
        res["label_provenance"] = label_provenance
        if label_provenance["mode"] == "AH":
            res["label_source"] = AH_LABEL_SOURCE
    primary_scored, _ = split_primary_and_controls(cells)
    res["descriptive"] = {
        "order_drift": order_drift_diagnostic(primary_scored, audit),
        "ah_correction": ah_correction_rates(
            primary_scored, drafts=drafts, audit=audit,
            label_spans=primary_labels.spans if primary_labels is not None else None,
            detail=detail),
    }
    res["judge_simulated"] = judge_simulated
    if judge_simulated and not simulated:
        res["rehearsal"] = True
        res["rehearsal_note"] = (
            "human-sourced labels over a SIMULATED judge run; not a manuscript result"
        )
    provenance = {
        "analyzer_sha256": _sha256_file(Path(__file__).resolve()),
        "cells_jsonl": {"path": str(a.cells), "sha256": _sha256_file(a.cells)},
    }
    for key, path in (("labels_csv", a.labels), ("labels_washout_csv", a.labels_washout),
                      ("label_audit_jsonl", a.label_audit), ("drafts_csv", a.drafts)):
        if path is not None:
            provenance[key] = {"path": str(path), "sha256": _sha256_file(path)}
    provenance["unblind_boundary"] = a.unblind_boundary
    provenance["environment"] = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }
    res["input_provenance"] = provenance
    res["output_policy"] = {
        "main_json": "aggregates only; no cell-level judge/human value and no cell or CQ "
                     "identifier",
        "per_cell_detail": "written only to --out-cells" if a.out_cells else "not written",
    }

    main_text = json.dumps(res, indent=2, default=_json_default)
    leaks = find_cell_level_leaks(
        main_text, [c.get("cell_id") for c in run_cells] + [c.get("cq_id") for c in run_cells]
        + list(detail.get("unlabeled_primary_cell_ids", [])))
    if leaks:
        raise SystemExit(
            "refusing to write the main results: cell-level identifiers found in an "
            f"aggregates-only JSON: {leaks[:5]}")
    a.out.write_text(main_text)
    if a.out_cells is not None:
        payload = {
            "WARNING": ("per-cell judge AND human values: keep sealed; the labeler must not "
                        "see per-cell judge/human disagreement before the washout"),
            "schema": "analyze_holdout per-cell detail v1",
            "primary_cells": _cell_detail_rows(primary_scored, audit, detail),
            "id_lists": {k: v for k, v in detail.items() if k != "ah_per_cell"},
        }
        a.out_cells.write_text(json.dumps(payload, indent=2, default=_json_default))
        print(f"NOTE: {a.out_cells} holds per-cell judge/human values; keep it sealed until "
              "after the washout", file=sys.stderr)
    print(json.dumps(res["coverage_pct"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
