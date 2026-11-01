#!/usr/bin/env python3
"""Experiment 3 (rendering-length) input generator.  NO judge call is made here.

For each variant x CQ it writes the judge input of three conditions:

  full      the frozen ``variants/<V>/rendered_view.txt`` as-is.  Referenced by
            path + sha256 in the manifest; NEVER copied (no file under inputs/).
  limited   the first LIMITED_CHARS characters of the view, cut on a line
            boundary, with the marker ``[truncated]`` appended (rule below).
  subgraph  ``graph_view.ego_graph`` (hop 2, question-token matching) around the
            nodes whose names/labels match the question, rendered as text by the
            SAME renderer as the full view (``run_simulated.schema_view``) on a
            temporary Turtle holding only the sub-graph.  Zero matched nodes (or
            an empty render) -> ``not_applicable``; no file is written.

Truncation rule (to be registered verbatim, PREREG addendum 17):
  head = view[:60000].  If view has <= 60000 characters it is unchanged.
  Otherwise, unless view[60000] is a newline (head already ends on a complete
  line), drop everything after the last newline in head; if head has no newline,
  keep head.  Then append "\\n[truncated]".  Characters counted as Python str
  code points (UTF-8 text).

Answer-leak guard: sub-graph extraction receives ONLY the question text.  The
bank is read through ``load_questions`` which keeps cq_id/question/cluster_id/
category and drops every other column (``grounding``, ``expected_answer``, ...).
The judge-evidence argument of ``ego_graph`` is always empty.  Pinned by tests.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
sys.path.insert(0, str(HARNESS))

import graph_view as gv  # noqa: E402

LIMITED_CHARS = 60_000
TRUNC_MARKER = "[truncated]"
HOP = 2  # fixed inside graph_view.ego_graph (depth-2 BFS); recorded in the manifest
CONDITIONS = ("full", "limited", "subgraph")
BANK_PATH = ACCESS / "bank" / "cq_bank_brick_v1.csv"
VARIANTS_DIR = HARNESS / "variants"
VARIANT_IDS = ("A", "B", "C", "D", "E", "F")
ALLOWED_BANK_COLUMNS = ("cq_id", "question", "cluster_id", "category")
SUBGRAPH_FORBIDDEN_COLUMNS = ("grounding", "expected_answer")


def est_tokens(chars: int) -> int:
    return -(-chars // 4)  # ceil(chars / 4), the registered estimate


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_questions(path: Path = BANK_PATH) -> list[dict]:
    """Bank rows reduced to ALLOWED_BANK_COLUMNS (leak guard by construction)."""
    with path.open(encoding="utf-8", newline="") as fh:
        return [{k: row[k] for k in ALLOWED_BANK_COLUMNS} for row in csv.DictReader(fh)]


def limit_view(view: str, limit: int = LIMITED_CHARS) -> tuple[str, bool]:
    """Registered truncation rule.  Returns (text, truncated?)."""
    if len(view) <= limit:
        return view, False
    head = view[:limit]
    if view[limit] != "\n":
        cut = head.rfind("\n")
        if cut >= 0:
            head = head[:cut]
    return head + "\n" + TRUNC_MARKER, True


class VariantContext:
    """Per-variant parsed graph, loaded once (rdflib parse of the TTL)."""

    def __init__(self, variant: str, variants_dir: Path = VARIANTS_DIR):
        from rdflib import Graph
        self.variant = variant
        self.view_path = variants_dir / variant / "rendered_view.txt"
        self.ttl_path = variants_dir / variant / f"graph_{variant}.ttl"
        self.view = self.view_path.read_text(encoding="utf-8")
        self.view_sha = sha256_text(self.view)
        self.vg = gv.load_variant_ttl(self.ttl_path)
        self.graph = Graph().parse(str(self.ttl_path), format="turtle")


def build_subgraph_text(ctx: VariantContext, question: str) -> tuple[str, int, int]:
    """(rendered text, matched root nodes, sub-graph nodes) from the QUESTION only."""
    from rdflib import Graph, Literal, RDF, URIRef
    from run_simulated import schema_view

    ego = gv.ego_graph(ctx.vg, gv.cq_tokens(question), gv.JudgeEvidence((), {}))
    nodes = ego.get("nodes", [])
    if not nodes:
        return "", 0, 0
    keep = {n["id"] for n in nodes}
    roots = sum(1 for n in nodes if n["cls"] == "root")
    sub = Graph()
    for s in keep:
        for p, o in ctx.graph.predicate_objects(URIRef(s)):
            if isinstance(o, Literal) or p == RDF.type or str(o) in keep:
                sub.add((URIRef(s), p, o))
    with tempfile.TemporaryDirectory() as tmp:
        tmp_ttl = Path(tmp) / "subgraph.ttl"
        sub.serialize(destination=str(tmp_ttl), format="turtle")
        text = schema_view(tmp_ttl)
    return text, roots, len(keep)


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ACCESS.resolve()))
    except ValueError:
        return str(path.resolve())


def generate(bank: Path, out_dir: Path, variants: tuple[str, ...] = VARIANT_IDS,
             variants_dir: Path = VARIANTS_DIR, exclusions: frozenset = frozenset()) -> list[dict]:
    rows = load_questions(bank)
    records: list[dict] = []
    for v in variants:
        ctx = VariantContext(v, variants_dir)
        for row in rows:
            cq = row["cq_id"]
            base = {"variant": v, "cq_id": cq, "cluster_id": row["cluster_id"],
                    "category": row["category"], "documented_exclusion": (v, cq) in exclusions}
            # (a) full: reference only
            records.append({**base, "condition": "full", "status": "ok", "ref": True,
                            "path": _rel(ctx.view_path), "chars": len(ctx.view),
                            "est_tokens": est_tokens(len(ctx.view)), "matched_nodes": None,
                            "sha256": ctx.view_sha, "source_view_sha256": ctx.view_sha,
                            "truncated": False})
            # (b) limited
            text, truncated = limit_view(ctx.view)
            p = out_dir / v / cq / "limited.txt"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            records.append({**base, "condition": "limited", "status": "ok", "ref": False,
                            "path": _rel(p), "chars": len(text), "est_tokens": est_tokens(len(text)),
                            "matched_nodes": None, "sha256": sha256_text(text),
                            "source_view_sha256": ctx.view_sha, "truncated": truncated})
            # (c) subgraph
            sg, roots, n_nodes = build_subgraph_text(ctx, row["question"])
            sp = out_dir / v / cq / "subgraph.txt"
            if roots == 0 or not sg.strip():
                if sp.exists():
                    sp.unlink()
                records.append({**base, "condition": "subgraph", "status": "not_applicable",
                                "reason": "no_matching_nodes" if roots == 0 else "empty_render",
                                "ref": False, "path": None, "chars": 0, "est_tokens": 0,
                                "matched_nodes": roots, "subgraph_nodes": n_nodes,
                                "sha256": None, "source_view_sha256": ctx.view_sha,
                                "truncated": False})
            else:
                sp.write_text(sg, encoding="utf-8")
                records.append({**base, "condition": "subgraph", "status": "ok", "ref": False,
                                "path": _rel(sp), "chars": len(sg), "est_tokens": est_tokens(len(sg)),
                                "matched_nodes": roots, "subgraph_nodes": n_nodes,
                                "sha256": sha256_text(sg), "source_view_sha256": ctx.view_sha,
                                "truncated": False})
    return records


def documented_exclusions() -> frozenset:
    import run_holdout as rh
    return frozenset(rh.DOCUMENTED_EXCLUSION_KEYS)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bank", type=Path, default=BANK_PATH)
    ap.add_argument("--out", type=Path, default=HERE / "inputs")
    ap.add_argument("--variants", default=",".join(VARIANT_IDS))
    a = ap.parse_args()
    variants = tuple(x for x in a.variants.split(",") if x)
    records = generate(a.bank, a.out, variants, VARIANTS_DIR, documented_exclusions())
    a.out.mkdir(parents=True, exist_ok=True)
    with (a.out / "manifest.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    na = [r for r in records if r["status"] == "not_applicable"]
    print(f"records={len(records)} not_applicable={len(na)} "
          f"(of which documented_exclusion={sum(r['documented_exclusion'] for r in na)})")
    for v in variants:
        print(f"  {v}: not_applicable={sum(r['variant'] == v for r in na)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
