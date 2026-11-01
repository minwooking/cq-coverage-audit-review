#!/usr/bin/env python3
# AI-generated draft: a person must review and test it before use.  (Addendum 47, C2.)
"""Machine validation for every eqv2 draft row (addendum 47, 47.3).

V1 form: columns present, cq_id matches CQE\\d{3} (CQE\\d{3,4} since b2, whose ids reach CQE1008), known category, exactly one '?' in the
   question, <= 30 words; and (amendment 47.A1, V1f) a relations question names its own
   term at most once -- the doubled-name sentences that failed the CP-1 screen.
V2 the target term's local name or rdfs:label appears verbatim in the question.
V3 every grounding anchor exists in the snapshot -- read-only through run_holdout's
   _grounding_anchors (the rule code is never edited).  harness/run_holdout.py is
   imported only after an AST gate proves that importing it cannot touch any file
   (module-level code is constants and function defs only); if the gate fails or the
   import raises, the function's own source text is extracted with AST and executed
   alone.  The route taken is recorded in the report.
V4 the row's ASK query evaluates true on the snapshot.
V5 no answer leak: longest common substring(question, expected_answer) < 40 chars and
   token Jaccard <= 0.50.
V6 the de-duplication rules D1-D5 (dedup.check_row) pass.

Failed rows drop with a record.  Per batch exactly ONE automatic replacement wave, fed by
the frame tail: the caller (P3) supplies a replacement drafter callable that produces a
draft row for a candidate term via draft.py; in C2 the wave is exercised with an injected
drafter (the tests) or left empty.  If the tail is exhausted the batch continues short.

Only the snapshot, the row's own text and the reference banks' question/grounding columns
are read.  Endpoints/hosts never appear.  A runtime audit hook blocks forbidden paths.

Usage:
    python3 validate.py --rows draft_b1.jsonl --out validated_b1.jsonl \
        [--frame frame_summary.json] [--report validate_report_b1.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import common
import dedup as dedup_mod
from common import CATEGORIES, Snapshot, install_blind_hooks

HERE = common.TOOLS
HARNESS = common.ACCESS / "harness"
CQE_RE = re.compile(r"^CQE\d{3,4}$")  # b1: CQE001-CQE504; b2 runs CQE505-CQE1008


def run_holdout_anchor_fn() -> tuple[object, str]:
    """(_grounding_anchors, route) -- route is 'import' (AST gate passed) or
    'ast-extract' (the one function's source was executed alone)."""
    return common.load_run_holdout_anchors(HARNESS)


def anchors_in_snapshot(snap: Snapshot, anchors: list[str]) -> list[str]:
    terms = snap.terms()
    known_locals = snap.all_locals()
    missing = []
    for a in anchors:
        if ":" in a:
            if a not in terms:
                missing.append(a)
        elif a not in known_locals:
            missing.append(a)
    return missing


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))


def validate_row(snap: Snapshot, row: dict, anchor_fn, dedup_ctx: dict) -> list[str]:
    """Return failure reasons; empty list == all six checks pass."""
    fails: list[str] = []
    q = row.get("question") or ""
    term = row.get("term") or ""
    # V1
    for col in ("cq_id", "category", "question", "grounding", "expected_answer", "ask",
                "ask_expressible", "batch", "frame_rank", "draft_model", "prompt_sha256"):
        if col not in row:
            fails.append(f"V1 missing column {col}")
    if not CQE_RE.match(str(row.get("cq_id") or "")):
        fails.append("V1 cq_id pattern")
    if row.get("category") not in CATEGORIES:
        fails.append("V1 unknown category")
    if q.count("?") != 1:
        fails.append("V1 question-mark count")
    if common.word_count(q) > 30:
        fails.append("V1 word count > 30")
    # V1f (amendment 47.A1, form rule for relations only): the question must name the
    # target term ONCE. The C2 frame filled the {owner} placeholder with the property
    # term itself, which produced doubled-name questions (CP-1 form failures CQE288,
    # CQE292, CQE297; the same form appears unscreened); the rule fires only at >= 2
    # word-boundary occurrences of the row's own local name, so non-relations rows that
    # passed round 1 cannot newly fail on it.
    if row.get("category") == "relations" and term:
        occ = len(re.findall(r"(?<![\w])" + re.escape(common.local(term)) + r"(?![\w])", q, re.I))
        if occ > 1:
            fails.append("V1 relations term repeated in question")
    # V2
    if term:
        lname, lab = common.local(term), snap.label(term)
        if lname not in q and (not lab or lab not in q):
            fails.append("V2 term name/label absent from question")
    # V3 (run_holdout's tokenizer, read-only)
    anchors = anchor_fn(row.get("grounding") or "")
    missing = anchors_in_snapshot(snap, list(anchors))
    if missing:
        fails.append("V3 anchors missing from snapshot: " + ",".join(missing[:5]))
    # V4
    ask = row.get("ask") or ""
    try:
        m = re.match(r"^\s*ASK\s*\{(.*)\}\s*$", ask, re.S)
        body = m.group(1) if m else ask
        if not snap.ask(body):
            fails.append("V4 ASK not true on snapshot")
    except Exception as exc:  # noqa: BLE001 -- validation channel reports, never crashes
        fails.append(f"V4 ASK error {type(exc).__name__}")
    # V5
    exp = row.get("expected_answer") or ""
    if common.lcs_len(q, exp) >= 40:
        fails.append("V5 longest common substring >= 40")
    jac = _jaccard(common.token_set(q), common.token_set(exp))
    if jac > 0.50:
        fails.append(f"V5 token jaccard {jac:.2f} > 0.50")
    # V6
    dres = dedup_mod.check_row(snap, row, dedup_ctx)
    fails.extend(dres["rules_triggered"])
    return fails


def validate_batch(rows: list[dict], snap: Snapshot, frame: dict, batch: str,
                   drafter=None, frame_terms: dict[str, str] | None = None,
                   embed=None, tau: float | None = None,
                   extra_rows: list[dict] | None = None) -> dict:
    """Validate rows, drop failures with records, then run at most one replacement wave
    from the frame tail (each drop consumes candidates from its category's tail until one
    validates; drafter(term, category, rank, cq_id) -> draft row).  embed/tau are the
    test-injection seam for D5; in production they stay None and the local model is used
    (strict -- absence raises, see dedup.build_context)."""
    anchor_fn, route = run_holdout_anchor_fn()
    ctx = (dedup_mod.build_context(snap, extra_rows=extra_rows) if embed is None and tau is None
           else dedup_mod.build_context(snap, extra_rows=extra_rows, embed=embed, tau=tau))
    is_b2 = batch == "b2"
    idx = {it["cq_id"]: it for it in common.frame_items(frame, "b2" if is_b2 else "b1")}
    for row in rows:  # rows carry no term column; recover it from the shared frame mapping
        if not row.get("term"):
            row["term"] = (idx.get(row.get("cq_id")) or {}).get("term", "")
    term2cat = frame_terms or {}
    for cat in CATEGORIES:
        for t in frame["categories"][cat]["b1_terms"]:
            term2cat.setdefault(t, cat)
    tails = {c: list(frame["categories"][c]["frame_tail"]) for c in CATEGORIES}
    tail_ranks = {c: list(frame["categories"][c].get("frame_tail_frame_rank") or [])
                  for c in CATEGORIES}
    if is_b2:
        # b2's single replacement wave draws only from the tail left after b1's wave and
        # the b2 items themselves (an exhausted tail leaves the batch short).
        tails, tail_ranks = common.batch2_leftover_tails(frame)
        for it in idx.values():
            term2cat.setdefault(it["term"], it["category"])
    ptr = {c: 0 for c in CATEGORIES}
    kept, dropped = [], []
    pending: list[dict] = []
    for row in rows:
        fails = validate_row(snap, row, anchor_fn, ctx)
        if fails:
            entry = {"cq_id": row.get("cq_id"), "term": row.get("term"), "category": row.get("category"),
                     "reasons": fails, "replaced_by": None}
            dropped.append(entry)
            pending.append(entry)
        else:
            kept.append(row)
    # one automatic replacement wave: candidate terms and frame ranks come from the
    # frame tail (seed-fixed by frame.py); an exhausted tail leaves the batch short.
    if drafter is not None:
        for entry in pending:
            cat = entry.get("category") or term2cat.get(entry["term"], "")
            if cat not in CATEGORIES:
                continue
            while ptr[cat] < len(tails[cat]):
                term = tails[cat][ptr[cat]]
                rank = tail_ranks[cat][ptr[cat]] if ptr[cat] < len(tail_ranks[cat]) else 0
                ptr[cat] += 1
                cand = drafter(term, cat, rank, entry["cq_id"])
                cand["batch"] = batch
                cand["frame_rank"] = rank
                cand.setdefault("term", term)
                cand.setdefault("cq_id", entry["cq_id"])
                if not validate_row(snap, cand, anchor_fn, ctx):
                    entry["replaced_by"] = cand["cq_id"]
                    kept.append(cand)
                    break
    got = {c: sum(1 for r in kept if r.get("category") == c) for c in CATEGORIES}
    target = ({c: common.load_batch2_plan()["categories"][c]["allocation_b2"] for c in CATEGORIES}
              if is_b2 else {c: frame["categories"][c]["allocation_b1"] for c in CATEGORIES})
    short = {c: target[c] - got[c] for c in CATEGORIES if got[c] < target[c]}
    kept.sort(key=lambda r: common.cq_sort_key(r.get("cq_id")))
    return {"anchor_route": route, "kept": kept, "dropped": dropped, "still_short_by": short}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rows", required=True, help="draft rows jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--frame", default=str(common.FRAME_SUMMARY))
    ap.add_argument("--report", default=None)
    ap.add_argument("--batch", default="b1", choices=["b1", "b2"])
    ap.add_argument("--extra", default=None,
                    help="jsonl of earlier eqv2 rows for D1-D5 (b1 as jsonl, see plan_b2.py --b1-extra)")
    ap.add_argument("--no-hook", action="store_true")
    args = ap.parse_args(argv)
    if not args.no_hook:
        install_blind_hooks(f"blind_open_log_{args.batch}.jsonl")
    snap = Snapshot()
    frame = json.loads(Path(args.frame).read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in Path(args.rows).read_text(encoding="utf-8").splitlines() if line.strip()]
    extra = ([json.loads(line) for line in Path(args.extra).read_text(encoding="utf-8").splitlines() if line.strip()]
             if args.extra else None)
    if args.batch == "b2" and not extra:
        raise SystemExit("b2 validation needs --extra (the frozen b1 bank as jsonl): D1-D5 run against b1 too")
    res = validate_batch(rows, snap, frame, args.batch, extra_rows=extra)
    Path(args.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in res["kept"]),
                              encoding="utf-8")
    report = {"anchor_route": res["anchor_route"], "n_in": len(rows), "n_kept": len(res["kept"]),
              "n_dropped": len(res["dropped"]), "dropped_records": res["dropped"],
              "still_short_by": res["still_short_by"]}
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "dropped_records"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
