#!/usr/bin/env python3
# AI-generated draft: a person must review and test it before use.  (Addendum 47, batch 2.)
"""Deterministic author-screen sample (47.3 'Author screen', CP-1) for b1, its round 2, and b2.

Procedure (the one that reproduces the round-1 and round-2 samples of b1 exactly):
one random.Random(seed); categories in canonical order; per category the passing cq_ids
sorted by number, then shuffled; the first k_c are kept; the sample is written in sorted cq_id order.

k_c: the `total` rows are split equally over the categories that have passing ids; the
remainder of total / m goes one row each to the first categories in canonical order; a
category with fewer passing ids than its share gives all of them and the missing rows are
dealt one at a time, in canonical order, to categories that still have unsampled ids.
With six categories and total 30 this is 5 per category (b1, round 2); with the three
categories that hold b2 rows it is 10 each.

The sheet carries the same five columns as the sample plus the five author criteria
columns of screen_b1_sheet.csv (blank).  Only the five text columns of the validated
rows are read; no rendering, eligibility, graph or judge file is touched.

Usage:
    python3 screen_sample.py --preset b2 --out screen_b2_sample.csv --sheet screen_b2_sheet.csv
    python3 screen_sample.py --rows validated_b1_r2.jsonl --seed 20260914 --out s.csv --sheet t.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

import common
from common import BANK, CATEGORIES

SAMPLE_COLUMNS = ["cq_id", "category", "question", "grounding", "expected_answer"]
CRITERIA_COLUMNS = ["형식_불량", "답_스냅샷_불일치", "grounding_대상아님", "답_누설또는모호", "기존문항과_거의동일"]
TOTAL = 30
PRESETS = {  # seed per 47.3 / 47.A1.5 / BATCH2_PROCEDURE.md
    "b1": {"seed": 20260913, "rows": "round1/validated_b1.jsonl"},
    "r2": {"seed": 20260914, "rows": "validated_b1_r2.jsonl", "eol": "\r\n"},  # the committed r2 files are CRLF
    "b2": {"seed": 20260915, "rows": "validated_b2.jsonl"},
}


def allocate_sample(counts: dict[str, int], total: int = TOTAL) -> dict[str, int]:
    """Rows per category (see module docstring).  counts = passing ids per category."""
    cats = [c for c in CATEGORIES if counts.get(c, 0) > 0]
    if not cats:
        raise ValueError("no passing rows")
    total = min(total, sum(counts[c] for c in cats))
    base, rem = divmod(total, len(cats))
    k = {c: base + (1 if i < rem else 0) for i, c in enumerate(cats)}
    spill = 0
    for c in cats:
        if k[c] > counts[c]:
            spill += k[c] - counts[c]
            k[c] = counts[c]
    while spill:
        progressed = False
        for c in cats:
            if spill and k[c] < counts[c]:
                k[c] += 1
                spill -= 1
                progressed = True
        if not progressed:
            break
    return {c: k.get(c, 0) for c in CATEGORIES}


def draw_sample(rows: list[dict], seed: int, total: int = TOTAL) -> list[dict]:
    by_cat = {c: sorted((r["cq_id"] for r in rows if r["category"] == c), key=common.cq_sort_key)
              for c in CATEGORIES}
    k = allocate_sample({c: len(v) for c, v in by_cat.items()}, total)
    rng = random.Random(seed)
    chosen: set[str] = set()
    for c in CATEGORIES:
        ids = list(by_cat[c])
        if not ids:
            continue
        rng.shuffle(ids)
        chosen.update(ids[:k[c]])
    by_id = {r["cq_id"]: r for r in rows}
    return [{col: by_id[i][col] for col in SAMPLE_COLUMNS} for i in sorted(chosen, key=common.cq_sort_key)]


def write_csv(path: Path, header: list[str], rows: list[list], eol: str = "\n") -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator=eol)
        w.writerow(header)
        w.writerows(rows)


def write_outputs(sample: list[dict], out: Path, sheet: Path | None, eol: str = "\n") -> None:
    write_csv(out, SAMPLE_COLUMNS, [[r[c] for c in SAMPLE_COLUMNS] for r in sample], eol)
    if sheet:
        write_csv(sheet, SAMPLE_COLUMNS + CRITERIA_COLUMNS,
                  [[r[c] for c in SAMPLE_COLUMNS] + [""] * len(CRITERIA_COLUMNS) for r in sample], eol)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--preset", choices=sorted(PRESETS), default=None)
    ap.add_argument("--rows", default=None, help="validated rows jsonl (default: the preset's file)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--total", type=int, default=TOTAL)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sheet", default=None)
    ap.add_argument("--crlf", action="store_true", help="CRLF line ends (the committed r2 files use them)")
    args = ap.parse_args(argv)
    preset = PRESETS.get(args.preset or "", {})
    seed = args.seed if args.seed is not None else preset.get("seed")
    rows_path = Path(args.rows) if args.rows else (BANK / preset["rows"] if preset else None)
    if seed is None or rows_path is None:
        ap.error("give --preset or both --rows and --seed")
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    sample = draw_sample(rows, seed, args.total)
    eol = "\r\n" if (args.crlf or preset.get("eol") == "\r\n") else "\n"
    write_outputs(sample, Path(args.out), Path(args.sheet) if args.sheet else None, eol)
    k = {c: sum(1 for r in sample if r["category"] == c) for c in CATEGORIES}
    print(json.dumps({"seed": seed, "n": len(sample), "per_category": k}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
