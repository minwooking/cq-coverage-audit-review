#!/usr/bin/env python3
# AI-generated draft: a person must review and test it before use.  (Addendum 47, batch 2.)
"""Batch-2 item list (addendum 47, 47.3 'Batch 2'; rules in BATCH2_PROCEDURE.md).

Pure planning, no model call, no network.  Inputs, each read once:
  * the batch-2 size N2 (--size-file; the file is read here and NOWHERE in the drafting,
    validation or de-duplication tools, which read only the batch2_plan.json this writes),
  * frame_summary.json (the frame tails; never rewritten),
  * the committed b1 validation report and validated rows (which tail items b1's single
    replacement wave consumed).

Rules (they use only quota and tail sizes -- never eligibility, scores or yields):
  1. quota per category = N2 / 6.
  2. capacity per category = frame tail minus the tail items b1 consumed.
  3. shortfall is redistributed by frame.allocate (round-robin, largest frame first).
  4. items are taken from the front of each tail, in the order frame.py fixed (seed 20260913).
  5. ids CQE505.. in canonical category order, tail order within a category.

b1's consumption of the tail is derived, not assumed: validate.py's replacement wave walks
each category's tail strictly in order (one pointer per category) and every dropped row of
a tail-bearing category was replaced.  So the consumed prefix of a category is
tail[:k+1] where k is the largest tail index among the terms of rows that replaced a
dropped row (a candidate that was drafted but failed validation sits below k and is
consumed too).  The replacing rows are the report's `replaced_by` ids.

Usage:
    python3 plan_b2.py --size-file <path to the size json> [--out batch2_plan.json] [--check]
    python3 plan_b2.py --b1-extra <cq_bank_brick_eqv2_b1.csv> --out b1_as_extra.jsonl
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import common
import frame as frame_mod
from common import BANK, CATEGORIES

B1_REPORT = BANK / "validate_report_b1_r2.json"
B1_VALIDATED = BANK / "validated_b1_r2.jsonl"
B1_BANK = BANK / "cq_bank_brick_eqv2_b1.csv"


class PlanError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def items_sha256(items: list[dict]) -> str:
    """Canonical hash of the item list: sorted keys, no whitespace, UTF-8."""
    blob = json.dumps(items, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def b1_replacing_terms(report: dict, validated: list[dict]) -> dict[str, list[str]]:
    """Per category, the terms of the rows that replaced a dropped b1 row (the terms the
    report's `replaced_by` ids carry in the validated rows)."""
    by_id = {r["cq_id"]: r for r in validated}
    out: dict[str, list[str]] = {c: [] for c in CATEGORIES}
    for rec in report["dropped_records"]:
        rb = rec.get("replaced_by")
        if rb is None:
            continue
        row = by_id[rb]
        out[row["category"]].append(row["term"])
    return out


def b1_used_tail_counts(frame: dict, report: dict, validated: list[dict]) -> dict[str, int]:
    """Length of the tail prefix b1 consumed, per category (0 when nothing replaced)."""
    used: dict[str, int] = {}
    repl = b1_replacing_terms(report, validated)
    for cat in CATEGORIES:
        tail = frame["categories"][cat]["frame_tail"]
        pos = {t: i for i, t in enumerate(tail)}
        idx = []
        for t in repl[cat]:
            if t not in pos:
                raise PlanError(f"{cat}: replacing term {t} is not in the frame tail")
            idx.append(pos[t])
        if len(set(idx)) != len(idx):
            raise PlanError(f"{cat}: a tail term replaced two rows")
        used[cat] = (max(idx) + 1) if idx else 0
    # Rows of tail-less categories that were dropped stay unreplaced; nothing else may
    # have consumed a tail.
    for rec in report["dropped_records"]:
        if rec.get("replaced_by") is None and frame["categories"][rec["category"]]["frame_tail"]:
            raise PlanError(f"{rec['cq_id']}: unreplaced drop in a category that has a tail")
    return used


def build_plan(frame: dict, report: dict, validated: list[dict], n2: int) -> dict:
    if n2 <= 0 or n2 % len(CATEGORIES):
        raise PlanError(f"N2={n2} must be a positive multiple of {len(CATEGORIES)}")
    quota = n2 // len(CATEGORIES)
    used = b1_used_tail_counts(frame, report, validated)
    remaining = {c: frame["categories"][c]["frame_tail"][used[c]:] for c in CATEGORIES}
    total_cap = sum(len(v) for v in remaining.values())
    if total_cap < n2:
        raise PlanError(f"total remaining capacity {total_cap} < N2 {n2}")
    alloc, deficit = frame_mod.allocate(remaining, quota=quota)
    if deficit:
        raise PlanError(f"allocation left a deficit of {deficit}")
    if sum(alloc.values()) != n2:
        raise PlanError("allocation does not sum to N2")
    cats = {}
    items = []
    n = 0
    for cat in CATEGORIES:
        catd = frame["categories"][cat]
        tail_total = len(catd["frame_tail"])
        first = used[cat]
        k = alloc[cat]
        cats[cat] = {"tail_total": tail_total, "b1_used": used[cat], "remaining": len(remaining[cat]),
                     "quota": quota, "quota_taken": min(quota, len(remaining[cat])),
                     "redistributed_in": k - min(quota, len(remaining[cat])),
                     "allocation_b2": k, "tail_start_index": first, "tail_next_index": first + k}
        for off in range(k):
            ti = first + off
            items.append({"cq_id": f"CQE{common.B2_FIRST_ID + n:03d}", "category": cat,
                          "term": catd["frame_tail"][ti], "frame_rank": catd["frame_tail_frame_rank"][ti],
                          "tail_index": ti})
            n += 1
    return {"ai_generated_draft": True, "batch": "b2", "plan_based": True, "exploratory": True,
            "n2": n2, "quota_per_category": quota, "seed_frame": frame["seed"],
            "prompt_sha256": common.expected_prompt_sha256(),
            "categories": cats, "n_items": len(items), "items": items,
            "items_sha256": items_sha256(items)}


def plan_inputs(size_file: Path, frame_path: Path, report_path: Path, validated_path: Path):
    n2 = int(json.loads(Path(size_file).read_text(encoding="utf-8"))["N2"])
    frame = json.loads(Path(frame_path).read_text(encoding="utf-8"))
    return n2, frame, json.loads(Path(report_path).read_text(encoding="utf-8")), read_jsonl(validated_path)


def render(plan: dict) -> str:
    return json.dumps(plan, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


def b1_bank_as_extra_rows(bank_csv: Path) -> list[dict]:
    """The frozen b1 bank as de-duplication reference rows (cq_id, category, question,
    grounding) -- the columns dedup.build_context reads.  The csv is only read."""
    with Path(bank_csv).open(newline="", encoding="utf-8") as fh:
        return [{"cq_id": r["cq_id"], "category": r["category"], "question": r["question"],
                 "grounding": r["grounding"]} for r in csv.DictReader(fh)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--size-file", default=None, help="json with the key N2 (read here only)")
    ap.add_argument("--frame", default=str(common.FRAME_SUMMARY))
    ap.add_argument("--b1-report", default=str(B1_REPORT))
    ap.add_argument("--b1-validated", default=str(B1_VALIDATED))
    ap.add_argument("--out", default=None)
    ap.add_argument("--check", action="store_true", help="recompute and compare with --out; write nothing")
    ap.add_argument("--b1-extra", default=None, help="convert this b1 bank csv to a de-dup reference jsonl (--out)")
    args = ap.parse_args(argv)

    if args.b1_extra:
        rows = b1_bank_as_extra_rows(Path(args.b1_extra))
        out = Path(args.out or "b1_as_extra.jsonl")
        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        print(f"wrote {len(rows)} b1 reference rows -> {out}")
        return 0

    if not args.size_file:
        ap.error("--size-file is required")
    n2, frame, report, validated = plan_inputs(Path(args.size_file), Path(args.frame),
                                               Path(args.b1_report), Path(args.b1_validated))
    plan = build_plan(frame, report, validated, n2)
    out = Path(args.out or str(BANK / "batch2_plan.json"))
    text = render(plan)
    if args.check:
        same = out.exists() and out.read_text(encoding="utf-8") == text
        print(json.dumps({"matches_existing": same, "items_sha256": plan["items_sha256"]}))
        return 0 if same else 1
    out.write_text(text, encoding="utf-8")
    print(json.dumps({"n_items": plan["n_items"], "items_sha256": plan["items_sha256"],
                      "allocation_b2": {c: v["allocation_b2"] for c, v in plan["categories"].items()}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
