#!/usr/bin/env python3
"""Generate one domain's question bank CSV from its spec and the frozen ontology snapshot (addendum 35 PLAN 35.4).
AI-generated draft; no author review.  Offline.  Expected answers are copied verbatim from the snapshot by the script.

  make_bank.py <domain>  -> <domain>/bank/bank_<domain>_v1.csv  (+ prints sha256)
Never reads a graph, rendering or build output (none exists when this is run).
"""
from __future__ import annotations

import csv
import importlib
import sys

from rdflib import Graph, OWL, RDFS, SKOS, URIRef, BNode

import s4_common as C

CREATED = "2026-10-20"
STATUS = "draft (AI-written from the ontology snapshot and documentation; not reviewed by an author)"
FIELDS = ["cq_id", "category", "question", "grounding", "expected_answer", "status", "cluster_id", "created"]


def load_graph(d: str, files: list[str]) -> Graph:
    g = Graph()
    for f in files:
        g.parse(C.ddir(d) / "raw" / f, format="turtle")
    return g


def en(g: Graph, s, p) -> list[str]:
    return [str(o).strip() for o in g.objects(s, p) if getattr(o, "language", None) in (None, "en")]


def local(u) -> str:
    u = str(u)
    return u.split("#")[-1] if "#" in u else u.rstrip("/").rsplit("/", 1)[-1]


def build(d: str) -> list[dict]:
    spec = importlib.import_module(f"specs.{d}")
    g = load_graph(d, spec.SNAPSHOTS)
    ns, px = spec.NS, spec.PFX
    nsmap = {"skos": str(SKOS), **getattr(spec, "NSMAP", {px: ns})}

    def split(x):                       # "sosa:Sensor" -> (prefix, "Sensor"); bare names take the default prefix
        p, _, n = x.rpartition(":")
        return (p or px), n

    extra = [URIRef(u) for u in getattr(spec, "EXTRA_PREDS", [])]       # e.g. prov:definition, prov:editorialNote
    def_pg = getattr(spec, "DEF_GROUNDING", "skos:definition")

    def defs(t):
        for p in [SKOS.definition, *extra[:1], RDFS.comment]:
            v = en(g, t, p)
            if v:
                return v
        return [""]

    T = lambda x: URIRef(nsmap[split(x)[0]] + split(x)[1])
    Q = lambda x: f"{split(x)[0]}:{split(x)[1]}"          # qualified display name
    rows = []
    for i, r in enumerate(spec.ROWS, 1):
        cat, kind, arg, q = r[:4]
        cq = f"{spec.ID_PREFIX}{i:02d}"
        if kind == "def":
            a = defs(T(arg))[0]
            gr = f"{def_pg} {Q(arg)}"
        elif kind == "sub":
            x, y = arg
            ty = next((URIRef(u + split(y)[1]) for u in ([nsmap[split(y)[0]]] + list(nsmap.values())) if (T(x), RDFS.subClassOf, URIRef(u + split(y)[1])) in g), None)
            assert ty is not None, f"{cq}: {x} subClassOf {y} not in snapshot"
            # a target outside the default namespace is shown bare when written bare (kept as frozen for the DCAT bank)
            a = f"Yes; direct rdfs:subClassOf {Q(y) if (':' in y or str(ty).startswith(ns)) else split(y)[1]}."
            gr = f"subclassof:{split(x)[1]}>{split(y)[1]}"
        elif kind == "children":
            kids = sorted({local(s) for s in g.subjects(RDFS.subClassOf, T(arg)) if isinstance(s, URIRef) and str(s).startswith(tuple(nsmap.values()))})
            assert kids, f"{cq}: no subclasses of {arg}"
            a = f"{', '.join(kids)} ({len(kids)})."
            gr = f"children:{split(arg)[1]}"
        elif kind == "dr":
            dom = [local(o) for o in g.objects(T(arg), RDFS.domain) if isinstance(o, URIRef)]
            rng = [local(o) for o in g.objects(T(arg), RDFS.range) if isinstance(o, URIRef)]
            parts = []
            if dom:
                parts.append(f"rdfs:domain {', '.join(dom)}")
            if rng:
                parts.append(f"rdfs:range {', '.join(rng)}")
            df = defs(T(arg))[0]
            a = Q(arg) + (f" ({'; '.join(parts)})" if parts else "") + (f": {df}" if df else "")
            gr = f"prop:{split(arg)[1]}"
        elif kind == "inv":
            p1, p2 = arg
            ok = (T(p1), OWL.inverseOf, T(p2)) in g or (T(p2), OWL.inverseOf, T(p1)) in g
            assert ok, f"{cq}: {p1}~{p2} not inverse in snapshot"
            a = f"{Q(p2)} (owl:inverseOf {Q(p1)})."
            gr = f"inverse:{split(p1)[1]}~{split(p2)[1]}"
        elif kind == "prop":
            a = f"{Q(arg)}: " + defs(T(arg))[0]
            gr = f"prop:{split(arg)[1]}"
        elif kind == "note":
            needle = r[4]
            notes = (en(g, T(arg), SKOS.scopeNote) + en(g, T(arg), SKOS.example) + en(g, T(arg), SKOS.note)
                     + en(g, T(arg), SKOS.definition) + en(g, T(arg), RDFS.comment)
                     + [x for p in extra for x in en(g, T(arg), p)])
            hit = [n for n in notes if needle.lower() in n.lower()]
            assert hit, f"{cq}: no note with {needle!r} for {arg}"
            a = hit[0]
            gr = f"rdfs:comment {Q(arg)}"
        else:
            raise ValueError(kind)
        rows.append({"cq_id": cq, "category": cat, "question": q, "grounding": gr, "expected_answer": a,
                     "status": STATUS, "cluster_id": cq, "created": CREATED})
    return rows


def main(argv=None) -> int:
    d = (argv or sys.argv[1:])[0]
    rows = build(d)
    out = C.ddir(d) / "bank" / f"bank_{d}_v1.csv"
    out.parent.mkdir(exist_ok=True)
    fz = C.ddir(d) / "bank_freeze.json"
    if fz.exists():
        raise SystemExit(f"{d} bank is frozen ({fz.name}); refusing to regenerate")
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(len(rows), dict(Counter(r["category"] for r in rows)), C.sha256_file(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
