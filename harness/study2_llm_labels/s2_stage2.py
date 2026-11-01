#!/usr/bin/env python3
"""Stage 2 plumbing of addendum 32 (PLAN.md 32.7-32.9).  AI-generated; review and test before use.

  s2_stage2.py eligibility   -> manifests/eligibility.json   (after the bank freeze; the paper's strict eligibility rule per cell)
  s2_stage2.py judge-jobs    -> jobs_stage2.jsonl            (eligible cells; judge view = question-only subgraph of addendum 30's exp set)
  s2_stage2.py judge-run --judge glm|gptoss --endpoint URL [--workers N]   (addendum 26's scorer, imported; 3 repeats)
  s2_stage2.py manifest      -> manifests/stage2.json + views_cache/  (labeler views with the judges' located evidence; G3 controls)

No label is read.  The expected_answer of the bank is used only to measure the view's term coverage.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HARNESS))
import s2_cells as C  # noqa: E402
import s2_views as V  # noqa: E402
import run_holdout as rh  # noqa: E402

FROZEN = HERE / "bank_frozen_v1.csv"
FROZEN_SHA_FILE = HERE / "bank_freeze.json"
EXP_MANIFEST = HARNESS / "review10_llm_labels" / "manifests" / "exp.json"
EXP_MANIFEST_SHA = "e4b18886511b36b4841dbc599b7032793b047f59857a12ad5cdac37751a2b7bd"
M6 = HARNESS / "review6_raters" / "cells_manifest.json"
JOBS = HERE / "jobs_stage2.jsonl"
VARIANTS = "ABCDEF"
N_CONTROLS = 24


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def frozen_bank() -> dict[str, dict]:
    info = json.loads(FROZEN_SHA_FILE.read_text(encoding="utf-8"))
    assert hashlib.sha256(FROZEN.read_bytes()).hexdigest() == info["frozen_sha256"], "frozen bank digest mismatch"
    return C.load_bank(FROZEN)


def eligibility() -> dict:
    bank = frozen_bank()
    cells = {}
    for v in VARIANTS:
        text = V.rendering(v)
        for cq, row in bank.items():
            info = rh._grounding_match_info(text, {"grounding": row["grounding"]})
            cells[f"primary:{v}:{cq}"] = {"variant": v, "cq_id": cq, "eligible": bool(info["can_ablate"]),
                                          "n_matching_lines": len(info["matching_line_numbers"]),
                                          "missing_required": info["missing_required_grounding_anchors"]}
    elig_cells = [c for c, x in cells.items() if x["eligible"]]
    by_cq: dict[str, list[str]] = {}
    for c in elig_cells:
        by_cq.setdefault(cells[c]["cq_id"], []).append(cells[c]["variant"])
    out = {"bank_sha256": json.loads(FROZEN_SHA_FILE.read_text())["frozen_sha256"], "n_questions": len(bank),
           "n_cells_total": len(cells), "n_eligible_cells": len(elig_cells),
           "eligible_cells_by_variant": {v: sum(1 for c in elig_cells if cells[c]["variant"] == v) for v in VARIANTS},
           "n_eligible_clusters": len(by_cq),
           "n_clusters_eligible_in_A_and_B": sum(1 for vs in by_cq.values() if "A" in vs and "B" in vs),
           "target_clusters": 60, "target_met": len(by_cq) >= 60,
           "ineligible_clusters": sorted(set(bank) - set(by_cq)), "cells": cells}
    (HERE / "manifests").mkdir(exist_ok=True)
    (HERE / "manifests" / "eligibility.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    return {k: v for k, v in out.items() if k != "cells"}


def load_elig() -> dict:
    return json.loads((HERE / "manifests" / "eligibility.json").read_text(encoding="utf-8"))


def judge_jobs() -> int:
    assert hashlib.sha256(EXP_MANIFEST.read_bytes()).hexdigest() == EXP_MANIFEST_SHA
    bank = frozen_bank()
    elig = load_elig()["cells"]
    exp = {r["cell_id"]: r for r in json.loads(EXP_MANIFEST.read_text(encoding="utf-8"))["rows"]}
    m6 = json.loads(M6.read_text(encoding="utf-8"))
    n = 0
    with JOBS.open("w", encoding="utf-8") as fh:
        for cid in sorted(c for c, x in elig.items() if x["eligible"]):
            v, cq = elig[cid]["variant"], elig[cid]["cq_id"]
            e = exp[f"exp:{v}:{cq}"]
            assert e["q"] == bank[cq]["question"], f"{cq}: question text differs from the frozen bank"
            p = ACCESS / e["view_path"]
            view = p.read_text(encoding="utf-8")
            assert sha256_text(view) == e["view_sha256"], f"{cid}: view sha256 mismatch"
            system = rh.RUBRIC
            user = f"ARTIFACT:\n{view}\n\nQUESTION: {bank[cq]['question']}"
            job = {"job_id": f"s2|{cid}", "study": "stage2", "cell_id": cid, "cell_kind": "primary", "variant": v, "cq_id": cq,
                   "cluster_id": cq, "category": bank[cq]["category"], "view_kind": "subgraph", "view_chars": len(view),
                   "artifact_sha256": e["view_sha256"], "system": system, "user": user,
                   "prompt_sha256": sha256_text(system + "\n\x00\n" + user)}
            fh.write(json.dumps(job, ensure_ascii=False) + "\n")
            n += 1
    print(json.dumps({"jobs": n, "jobs_sha256": hashlib.sha256(JOBS.read_bytes()).hexdigest()}))
    return 0


def judge_run(argv: list[str]) -> int:
    spec = importlib.util.spec_from_file_location("sj", HARNESS / "review6_judges" / "score_judges.py")
    sj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sj)
    sj.MAX_WORKERS = 32                      # addendum 26 capped at 3; this study uses the concurrency of PLAN 32.5 (>= 16)
    judge = argv[argv.index("--judge") + 1]
    out = HERE / "raw" / f"judge_{judge}_stage2.jsonl"
    args = ["--jobs", str(JOBS), "--judge", judge, "--out", str(out), "--repeats", "3", "--confirm-addendum26-frozen"] + argv
    if "--workers" not in argv:
        args += ["--workers", "16"]
    return sj.main(args)


def judge_median(records_by_judge: dict[str, list[dict]]) -> dict[str, dict]:
    """cell_id -> {judge: {"J": median of the valid repeats (lower median), "evidence": [distinct strings], "n_valid": k}}."""
    out: dict[str, dict] = {}
    for judge, recs in records_by_judge.items():
        by: dict[str, list[dict]] = {}
        for r in recs:
            if r.get("valid") and r.get("J") is not None:
                by.setdefault(r["cell_id"], []).append(r)
        for cid, rs in by.items():
            js = sorted(int(r["J"]) for r in rs)
            ev = []
            for r in sorted(rs, key=lambda r: r["repeat"]):
                for s in C.spans_of(r.get("evidence")):
                    if s not in ev:
                        ev.append(s)
            jmed = js[(len(js) - 1) // 2]
            at_med = next((C.spans_of(r.get("evidence")) for r in sorted(rs, key=lambda r: r["repeat"]) if int(r["J"]) == jmed), [])
            out.setdefault(cid, {})[judge] = {"J": jmed, "evidence": ev, "evidence_at_median": at_med, "n_valid": len(js)}
    return out


def build_manifest() -> dict:
    bank = frozen_bank()
    crits = {k: V.Crit(r) for k, r in bank.items()}
    el = load_elig()
    cells = el["cells"]
    recs = {}
    for judge in ("glm", "gptoss"):
        p = HERE / "raw" / f"judge_{judge}_stage2.jsonl"
        recs[judge] = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []
    jm = judge_median(recs)
    m6 = json.loads(M6.read_text(encoding="utf-8"))
    cat_ko = {c["cat"]: c["catKo"] for c in m6["cells"]}
    rows = []
    for cid in sorted(c for c, x in cells.items() if x["eligible"]):
        v, cq = cells[cid]["variant"], cells[cid]["cq_id"]
        spans = []
        for judge in ("glm", "gptoss"):
            spans += jm.get(cid, {}).get(judge, {}).get("evidence", [])
        r = C.make_row(cid, "primary", v, bank[cq], cat_ko[bank[cq]["category"]], "", spans, crits[cq])
        for judge in ("glm", "gptoss"):
            r[f"J_{judge}"] = jm.get(cid, {}).get(judge, {}).get("J")
            r[f"J_{judge}_n_valid"] = jm.get(cid, {}).get(judge, {}).get("n_valid", 0)
        r["full_holds_terms"] = V.holds_terms(V.rendering(v), crits[cq])[0]
        rows.append(r)
    # G3 controls: Random(20260913) over the sorted eligible cell ids, at most one per cluster, until 24
    ids = sorted(r["cell_id"] for r in rows)
    random.Random(C.ORDER_SEED).shuffle(ids)
    used, picked = set(), []
    for cid in ids:
        cq = cells[cid]["cq_id"]
        if cq in used:
            continue
        used.add(cq)
        picked.append(cid)
        if len(picked) == N_CONTROLS:
            break
    for cid in picked:
        v, cq = cells[cid]["variant"], cells[cid]["cq_id"]
        abl = C.V_ablate(V.rendering(v), bank[cq])
        rows.append(C.make_row("ablated_control" + cid[len("primary"):], "ablated_control", v, bank[cq], cat_ko[bank[cq]["category"]], "", [],
                               crits[cq], rendering_text=abl))
    summ = {"n_primary": sum(1 for r in rows if r["cell_kind"] == "primary"), "n_controls": len(picked),
            "view_holds_terms": sum(bool(r["view_holds_terms"]) for r in rows if r["cell_kind"] == "primary"),
            "full_holds_terms": sum(bool(r["full_holds_terms"]) for r in rows if r["cell_kind"] == "primary"),
            "max_view_chars": max(r["view_chars"] for r in rows),
            "span_given_cells": sum(1 for r in rows if r["cell_kind"] == "primary" and r["span_given"]),
            "span_all_pieces_found": sum(1 for r in rows if r["cell_kind"] == "primary" and r["span_given"] and r["span_pieces_found"] == r["span_pieces_total"] > 0),
            "judge_valid_cells": {j: sum(1 for c in jm.values() if j in c) for j in ("glm", "gptoss")}}
    (HERE / "manifests" / "stage2.json").write_text(json.dumps({"stage": "stage2", "summary": summ, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summ, indent=1))
    return summ


def main(argv=None) -> int:
    a = argv or sys.argv[1:]
    cmd = a[0] if a else ""
    if cmd == "eligibility":
        print(json.dumps(eligibility(), indent=1))
        return 0
    if cmd == "judge-jobs":
        return judge_jobs()
    if cmd == "judge-run":
        return judge_run(a[1:])
    if cmd == "manifest":
        build_manifest()
        return 0
    raise SystemExit("usage: s2_stage2.py eligibility|judge-jobs|judge-run|manifest")


if __name__ == "__main__":
    sys.exit(main())
