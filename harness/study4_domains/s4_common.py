"""Shared constants for addendum 35 (study4_domains).  AI-generated; review and test before reuse.  No network, no model."""
from __future__ import annotations

import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
REPO = ACCESS.parent.parent
SEED = 20260913
BOOT_B = 10_000

# license: how the source states it; redistribute = may corpus text / graphs / views be committed (see PLAN.md 35.2)
DOMAINS = {
    "dcat": {
        "title": "DCAT 3 (W3C Data Catalog Vocabulary)",
        "docs": [("dcat3-rec", "https://www.w3.org/TR/vocab-dcat-3/")],
        "ontology": [("dcat.ttl", "https://www.w3.org/ns/dcat.ttl", "text/turtle")],
        "license_docs": "W3C permissive document license (W3C Software and Document Notice and License 2023)",
        "license_ontology": "CC BY 4.0 (dcterms:license in dcat.ttl)",
        "redistribute": True,
        "prefixes": {"dcat": "http://www.w3.org/ns/dcat#", "dcterms": "http://purl.org/dc/terms/",
                     "prov": "http://www.w3.org/ns/prov#", "odrl": "http://www.w3.org/ns/odrl/2/"},
    },
    "ssn": {
        "title": "SOSA/SSN (W3C/OGC Semantic Sensor Network Ontology)",
        "docs": [("ssn-rec", "https://www.w3.org/TR/vocab-ssn/")],
        "ontology": [("sosa.ttl", "https://www.w3.org/ns/sosa/", "text/turtle"),
                     ("ssn.ttl", "https://www.w3.org/ns/ssn/", "text/turtle")],
        "license_docs": "W3C/OGC document use license (copying with notice; no derivative works)",
        "license_ontology": "W3C Software and Document License 2015 + OGC Software license (dcterms:license in the files)",
        "redistribute": False,
        "prefixes": {"sosa": "http://www.w3.org/ns/sosa/", "ssn": "http://www.w3.org/ns/ssn/",
                     "ssn-system": "http://www.w3.org/ns/ssn/systems/"},
    },
    "prov": {
        "title": "PROV (W3C PROV-O and PROV-DM)",
        "docs": [("prov-o", "https://www.w3.org/TR/prov-o/"), ("prov-dm", "https://www.w3.org/TR/prov-dm/")],
        "ontology": [("prov.ttl", "https://www.w3.org/ns/prov.ttl", "text/turtle")],
        "license_docs": "W3C document use license (copying with notice; no derivative works)",
        "license_ontology": "no license statement in the file; W3C document/software notice of the namespace",
        "redistribute": False,
        "prefixes": {"prov": "http://www.w3.org/ns/prov#"},
    },
}
UA = "study4-fetch/1.0 (research; plain GET)"


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def ddir(d: str) -> Path:
    p = HERE / d
    p.mkdir(exist_ok=True)
    return p
