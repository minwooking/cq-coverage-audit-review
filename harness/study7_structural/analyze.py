"""Study 7: structural outputs per pipeline stage (variants A-F) across domains.

Computed from released graph files with rdflib; SHACL/OWL via the project's own
chunktograph.metrics.validity (stage5_shacl shapes + pyshacl; owlrl closure).
No model calls. Run from repo root with the project venv:
    PYTHONPATH=src .venv/bin/python paper/access2026/harness/study7_structural/analyze.py
Second-domain graphs: only numeric aggregates are written (no labels/text).
"""
from __future__ import annotations
import hashlib, json, sys, time
from pathlib import Path
from rdflib import Graph, URIRef, Literal, RDF, RDFS, OWL, Namespace
from rdflib.namespace import SKOS

PROV = Namespace("http://www.w3.org/ns/prov#")
DCT = Namespace("http://purl.org/dc/terms/")
SH = Namespace("http://www.w3.org/ns/shacl#")
PROP_TYPES = {OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty,
              RDF.Property, OWL.FunctionalProperty, OWL.TransitiveProperty,
              OWL.SymmetricProperty}
CLASS_TYPES = {OWL.Class, RDFS.Class}
IGNORE_TYPE_OBJ = {OWL.NamedIndividual, SKOS.Concept, OWL.Class, RDFS.Class,
                   OWL.Ontology, SKOS.ConceptScheme, RDF.Property} | PROP_TYPES

ROOT = Path(__file__).resolve().parents[4]
H = ROOT / "paper/access2026/harness"
VARS = "ABCDEF"


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def structural(g: Graph) -> dict:
    classes = {s for t in CLASS_TYPES for s in g.subjects(RDF.type, t) if isinstance(s, URIRef)}
    props = {s for t in PROP_TYPES for s in g.subjects(RDF.type, t) if isinstance(s, URIRef)}
    dom = {s for s in g.subjects(RDFS.domain, None) if isinstance(s, URIRef)}
    rng = {s for s in g.subjects(RDFS.range, None) if isinstance(s, URIRef)}
    props_all = props | dom | rng
    both = dom & rng
    typed = [(s, o) for s, o in g.subject_objects(RDF.type)
             if o not in IGNORE_TYPE_OBJ and o in classes]
    prov_all = [(s, p, o) for s, p, o in g if str(p).startswith(str(PROV))]
    return {
        "triples": len(g),
        "classes": len(classes),
        "properties": len(props_all),
        "props_with_domain": len(dom),
        "props_with_range": len(rng),
        "props_with_domain_and_range": len(both),
        "domain_range_share": (len(both) / len(props_all)) if props_all else None,
        "domain_statements": len(list(g.triples((None, RDFS.domain, None)))),
        "range_statements": len(list(g.triples((None, RDFS.range, None)))),
        "skos_broader": len(list(g.triples((None, SKOS.broader, None)))),
        "skos_narrower": len(list(g.triples((None, SKOS.narrower, None)))),
        "entity_type_statements": len(typed),
        "typed_entities": len({s for s, _ in typed}),
        "prov_links": len(prov_all),
        "prov_wasDerivedFrom": sum(1 for _, p, _ in prov_all if p == PROV.wasDerivedFrom),
        "prov_wasGeneratedBy": sum(1 for _, p, _ in prov_all if p == PROV.wasGeneratedBy),
        "dct_source": len(list(g.triples((None, DCT.source, None)))),
        "std_aligned_in_graph": sum(
            1 for p in (RDFS.subPropertyOf, OWL.equivalentProperty)
            for _, o in g.subject_objects(p) if isinstance(o, URIRef)),
    }


def validity(g: Graph, run: bool = True) -> dict:
    if not run:
        return {"shacl_conforms": None, "shacl_violations": None, "shacl_note": "skipped",
                "owl_consistent": None, "owl_note": "skipped"}
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from chunktograph import metrics
        v = metrics.validity(g, metrics._infer_base_iri(g))
    except Exception as e:  # noqa
        return {"shacl_conforms": None, "shacl_violations": None, "shacl_note": f"error: {e}",
                "owl_consistent": None, "owl_note": f"error: {e}"}
    return {"shacl_conforms": v["shacl"]["conforms"], "shacl_violations": v["shacl"]["violations"],
            "shacl_note": v["shacl"]["note"], "owl_consistent": v["owl"]["consistent"],
            "owl_note": v["owl"]["note"]}


def released_shapes(g: Graph, shapes_path: Path | None) -> dict:
    if not shapes_path or not shapes_path.exists():
        return {"released_shapes": None}
    try:
        from pyshacl import validate
        sg = Graph().parse(shapes_path)
        ok, _, _ = validate(g, shacl_graph=sg, inference="rdfs")
        return {"released_shapes": str(shapes_path.relative_to(ROOT)), "released_shapes_conform": bool(ok)}
    except Exception as e:  # noqa
        return {"released_shapes": str(shapes_path.relative_to(ROOT)), "released_shapes_conform": None, "note": str(e)}


def alignment(path: Path | None) -> dict:
    if not path or not path.exists():
        return {"aligned_predicates": None, "alignment_total": None}
    d = json.loads(path.read_text())
    return {"aligned_predicates": sum(1 for v in d.values() if v), "alignment_total": len(d),
            "alignment_file": str(path.relative_to(ROOT))}


def dedup(path: Path | None) -> dict:
    if not path or not path.exists():
        return {"dedup": None}
    d = json.loads(path.read_text())
    return {"dedup_file": str(path.relative_to(ROOT)),
            "d_triples_in": d["input_count"], "d_triples_out": d["output_count"],
            "d_triples_dropped": d["dropped"]["total"],
            "d_predicates_merged": d["predicates"]["before"] - d["predicates"]["after"],
            "d_entities_merged": d["entities"]["before"] - d["entities"]["after"]}


def domain_spec():
    """domain -> {variant: graph path}, plus aux files. Paths relative to ROOT."""
    S4, S5, S5C = H / "study4_domains", H / "study5_judge_panel", H / "study5c_full_ladder"
    doms = {}
    doms["development"] = dict(
        graphs={v: ROOT / f"output/ontology_{v}.ttl" for v in VARS},
        align=ROOT / "output/standard_alignment.json", dedup=ROOT / "output/d_refine_report.json",
        shapes=ROOT / "output/shapes_F.ttl")
    doms["Brick holdout"] = dict(
        graphs={v: H / f"variants/{v}/graph_{v}.ttl" for v in VARS},
        align=H / "variants/_work/standard_alignment.json", dedup=H / "variants/_work/d_refine_report.json",
        shapes=H / "variants/_work/shapes_F.ttl")
    for d in ("dcat", "ssn", "prov"):
        g = {"A": S4 / d / "variants/A/graph_A.ttl", "B": S4 / d / "variants/B/graph_B.ttl"}
        for v in "CDE":
            g[v] = S5C / d / f"variants/{v}/graph_{v}.ttl"
        g["F"] = S5 / d / "variants/F/graph_F.ttl"
        doms[d.upper() if d != "ssn" else "SOSA/SSN"] = dict(
            graphs=g, align=S5 / d / "work/standard_alignment.json", dedup=S5 / d / "work/d_refine_report.json",
            shapes=S5 / d / "work/shapes_F.ttl")
    mfg = ROOT / "output_mfg"
    doms["second domain (counts only)"] = dict(
        graphs={"A": mfg / "ontology_A.ttl", "B": mfg / "ontology_B.ttl", "C": mfg / "ontology_C.ttl",
                "B'": mfg / "r34_bprime/ontology_Bp.ttl"},
        align=None, dedup=None, shapes=None, counts_only=True)
    return doms


def run(shacl: bool = True) -> dict:
    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "domains": {}}
    for name, spec in domain_spec().items():
        dom = {"variants": {}, "counts_only": bool(spec.get("counts_only"))}
        dom.update({k: v for k, v in dedup(spec["dedup"]).items()})
        al = alignment(spec["align"]); dom.update(al)
        for v, p in spec["graphs"].items():
            if not p.exists():
                dom["variants"][v] = {"missing": str(p.relative_to(ROOT))}
                continue
            g = Graph().parse(p)
            rec = {"file": str(p.relative_to(ROOT)), "sha256": sha256(p)}
            rec.update(structural(g))
            rec.update(validity(g, shacl))
            if v == "F":
                rec.update(released_shapes(g, spec["shapes"]))
            dom["variants"][v] = rec
            print(name, v, rec["triples"], rec["shacl_conforms"], rec["owl_consistent"], flush=True)
        out["domains"][name] = dom
    return out


if __name__ == "__main__":
    res = run(shacl="--no-shacl" not in sys.argv)
    (Path(__file__).parent / "results.json").write_text(json.dumps(res, indent=1, default=str))
