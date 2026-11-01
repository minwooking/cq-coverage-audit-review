import csv
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import build_expert_quality_packets as B  # noqa: E402

TTL_A = """@prefix ex: <http://example.org/chunktograph#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
ex:Room a owl:Class ; rdfs:label "Room" ; owl:definition "A space" .
ex:Office a owl:Class ; rdfs:label "Office" ; rdfs:subClassOf ex:Room .
ex:hasPart a owl:ObjectProperty ; rdfs:domain ex:Room ; rdfs:range ex:Office .
ex:Room ex:hasPart ex:Office .
"""
TTL_E = """@prefix ct: <http://example.org/chunktograph#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
ct:room a skos:Concept ; skos:prefLabel "room" ; prov:wasGeneratedBy ct:buildrun_%s .
ct:office a skos:Concept ; skos:prefLabel "office" ; skos:broader ct:room ; ct:p_in ct:room ; prov:wasGeneratedBy ct:buildrun_%s .
"""


class Builder(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        (t / "gA.ttl").write_text(TTL_A)
        (t / "gE.ttl").write_text(TTL_E % ("E", "E"))
        (t / "gF.ttl").write_text(TTL_E % ("F", "F"))
        cfg = {"task_statement": "Reuse as a small domain ontology.", "artifacts": [
            {"set": "s1", "variant": "A", "graph": "gA.ttl"},
            {"set": "s1", "variant": "E", "graph": "gE.ttl"},
            {"set": "s1", "variant": "F", "graph": "gF.ttl"}]}
        (t / "cfg.json").write_text(json.dumps(cfg))
        self.cfg, self.out, self.keys = t / "cfg.json", t / "out", t / "keys"
        self.sizes = dict(n_concepts=5, n_props=5, n_stmts=5, tree_roots=3, tree_depth=2, tree_children=4)

    def tearDown(self):
        self.tmp.cleanup()

    def test_merge_identical_and_blinding(self):
        m = B.build(self.cfg, ["R1", "R2"], "seed", self.out, self.keys, False, None, self.sizes, True, None)
        self.assertEqual(len(m["units"]), 2)  # A and E+F
        self.assertIn("E+F", [u["variant"] for u in m["units"]])
        for rid in ("R1", "R2"):
            blob = ""
            for f in (self.out / rid).rglob("*"):
                if f.is_file():
                    blob += f.name + "\n" + f.read_text()
            self.assertEqual(B.leak_hits(blob), [])
            self.assertNotRegex(blob, r"buildrun_[A-Z]\b")
            self.assertNotIn("ontology_", blob)
        k1 = list(csv.DictReader(open(self.keys / "key_R1.csv")))
        k2 = list(csv.DictReader(open(self.keys / "key_R2.csv")))
        self.assertTrue({r["artifact_id"] for r in k1}.isdisjoint({r["artifact_id"] for r in k2}))
        self.assertEqual({r["variant"] for r in k1}, {"A", "E+F"})

    def test_keep_duplicates(self):
        m = B.build(self.cfg, ["R1"], "seed", self.out, self.keys, True, None, self.sizes, False, None)
        self.assertEqual(len(m["units"]), 3)
        k = list(csv.DictReader(open(self.keys / "key_R1.csv")))
        self.assertEqual(len({r["group_id"] for r in k}), 2)

    def test_same_dossier_for_all_raters(self):
        B.build(self.cfg, ["R1", "R2"], "seed", self.out, self.keys, False, None, self.sizes, False, None)
        def bodies(r):
            return sorted(re.sub(r"Review material \w+", "", f.read_text()) for f in (self.out / r / "materials").glob("*.md"))
        self.assertEqual(bodies("R1"), bodies("R2"))

    def test_reproducible_with_same_seed(self):
        def bodies(out, keys):
            B.build(self.cfg, ["R1"], "seed", out, keys, False, None, self.sizes, False, None)
            return sorted(re.sub(r"Review material \w+", "", f.read_text()) for f in (out / "R1" / "materials").glob("*.md"))
        t = Path(self.tmp.name)
        self.assertEqual(bodies(t / "o1", t / "k1"), bodies(t / "o2", t / "k2"))

    def test_no_forbidden_columns(self):
        B.build(self.cfg, ["R1"], "seed", self.out, self.keys, False, None, self.sizes, False, None)
        head = open(self.out / "R1" / "rating_sheet_R1.csv").readline()
        for bad in ("variant", "coverage", "J_", "set"):
            self.assertNotIn(bad, head)

    def test_leak_scan(self):
        self.assertTrue(B.leak_hits("see graph_B.ttl"))
        self.assertTrue(B.leak_hits("prov:wasGeneratedBy ct:buildrun_F"))
        self.assertEqual(B.leak_hits("a normal sentence about rooms"), [])


if __name__ == "__main__":
    unittest.main()
