"""Study 9 (prereg addendum 39): schema-anchored official SHACL shapes + internal-consistency shapes.

(a) official shapes generated from the official ontology for every official class the variant references,
(b) shapes generated from the variant's own rdfs:domain / rdfs:range declarations.
No model calls, no server access, nothing downloaded (study 8's files are reused).
Run from the repo root:  python3 paper/access2026/harness/study9_schema_shapes/analyze.py [--only NAME]
Second-domain and development graphs: numeric counts only (no IRIs, labels or text are written).
AI-generated code: review and test before reuse; not for production systems.
"""
from __future__ import annotations

import importlib.util
import json
import signal
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace, URIRef, RDF, RDFS, OWL
from rdflib.collection import Collection
from rdflib.namespace import SKOS, XSD

HERE = Path(__file__).resolve().parent
S8_DIR = HERE.parent / "study8_structural_quality"
_spec = importlib.util.spec_from_file_location("study8_analyze", S8_DIR / "analyze.py")
s8 = importlib.util.module_from_spec(_spec)
sys.modules["study8_analyze"] = s8
_spec.loader.exec_module(s8)

SH = s8.SH
PROV = s8.PROV
THINGS = s8.THINGS
local = s8.local
share = s8.share
EXT = s8.EXT
TIMEOUT = 1800
META_TYPES = {SKOS.Concept, OWL.NamedIndividual, PROV.Entity, OWL.Class, RDFS.Class, OWL.Thing, RDFS.Resource,
              RDF.Property, OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty, OWL.Restriction}
S9 = Namespace("urn:study9:")
LITERAL_DT = (RDFS.Literal, RDF.langString)


# ----------------------------------------------------------------------------- shape statistics
def count_constraints(sg: Graph) -> dict:
    prop_shapes = set(sg.subjects(SH.path, None))
    mc = [int(o) for s in prop_shapes for o in sg.objects(s, SH.minCount) if isinstance(o, Literal)]
    node_shapes = set(sg.subjects(RDF.type, SH.NodeShape))
    return {
        "node_shapes": len(node_shapes),
        "property_shapes": len(prop_shapes),
        "minCount_ge1": sum(1 for x in mc if x >= 1),
        "sh_class": sum(1 for _ in sg.triples((None, SH["class"], None))),
        "sh_datatype": sum(1 for _ in sg.triples((None, SH.datatype, None))),
        "sh_nodeKind": sum(1 for _ in sg.triples((None, SH.nodeKind, None))),
    }


def verdict(focus: int | None, violations: int | None, error: str | None = None) -> str:
    if error:
        return "error"
    if not focus:
        return "NA (vacuous)"
    return "pass" if violations == 0 else "fail"


# ----------------------------------------------------------------------------- (a) official shapes
def _range_members(off, q):
    return off.dom_rng(q, "range")[0]


def required_pairs(off, shacl_graphs: list[Graph]) -> dict:
    """class C -> {q: {'class': set, 'datatype': set, 'nodeKind': set}} for properties the official declarations
    mark as required (owl min cardinality >= 1, or official sh:property with sh:minCount >= 1 on a class holder)."""
    req: dict = defaultdict(dict)
    g = off.g
    for C in off.classes:
        for sc in g.objects(C, RDFS.subClassOf):
            if isinstance(sc, BNode) and (sc, RDF.type, OWL.Restriction) in g:
                q = g.value(sc, OWL.onProperty)
                for pred in (OWL.minCardinality, OWL.minQualifiedCardinality):
                    for n in g.objects(sc, pred):
                        try:
                            if int(n) >= 1 and isinstance(q, URIRef):
                                req[C].setdefault(q, {"class": set(), "datatype": set(), "nodeKind": set()})
                        except (TypeError, ValueError):
                            pass
    for sg in [g] + list(shacl_graphs):
        for holder, ps in sg.subject_objects(SH.property):
            q = sg.value(ps, SH.path)
            if not isinstance(q, URIRef):
                continue
            ok = False
            for n in sg.objects(ps, SH.minCount):
                try:
                    ok = ok or int(n) >= 1
                except (TypeError, ValueError):
                    pass
            if not ok:
                continue
            holders = set()
            if isinstance(holder, URIRef) and holder in off.classes:
                holders.add(holder)
            holders |= {c for c in sg.objects(holder, SH.targetClass) if c in off.classes}
            for C in holders:
                d = req[C].setdefault(q, {"class": set(), "datatype": set(), "nodeKind": set()})
                d["class"] |= {c for c in sg.objects(ps, SH["class"]) if isinstance(c, URIRef)}
                d["datatype"] |= {c for c in sg.objects(ps, SH.datatype) if isinstance(c, URIRef)}
                d["nodeKind"] |= {c for c in sg.objects(ps, SH.nodeKind) if isinstance(c, URIRef)}
    return req


class OfficialIndex:
    """Official ontology + derived lookup tables used for generation."""

    def __init__(self, files, word, extra_shacl: list[Path] | None = None):
        self.off = s8.Official(files, word)
        self.extra = []
        for f in extra_shacl or []:
            sg = Graph().parse(f, format="turtle")
            sg, _ = s8.clean_shapes(sg)
            self.extra.append(sg)
        self.dom_by_class = defaultdict(set)
        for q in self.off.props:
            for c in self.off.dom_rng(q, "domain")[0]:
                if isinstance(c, URIRef) and c not in THINGS:
                    self.dom_by_class[c].add(q)
        self.required = required_pairs(self.off, self.extra)


def _add_range(sg: Graph, ps, members: set, classes: set, copied: dict | None = None):
    cls = sorted(m for m in members if isinstance(m, URIRef) and m not in THINGS and not s8._is_dt(m))
    dts = sorted(m for m in members if isinstance(m, URIRef) and s8._is_dt(m) and m not in LITERAL_DT)
    lit = any(m in LITERAL_DT for m in members)
    if copied:
        cls = sorted(set(cls) | copied["class"]) if not cls else cls
        dts = sorted(set(dts) | copied["datatype"]) if not dts else dts
    alts = [(SH["class"], c) for c in cls] + [(SH.datatype, d) for d in dts]
    if len(alts) == 1:
        sg.add((ps, alts[0][0], alts[0][1]))
    elif len(alts) > 1:
        items = []
        for pred, val in alts:
            b = BNode()
            sg.add((b, pred, val))
            items.append(b)
        lst = BNode()
        Collection(sg, lst, items)
        sg.add((ps, SH["or"], lst))
    elif lit:
        sg.add((ps, SH.nodeKind, SH.Literal))
    elif copied and copied["nodeKind"]:
        for nk in sorted(copied["nodeKind"]):
            sg.add((ps, SH.nodeKind, nk))


def gen_official_shapes(oi: OfficialIndex, refs: dict | set) -> tuple[Graph, dict]:
    """Rule of PLAN 9.3. refs: class -> level ('R1'/'R2')."""
    sg = Graph()
    sg.bind("sh", SH)
    n_cls_with = 0
    for i, C in enumerate(sorted(refs)):
        props = set(oi.dom_by_class.get(C, set())) | set(oi.required.get(C, {}))
        if not props:
            continue
        n_cls_with += 1
        ns = S9[f"shape/{i}"]
        sg.add((ns, RDF.type, SH.NodeShape))
        sg.add((ns, SH.targetClass, C))
        sg.add((ns, SH.closed, Literal(False)))
        for j, q in enumerate(sorted(props)):
            ps = S9[f"shape/{i}/p{j}"]
            sg.add((ns, SH.property, ps))
            sg.add((ps, SH.path, q))
            req = oi.required.get(C, {}).get(q)
            if req is not None:
                sg.add((ps, SH.minCount, Literal(1)))
            members = set(_range_members(oi.off, q))
            _add_range(sg, ps, members, oi.off.classes, req)
    stats = count_constraints(sg)
    stats["referenced_classes"] = len(refs)
    stats["referenced_by_level"] = dict(Counter(refs.values())) if isinstance(refs, dict) else {}
    stats["classes_with_constraints"] = n_cls_with
    return sg, stats


def referenced_classes(g: Graph, off: s8.Official) -> dict:
    refs = {}
    terms = {x for t in g for x in t if isinstance(x, URIRef)}
    for t in terms:
        if t in off.classes:
            refs[t] = "R1"
    cand = set()
    for t in (OWL.Class, RDFS.Class):
        cand |= {s for s in g.subjects(RDF.type, t) if isinstance(s, URIRef)}
    for c in cand:
        if c in refs:
            continue
        r = off.resolve_keys([local(c)] + [str(x) for x in g.objects(c, RDFS.label)])
        if r is not None:
            refs.setdefault(r, "R2")
    for n in g.subjects(RDF.type, SKOS.Concept):
        if isinstance(n, URIRef):
            r = off.resolve_keys(s8.entity_labels(g, n))
            if r is not None:
                refs.setdefault(r, "R2")
    return refs


def subclass_edges(off: s8.Official) -> list:
    return [(s, RDFS.subClassOf, o) for s, o in off.g.subject_objects(RDFS.subClassOf)
            if isinstance(s, URIRef) and isinstance(o, URIRef)]


def make_l1(g: Graph, off: s8.Official) -> Graph:
    d = Graph()
    for t in g:
        d.add(t)
    for t in subclass_edges(off):
        d.add(t)
    return d


def make_l2(g: Graph, off: s8.Official, align: dict | None) -> tuple[Graph, dict]:
    d = make_l1(g, off)
    typed = 0
    for n in set(g.subjects(RDF.type, SKOS.Concept)):
        if isinstance(n, URIRef):
            r = off.resolve_keys(s8.entity_labels(g, n))
            if r is not None:
                d.add((n, RDF.type, r))
                typed += 1
    mapped_props = 0
    added = 0
    for p in s8.pipeline_properties(g):
        lv, q = s8.map_property(p, g, off, align or {})
        if q is None or q == p:
            continue
        mapped_props += 1
        for s, o in list(g.subject_objects(p)):
            d.add((s, q, o))
            added += 1
    return d, {"entities_typed_by_label": typed, "properties_mapped": mapped_props, "triples_added": added}


# ----------------------------------------------------------------------------- validation
class _TO(Exception):
    pass


def _alarm(signum, frame):
    raise _TO()


def run_shacl(data: Graph, shapes: Graph, orig_nodes: set, timeout_s: int = TIMEOUT) -> dict:
    from pyshacl import validate
    old = signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(timeout_s)
    t0 = time.time()
    try:
        conforms, rg, _ = validate(data, shacl_graph=shapes, inference="none", advanced=False)
    except _TO:
        return {"error": f"timeout {timeout_s}s"}
    except Exception as e:  # noqa
        return {"error": f"{type(e).__name__}: {e}"[:300]}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    results = []
    ignored = 0
    for r in rg.subjects(RDF.type, SH.ValidationResult):
        fn = rg.value(r, SH.focusNode)
        if fn not in orig_nodes:
            ignored += 1
            continue
        results.append({"focus": fn, "value": rg.value(r, SH.value), "path": rg.value(r, SH.resultPath),
                        "comp": local(rg.value(r, SH.sourceConstraintComponent) or "?"),
                        "sev": local(rg.value(r, SH.resultSeverity) or "Violation"),
                        "shape": rg.value(r, SH.sourceShape)})
    return {"results": results, "ignored": ignored, "conforms_raw": bool(conforms), "seconds": round(time.time() - t0, 1)}


def summarise(run: dict, scope_d: dict, n_triples: int, redact: bool) -> dict:
    if "error" in run:
        return {"error": run["error"], "verdict": "error", "focus_nodes": scope_d.get("constraint_distinct_focus_nodes")}
    res = run["results"]
    viol = sum(1 for r in res if r["sev"] == "Violation")
    top = Counter()
    for r in res:
        sh = r["shape"]
        top[(r["comp"], str(r["path"]) if r["path"] is not None else "-",
             str(sh) if isinstance(sh, URIRef) else "(blank node)")] += 1
    focus = scope_d.get("constraint_distinct_focus_nodes", 0)
    out = {
        "focus_nodes": focus, "shapes_with_focus_nodes": scope_d.get("constraint_shapes_with_focus_nodes"),
        "constraint_shapes": scope_d.get("constraint_shapes_targeted"),
        "conforms": viol == 0, "violations": viol, "other_severity": len(res) - viol,
        "violations_per_1000_triples": (1000.0 * viol / n_triples) if n_triples else None,
        "verdict": verdict(focus, viol), "seconds": run["seconds"],
        "results_on_official_nodes_ignored": run["ignored"],
    }
    if redact:
        comp = Counter()
        for k, n in top.items():
            comp[k[0]] += n
        out["top_constraints"] = [{"component": c, "n": n} for c, n in comp.most_common(5)]
    else:
        out["top_constraints"] = [{"component": k[0], "path": k[1], "sourceShape": k[2], "n": n}
                                  for k, n in top.most_common(5)]
    return out


# ----------------------------------------------------------------------------- (b) internal consistency
def gen_internal_shapes(g: Graph) -> tuple[Graph, dict]:
    sg = Graph()
    sg.bind("sh", SH)
    props = {s for p in (RDFS.domain, RDFS.range) for s in g.subjects(p, None) if isinstance(s, URIRef)}
    skipped = 0
    declared = 0
    for i, p in enumerate(sorted(props)):
        ns = S9[f"int/{i}"]
        added = False
        for D in g.objects(p, RDFS.domain):
            if isinstance(D, URIRef) and D not in THINGS:
                sg.add((ns, SH["class"], D))
                added = True
            elif not isinstance(D, URIRef):
                skipped += 1
        for R in g.objects(p, RDFS.range):
            if not isinstance(R, URIRef):
                skipped += 1
                continue
            if R in THINGS:
                continue
            ps = S9[f"int/{i}/r"]
            if (ns, SH.property, ps) not in sg:
                sg.add((ns, SH.property, ps))
                sg.add((ps, SH.path, p))
            if R == RDFS.Literal:
                sg.add((ps, SH.nodeKind, SH.Literal))
            elif str(R).startswith(str(XSD)) or R == RDF.langString:
                sg.add((ps, SH.datatype, R))
            else:
                sg.add((ps, SH["class"], R))
            added = True
        if added:
            declared += 1
            sg.add((ns, RDF.type, SH.NodeShape))
            sg.add((ns, SH.targetSubjectsOf, p))
    stats = count_constraints(sg)
    stats["properties_with_declaration"] = len(props)
    stats["properties_with_constraint"] = declared
    stats["complex_declarations_skipped"] = skipped
    return sg, stats


def classify_internal(g: Graph, results: list) -> dict:
    """Split internal violations (reporting only)."""
    def real_types(n):
        return {t for t in g.objects(n, RDF.type) if isinstance(t, URIRef) and t not in META_TYPES}
    kinds = Counter()
    per_path = defaultdict(Counter)
    for r in results:
        if r["sev"] != "Violation":
            continue
        comp, path = r["comp"], r["path"]
        if comp == "ClassConstraintComponent" and path is None:
            k = "domain_wrong_typed_subject" if real_types(r["focus"]) else "domain_untyped_subject"
            p_key = None
        elif comp == "ClassConstraintComponent":
            v = r["value"]
            if isinstance(v, Literal):
                k = "range_literal_where_class_expected"
            elif real_types(v):
                k = "range_wrong_typed_object"
            else:
                k = "range_untyped_object"
            p_key = path
        elif comp in ("DatatypeConstraintComponent", "NodeKindConstraintComponent"):
            k, p_key = "range_wrong_datatype_or_kind", path
        else:
            k, p_key = "other:" + comp, path
        kinds[k] += 1
        per_path[path if p_key is not None else "__domain__"][k] += 1
    return {"by_kind": dict(kinds), "per_path": per_path}


def step2_offenders(g: Graph, sg: Graph, run: dict, public: bool, topn: int = 10) -> dict:
    """Per-property attribution of internal violations. A domain violation on node f is attributed to every
    declared property p (with that sh:class domain D) that f is a subject of and that f is not typed D for."""
    res = [r for r in run["results"] if r["sev"] == "Violation"]
    # shape -> property
    shape_prop = {}
    for ns in sg.subjects(SH.targetSubjectsOf, None):
        shape_prop[ns] = sg.value(ns, SH.targetSubjectsOf)
    for ns, ps in sg.subject_objects(SH.property):
        shape_prop.setdefault(ps, shape_prop.get(ns))
    per_p = defaultdict(Counter)
    for r in res:
        p = shape_prop.get(r["shape"])
        if p is None and r["path"] is not None:
            p = r["path"]
        if p is None:
            continue
        comp, v = r["comp"], r["value"]
        if comp == "ClassConstraintComponent" and r["path"] is None:
            k = "domain"
        elif isinstance(v, Literal):
            k = "range_literal" if comp == "ClassConstraintComponent" else "range_datatype"
        else:
            k = "range_class"
        per_p[p][k] += 1
    total = sum(sum(c.values()) for c in per_p.values())
    n_decl = len({s for q in (RDFS.domain, RDFS.range) for s in g.subjects(q, None) if isinstance(s, URIRef)})
    ranked = sorted(per_p.items(), key=lambda kv: -sum(kv[1].values()))
    out = {"properties_with_violation": len(per_p), "declared_properties": n_decl,
           "share_declared_properties_with_violation": share(len(per_p), n_decl),
           "violations_attributed": total,
           "share_violations_on_top10": share(sum(sum(c.values()) for _, c in ranked[:topn]), total)}
    if public:
        rows = []
        for p, c in ranked[:topn]:
            subs = set(g.subjects(p, None))
            doms = [D for D in g.objects(p, RDFS.domain) if isinstance(D, URIRef)]
            rngs = [R for R in g.objects(p, RDFS.range) if isinstance(R, URIRef)]
            anc = _anc(g)
            typed_d = sum(1 for s in subs if any(D in anc.get(t, {t}) for t in g.objects(s, RDF.type) for D in doms)) if doms else None
            cls = Counter(t for s in subs for t in g.objects(s, RDF.type) if isinstance(t, URIRef) and t not in META_TYPES)
            rows.append({"property": local(p), "declared_domain": [local(d) for d in doms],
                         "declared_range": [local(r) for r in rngs], "triples": sum(1 for _ in g.triples((None, p, None))),
                         "subjects": len(subs), "violations": dict(c), "violations_total": sum(c.values()),
                         "share_subjects_typed_declared_domain": share(typed_d, len(subs)) if typed_d is not None else None,
                         "top_subject_classes": [{"class": local(k), "n": n} for k, n in cls.most_common(3)]})
        out["top_properties"] = rows
    return out


_ANC_CACHE: dict = {}


def _anc(g: Graph) -> dict:
    k = id(g)
    if k not in _ANC_CACHE:
        types = {o for o in g.objects(None, RDF.type) if isinstance(o, URIRef)}
        _ANC_CACHE.clear()
        _ANC_CACHE[k] = s8._ancestors(types, [g])
    return _ANC_CACHE[k]


# ----------------------------------------------------------------------------- driver
OFFICIAL_SPEC = {
    "Brick holdout": dict(files=[EXT / "brick/Brick.ttl"], extra=[]),
    "DCAT": dict(files=None, extra=[EXT / "dcat-ap-3.0.1/dcat-ap-SHACL.ttl"]),
    "SOSA/SSN": dict(files=None, extra=[]),
    "PROV": dict(files=None, extra=[]),
}


def validate_variant_internal(g: Graph, public: bool, n_triples: int) -> tuple[dict, Graph, dict]:
    sg, stats = gen_internal_shapes(g)
    orig = {x for t in g for x in t if not isinstance(x, Literal)}
    sc = s8.scope(g, sg, [])
    run = run_shacl(g, sg, orig)
    rec = {"shape_counts": stats, **summarise(run, sc, n_triples, not public)}
    return rec, sg, run


def run(only: str | None = None) -> dict:
    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "domains": {}}
    for name, spec in s8.domain_spec().items():
        if only and only != name:
            continue
        co = bool(spec.get("counts_only"))
        public = bool(spec.get("public_ids")) and not co
        dom = {"counts_only": co, "variants": {}}
        oi = None
        if spec["onts"]:
            files = spec["onts"]
            ex = OFFICIAL_SPEC.get(name, {}).get("extra", [])
            oi = OfficialIndex(files, spec["word"], ex)
            full_sg, full_stats = gen_official_shapes(oi, {c: "all" for c in oi.off.classes})
            dom["official_full_shape_set"] = full_stats
            dom["official_required_pairs"] = sum(len(v) for v in oi.required.values())
            dom["official_files"] = s8.sha_files(files) + (s8.sha_files(ex) if ex else [])
        align = json.loads(spec["align"].read_text()) if spec["align"] and spec["align"].exists() else None
        for v, p in spec["graphs"].items():
            if not p.exists():
                dom["variants"][v] = {"missing": True}
                continue
            g = Graph().parse(p)
            n = len(g)
            rec = {"sha256": s8.sha256(p), "triples": n}
            if oi is not None:
                refs = referenced_classes(g, oi.off)
                sg, st = gen_official_shapes(oi, refs)
                orig = {x for t in g for x in t if not isinstance(x, Literal)}
                l1 = make_l1(g, oi.off)
                sc = s8.scope(l1, sg, [oi.off.g])
                r1 = run_shacl(l1, sg, orig)
                rec["official"] = {"shape_counts": st, "L1": summarise(r1, sc, n, not public)}
                l2, l2info = make_l2(g, oi.off, align)
                sc2 = s8.scope(l2, sg, [oi.off.g])
                r2 = run_shacl(l2, sg, orig)
                rec["official"]["L2_punning_sensitivity"] = {**l2info, **summarise(r2, sc2, n, not public)}
            else:
                rec["official"] = {"verdict": "no official ontology"}
            irec, isg, irun = validate_variant_internal(g, public, n)
            rec["internal"] = irec
            if "results" in irun and irec.get("violations", 0) > 0:
                cl = classify_internal(g, irun["results"])
                rec["internal"]["violations_by_kind"] = cl["by_kind"]
                if v in "CDEF" or v in ("B'",):
                    rec["internal"]["step2_offenders"] = step2_offenders(g, isg, irun, public)
            dom["variants"][v] = rec
            print(name, v, n, rec["official"].get("L1", {}).get("verdict", rec["official"].get("verdict")),
                  rec["internal"].get("verdict"), flush=True)
        out["domains"][name] = dom
    return out


if __name__ == "__main__":
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    res = run(only)
    import re
    fn = HERE / ("results.json" if not only else f"results_{re.sub(r'\W+', '_', only)}.json")
    fn.write_text(json.dumps(res, indent=1, default=str))
    print("wrote", fn)
