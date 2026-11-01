"""Question spec of the SOSA/SSN bank (addendum 35).  AI draft written from the frozen snapshots and the documentation only; not author-reviewed."""
NS = "http://www.w3.org/ns/sosa/"
PFX = "sosa"
NSMAP = {"sosa": "http://www.w3.org/ns/sosa/", "ssn": "http://www.w3.org/ns/ssn/"}
ID_PREFIX = "CQS"
SNAPSHOTS = ["sosa.ttl", "ssn.ttl"]
ROWS = [
    # concept_definition
    ("concept_definition", "def", "sosa:Sensor", "What is a sosa:Sensor?"),
    ("concept_definition", "def", "sosa:Observation", "What does sosa:Observation represent?"),
    ("concept_definition", "def", "sosa:Actuation", "What is a sosa:Actuation?"),
    ("concept_definition", "def", "sosa:Platform", "What is a sosa:Platform?"),
    ("concept_definition", "def", "sosa:FeatureOfInterest", "What is a sosa:FeatureOfInterest?"),
    ("concept_definition", "def", "ssn:Deployment", "What does ssn:Deployment describe?"),
    ("concept_definition", "def", "ssn:System", "What is an ssn:System?"),
    # taxonomy
    ("taxonomy", "sub", ("sosa:Sensor", "ssn:System"), "Is sosa:Sensor a subclass of ssn:System?"),
    ("taxonomy", "sub", ("sosa:Actuator", "ssn:System"), "Is sosa:Actuator a subclass of ssn:System?"),
    ("taxonomy", "sub", ("sosa:Sampler", "ssn:System"), "Is sosa:Sampler a subclass of ssn:System?"),
    ("taxonomy", "sub", ("sosa:Sample", "sosa:FeatureOfInterest"), "Is sosa:Sample a subclass of sosa:FeatureOfInterest?"),
    ("taxonomy", "sub", ("sosa:ObservableProperty", "ssn:Property"), "Is sosa:ObservableProperty a subclass of ssn:Property?"),
    ("taxonomy", "children", "ssn:System", "Which SOSA classes are direct subclasses of ssn:System?"),
    ("taxonomy", "children", "ssn:Property", "Which classes are direct subclasses of ssn:Property?"),
    # relations
    ("relations", "inv", ("sosa:hosts", "sosa:isHostedBy"), "What is the inverse of sosa:hosts?"),
    ("relations", "inv", ("sosa:observes", "sosa:isObservedBy"), "Which property is the inverse of sosa:observes?"),
    ("relations", "inv", ("sosa:madeBySensor", "sosa:madeObservation"), "Which property is the inverse of sosa:madeBySensor?"),
    ("relations", "inv", ("sosa:hasResult", "sosa:isResultOf"), "How is the inverse of sosa:hasResult called?"),
    ("relations", "inv", ("ssn:hasProperty", "ssn:isPropertyOf"), "What is the inverse of ssn:hasProperty?"),
    ("relations", "inv", ("ssn:implements", "ssn:implementedBy"), "Which property is the inverse of ssn:implements?"),
    ("relations", "dr", "sosa:usedProcedure", "How does an Observation, Actuation or Sample refer to a re-usable Procedure?"),
    # slots_facets
    ("slots_facets", "prop", "sosa:hasSimpleResult", "Which property holds the simple value of an Observation?"),
    ("slots_facets", "prop", "sosa:resultTime", "Which property gives the instant at which an Observation activity completed and the result became available?"),
    ("slots_facets", "prop", "sosa:phenomenonTime", "Which property gives the time that a Result applies to the feature of interest?"),
    ("slots_facets", "prop", "ssn:hasInput", "Which property links a Procedure to an Input to it?"),
    ("slots_facets", "prop", "ssn:hasOutput", "Which property links a Procedure to an Output of it?"),
    ("slots_facets", "prop", "ssn:hasSubSystem", "Which property relates a System to its component parts?"),
    ("slots_facets", "prop", "ssn:detects", "Which property relates a Sensor to the Stimulus it detects?"),
    # instances (examples named in the text)
    ("instances", "note", "sosa:Sensor", "Which devices does the documentation give as examples of sensors on a smart phone?", "Accelerometers"),
    ("instances", "note", "sosa:ObservableProperty", "Which examples of observable properties does the documentation give?", "height of a tree"),
    ("instances", "note", "sosa:Result", "What example is given for a sosa:Result?", "20"),
    ("instances", "note", "ssn:Deployment", "What examples of an ssn:Deployment are given?", "temperature Sensor deployed"),
    ("instances", "note", "sosa:hasFeatureOfInterest", "What example is given for sosa:hasFeatureOfInterest?", "weight of a person"),
    ("instances", "note", "ssn:isProxyFor", "What example is given for a Stimulus serving as a proxy for a property?", "quicksilver"),
    ("instances", "note", "sosa:Procedure", "What example does the documentation give of a procedure that fixes the sensor height?", "standard height"),
    # methodology (usage guidance)
    ("methodology", "note", "sosa:observedProperty", "Of which entity should the observed property of an Observation be a property?", "should be a property"),
    ("methodology", "note", "sosa:Procedure", "Can many observations be created via the same Procedure?", "Many observations"),
    ("methodology", "note", "sosa:Sample", "Is a transient sample such as a ships-track expected to be revisited exactly?", "transient sample"),
    ("methodology", "note", "sosa:phenomenonTime", "Is the phenomenon time necessarily the same as the result time?", "Not necessarily"),
    ("methodology", "note", "sosa:usedProcedure", "What kind of Procedure does sosa:usedProcedure link to?", "re-usable"),
    ("methodology", "note", "ssn:Stimulus", "Is a Stimulus the event or the object that triggers the Sensor?", "not the object"),
    ("methodology", "note", "sosa:Sensor", "What does a sosa:Sensor respond to?", "respond to a stimulus"),
]
