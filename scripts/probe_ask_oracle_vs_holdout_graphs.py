#!/usr/bin/env python3
"""Diagnostic probe: can the bank's canonical ASK queries score the holdout run's
own generated graphs?

This is NOT an adjudication script. It produces no A(v,q) values and is not
wired into harness/analyze_holdout.py. It exists only to reproduce, on demand,
the finding recorded in PREREG.md section 7 (2026-09-21 addendum): the 18
ask_expressible=="yes" CQ ASK queries in bank/ask_queries/ are written against
the canonical https://brickschema.org/schema/Brick# namespace, but every one
of the six holdout variant graphs (harness/variants/{A..F}/graph_*.ttl) renders
Brick concepts under the pipeline-local http://example.org/chunktograph#
namespace instead, so executing those queries verbatim against the holdout
artifacts returns ASK=false uniformly, regardless of whether the corresponding
fact is present. No pre-registered term-alignment rule bridges the two
namespaces, so this script deliberately does not attempt one; it only reports
what it observes.

Usage: python3 scripts/probe_ask_oracle_vs_holdout_graphs.py
Exit code is 0 regardless of outcome; this is a report, not a gate.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

from rdflib import Graph

BASE = Path(__file__).resolve().parent.parent
BANK_CSV = BASE / "bank" / "cq_bank_brick_v1.csv"
VARIANTS = ("A", "B", "C", "D", "E", "F")
CANONICAL_BRICK_NS = "https://brickschema.org/schema/Brick#"


def load_ask_expressible_rows() -> list[dict]:
    with BANK_CSV.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return [row for row in rows if row["ask_expressible"] == "yes"]


def load_variant_graphs() -> dict[str, Graph]:
    graphs = {}
    for variant in VARIANTS:
        path = BASE / "harness" / "variants" / variant / f"graph_{variant}.ttl"
        if not path.is_file():
            raise SystemExit(f"missing variant graph: {path}")
        graph = Graph()
        graph.parse(path, format="turtle")
        graphs[variant] = graph
    return graphs


def canonical_brick_iri_count(graph: Graph) -> int:
    return sum(
        1
        for term in set(graph.subjects()) | set(graph.predicates()) | set(graph.objects())
        if str(term).startswith(CANONICAL_BRICK_NS)
    )


def main() -> int:
    rows = load_ask_expressible_rows()
    print(f"ask_expressible=yes CQ count: {len(rows)}")
    graphs = load_variant_graphs()

    print()
    print("Canonical brickschema.org/schema/Brick# IRI occurrences per variant graph:")
    for variant, graph in graphs.items():
        count = canonical_brick_iri_count(graph)
        print(f"  variant {variant}: {count} canonical Brick IRIs among {len(graph)} triples")

    print()
    print("Executing each ask_expressible=yes CQ's canonical-namespace ASK query against "
          "every variant graph:")
    total = 0
    true_count = 0
    for row in rows:
        query_text = (BASE / "bank" / row["ask_query_file"]).read_text(encoding="utf-8")
        for variant, graph in graphs.items():
            total += 1
            result = bool(graph.query(query_text))
            if result:
                true_count += 1
            print(f"  {row['cq_id']} variant={variant}: ASK={result}")

    print()
    print(f"Summary: {true_count}/{total} ASK=true across "
          f"{len(rows)} CQs x {len(graphs)} variants.")
    if true_count == 0:
        print(
            "As expected given 0 canonical Brick IRIs in every variant graph: the "
            "canonical-namespace ASK queries cannot score these pipeline-local-namespace "
            "graphs without an (unregistered) term-alignment step. See PREREG.md section 7."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
