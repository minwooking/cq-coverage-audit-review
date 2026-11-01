#!/usr/bin/env python3
"""Build and machine-screen the DRAFT expansion bank (Brick v1.4.4), 84 questions.

AI-GENERATED CODE AND DATA.  Written 2026-10-13 by an AI assistant.  No human has
reviewed it.  Review and test before any freeze; do not apply unreviewed.

Artifact-blind: this script reads ONLY
  * data/brick-v1.4.4.ttl            (the frozen snapshot, sha256 pinned below)
  * bank/cq_bank_brick_v2.csv        (question text + grounding of the 60 existing
                                      rows, used only for the duplicate check)
It never opens variants/, graph_*.ttl, rendered views, judge cells, labels or any
length-experiment input.  No judge call is made.

What it does
  1. Builds the 84 draft rows from SPEC (answers and ASK queries are generated from
     the snapshot, not typed from memory) and writes the CSV plus ask_queries/*.rq.
  2. Runs the three machine channels of the bank's screen:
       (1) format     -- columns, id pattern, category, question form, query file
       (2) grounding  -- every brick:/rec:/ref: term occurs in the snapshot (rdflib);
                         every "definition claim" has a non-empty literal triple
       (3) ASK        -- the row's ASK query evaluates to true on the snapshot
  3. Runs a semantic-duplicate check against CQB01-CQB60 and among the new rows
     (question-token Jaccard and shared primary grounding terms).
Rows that fail any check carry screen_fail=FAIL and a reason in screen_notes.

Usage:  python3 build_and_screen.py            (from any directory)
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import deque
from pathlib import Path

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

HERE = Path(__file__).resolve().parent
ACCESS = HERE.parent.parent
SNAPSHOT = ACCESS / "data" / "brick-v1.4.4.ttl"
EXISTING = ACCESS / "bank" / "cq_bank_brick_v2.csv"  # 60-row pool, text only
OUT_CSV = HERE / "cq_bank_brick_expansion_draft_v1.csv"
OUT_JSON = HERE / "screen_results.json"
QDIR = HERE / "ask_queries"
SNAPSHOT_SHA256 = "b65720b7b9b64c646745c689777e6138c0d59ce0088df0aeb78fbd444d04d8e7"
CREATED = "2026-10-13"
HEADER = (
    "# AI-GENERATED DRAFT (2026-10-13). Written artifact-blind from data/brick-v1.4.4.ttl only. "
    "NOT frozen. author_review=pending on every row: the author must review, edit and freeze "
    "(tag) before any judge call. Delete this comment line when freezing; the CSV then "
    "parses with csv.DictReader."
)

B = Namespace("https://brickschema.org/schema/Brick#")
R = Namespace("https://w3id.org/rec#")
F = Namespace("https://brickschema.org/schema/Brick/ref#")
SH = Namespace("http://www.w3.org/ns/shacl#")
NSMAP = {"brick": B, "rec": R, "ref": F}
CATEGORIES = ("concept_definition", "taxonomy", "relations", "slots_facets", "instances", "methodology")
PREAMBLE = (
    "PREFIX brick: <https://brickschema.org/schema/Brick#>\n"
    "PREFIX rec: <https://w3id.org/rec#>\n"
    "PREFIX ref: <https://brickschema.org/schema/Brick/ref#>\n"
    "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
    "PREFIX skos: <http://www.w3.org/2004/02/skos/core#>\n"
    "PREFIX owl: <http://www.w3.org/2002/07/owl#>\n"
    "PREFIX sh: <http://www.w3.org/ns/shacl#>\n"
    "PREFIX qudt: <http://qudt.org/schema/qudt/>\n\n"
)

g = Graph()
g.parse(SNAPSHOT, format="turtle")


def iri(t: str) -> URIRef:
    p, l = t.split(":")
    return NSMAP[p][l]


def q(u) -> str:
    s = str(u)
    for p, n in NSMAP.items():
        if s.startswith(str(n)):
            return f"{p}:{s[len(str(n)):]}"
    return s


def text(t: str, pred=None) -> str:
    u = iri(t)
    for p in ([pred] if pred else [SKOS.definition, RDFS.comment]):
        v = g.value(u, p)
        if v is not None:
            return str(v).replace("\n", " ").replace("­", "").strip()
    raise KeyError(f"no definition/comment for {t}")


def parents(t: str) -> list[str]:
    return sorted(q(o) for o in g.objects(iri(t), RDFS.subClassOf)
                  if isinstance(o, URIRef) and q(o).split(":")[0] in NSMAP)


def children(t: str) -> list[str]:
    return sorted(q(s) for s in g.subjects(RDFS.subClassOf, iri(t)) if isinstance(s, URIRef))


def local(t: str) -> str:
    return t.split(":", 1)[1]


def chain(a: str, b: str) -> list[str]:
    """Shortest rdfs:subClassOf chain a -> ... -> b (IRIs in brick/rec namespaces)."""
    seen, dq = {a: None}, deque([a])
    while dq:
        x = dq.popleft()
        if x == b:
            out = []
            while x:
                out.append(x)
                x = seen[x]
            return out[::-1]
        for p in parents(x):
            if p not in seen:
                seen[p] = x
                dq.append(p)
    raise ValueError(f"no chain {a}->{b}")


def dep(t: str) -> tuple[str, str, str]:
    u = iri(t)
    return (str(g.value(u, B.deprecatedInVersion)), q(g.value(u, B.isReplacedBy)),
            str(g.value(u, B.deprecationMitigationMessage)))


def shape_info(owner: str, prop: str) -> tuple[str, str]:
    """(sh:class target, sh:description or '') of the property shape on owner."""
    for ps in g.objects(iri(owner), SH.property):
        if (ps, SH.path, iri(prop)) in g:
            tgt = g.value(ps, SH["class"])
            desc = g.value(ps, SH.description)
            return q(tgt), (str(desc).strip() if desc else "")
    raise KeyError(f"no shape {owner} {prop}")


rows: list[dict] = []


def add(category, question, grounding, expected, ask, expressible, key=None):
    rows.append(dict(category=category, question=question, grounding=grounding,
                     expected_answer=expected, ask=ask, ask_expressible=expressible))


def A(body: str) -> str:
    return "ASK { " + body + " }"


# ---------------------------------------------------------------- concept_definition (14)
def cdef(term, question):
    pred = "rdfs:comment" if term.startswith("rec:") else "skos:definition"
    d = text(term, RDFS.comment if term.startswith("rec:") else SKOS.definition)
    ps = parents(term)
    exp = d.rstrip(".") + "." + (f" Subclass of {', '.join(ps)}." if ps else "")
    body = f"{term} {pred} ?d" + "".join(f" . {term} rdfs:subClassOf {p}" for p in ps)
    add("concept_definition", question, f"{pred} {term}", exp, A(body), "partial")


cdef("brick:Variable_Frequency_Drive", "What is a brick:Variable_Frequency_Drive?")
cdef("brick:Heat_Exchanger", "What does brick:Heat_Exchanger represent?")
cdef("brick:Temperature_Sensor", "What does a brick:Temperature_Sensor measure?")
cdef("brick:Luminance_Sensor", "What does a brick:Luminance_Sensor measure?")
cdef("brick:Elevator", "What is a brick:Elevator?")
cdef("brick:Chilled_Water", "What is brick:Chilled_Water?")
cdef("brick:Battery", "What is a brick:Battery?")
cdef("brick:Photovoltaic_Array", "What does brick:Photovoltaic_Array represent?")
cdef("brick:Cooling_Tower", "What is a brick:Cooling_Tower?")
cdef("brick:Occupancy_Sensor", "What does a brick:Occupancy_Sensor detect?")
cdef("brick:Electric_Vehicle_Charging_Station", "What is a brick:Electric_Vehicle_Charging_Station?")
cdef("rec:Site", "What is a rec:Site?")
cdef("rec:Geotransform", "What does rec:Geotransform express?")
cdef("rec:Person", "What is a rec:Person?")

# ---------------------------------------------------------------- taxonomy (14)
def kids(term, question):
    ch = children(term)
    n = len(ch)
    names = ", ".join(local(c) for c in ch[:8])
    exp = f"{n} direct subclasses" + (f": {names}." if n <= 8 else f" incl. {names}.")
    ask = A("{ SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE { ?c rdfs:subClassOf " + term +
            " . FILTER(isIRI(?c)) } } FILTER(?n = " + str(n) + ")")
    add("taxonomy", question, f"rdfs:subClassOf {term}", exp, ask, "yes")


kids("brick:Pump", "Which direct subclasses does brick:Pump have?")
kids("brick:Tank", "Which direct subclasses does brick:Tank have?")
kids("brick:Humidity_Sensor", "Which direct subclasses does brick:Humidity_Sensor have?")
kids("brick:Terminal_Unit", "Which direct subclasses does brick:Terminal_Unit have?")
kids("rec:Zone", "Which direct subclasses does rec:Zone have?")
kids("rec:ICTEquipment", "Which direct subclasses does rec:ICTEquipment have?")


def parent_q(term, question):
    ps = parents(term)
    exp = "Direct superclass" + ("es" if len(ps) > 1 else "") + ": " + " and ".join(ps) + "."
    body = " . ".join(f"{term} rdfs:subClassOf {p}" for p in ps)
    body += f" . FILTER NOT EXISTS {{ {term} rdfs:subClassOf ?o . FILTER(isIRI(?o) && ?o NOT IN (" + \
        ", ".join(ps) + ")) }"
    add("taxonomy", question, f"rdfs:subClassOf {term}", exp, A(body), "yes")


parent_q("brick:Thermostat", "Which classes is brick:Thermostat a direct subclass of?")
parent_q("brick:Rooftop_Unit", "What is the direct superclass of brick:Rooftop_Unit?")
parent_q("rec:Level", "What is the direct superclass of rec:Level?")

add("taxonomy", "Is brick:Electrical_Meter a direct subclass of brick:Meter?",
    "rdfs:subClassOf brick:Electrical_Meter brick:Meter",
    "Yes. brick:Electrical_Meter is a direct subclass of brick:Meter.",
    A("brick:Electrical_Meter rdfs:subClassOf brick:Meter"), "yes")
add("taxonomy", "Is brick:VAV a direct subclass of brick:HVAC_Equipment?",
    "rdfs:subClassOf brick:VAV brick:Terminal_Unit brick:HVAC_Equipment",
    "No. brick:VAV is a direct subclass of brick:Terminal_Unit, which is the direct subclass of "
    "brick:HVAC_Equipment, so VAV is only a transitive subclass.",
    A("brick:VAV rdfs:subClassOf brick:Terminal_Unit . brick:Terminal_Unit rdfs:subClassOf brick:HVAC_Equipment . "
      "FILTER NOT EXISTS { brick:VAV rdfs:subClassOf brick:HVAC_Equipment }"), "yes")
_c = chain("brick:Supply_Air_Temperature_Sensor", "brick:Sensor")
add("taxonomy", "Is brick:Supply_Air_Temperature_Sensor a subclass of brick:Sensor, directly or through other classes?",
    "rdfs:subClassOf brick:Supply_Air_Temperature_Sensor brick:Sensor",
    "Yes, through the chain " + " -> ".join(_c) + ".",
    A("brick:Supply_Air_Temperature_Sensor rdfs:subClassOf+ brick:Sensor"), "yes")
add("taxonomy", "Are brick:Fan and brick:Pump both direct subclasses of the same class?",
    "rdfs:subClassOf brick:Fan brick:Pump brick:HVAC_Equipment",
    "Yes. Both are direct subclasses of brick:HVAC_Equipment.",
    A("brick:Fan rdfs:subClassOf brick:HVAC_Equipment . brick:Pump rdfs:subClassOf brick:HVAC_Equipment"), "yes")
add("taxonomy", "Are brick:Parameter and brick:Status disjoint in Brick?",
    "brick:Parameter brick:Status",
    "Yes. The snapshot declares brick:Parameter and brick:Status owl:disjointWith each other.",
    A("{ brick:Parameter owl:disjointWith brick:Status } UNION { brick:Status owl:disjointWith brick:Parameter }"), "yes")

# ---------------------------------------------------------------- relations (14)
def rel(question, owner, prop, tail=""):
    tgt, desc = shape_info(owner, prop)
    exp = f"{prop} (a property shape on {owner} with sh:class {tgt})." + (f" Shape description: {desc}" if desc else "")
    exp += tail
    add("relations", question, f"sh:path {prop}", exp,
        A(f"{owner} sh:property ?ps . ?ps sh:path {prop} ; sh:class {tgt}"), "yes")


rel("Which property records the agent that manufactured an Asset?", "rec:Asset", "rec:manufacturedBy")
rel("Which property records the agent that installed an Asset?", "rec:Asset", "rec:installedBy")
rel("Which property links an Asset to the building element it is mounted on?", "rec:Asset", "rec:mountedOn")
rel("Which property records the agent that architected an Architecture entity?", "rec:Architecture", "rec:architectedBy")
rel("Which property links an Architecture entity to the building elements it contains?", "rec:Architecture", "rec:containsElement")
rel("Which property lists the agents that belong to an Organization?", "rec:Organization", "rec:hasMember")
rel("Which property names the agent that leases a leasable object?", "rec:Lease", "rec:leasee")
rel("Which property names the agent that leases out an object?", "rec:Lease", "rec:leasor")
rel("Which property links an Architecture entity to its postal address?", "rec:Architecture", "rec:address")
rel("Which property attaches a Document to an Asset as documentation?", "rec:Asset", "rec:documentation")
rel("Which property records the agent that operates an Architecture entity?", "rec:Architecture", "rec:operatedBy")
rel("Which property links a Space to its geometry?", "rec:Space", "rec:geometry")
rel("Which property links a Meter to the Substance it meters?", "brick:Meter", "brick:hasSubstance")
rel("Which property declares that one Brick entity is an alias of another?", "brick:Entity", "brick:aliasOf")

# ---------------------------------------------------------------- slots_facets (14)
def slot(term, question):
    d = text(term, SKOS.definition)
    add("slots_facets", question, f"skos:definition {term}", f"{term}: " + d.rstrip(".") + ".",
        A(f"{term} skos:definition ?d . {term} a brick:EntityProperty"), "partial")


slot("brick:area", "Which property records the two-dimensional area of an entity?")
slot("brick:azimuth", "What does brick:azimuth record?")
slot("brick:tilt", "Which property records the direction an entity faces above the horizon?")
slot("brick:volume", "What does brick:volume record?")
slot("brick:netArea", "What does brick:netArea record?")
slot("brick:panelArea", "What does brick:panelArea record?")
slot("brick:electricalPhases", "Which property records the electrical AC phases of an entity?")
slot("brick:operationalStageCount", "What does brick:operationalStageCount record?")
slot("brick:thermalTransmittance", "What does brick:thermalTransmittance record?")
slot("brick:conversionEfficiency", "Which property records the percent efficiency of a conversion process?")
slot("brick:ratedPowerOutput", "What does brick:ratedPowerOutput record?")
slot("brick:ratedVoltageInput", "Which property records the nominal rated voltage input of an entity?")
slot("brick:electricVehicleChargerType", "What does brick:electricVehicleChargerType identify?")
slot("brick:currentFlowType", "What does brick:currentFlowType record?")

# ---------------------------------------------------------------- instances (14)
def inst(term, question, key):
    pred = SKOS.definition if term.startswith("brick:") else RDFS.comment
    pn = "skos:definition" if term.startswith("brick:") else "rdfs:comment"
    d = text(term, pred)
    add("instances", question, f"{pn} {term}", d.rstrip(".") + ".",
        A(f'{term} {pn} ?d . FILTER(CONTAINS(STR(?d), "{key}"))'), "partial")


inst("rec:Architecture", "Which kinds of architectural parts does the rec:Architecture definition list as examples?", "a building site")
inst("brick:Electric_Vehicle_Charging_Hub", "What example does the brick:Electric_Vehicle_Charging_Hub definition give of where a hub may be located?", "parking lot")
inst("brick:Distribution_Frame", "Which spaces does the brick:Distribution_Frame definition give as examples?", "wiring closet")
inst("brick:Field_Of_Play", "What example does the brick:Field_Of_Play definition give?", "soccer pitch")
inst("brick:Library", "Which media does the brick:Library definition cite as examples?", "periodicals")
inst("brick:Retail_Room", "What example does the brick:Retail_Room definition give of a retail space?", "gift shop")
inst("brick:Riser", "Which kinds of infrastructure does the brick:Riser definition list as examples?", "plumbing")
inst("brick:Service_Room", "Which building subsystems does the brick:Service_Room definition list?", "HVAC, electrical, IT, plumbing")
inst("brick:Furniture", "Which activities does the brick:Furniture definition name as examples?", "seating, eating and sleeping")
inst("brick:Waste_Storage", "What does the brick:Waste_Storage definition give as examples of stored waste?", "trash or recycling")
inst("brick:Motor_Direction_Status", "Which operating directions does the brick:Motor_Direction_Status definition give as examples?", "forward or reverse")
inst("brick:Speed_Mode_Status", "Which speed settings does the brick:Speed_Mode_Status definition give as examples?", "low, medium, and high")
inst("brick:Contact_Sensor", "What example does the brick:Contact_Sensor definition give of what contact detection is for?", "door is closed")
inst("brick:TETRA_Room", "What example does the brick:TETRA_Room definition give of two-way radio use?", "facilities staff")

# ---------------------------------------------------------------- methodology (14)
def repl_g(term):
    r = dep(term)[1]
    return r if r.split(":")[0] in NSMAP else ""


def mdep(term, question, gist):
    ver, repl, msg = dep(term)
    exp = f"{gist} Deprecated in {ver}; replaced by {repl}; the mitigation message reads: \"{msg}\""
    esc = msg.replace("\\", "\\\\").replace('"', '\\"')
    body = (f'{term} brick:deprecatedInVersion "{ver}" . {term} brick:isReplacedBy {iri_or_q(repl)} . '
            f'{term} brick:deprecationMitigationMessage ?m . FILTER(CONTAINS(STR(?m), "{esc[:48]}"))')
    add("methodology", question,
        f"{term} {repl_g(term)}".strip(), exp, A(body), "yes")


def iri_or_q(s: str) -> str:
    return s if s.split(":")[0] in NSMAP else f"<{s}>"


mdep("brick:Condenser", "How does the schema document the renaming of brick:Condenser?", "Renamed class.")
mdep("brick:Chilled_Water_Supply_Temperature_Sensor",
     "What replaces brick:Chilled_Water_Supply_Temperature_Sensor, and why?", "Supply/return naming was swapped.")
mdep("brick:Deceleration_Time", "How is the deprecation of brick:Deceleration_Time handled?",
     "Brick-defined quantity retired in favour of a QUDT quantity.")
mdep("brick:Detention_Room", "What does the schema say about a REC replacement for brick:Detention_Room?",
     "Location class phased out.")
mdep("brick:Bench_Space", "How does the schema advise replacing brick:Bench_Space?", "Location class phased out.")
mdep("brick:Basement", "Which REC class is recorded as the replacement of the deprecated brick:Basement?",
     "Location class phased out.")

_vw = dep("brick:Water_Tank")
add("methodology", "What caveat does the schema attach to brick:Water_Tank about its own future?",
    "skos:definition brick:Water_Tank rec:UtilitiesRoom",
    f"The definition warns it \"{text('brick:Water_Tank', SKOS.definition)[text('brick:Water_Tank', SKOS.definition).index('This will'):]}\" "
    f"and the deprecation record (version {_vw[0]}, brick:isReplacedBy {_vw[1]}) carries the message \"{_vw[2]}\".",
    A("brick:Water_Tank skos:definition ?d . FILTER(CONTAINS(STR(?d), \"likely be deprecated\")) . "
      "brick:Water_Tank brick:deprecatedInVersion ?v . brick:Water_Tank brick:deprecationMitigationMessage ?m"), "yes")
add("methodology", "What should consumers of the model do when an entity has several external references?",
    "skos:definition ref:preferred", text("ref:preferred", SKOS.definition).rstrip(".") + ".",
    A("ref:preferred skos:definition ?d . FILTER(CONTAINS(STR(?d), \"prioritize\"))"), "partial")
add("methodology", "When is brick:Heating_Command the right class rather than brick:Heating_Enable_Command?",
    "skos:definition brick:Heating_Enable_Command + brick:Heating_Command",
    text("brick:Heating_Enable_Command", SKOS.definition).rstrip(".") + ". "
    "Heating_Command: " + text("brick:Heating_Command", SKOS.definition).rstrip(".") + ".",
    A("brick:Heating_Enable_Command skos:definition ?d . FILTER(CONTAINS(STR(?d), \"see Heating_Command\")) . "
      "brick:Heating_Command skos:definition ?e"), "partial")
add("methodology", "How should the stage number of a brick:Stage_Enable_Command be identified?",
    "skos:definition brick:Stage_Enable_Command",
    text("brick:Stage_Enable_Command", SKOS.definition).rstrip(".") + ".",
    A("brick:Stage_Enable_Command skos:definition ?d . FILTER(CONTAINS(STR(?d), \"identified by an entity property\"))"),
    "partial")
add("methodology", "How does the schema treat a main disconnect switch versus a main circuit breaker in a panel?",
    "skos:definition brick:Main_Circuit_Breaker",
    text("brick:Main_Circuit_Breaker", SKOS.definition).rstrip(".") + ".",
    A("brick:Main_Circuit_Breaker skos:definition ?d . FILTER(CONTAINS(STR(?d), \"Main Disconnect Switch\"))"), "partial")
add("methodology", "How is the location of a Point's timeseries data represented?",
    "skos:definition ref:hasTimeseriesReference ref:TimeseriesReference ref:storedAt ref:hasTimeseriesId",
    "ref:hasTimeseriesReference relates a data source to a ref:TimeseriesReference, which records where the data is "
    "stored (ref:storedAt: " + text("ref:storedAt", SKOS.definition) + ") and a unique identifier "
    "(ref:hasTimeseriesId: " + text("ref:hasTimeseriesId", SKOS.definition) + ").",
    A("ref:hasTimeseriesReference skos:definition ?a . ref:TimeseriesReference skos:definition ?b . "
      "ref:storedAt skos:definition ?c . ref:hasTimeseriesId skos:definition ?d"), "partial")
add("methodology", "What does the definition of brick:MAU point the reader to?",
    "skos:definition brick:MAU + rdfs:subClassOf",
    "\"" + text("brick:MAU", SKOS.definition) + "\" (brick:MAU parents: " + ", ".join(parents("brick:MAU")) + ").",
    A("brick:MAU skos:definition ?d . FILTER(CONTAINS(STR(?d), \"See Makeup_Air_Unit\")) . "
      + " . ".join(f"brick:MAU rdfs:subClassOf {p}" for p in parents("brick:MAU"))), "partial")
add("methodology", "How does the definition of brick:HVAC_System direct a reader to another term?",
    "skos:definition brick:HVAC_System + rdfs:subClassOf brick:System",
    "\"" + text("brick:HVAC_System", SKOS.definition) + "\" (brick:HVAC_System is a subclass of brick:System).",
    A("brick:HVAC_System skos:definition ?d . FILTER(CONTAINS(STR(?d), \"See Heating_Ventilation_Air_Conditioning_System\")) . "
      "brick:HVAC_System rdfs:subClassOf brick:System"), "partial")

# ---------------------------------------------------------------- number, write
assert len(rows) == 84, len(rows)
cnt = {c: sum(1 for r in rows if r["category"] == c) for c in CATEGORIES}
assert set(cnt.values()) == {14}, cnt
QDIR.mkdir(exist_ok=True)
for i, r in enumerate(rows, 1):
    r["cq_id"] = f"CQX{i:02d}"
    r["cluster_id"] = r["cq_id"]
    r["created"] = CREATED
    r["status"] = "draft (AI-generated, artifact-blind; author_review pending)"
    r["ask_query_file"] = f"ask_queries/{r['cq_id']}.rq"
    r["author_review"] = "pending"
    (HERE / r["ask_query_file"]).write_text(PREAMBLE + r["ask"] + "\n", encoding="utf-8")

# ---------------------------------------------------------------- screens
sys.path.insert(0, str(ACCESS / "harness"))
import run_holdout as _rh  # noqa: E402  (only its pure function _grounding_anchors is used)
_locals = {str(x).split("#")[-1].split("/")[-1] for x in (set(g.subjects()) | set(g.objects()) | set(g.predicates()))
           if isinstance(x, URIRef)}
known = {str(x) for x in set(g.subjects()) | set(g.objects()) | set(g.predicates())}
TERM = re.compile(r"\b(brick|rec|ref):([A-Za-z0-9_]+)")
DEFCLAIM = re.compile(r"(skos:definition|rdfs:comment)\s+((?:brick|rec|ref):[A-Za-z0-9_]+)")
COLS = ["cq_id", "category", "question", "grounding", "expected_answer", "status", "cluster_id",
        "created", "ask_expressible", "ask_query_file", "author_review"]
sha = hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest()
assert sha == SNAPSHOT_SHA256, f"snapshot sha mismatch {sha}"

existing = list(csv.DictReader(EXISTING.open(newline="", encoding="utf-8")))
tok = lambda s: set(re.findall(r"[a-z0-9_:]+", s.lower())) - {"what", "is", "a", "the", "of", "which", "does", "how", "are", "to", "an", "in", "for", "and", "its", "that"}  # noqa: E731
gterms = lambda s: {f"{p}:{l}" for p, l in TERM.findall(s)}  # noqa: E731
ex_tok = [(e["cq_id"], tok(e["question"]), gterms(e["grounding"]), e["category"]) for e in existing]

ids, qs = set(), set()
for i, r in enumerate(rows):
    notes = []
    # (1) format
    f = True
    if not re.fullmatch(r"CQX\d{2}", r["cq_id"]) or r["cq_id"] in ids:
        f = False; notes.append("bad/duplicate id")
    ids.add(r["cq_id"])
    if r["category"] not in CATEGORIES:
        f = False; notes.append("bad category")
    if not (15 <= len(r["question"]) <= 200 and r["question"].endswith("?")) or r["question"] in qs:
        f = False; notes.append("question form/duplicate text")
    qs.add(r["question"])
    if len(r["expected_answer"]) < 10 or not r["grounding"].strip():
        f = False; notes.append("empty expected/grounding")
    if r["ask_expressible"] not in {"yes", "partial", "no"}:
        f = False; notes.append("bad ask_expressible")
    if any(ord(ch) > 127 for ch in r["question"] + r["grounding"]):
        f = False; notes.append("non-ASCII in question/grounding")
    if r["ask_expressible"] in {"yes", "partial"} and not (HERE / r["ask_query_file"]).is_file():
        f = False; notes.append("ask file missing")
    if not gterms(r["grounding"]):
        f = False; notes.append("grounding has no registered-prefix term")
    anchors = _rh._grounding_anchors(r["grounding"])
    r["eligibility_anchors"] = " | ".join(anchors)
    bad = [a for a in anchors if a.split(":")[-1] not in _locals]
    r["anchor_rule_check"] = "PASS" if anchors and not bad else "FAIL"
    if r["anchor_rule_check"] == "FAIL":
        notes.append(f"anchors not snapshot names: {bad}")
    r["screen_format"] = "PASS" if f else "FAIL"
    # (2) grounding existence + definition claim
    gr = True
    for p, l in TERM.findall(r["grounding"] + " " + r["expected_answer"] + " " + r["question"]):
        if str(NSMAP[p][l]) not in known:
            gr = False; notes.append(f"term missing {p}:{l}")
    for pred, term in DEFCLAIM.findall(r["grounding"]):
        pu = SKOS.definition if pred == "skos:definition" else RDFS.comment
        if not any(isinstance(o, Literal) and str(o).strip() for o in g.objects(iri(term), pu)):
            gr = False; notes.append(f"no literal for {pred} {term}")
    r["screen_grounding"] = "PASS" if gr else "FAIL"
    # (3) ASK
    try:
        res = bool(g.query(PREAMBLE + r["ask"]).askAnswer)
    except Exception as exc:  # noqa: BLE001
        res = False; notes.append(f"ASK error {exc}")
    r["screen_ask"] = "PASS" if res else "FAIL"
    if not res:
        notes.append("ASK false")
    # duplicate check: primary term = first registered term of the grounding cell.
    t = tok(r["question"])
    pm = TERM.search(r["grounding"])
    prim = f"{pm.group(1)}:{pm.group(2)}" if pm else ""
    pl = (pm.group(2).lower() if pm else "")
    best = max(((len(t & et) / max(1, len(t | et)), eid) for eid, et, eg, cat in ex_tok), default=(0, ""))
    hits = [eid for eid, et, eg, cat in ex_tok
            if prim and (prim in eg or prim.lower() in et or pl in {x.split(":")[-1] for x in et})]
    r["nearest_existing"] = f"{best[1]} (token jaccard {best[0]:.2f})"
    dup = best[0] >= 0.8 or bool(hits)
    if dup:
        notes.append(f"primary term/question overlaps existing {hits or best[1]}")
    new_dup = [rows[j]["cq_id"] for j in range(i)
               if (prim and prim == (TERM.search(rows[j]["grounding"]).group(0) if TERM.search(rows[j]["grounding"]) else ""))
               or len(t & tok(rows[j]["question"])) / max(1, len(t | tok(rows[j]["question"]))) >= 0.8]
    if new_dup:
        dup = True
        notes.append(f"primary term/question overlaps new rows {new_dup}")
    r["screen_dup"] = "REVIEW" if dup else "PASS"
    r["screen_fail"] = "FAIL" if (not f or not gr or not res or r["anchor_rule_check"] == "FAIL") else ("REVIEW" if dup else "ok")
    r["screen_notes"] = "; ".join(notes)

with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
    fh.write(HEADER + "\n")
    w = csv.DictWriter(fh, fieldnames=COLS + ["screen_format", "screen_grounding", "screen_ask", "screen_dup",
                                              "nearest_existing", "eligibility_anchors", "anchor_rule_check", "screen_fail", "screen_notes"],
                       extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    w.writerows(rows)

summary = {
    "snapshot_sha256": sha, "rows": len(rows), "per_category": cnt,
    "format_pass": sum(r["screen_format"] == "PASS" for r in rows),
    "grounding_pass": sum(r["screen_grounding"] == "PASS" for r in rows),
    "ask_pass": sum(r["screen_ask"] == "PASS" for r in rows),
    "all_three_pass": sum(r["screen_format"] == r["screen_grounding"] == r["screen_ask"] == "PASS" for r in rows),
    "anchor_rule_pass": sum(r["anchor_rule_check"] == "PASS" for r in rows),
    "dup_review": [r["cq_id"] for r in rows if r["screen_dup"] == "REVIEW"],
    "fail": [(r["cq_id"], r["screen_notes"]) for r in rows if r["screen_fail"] == "FAIL"],
    "ask_expressible": {k: sum(r["ask_expressible"] == k for r in rows) for k in ("yes", "partial", "no")},
    "grounding_terms_checked": sum(len(TERM.findall(r["grounding"] + " " + r["expected_answer"] + " " + r["question"])) for r in rows),
}
OUT_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2, ensure_ascii=False))
sys.exit(1 if summary["fail"] else 0)
