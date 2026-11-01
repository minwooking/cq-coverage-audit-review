"""Correct CQ bank groundings against the frozen Brick v1.4.4 snapshot.
Every replacement below was verified with rdflib against
paper/access2026/data/brick-v1.4.4.ttl before being written.
"""
import csv
from collections import Counter

BASE = "bank/"

FIX = {
    "CQB01": ("What is a brick:Sensor?", "skos:definition brick:Sensor",
              "An input point representing the value of a device/instrument designed to detect and "
              "measure a variable (ASHRAE Dictionary); subclass of brick:Point.",
              "candidate (REPLACED: brick:Point carries no definition in v1.4.4)"),
    "CQB02": ("What does brick:Meter represent?", "skos:definition brick:Meter + rdfs:subClassOf",
              "A device that measures usage or consumption of some media, typically a form of energy "
              "or power; rdfs:subClassOf brick:Equipment.",
              "candidate (expected text aligned to snapshot wording)"),
    "CQB03": ("What is a rec:Asset?", "rdfs:comment rec:Asset",
              "Something placed inside a building but not an integral part of that building's "
              "structure; e.g. furniture, equipment, systems.",
              "candidate (namespace corrected: rec:, not brick:)"),
    "CQB04": ("What is a brick:Zone?", "skos:definition brick:Zone",
              "(1) a separately controlled heated or cooled space; (2) one or several occupied spaces "
              "with similar occupancy category, occupant density, air distribution effectiveness and "
              "primary airflow per unit area.",
              "candidate (expected text aligned to snapshot wording)"),
    "CQB05": ("What is a rec:Campus?", "rdfs:comment rec:Campus",
              "A collection of location entities that may differ in legal ownership and purpose but "
              "are perceived as a coherent unit or sub-region within a city/region.",
              "candidate (namespace corrected: rec:)"),
    "CQB06": ("What does rec:Georeference express?", "rdfs:comment rec:Georeference",
              "A relationship created between a local coordinate system and a geographic coordinate system.",
              "candidate (namespace corrected: rec:)"),
    "CQB10": ("Is brick:Building a direct subclass of brick:Location?", "rdfs:subClassOf brick:Building",
              "Yes; brick:Building rdfs:subClassOf brick:Location directly (not routed via Space).",
              "candidate (verified: single direct parent Location)"),
    "CQB17": ("Which property expresses spatial containment of an entity in a location?",
              "rec:locatedIn (sh:path)",
              "rec:locatedIn, used in SHACL property shapes; the Brick-namespace counterpart is "
              "brick:hasLocation / brick:isLocationOf.",
              "candidate (CORRECTED: brick:locatedIn does not exist in the snapshot)"),
    "CQB25": ("Which entities does the rec:BuildingElement definition list as examples?",
              "rdfs:comment rec:BuildingElement", "Facade, Wall, Slab, Roof.",
              "candidate (namespace corrected: rec:)"),
    "CQB26": ("Which events does the rec:Event definition give as examples?", "rdfs:comment rec:Event",
              "An observation, a lease, a construction project; may be instantaneous or have temporal extent.",
              "candidate (namespace corrected: rec:)"),
    "CQB27": ("What does rec:PointEvent exemplify?", "rdfs:comment rec:PointEvent",
              "An event emanating from or targeting a Point; e.g. an individual Observation from a "
              "Sensor point, or an Actuation sent to a Command point.",
              "candidate (CORRECTED: snapshot says Actuation to a Command point)"),
    "CQB28": ("What organizations does the rec:Organization definition cite?", "rdfs:comment rec:Organization",
              "A business, association, project, consortium, tribe.",
              "candidate (namespace corrected: rec:)"),
    "CQB29": ("What containment example does the rec:Space definition give?", "rdfs:comment rec:Space",
              "A Region can contain many Sites, which in turn can contain many Buildings.",
              "candidate (CORRECTED: earlier draft invented a security-zone example)"),
    "CQB30": ("What does the rec:Portfolio definition list as groupable members?", "rdfs:comment rec:Portfolio",
              "Buildings, sites, apartments, campuses sharing a business-relevant commonality (same "
              "manager, same tenant, shared utilization or legal definition).",
              "candidate (namespace corrected: rec:)"),
    "CQB31": ("How does the schema advise handling rec:ArchitectureArea measurements?",
              "rdfs:comment rec:ArchitectureArea",
              "Requirements vary case to case and jurisdiction to jurisdiction, so subclassing and "
              "specializing the definition is encouraged.",
              "candidate (namespace corrected: rec:)"),
    "CQB34": ("When should a rec:Collection be used?", "rdfs:comment rec:Collection",
              "For an administrative grouping of entities addressed and treated as a unit; spatial "
              "contiguity is possible but not required (e.g. a distributed campus).",
              "candidate (namespace corrected: rec:)"),
    "CQB36": ("Which property links a Brick entity to an external vocabulary reference?",
              "ref:hasExternalReference / brick:hasQUDTReference",
              "ref:hasExternalReference (Brick/ref# namespace) for BACnet/IFC references; "
              "brick:hasQUDTReference for QUDT units.",
              "candidate (CORRECTED: brick:hasExternalReference does not exist)"),
}


def main() -> None:
    rows = list(csv.reader(open(BASE + "cq_bank_brick_v0.csv")))
    header, body = rows[0], rows[1:]
    fixed = 0
    for row in body:
        if row[0] in FIX:
            row[2], row[3], row[4], row[5] = FIX[row[0]]
            fixed += 1
    with open(BASE + "cq_bank_brick_v1.csv", "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(body)
    print("rows corrected:", fixed, "of", len(body))
    print(Counter(row[1] for row in body))


if __name__ == "__main__":
    main()
