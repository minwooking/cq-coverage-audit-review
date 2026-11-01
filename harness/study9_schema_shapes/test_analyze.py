"""Tests for study 9 on synthetic graphs (known violations must be caught). AI-generated; review before reuse."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze as a
from rdflib import Graph, Literal, URIRef, RDF, RDFS, OWL, Namespace
from rdflib.namespace import XSD

EX = Namespace("http://ex.org/")
ONT = """
@prefix ex: <http://ex.org/> . @prefix owl: <http://www.w3.org/2002/07/owl#> . @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
ex:Sensor a owl:Class . ex:TempSensor a owl:Class ; rdfs:subClassOf ex:Sensor, [ a owl:Restriction ; owl:onProperty ex:hasUnit ; owl:minCardinality 1 ] .
ex:Room a owl:Class . ex:Unit a owl:Class . ex:Other a owl:Class .
ex:isIn a owl:ObjectProperty ; rdfs:domain ex:Sensor ; rdfs:range ex:Room .
ex:hasUnit a owl:ObjectProperty ; rdfs:domain ex:TempSensor ; rdfs:range ex:Unit .
ex:serial a owl:DatatypeProperty ; rdfs:domain ex:Sensor ; rdfs:range xsd:integer .
"""


def official(tmp):
    f = Path(tmp) / "o.ttl"
    f.write_text(ONT)
    return a.OfficialIndex([f], "")


def run_off(oi, data_ttl, refs):
    g = Graph().parse(data=data_ttl, format="turtle")
    sg, st = a.gen_official_shapes(oi, refs)
    l1 = a.make_l1(g, oi.off)
    orig = {x for t in g for x in t if not isinstance(x, Literal)}
    sc = a.s8.scope(l1, sg, [oi.off.g])
    r = a.run_shacl(l1, sg, orig)
    return a.summarise(r, sc, len(g), False), st


PRE = "@prefix ex: <http://ex.org/> . @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"


def test_generation_counts():
    with tempfile.TemporaryDirectory() as t:
        oi = official(t)
        sg, st = a.gen_official_shapes(oi, {EX.TempSensor: "R1", EX.Sensor: "R1", EX.Other: "R2"})
        assert st["node_shapes"] == 2          # Other has no properties
        assert st["minCount_ge1"] == 1         # hasUnit required on TempSensor only
        assert st["sh_class"] == 2 and st["sh_datatype"] == 1


def test_known_violations_caught():
    with tempfile.TemporaryDirectory() as t:
        oi = official(t)
        refs = {EX.TempSensor: "R1", EX.Sensor: "R1"}
        data = PRE + """
        ex:s1 a ex:TempSensor ; ex:isIn ex:r1 ; ex:hasUnit ex:u1 ; ex:serial 5 .
        ex:r1 a ex:Room . ex:u1 a ex:Unit .
        ex:s2 a ex:TempSensor ; ex:isIn ex:r2 ; ex:hasUnit ex:u1 .
        ex:r2 a ex:Other .
        ex:s3 a ex:TempSensor ; ex:serial "abc" ; ex:hasUnit ex:u1 .
        ex:s4 a ex:TempSensor .
        """
        out, _ = run_off(oi, data, refs)
        assert out["focus_nodes"] == 4
        assert out["verdict"] == "fail"
        comps = {c["component"] for c in out["top_constraints"]}
        assert {"ClassConstraintComponent", "DatatypeConstraintComponent", "MinCountConstraintComponent"} <= comps
        assert out["violations"] == 3          # s2 range, s3 datatype, s4 minCount


def test_pass_and_vacuous():
    with tempfile.TemporaryDirectory() as t:
        oi = official(t)
        refs = {EX.TempSensor: "R1", EX.Sensor: "R1"}
        ok, _ = run_off(oi, PRE + "ex:s1 a ex:TempSensor ; ex:hasUnit ex:u1 ; ex:isIn ex:r1 . ex:u1 a ex:Unit . ex:r1 a ex:Room .", refs)
        assert ok["verdict"] == "pass" and ok["focus_nodes"] == 1
        vac, _ = run_off(oi, PRE + "ex:z a ex:Foo ; ex:isIn ex:r1 .", refs)
        assert vac["verdict"] == "NA (vacuous)" and vac["violations"] == 0


def test_referenced_classes_levels():
    with tempfile.TemporaryDirectory() as t:
        oi = official(t)
        g = Graph().parse(data=PRE + """@prefix owl: <http://www.w3.org/2002/07/owl#> . @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
        ex:x a skos:Concept ; skos:prefLabel "Room" . <http://other.org/c> a skos:Concept ; skos:prefLabel "Unit" .
        ex:y ex:isIn ex:Sensor .""", format="turtle")
        refs = a.referenced_classes(g, oi.off)
        assert refs[EX.Sensor] == "R1" and refs[EX.Room] == "R2" and refs[EX.Unit] == "R2"


def test_internal_domain_range_datatype_and_na():
    ttl = PRE + """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    ex:p rdfs:domain ex:D ; rdfs:range ex:R . ex:q rdfs:domain ex:D ; rdfs:range xsd:integer . ex:unused rdfs:domain ex:D .
    ex:E rdfs:subClassOf ex:D .
    ex:a a ex:D ; ex:p ex:r ; ex:q 3 . ex:r a ex:R .
    ex:b a ex:E ; ex:p ex:r .
    ex:c a ex:X ; ex:p ex:r .
    ex:d a ex:D ; ex:p ex:w ; ex:q "no" . ex:w a ex:X .
    ex:e ex:p ex:r .
    """
    g = Graph().parse(data=ttl, format="turtle")
    rec, sg, run = a.validate_internal = a.validate_variant_internal(g, True, len(g))
    assert rec["focus_nodes"] == 5
    assert rec["verdict"] == "fail"
    # c: wrong domain; e: untyped subject; d: wrong range class + wrong datatype  -> 4
    assert rec["violations"] == 4
    cl = a.classify_internal(g, run["results"])["by_kind"]
    assert cl["domain_wrong_typed_subject"] == 1 and cl["domain_untyped_subject"] == 1
    assert cl["range_wrong_typed_object"] == 1 and cl["range_wrong_datatype_or_kind"] == 1


def test_internal_vacuous_when_no_declared_use():
    g = Graph().parse(data=PRE + "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . ex:p rdfs:domain ex:D . ex:a ex:other ex:b .", format="turtle")
    rec, _, _ = a.validate_variant_internal(g, True, len(g))
    assert rec["verdict"] == "NA (vacuous)"


def test_verdict_rule():
    assert a.verdict(0, 0) == "NA (vacuous)" and a.verdict(3, 0) == "pass" and a.verdict(3, 1) == "fail"
    assert a.verdict(3, 0, "x") == "error"
