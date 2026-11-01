#!/usr/bin/env python3
# AI-generated draft: a person must review and test it before use.  (Addendum 47, C4.)
"""Eligibility of the frozen eqv2 bank b1 on the FULL renderings A and B (addendum 47.4).

For every bank row and each variant V in {A, B}:
    can_ablate = run_holdout._grounding_match_info(R_V, {"grounding": ...})["can_ablate"]
with R_V = harness/variants/V/rendered_view.txt read whole.  The rule code is imported, never
edited; there is no allowlist and no exception.  Pure local computation: no model call, no
network, no remote host.

Reads (and only these): the frozen bank (columns cq_id, category, grounding), the two full
renderings; imports harness/run_holdout.py.  Every input hash is asserted before use.
Writes: bank/eqv2_2026-10/eligibility_b1.json (not committed by this tool).

Usage:  python eligibility.py [--out PATH]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
BANK_DIR = TOOLS.parent
ACCESS = BANK_DIR.parent.parent
HARNESS = ACCESS / "harness"

BANK_CSV = BANK_DIR / "cq_bank_brick_eqv2_b1.csv"
BANK_SHA256 = "b8478fca86de80b0c998eb6e5a3f7f11ef62433bcc75428e0bf8abe03d336efe"
RENDER = {"A": HARNESS / "variants" / "A" / "rendered_view.txt",
          "B": HARNESS / "variants" / "B" / "rendered_view.txt"}
RENDER_SHA256 = {"A": "f6cca070efee8d933b41ba96d2d2b9c666af5bd804926c22ae0834b099830b98",
                 "B": "d0b9543521340c2719381cc7d1312b704322c0e33d452166212840854cbc165f"}
RUN_HOLDOUT = HARNESS / "run_holdout.py"
RUN_HOLDOUT_SHA256 = "c69f105c4e9d9903549a163bc4ba3b7fbe99994ee103392e39102364556ed3ad"
RUBRIC_SHA256 = "85e208799f10b756125c524dc43222064ac946f3c01f000ee03cf331800cee72"
VARIANTS = ("A", "B")
# Column filter: grounding is the rule's input; expected_answer and every other column is dropped.
BANK_COLUMNS = ("cq_id", "category", "grounding")
OUT_DEFAULT = BANK_DIR / "eligibility_b1.json"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def load_bank(path: Path = BANK_CSV, columns=BANK_COLUMNS, expect_sha: str | None = BANK_SHA256) -> list[dict]:
    raw = path.read_bytes()
    if expect_sha is not None and sha256_bytes(raw) != expect_sha:
        raise SystemExit(f"bank sha256 mismatch: {sha256_bytes(raw)}")
    text = raw.decode("utf-8")
    return [{k: r[k] for k in columns} for r in csv.DictReader(text.splitlines(keepends=True))]


def import_rule():
    """Import run_holdout after asserting its file hash; assert the rubric hash on the imported value."""
    got = sha256_file(RUN_HOLDOUT)
    if got != RUN_HOLDOUT_SHA256:
        raise SystemExit(f"run_holdout.py sha256 mismatch: {got}")
    sys.path.insert(0, str(HARNESS))
    import run_holdout as rh  # noqa: E402
    rub = sha256_bytes(rh.RUBRIC.encode("utf-8"))
    if rub != RUBRIC_SHA256:
        raise SystemExit(f"RUBRIC (module value) sha256 mismatch: {rub}")
    return rh


def classify(info: dict) -> str:
    if info["can_ablate"]:
        return "eligible"
    if not info["matching_line_numbers"]:
        return "no_matching_line"
    return "missing_required_anchor"


def evaluate_cell(rule, view: str, row: dict) -> dict:
    """Apply the paper's rule to one (view, row); only the grounding string is passed in."""
    info = rule(view, {"grounding": row["grounding"]})
    return {
        "can_ablate": bool(info["can_ablate"]),
        "reason": classify(info),
        "n_matching_lines": len(info["matching_line_numbers"]),
        "anchors": list(info["anchors"]),
        "missed_anchors": list(info["missing_required_grounding_anchors"]),
    }


def compute(rows: list[dict], views: dict[str, str], rule) -> list[dict]:
    cells = []
    for v in VARIANTS:
        for r in rows:
            c = evaluate_cell(rule, views[v], r)
            cells.append({"cell_id": f"{v}:{r['cq_id']}", "variant": v, "cq_id": r["cq_id"],
                          "category": r["category"], **c})
    return sorted(cells, key=lambda c: (c["variant"], c["cq_id"]))


def summarize(cells: list[dict]) -> dict:
    out: dict = {"by_variant": {}, "by_variant_category": {}, "reasons": {}}
    for v in VARIANTS:
        vc = [c for c in cells if c["variant"] == v]
        out["by_variant"][v] = {"n": len(vc), "eligible": sum(c["can_ablate"] for c in vc)}
        out["reasons"][v] = dict(sorted(Counter(c["reason"] for c in vc).items()))
        cats = sorted({c["category"] for c in vc})
        out["by_variant_category"][v] = {k: {"n": sum(1 for c in vc if c["category"] == k),
                                             "eligible": sum(1 for c in vc if c["category"] == k and c["can_ablate"])}
                                         for k in cats}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    args = ap.parse_args(argv)
    rh = import_rule()
    rows = load_bank()
    views = {}
    for v in VARIANTS:
        raw = RENDER[v].read_bytes()
        if sha256_bytes(raw) != RENDER_SHA256[v]:
            raise SystemExit(f"rendering {v} sha256 mismatch")
        views[v] = raw.decode("utf-8")
    cells = compute(rows, views, rh._grounding_match_info)
    doc = {
        "study": "addendum 47 (plan-based, exploratory), C4 eligibility, bank b1",
        "rule": "run_holdout._grounding_match_info(R_V, row)['can_ablate'] on the full rendering; no allowlist",
        "inputs": {"bank_sha256": BANK_SHA256, "rendering_sha256": RENDER_SHA256,
                   "run_holdout_sha256": RUN_HOLDOUT_SHA256, "rubric_sha256": RUBRIC_SHA256},
        "n_rows": len(rows),
        "summary": summarize(cells),
        "cells": cells,
    }
    args.out.write_text(json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    s = doc["summary"]["by_variant"]
    print(f"rows={len(rows)} eligible A={s['A']['eligible']} B={s['B']['eligible']} -> {args.out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
