"""Question spec of the PROV bank (addendum 35).  AI draft written from the frozen snapshot and the documentation only; not author-reviewed."""
NS = "http://www.w3.org/ns/prov#"
PFX = "prov"
ID_PREFIX = "CQP"
SNAPSHOTS = ["prov.ttl"]
EXTRA_PREDS = ["http://www.w3.org/ns/prov#definition", "http://www.w3.org/ns/prov#editorialNote"]
DEF_GROUNDING = "prov:definition"
ROWS = [
    # concept_definition
    ("concept_definition", "def", "Entity", "What is a prov:Entity?"),
    ("concept_definition", "def", "Activity", "What is a prov:Activity?"),
    ("concept_definition", "def", "Agent", "What is a prov:Agent?"),
    ("concept_definition", "def", "Bundle", "What is a prov:Bundle?"),
    ("concept_definition", "def", "Plan", "What is a prov:Plan?"),
    ("concept_definition", "def", "Influence", "What does prov:Influence mean?"),
    ("concept_definition", "def", "Role", "What is a prov:Role?"),
    # taxonomy
    ("taxonomy", "sub", ("Person", "Agent"), "Is prov:Person a subclass of prov:Agent?"),
    ("taxonomy", "sub", ("Organization", "Agent"), "Is prov:Organization a subclass of prov:Agent?"),
    ("taxonomy", "sub", ("Bundle", "Entity"), "Is prov:Bundle a subclass of prov:Entity?"),
    ("taxonomy", "sub", ("Quotation", "Derivation"), "Is prov:Quotation a subclass of prov:Derivation?"),
    ("taxonomy", "sub", ("Revision", "Derivation"), "Is prov:Revision a subclass of prov:Derivation?"),
    ("taxonomy", "children", "Agent", "Which classes are direct subclasses of prov:Agent?"),
    ("taxonomy", "children", "Influence", "Which classes are direct subclasses of prov:Influence?"),
    # relations
    ("relations", "dr", "used", "Which property links an Activity to an Entity it used?"),
    ("relations", "dr", "wasAttributedTo", "How is an Entity attributed to an Agent?"),
    ("relations", "dr", "hadPlan", "Which property attaches a Plan to an Association?"),
    ("relations", "dr", "wasInformedBy", "Which property expresses that one activity was informed by another?"),
    ("relations", "inv", ("wasGeneratedBy", "generated"), "What is the inverse of prov:wasGeneratedBy?"),
    ("relations", "inv", ("actedOnBehalfOf", "hadDelegate"), "Which property is the inverse of prov:actedOnBehalfOf?"),
    ("relations", "inv", ("wasDerivedFrom", "hadDerivation"), "Which property is the inverse of prov:wasDerivedFrom?"),
    # slots_facets
    ("slots_facets", "prop", "startedAtTime", "Which property gives the time at which an activity started?"),
    ("slots_facets", "prop", "generatedAtTime", "Which property gives the time at which an entity was completely created and is available for use?"),
    ("slots_facets", "prop", "invalidatedAtTime", "Which property gives the time at which an entity was invalidated?"),
    ("slots_facets", "prop", "atLocation", "Which property records the location of any resource?"),
    ("slots_facets", "prop", "hadRole", "Which property gives the role an entity assumed in the context of an activity?"),
    ("slots_facets", "prop", "value", "Which property provides a direct representation of an entity as a value?"),
    ("slots_facets", "prop", "qualifiedUsage", "Which property is used to qualify how an activity used an entity?"),
    # instances (examples named in the text)
    ("instances", "note", "Bundle", "What kinds of bundles does the documentation name that PROV-O does not express?", "handwritten letters"),
    ("instances", "note", "used", "What example does the documentation give for prov:used?", "baking"),
    ("instances", "note", "hadRole", "What example is given for prov:hadRole?", "mixing_implement"),
    ("instances", "note", "Quotation", "What example is given for a prov:Quotation?", "casablanca"),
    ("instances", "note", "Revision", "What example is given for a prov:Revision?", "draft_2"),
    ("instances", "note", "Delegation", "What example is given for a prov:Delegation?", "toddler"),
    ("instances", "note", "Influence", "What example is given for an instance of prov:Influence?", "stomach_ache"),
    # methodology (usage guidance)
    ("methodology", "note", "wasDerivedFrom", "Which more specific subproperties of prov:wasDerivedFrom should be used when applicable?", "should be used when applicable"),
    ("methodology", "note", "wasInfluencedBy", "Which more specific subproperties of prov:wasInfluencedBy should be used when applicable?", "should be used when applicable"),
    ("methodology", "note", "Plan", "Does PROV-O prescribe the nature of plans?", "no prescriptive requirement"),
    ("methodology", "note", "atLocation", "Is prov:atLocation functional?", "not functional"),
    ("methodology", "note", "hadPlan", "Is the plan of an association required?", "optional"),
    ("methodology", "note", "value", "Why does prov:value exist alongside rdf:value?", "reintroduced"),
]
