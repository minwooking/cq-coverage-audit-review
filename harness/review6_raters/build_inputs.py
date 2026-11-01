#!/usr/bin/env python3
"""Build cells_manifest.json for addendum 28 (review6_raters) WITHOUT opening any sealed file.

AI-generated code: review and test before use.  Reads only:
  bank/cq_bank_brick_v1.csv                         question text / category per CQ
  annotation/multirater_2026-10/labeling_site/data/cells.json   question text, Korean category, Korean translation
                                                    (keyed by an OPAQUE id; the key file is never opened)
  harness/real_run/cells.jsonl                      cell id, cluster id, variant of the 188 primary cells
  harness/length_experiment/inputs/manifest.jsonl   subgraph / full rendering paths + sha256
  harness/llm_rater_luna_2026-10-15/subgraph_r25/luna_rater_subgraph_raw.jsonl   S21 run (view sha256 cross-check)
It never opens site_key*, labeling_sheet_key*, human_labels_export*, views_for_raters.zip, .env or sealed files.
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
sys.path.insert(0, str(HARNESS / "llm_rater_luna_2026-10-15"))
sys.path.insert(0, str(HARNESS))
import rater_luna as rl  # noqa: E402  (prompt + user_message only; load_site/load_views are NEVER called)

BANK = ACCESS / "bank" / "cq_bank_brick_v1.csv"
SITE_CELLS = ACCESS / "annotation" / "multirater_2026-10" / "labeling_site" / "data" / "cells.json"
CELLS = HARNESS / "real_run" / "cells.jsonl"
LENGTH_MANIFEST = HARNESS / "length_experiment" / "inputs" / "manifest.jsonl"
S21_RAW = HARNESS / "llm_rater_luna_2026-10-15" / "subgraph_r25" / "luna_rater_subgraph_raw.jsonl"
OUT = HERE / "cells_manifest.json"
AUX_SEED = 20260913
AUX_N = 48


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build() -> dict:
    bank = {r["cq_id"]: r for r in csv.DictReader(BANK.open(encoding="utf-8"))}
    q2cq = {}
    for cq, r in bank.items():
        q2cq.setdefault(r["question"], []).append(cq)
    site = json.loads(SITE_CELLS.read_text(encoding="utf-8"))
    qinfo = {}
    for c in site:
        info = (c["catKo"], c.get("qko") or "", c["cat"])
        prev = qinfo.setdefault(c["q"], info)
        if prev != info:
            raise SystemExit(f"question {c['q']!r} has inconsistent category/translation across site cells")
    cq_info = {}
    for q, (catko, qko, cat) in qinfo.items():
        cqs = q2cq.get(q, [])
        if len(cqs) != 1:
            raise SystemExit(f"question text {q!r} maps to {cqs} in the bank (need exactly 1)")
        if bank[cqs[0]]["category"] != cat:
            raise SystemExit(f"category mismatch for {cqs[0]}")
        cq_info[cqs[0]] = {"q": q, "qko": qko, "catKo": catko, "cat": cat}
    cells = [json.loads(l) for l in CELLS.read_text(encoding="utf-8").splitlines() if l.strip()]
    prim = sorted((c for c in cells if c["cell_id"].startswith("primary:")), key=lambda c: c["cell_id"])
    if len(prim) != 188:
        raise SystemExit(f"expected 188 primary cells, got {len(prim)}")
    man = [json.loads(l) for l in LENGTH_MANIFEST.read_text(encoding="utf-8").splitlines() if l.strip()]
    sg = {(r["variant"], r["cq_id"]): r for r in man if r["condition"] == "subgraph"}
    full = {(r["variant"], r["cq_id"]): r for r in man if r["condition"] == "full"}
    s21 = {}
    for l in S21_RAW.read_text(encoding="utf-8").splitlines():
        r = json.loads(l)
        if r.get("valid") and r["cell_id"] not in s21:
            s21[r["cell_id"]] = r
    out_cells = []
    for c in prim:
        _, v, q = c["cell_id"].split(":")
        if q not in cq_info:
            raise SystemExit(f"{c['cell_id']}: cq {q} has no site question info")
        info = cq_info[q]
        f = full[(v, q)]
        s = sg[(v, q)]
        fpath = ACCESS / f["path"]
        if sha256_file(fpath) != f["sha256"]:
            raise SystemExit(f"{c['cell_id']}: full rendering sha mismatch")
        if s["status"] == "ok":
            spath = ACCESS / s["path"]
            if sha256_file(spath) != s["sha256"]:
                raise SystemExit(f"{c['cell_id']}: subgraph sha mismatch")
            kind, path, sha, chars = "subgraph", s["path"], s["sha256"], len(spath.read_text(encoding="utf-8"))
        else:
            kind, path, sha, chars = "full_view_fallback", f["path"], f["sha256"], len(fpath.read_text(encoding="utf-8"))
        if s21[c["cell_id"]]["view_sha256"] != sha:
            raise SystemExit(f"{c['cell_id']}: S21 view sha differs from the rebuilt material")
        text = (ACCESS / path).read_text(encoding="utf-8")
        cell = {"catKo": info["catKo"], "q": info["q"], "qko": info["qko"]}
        est = -(-(len(rl.RATER_PROMPT) + len(rl.user_message(text, cell))) // 4)
        ftext = fpath.read_text(encoding="utf-8")
        est_full = -(-(len(rl.RATER_PROMPT) + len(rl.user_message(ftext, cell))) // 4)
        out_cells.append({"cell_id": c["cell_id"], "variant": v, "cq_id": q, "cluster_id": c["cluster_id"],
                          "J_registered_judge": c["J"], "cat": info["cat"], "catKo": info["catKo"],
                          "q": info["q"], "qko": info["qko"], "view_kind": kind, "view_path": path,
                          "view_sha256": sha, "view_chars": chars, "est_input_tokens": est,
                          "full_path": f["path"], "full_sha256": f["sha256"], "est_input_tokens_full": est_full})
    ids = [c["cell_id"] for c in out_cells]
    aux = random.Random(AUX_SEED).sample(ids, AUX_N)
    by = {}
    for c in out_cells:
        d = by.setdefault(c["view_kind"], [0, 0])
        d[0] += 1
        d[1] += c["est_input_tokens"]
    emap = {c["cell_id"]: c for c in out_cells}
    return {"n_cells": len(out_cells), "prompt_sha256": rl.RATER_PROMPT_SHA256,
            "by_view_kind": {k: {"cells": v[0], "est_input_tokens": v[1]} for k, v in by.items()},
            "est_input_tokens_one_run_188": sum(c["est_input_tokens"] for c in out_cells),
            "aux_sample_seed": AUX_SEED, "aux_sample_rule": "random.Random(20260913).sample(sorted 188 primary cell ids, 48)",
            "aux_sample": aux,
            "aux_est_input_tokens_full_view": sum(emap[i]["est_input_tokens_full"] for i in aux),
            "cells": out_cells}


if __name__ == "__main__":
    m = build()
    OUT.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in m.items() if k not in ("cells", "aux_sample")}, indent=1))
    print("sha256", sha256_file(OUT))
