#!/usr/bin/env python3
# AI-generated draft: a person must review and test it before use.  (Addendum 47, C2.)
"""Build the eqv2 sampling frame from the frozen Brick snapshot (addendum 47, 47.3).

Reads ONLY data/brick-v1.4.4.ttl and the five reference banks' grounding text (for the
exclusion set).  Never opens renderings, graphs, raw judge records, eligibility or
annotation outputs; a runtime audit hook refuses any forbidden path (common.py).

Categories (six) and per-category eligibility, re-implementing the expansion builder's
grounding grammar without importing that builder (its module-level code runs on import):
  concept_definition  term has a definition sentence (skos:definition / rdfs:comment)
  taxonomy            term has a parent or a child (rdfs:subClassOf)
  relations           term is a sh:path of a class-targeted property shape
  slots_facets        term is a brick:EntityProperty with a definition
  instances           term's definition enumerates examples ("such as", "for example", ...)
  methodology         term has a full deprecation record (version + replacement + message)

Exclusions: every term used as a grounding anchor by the five reference banks (local-name
mapping, so an alias term with the same local name in either namespace goes too), plus
their aliases via owl:equivalentClass and "See X" definitions.

Sampling: per category, qnames sorted then shuffled with random.Random(20260913); b1
takes the first 84 per category (504 total); short categories give their whole frame and
the deficit is redistributed round-robin to the largest frames.  Later items stay in the
frame tail for auto-replacement and (if needed) b2.  Frame rank (one of three prompt
frames per category) is drawn with the same seed, single stream, in frame order.

Output: frame_summary.json next to the bank (per-category frame sizes and exclusions,
b1 allocation, seed, snapshot sha, prompt-template sha256; tau_emb is filled later by
dedup.py and merged).

Usage:  python3 frame.py [--emit-stdout]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import common
from common import (ACCESS, B1_QUOTA_PER_CATEGORY, CATEGORIES, FRAME_SUMMARY, SEED,
                    SNAPSHOT_SHA256, Snapshot, install_blind_hooks, local, now_iso,
                    prompt_sha256)

HERE = common.TOOLS


def reference_anchor_terms(snap: Snapshot) -> tuple[set[str], set[str]]:
    """(anchored_terms, alias_terms). Anchored: snapshot terms whose local name is a
    grounding anchor of the five reference banks. Alias: terms linked to an anchored
    term by owl:equivalentClass (both directions) or by a 'See X' definition where the
    other side is anchored."""
    locals2terms: dict[str, set[str]] = {}
    for t in snap.terms():
        locals2terms.setdefault(local(t), set()).add(t)
    anchored: set[str] = set()
    for l in common.reference_anchor_locals():
        anchored |= locals2terms.get(l, set())
    alias: set[str] = set()
    for a, b_ in snap.equivalents():
        aq, bq = common.q(a), common.q(b_)
        if aq and bq:
            if aq in anchored:
                alias.add(bq)
            if bq in anchored:
                alias.add(aq)
    see = common.re.compile(r"""See\s+'?\s*((?:brick|rec|ref):)?([A-Za-z][A-Za-z0-9_]*)""")
    defs_ = list(snap.g.subject_objects(common.SKOS.definition)) + list(snap.g.subject_objects(common.RDFS.comment))
    for s, o in defs_:
        t = common.q(s)
        if not t:
            continue
        for m in see.finditer(str(o)):
            tgt_local = m.group(2).strip().rstrip(".")
            if m.group(1):
                tgt_terms = {f"{m.group(1)}:{tgt_local}"}
            else:
                tgt_terms = set(locals2terms.get(tgt_local, set()))
            hit = any(x in anchored for x in tgt_terms if x)
            if hit:
                alias.add(t)
            if t in anchored:
                alias |= {x for x in tgt_terms if x}
    return anchored, alias


def category_frames(snap: Snapshot) -> dict[str, set[str]]:
    terms = snap.terms()
    def_ok = {t for t in terms if snap.has_def(t)}
    kids = {t for t in terms if snap.children(t)}
    pars = {t for t in terms if snap.parents(t)}
    relations = set(snap.prop_shapes())
    slots = {t for t in snap.entity_props() if snap.has_def(t)}
    instances = {t for t in def_ok if common.ENUM_CUE.search(snap.def_text(t) or "")}
    methodology = {t for t in terms if snap.deprecation(t) is not None}
    return {
        "concept_definition": def_ok,
        "taxonomy": kids | pars,
        "relations": relations & terms,
        "slots_facets": slots,
        "instances": instances,
        "methodology": methodology,
    }


def allocate(frames_post: dict[str, list[str]], quota: int = B1_QUOTA_PER_CATEGORY):
    """b1 takes `quota` per category; short frames give all; deficit goes round-robin to
    the largest remaining frames (frame size desc). Returns allocation counts + tails used."""
    alloc = {c: min(quota, len(frames_post[c])) for c in frames_post}
    deficit = sum(quota - v for v in alloc.values())
    order = sorted(frames_post, key=lambda c: (-len(frames_post[c]), c))
    used_extra: dict[str, int] = {c: 0 for c in alloc}
    while deficit > 0:
        progressed = False
        for c in order:
            if deficit <= 0:
                break
            if alloc[c] < len(frames_post[c]):
                alloc[c] += 1
                used_extra[c] += 1
                deficit -= 1
                progressed = True
        if not progressed:
            break
    return alloc, deficit


def frame_plan(snap: Snapshot) -> dict:
    anchored, alias = reference_anchor_terms(snap)
    excluded = anchored | alias
    frames_raw = category_frames(snap)
    per_cat = {}
    rng_rank = random.Random(SEED)
    summary_frames: dict[str, dict] = {}
    frame_sizes = {c: sorted(set(frames_raw[c]) - excluded) for c in CATEGORIES}
    for c in CATEGORIES:
        items = frame_sizes[c]
        rng = random.Random(SEED)
        shuffled = list(items)
        rng.shuffle(shuffled)
        per_cat[c] = shuffled
    alloc, leftover_deficit = allocate({c: per_cat[c] for c in CATEGORIES})
    for c in CATEGORIES:
        selected = []
        ranks = []
        for i, term in enumerate(per_cat[c]):
            if i < alloc[c]:
                rank = rng_rank.randrange(3)
                selected.append(term)
                ranks.append(rank)
        # Frame-tail ranks: a separate seed-20260913 stream per category (the b1 rank
        # stream must not shift). Used only by the replacement wave (validate.py).
        rng_tail = random.Random(SEED)
        tail_ranks = [rng_tail.randrange(3) for _ in per_cat[c][alloc[c]:]]
        summary_frames[c] = {
            "frame_size_pre_exclusion": len(set(frames_raw[c])),
            "excluded_from_frame": len(set(frames_raw[c]) & excluded),
            "frame_size": len(per_cat[c]),
            "allocation_b1": alloc[c],
            "b1_terms": selected,
            "b1_frame_rank": ranks,
            "frame_tail": per_cat[c][alloc[c]:],
            "frame_tail_frame_rank": tail_ranks,
        }
    return {
        "generated_utc": now_iso(),
        "plan_based": True,
        "exploratory": True,
        "snapshot_sha256": SNAPSHOT_SHA256,
        "seed": SEED,
        "quota_per_category_b1": B1_QUOTA_PER_CATEGORY,
        "total_b1": sum(alloc.values()),
        "reference_anchors_terms": len(anchored),
        "reference_alias_terms": len(alias),
        "excluded_terms_total": len(excluded),
        "excluded_terms": sorted(excluded),
        "redistribution": {"short_categories": {c: alloc[c] for c in CATEGORIES if alloc[c] < B1_QUOTA_PER_CATEGORY},
                           "extra_after_redistribution": {c: alloc[c] - min(B1_QUOTA_PER_CATEGORY, len(per_cat[c]))
                                                          for c in CATEGORIES if alloc[c] > min(B1_QUOTA_PER_CATEGORY, len(per_cat[c]))},
                           "deficit_after_redistribution": leftover_deficit},
        "prompt_sha256": prompt_sha256(),
        "tau_emb": None,
        "categories": summary_frames,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(FRAME_SUMMARY), help="frame_summary.json path")
    ap.add_argument("--no-hook", action="store_true", help="skip the audit hook (tests only)")
    ap.add_argument("--emit-stdout", action="store_true", help="print the full summary")
    args = ap.parse_args(argv)
    if not args.no_hook:
        install_blind_hooks()
    snap = Snapshot()
    summary = frame_plan(snap)
    Path_out = Path(args.out)
    Path_out.parent.mkdir(parents=True, exist_ok=True)
    Path_out.write_text(json.dumps(summary, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    if args.emit_stdout:
        print(json.dumps(summary, indent=1, ensure_ascii=False))
    print(f"frame_summary -> {args.out}  total_b1={summary['total_b1']}  "
          f"excluded={summary['excluded_terms_total']}  tau_emb={summary['tau_emb']}")
    for c in CATEGORIES:
        d = summary["categories"][c]
        print(f"  {c:20} frame={d['frame_size']:5} alloc={d['allocation_b1']:3} "
              f"pre={d['frame_size_pre_exclusion']:5} excl={d['excluded_from_frame']:3}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
