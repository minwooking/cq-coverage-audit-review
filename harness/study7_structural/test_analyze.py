import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from rdflib import Graph
import analyze

TTL = """
@prefix ex: <http://example.org/> . @prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> . @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
ex:C1 a owl:Class . ex:C2 a owl:Class .
ex:p1 a owl:ObjectProperty ; rdfs:domain ex:C1 ; rdfs:range ex:C2 .
ex:p2 a owl:ObjectProperty ; rdfs:domain ex:C1 .
ex:p3 a owl:DatatypeProperty .
ex:i1 a ex:C1, owl:NamedIndividual ; skos:broader ex:i2 ; prov:wasDerivedFrom ex:chunk1, ex:chunk2 .
ex:i2 a ex:C2 ; prov:wasGeneratedBy ex:act .
"""

def test_structural():
    r = analyze.structural(Graph().parse(data=TTL, format="turtle"))
    assert r["classes"] == 2
    assert r["properties"] == 3
    assert r["props_with_domain_and_range"] == 1
    assert abs(r["domain_range_share"] - 1 / 3) < 1e-9
    assert r["skos_broader"] == 1
    assert r["entity_type_statements"] == 2 and r["typed_entities"] == 2
    assert r["prov_links"] == 3 and r["prov_wasDerivedFrom"] == 2 and r["prov_wasGeneratedBy"] == 1

def test_validity_skipped():
    assert analyze.validity(Graph(), run=False)["shacl_conforms"] is None
