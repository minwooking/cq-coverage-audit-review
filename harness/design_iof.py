"""IOF registered analysis design, DERIVED from the committed preflight manifest.

PREREG.md addendum 15 §15.7-2: the IOF analysis needs a registered design table
(the CQ x variant eligible grid, the exclusion rule, the A->B pair count m and the
cluster count N) because ``analyze_holdout.py``'s ``REGISTERED_*`` tables are
Brick-only -- and ``analyze_holdout.py`` itself must stay byte-identical (its
SHA-256 is pinned by committed artifacts). This module is that change: the IOF
design enters here and through ``analyze_domain.py``, never by editing the pinned
analyzer.

Where the numbers come from (§15.2/§15.7-4 -- design values are NEVER re-typed from
prose): the eligibility preflight over the IOF variant artifacts ran BEFORE any
judge call and committed its manifest at ``harness/real_run_iof/MANIFEST.json``
(the path is declared per-domain in ``domains/iof.toml`` under
``[analysis].preflight_manifest``). This loader derives from that committed file:

  grid          = manifest variant_ids x the frozen bank's 36 CQ ids (216 cells)
  excluded      = manifest eligibility_exclusions (178 grounding-absent cells,
                  rule: grounding_anchor_absent_from_view per §15.2)
  eligible      = grid - excluded (38 primary cells; A: 8, B-F: 6 each)
  N_IOF         = |union of eligible CQs| = 8 (scored-CQ / cluster count, §15.2)
  m             = |Q_A n Q_B| = 6 (CQs scored by both A and B, §15.4.1)
  pooled N      = 33 + N_IOF, pooled pairs = 23 + m -- the Brick side (33, 23) is
                  derived from analyze_holdout's committed REGISTERED_PRIMARY_SET,
                  not from prose.

Every derivation is cross-checked against the manifest's own aggregate fields and
against the frozen bank digest; any disagreement is a ``REFUSING TO RUN`` exit, so
a design that drifted from the committed preflight can never silently analyse.

The §15.3.2 / §15.4.3 arithmetic the addendum registers (Clopper-Pearson N-table,
pooled-MDE row) lives here as pure functions so the registered formulas are code
committed before IOF labels are read (§15.7-5), not prose retyped inside a test.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from scipy import stats

import analyze_holdout as ah
from domains import ACCESS, DomainError, DomainConfig, load_domain

MANIFEST_SCHEMA_NOTE = "run_holdout.py eligibility preflight manifest"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class IofDesign:
    """The registered IOF analysis design, derived from the committed manifest."""
    manifest_path: Path
    manifest_sha256: str
    bank_sha256: str
    bank_rows: int
    seed: int
    variant_ids: tuple[str, ...]
    cq_ids: tuple[str, ...]
    excluded_pairs: frozenset[tuple[str, str]]
    eligible_pairs: frozenset[tuple[str, str]]
    exclusion_rule: str
    checked_primary_cells: int
    excluded_primary_cells: int
    eligible_primary_cells: int
    n_clusters: int            # IOF scored CQs (N_IOF, §15.2/§15.3.1)
    m_ab_pairs: int            # IOF CQs scored by BOTH A and B (§15.4.1)
    ablated_control_cells: int
    preserved_control_cells: int
    preserved_controls_omitted_reason: str
    brick_n_clusters: int      # derived from REGISTERED_PRIMARY_SET (33)
    brick_m_ab_pairs: int      # derived from REGISTERED_PRIMARY_SET (23)

    @property
    def pooled_n_clusters(self) -> int:
        return self.brick_n_clusters + self.n_clusters

    @property
    def pooled_ab_pairs(self) -> int:
        return self.brick_m_ab_pairs + self.m_ab_pairs

    @property
    def per_variant_counts(self) -> dict[str, int]:
        return {v: sum(1 for vv, _ in self.eligible_pairs if vv == v)
                for v in self.variant_ids}


def _refuse(why: str) -> None:
    raise DomainError(f"REFUSING TO RUN: IOF registered design: {why}")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ACCESS))
    except ValueError:
        return str(path)


def _brick_side_design() -> tuple[int, int]:
    """(N_brick, m_brick) derived from the committed Brick design table."""
    by_variant: dict[str, set[str]] = {}
    for v, q in ah.REGISTERED_PRIMARY_SET:
        by_variant.setdefault(v, set()).add(q)
    union = set().union(*by_variant.values())
    if "A" not in by_variant or "B" not in by_variant:
        _refuse("analyze_holdout's REGISTERED_PRIMARY_SET has no A or B variant")
    return len(union), len(by_variant["A"] & by_variant["B"])


def load_iof_design(domain: DomainConfig | None = None,
                    manifest_path: Path | None = None) -> IofDesign:
    """Load and cross-validate the IOF design; refuse on any disagreement.

    The bank must be frozen (§15.7-1 -- that refusal stays unchanged), the domain
    must declare ``[analysis].preflight_manifest`` (§15.7-2), and every derived
    count must agree with the manifest's own aggregate fields and the bank digest.
    """
    cfg = domain if domain is not None else load_domain("iof")
    cfg.require_frozen_bank()
    path = manifest_path if manifest_path is not None else cfg.preflight_manifest
    if path is None:
        _refuse(f"domains/{cfg.name}.toml declares no [analysis].preflight_manifest, "
                "so this domain has no registered analysis design (§15.7-2/4)")
    if not Path(path).is_file():
        _refuse(f"the committed preflight manifest is missing: {path}")
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))

    if manifest.get("bank_sha256") != cfg.bank_sha256:
        _refuse("manifest bank_sha256 does not match the frozen bank pin of "
                f"domains/{cfg.name}.toml ({manifest.get('bank_sha256')!r})")
    if manifest.get("bank_rows") != cfg.bank_rows:
        _refuse(f"manifest bank_rows {manifest.get('bank_rows')!r} != {cfg.bank_rows}")
    if manifest.get("bank_sha256") != _sha256_file(cfg.bank_path):
        _refuse(f"manifest bank_sha256 does not match the bytes of {cfg.bank_path}")
    seed = manifest.get("seed")
    if seed != ah.REGISTERED_SEED:
        _refuse(f"manifest seed {seed!r} is not the registered seed {ah.REGISTERED_SEED} "
                "(§15.2 reuses the registered seed; a different manifest is a different run)")

    with cfg.bank_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = [str(n).strip() for n in (reader.fieldnames or [])]
        if "cq_id" not in fieldnames:
            _refuse(f"bank {cfg.bank_path} has no cq_id column")
        bank_cq_ids = tuple(sorted(str(row["cq_id"]).strip() for row in reader))
    if len(bank_cq_ids) != cfg.bank_rows or len(set(bank_cq_ids)) != len(bank_cq_ids):
        _refuse(f"bank cq_id count {len(bank_cq_ids)} != declared bank_rows {cfg.bank_rows}")

    variant_ids = tuple(manifest.get("variant_ids") or [])
    if not variant_ids or len(set(variant_ids)) != len(variant_ids):
        _refuse(f"manifest variant_ids are not a distinct list: {variant_ids!r}")

    exclusions = manifest.get("eligibility_exclusions") or []
    excluded: set[tuple[str, str]] = set()
    rules: set[str] = set()
    for i, e in enumerate(exclusions):
        pair = (str(e.get("variant")), str(e.get("cq_id")))
        if pair in excluded:
            _refuse(f"duplicate eligibility exclusion for cell {pair} (entry {i})")
        excluded.add(pair)
        if pair[0] not in variant_ids:
            _refuse(f"eligibility exclusion for unknown variant {pair[0]!r} (entry {i})")
        if pair[1] not in bank_cq_ids:
            _refuse(f"eligibility exclusion for CQ outside the frozen bank: "
                    f"{pair[1]!r} (entry {i})")
        rules.add(str(e.get("reason", "")))
    if len(rules) != 1:
        _refuse(f"manifest holds {len(rules)} different exclusion rules; one registered "
                "rule is expected (§15.2: the rule is not changed after results exist)")

    grid = {(v, q) for v in variant_ids for q in bank_cq_ids}
    if not excluded <= grid:
        _refuse("eligibility exclusions reach outside variant_ids x bank CQs")
    eligible = frozenset(grid - excluded)

    counts = manifest.get("eligibility_counts") or {}
    checks = (
        ("checked_primary_cells", len(grid), counts.get("checked_primary_cells")),
        ("excluded_grounding_absent", len(excluded), counts.get("excluded_grounding_absent")),
        ("eligible_primary_cells", len(eligible), counts.get("eligible_primary_cells")),
    )
    for field, derived, declared in checks:
        if declared is None:
            _refuse(f"manifest eligibility_counts has no {field!r}")
        if derived != declared:
            _refuse(f"{field} derived from the manifest ({derived}) disagrees with the "
                    f"manifest's own count ({declared})")
    if manifest.get("eligibility_exclusion_count") != len(excluded):
        _refuse("manifest eligibility_exclusion_count disagrees with the exclusion list")
    if manifest.get("primary_cells") != len(eligible):
        _refuse("manifest primary_cells disagrees with the eligible grid")
    ablated = int(manifest.get("ablated_control_cells", -1))
    preserved = int(manifest.get("preserved_control_cells", -1))
    planned = manifest.get("planned_cells")
    if planned != len(eligible) + ablated + preserved:
        _refuse(f"planned_cells {planned!r} != eligible {len(eligible)} + ablated "
                f"{ablated} + preserved {preserved}")

    by_variant: dict[str, set[str]] = {}
    for v, q in eligible:
        by_variant.setdefault(v, set()).add(q)
    n_clusters = len(set().union(*by_variant.values())) if by_variant else 0
    if "A" not in by_variant or "B" not in by_variant:
        _refuse("no eligible A or B cells: the registered A->B contrast would be undefined")
    m_ab = len(by_variant["A"] & by_variant["B"])
    brick_n, brick_m = _brick_side_design()

    return IofDesign(
        manifest_path=Path(path),
        manifest_sha256=_sha256_file(Path(path)),
        bank_sha256=str(manifest["bank_sha256"]),
        bank_rows=int(manifest["bank_rows"]),
        seed=int(seed),
        variant_ids=variant_ids,
        cq_ids=bank_cq_ids,
        excluded_pairs=frozenset(excluded),
        eligible_pairs=frozenset(eligible),
        exclusion_rule=rules.pop(),
        checked_primary_cells=len(grid),
        excluded_primary_cells=len(excluded),
        eligible_primary_cells=len(eligible),
        n_clusters=n_clusters,
        m_ab_pairs=m_ab,
        ablated_control_cells=ablated,
        preserved_control_cells=preserved,
        preserved_controls_omitted_reason=str(
            manifest.get("preserved_controls_omitted_reason", "")),
        brick_n_clusters=brick_n,
        brick_m_ab_pairs=brick_m,
    )


def make_design_checker(design: IofDesign, *, allow_partial: bool = False):
    """A replacement for ``analyze_holdout.check_registered_design`` bound to ``design``.

    ``analyze_domain.py`` swaps it in AT RUNTIME for ``--domain iof`` only (the
    pinned analyzer looks the name up through its module global, so the file bytes
    never change and the brick route never sees it). Same return shape as the
    Brick original: (aggregate summary WITHOUT any CQ/cell identifier -- the
    main-results leak guard applies --, per-cell id lists for the sealed detail).
    On a non-conforming cell set it refuses in IOF's own words, because the refusal
    text inside the pinned analyzer is Brick-worded.
    """
    expected = design.eligible_pairs
    expected_by_variant = design.per_variant_counts

    def check(primary: list[dict]) -> tuple[dict, dict]:
        observed = [(str(c.get("variant")), str(c.get("cq_id"))) for c in primary]
        observed_set = set(observed)
        missing = sorted(expected - observed_set)
        unexpected = sorted(observed_set - expected)
        by_variant = {}
        for v in sorted(set(expected_by_variant) | {v for v, _ in observed_set}):
            exp = {q for vv, q in expected if vv == v}
            obs = {q for vv, q in observed_set if vv == v}
            by_variant[v] = {"expected": len(exp), "observed": len(obs),
                             "n_missing": len(exp - obs), "n_unexpected": len(obs - exp)}
        n_dup = len(observed) - len(observed_set)
        conforms = not missing and not unexpected and n_dup == 0
        if not conforms and not allow_partial:
            raise SystemExit(
                "REFUSING TO RUN: the IOF primary cell set is not the registered design "
                f"derived from the committed preflight manifest {design.manifest_path} "
                f"(sha256 {design.manifest_sha256}): "
                f"{len(observed)} cells observed vs {len(expected)} eligible "
                f"({len(missing)} missing, {len(unexpected)} unexpected, {n_dup} duplicate; "
                "per variant "
                + ", ".join(f"{v}: {d['observed']}/{d['expected']}"
                            for v, d in sorted(by_variant.items())) +
                "). The eligibility exclusion rule is committed and is not changed "
                "after results exist (§15.2). Pass --allow-partial to analyse it "
                "anyway; the non-conformance is then recorded in "
                "analysis_population.registered_design.")
        summary = {
            "conforms": conforms,
            "expected_primary_cells": len(expected),
            "observed_primary_cells": len(observed),
            "n_missing": len(missing), "n_unexpected": len(unexpected),
            "n_duplicate_cells": n_dup, "by_variant": by_variant,
            "source": (
                f"IOF registered design derived from the committed eligibility-preflight "
                f"manifest {_display_path(design.manifest_path)} "
                f"(sha256 {design.manifest_sha256}) per PREREG.md addendum 15 §15.2/§15.7: "
                f"{design.checked_primary_cells} CQ x variant cells checked, "
                f"{design.excluded_primary_cells} excluded by the committed rule "
                f"{design.exclusion_rule!r}, {design.eligible_primary_cells} eligible "
                f"primary cells ({design.per_variant_counts}); the exclusion rule was "
                "fixed before the first judge call and is not changed after results exist."
            ),
            "iof_design": {
                "manifest_sha256": design.manifest_sha256,
                "eligibility_rule": design.exclusion_rule,
                "n_iof_clusters": design.n_clusters,
                "m_ab_pairs": design.m_ab_pairs,
                "pooled_n_clusters": design.pooled_n_clusters,
                "pooled_ab_pairs": design.pooled_ab_pairs,
                "ablated_control_cells_planned": design.ablated_control_cells,
                "preserved_control_cells_planned": design.preserved_control_cells,
            },
        }
        ids = {"registered_design_missing_cells": [f"{v}:{q}" for v, q in missing],
               "registered_design_unexpected_cells": [f"{v}:{q}" for v, q in unexpected]}
        return summary, ids

    return check


# ---------------------------------------------------------------------------
# §15.3.2 / §15.4.3 registered arithmetic (pure functions; committed pre-labels)
# ---------------------------------------------------------------------------
def cp_row(n_clusters: int, ks: range | tuple[int, ...] = range(5),
           alphas: tuple[float, ...] = (0.025, 0.05)) -> dict:
    """One row of the PREREG §15.3.2 N-table: one-sided Clopper-Pearson upper
    bounds (as %) for k events in n clusters at both registered levels, plus the
    largest k still below the 10% REFERENCE LINE (never a verdict, §15.3.1)."""
    row = {"n_clusters": n_clusters, "events_upper_bound_pct": {}}
    for k in [x for x in ks if x <= n_clusters]:
        row["events_upper_bound_pct"][k] = {
            f"one_sided_{(1 - a) * 100:g}%":
                round(100.0 * ah.clopper_pearson_upper(k, n_clusters, alpha=a), 2)
            for a in alphas}
    for a in alphas:
        label = f"max_events_below_10pct_reference_line_one_sided_{(1 - a) * 100:g}%"
        max_k = None
        for k in range(n_clusters + 1):
            if ah.clopper_pearson_upper(k, n_clusters, alpha=a) <= 0.10:
                max_k = k
            else:
                break
        row[label] = max_k
    row["note"] = ("reference table (PREREG §15.3.2): the pooled G1 is an ESTIMAND, "
                   "not a gate; the 10% line is a reference only -- no verdict (§15.3.1)")
    return row


def mde_row(iof_pairs: int, brick_pairs: int = 23, sigma: float = 1.155,
            sigma_sensitivity: float = 1.336) -> dict:
    """One row of the PREREG §15.4.3 pooled-MDE table for a pooled pair count of
    ``brick_pairs + iof_pairs``. The registered column is the normal-approximation
    MDE at 80% power / two-sided alpha=0.05, MDE(n) = (z_.975 + z_.80) * sigma / sqrt(n);
    the t and sensitivity columns are informational (§15.4.3)."""
    n = brick_pairs + iof_pairs
    z = stats.norm.ppf(0.975) + stats.norm.ppf(0.80)
    half = lambda s: stats.t.ppf(0.95, n - 1) * s / math.sqrt(n)  # noqa: E731
    return {
        "iof_pairs": iof_pairs, "pooled_pairs": n,
        "mde_normal_approx_sigma_1_155": round(float(z * sigma / math.sqrt(n)), 3),
        "coverage_points": round(float(z * sigma / math.sqrt(n)) / 3 * 100, 1),
        "mde_t_approx_sigma_1_155": round(float((stats.t.ppf(0.975, n - 1)
                                                 + stats.t.ppf(0.80, n - 1))
                                                * sigma / math.sqrt(n)), 3),
        "mde_normal_approx_sigma_1_336_sensitivity":
            round(float(z * sigma_sensitivity / math.sqrt(n)), 3),
        "ci90_half_width_sigma_1_155": round(float(half(sigma)), 3),
        "ci90_half_width_sigma_1_336": round(float(half(sigma_sensitivity)), 3),
        "note": ("PREREG §15.4.3: sigma is the registered 1.155 from one moved "
                 "development contrast; the 1.336 column is the sensitivity for the "
                 "observed Brick spread; MDE gauges resolution, it is not a decision "
                 "condition"),
    }
