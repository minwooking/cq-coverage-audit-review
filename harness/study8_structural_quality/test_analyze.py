"""Synthetic tests for study 8 analysis code (no repository graphs needed)."""
import sys
from pathlib import Path
import pytest
from rdflib import Graph, URIRef, Literal, RDF, RDFS, OWL, Namespace
from rdflib.namespace import SKOS

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze as A  # noqa: E402

PFX = """@prefix ex: <http://ex.org/o#> . @prefix ct: <http://example.org/chunktograph#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> . @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> . @prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix prov: <http://www.w3.org/ns/prov#> . @prefix dct: <http://purl.org/dc/terms/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> . @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
"""
ONT = PFX + """
ex:Thingy a owl:Class . ex:Sensor a owl:Class ; rdfs:subClassOf ex:Thingy ; rdfs:label "Sensor" .
ex:Room a owl:Class ; rdfs:label "Room" . ex:TempSensor a owl:Class ; rdfs:subClassOf ex:Sensor .
ex:feeds a owl:ObjectProperty ; rdfs:domain ex:Sensor ; rdfs:range ex:Room .
ex:hasName a owl:DatatypeProperty ; rdfs:domain ex:Thingy ; rdfs:range xsd:string .
ex:free a owl:ObjectProperty .
ex:uni a owl:ObjectProperty ; rdfs:domain [ owl:unionOf ( ex:Room ex:Sensor ) ] .
"""


def G(t):
    return Graph().parse(data=t, format="turtle")


def off():
    p = Path(__file__).parent / "_tmp_ont.ttl"
    p.write_text(ONT)
    try:
        return A.Official([p], "ex")
    finally:
        p.unlink()


def test_norm_and_local():
    assert A.norm("Absolute_Humidity-Sensor") == "absolutehumiditysensor"
    assert A.local("http://x/y#Foo_Bar") == "Foo_Bar"
    assert A.share(1, 0) is None


def test_shape_stats_and_vacuity():
    sg = G(PFX + """ex:S a sh:NodeShape ; sh:targetClass ex:Sensor ; sh:property [ sh:path ex:a ; sh:minCount 0 ; sh:nodeKind sh:IRI ] ,
      [ sh:path ex:b ; sh:minCount 1 ; sh:datatype xsd:string ] .""")
    s = A.shape_stats(sg)
    assert s["minCount_0"] == 1 and s["minCount_ge1"] == 1 and s["datatype"] == 1 and s["nodeKind"] == 1
    assert s["shapes_with_explicit_target"] == 1
    only0 = G(PFX + "ex:S a sh:NodeShape ; sh:property [ sh:path ex:a ; sh:minCount 0 ] .")
    assert A.shape_stats(only0)["non_vacuous_constraints"] is False


def test_scope_counts_subclass_instances_and_zero_for_foreign_iris():
    o = off()
    sg = G(PFX + "ex:S a sh:NodeShape ; sh:targetClass ex:Sensor .")
    d = G(PFX + "ct:x a ex:TempSensor . ct:y a ct:Class_artifact . ct:z a ex:Room .")
    s = A.scope(d, sg, [o.g])
    assert s["distinct_focus_nodes"] == 1 and s["shapes_with_focus_nodes"] == 1
    d2 = G(PFX + "ct:y a ct:Class_artifact .")
    assert A.scope(d2, sg, [o.g])["distinct_focus_nodes"] == 0


def test_validate_external_ignores_ontology_nodes_and_reports_top():
    o = off()
    sg = G(PFX + "ex:S a sh:NodeShape ; sh:targetClass ex:Sensor ; sh:property [ sh:path ex:hasName ; sh:minCount 1 ] .")
    d = G(PFX + "ct:x a ex:TempSensor .")
    r = A.validate_external(d, sg, o.g, timeout_s=60)
    assert r["violations"] == 1 and r["conforms_data_nodes_only"] is False
    assert r["top_constraints"][0]["component"] == "MinCountConstraintComponent"
    # the ontology's own Sensor class node is not a data node -> its results (if any) are ignored, not counted
    d0 = G(PFX + "ct:y a ct:Class_artifact .")
    assert A.validate_external(d0, sg, o.g, timeout_s=60)["violations"] == 0


def test_official_domain_range_and_union():
    o = off()
    E = Namespace("http://ex.org/o#")
    assert o.dom_rng(E.feeds, "domain")[0] == {E.Sensor}
    assert o.dom_rng(E.uni, "domain")[0] == {E.Room, E.Sensor}
    assert o.dom_rng(E.free, "domain") == (set(), "none")


def test_compat_categories():
    o = off()
    E = Namespace("http://ex.org/o#")
    D = {E.Sensor}
    assert A.compat(E.Sensor, D, o) == "exact"
    assert A.compat(E.TempSensor, D, o) == "subclass"
    assert A.compat(E.Thingy, D, o) == "broader"
    assert A.compat(E.Room, D, o) == "mismatch"
    assert A.compat(URIRef("http://example.org/chunktograph#Class_artifact"), D, o, lambda c: None) == "noncomparable"
    assert A.compat(OWL.Thing, D, o) == "broader"
    assert A.compat(E.Room, set(), o) == "official_undeclared"
    assert A.compat(URIRef("http://www.w3.org/2001/XMLSchema#string"), {URIRef("http://www.w3.org/2001/XMLSchema#string")}, o) == "exact"
    assert A.compat(URIRef("http://www.w3.org/2001/XMLSchema#int"), {RDFS.Literal}, o) == "subclass"
    assert A.compat(E.Room, {URIRef("http://www.w3.org/2001/XMLSchema#string")}, o) == "mismatch"


def test_mapping_levels():
    o = off()
    E = Namespace("http://ex.org/o#")
    g = G(PFX + 'ct:p_feed a owl:ObjectProperty ; rdfs:label "feed" . ct:p_zzz a owl:ObjectProperty ; rdfs:label "zzz" . '
                'ct:p_link a owl:ObjectProperty ; rdfs:label "link" . ct:p_dct a owl:ObjectProperty ; rdfs:label "dctlike" .')
    ct = Namespace("http://example.org/chunktograph#")
    assert A.map_property(ct.p_feed, g, o, {}) == ("localname", E.feeds)
    assert A.map_property(ct.p_zzz, g, o, {}) == ("unmapped", None)
    assert A.map_property(ct.p_link, g, o, {"link": str(E.hasName)}) == ("alignment", E.hasName)
    assert A.map_property(ct.p_dct, g, o, {"dctlike": "http://purl.org/dc/terms/hasPart"}) == ("aligned_nondomain", None)
    assert A.map_property(E.feeds, g, o, {}) == ("exact_iri", E.feeds)


def test_step2_declared_usage_and_mfc():
    o = off()
    g = G(PFX + """ct:Class_artifact a owl:Class . ct:Class_process a owl:Class .
    ct:p_feed a owl:ObjectProperty ; rdfs:label "feed" ; rdfs:domain ct:Class_artifact ; rdfs:range ct:Class_artifact .
    ct:p_other a owl:ObjectProperty ; rdfs:label "other" ; rdfs:domain ct:Class_artifact ; rdfs:range ct:Class_process .
    ct:ex-sensor a ct:Class_artifact, skos:Concept ; skos:prefLabel "ex sensor" ; ct:p_feed ct:ex-room .
    ct:ex-room a ct:Class_artifact, skos:Concept ; skos:prefLabel "room" .
    ct:ex-temp-sensor a ct:Class_artifact, skos:Concept ; ct:p_feed ct:ex-sensor .""")
    r = A.step2(g, o, {})
    assert r["mapping_levels"]["localname"] == 1 and r["n_mapped"] == 1
    assert r["declared_domain"] == {"noncomparable": 1}
    assert r["usage_subject"] == {"compatible": 2}      # ex sensor (word dropped), ex-temp-sensor -> ex:Sensor? see below
    assert r["share_domain_is_most_frequent_declared_domain"] == 1.0
    assert r["most_frequent_entity_class_share_of_typed_entities"] == 1.0
    assert r["usage_object"]["compatible"] == 1 and r["usage_object"]["incompatible"] == 1


def test_provenance_coverage_and_spotcheck_seeded():
    g = G(PFX + """ct:boiler1 a skos:Concept ; skos:prefLabel "boiler" ; prov:wasDerivedFrom ct:chunk_c1, ct:chunk_c2 ; ct:p ct:b .
    ct:b a skos:Concept ; skos:prefLabel "valve" ; dct:source "c3" . ct:d a skos:Concept ; skos:prefLabel "pump" .""")
    r = A.prov_coverage(g, {"c1", "c2", "c3", "c4"})
    assert r["concepts"] == 3 and r["concepts_with_prov"] == 1 and r["concepts_with_source_but_no_prov"] == 1
    assert r["chunks_referenced"] == 2 and r["share_chunks_referenced"] == 0.5
    assert r["links_per_linked_concept_mean"] == 2
    chunks = {"c1": "The Boiler heats water.", "c2": "A pump moves water."}
    s = A.spot_check(g, chunks, "", n=30)
    assert s["sampled"] == 2 and s["strict_contained"] == 1 and s["strict_share"] == 0.5
    assert A.spot_check(g, chunks, "", n=1)["sample"] == A.spot_check(g, chunks, "", n=1)["sample"]
    assert "sample" not in A.spot_check(g, chunks, "", with_ids=False)


def test_loose_reading_any_order():
    g = G(PFX + 'ct:ahu1 a skos:Concept ; skos:prefLabel "air handler unit" ; prov:wasDerivedFrom ct:chunk_c1 .')
    s = A.spot_check(g, {"c1": "The unit for the handler of air."}, "")
    assert s["strict_contained"] == 0 and s["loose_contained"] == 1


def test_stem_sensitivity_only_when_enabled():
    o = off()
    ct = Namespace("http://example.org/chunktograph#")
    g = G(PFX + 'ct:p_feeding a owl:ObjectProperty ; rdfs:label "feeding" .')
    assert A.map_property(ct.p_feeding, g, o, {})[0] == "unmapped"
    assert A.map_property(ct.p_feeding, g, o, {}, use_stem=True)[0] == "stem"


def test_scope_constraint_bearing_vs_rule_only():
    o = off()
    sg = G(PFX + """ex:R a sh:NodeShape ; sh:targetClass ex:Sensor ; sh:rule [ a sh:TripleRule ] .
    ex:S a sh:NodeShape ; sh:targetClass ex:Room ; sh:property [ sh:path ex:x ; sh:minCount 1 ] .""")
    d = G(PFX + "ct:x a ex:Sensor . ct:y a ex:Room . ct:w a ex:Room .")
    s = A.scope(d, sg, [o.g])
    assert s["shapes_with_focus_nodes"] == 2 and s["constraint_shapes_with_focus_nodes"] == 1
    assert s["constraint_distinct_focus_nodes"] == 2 and s["distinct_focus_nodes"] == 3


def test_clean_shapes_removes_dangling_property_refs():
    sg = G(PFX + "ex:S a sh:NodeShape ; sh:property ex:ok, ex:gone . ex:ok sh:path ex:p ; sh:minCount 1 .")
    c, n = A.clean_shapes(sg)
    assert n == 1 and (URIRef("http://ex.org/o#S"), A.SH.property, URIRef("http://ex.org/o#gone")) not in c
    assert (URIRef("http://ex.org/o#S"), A.SH.property, URIRef("http://ex.org/o#ok")) in c
