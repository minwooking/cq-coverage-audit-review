"""Question spec of the DCAT bank (addendum 35).  AI draft written from the frozen snapshot and the documentation only; not author-reviewed.
Each row: (category, kind, args, question [, needle]).  Answers are generated verbatim from the snapshot by make_bank.py."""
NS = "http://www.w3.org/ns/dcat#"
PFX = "dcat"
ID_PREFIX = "CQD"
SNAPSHOTS = ["dcat.ttl"]
ROWS = [
    # concept_definition
    ("concept_definition", "def", "Dataset", "What is a dcat:Dataset?"),
    ("concept_definition", "def", "Catalog", "What does dcat:Catalog represent?"),
    ("concept_definition", "def", "Distribution", "What is a dcat:Distribution?"),
    ("concept_definition", "def", "DataService", "What is a dcat:DataService?"),
    ("concept_definition", "def", "DatasetSeries", "What is a dcat:DatasetSeries?"),
    ("concept_definition", "def", "Relationship", "What is the purpose of the dcat:Relationship class?"),
    ("concept_definition", "def", "Role", "What is a dcat:Role?"),
    # taxonomy
    ("taxonomy", "sub", ("Catalog", "Dataset"), "Is dcat:Catalog a subclass of dcat:Dataset?"),
    ("taxonomy", "sub", ("DatasetSeries", "Dataset"), "Is dcat:DatasetSeries a subclass of dcat:Dataset?"),
    ("taxonomy", "sub", ("Dataset", "Resource"), "Is dcat:Dataset a subclass of dcat:Resource?"),
    ("taxonomy", "sub", ("DataService", "Resource"), "Is dcat:DataService a subclass of dcat:Resource?"),
    ("taxonomy", "children", "Resource", "Which classes are direct subclasses of dcat:Resource?"),
    ("taxonomy", "children", "Dataset", "Which classes are direct subclasses of dcat:Dataset?"),
    ("taxonomy", "sub", ("Role", "Concept"), "Is dcat:Role a subclass of skos:Concept?"),
    # relations
    ("relations", "dr", "distribution", "Which property links a dcat:Dataset to its dcat:Distribution?"),
    ("relations", "dr", "servesDataset", "How does a dcat:DataService indicate the datasets it can distribute?"),
    ("relations", "dr", "record", "How is a dcat:CatalogRecord attached to a dcat:Catalog?"),
    ("relations", "dr", "qualifiedRelation", "Which property points from a resource to a description of its relationship with another resource?"),
    ("relations", "inv", ("distribution", "isDistributionOf"), "What is the inverse of dcat:distribution?"),
    ("relations", "inv", ("inSeries", "seriesMember"), "Which property is the inverse of dcat:inSeries?"),
    ("relations", "inv", ("previousVersion", "nextVersion"), "Which property is the inverse of dcat:previousVersion?"),
    # slots_facets
    ("slots_facets", "prop", "byteSize", "Which property records the size of a distribution in bytes?"),
    ("slots_facets", "prop", "compressFormat", "Which property states the compression format of a distribution?"),
    ("slots_facets", "prop", "packageFormat", "Which property states how the files of a distribution are packaged together?"),
    ("slots_facets", "prop", "endpointURL", "Which property gives the root location of a data service?"),
    ("slots_facets", "prop", "temporalResolution", "Which property gives the minimum time period resolvable in a dataset?"),
    ("slots_facets", "prop", "bbox", "Which property holds the geographic bounding box of a spatial thing?"),
    ("slots_facets", "prop", "keyword", "Which property holds a keyword or tag describing a resource?"),
    # instances (examples named in the text)
    ("instances", "note", "accessURL", "Which kinds of resources does the dcat:accessURL definition give as examples?", "E.g."),
    ("instances", "note", "downloadURL", "Which file formats does the dcat:downloadURL definition give as examples?", "E.g."),
    ("instances", "note", "DatasetSeries", "Which common scenarios does the documentation give for a dcat:DatasetSeries?", "Common scenarios"),
    ("instances", "note", "Catalog", "What does the documentation name as examples of resources in a data catalog?", "examples of resources"),
    ("instances", "note", "packageFormat", "Which package file types does dcat:packageFormat mention as examples?", "TAR file"),
    ("instances", "note", "bbox", "Which geometry encoding does dcat:bbox mention as an example?", "WKT"),
    ("instances", "note", "Distribution", "How does the documentation say a dcat:Distribution can differ from other distributions of the same dataset?", "differ in various ways"),
    # methodology (usage guidance)
    ("methodology", "note", "downloadURL", "When should dcat:downloadURL be used?", "SHOULD be used"),
    ("methodology", "note", "mediaType", "When should dcat:mediaType be used instead of dcterms:format?", "SHOULD be used"),
    ("methodology", "note", "landingPage", "What should be done when a distribution is only accessible through a landing page?", "duplicated"),
    ("methodology", "note", "Role", "How are the values of dcat:Role recommended to be managed?", "recommended"),
    ("methodology", "note", "themeTaxonomy", "How is the theme taxonomy of a catalog recommended to be organized?", "recommended"),
    ("methodology", "note", "CatalogRecord", "Is the dcat:CatalogRecord class required in a catalog?", "optional"),
    ("methodology", "note", "prev", "How does dcat:prev differ from dcat:previousVersion?", "different from"),
]
