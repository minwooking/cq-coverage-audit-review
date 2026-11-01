"""Generate a pipeline input corpus from the frozen IOF Core Release_202603 snapshot.

Same principle as build_brick_corpus.py: every sentence is assembled mechanically from
triples in the frozen snapshot (`data/iof_core_202603/Core.ttl`), nothing is added, and the
output has the nested shape the pipeline reads (stage1_extract._iter_leaf). The rendering rules
are documented in data/iof_core_202603/CORPUS_RENDERING.md.

Differences forced by the source, not by choice:
  * definitions live in iof-av:naturalLanguageDefinition (Brick: skos:definition / rdfs:comment);
  * owl:Restriction / equivalentClass / union-domain blank nodes are NOT rendered (named terms only);
  * BFO is imported but not stored in the snapshot, so BFO terms appear only where Core.ttl
    itself annotates them (one re-annotated class) or references them as named parents.

The same caveat as Brick applies: the CQ bank was authored against this snapshot, so the corpus
contains the answers; the study measures preservation, not discovery.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rdflib import Graph, RDF, RDFS, OWL, URIRef

from domains import load_domain

DOMAIN = load_domain("iof")
FROZEN_TTL_SHA256 = DOMAIN.snapshot_sha256
IOF_AV = "https://spec.industrialontologies.org/ontology/annotation/"
NL_DEFINITION = URIRef(IOF_AV + "naturalLanguageDefinition")


def _named(objs) -> list[URIRef]:
    return [x for x in objs if isinstance(x, URIRef)]


def _qnames(objs) -> list[str]:
    return sorted({DOMAIN.qname(x) for x in _named(objs)})


def _first(g: Graph, s, p):
    # Deterministic choice if a term ever carries several values.
    values = sorted(str(o) for o in g.objects(s, p))
    return values[0] if values else None


def build(ttl: Path) -> dict:
    digest = hashlib.sha256(ttl.read_bytes()).hexdigest()
    if digest != FROZEN_TTL_SHA256:
        raise SystemExit(f"snapshot digest mismatch: {digest}")

    g = Graph()
    g.parse(ttl, format="turtle")
    classes = set(_named(g.subjects(RDF.type, OWL.Class)))

    sections: dict[tuple[str, ...], list[str]] = {}

    def add(hierarchy: tuple[str, ...], text: str) -> None:
        sections.setdefault(hierarchy, []).append(text)

    def ns_of(name: str) -> str:
        return name.split(":")[0] if ":" in name else "other"

    for s in sorted(classes, key=str):
        name = DOMAIN.qname(s)
        label = _first(g, s, RDFS.label)
        defn = _first(g, s, NL_DEFINITION)
        parents = _qnames(g.objects(s, RDFS.subClassOf))
        sent = [f"{name} is a class in the schema."]
        if label:
            sent.append(f'Its label is "{label}".')
        if parents:
            sent.append(f"It is a subclass of {', '.join(parents)}.")
        if defn:
            sent.append(f"It is defined as: {defn}")
        add(("Schema", f"{ns_of(name)} vocabulary", "Classes"), " ".join(sent))

    for pred_type, kind in ((OWL.ObjectProperty, "object property"),
                            (OWL.DatatypeProperty, "datatype property")):
        for s in sorted(set(_named(g.subjects(RDF.type, pred_type))), key=str):
            name = DOMAIN.qname(s)
            label = _first(g, s, RDFS.label)
            defn = _first(g, s, NL_DEFINITION)
            parents = _qnames(g.objects(s, RDFS.subPropertyOf))
            dom = _qnames(g.objects(s, RDFS.domain))
            rng = _qnames(g.objects(s, RDFS.range))
            inv = _qnames(g.objects(s, OWL.inverseOf))
            sent = [f"{name} is an {kind}."]
            if label:
                sent.append(f'Its label is "{label}".')
            if parents:
                sent.append(f"It is a subproperty of {', '.join(parents)}.")
            if dom:
                sent.append(f"Its domain is {', '.join(dom)}.")
            if rng:
                sent.append(f"Its range is {', '.join(rng)}.")
            if inv:
                sent.append(f"It is the inverse of {', '.join(inv)}.")
            if defn:
                sent.append(f"It is defined as: {defn}")
            add(("Schema", f"{ns_of(name)} vocabulary", kind.title() + " definitions"),
                " ".join(sent))

    chunks, toc, n_atomic = [], [], 0
    for ci, (hierarchy, texts) in enumerate(sorted(sections.items())):
        toc.append({"title": " / ".join(hierarchy), "level": len(hierarchy)})
        chunks.append({
            "toc_hierarchy": list(hierarchy[:-1]),
            "toc_index": f"{ci + 1}",
            "child_chunks": {
                "advanced_chunking_result": [{
                    "title": hierarchy[-1],
                    "status": "ok",
                    "chunk_text": " ".join(texts)[:4000],
                    "atomic_chunks": [{"content": {"text": t}} for t in texts],
                }]
            },
        })
        n_atomic += len(texts)

    return {
        "toc": toc,
        "chunks": chunks,
        "_provenance": {
            "generated_from": DOMAIN.corpus_generated_from,
            "snapshot_sha256": digest,
            "n_top_level_chunks": len(chunks),
            "n_atomic_chunks": n_atomic,
            "note": "Derived from the same snapshot the CQ bank was authored "
                    "against. Measures extraction fidelity, not discovery.",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ttl", type=Path, default=DOMAIN.snapshot_path)
    ap.add_argument("--out", type=Path, default=DOMAIN.corpus_path)
    a = ap.parse_args()
    corpus = build(a.ttl)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(corpus, ensure_ascii=False, indent=1))
    n = corpus["_provenance"]["n_atomic_chunks"]
    print(f"wrote {a.out}: {len(corpus['chunks'])} sections, {n} atomic chunks")
    print(f"rough extraction cost: {n} LLM calls "
          f"(~{n * 2 / 60:.0f} min at 2 s/call, ~{n * 30 / 3600:.1f} h at 30 s/call)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
