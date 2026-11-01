#!/usr/bin/env python3
"""Build primary-pass and washout-reassessment sheets from a judge run.

The preregistered design has one annotator: a full primary evidence pass and a
separate washout reassessment pass by the same annotator. Judge J is never
copied into either packet. A formal washout sheet selects the preregistered
72-cell stratified subset when at least 72 run cells are available.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from pathlib import Path

PRIMARY_PASS_SEED = 20260913
WASHOUT_REASSESSMENT_SEED = 20260914
WASHOUT_N = 72
COLUMNS = (
    "cell_id", "cq_id", "cluster_id", "category", "variant", "cq_text",
    "judge_evidence_span", "rendered_view_path", "evidence_span_verbatim",
    "A", "rater_L1", "note",
)


def _find_bank(cells_path: Path) -> Path | None:
    candidates = (
        cells_path.parent.parent / "bank" / "cq_bank_brick_v1.csv",
        cells_path.parent.parent.parent / "bank" / "cq_bank_brick_v1.csv",
        Path(__file__).resolve().parents[2] / "bank" / "cq_bank_brick_v1.csv",
    )
    return next((path for path in candidates if path.exists()), None)


def _domain_material(domain: str) -> tuple[Path, Path] | None:
    """Registered bank/variants for a non-Brick domain, via domains.py.

    Brick keeps its legacy path-walk unchanged (None -> old resolution).
    IOF must resolve through domains/iof.toml: the brick walk from
    harness/real_run_iof would silently find the BRICK bank and the BRICK
    variants directory and build a packet with the wrong CQ text/views."""
    if domain == "brick":
        return None
    harness = Path(__file__).resolve().parents[2] / "harness"
    sys.path.insert(0, str(harness))
    from domains import load_domain  # noqa: PLC0415 - only needed for non-brick

    d = load_domain(domain)
    if not d.bank_path.exists():
        raise SystemExit(f"domain {domain}: bank not found at {d.bank_path}")
    if not d.variants_dir.is_dir():
        raise SystemExit(f"domain {domain}: variants dir not found at {d.variants_dir}")
    return d.bank_path, d.variants_dir


def _variants_dir(cells_path: Path) -> Path | None:
    # The real multi-variant holdout run keeps per-variant judge material in a
    # sibling `variants/` directory (harness/variants/{A..F}/rendered_view.txt),
    # not in the run directory itself. Try the two layouts seen in this repo:
    # harness/real_run/cells.jsonl -> harness/variants, and one level deeper
    # for nested dryrun subdirectories.
    for candidate in (cells_path.parent.parent / "variants", cells_path.parent.parent.parent / "variants"):
        if candidate.is_dir():
            return candidate
    return None


def _variant_rendered_view(variants_dir: Path | None, variant: str) -> Path | None:
    if not variants_dir or not variant:
        return None
    path = variants_dir / variant / "rendered_view.txt"
    return path if path.is_file() else None


def _read_cells(run_dir: Path, bank_override: Path | None = None,
                variants_override: Path | None = None) -> tuple[list[dict], Path | None, Path | None]:
    cells_path = run_dir / "cells.jsonl"
    shared_view_path = run_dir / "schema_view.txt"
    if not cells_path.exists():
        raise SystemExit(f"missing {cells_path}")
    rows = [json.loads(line) for line in cells_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise SystemExit(f"no cells in {cells_path}")
    required = {"cq_id", "cluster_id", "category", "variant"}
    missing = required - set(rows[0])
    if missing:
        raise SystemExit(f"cells.jsonl missing required fields: {sorted(missing)}")

    # Formal multi-variant runs (real_run: variants A-F) supply the material the
    # judge actually saw as one rendered_view.txt PER VARIANT under a sibling
    # variants/ directory -- a single shared schema_view.txt would silently
    # point every row at the wrong variant's material. Prefer per-variant
    # resolution when it covers every variant present in cells.jsonl; only
    # fall back to the single shared file (legacy single-variant smoke/dryrun
    # runs, e.g. variant "BRICK_SOURCE") when that per-variant lookup can't
    # cover all rows.
    variants_dir = variants_override if variants_override is not None else _variants_dir(cells_path)
    variants_used = {row["variant"] for row in rows}
    per_variant_complete = bool(variants_dir) and all(
        _variant_rendered_view(variants_dir, variant) is not None for variant in variants_used
    )
    if not per_variant_complete and not shared_view_path.exists():
        raise SystemExit(
            f"missing {shared_view_path} and no complete per-variant rendered_view.txt set under "
            f"{variants_dir or '<none found>'} for variants {sorted(variants_used)}"
        )

    bank_path = bank_override if bank_override is not None else _find_bank(cells_path)
    bank: dict[str, dict] = {}
    if bank_path:
        with bank_path.open(newline="", encoding="utf-8") as fh:
            bank = {row["cq_id"]: row for row in csv.DictReader(fh)}
    for row in rows:
        if "question" not in row and "cq_text" not in row and row["cq_id"] not in bank:
            raise SystemExit(f"no CQ text for {row['cq_id']}; cells.jsonl and frozen bank both lack it")
    return rows, (variants_dir if per_variant_complete else None), (shared_view_path if shared_view_path.exists() else None)


def _cell_id(row: dict, index: int) -> str:
    # Stable presentation identifier; no CQ, category, or variant is encoded.
    raw = f"{row['cq_id']}|{row.get('variant', '')}|{index}".encode()
    return "cell-" + hashlib.sha256(raw).hexdigest()[:16]


def _judge_evidence(row: dict) -> str:
    # The quoted evidence span is supplied to the annotator; judge score and
    # rationale remain absent. Formal runs store it in judge_response; the
    # simulated runner stores it as claimed_evidence.
    response = row.get("judge_response")
    if isinstance(response, dict) and response.get("evidence") is not None:
        return str(response["evidence"])[:2000]
    return str(row.get("claimed_evidence", ""))[:2000]


def _make_rows(
    cells: list[dict],
    variants_dir: Path | None,
    shared_view_path: Path | None,
    bank_path: Path | None,
) -> list[dict]:
    bank: dict[str, dict] = {}
    if bank_path:
        with bank_path.open(newline="", encoding="utf-8") as fh:
            bank = {row["cq_id"]: row for row in csv.DictReader(fh)}
    rows = []
    for index, cell in enumerate(cells):
        bank_row = bank.get(cell["cq_id"], {})
        variant = cell.get("variant", "")
        per_variant_view = _variant_rendered_view(variants_dir, variant)
        if per_variant_view is not None:
            rendered_view_path = per_variant_view
        elif shared_view_path is not None:
            rendered_view_path = shared_view_path
        else:
            raise SystemExit(f"no rendered-view material resolvable for cell {cell.get('cell_id', index)} (variant={variant!r})")
        rows.append({
            "cell_id": cell.get("cell_id") or _cell_id(cell, index),
            "cq_id": cell["cq_id"],
            "cluster_id": cell.get("cluster_id", cell["cq_id"]),
            "category": cell.get("category", bank_row.get("category", "")),
            "variant": variant,
            "cq_text": cell.get("question", cell.get("cq_text", bank_row.get("question", ""))),
            "judge_evidence_span": _judge_evidence(cell),
            "rendered_view_path": str(rendered_view_path.resolve()),
            "evidence_span_verbatim": "",
            "A": "",
            "rater_L1": "",
            "note": "",
        })
    return rows


def _constrained_shuffle(rows: list[dict], seed: int, min_gap: int = 20) -> list[dict]:
    """Seeded order with same-CQ cells separated by at least min_gap when feasible.

    Uses the standard "rearrange with minimum distance apart" greedy: at every
    position, place an eligible (not-in-cooldown) group with the most items
    still remaining. This greedy is exchange-argument optimal for uniform
    cooldown -- it succeeds whenever a valid arrangement exists at all, so no
    random retries are needed for feasibility. A seeded per-group tie-breaker
    keeps the result deterministic under equal remaining counts without
    affecting whether a feasible arrangement is found; items within a group
    are also seed-shuffled before placement.
    """
    rng = random.Random(seed)
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["cq_id"], []).append(row)
    for values in groups.values():
        rng.shuffle(values)
    if max(map(len, groups.values()), default=0) <= 1:
        output = list(rows)
        rng.shuffle(output)
        return output
    tie_breaker = {key: rng.random() for key in groups}
    remaining = {key: list(value) for key, value in groups.items()}
    output: list[dict] = []
    last_position: dict[str, int] = {}
    for _ in range(len(rows)):
        eligible = [
            key for key in remaining
            if key not in last_position or len(output) - last_position[key] >= min_gap
        ]
        if eligible:
            # Preregistered case: place the most-remaining eligible group.
            key = max(eligible, key=lambda k: (len(remaining[k]), tie_breaker[k]))
        else:
            # min_gap is provably infeasible for this row set (see module
            # docstring note below); relax to "least-recently placed" so the
            # achieved minimum gap is maximized rather than collapsing to an
            # unconstrained random shuffle. Never happens when the
            # (max_count-1)*(min_gap+1)+num_max <= n bound holds.
            key = max(
                remaining,
                key=lambda k: (len(output) - last_position.get(k, -min_gap - 1), tie_breaker[k]),
            )
        output.append(remaining[key].pop(0))
        last_position[key] = len(output) - 1
        if not remaining[key]:
            del remaining[key]
    assert len(output) == len(rows)
    gaps = [b - a for values in (
        [i for i, row in enumerate(output) if row["cq_id"] == cq_id] for cq_id in groups
    ) for a, b in zip(values, values[1:])]
    achieved = min(gaps, default=min_gap)
    if achieved < min_gap:
        print(
            f"WARNING: {min_gap}-position CQ separation is infeasible for this row set "
            f"(largest group vs. n); best achievable minimum gap used instead, "
            f"achieved={achieved}",
            file=sys.stderr,
        )
    return output


def _washout_selection(rows: list[dict], cells: list[dict], seed: int) -> list[dict]:
    if len(rows) <= WASHOUT_N:
        print(f"WARNING: run has {len(rows)} cells; washout reassessment contains all available cells, not preregistered n={WASHOUT_N}", file=sys.stderr)
        return list(rows)
    rng = random.Random(seed)
    groups: dict[tuple[str, int], list[dict]] = {}
    for row, cell in zip(rows, cells):
        # Category x judge band is the available operationalization of the
        # preregistered proportional stratification. The extra ASK-conflict
        # enrichment must be reviewed/selected by the project owner.
        band = int(cell.get("J", 0))
        groups.setdefault((row["category"], band), []).append(row)
    for values in groups.values():
        rng.shuffle(values)
    total = len(rows)
    allocation = {key: min(len(values), WASHOUT_N * len(values) // total) for key, values in groups.items()}
    while sum(allocation.values()) < WASHOUT_N:
        candidates = [key for key in sorted(groups) if allocation[key] < len(groups[key])]
        if not candidates:
            break
        key = max(candidates, key=lambda candidate: len(groups[candidate]) - allocation[candidate])
        allocation[key] += 1
    selected = [row for key in sorted(groups) for row in groups[key][:allocation[key]]]
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--domain", default="brick",
                        help="holdout domain (domains/<name>.toml); a non-brick domain resolves "
                             "its bank/variants through domains.py (no brick path-walk) and gets "
                             "no washout sheet — PREREG addendum 15 §15.5 registers no IOF washout")
    args = parser.parse_args()
    material = _domain_material(args.domain)
    bank_override, variants_override = material if material else (None, None)
    cells, variants_dir, shared_view_path = _read_cells(args.run_dir, bank_override, variants_override)
    rows = _make_rows(cells, variants_dir, shared_view_path,
                      bank_override if bank_override is not None else _find_bank(args.run_dir / "cells.jsonl"))
    outputs = [("labels_primary_pass_blank.csv", rows, PRIMARY_PASS_SEED)]
    if material is None:  # brick only: the registered 72-cell washout reassessment
        washout = _washout_selection(rows, cells, WASHOUT_REASSESSMENT_SEED)
        outputs.append(("labels_washout_reassessment_pass_blank.csv", washout, WASHOUT_REASSESSMENT_SEED))
    else:
        print("iof/non-brick domain: washout sheet not built (§15.5: no IOF washout)")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for filename, source, seed in outputs:
        path = args.out_dir / filename
        if path.exists() and not args.force:
            raise SystemExit(f"refusing to overwrite {path}; use --force")
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(_constrained_shuffle(source, seed))
        print(f"wrote {len(source)} rows to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
