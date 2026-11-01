"""Study 8 (prereg addendum 38): independent structural-quality measurements.

Step 1  external SHACL validation (+ scope = focus nodes selected, + shape statistics)
Step 2  domain/range quality against the official ontologies (+ most-frequent-class artifact)
Step 3  provenance coverage and a seeded link spot-check

No model calls, no server access. Run from the repo root with the project venv:
    .venv/bin/python paper/access2026/harness/study8_structural_quality/analyze.py [--no-shacl] [--only NAME]
Second-domain graphs: numeric counts only (no labels, text or IRIs are written).
AI-generated code: review and test before reuse; not for production systems.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import signal
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, URIRef, RDF, RDFS, OWL
from rdflib.collection import Collection
from rdflib.namespace import SKOS, XSD

SH = Namespace("http://www.w3.org/ns/shacl#")
PROV = Namespace("http://www.w3.org/ns/prov#")
DCT = Namespace("http://purl.org/dc/terms/")
SCHEMA_DOM = URIRef("https://schema.org/domainIncludes")
SCHEMA_RNG = URIRef("https://schema.org/rangeIncludes")
SCHEMA_DOM_H = URIRef("http://schema.org/domainIncludes")
SCHEMA_RNG_H = URIRef("http://schema.org/rangeIncludes")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
H = ROOT / "paper/access2026/harness"
EXT = HERE / "external"
VARS = "ABCDEF"
SEED = 20260913
THINGS = {OWL.Thing, RDFS.Resource}
PROP_TYPES = {OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty, RDF.Property,
              OWL.FunctionalProperty, OWL.TransitiveProperty, OWL.SymmetricProperty,
              OWL.AsymmetricProperty, OWL.IrreflexiveProperty, OWL.InverseFunctionalProperty}
CLASS_TYPES = {OWL.Class, RDFS.Class}
META_NS = tuple(str(n) for n in (RDF, RDFS, OWL, SKOS, PROV, DCT, XSD, SH))
STOP = {"a", "an", "the", "of", "and", "or", "to", "in", "for"}
CONSTRAINT_PREDS = {SH.property, SH["class"], SH.datatype, SH.nodeKind, SH.minCount, SH.maxCount, SH.node, SH["in"],
                    SH.pattern, SH["or"], SH["and"], SH["not"], SH.xone, SH.hasValue, SH.sparql, SH.closed,
                    SH.minLength, SH.maxLength, SH.equals, SH.disjoint, SH.lessThan, SH.minInclusive,
                    SH.maxInclusive, SH.minExclusive, SH.maxExclusive, SH.uniqueLang, SH.languageIn, SH.qualifiedValueShape}


# ----------------------------------------------------------------------------- helpers
def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def local(iri) -> str:
    s = str(iri)
    return re.split(r"[#/]", s.rstrip("/#"))[-1]


def norm(s: str) -> str:
    """lower-case, non-alphanumerics removed"""
    s = unicodedata.normalize("NFKC", str(s)).lower()
    return re.sub(r"[\W_]+", "", s)


def norm_words(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s)).lower()
    return re.sub(r"[\W_]+", " ", s).strip()


def share(a, b):
    return (a / b) if b else None


class Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise Timeout()


# ----------------------------------------------------------------------------- Step 1
def shape_stats(sg: Graph) -> dict:
    """Constraint statistics of a shapes graph (non-vacuity of the shapes themselves)."""
    prop_shapes = set(sg.subjects(SH.path, None))
    mc = [int(o) for s in prop_shapes for o in sg.objects(s, SH.minCount) if isinstance(o, Literal)]
    node_shapes = set(sg.subjects(RDF.type, SH.NodeShape))
    targeted = set()
    for p in (SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf):
        targeted |= set(sg.subjects(p, None))
    implicit = {s for s in node_shapes if (s, RDF.type, RDFS.Class) in sg or (s, RDF.type, OWL.Class) in sg}
    cnt = lambda p: sum(1 for s in prop_shapes | node_shapes if (s, p, None) in sg)  # noqa: E731
    return {
        "triples": len(sg),
        "node_shapes": len(node_shapes),
        "property_shapes_with_path": len(prop_shapes),
        "minCount_0": sum(1 for x in mc if x == 0),
        "minCount_ge1": sum(1 for x in mc if x >= 1),
        "maxCount": cnt(SH.maxCount),
        "nodeKind": cnt(SH.nodeKind),
        "datatype": cnt(SH.datatype),
        "class_constraints": cnt(SH["class"]),
        "node_constraints": cnt(SH.node),
        "in_constraints": cnt(SH["in"]),
        "pattern": cnt(SH.pattern),
        "shapes_with_explicit_target": len(targeted),
        "shapes_with_implicit_class_target": len(implicit),
        "non_vacuous_constraints": bool(sum(1 for x in mc if x >= 1) or cnt(SH["class"]) or cnt(SH.datatype)),
    }


def clean_shapes(sg: Graph) -> tuple[Graph, int]:
    """Copy of a shapes graph without `sh:property` links to nodes that have no `sh:path` (dangling references
    in the released files make pyshacl abort as soon as such a shape has a focus node)."""
    out = Graph()
    for pfx, ns in sg.namespaces():
        out.bind(pfx, ns)
    dang = {(s, o) for s, o in sg.subject_objects(SH.property) if (o, SH.path, None) not in sg}
    for t in sg:
        if not (t[1] == SH.property and (t[0], t[2]) in dang):
            out.add(t)
    return out, len(dang)


def _ancestors(types: set, graphs: list[Graph]) -> dict:
    """class -> set(self + rdfs:subClassOf* ancestors) over the union of graphs (equivalentClass symmetric)."""
    up = defaultdict(set)
    for g in graphs:
        for s, o in g.subject_objects(RDFS.subClassOf):
            if isinstance(s, URIRef) and isinstance(o, URIRef):
                up[s].add(o)
        for s, o in g.subject_objects(OWL.equivalentClass):
            if isinstance(s, URIRef) and isinstance(o, URIRef):
                up[s].add(o)
                up[o].add(s)
    memo = {}
    for t in types:
        seen, stack = {t}, [t]
        while stack:
            x = stack.pop()
            for y in up.get(x, ()):
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        memo[t] = seen
    return memo


def scope(data: Graph, shapes: Graph, onts: list[Graph]) -> dict:
    """How many focus nodes of `data` do the shapes' targets select? (0 -> the check cannot fail)."""
    node_types = defaultdict(set)
    for s, o in data.subject_objects(RDF.type):
        if isinstance(o, URIRef):
            node_types[s].add(o)
    all_types = {t for ts in node_types.values() for t in ts}
    anc = _ancestors(all_types, [data, shapes] + onts)
    by_class = defaultdict(set)
    for n, ts in node_types.items():
        for t in ts:
            for a in anc[t]:
                by_class[a].add(n)
    subj_of = defaultdict(set)
    obj_of = defaultdict(set)
    for s, p, o in data:
        subj_of[p].add(s)
        if not isinstance(o, Literal):
            obj_of[p].add(o)
    data_nodes = {x for s, _, o in data for x in (s, o) if not isinstance(x, Literal)}
    n_shapes = 0
    with_focus = 0
    focus = set()
    focus_shapes = []
    cfocus = set()
    n_cshapes = 0
    n_cwith = 0
    shape_ids = set()
    for p in (SH.targetClass, SH.targetNode, SH.targetSubjectsOf, SH.targetObjectsOf):
        shape_ids |= set(shapes.subjects(p, None))
    for s in shapes.subjects(RDF.type, SH.NodeShape):
        if (s, RDF.type, RDFS.Class) in shapes or (s, RDF.type, OWL.Class) in shapes:
            shape_ids.add(s)
    for s in shape_ids:
        n_shapes += 1
        has_c = any((s, cp, None) in shapes for cp in CONSTRAINT_PREDS)
        n_cshapes += has_c
        f = set()
        for c in shapes.objects(s, SH.targetClass):
            f |= by_class.get(c, set())
        if (s, RDF.type, RDFS.Class) in shapes or (s, RDF.type, OWL.Class) in shapes:
            f |= by_class.get(s, set())
        for n in shapes.objects(s, SH.targetNode):
            if n in data_nodes:
                f.add(n)
        for p in shapes.objects(s, SH.targetSubjectsOf):
            f |= subj_of.get(p, set())
        for p in shapes.objects(s, SH.targetObjectsOf):
            f |= obj_of.get(p, set())
        if f:
            with_focus += 1
            focus |= f
            focus_shapes.append((str(s), len(f)))
            if has_c:
                n_cwith += 1
                cfocus |= f
    return {"targeted_shapes": n_shapes, "shapes_with_focus_nodes": with_focus,
            "distinct_focus_nodes": len(focus), "data_nodes": len(data_nodes),
            "constraint_shapes_targeted": n_cshapes, "constraint_shapes_with_focus_nodes": n_cwith,
            "constraint_distinct_focus_nodes": len(cfocus),
            "shapes_with_focus_top": [{"shape": a, "focus_nodes": b} for a, b in sorted(focus_shapes, key=lambda x: -x[1])[:5]]}


def validate_external(data: Graph, shapes: Graph, ont: Graph | None, timeout_s: int = 1800) -> dict:
    """pyshacl; results whose focus node is not a node of `data` (i.e. the official ontology's own
    nodes pulled in through ont_graph) are counted separately and excluded."""
    from pyshacl import validate
    data_nodes = {x for s, _, o in data for x in (s, o) if not isinstance(x, Literal)}
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(timeout_s)
    t0 = time.time()
    try:
        conforms, rg, _ = validate(data, shacl_graph=shapes, ont_graph=ont, inference="rdfs", advanced=True)
    except Timeout:
        return {"error": f"timeout {timeout_s}s"}
    except Exception as e:  # noqa
        return {"error": f"{type(e).__name__}: {e}"[:300]}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    own = Counter()
    ignored = 0
    top = Counter()
    for r in rg.subjects(RDF.type, SH.ValidationResult):
        fn = rg.value(r, SH.focusNode)
        if fn not in data_nodes:
            ignored += 1
            continue
        sev = local(rg.value(r, SH.resultSeverity) or "Violation")
        own[sev] += 1
        comp = local(rg.value(r, SH.sourceConstraintComponent) or "?")
        path = rg.value(r, SH.resultPath)
        ss = rg.value(r, SH.sourceShape)
        top[(comp, str(path) if path is not None else "-", str(ss) if isinstance(ss, URIRef) else "(blank node)")] += 1
    return {"conforms_data_nodes_only": sum(own.values()) == 0, "conforms_pyshacl_raw": bool(conforms),
            "violations": own.get("Violation", 0), "warnings": own.get("Warning", 0), "infos": own.get("Info", 0),
            "results_on_data_nodes": sum(own.values()), "results_on_official_ontology_nodes_ignored": ignored,
            "top_constraints": [{"component": k[0], "path": k[1], "sourceShape": k[2], "n": n}
                                for k, n in top.most_common(5)],
            "seconds": round(time.time() - t0, 1)}


def own_shapes_check(data: Graph, shapes_path: Path) -> dict:
    sg = Graph().parse(shapes_path)
    out = {"file": rel(shapes_path), "sha256": sha256(shapes_path), **shape_stats(sg)}
    try:
        from pyshacl import validate
        ok, _, _ = validate(data, shacl_graph=sg, inference="rdfs")
        out["F_conforms"] = bool(ok)
    except Exception as e:  # noqa
        out["F_conforms"] = None
        out["error"] = str(e)[:200]
    return out


# ----------------------------------------------------------------------------- official ontology index
class Official:
    def __init__(self, files: list[Path], domain_word: str):
        self.g = Graph()
        for f in files:
            self.g.parse(f)
        self.word = domain_word
        g = self.g
        self.classes = {s for t in CLASS_TYPES for s in g.subjects(RDF.type, t) if isinstance(s, URIRef)}
        self.props = {s for t in PROP_TYPES for s in g.subjects(RDF.type, t) if isinstance(s, URIRef)}
        for p in (RDFS.domain, RDFS.range, SCHEMA_DOM, SCHEMA_RNG, SCHEMA_DOM_H, SCHEMA_RNG_H):
            self.props |= {s for s in g.subjects(p, None) if isinstance(s, URIRef)}
        self._sh_dom = defaultdict(set)
        self._sh_rng = defaultdict(set)
        for holder, ps in g.subject_objects(SH.property):
            q = g.value(ps, SH.path)
            if isinstance(holder, URIRef) and isinstance(q, URIRef):
                self._sh_dom[q].add(holder)
                for c in g.objects(ps, SH["class"]):
                    if isinstance(c, URIRef):
                        self._sh_rng[q].add(c)
                for d in g.objects(ps, SH.datatype):
                    if isinstance(d, URIRef):
                        self._sh_rng[q].add(d)
        self.anc = _ancestors(self.classes | THINGS, [g])
        self.keys = defaultdict(set)
        for c in self.classes:
            self.keys[norm(local(c))].add(c)
            for lab in g.objects(c, RDFS.label):
                self.keys[norm(lab)].add(c)
        self.pkeys = defaultdict(set)
        for q in self.props:
            self.pkeys[norm(local(q))].add(q)
            for lab in g.objects(q, RDFS.label):
                self.pkeys[norm(lab)].add(q)

    def _members(self, node) -> set:
        if isinstance(node, BNode):
            u = self.g.value(node, OWL.unionOf)
            if u is not None:
                out = set()
                for m in Collection(self.g, u):
                    out |= self._members(m)
                return out
            return set()
        return {node}

    def dom_rng(self, q: URIRef, which: str) -> tuple[set, str]:
        preds = (RDFS.domain, SCHEMA_DOM, SCHEMA_DOM_H) if which == "domain" else (RDFS.range, SCHEMA_RNG, SCHEMA_RNG_H)
        s = set()
        for p in preds:
            for o in self.g.objects(q, p):
                s |= self._members(o)
        if s:
            return s, "rdfs/schema"
        sh = self._sh_dom.get(q) if which == "domain" else self._sh_rng.get(q)
        if sh:
            return set(sh), "shacl-derived"
        return set(), "none"

    def resolve_keys(self, labels: list[str]):
        """candidate strings -> unique official class or None. Dropping a leading domain word is tried too."""
        cands = []
        for lab in labels:
            n = norm(lab)
            if not n:
                continue
            cands.append(n)
            if self.word and n.startswith(self.word) and len(n) > len(self.word):
                cands.append(n[len(self.word):])
        for n in cands:
            hit = self.keys.get(n)
            if hit and len(hit) == 1:
                return next(iter(hit))
        return None

    def supers(self, c):
        return self.anc.get(c, {c})


def _is_dt(x) -> bool:
    return isinstance(x, URIRef) and (str(x).startswith(str(XSD)) or x in (RDFS.Literal, RDF.langString))


def compat(c, official_set: set, off: Official, resolver=None) -> str:
    """Category of declared/used class `c` against the official set."""
    if not official_set:
        return "official_undeclared"
    if _is_dt(c):
        if c in official_set:
            return "exact"
        if RDFS.Literal in official_set or official_set & THINGS:
            return "subclass"
        return "mismatch"
    if official_set and all(_is_dt(x) for x in official_set):
        return "mismatch"
    if c in THINGS:
        return "exact" if (c in official_set or official_set & THINGS) else "broader"
    if official_set & THINGS:
        return "subclass"
    rc = c if c in off.classes else (resolver(c) if resolver else None)
    if rc is None:
        return "noncomparable"
    if rc in official_set:
        return "exact"
    if off.supers(rc) & official_set:
        return "subclass"
    for d in official_set:
        if d in off.classes and rc in off.supers(d):
            return "broader"
    return "mismatch"


# ----------------------------------------------------------------------------- Step 2
def entity_labels(g: Graph, n) -> list[str]:
    labs = [local(n)]
    for o in g.objects(n, SKOS.prefLabel):
        labs.append(str(o) if isinstance(o, Literal) else local(o))
    for o in g.objects(n, RDFS.label):
        labs.append(str(o))
    return labs


def pipeline_properties(g: Graph) -> set:
    props = {s for t in PROP_TYPES for s in g.subjects(RDF.type, t) if isinstance(s, URIRef)}
    props |= {s for p in (RDFS.domain, RDFS.range) for s in g.subjects(p, None) if isinstance(s, URIRef)}
    for p in g.predicates():
        if isinstance(p, URIRef) and not str(p).startswith(META_NS):
            props.add(p)
    return {p for p in props if not str(p).startswith(META_NS)}


_SUF = ("ations", "ation", "ions", "ion", "ings", "ing", "ed", "es", "s")


def stem(k: str) -> str:
    """crude suffix stripper used only by the post-plan sensitivity reading"""
    if k.startswith("has") and len(k) > 5:
        k = k[3:]
    for suf in _SUF:
        if k.endswith(suf) and len(k) - len(suf) >= 3:
            return k[: -len(suf)]
    return k


def map_property(p: URIRef, g: Graph, off: Official, align: dict, use_stem: bool = False) -> tuple[str, URIRef | None]:
    if p in off.props:
        return "exact_iri", p
    labs = [str(x) for x in g.objects(p, RDFS.label)]
    lk = local(p)
    labs.append(re.sub(r"^p[_-]", "", lk).replace("-", " ").replace("_", " "))
    for lab in labs:
        t = align.get(lab)
        if t:
            tt = URIRef(t)
            if tt in off.props:
                return "alignment", tt
            return "aligned_nondomain", None
    key = norm(re.sub(r"^p[_-]", "", lk))
    if key:
        hits = set()
        for k, qs in off.pkeys.items():
            if key == k or key + "s" == k or "has" + key == k or (k and key == k + "s"):
                hits |= qs
        if len(hits) == 1:
            return "localname", next(iter(hits))
        if len(hits) > 1:
            return "ambiguous", None
        if use_stem:
            sk = stem(key)
            hits = {q for k, qs in off.pkeys.items() if stem(k) == sk for q in qs}
            if len(hits) == 1:
                return "stem", next(iter(hits))
            if len(hits) > 1:
                return "ambiguous", None
    return "unmapped", None


def step2(g: Graph, off: Official | None, align: dict | None, use_stem: bool = False) -> dict:
    classes = {s for t in CLASS_TYPES for s in g.subjects(RDF.type, t) if isinstance(s, URIRef)}
    ent_types = Counter()
    for s in g.subjects(RDF.type, SKOS.Concept):
        for o in g.objects(s, RDF.type):
            if isinstance(o, URIRef) and o not in (SKOS.Concept, OWL.NamedIndividual):
                ent_types[o] += 1
    props = {s for t in PROP_TYPES for s in g.subjects(RDF.type, t) if isinstance(s, URIRef)}
    dom = {p: next(iter(g.objects(p, RDFS.domain)), None) for p in props}
    rng = {p: next(iter(g.objects(p, RDFS.range)), None) for p in props}
    dd = Counter(v for v in dom.values() if v is not None)
    rr = Counter(v for v in rng.values() if v is not None)
    mfd = dd.most_common(1)[0] if dd else (None, 0)
    mfr = rr.most_common(1)[0] if rr else (None, 0)
    mfe = ent_types.most_common(1)[0] if ent_types else (None, 0)
    res = {
        "classes_declared": len(classes), "classes_used_as_entity_type": len(ent_types),
        "properties_typed": len(props),
        "props_with_domain": len([p for p, v in dom.items() if v is not None]),
        "props_with_range": len([p for p, v in rng.items() if v is not None]),
        "share_domain_is_most_frequent_declared_domain": share(mfd[1], sum(dd.values())),
        "share_range_is_most_frequent_declared_range": share(mfr[1], sum(rr.values())),
        "share_domain_is_most_frequent_entity_class": share(sum(1 for v in dom.values() if v is not None and v == mfe[0]), sum(dd.values())),
        "most_frequent_entity_class_share_of_typed_entities": share(mfe[1], sum(ent_types.values())),
        "distinct_declared_domains": len(dd), "distinct_declared_ranges": len(rr),
    }
    if off is None:
        return res
    resolver_cache = {}

    def resolve_class_iri(c):
        if c not in resolver_cache:
            resolver_cache[c] = off.resolve_keys([local(c)] + [str(x) for x in g.objects(c, RDFS.label)])
        return resolver_cache[c]

    ent_cache = {}

    def resolve_entity(n):
        if n not in ent_cache:
            ent_cache[n] = off.resolve_keys(entity_labels(g, n)) if isinstance(n, URIRef) else None
        return ent_cache[n]

    P = pipeline_properties(g)
    levels = Counter()
    mapped = {}
    for p in P:
        lv, q = map_property(p, g, off, align or {}, use_stem)
        levels[lv] += 1
        if q is not None:
            mapped[p] = (lv, q)
    declared = Counter()
    rngc = Counter()
    n_decl_mapped = 0
    for p, (lv, q) in mapped.items():
        d, r = dom.get(p), rng.get(p)
        if d is None and r is None:
            declared["not_declared"] += 1
            continue
        n_decl_mapped += 1
        if d is not None:
            declared[compat(d, off.dom_rng(q, "domain")[0], off, resolve_class_iri)] += 1
        if r is not None:
            rngc[compat(r, off.dom_rng(q, "range")[0], off, resolve_class_iri)] += 1
    # usage level
    use_s = Counter()
    use_o = Counter()
    n_use = 0
    for p, (lv, q) in mapped.items():
        Dq = off.dom_rng(q, "domain")[0]
        Rq = off.dom_rng(q, "range")[0]
        for s, o in g.subject_objects(p):
            n_use += 1
            rs = resolve_entity(s)
            if rs is None:
                use_s["unresolved"] += 1
            elif not Dq:
                use_s["official_undeclared"] += 1
            else:
                use_s["compatible" if compat(rs, Dq, off) in ("exact", "subclass") else "incompatible"] += 1
            if isinstance(o, Literal):
                use_o["literal"] += 1
                continue
            ro = resolve_entity(o)
            if ro is None:
                use_o["unresolved"] += 1
            elif not Rq:
                use_o["official_undeclared"] += 1
            else:
                use_o["compatible" if compat(ro, Rq, off) in ("exact", "subclass") else "incompatible"] += 1
    res.update({
        "pipeline_properties": len(P), "mapping_levels": dict(levels), "n_mapped": len(mapped),
        "n_mapped_with_declared_domain_or_range": n_decl_mapped,
        "declared_domain": dict(declared), "declared_range": dict(rngc),
        "usage_triples_on_mapped": n_use, "usage_subject": dict(use_s), "usage_object": dict(use_o),
        "usage_subject_compatible_share": share(use_s["compatible"], use_s["compatible"] + use_s["incompatible"]),
        "usage_object_compatible_share": share(use_o["compatible"], use_o["compatible"] + use_o["incompatible"]),
        "usage_subject_resolvable_share": share(sum(v for k, v in use_s.items() if k != "unresolved"), sum(use_s.values())),
    })
    return res


# ----------------------------------------------------------------------------- Step 3
def concepts_of(g: Graph) -> list:
    return sorted({s for s in g.subjects(RDF.type, SKOS.Concept) if isinstance(s, URIRef)}, key=str)


def chunk_id_of(o) -> str:
    return re.sub(r"^chunk_", "", local(o))


def prov_coverage(g: Graph, chunk_ids: set | None) -> dict:
    cons = concepts_of(g)
    cset = set(cons)
    links = defaultdict(set)
    for s, o in g.subject_objects(PROV.wasDerivedFrom):
        if s in cset:
            links[s].add(chunk_id_of(o))
    src_only = sum(1 for c in cons if c not in links and (c, DCT.source, None) in g)
    ref_chunks = {x for v in links.values() for x in v}
    lens = sorted(len(v) for v in links.values())
    eligible = [(s, p, o) for s, p, o in g if p != DCT.source and not str(p).startswith(str(PROV))]
    n_el = len(eligible)
    n_el_prov = sum(1 for s, _, _ in eligible if s in links)
    n_el_c = sum(1 for s, _, _ in eligible if s in cset)
    return {
        "concepts": len(cons), "concepts_with_prov": len(links),
        "share_concepts_with_prov": share(len(links), len(cons)),
        "concepts_with_source_but_no_prov": src_only,
        "chunks_total": len(chunk_ids) if chunk_ids is not None else None,
        "chunks_referenced": len(ref_chunks & chunk_ids) if chunk_ids is not None else len(ref_chunks),
        "share_chunks_referenced": share(len(ref_chunks & chunk_ids), len(chunk_ids)) if chunk_ids else None,
        "links_total": sum(lens),
        "links_per_linked_concept_mean": (sum(lens) / len(lens)) if lens else None,
        "links_per_linked_concept_median": (lens[len(lens) // 2] if lens else None),
        "links_per_linked_concept_max": (lens[-1] if lens else None),
        "triples_eligible": n_el,
        "share_triples_subject_has_prov": share(n_el_prov, n_el),
        "share_concept_subject_triples_subject_has_prov": share(n_el_prov, n_el_c),
    }


def prov_links(g: Graph) -> list:
    cset = set(concepts_of(g))
    return sorted({(s, chunk_id_of(o)) for s, o in g.subject_objects(PROV.wasDerivedFrom) if s in cset},
                  key=lambda x: (str(x[0]), x[1]))


def label_candidates(g: Graph, c, word: str) -> list[str]:
    labs = entity_labels(g, c)
    out = []
    for lab in labs:
        n = norm_words(lab)
        if not n:
            continue
        out.append(n)
        if word and n.startswith(word + " ") and len(n) > len(word) + 1:
            out.append(n[len(word) + 1:])
    return list(dict.fromkeys(out))


def spot_check(g: Graph, chunks: dict, word: str, n: int = 30, seed: int = SEED, with_ids: bool = True) -> dict:
    links = prov_links(g)
    rnd = random.Random(seed)
    samp = rnd.sample(links, min(n, len(links)))
    strict = loose = missing = 0
    rows = []
    for c, cid in samp:
        text = chunks.get(cid)
        if text is None:
            missing += 1
            rows.append({"concept": local(c), "chunk": cid, "strict": None, "loose": None})
            continue
        t = norm_words(text)
        cands = label_candidates(g, c, word)
        s_ok = any(f" {x} " in f" {t} " for x in cands)
        tt = set(t.split())
        l_ok = any(all(w in tt for w in x.split() if w not in STOP) for x in cands if any(w not in STOP for w in x.split()))
        strict += s_ok
        loose += l_ok
        rows.append({"concept": local(c), "chunk": cid, "strict": bool(s_ok), "loose": bool(l_ok)})
    judged = len(samp) - missing
    out = {"links_available": len(links), "sampled": len(samp), "chunk_text_missing": missing,
           "strict_contained": strict, "strict_share": share(strict, judged),
           "loose_contained": loose, "loose_share": share(loose, judged)}
    if with_ids:
        out["sample"] = rows
    return out


# ----------------------------------------------------------------------------- domain spec
def domain_spec() -> dict:
    S4, S5, S5C = H / "study4_domains", H / "study5_judge_panel", H / "study5c_full_ladder"
    D = {}
    D["development"] = dict(
        graphs={v: ROOT / f"output/ontology_{v}.ttl" for v in VARS}, chunks=ROOT / "output/atomic_chunks.json",
        align=ROOT / "output/standard_alignment.json", shapes_own=ROOT / "output/shapes_F.ttl",
        onts=None, ext_shapes=None, word="", public_ids=False)
    D["Brick holdout"] = dict(
        graphs={v: H / f"variants/{v}/graph_{v}.ttl" for v in VARS}, chunks=H / "variants/_work/atomic_chunks.json",
        align=H / "variants/_work/standard_alignment.json", shapes_own=H / "variants/_work/shapes_F.ttl",
        onts=[EXT / "brick/Brick.ttl"], ext_shapes={"Brick.ttl (release shapes)": [EXT / "brick/Brick.ttl"]}, word="brick", public_ids=True)
    onts = {"dcat": [S4 / "dcat/raw/dcat.ttl"], "ssn": [S4 / "ssn/raw/sosa.ttl", S4 / "ssn/raw/ssn.ttl"],
            "prov": [S4 / "prov/raw/prov.ttl"]}
    words = {"dcat": "dcat", "ssn": "sosa", "prov": "prov"}
    for d in ("dcat", "ssn", "prov"):
        g = {"A": S4 / d / "variants/A/graph_A.ttl", "B": S4 / d / "variants/B/graph_B.ttl"}
        for v in "CDE":
            g[v] = S5C / d / f"variants/{v}/graph_{v}.ttl"
        g["F"] = S5 / d / "variants/F/graph_F.ttl"
        D[{"dcat": "DCAT", "ssn": "SOSA/SSN", "prov": "PROV"}[d]] = dict(
            graphs=g, chunks=S5 / d / "work/atomic_chunks.json", align=S5 / d / "work/standard_alignment.json",
            shapes_own=S5 / d / "work/shapes_F.ttl", onts=onts[d],
            ext_shapes=({"DCAT-AP 3.0.1 core": [EXT / "dcat-ap-3.0.1/dcat-ap-SHACL.ttl"],
                         "DCAT-AP 3.0.1 core+ranges": [EXT / "dcat-ap-3.0.1/dcat-ap-SHACL.ttl", EXT / "dcat-ap-3.0.1/ranges.ttl"]}
                        if d == "dcat" else None),
            word=words[d], public_ids=True)
    mfg = ROOT / "output_mfg"
    D["second domain (counts only)"] = dict(
        graphs={"A": mfg / "ontology_A.ttl", "B": mfg / "ontology_B.ttl", "C": mfg / "ontology_C.ttl",
                "B'": mfg / "r34_bprime/ontology_Bp.ttl"},
        chunks=None, align=None, shapes_own=None, onts=None, ext_shapes=None, word="", counts_only=True, public_ids=False)
    return D


def load_chunks(p: Path | None) -> dict:
    if not p or not p.exists():
        return {}
    return {c["id"]: c["atomic_chunk"] for c in json.loads(p.read_text())}


def sha_files(files):
    return [{"file": rel(f), "sha256": sha256(f)} for f in files]


def search_sh_terms(files) -> dict:
    out = {}
    for f in files:
        g = Graph().parse(f)
        out[rel(f)] = sum(1 for p in g.predicates() if str(p).startswith(str(SH)))
    return out


def run(shacl: bool = True, only: str | None = None) -> dict:
    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seed": SEED,
           "external_fetch_log": json.loads((EXT / "FETCH_LOG.json").read_text()), "domains": {}}
    for name, spec in domain_spec().items():
        if only and only != name:
            continue
        co = bool(spec.get("counts_only"))
        dom = {"counts_only": co, "variants": {}}
        off = Official(spec["onts"], spec["word"]) if spec["onts"] else None
        align = json.loads(spec["align"].read_text()) if spec["align"] and spec["align"].exists() else None
        chunks = load_chunks(spec["chunks"])
        ext_sets = {}
        if spec["ext_shapes"]:
            dom["external_shapes"] = {}
            for sname, files in spec["ext_shapes"].items():
                sg = Graph()
                for f in files:
                    sg.parse(f, format="turtle")
                dom["external_shapes"][sname] = {"files": sha_files(files), **shape_stats(sg)}
                sg, nd = clean_shapes(sg)
                dom["external_shapes"][sname]["dangling_sh_property_refs_removed_before_validation"] = nd
                ext_sets[sname] = sg
        else:
            dom["external_shapes"] = None
            if spec["onts"]:
                dom["official_ontology_sh_terms"] = search_sh_terms(spec["onts"])
        if off:
            dom["official_ontology"] = {"files": sha_files(spec["onts"]), "classes": len(off.classes), "properties": len(off.props),
                                        "props_with_official_domain": sum(1 for q in off.props if off.dom_rng(q, "domain")[0]),
                                        "props_with_official_range": sum(1 for q in off.props if off.dom_rng(q, "range")[0])}
        for v, p in spec["graphs"].items():
            if not p.exists():
                dom["variants"][v] = {"missing": rel(p)}
                continue
            g = Graph().parse(p)
            rec = {"sha256": sha256(p), "triples": len(g)}
            if not co:
                rec["file"] = rel(p)
            if ext_sets and shacl:
                rec["external_shacl"] = {}
                for sname, sg in ext_sets.items():
                    rec["external_shacl"][sname] = {"scope": scope(g, sg, [off.g] if off else []),
                                                    **validate_external(g, sg, off.g if off else None)}
            rec["step2"] = step2(g, off, align)
            if off is not None and not co:
                rec["step2_stem_sensitivity"] = step2(g, off, align, use_stem=True)
            if v in ("E", "F") and not co:
                rec["step3"] = prov_coverage(g, set(chunks) if chunks else None)
                if v == "E":
                    rec["step3"]["spot_check"] = spot_check(g, chunks, spec["word"], with_ids=spec["public_ids"])
            if v == "F" and spec["shapes_own"]:
                rec["own_shapes"] = own_shapes_check(g, spec["shapes_own"])
            dom["variants"][v] = rec
            print(name, v, len(g), flush=True)
        out["domains"][name] = dom
    return out


if __name__ == "__main__":
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    res = run(shacl="--no-shacl" not in sys.argv, only=only)
    fn = HERE / ("results.json" if not only else f"results_{re.sub(r'\W+', '_', only)}.json")
    fn.write_text(json.dumps(res, indent=1, default=str))
    print("wrote", fn)
