"""Pooled G1 across holdout domains (Brick + IOF) — the REGISTERED estimand, no verdict.

PREREG.md addendum 15 (DN15-1, §15.3): the pooled G1 is a pre-registered ESTIMAND, not a
gate — the one-sided Clopper-Pearson upper bound of the cluster event rate is reported at
BOTH 97.5% and 95%, always together, and NO pass/fail is attached to it; the 10% threshold
survives only as a reference line (§15.3.1). §15.7-3 registered this in three parts: (a)
this commit flips ``POOLED_G1_REGISTERED`` to True — the flip IS the registration act; (b)
the output carries the §15.3.4 per-domain companions (events, clusters, both-level upper
bounds, cell-level pi-hat with BCa, descriptive Fisher heterogeneity) and the §15.3.2
N-table row at the OBSERVED pooled N; (c) the former decision field is gone — replaced by
the "추정, 판정 없음" (estimation, no verdict) marking.

Lives beside ``analyze_holdout.py`` rather than in it on purpose: committed artifacts
(``ask_results.json``, ``exploratory_reanalysis.json``) pin the SHA-256 of analyze_holdout.py,
and the registered Brick analysis code must stay byte-identical. Nothing in the registered
Brick pipeline imports this module; Brick single-domain numbers do not flow through it.

Same estimand as ``analyze_holdout.silent_over_credit``: a CQ cluster is an event when any of its
primary cells has J >= 2 and A == 0. Clusters are qualified with their domain's ``cluster_prefix``
(``brick:CQB01``, ``iof:CQI01``) so equal raw ids in two domains stay two clusters; events and
clusters are summed; the bound is the one-sided Clopper-Pearson limit (§15.3.1). Control cells
are excluded exactly as ``analyse`` excludes them. An explicit ``enabled=False`` still refuses,
so a rehearsal can never emit pooled numbers unnoticed.
"""
from __future__ import annotations

from scipy import stats

import analyze_holdout as ah
import design_iof
from domains import load_domain

POOLED_G1_REGISTERED = True

DECISION_MARK = "추정, 판정 없음 (estimation, no verdict — pooled G1 is an estimand, not a gate)"


def pooled_g1(
    cells_by_domain: dict[str, list[dict]],
    alpha: float = 0.025,
    threshold: float = ah.G1_UPPER_BOUND_THRESHOLD,
    *,
    enabled: bool = POOLED_G1_REGISTERED,
    seed: int = ah.REGISTERED_SEED,
    bootstrap_resamples: int = ah.BOOTSTRAP_RESAMPLES,
) -> dict:
    """Pooled G1 estimate over ``{domain name: cells}``; control cells are excluded as in
    ``analyse``.

    Refuses unless ``enabled`` (default: the registered flag); pass ``enabled=False``
    only to disable a call explicitly. ``bootstrap_resamples`` is the registered BCa B
    for the per-domain cell-level pi-hat companion; lower it only in tests.
    """
    if not enabled:
        raise RuntimeError("pooled G1 is disabled for this call (POOLED_G1_REGISTERED is "
                           "True since the §15.7-3(a) registration; enabled=False is for a "
                           "rehearsal that must not emit pooled numbers)")
    if alpha not in (0.05, 0.025):
        raise ValueError("alpha must be 0.05 (95%) or 0.025 (97.5%)")
    if not cells_by_domain:
        raise ValueError("pooled G1 needs at least one domain")
    qualified: list[dict] = []
    per_domain: dict[str, dict] = {}
    prefix_owner: dict[str, str] = {}
    for name in sorted(cells_by_domain):
        cfg = load_domain(name)
        if prefix_owner.setdefault(cfg.cluster_prefix, name) != name:
            raise ValueError(f"cluster_prefix {cfg.cluster_prefix!r} is used by two domains")
        primary, _ = ah.split_primary_and_controls(list(cells_by_domain[name]))
        if not primary:
            raise ValueError(f"domain {name!r} has no primary cells")
        events, n = ah.silent_over_credit(primary)
        both_levels = {
            "one_sided_97_5": {"alpha": 0.025,
                              "upper_bound": ah.clopper_pearson_upper(events, n, alpha=0.025)},
            "one_sided_95": {"alpha": 0.05,
                             "upper_bound": ah.clopper_pearson_upper(events, n, alpha=0.05)},
        }
        per_domain[name] = {
            "events": events, "n_clusters": n, "cluster_prefix": cfg.cluster_prefix,
            **both_levels,
            "threshold_reference_line": threshold,
            "threshold_reference_line_role": "참고 선(독자 비교용)일 뿐 판정에 쓰지 않는다 "
                                            "(PREREG §15.3.1/§15.3.4); 추정, 판정 없음",
            "cell_level": ah.silent_over_credit_rate(
                primary, seed=seed, B=bootstrap_resamples),
        }
        qualified += [{**c, "cluster_id": cfg.qualify_cluster(str(c["cluster_id"]))} for c in primary]
    events, n = ah.silent_over_credit(qualified)
    if (events, n) != (sum(d["events"] for d in per_domain.values()),
                       sum(d["n_clusters"] for d in per_domain.values())):
        raise AssertionError("pooled cluster counts disagree with the per-domain counts")
    n_row = design_iof.cp_row(n)
    n_row["observed_events"] = events
    return {
        "estimand": ("pi = Pr[J >= 2 AND A == 0], pooled over domain-qualified CQ-clusters; "
                     "PRE-REGISTERED ESTIMAND (§15.3): no verdict, never a calibration claim"),
        "registered": True,
        "decision": DECISION_MARK,
        "events": events,
        "n_clusters": n,
        "upper_bound_one_sided": ah.clopper_pearson_upper(events, n, alpha=alpha),
        "confidence_level_one_sided": 1.0 - alpha,
        "upper_bounds_one_sided_always_both": {
            "one_sided_97_5": ah.clopper_pearson_upper(events, n, alpha=0.025),
            "one_sided_95": ah.clopper_pearson_upper(events, n, alpha=0.05),
        },
        "threshold_reference_line": threshold,
        "threshold_reference_line_role": ("참고 선(독자 비교용)일 뿐 판정에 쓰지 않는다 "
                                          "(PREREG §15.3.1); 추정, 판정 없음"),
        "method": "Clopper-Pearson (bootstrap is prohibited for this quantity)",
        "n_table_row": n_row,
        "heterogeneity": _heterogeneity(per_domain),
        "per_domain": per_domain,
    }


def _heterogeneity(per_domain: dict[str, dict]) -> dict:
    """§15.3.4 descriptive heterogeneity: the event-rate difference between the two
    domains with a Fisher exact p-value. DESCRIPTIVE ONLY — never a verdict; a large
    p or a small one changes nothing here, and a pooled rate over heterogeneous
    domains is a mixture of two populations, not one rate (§15.3.4/§15.9)."""
    names = sorted(per_domain)
    if len(names) != 2:
        return {"descriptive_only": True, "test": "Fisher exact",
                "p_two_sided": None,
                "note": f"descriptive two-domain statistic; {len(names)} domains supplied"}
    a, b = (per_domain[x] for x in names)
    table = [[a["events"], a["n_clusters"] - a["events"]],
             [b["events"], b["n_clusters"] - b["events"]]]
    p = float(stats.fisher_exact(table).pvalue)
    return {
        "descriptive_only": True, "test": "Fisher exact", "two_sided": True,
        "pair": names, "table_events_vs_clean_clusters": table,
        "p_two_sided": p,
        "event_rate_difference": (a["events"] / a["n_clusters"]) - (b["events"] / b["n_clusters"]),
        "note": ("descriptive (§15.3.4): heterogeneity is reported, not judged; if the "
                 "domains differ, the pooled rate is a mixture of two populations"),
    }
