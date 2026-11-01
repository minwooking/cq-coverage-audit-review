#!/usr/bin/env python3
"""Cell manifests and view cache of addendum 32 (Study 2).  AI-generated; review and test before use.  NO model call.

  s2_cells.py stage1     -> manifests/stage1.json  (188 primary cells + the 24 registered ablated controls; views built by
                            s2_views.build_view with the registered judge's quoted evidence located in the rendering) and
                            views_cache/<id>.txt (git-ignored; rebuilt deterministically; sha256 of every view in the manifest)
  s2_cells.py stage2     -> manifests/stage2.json  (after the bank freeze and the judge runs; see s2_stage2.py)

Rows follow review10's cell rows (cell_id, variant, cq_id, cluster_id, cat, catKo, q, qko, view_kind, view_sha256, ...), so
the runner works on them unchanged.  The bank's expected_answer is read here only to measure the term coverage of the view
(PLAN 32.4); it never enters a view or a prompt.  Reads no human label, no site key, no export, no zip.
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HARNESS))
import s2_views as V  # noqa: E402
import run_holdout as rh  # noqa: E402

MANIFESTS = HERE / "manifests"
CACHE = HERE / "views_cache"
BANK_V1 = ACCESS / "bank" / "cq_bank_brick_v1.csv"
MANIFEST6 = HARNESS / "review6_raters" / "cells_manifest.json"
REG_CELLS = HARNESS / "real_run" / "cells.jsonl"
ORDER_SEED = 20260913


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def load_bank(path: Path = BANK_V1, comment_prefix: str | None = None) -> dict[str, dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        lines = [l for l in fh if not (comment_prefix and l.startswith(comment_prefix))]
    return {r["cq_id"]: r for r in csv.DictReader(lines)}


def spans_of(evidence) -> list[str]:
    if evidence is None:
        return []
    if isinstance(evidence, str):
        return [evidence] if evidence.strip() else []
    if isinstance(evidence, (list, tuple)):
        return [str(e) for e in evidence if str(e).strip()]
    return [str(evidence)]


def registered_evidence() -> dict[str, list[str]]:
    """cell_id -> quoted evidence strings of the registered judge (only cell_id and judge_response.evidence are read)."""
    out = {}
    for line in REG_CELLS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["cell_id"]] = spans_of((r.get("judge_response") or {}).get("evidence"))
    return out


def order(ids: list[str], first_variants: str = "") -> list[str]:
    """Seeded shuffle of the sorted ids (PLAN 32.3/32.9); with ``first_variants`` those variants come first (each group shuffled)."""
    ids = sorted(ids)
    if not first_variants:
        random.Random(ORDER_SEED).shuffle(ids)
        return ids
    a = [i for i in ids if i.split(":")[1] in first_variants]
    b = [i for i in ids if i.split(":")[1] not in first_variants]
    random.Random(ORDER_SEED).shuffle(a)
    random.Random(ORDER_SEED).shuffle(b)
    return a + b


def cache_path(cell_id: str) -> Path:
    return CACHE / (cell_id.replace(":", "__") + ".txt")


def material_for(row: dict) -> str:
    """The view text of a manifest row, from the cache (rebuilt if missing); sha256 checked."""
    p = cache_path(row["cell_id"])
    if not p.exists():
        raise SystemExit(f"{row['cell_id']}: view cache missing; run the manifest builder")
    t = p.read_text(encoding="utf-8")
    if sha256_text(t) != row["view_sha256"]:
        raise SystemExit(f"{row['cell_id']}: view sha256 mismatch")
    return t


def make_row(cell_id: str, kind: str, variant: str, brow: dict, catKo: str, qko: str, spans: list[str],
             crit: V.Crit | None, rendering_text: str | None = None) -> dict:
    d = V.build_view(variant, brow["grounding"], brow["question"], spans, rendering_text=rendering_text)
    text = d.pop("text")
    CACHE.mkdir(exist_ok=True)
    cache_path(cell_id).write_text(text, encoding="utf-8")
    row = {"cell_id": cell_id, "cell_kind": kind, "variant": variant, "cq_id": brow["cq_id"], "cluster_id": brow["cq_id"],
           "cat": brow["category"], "catKo": catKo, "q": brow["question"], "qko": qko, "view_kind": "retrieval",
           "view_sha256": sha256_text(text), "view_chars": len(text), "est_input_tokens": -(-len(text) // 3)}
    row.update(d)
    if crit is not None:
        ok, frac = V.holds_terms(text, crit)
        row.update(view_holds_terms=ok, view_best_fraction=round(frac, 4))
    return row


def stage1_rows() -> list[dict]:
    bank = load_bank()
    crits = {k: V.Crit(r) for k, r in bank.items()}
    m6 = json.loads(MANIFEST6.read_text(encoding="utf-8"))
    cmap = {c["cell_id"]: c for c in m6["cells"]}
    ev = registered_evidence()
    rows = []
    for cid in sorted(cmap):
        c = cmap[cid]
        b = bank[c["cq_id"]]
        r = make_row(cid, "primary", c["variant"], b, c["catKo"], c.get("qko", ""), ev.get(cid, []), crits[c["cq_id"]])
        # reference measures (ceiling and the addendum-30 subgraph view); measurement only
        full = V.rendering(c["variant"])
        r["full_holds_terms"] = V.holds_terms(full, crits[c["cq_id"]])[0]
        sub = (ACCESS / c["view_path"]).read_text(encoding="utf-8")
        r["subgraph_view_holds_terms"] = V.holds_terms(sub, crits[c["cq_id"]])[0]
        r["subgraph_view_kind"] = c["view_kind"]
        rows.append(r)
    cat_ko = {c["cat"]: c["catKo"] for c in m6["cells"]}
    qko = {c["cq_id"]: c.get("qko", "") for c in m6["cells"]}
    for line in REG_CELLS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rr = json.loads(line)
        if rr["cell_kind"] != "ablated_control":
            continue
        b = bank[rr["cq_id"]]
        abl = V_ablate(V.rendering(rr["variant"]), b)
        rows.append(make_row(rr["cell_id"], "ablated_control", rr["variant"], b, cat_ko[b["category"]], qko.get(rr["cq_id"], ""),
                             spans_of((rr.get("judge_response") or {}).get("evidence")), crits[rr["cq_id"]], rendering_text=abl))
    return sorted(rows, key=lambda r: r["cell_id"])


def preserved_rows() -> list[dict]:
    """Addendum 33: the 12 registered preserved controls, unablated full rendering, same builder and judge-span rule as the primary cells."""
    bank = load_bank()
    crits = {k: V.Crit(r) for k, r in bank.items()}
    m6 = json.loads(MANIFEST6.read_text(encoding="utf-8"))
    cat_ko = {c["cat"]: c["catKo"] for c in m6["cells"]}
    qko = {c["cq_id"]: c.get("qko", "") for c in m6["cells"]}
    rows = []
    for line in REG_CELLS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rr = json.loads(line)
        if rr["cell_kind"] != "preserved_control":
            continue
        b = bank[rr["cq_id"]]
        rows.append(make_row(rr["cell_id"], "preserved_control", rr["variant"], b, cat_ko[b["category"]], qko.get(rr["cq_id"], ""),
                             spans_of((rr.get("judge_response") or {}).get("evidence")), crits[rr["cq_id"]]))
    return sorted(rows, key=lambda r: r["cell_id"])


def V_ablate(rendering_text: str, brow: dict) -> str:
    return rh.ablate_rendered_view(rendering_text, {"grounding": brow["grounding"], "cq_id": brow["cq_id"]})


def load_manifest(stage: str) -> list[dict]:
    p = MANIFESTS / f"{stage}.json"
    if not p.exists():
        raise SystemExit(f"{p.name} missing: run the manifest builder first")
    return json.loads(p.read_text(encoding="utf-8"))["rows"]


def main(argv=None) -> int:
    a = argv or sys.argv[1:]
    if a[:1] == ["preserved"]:
        MANIFESTS.mkdir(exist_ok=True)
        rows = preserved_rows()
        summ = {"n_preserved_controls": len(rows), "view_holds_terms": sum(r["view_holds_terms"] for r in rows),
                "fallback_used": sum(r["fallback_used"] for r in rows), "cap_reached": sum(r["cap_reached"] for r in rows),
                "max_view_chars": max(r["view_chars"] for r in rows), "span_given": sum(1 for r in rows if r["span_given"]),
                "n_missing_qko": sum(1 for r in rows if not r["qko"])}
        (MANIFESTS / "preserved.json").write_text(json.dumps({"stage": "preserved", "summary": summ, "rows": rows},
                                                             ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(summ, indent=1))
        return 0
    if a[:1] != ["stage1"]:
        raise SystemExit("usage: s2_cells.py stage1 | preserved")
    MANIFESTS.mkdir(exist_ok=True)
    rows = stage1_rows()
    prim = [r for r in rows if r["cell_kind"] == "primary"]
    summ = {
        "n_primary": len(prim), "n_ablated_controls": len(rows) - len(prim),
        "view_holds_terms_primary": sum(r["view_holds_terms"] for r in prim),
        "full_holds_terms_primary": sum(r["full_holds_terms"] for r in prim),
        "subgraph_view_holds_terms_primary": sum(r["subgraph_view_holds_terms"] for r in prim),
        "fallback_used": sum(r["fallback_used"] for r in rows), "cap_reached": sum(r["cap_reached"] for r in rows),
        "max_view_chars": max(r["view_chars"] for r in rows), "span_given_primary": sum(1 for r in prim if r["span_given"]),
        "span_all_pieces_found_primary": sum(1 for r in prim if r["span_given"] and r["span_pieces_found"] == r["span_pieces_total"] > 0),
    }
    (MANIFESTS / "stage1.json").write_text(json.dumps({"stage": "stage1", "summary": summ, "rows": rows}, ensure_ascii=False, indent=1),
                                           encoding="utf-8")
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
