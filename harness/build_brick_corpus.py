"""Generate a pipeline input corpus from the frozen Brick snapshot.

The holdout compares pipeline variants built from Brick DOCUMENTATION. No such
corpus ships with this repository -- only the ontology itself -- so there is
nothing for the pipeline to consume and therefore no variants to contrast. This
script closes that gap deterministically: it renders the frozen snapshot as
prose documentation in the chunking format the pipeline expects.

What this is NOT: it does not fabricate content. Every sentence is assembled
from triples in the frozen TTL, so the corpus says exactly what the snapshot
says and nothing more.

A caveat worth stating plainly. The CQ bank was authored blind against this same
snapshot, so a corpus derived from it is guaranteed to CONTAIN the answers. That
makes the resulting study a test of whether the pipeline PRESERVES what its
input already stated -- an upper bound on extraction fidelity, not evidence that
the pipeline discovers anything. Do not present it as the latter.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rdflib import Graph, RDF, RDFS, OWL
from rdflib.namespace import SKOS

from domains import load_domain

# Snapshot digest, namespace table, snapshot path and output path now come from
# domains/brick.toml (values unchanged; harness/test_domain_regression.py pins the output bytes).
DOMAIN = load_domain("brick")
FROZEN_TTL_SHA256 = DOMAIN.snapshot_sha256


def _qname(u) -> str:
    return DOMAIN.qname(u)


def build(ttl: Path) -> dict:
    digest = hashlib.sha256(ttl.read_bytes()).hexdigest()
    if digest != FROZEN_TTL_SHA256:
        raise SystemExit(f"snapshot digest mismatch: {digest}")

    g = Graph()
    g.parse(ttl, format="turtle")
    classes = set(g.subjects(RDF.type, OWL.Class)) | set(g.subjects(RDF.type, RDFS.Class))

    # The pipeline reads a nested shape (see stage1_extract._iter_leaf):
    #   chunks[].toc_hierarchy
    #   chunks[].toc_index
    #   chunks[].child_chunks.advanced_chunking_result[].title
    #   chunks[].child_chunks.advanced_chunking_result[].atomic_chunks[].content.text
    # Emit exactly that, grouped one top-level chunk per vocabulary section.
    sections: dict[tuple[str, ...], list[str]] = {}

    def add(hierarchy: tuple[str, ...], text: str) -> None:
        sections.setdefault(hierarchy, []).append(text)

    for s in sorted((c for c in classes if not str(c).startswith("_")), key=str):
        name = _qname(s)
        label = next(g.objects(s, RDFS.label), None)
        defn = (next(g.objects(s, SKOS.definition), None)
                or next(g.objects(s, RDFS.comment), None))
        parents = sorted({_qname(x) for x in g.objects(s, RDFS.subClassOf)
                          if not str(x).startswith("_")})
        sent = [f"{name} is a class in the schema."]
        if label:
            sent.append(f'Its label is "{label}".')
        if parents:
            sent.append(f"It is a subclass of {', '.join(parents)}.")
        if defn:
            sent.append(f"It is defined as: {defn}")
        ns = name.split(":")[0] if ":" in name else "other"
        add(("Schema", f"{ns} vocabulary", "Classes"), " ".join(sent))

    for pred_type, kind in ((OWL.ObjectProperty, "object property"),
                            (OWL.DatatypeProperty, "datatype property")):
        for s in sorted(set(g.subjects(RDF.type, pred_type)), key=str):
            name = _qname(s)
            dom = sorted({_qname(x) for x in g.objects(s, RDFS.domain)})
            rng = sorted({_qname(x) for x in g.objects(s, RDFS.range)})
            inv = sorted({_qname(x) for x in g.objects(s, OWL.inverseOf)})
            sent = [f"{name} is an {kind}."]
            if dom:
                sent.append(f"Its domain is {', '.join(dom)}.")
            if rng:
                sent.append(f"Its range is {', '.join(rng)}.")
            if inv:
                sent.append(f"It is the inverse of {', '.join(inv)}.")
            ns = name.split(":")[0] if ":" in name else "other"
            add(("Schema", f"{ns} vocabulary", kind.title() + " definitions"),
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
                    "atomic_chunks": [
                        {"content": {"text": t}} for t in texts
                    ],
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
    ap.add_argument("--ttl", type=Path, default=Path("data/brick-v1.4.4.ttl"))
    ap.add_argument("--out", type=Path, default=Path("harness/brick_corpus.json"))
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
