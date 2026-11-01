#!/usr/bin/env python3
# AI-generated draft: a person must review and test it before use.  (Addendum 47, C2.)
"""De-duplication rules D1-D5 for bank eqv2 (addendum 47, 47.3).

Reference sets: the five reference banks (question + grounding columns only), earlier
eqv2 rows of the same batch, and for b2 the whole of b1 (supplied by the caller as
extra_rows).  Rules:

  D1  normalized question identical
  D2  normalized grounding identical
  D3  primary grounding term (with aliases) equals a reference anchor -- already caught
      at frame time, re-checked here
  D4  question token Jaccard >= 0.80 (the expansion builder's precedent threshold)
  D5  embedding cosine (local all-MiniLM-L6-v2, CPU, normalized vectors):
      exclude when cosine >= tau_emb AND anchor-set Jaccard >= 0.5;
      cosine >= 0.95 with a different anchor set is KEPT and flagged log_only, so the
      same-frame question shapes do not get over-excluded.
      tau_emb = min(0.90, P10 of the 36 holdout<->paraphrase cosine pairs), computed
      offline in C2 and recorded in frame_summary.json (+ tau_emb.json).

The embedding model is LOCAL-ONLY (offline, local_files_only): nothing is downloaded; if
the cache is absent the tool stops and reports.  CPU only, no GPU, no network, no
endpoint, no host, no port.  The audit hook blocks forbidden paths.

Usage:
    python3 dedup.py --tau-out tau_emb.json [--merge-frame]     # calibrate tau (CPU)
    python3 dedup.py --rows draft_b1.jsonl --log dedup_log_b1.csv
    python3 dedup.py --batch b2 --rows draft_b2.jsonl --extra <b1 bank as jsonl> --log dedup_log_b2.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import common
from common import ACCESS, CATEGORIES, REFERENCE_BANKS, Snapshot, install_blind_hooks

HERE = common.TOOLS
D4_JACCARD_THRESHOLD = 0.80
D5_ANCHOR_JACCARD_THRESHOLD = 0.50
D5_LOG_ONLY_COSINE = 0.95
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_EMBED_SINGLETON: object | None = None
_REF_VECS: list = []


class EmbedMissingError(RuntimeError):
    pass


def local_embed_fn():
    """all-MiniLM-L6-v2 on CPU, strictly offline (no downloads)."""
    global _EMBED_SINGLETON
    if _EMBED_SINGLETON is not None:
        return _EMBED_SINGLETON
    try:
        import os
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415 -- deliberate heavy import
        model = SentenceTransformer(MODEL_NAME, device="cpu", local_files_only=True)
    except Exception as exc:  # noqa: BLE001 -- cache absence must stop and report
        raise EmbedMissingError(
            f"local {MODEL_NAME} unavailable offline ({type(exc).__name__}): "
            "stop and report; do not download") from exc

    def embed(texts: list[str]):
        import numpy as np
        return model.encode(list(texts), normalize_embeddings=True,
                            convert_to_numpy=True, show_progress_bar=False)

    _EMBED_SINGLETON = embed
    return embed


def build_alias_map(snap: Snapshot) -> dict[str, set[str]]:
    alias: dict[str, set[str]] = {}
    for a, b_ in snap.equivalents():
        aq, bq = common.q(a), common.q(b_)
        if aq and bq:
            alias.setdefault(aq, set()).add(bq)
            alias.setdefault(bq, set()).add(aq)
    see = common.re.compile(r"""See\s+'?\s*((?:brick|rec|ref):)?([A-Za-z][A-Za-z0-9_]*)""")
    locals2terms: dict[str, set[str]] = {}
    for t in snap.terms():
        locals2terms.setdefault(common.local(t), set()).add(t)
    for s, o in (list(snap.g.subject_objects(common.SKOS.definition))
                 + list(snap.g.subject_objects(common.RDFS.comment))):
        t = common.q(s)
        if not t:
            continue
        for m in see.finditer(str(o)):
            if m.group(1):
                alias.setdefault(t, set()).add(f"{m.group(1)}:{m.group(2)}")
            else:
                alias.setdefault(t, set()).update(locals2terms.get(m.group(2).strip().rstrip("."), set()))
    return alias


def _token_to_terms(snap: Snapshot, token: str, locals2terms: dict[str, set[str]] | None = None) -> set[str]:
    if ":" in token:
        p = token.split(":", 1)[0]
        return {token} if p in common.NSMAP else set()
    if locals2terms is not None:
        return set(locals2terms.get(token, set()))
    return {t for t in snap.terms() if common.local(t) == token}


def anchor_terms_of_grounding(snap: Snapshot, grounding: str, alias: dict[str, set[str]],
                              locals2terms: dict[str, set[str]] | None = None) -> set[str]:
    """Every snapshot term the grounding cell points at: each tokenizer anchor resolved
    to terms by exact qname or local name, then closed under owl:equivalentClass /
    'See X' aliases.  (The local-name index can be supplied by callers who build it once;
    building it per call would make D5 quadratic.)"""
    if locals2terms is None:
        locals2terms = _locals_index(snap)
    out: set[str] = set()
    for token in common.grounding_anchors_from_text(grounding or ""):
        out |= _token_to_terms(snap, token, locals2terms)
    closed: set[str] = set()
    for t in out:
        closed.add(t)
        closed |= alias.get(t, set())
    return closed


_LOCALS_INDEX_CACHE: "dict[tuple, dict[str, set[str]]]" = {}


def _locals_index(snap: Snapshot) -> dict[str, set[str]]:
    key = (id(snap), snap.sha256)
    idx = _LOCALS_INDEX_CACHE.get(key)
    if idx is None:
        idx = {}
        for t in snap.terms():
            idx.setdefault(common.local(t), set()).add(t)
        _LOCALS_INDEX_CACHE.clear()
        _LOCALS_INDEX_CACHE[key] = idx
    return idx


def primary_terms(snap: Snapshot, grounding: str, alias: dict[str, set[str]],
                  locals2terms: dict[str, set[str]] | None = None) -> set[str]:
    """The primary (first listed) grounding term(s), with aliases."""
    if locals2terms is None:
        locals2terms = _locals_index(snap)
    for token in common.grounding_anchors_from_text(grounding or ""):
        hits = _token_to_terms(snap, token, locals2terms)
        if hits:
            return hits | set().union(*(alias.get(t, set()) for t in hits))
    return set()


def load_tau(frame_path: Path | None = None) -> float:
    fp = Path(frame_path) if frame_path else common.FRAME_SUMMARY
    try:
        v = json.loads(fp.read_text(encoding="utf-8")).get("tau_emb")
        if isinstance(v, (int, float)):
            return float(v)
    except (OSError, json.JSONDecodeError):
        pass
    try:
        v = json.loads((HERE.parent / "tau_emb.json").read_text(encoding="utf-8")).get("tau_emb")
        if isinstance(v, (int, float)):
            return float(v)
    except (OSError, json.JSONDecodeError):
        pass
    return 0.90  # conservative default: min(0.90, ...) is the rule's own ceiling


def build_context(snap: Snapshot, extra_rows: list[dict] | None = None,
                  embed=None, tau: float | None = None) -> dict:
    """Reference corpus (five banks + extra rows) with per-row terms, alias map, tau.
    The embedding corpus is appended lazily so reference vectors can persist (D5 is
    quadratic otherwise).  If no embed is injected and the local model is unavailable,
    EmbedMissingError propagates -- D5 without embeddings is not a silent downgrade
    (addendum 47, 47.3: local-only model, cache absence stops and reports)."""
    if embed is None:
        embed = local_embed_fn()
    alias = build_alias_map(snap)
    refs: list[dict] = []
    for p in REFERENCE_BANKS:
        with p.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if not (row.get("question") or "").strip():
                    continue
                refs.append({"ref_id": row.get("cq_id") or p.name,
                             "question": row["question"], "grounding": row.get("grounding", "")})
    for row in extra_rows or []:
        if not (row.get("question") or "").strip():
            continue
        refs.append({"ref_id": row.get("cq_id") or "eqv2-earlier",
                     "question": row["question"], "grounding": row.get("grounding", "")})
    for r in refs:
        r["terms"] = anchor_terms_of_grounding(snap, r["grounding"], alias)
    return {"snap": snap, "alias": alias, "refs": refs, "embed": embed,
            "tau": float(tau if tau is not None else load_tau()), "_corpus": [], "_vec": []}


def check_row(snap: Snapshot, row: dict, ctx: dict, embeddable: bool = True) -> dict:
    """Run D1-D5 for one row. Returns triggered rules, the nearest reference id and the
    metrics used. log_only marks a D5-adjacent near-cosine hit that does NOT exclude."""
    q_norm = common.norm_text(row.get("question") or "")
    g_norm = common.norm_text(row.get("grounding") or "")
    q_tok = common.token_set(row.get("question") or "")
    prim = primary_terms(snap, row.get("grounding") or "", ctx["alias"])
    row_terms = anchor_terms_of_grounding(snap, row.get("grounding") or "", ctx["alias"])
    embed = ctx["embed"] if embeddable else None
    my_vec = None
    if embed is not None:
        try:
            my_vec = embed([row.get("question") or ""])[0]
            if not ctx["_vec"]:
                ctx["_vec"] = list(embed([r["question"] for r in ctx["refs"]]))
        except Exception as exc:  # noqa: BLE001 -- embedding failure is fatal, not a downgrade
            raise EmbedMissingError(f"D5 embedding failed ({type(exc).__name__}: {exc}): "
                                    "stop and report; D5 without embeddings is not a valid run "
                                    "(addendum 47, 47.3)") from exc
    triggered: list[str] = []
    log_only = False
    best = {"ref_id": "", "jaccard": 0.0, "cosine": 0.0, "anchor_jaccard": 0.0}
    # Text rules first, collected across ALL references (the log row may name several
    # rules; reporting only the first-matching rule would understate why a row drops).
    for r in ctx["refs"]:
        if q_norm and common.norm_text(r["question"]) == q_norm:
            triggered.append("D1")
        if g_norm and common.norm_text(r["grounding"]) == g_norm:
            triggered.append("D2")
        if prim and (prim & r["terms"]):
            triggered.append("D3")
    for r in ctx["refs"]:
        j = _jac(common.token_set(r["question"]), q_tok)
        if j >= D4_JACCARD_THRESHOLD:
            triggered.append("D4")
            break  # D4 excludes identically wherever it hits
    # Vector pass (D5, and the log_only companion).
    for r, rv in zip(ctx["refs"], (ctx["_vec"] if ctx["_vec"] else [None] * len(ctx["refs"]))):
        j = _jac(common.token_set(r["question"]), q_tok)
        aj = _jac(r["terms"], row_terms)
        c = float(my_vec @ rv) if (my_vec is not None and rv is not None) else 0.0
        if j > best["jaccard"]:
            best.update({"ref_id": r["ref_id"], "jaccard": round(j, 3)})
        if c > best["cosine"]:
            best.update({"ref_id": r["ref_id"], "cosine": round(c, 3), "anchor_jaccard": round(aj, 3)})
        if my_vec is not None and rv is not None and c >= ctx["tau"] and aj >= D5_ANCHOR_JACCARD_THRESHOLD:
            triggered.append("D5")
            best["ref_id"] = best["ref_id"] or r["ref_id"]
        elif my_vec is not None and rv is not None and c >= D5_LOG_ONLY_COSINE:
            log_only = True
    triggered = sorted(set(triggered))
    return {"rules_triggered": triggered, "nearest_ref_id": best["ref_id"],
            "jaccard": best["jaccard"], "cosine": best["cosine"],
            "anchor_jaccard": best["anchor_jaccard"], "log_only": log_only,
            "tau_emb": ctx["tau"]}


def _jac(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


# ---------------------------------------------------------------- tau_emb calibration (C2/P2)
def compute_tau(embed) -> dict:
    """P10 of the 36 cosine similarities of bank-v1 questions against their frozen
    paraphrases (same cq_id pair); tau_emb = min(0.90, P10).  Cosines are between
    normalized vectors of (question, paraphrase_text) of the same cq_id -- sorted id
    order, 36 pairs; the percentiles use numpy's default linear interpolation.  min,
    P10 and median are all recorded as the computation basis."""
    v1 = {}
    with (ACCESS / "bank" / "cq_bank_brick_v1.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("question"):
                v1[row["cq_id"]] = row["question"]
    par = {}
    with (ACCESS / "bank" / "cq_bank_brick_v1_paraphrases.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("paraphrase_text"):
                par[row["cq_id"]] = row["paraphrase_text"]
    keys = [k for k in sorted(v1) if k in par]
    if len(keys) != 36:
        raise ValueError(f"expected 36 holdout/paraphrase pairs, found {len(keys)}")
    import numpy as np
    a = embed([v1[k] for k in keys])
    b = embed([par[k] for k in keys])
    sims = np.sum(np.asarray(a) * np.asarray(b), axis=1)
    p10 = float(np.percentile(sims, 10))
    return {"model": "all-MiniLM-L6-v2 (local, CPU)", "pairs": len(keys),
            "pairs_definition": "cq_bank_brick_v1.csv question <-> "
                                "cq_bank_brick_v1_paraphrases.csv paraphrase_text, "
                                "paired by cq_id (sorted, 36 pairs)",
            "percentile_method": "numpy default (linear) interpolation",
            "cosines": [round(float(s), 4) for s in sims],
            "min": round(float(sims.min()), 4), "p10": round(p10, 4),
            "median": round(float(np.median(sims)), 4),
            "tau_emb": round(min(0.90, p10), 4)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tau-out", default=None, help="calibrate tau_emb and write this json")
    ap.add_argument("--merge-frame", action="store_true", help="also record tau_emb in frame_summary.json")
    ap.add_argument("--rows", default=None, help="run D1-D5 over this jsonl, write a log")
    ap.add_argument("--log", default=None)
    ap.add_argument("--frame", default=str(common.FRAME_SUMMARY))
    ap.add_argument("--extra", default=None, help="earlier eqv2 rows jsonl (b1 for a b2 run)")
    ap.add_argument("--batch", default="b1")
    ap.add_argument("--no-hook", action="store_true")
    args = ap.parse_args(argv)
    if not args.no_hook:
        install_blind_hooks(f"blind_open_log_{args.batch}.jsonl")
    snap = Snapshot()
    tau_written = False

    if args.tau_out:
        t = compute_tau(local_embed_fn())  # local-only; absence raises -> stop and report
        Path(args.tau_out).write_text(json.dumps(t, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"tau_emb={t['tau_emb']} (p10={t['p10']}, pairs={t['pairs']}) -> {args.tau_out}")
        if args.merge_frame:
            fp = Path(args.frame)
            f = json.loads(fp.read_text(encoding="utf-8"))
            f["tau_emb"] = t["tau_emb"]
            f["tau_emb_basis"] = {"model": t["model"], "pairs": t["pairs"], "p10": t["p10"]}
            fp.write_text(json.dumps(f, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
            print(f"merged tau_emb into {fp}")
        tau_written = True

    if args.rows:
        rows = [json.loads(line) for line in Path(args.rows).read_text(encoding="utf-8").splitlines() if line.strip()]
        extra = [json.loads(line) for line in Path(args.extra).read_text(encoding="utf-8").splitlines()
                 if line.strip()] if args.extra else None
        if args.batch == "b2" and not extra:
            raise SystemExit("b2 de-duplication needs --extra: the frozen b1 bank as jsonl "
                             "(python3 plan_b2.py --b1-extra <b1 bank csv> --out <jsonl>)")
        ctx = build_context(snap, extra_rows=extra)
        log_path = Path(args.log or str(common.BANK / f"dedup_log_{args.batch}.csv"))
        with log_path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["cq_id", "ref_id", "jaccard", "cosine", "anchor_jaccard", "rule", "decision"])
            excluded = 0
            for row in rows:
                res = check_row(snap, row, ctx)
                decision = "exclude" if res["rules_triggered"] else ("log_only" if res["log_only"] else "keep")
                excluded += decision == "exclude"
                w.writerow([row.get("cq_id"), res["nearest_ref_id"], res["jaccard"], res["cosine"],
                            res["anchor_jaccard"], "|".join(res["rules_triggered"]) or "-", decision])
        print(f"dedup: {len(rows)} rows, {excluded} excluded -> {log_path}")
        return 0

    if not tau_written:
        print("nothing to do (give --tau-out or --rows)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
