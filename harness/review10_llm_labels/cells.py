#!/usr/bin/env python3
"""Cell sets of addendum 30 (review10_llm_labels).  AI-generated; review and test before use.

Tier 1  = the 188 primary holdout cells, read from harness/review6_raters/cells_manifest.json (pinned by sha256 in
          PLAN.md; every view is sha256-checked by run_rater.material_for when it is read).
Tier 2a = the (variant, question) cells of the 216-cell grid of the length experiment that are not primary (subgraph views).
Tier 2b = the 72 natural-documentation A/B cells of addendum 27 (subgraph views).
Tiers 3a-3e (amendment A1): manifests/<set>.json written by build_views.py (paraphrases, v2 extras, development bank, second
domain, expansion draft).
Only the question and the category of the bank are read; the bank's grounding and expected_answer columns are never read.
It never opens site_key*, labeling_sheet_key*, human_labels_export*, views_for_raters.zip, .env or sealed files.

Row format = the rows of cells_manifest.json (cell_id, variant, cq_id, cluster_id, catKo, q, qko, view_kind, view_path,
view_sha256, est_input_tokens), so run_rater.material_for / est_for work on every tier unchanged.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
sys.path.insert(0, str(HARNESS / "review6_raters"))
sys.path.insert(0, str(HARNESS / "llm_rater_luna_2026-10-15"))
sys.path.insert(0, str(HARNESS))
import rater_luna as rl  # noqa: E402  (prompt + user_message constants only)

MANIFEST6 = HARNESS / "review6_raters" / "cells_manifest.json"
BANK = ACCESS / "bank" / "cq_bank_brick_v1.csv"
LENGTH_MANIFEST = HARNESS / "length_experiment" / "inputs" / "manifest.jsonl"
NATURAL_MANIFEST = HARNESS / "review6_natural" / "inputs" / "manifest.jsonl"
ORDER_SEED = 20260913
TIERS = ("1", "2a", "2b", "3a", "3b", "3c", "3d", "3e")      # queue order (PLAN 30.12)
MANIFESTS = HERE / "manifests"
T3_SETS = {"3a": ["para"], "3b": ["v2x"], "3c": ["dev"], "3d": ["mfg", "mfgko"], "3e": ["exp"]}
INTERNAL_TIERS = ("3d",)      # second domain: raw call records are not committed


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _primary_manifest() -> list[dict]:
    m = json.loads(MANIFEST6.read_text(encoding="utf-8"))
    return sorted(m["cells"], key=lambda c: c["cell_id"])


def _bank_questions() -> dict[str, dict]:
    out = {}
    with BANK.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[r["cq_id"]] = {"q": r["question"], "cat": r["category"]}   # nothing else is read from the bank
    return out


def _tier2_rows(manifest_path: Path, prefix: str, exclude: set[tuple[str, str]]) -> list[dict]:
    prim = _primary_manifest()
    cat_ko = {c["cat"]: c["catKo"] for c in prim}
    qko = {c["cq_id"]: c["qko"] for c in prim}
    bank = _bank_questions()
    rows = []
    for l in manifest_path.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        if r["condition"] != "subgraph" or r["status"] != "ok":
            continue
        key = (r["variant"], r["cq_id"])
        if key in exclude:
            continue
        b = bank[r["cq_id"]]
        path = ACCESS / r["path"]
        if sha256_file(path) != r["sha256"]:
            raise SystemExit(f"{r['path']}: sha256 mismatch")
        cell = {"catKo": cat_ko[b["cat"]], "q": b["q"], "qko": qko.get(r["cq_id"], "")}
        text = path.read_text(encoding="utf-8")
        est = -(-(len(rl.RATER_PROMPT) + len(rl.user_message(text, cell))) // 4)
        rows.append({"cell_id": f"{prefix}:{r['variant']}:{r['cq_id']}", "variant": r["variant"], "cq_id": r["cq_id"],
                     "cluster_id": r["cluster_id"], "cat": b["cat"], "catKo": cell["catKo"], "q": cell["q"],
                     "qko": cell["qko"], "view_kind": "subgraph", "view_path": r["path"], "view_sha256": r["sha256"],
                     "view_chars": len(text), "est_input_tokens": est})
    return sorted(rows, key=lambda c: c["cell_id"])


def load_tier(tier: str) -> list[dict]:
    """Rows of a tier, sorted by cell_id."""
    if tier == "1":
        return _primary_manifest()
    prim = {(c["variant"], c["cq_id"]) for c in _primary_manifest()}
    if tier == "2a":
        return _tier2_rows(LENGTH_MANIFEST, "grid", prim)
    if tier == "2b":
        return _tier2_rows(NATURAL_MANIFEST, "natural", set())
    if tier in T3_SETS:
        rows = []
        for name in T3_SETS[tier]:
            p = MANIFESTS / f"{name}.json"
            if not p.exists():
                raise SystemExit(f"{p.name} missing: run build_views.py first")
            rows += json.loads(p.read_text(encoding="utf-8"))["rows"]
        return sorted(rows, key=lambda c: c["cell_id"])
    raise SystemExit(f"unknown tier {tier}")


def order(rows: list[dict]) -> list[str]:
    """The processing order of the plan: random.Random(20260913).shuffle(sorted cell ids)."""
    ids = sorted(r["cell_id"] for r in rows)
    random.Random(ORDER_SEED).shuffle(ids)
    return ids


if __name__ == "__main__":
    for t in TIERS:
        rows = load_tier(t)
        by = {}
        for r in rows:
            by[r["view_kind"]] = by.get(r["view_kind"], 0) + 1
        print(t, len(rows), by, "clusters", len({r["cluster_id"] for r in rows}),
              "est_tokens", sum(r["est_input_tokens"] for r in rows), "first3", order(rows)[:3])
