"""Domain-aware entry point for the registered analysis.

    python analyze_domain.py --domain brick <analyze_holdout.py arguments ...>
    python analyze_domain.py --domain iof   <analyze_holdout.py arguments ...>

``brick`` hands every remaining argument to ``analyze_holdout.main`` unchanged (same code, same
output). ``iof`` is routed per PREREG.md addendum 15 §15.7-2: the unfrozen-bank refusal stays,
and the registered IOF design — derived from the committed eligibility-preflight manifest by
``design_iof.py``, never from prose — replaces the pinned analyzer's Brick-only design check at
RUNTIME (analyze_holdout looks the name up through its module global, so the file itself stays
byte-identical and its pinned SHA-256 holds; the swap is restored afterwards). Any other domain
is refused: first because its CQ bank must be frozen, then because it has no registered design.
This wrapper exists so that analyze_holdout.py itself stays byte-identical (committed artifacts
pin its SHA-256).
"""
from __future__ import annotations

import sys

from domains import DEFAULT_DOMAIN, known_domains, load_domain


def main(argv: list[str]) -> int:
    domain_name = DEFAULT_DOMAIN
    rest = list(argv)
    if "--domain" in rest:
        i = rest.index("--domain")
        if i + 1 >= len(rest):
            raise SystemExit("--domain needs a value")
        domain_name = rest[i + 1]
        del rest[i:i + 2]
    if domain_name not in known_domains():
        raise SystemExit(f"unknown domain {domain_name!r}; known: {known_domains()}")
    domain = load_domain(domain_name)
    iof_design = None
    if domain.name != DEFAULT_DOMAIN:
        domain.require_frozen_bank()
        if domain.preflight_manifest is not None:
            import design_iof
            iof_design = design_iof.load_iof_design(domain)
        else:
            raise SystemExit(f"REFUSING TO RUN: no registered analysis design for domain "
                             f"{domain.name!r} (analyze_holdout's REGISTERED_* tables are "
                             "Brick-only; a §15.7 domain must declare "
                             "[analysis].preflight_manifest in domains/{name}.toml)")
    import analyze_holdout
    checker = None
    if iof_design is not None:
        requested = _requested_seed(rest)
        if requested is not None and requested != iof_design.seed:
            raise SystemExit(f"REFUSING TO RUN: --seed {requested} is not the seed "
                             f"{iof_design.seed} committed in the IOF preflight manifest "
                             f"{iof_design.manifest_path} (PREREG §15.2)")
        checker = design_iof.make_design_checker(
            iof_design, allow_partial=("--allow-partial" in rest))
    original = analyze_holdout.check_registered_design
    try:
        if checker is not None:
            analyze_holdout.check_registered_design = checker
        sys.argv = ["analyze_holdout.py", *rest]
        return analyze_holdout.main()
    finally:
        analyze_holdout.check_registered_design = original


def _requested_seed(rest: list[str]) -> int | None:
    return int(rest[rest.index("--seed") + 1]) if "--seed" in rest else None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
