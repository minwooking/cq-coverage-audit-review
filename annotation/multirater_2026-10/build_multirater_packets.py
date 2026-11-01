#!/usr/bin/env python3
"""Build N fully blinded, independently shuffled rater sheets (stdlib only).

Input: the existing blind sheet (labeling_sheet_blind_*.csv). Only the columns
cell_id, cq_id, category, question_text, rendered_view_path are read. Judge
score J, judge quote/span, AI draft, AH label, independent labels and the
variant column are never copied to a rater sheet. The cell_id -> opaque ID
mapping goes to keys/ (never distribute keys/).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import secrets
import shutil
import sys
from pathlib import Path

OUT_COLS = ("cell_id", "question_text", "category", "rendered_view_path",
            "S_label", "R_score", "evidence_span", "rater_note",
            "start_time", "end_time")
REQUIRED = ("cell_id", "cq_id", "category", "question_text", "rendered_view_path")
MIN_GAP = 20


def read_cells(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit(f"empty input: {path}")
    miss = [c for c in REQUIRED if c not in rows[0]]
    if miss:
        raise SystemExit(f"input missing columns: {miss}")
    ids = [r["cell_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate cell_id in input")
    return rows


def rater_seed(master_seed: str, rater_id: str) -> int:
    h = hashlib.sha256(f"{master_seed}|{rater_id}".encode()).digest()
    return int.from_bytes(h[:8], "big")


def constrained_shuffle(cq_ids: list[str], seed: int, min_gap: int = MIN_GAP,
                        max_tries: int = 2000) -> list[int]:
    """Return an order (indices) where equal cq_ids are >= min_gap apart."""
    n = len(cq_ids)
    for attempt in range(max_tries):
        rng = random.Random(f"{seed}:{attempt}")
        pools: dict[str, list[int]] = {}
        for i, c in enumerate(cq_ids):
            pools.setdefault(c, []).append(i)
        for p in pools.values():
            rng.shuffle(p)
        last: dict[str, int] = {}
        order: list[int] = []
        ok = True
        for pos in range(n):
            avail = [c for c, p in pools.items() if p and (c not in last or pos - last[c] >= min_gap)]
            if not avail:
                ok = False
                break
            # favour CQs with the most cells left (keeps the tail feasible)
            top = max(len(pools[c]) for c in avail)
            cand = [c for c in avail if len(pools[c]) >= top - 1]
            c = rng.choice(cand)
            order.append(pools[c].pop())
            last[c] = pos
        if ok:
            return order
    raise SystemExit(f"could not satisfy min gap {min_gap}; lower it or check CQ counts")


def check_gap(cq_seq: list[str], min_gap: int = MIN_GAP) -> int:
    last: dict[str, int] = {}
    worst = 10**9
    for pos, c in enumerate(cq_seq):
        if c in last:
            worst = min(worst, pos - last[c])
        last[c] = pos
    return worst


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True, type=Path, help="existing blind sheet CSV")
    ap.add_argument("--raters", required=True, nargs="+", help="2-3 rater IDs (e.g. R1 R2 R3)")
    ap.add_argument("--master-seed", required=True, help="author-chosen string; per-rater seed = sha256(master|rater)")
    ap.add_argument("--out-dir", type=Path, default=Path(__file__).parent / "packets")
    ap.add_argument("--keys-dir", type=Path, default=Path(__file__).parent / "keys")
    ap.add_argument("--anonymize-views", action="store_true",
                    help="copy view files under random names per rater (hides variant letter in path)")
    ap.add_argument("--min-gap", type=int, default=MIN_GAP)
    a = ap.parse_args(argv)

    if not 2 <= len(a.raters) <= 3 or len(set(a.raters)) != len(a.raters):
        raise SystemExit("--raters needs 2 or 3 distinct IDs")
    cells = read_cells(a.input)
    if not a.anonymize_views:
        print("WARNING: view paths keep variant-specific file names (variant leaks). "
              "Use --anonymize-views for distribution.", file=sys.stderr)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    a.keys_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"input": str(a.input), "n_cells": len(cells), "min_gap": a.min_gap,
                "anonymize_views": a.anonymize_views, "raters": {}}
    for rid in a.raters:
        seed = rater_seed(a.master_seed, rid)
        order = constrained_shuffle([c["cq_id"] for c in cells], seed, a.min_gap)
        gap = check_gap([cells[i]["cq_id"] for i in order], a.min_gap)
        if gap < a.min_gap:
            raise SystemExit(f"gap check failed for {rid}: {gap}")
        rng = random.Random(seed ^ 0x5EED)
        opaque, used = [], set()
        for _ in cells:
            while True:
                o = "X" + format(rng.getrandbits(40), "010x")
                if o not in used:
                    used.add(o)
                    opaque.append(o)
                    break
        view_map: dict[str, str] = {}
        rdir = a.out_dir / rid
        rdir.mkdir(parents=True, exist_ok=True)
        if a.anonymize_views:
            vdir = rdir / "views"
            vdir.mkdir(exist_ok=True)
            for src in sorted({c["rendered_view_path"] for c in cells}):
                name = "v" + secrets.token_hex(5) + ".txt"  # random, not reproducible; recorded in key
                shutil.copyfile(src, vdir / name)
                view_map[src] = f"views/{name}"
        sheet = rdir / f"sheet_{rid}.csv"
        with sheet.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=OUT_COLS)
            w.writeheader()
            for pos, i in enumerate(order):
                c = cells[i]
                w.writerow({"cell_id": opaque[pos], "question_text": c["question_text"],
                            "category": c["category"],
                            "rendered_view_path": view_map.get(c["rendered_view_path"], c["rendered_view_path"]),
                            "S_label": "", "R_score": "", "evidence_span": "", "rater_note": "",
                            "start_time": "", "end_time": ""})
        key = a.keys_dir / f"key_{rid}.csv"
        with key.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["opaque_id", "cell_id", "position"])
            for pos, i in enumerate(order):
                w.writerow([opaque[pos], cells[i]["cell_id"], pos + 1])
        manifest["raters"][rid] = {
            "seed": seed, "min_gap_achieved": gap,
            "sheet_sha256": hashlib.sha256(sheet.read_bytes()).hexdigest(),
            "view_map": view_map if a.anonymize_views else None}
        print(f"{rid}: {len(cells)} cells, min same-CQ gap {gap}, sheet {sheet}")
    (a.keys_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"keys written to {a.keys_dir} (do NOT distribute)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
