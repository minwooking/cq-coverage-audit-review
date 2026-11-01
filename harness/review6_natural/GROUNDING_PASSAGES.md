# Passages for the analyst read (auto-ranked by question + anchor terms only)

## CQB01 [concept_definition] What is a brick:Sensor?

- grounding: `skos:definition brick:Sensor`; anchors ['Sensor']; L0=True L1=True (sections 50) L2=True (best answer-term fraction 0.643)
- expected_answer (bank): An input point representing the value of a device/instrument designed to detect and measure a variable (ASHRAE Dictionary); subclass of brick:Point.

**P1** (score 5; Brick developer documentation (docs.brickschema.org) / Core Concepts :: Tag; c1.s2#0)

> A tag is an atomic fact or attribute of an entity.
> Examples of tags are sensor, setpoint, air, water, discharge, leaving and vav.
> Brick borrows the concept of tags from Project Haystack in order to preserve the flexibility and ease of use for annotation; however, Brick does not rely on tags alone to determine the type of an entity.

**P2** (score 5; Brick developer documentation (docs.brickschema.org) / Entity Properties :: Peak Hourly Power Meter; c13.s3#0)

> This is the model of a power sensor which tracks the peak hourly real power.
> This is a little more complex than the earlier example. There are two entity properties associated with the Power_Sensor entity. The first is brick:powerComplexity which tells us that the sensor measures real power. The second is brick:aggregate. The two properties of the brick:aggregate value tell us that the sensor's values are aggregated on a 1 hour window; this is indicated by the brick:aggregationInterval property. The brick:aggregationFunction indicates that the values within that 1 hour interval are aggregated to the maximum of the values in that window.

**P3** (score 5; Brick developer documentation (docs.brickschema.org) / Using Tags :: Using Tags; c15.s0#1)

> In contrast to other metadata efforts such as Project Haystack, Brick does not use tags to define what an entity is.
> Tags constitute a "folksonomic" approach to capturing knowledge.
> Because tags are usually just words (e.g. hot, water, sensor, evaporative), there is no explicit mechanism to state how a certain word is intended.
> As a result, while tags are great for to informally annotate properties whose meaning is already known to the user, they are not an effective mechanism for communicating semantic information in a consistent and interpretable manner fierro2019beyond.

## CQB02 [concept_definition] What does brick:Meter represent?

- grounding: `skos:definition brick:Meter + rdfs:subClassOf`; anchors ['Meter']; L0=True L1=True (sections 18) L2=True (best answer-term fraction 0.615)
- expected_answer (bank): A device that measures usage or consumption of some media, typically a form of energy or power; rdfs:subClassOf brick:Equipment.

**P1** (score 5; Brick developer documentation (docs.brickschema.org) / Entity Properties :: Entity Properties; c13.s0#0)

> This feature is new in Brick v1.2
> Entity Properties are attributes or characteristics of Brick entities. The values of Entity Properties should change rarely, if ever; if a value is changing regularly, then it is likely better modeled as a Brick Point. Entity properties are useful for modeling static charcteristics such as:
> - floor area, room volume
> - phase count, phases, and flow of electric meters
> - which operational stage a point is associated with
> - how the values of a given Point are aggregated
> - and many others!

**P2** (score 5; Brick developer documentation (docs.brickschema.org) / Entity Properties :: Peak Hourly Power Meter; c13.s3#0)

> This is the model of a power sensor which tracks the peak hourly real power.
> This is a little more complex than the earlier example. There are two entity properties associated with the Power_Sensor entity. The first is brick:powerComplexity which tells us that the sensor measures real power. The second is brick:aggregate. The two properties of the brick:aggregate value tell us that the sensor's values are aggregated on a 1 hour window; this is indicated by the brick:aggregationInterval property. The brick:aggregationFunction indicates that the values within that 1 hour interval are aggregated to the maximum of the values in that window.

**P3** (score 5; Brick developer documentation (docs.brickschema.org) / Entity Properties :: Peak Hourly Power Meter; c13.s3#1)

> brick:aggregationInterval uses the ISO 8601 Duration specification to indicate the length of an interval. It also incorporates an R prefix to indicate a repeating duration.

## CQB03 [concept_definition] What is a rec:Asset?

- grounding: `rdfs:comment rec:Asset`; anchors ['Asset']; L0=True L1=True (sections 11) L2=True (best answer-term fraction 0.5)
- expected_answer (bank): Something placed inside a building but not an integral part of that building's structure; e.g. furniture, equipment, systems.

**P1** (score 4; Brick developer documentation (docs.brickschema.org) / Automation and Point Collections :: Relationship Roles; c21.s3#1)

> Equipment, spaces, and zones can include automation collections with rec:includes. This is useful when an asset or zone has a logical application bundle, but the bundle is not a physical part of that asset or zone.

**P2** (score 4; Brick website (brickschema.org) / brick and vbis :: brick and vbis; c31.s0#1)

> Both initiatives have the aligned goal of promoting a consistent standardized approach to structuring data to gain better insights but with differing focus areas. Brick, through collaboration with Project Haystack and ASHRAE, defines an extensive dictionary of I/O points (including automation control points), HVAC, lighting and electrical assets, and relationships between assets and points. VBIS in turn has a comprehensive classification structure and asset specific metatag for all assets that make up the built environment as well as a mechanism to allow linking asset data that is stored in disparate locations to allow discovery and use of information.

**P3** (score 4; Brick website (brickschema.org) / brick and vbis :: brick and vbis; c31.s0#2)

> The collaboration brings together these complementary developments. The VBIS classification structure, which captures detailed asset properties not covered by Brick, will be mapped to the asset classes in Brick. This will provide a comprehensive data model definition that supports deploying analytics, energy efficiency measures, automation as well as Asset Management and Facility Management activities such as lifecycle planning, maintenance planning and performance benchmarking.

## CQB04 [concept_definition] What is a brick:Zone?

- grounding: `skos:definition brick:Zone`; anchors ['Zone']; L0=True L1=True (sections 27) L2=False (best answer-term fraction 0.389)
- expected_answer (bank): (1) a separately controlled heated or cooled space; (2) one or several occupied spaces with similar occupancy category, occupant density, air distribution effectiveness and primary airflow per unit area.

**P1** (score 5; Brick developer documentation (docs.brickschema.org) / Using Tags :: Tags and Brick Classes; c15.s2#0)

> Most, if not all, Brick classes have a set of associated tags, which will be "inherited" by any Brick entity which is an instance of that class.
> Tags are related to a Brick class via the brick:hasAssociatedTag relationship.
> For example, to fetch the tags associated with the brick:Zone_Air_Temperature_Sensor class, execute the following query:

**P2** (score 5; Brick developer documentation (docs.brickschema.org) / Using Tags :: Tags and Brick Entities; c15.s3#1)

> For example, consider an instance of brick:Zone_Air_Temperature_Sensor in a Brick model (before inference is applied):
> After inference, the model will consist of the following:

**P3** (score 5; Brick developer documentation (docs.brickschema.org) / Automation and Point Collections :: Relationship Roles; c21.s3#0)

> Use collection membership for organization, and use the normal Brick relationships for the model semantics:
> - Use rec:includes to put an entity into an Automation Collection or Point Collection.
> - Use brick:hasPart for physical or structural composition, such as an AHU having a fan or coil.
> - Use brick:hasPoint / brick:isPointOf to attach a point to the equipment, location, or zone it describes.
> - Use brick:hostsPoint / brick:isHostedBy to describe the ICT equipment, controller, gateway, or device that hosts or exposes a point.
> - Use brick:controls / brick:isControlledBy for control relationships between controllers and the equipment they supervise.

## CQB05 [concept_definition] What is a rec:Campus?

- grounding: `rdfs:comment rec:Campus`; anchors ['Campus']; L0=True L1=True (sections 1) L2=False (best answer-term fraction 0.167)
- expected_answer (bank): A collection of location entities that may differ in legal ownership and purpose but are perceived as a coherent unit or sub-region within a city/region.

**P1** (score 4; Papers / Fierro et al. 2020, Formalizing Tag-Based Metadata With the Brick Ontology (Frontiers in Big Data) :: 7.1. Migration Strategies for Brick; c55.s7#21)

> 8.1. Source Haystack Models We assemble a set of five Haystack models, each consisting of a set of tagged entities. Haystack model 1 is the “Carytown” reference model published by Project Haystack for a 3000 sq ft building in Richmond, VA. Haystack models 2 and 3 are sample Haystack data models with for complex buildings, and thus contain large numbers of specialized and non-standard tags (Coffey, 2019). Haystack models 4 and 5 represent two office buildings on the UC Davis campus. Together, these five Haystack models represent a diverse family spanning small to large buildings, differing numbers of custom tags, and different model modelers.

## CQB06 [concept_definition] What does rec:Georeference express?

- grounding: `rdfs:comment rec:Georeference`; anchors ['Georeference']; L0=False L1=False (sections 0) L2=False (best answer-term fraction 0.0)
- expected_answer (bank): A relationship created between a local coordinate system and a geographic coordinate system.

**P1** (score 1; Brick developer documentation (docs.brickschema.org) / Controllers :: Example: VAV Controller; c19.s2#0)

> Here brick:controls captures the supervisory relationship and brick:hosts captures which device exposes the points on the network.
> brick:hasPoint remains on the VAV to express that those points describe the VAV — not the controller.

**P2** (score 1; Brick developer documentation (docs.brickschema.org) / Relationships :: Definitions; c3.s0#2)

> Relationships express how entities, classes, tags and other "things" interact and are associated with each other. More formally, a relationship defines the nature of a link between two related entities. The purpose of this document is to provide greater clarity on:
> - the broad categories of relationships
> - names and definitions of the specific relationships defined by the Brick ontology
> - guidelines, idioms and examples for how to apply these relationships in practice

**P3** (score 1; Brick developer documentation (docs.brickschema.org) / Using Brick and RealEstateCore Together :: Collections; c5.s3#0)

> This section describes changes introduced in Brick v1.5.
> As of Brick v1.5.0, brick:Collection has been deprecated in favor of rec:Collection to remove redundancy between the two ontologies. Custom collections should now be typed as rec:Collection and use rec:includes to express membership:

## CQB07 [taxonomy] Is brick:Sensor a subclass of brick:Point?

- grounding: `subclassof:Sensor>Point`; anchors ['Sensor', 'Point']; L0=True L1=True (sections 34) L2=True (best answer-term fraction 1.0)
- expected_answer (bank): Yes; direct rdfs:subClassOf brick:Point.

**P1** (score 10; Papers / BrickLLM: A Python library for generating Brick-compliant RDF graphs using LLMs (SoftwareX) :: ARTICLE; c54.s1#22)

> SoftwareX 30 (2025) 102121
> Marco Perini et al.
> Fig. 3. Instructed workflow methodology.
> • Hierarchy construction (get_elem_children.py node): The identified entities are structured into a parent–child hierarchy, creating a JSON representation that reflects their relationships.
> In this way, a subset of the entire Brick ontology is constructed. • Relationships mapping (get_relationships.py node): this node identify the semantic elements in the user prompt, assign the corresponding Brick type and the appropriate relationship between entities.
> Finally, the graph is instantiated and all entities and relationships are added. • Sensor identification (get_sensors.py node): If entities of subclass Point are detected, their information is expanded to include attributes like timeseriesID unit of measures, database storage information or other relevant properties.

**P2** (score 9; Brick developer documentation (docs.brickschema.org) / Meters :: Meters; c20.s0#0)

> This feature is new in Brick v1.3
> Brick provides a basic but flexible model for describing meters, submeter hierarchies, and their relationships to the building.
> Meters are equipment (they are subclasses of the Brick Equipment class) that measure the consumption or production of energy, steam, gas or other "substances" in the building.
> The data produced by meters can be found in instances of the Brick Point class that are associated with the Meter.
> These include power, energy, water and gas consumption sensors and the like.

**P3** (score 9; Brick developer documentation (docs.brickschema.org) / Automation and Point Collections :: Automation and Point Collections; c21.s0#2)

> Do not infer functional semantics from collection membership alone. If a sensor, command, alarm, and piece of equipment are in the same collection, that only says they belong to the same modeled bundle. Use explicit Brick relationships to describe what is measured, commanded, controlled, hosted, or physically part of something else.

## CQB08 [taxonomy] Which top-level classes are direct subclasses of brick:Point?

- grounding: `children:Point`; anchors ['Point']; L0=True L1=True (sections 82) L2=True (best answer-term fraction 1.0)
- expected_answer (bank): Alarm, Command, Parameter, Sensor, Setpoint, Status (6).

**P1** (score 7; Papers / Fierro et al. 2020, Formalizing Tag-Based Metadata With the Brick Ontology (Frontiers in Big Data) :: 4. DESIGN OF BRICK+; c55.s4#4)

> of a “subclass” relationship (section 2), but differ in how they define relationships between concepts. A class hierarchy captures how concepts can be specialized, but does not encode how these concepts behave and relate to one another. In contrast, a lattice captures how concepts can be composed from sets of properties. This offers greater flexibility in the definition of concepts in Brick+ and facilitates the tag decomposition and mapping to Haystack detailed in section 5. Brick+ has six primary concepts. Point is the root class for all points of telemetry and actuation. There are six immediate subclasses of Point categorized by the high-level semantics of how each point behaves:

**P2** (score 7; Papers / Fierro et al. 2020, Formalizing Tag-Based Metadata With the Brick Ontology (Frontiers in Big Data) :: 5. BRICK+ IMPLEMENTATION; c55.s6#24)

> within an instance and do not result in any logical violations of the formal model.
> For example, consider the set of RDF statements in Figure 9.
> Lines 1–6 are a partial implementation of the Brick+ ontology.
> Lines 1–3 specify that any subject of the brick:isPointOf property is implied to be an instance of the brick:Point class. lines 5–6 state that the set of instances of brick:Point is disjoint with the set of instances of brick:Equipment; that is, no entity can be both a Point and an Equipment.
> We now turn to the definition of a violating Brick+ model.
> Lines 8 and 9 define two pieces of equipment (we use the high-level brick:Equipment for illustrative purposes; in reality these instances would be members of more specific, descriptive classes within the Brick+ Equipment class lattice).

**P3** (score 6; Brick developer documentation (docs.brickschema.org) / Core Concepts :: Brick Model; c1.s6#1)

> The blue nodes represent entities that are instances of Brick classes.These are the "things" inside our example building. They range from equipment (AHU1A, VAV2-4), points (VAV2-4.DPRPOS), locations (Room 410) and logical collections (VAV2-3Zone). The colored boxes connected to the instances with dashed lines represent Brick classes; the dashed line represents the "is an instance of" relationship (rdf:type). The rest of the class structure has been elided for simplicity. Lastly, the solid directed edges represent Brick relationships between entities.

## CQB09 [taxonomy] Which direct subclasses does brick:Equipment have?

- grounding: `children_count:Equipment`; anchors ['Equipment']; L0=True L1=True (sections 65) L2=False (best answer-term fraction 0.308)
- expected_answer (bank): 24 direct subclasses incl. Electrical_Equipment, HVAC_Equipment, Lighting_Equipment, Meter, Motor, Valve, Furniture, Camera, Elevator, Tank.

**P1** (score 6; Brick developer documentation (docs.brickschema.org) / Connections :: Connections on Brick Entities; c18.s2#0)

> Brick Equipment are now subclasses of s223:Equipment in the Brick ontology.
> This means that they can have ConnectionPoints and Connections associated with them.

**P2** (score 6; Brick developer documentation (docs.brickschema.org) / Meters :: Meters; c20.s0#0)

> This feature is new in Brick v1.3
> Brick provides a basic but flexible model for describing meters, submeter hierarchies, and their relationships to the building.
> Meters are equipment (they are subclasses of the Brick Equipment class) that measure the consumption or production of energy, steam, gas or other "substances" in the building.
> The data produced by meters can be found in instances of the Brick Point class that are associated with the Meter.
> These include power, energy, water and gas consumption sensors and the like.

**P3** (score 6; Papers / Fierro et al. 2020, Formalizing Tag-Based Metadata With the Brick Ontology (Frontiers in Big Data) :: 5. BRICK+ IMPLEMENTATION; c55.s6#39)

> FIGURE 12 | A SHACL shape encoding the required parts and points for a theoretical “Model XYZ” variable air volume box.
> Figure 11 contains an example of an idiomatic class shape that encodes the requirement that all VAVs in a model instance must refer to a downstream HVAC zone and an upstream air handling unit. Validating a Brick+ model instance against this shape involves examining all of the instances of brick:Variable_Air_Volume_Box and its subclasses to see if the required properties exist and if the objects of those properties fulfill the class requirements. Figure 12 is an example of a shape encoding the expected parts and points for a theoretical variable air volume box of a particular make and model. Applying this shape to a Brick+ model instance can help ensure that all instances of the equipment are modeled consistently.

## CQB10 [taxonomy] Is brick:Building a direct subclass of brick:Location?

- grounding: `rdfs:subClassOf brick:Building`; anchors ['Building']; L0=True L1=True (sections 75) L2=True (best answer-term fraction 0.714)
- expected_answer (bank): Yes; brick:Building rdfs:subClassOf brick:Location directly (not routed via Space).

**P1** (score 6; Brick developer documentation (docs.brickschema.org) / Core Concepts :: Brick Model; c1.s6#1)

> The blue nodes represent entities that are instances of Brick classes.These are the "things" inside our example building. They range from equipment (AHU1A, VAV2-4), points (VAV2-4.DPRPOS), locations (Room 410) and logical collections (VAV2-3Zone). The colored boxes connected to the instances with dashed lines represent Brick classes; the dashed line represents the "is an instance of" relationship (rdf:type). The rest of the class structure has been elided for simplicity. Lastly, the solid directed edges represent Brick relationships between entities.

**P2** (score 6; Brick developer documentation (docs.brickschema.org) / Design Principles :: Design Principles; c2.s1#0)

> Brick adheres to the following design principles:
> * Completeness: A schema should represent all the information (such as a sensor’s location, type, etc.) required by building applications.
> * Expressivity: A schema should capture the diverse family of entities and relationships between them that are present in a building's BMS and expressed in canonical energy-, operations- and management-oriented applications and scenarios.
> * Usability: A schema should be not too complex for users to easily understand and use.
> * Consistency: A schema should be able to enforce consistency in modeling processes across different users.
> * Extensibility: A schema should be easily extensible to cover new concepts in a consistent way.

**P3** (score 6; Brick developer documentation (docs.brickschema.org) / Meters :: Associating Meters; c20.s4#1)

> Metering brick:Equipment: useful when the Meter is measuring the consumption/production of a single Equipment instance.
> Metering brick:Locations: useful when the Meter is measuring the consumption/production of many entities within a single location, e.g. a building or floor or room.

## CQB11 [taxonomy] Are Alarm and Sensor disjoint in Brick?

- grounding: `disjoint:Sensor`; anchors ['Sensor']; L0=True L1=True (sections 50) L2=True (best answer-term fraction 0.778)
- expected_answer (bank): Yes; brick:Sensor owl:disjointWith Alarm, Command, Parameter, Setpoint, Status (and vice versa).

**P1** (score 6; Brick developer documentation (docs.brickschema.org) / Automation and Point Collections :: Automation and Point Collections; c21.s0#2)

> Do not infer functional semantics from collection membership alone. If a sensor, command, alarm, and piece of equipment are in the same collection, that only says they belong to the same modeled bundle. Use explicit Brick relationships to describe what is measured, commanded, controlled, hosted, or physically part of something else.

**P2** (score 6; Brick developer documentation (docs.brickschema.org) / Relationships :: Philosophy of Brick Relationships; c3.s1#3)

> Telemetry: the data sources associated or attached to various "things", be they logical, physical or virtual. In BMS-parlance, these are called "Points", and consist of the digital representations of the sensors, setpoints, commands, alarms and parameters that constitute the data produced by, for and on behalf of a building.
> Brick provides a way to describe a building and its subsystems along each of these perspectives.

**P3** (score 6; Brick developer documentation (docs.brickschema.org) / Modeling Data Sources :: Categorizing Data Sources; c4.s1#0)

> Instances of the Brick Point class represent sources or sinks of telemetry. There are several major classes of telemetry in Brick:
> - Sensor: represents the value of a device or instrument designed to detect and measure a variable
> - Setpoint: represents the value at which the desired property is set
> - Alarm: represents signals that alert an operator to an off-normal condition which requires some form of corrective action
> - Command: represents settings/actions that directly determines the behavior of equipment and/or affects relevant operational points.
> - Parameter: represents configuration settings used to guide the operation of equipment and control systems; for example they may provide bounds on valid setpoint values
> - Status: represents the current operating mode, state, position, or condition of an item. Statuses are observations and should be considered 'read-only'

## CQB12 [taxonomy] Which classes are direct subclasses of brick:Location?

- grounding: `children:Location`; anchors ['Location']; L0=True L1=True (sections 32) L2=False (best answer-term fraction 0.364)
- expected_answer (bank): Building, Floor, Outdoor_Area, Outside, Region, Site, Space, Storey, Wing, Zone (10).

**P1** (score 6; Brick developer documentation (docs.brickschema.org) / Core Concepts :: Brick Model; c1.s6#1)

> The blue nodes represent entities that are instances of Brick classes.These are the "things" inside our example building. They range from equipment (AHU1A, VAV2-4), points (VAV2-4.DPRPOS), locations (Room 410) and logical collections (VAV2-3Zone). The colored boxes connected to the instances with dashed lines represent Brick classes; the dashed line represents the "is an instance of" relationship (rdf:type). The rest of the class structure has been elided for simplicity. Lastly, the solid directed edges represent Brick relationships between entities.

**P2** (score 6; Brick website (brickschema.org) / Release Notes :: Tags; c38.s2#0)

> Brick is a "concept-first" ontology, which means that it focuses on modeling the definition and behavior of concepts (equipment, points, locations, and so on) and the relationships between them. This stands in contrast to efforts like Project Haystack, which use combinations of tags (short, atomic words and phrases) to hint at concepts. To facilitate the use of Brick's formal model over existing tag-based models and the use of tag-based "annotations", the Brick v1.1 release includes a mapping between Brick's classes and a set of tags.

**P3** (score 6; Brick website (brickschema.org) / Release Notes :: v1.2.0; c39.s2#3)

> - Timeseries Storage: the 1.2.0 release also includes some preliminary timeseries storage properties. See here for documentation; please file an issue or post on the mailing list to discuss any emergent modeling needs for timeseries
> - Alignments: Brick 1.2.0 also includes alignments with several external ontologies and metadata representations
> - BOT: an ontology for building topologies and locations
> - VBIS: an emerging standard for asset management tagging
> - REC: an emerging ontology for real estate management
> - Additional classes:
> - Locations: A large number of standard room use types have been added to Brick
> - Chiller Plants (more coming): A number of Chiller-related points and equipment have been added to Brick. Future discussions on chillers should be directed to

## CQB13 [relations] How do you express that a Point belongs to an Equipment?

- grounding: `inverse:hasPoint~isPointOf`; anchors ['hasPoint', 'isPointOf']; L0=True L1=True (sections 11) L2=True (best answer-term fraction 1.0)
- expected_answer (bank): brick:hasPoint (Equipment->Point) with inverse brick:isPointOf.

**P1** (score 8; Brick developer documentation (docs.brickschema.org) / Controllers :: Relationships; c19.s1#1)

> A point may be hosted by a controller (brick:hosts) and also described as belonging to an equipment (brick:hasPoint / brick:isPointOf). These two relationships are independent.

**P2** (score 8; Brick developer documentation (docs.brickschema.org) / Automation and Point Collections :: At-a-Glance; c21.s1#0)

> - Create a brick:Point_Collection for point-only groups.
> - Create a brick:Automation_Collection for mixed automation bundles.
> - Put member entities into the collection with rec:includes.
> - Attach every point to what it describes with brick:hasPoint or brick:isPointOf.
> - Attach every hosted point to its controller or ICT equipment with brick:hostsPoint or brick:isHostedBy.
> - Use brick:hasPart only for equipment composition, not collection membership.
> - Add rdfs:label so tools can present the collection clearly.

**P3** (score 8; Brick developer documentation (docs.brickschema.org) / Automation and Point Collections :: Relationship Roles; c21.s3#0)

> Use collection membership for organization, and use the normal Brick relationships for the model semantics:
> - Use rec:includes to put an entity into an Automation Collection or Point Collection.
> - Use brick:hasPart for physical or structural composition, such as an AHU having a fan or coil.
> - Use brick:hasPoint / brick:isPointOf to attach a point to the equipment, location, or zone it describes.
> - Use brick:hostsPoint / brick:isHostedBy to describe the ICT equipment, controller, gateway, or device that hosts or exposes a point.
> - Use brick:controls / brick:isControlledBy for control relationships between controllers and the equipment they supervise.

## CQB14 [relations] What relates an Equipment or Point to its Location?

- grounding: `prop:hasLocation`; anchors ['hasLocation']; L0=True L1=True (sections 11) L2=True (best answer-term fraction 1.0)
- expected_answer (bank): brick:hasLocation with inverse brick:isLocationOf.

**P1** (score 6; Brick developer documentation (docs.brickschema.org) / Relationships :: How and When to Use Brick Relationships; c3.s7#0)

> When your subject is a...
> - Location:
> - hasPart describes the components of that location
> - Floor hasPart Room
> - HVAC Zone hasPart Room
> - Point:
> - isPointOf describes what the data is relevant to
> - Sensor isPointOf Room
> - Equipment:
> - hasPoint describes telemetry associated with the equipment:
> - VAV hasPoint Temperature Sensor
> - Damper hasPoint Damper Position Command
> - hasLocation describes where the equipment is physically located
> - Thermostat hasLocation Room
> - hasPart describes the components of the equipment
> - VAV hasPart Damper
> - VAV hasPart Heating Coil
> - AHU hasPart Supply Fan
> - feeds describes downstream equipment and locations
> - AHU feeds VAV
> - VAV feeds HVAC Zone
> - isControlledBy describes the controller responsible for the equipment
> - VAV isControlledBy VAV_Controller
> - ICT Equipment:
> - hosts describes points exposed by the device
> - BACnet_Device hosts Temperature_Sensor
> - Controller:
> - controls describes what equipment the controller manages
> - VAV_Controller controls VAV

**P2** (score 6; Brick website (brickschema.org) / Definitions :: How and When to Use Brick Relationships; c52.s6#0)

> When your subject is a...
> - Location:
> - hasPart describes the components of that location
> - Floor hasPart Room
> - HVAC Zone hasPart Room
> - Point:
> - hasLocation describes where the point is physically located
> - Sensor hasLocation Room
> - Equipment:
> - hasPoint describes telemetry associated with the equipment:
> - VAV hasPoint Temperature Sensor
> - Damper hasPoint Damper Position Command
> - hasLocation describes where the equipment is physically located
> - Thermostat hasLocation Room
> - hasPart describes the components of the equipment
> - VAV hasPart Damper
> - VAV hasPart Heating Coil
> - AHU hasPart Supply Fan
> - feeds describes downstream equipment and locations
> - AHU feeds VAV
> - VAV feeds HVAC Zone

**P3** (score 4; Brick developer documentation (docs.brickschema.org) / Relationships :: Composition; c3.s3#0)

> brick:hasPart: the subject has some component or part identified by object; used to describe both physical and logical composition. This relationship is not typically used to desscribe the physical location of the object except in the case where the location of the object is fundamental to the identity of the subject. For example, a chair being located in a room is not fundamental to the definition of a room because a room can exist independent of whether or not a chair is located in it -- here, we would use the brick:hasLocation relationship (see below). However, a damper being "located" in a VAV is fundamental to the definition of a VAV because a VAV must be able to modulate the volume of air. In this case, we would use the brick:hasPart relationship.

## CQB15 [relations] Which property pair expresses supply/feed direction?

- grounding: `prop:feeds`; anchors ['feeds']; L0=True L1=True (sections 18) L2=True (best answer-term fraction 1.0)
- expected_answer (bank): brick:feeds with inverse brick:isFedBy.

**P1** (score 5; Brick developer documentation (docs.brickschema.org) / Relationships :: How and When to Use Brick Relationships; c3.s7#0)

> When your subject is a...
> - Location:
> - hasPart describes the components of that location
> - Floor hasPart Room
> - HVAC Zone hasPart Room
> - Point:
> - isPointOf describes what the data is relevant to
> - Sensor isPointOf Room
> - Equipment:
> - hasPoint describes telemetry associated with the equipment:
> - VAV hasPoint Temperature Sensor
> - Damper hasPoint Damper Position Command
> - hasLocation describes where the equipment is physically located
> - Thermostat hasLocation Room
> - hasPart describes the components of the equipment
> - VAV hasPart Damper
> - VAV hasPart Heating Coil
> - AHU hasPart Supply Fan
> - feeds describes downstream equipment and locations
> - AHU feeds VAV
> - VAV feeds HVAC Zone
> - isControlledBy describes the controller responsible for the equipment
> - VAV isControlledBy VAV_Controller
> - ICT Equipment:
> - hosts describes points exposed by the device
> - BACnet_Device hosts Temperature_Sensor
> - Controller:
> - controls describes what equipment the controller manages
> - VAV_Controller controls VAV

**P2** (score 5; Brick website (brickschema.org) / Definitions :: How and When to Use Brick Relationships; c52.s6#0)

> When your subject is a...
> - Location:
> - hasPart describes the components of that location
> - Floor hasPart Room
> - HVAC Zone hasPart Room
> - Point:
> - hasLocation describes where the point is physically located
> - Sensor hasLocation Room
> - Equipment:
> - hasPoint describes telemetry associated with the equipment:
> - VAV hasPoint Temperature Sensor
> - Damper hasPoint Damper Position Command
> - hasLocation describes where the equipment is physically located
> - Thermostat hasLocation Room
> - hasPart describes the components of the equipment
> - VAV hasPart Damper
> - VAV hasPart Heating Coil
> - AHU hasPart Supply Fan
> - feeds describes downstream equipment and locations
> - AHU feeds VAV
> - VAV feeds HVAC Zone

**P3** (score 5; Papers / BrickLLM: A Python library for generating Brick-compliant RDF graphs using LLMs (SoftwareX) :: 5. Conclusions; c54.s5#2)

> Case study 3 description prompt: ‘‘The building is composed by 5 HVAC zones. An Air Handling Unit feeds all the HVAC zones. Each HVAC zone has a zone air temperature sensor. The Air Handling Unit is composed by the following equipment: a cooling coil, a supply fan, a return fan, an outside damper and a return damper. Each equipment has the following sensors: • The cooling coil has a valve position sensor; • The outdoor air damper has a damper position sensor; • The return air damper has a damper position sensor; • The return fan has a speed setpoint and a speed status; • The supply fan has a speed setpoint and a speed status;

## CQB16 [relations] What is the inverse of brick:hasPart?

- grounding: `inverse:hasPart`; anchors ['hasPart']; L0=True L1=True (sections 15) L2=True (best answer-term fraction 1.0)
- expected_answer (bank): brick:isPartOf.

**P1** (score 5; Brick developer documentation (docs.brickschema.org) / Relationships :: Composition; c3.s3#0)

> brick:hasPart: the subject has some component or part identified by object; used to describe both physical and logical composition. This relationship is not typically used to desscribe the physical location of the object except in the case where the location of the object is fundamental to the identity of the subject. For example, a chair being located in a room is not fundamental to the definition of a room because a room can exist independent of whether or not a chair is located in it -- here, we would use the brick:hasLocation relationship (see below). However, a damper being "located" in a VAV is fundamental to the definition of a VAV because a VAV must be able to modulate the volume of air. In this case, we would use the brick:hasPart relationship.

**P2** (score 5; Brick website (brickschema.org) / Definitions :: Composition; c52.s3#0)

> brick:hasPart: the subject has some component or part identified by object; used to describe both physical and logical composition. This relationship is not typically used to describe the physical location of the object except in the case where the location of the object is fundamental to the identity of the subject. For example, a chair being located in a room is not fundamental to the definition of a room because a room can exist independent of whether or not a chair is located in it -- here, we would use the brick:hasLocation relationship (see below). However, a damper being "located" in a VAV is fundamental to the definition of a VAV because a VAV must be able to modulate the volume of air. In this case, we would use the brick:hasPart relationship.

**P3** (score 4; Brick developer documentation (docs.brickschema.org) / Automation and Point Collections :: At-a-Glance; c21.s1#0)

> - Create a brick:Point_Collection for point-only groups.
> - Create a brick:Automation_Collection for mixed automation bundles.
> - Put member entities into the collection with rec:includes.
> - Attach every point to what it describes with brick:hasPoint or brick:isPointOf.
> - Attach every hosted point to its controller or ICT equipment with brick:hostsPoint or brick:isHostedBy.
> - Use brick:hasPart only for equipment composition, not collection membership.
> - Add rdfs:label so tools can present the collection clearly.

## CQB17 [relations] Which property expresses spatial containment of an entity in a location?

- grounding: `rec:locatedIn (sh:path)`; anchors ['locatedIn']; L0=True L1=True (sections 6) L2=False (best answer-term fraction 0.286)
- expected_answer (bank): rec:locatedIn, used in SHACL property shapes; the Brick-namespace counterpart is brick:hasLocation / brick:isLocationOf.

**P1** (score 5; Papers / Fierro et al. 2020, Formalizing Tag-Based Metadata With the Brick Ontology (Frontiers in Big Data) :: 4. DESIGN OF BRICK+; c55.s4#16)

> isLocationOf
> yes
> isFedBy
> isPointOf
> isPartOf
> yes
> hasLocation
> Subject is physically located in the object entity
> Location
> feeds

**P2** (score 4; Brick developer documentation (docs.brickschema.org) / Relationships :: Composition; c3.s3#0)

> brick:hasPart: the subject has some component or part identified by object; used to describe both physical and logical composition. This relationship is not typically used to desscribe the physical location of the object except in the case where the location of the object is fundamental to the identity of the subject. For example, a chair being located in a room is not fundamental to the definition of a room because a room can exist independent of whether or not a chair is located in it -- here, we would use the brick:hasLocation relationship (see below). However, a damper being "located" in a VAV is fundamental to the definition of a VAV because a VAV must be able to modulate the volume of air. In this case, we would use the brick:hasPart relationship.

**P3** (score 4; Brick website (brickschema.org) / Definitions :: Composition; c52.s3#0)

> brick:hasPart: the subject has some component or part identified by object; used to describe both physical and logical composition. This relationship is not typically used to describe the physical location of the object except in the case where the location of the object is fundamental to the identity of the subject. For example, a chair being located in a room is not fundamental to the definition of a room because a room can exist independent of whether or not a chair is located in it -- here, we would use the brick:hasLocation relationship (see below). However, a damper being "located" in a VAV is fundamental to the definition of a VAV because a VAV must be able to modulate the volume of air. In this case, we would use the brick:hasPart relationship.

## CQB18 [relations] What relates a brick:Equipment to the tags it carries?

- grounding: `prop:hasAssociatedTag`; anchors ['hasAssociatedTag']; L0=True L1=True (sections 1) L2=True (best answer-term fraction 0.5)
- expected_answer (bank): brick:hasAssociatedTag to brick:Tag individuals.

**P1** (score 5; Brick developer documentation (docs.brickschema.org) / Using Tags :: Tags and Brick Classes; c15.s2#0)

> Most, if not all, Brick classes have a set of associated tags, which will be "inherited" by any Brick entity which is an instance of that class.
> Tags are related to a Brick class via the brick:hasAssociatedTag relationship.
> For example, to fetch the tags associated with the brick:Zone_Air_Temperature_Sensor class, execute the following query:

**P2** (score 4; Papers / Fierro et al. 2020, Formalizing Tag-Based Metadata With the Brick Ontology (Frontiers in Big Data) :: 1 Referred to as “Haystack” in the rest of the paper.; c55.s2#17)

> The most common types of semantic conflicts concern process tags and substance tags.
> We explore how ambiguities arise for these two family of tags; section 4 demonstrates how Brick handles these issues.
> Process Tags.
> For a metadata scheme to consistently describe a process, it must decompose a process into entities and capture how each entity relates to the process: does the entity monitor or control the process?
> Does it transport a substance or provide a means for two substances to interact?
> It is difficult for a limited dictionary of tags to capture unambiguously the family of concepts involved.
> Consider the case of an air handling unit that heats air by passing it around a coil of hot water.
> With a limited dictionary of tags, most of the entities (equipment and points) involved will be tagged with hot, heat, air and/or water.
> However, a flat set of tags does not permit any differentiation between concepts that share the same tags.

**P3** (score 3; Brick repository v1.4.4 documents / VBIS / Brick Alignment :: VBIS / Brick Alignment; c30.s0#0)

> Aligns concepts in Brick v1.1 with concepts in VBIS v3 ( ).
> Use the alignment file Brick-VBIS-alignment.ttl; import this into your RDF graph in order to realize the mappings between concepts in VBIS and Brick.
> Specifically, the file encodes which VBIS search tags are relevant for many different Brick equipment classes.
> The VBIS search tags are encoded as string literals and are related to Brick classes through the ` property.

## CQB19 [slots_facets] Which property attaches a unit to a Quantity or Point?

- grounding: `prop:hasUnit`; anchors ['hasUnit']; L0=True L1=True (sections 2) L2=True (best answer-term fraction 0.6)
- expected_answer (bank): brick:hasUnit (often via brick:hasQUDTReference to QUDT units).

**P1** (score 5; Brick developer documentation (docs.brickschema.org) / Entity Properties :: Area of a Room; c13.s2#1)

> The model here is relatively straight forward. The area is a (usually anonymous) Brick entity with a numerical value (indicated by brick:value) and a unit (indicated by brick:hasUnit). The area entity is associated with a Brick room through the brick:area property.

**P2** (score 5; Brick developer documentation (docs.brickschema.org) / Modeling Data Sources :: Units of Measure; c4.s3#1)

> Units of measures are instances of the qudt:Unit class, and are represented by URIs such as unit:DEG_F and unit:PPM. Units are associated with Brick Points with the brick:hasUnit relationship:

**P3** (score 5; Brick developer documentation (docs.brickschema.org) / Modeling Data Sources :: Units of Measure; c4.s3#2)

> A list of available units can be found here. Given a Brick Point instance, it is possible to query for valid potential units. The ?unit values returned by this query can be associated with a Point instance using the brick:hasUnit relationship as seen above.

## CQB20 [slots_facets] Where is the most recent observed value of a Point stored?

- grounding: `prop:lastKnownValue`; anchors ['lastKnownValue']; L0=True L1=True (sections 1) L2=False (best answer-term fraction 0.25)
- expected_answer (bank): brick:lastKnownValue linking to a Value/observation node.

**P1** (score 5; Brick website (brickschema.org) / Release Notes :: v1.3.0; c40.s0#1)

> The big features in Brick v1.3.0 are:
> - moving from an OWL-based ontology to a SHACL-based ontology. This allows Brick and Brick tooling to make use of the validation features of SHACL, which will help to ensure that Brick models are consistent and valid. We recommend using the pySHACL project to conduct validation of Brick models. The brickschema package also provides support for validation
> - ref:hasExternalReference is a new relationship that relates Brick entities to their representations in other digital forms, for example IFC models, BACnet networks and timeseries databases. This builds on work on the ref-schema, a new RDF schema for standardizing these external references
> - ability to model meter/submeter hierarchies, their relationships to devices and rooms, and the data they produce
> - ability to model the current value of Points, using brick:lastKnownValue
> - dramatically expanded sets of entity properties, capturing "nameplate" and other static characteristics of Brick entities

**P2** (score 2; Brick developer documentation (docs.brickschema.org) / Core Concepts :: Entity; c1.s1#1)

> Virtual entities are anything whose representation is based in software.
> Examples are sensing and status points which allow software to read the current state of the world (such as the value of a temperature sensor, the speed of a fan, or the energy consumption of a space heater), and actuation points which allow software to write values (such as temperature setpoints or the brightness of a lighting fixture).

**P3** (score 2; Brick developer documentation (docs.brickschema.org) / Entity Properties :: Entity Properties; c13.s0#0)

> This feature is new in Brick v1.2
> Entity Properties are attributes or characteristics of Brick entities. The values of Entity Properties should change rarely, if ever; if a value is changing regularly, then it is likely better modeled as a Brick Point. Entity properties are useful for modeling static charcteristics such as:
> - floor area, room volume
> - phase count, phases, and flow of electric meters
> - which operational stage a point is associated with
> - how the values of a given Point are aggregated
> - and many others!

## CQB21 [slots_facets] Which property records a building's gross floor area?

- grounding: `skos:definition brick:grossArea`; anchors ['grossArea']; L0=False L1=False (sections 0) L2=False (best answer-term fraction 0.0)
- expected_answer (bank): brick:grossArea; an owl:ObjectProperty and brick:EntityProperty. Definition: 'Entity has gross 2-dimensional area.'

**P1** (score 3; Brick website (brickschema.org) / Release Notes :: v1.2.0; c39.s2#2)

> - Namespace change (hopefully for the last time): to facilitate future development of Brick, Brick is changing its namespace to no longer contain a version number. Brick can still be downloaded on a per-version basis in the future, but to aid in the adoption of future (backwards-compatible) versions of Brick, it was decided that the best course of action was to remove the need to increment version numbers. This way, only a new copy of the Brick graph needs to be loaded in order to upgrade
> - Old namespace (v1.1.x): `
> - New namespace (v1.2.x and onward): `
> - Entity Properties: entity properties are a new Brick feature (described in-depth here) that allow models to attach static properties to Brick entities. The initial release of entity properties include floor area (net and gross), electrical metering properties, and aggregations. Documentation for entity properties on the Brick website is coming soon

**P2** (score 2; Brick developer documentation (docs.brickschema.org) / Core Concepts :: Entity; c1.s1#0)

> An entity is an abstraction of any physical, logical or virtual item; the actual "things" in a building.
> Physical entities are anything that has a physical presence in the world.
> Examples are mechanical equipment such as air handling units, variable air volume boxes, luminaires and lighting systems, networked devices like electric meters, thermostats and electrical vehicle chargers, and spatial elements like rooms and floors.

**P3** (score 2; Brick developer documentation (docs.brickschema.org) / Entity Properties :: Entity Properties; c13.s0#0)

> This feature is new in Brick v1.2
> Entity Properties are attributes or characteristics of Brick entities. The values of Entity Properties should change rarely, if ever; if a value is changing regularly, then it is likely better modeled as a Brick Point. Entity properties are useful for modeling static charcteristics such as:
> - floor area, room volume
> - phase count, phases, and flow of electric meters
> - which operational stage a point is associated with
> - how the values of a given Point are aggregated
> - and many others!

## CQB22 [slots_facets] Which property states the primary function of a Building?

- grounding: `prop:buildingPrimaryFunction`; anchors ['buildingPrimaryFunction']; L0=False L1=False (sections 0) L2=False (best answer-term fraction 0.0)
- expected_answer (bank): brick:buildingPrimaryFunction.

**P1** (score 2; Brick developer documentation (docs.brickschema.org) / Timeseries Storage :: Timeseries Storage; c16.s0#1)

> The ref:hasExternalReference property relates a Brick Point instance to a ref:TimeseriesReference object. This object has exactly one ref:hasTimeseriesId property, whose value is a string denoting the identifier or primary key of the instance's data in some database. The database itself is realized as an object and is related to the ref:TimeseriesReference through the ref:storedAt property.

**P2** (score 2; Brick developer documentation (docs.brickschema.org) / Meters :: Virtual Meters; c20.s3#0)

> It is useful to be able to model "virtual" meters which do not have a physical presence in the building.
> Brick supports modeling "virtual" meters using the brick:isVirtualMeter Entity Property.
> This property can only be "true" for instances of brick:Meter or subclasses thereof.

**P3** (score 2; Brick developer documentation (docs.brickschema.org) / Relationships :: Definitions; c3.s0#0)

> An Entity is a digital representation of any physical, logical or virtual item; the actual "things" in and around a building. Brick defines how entities can be classified and related to one another. There are several flavors of entities:
> - Physical Entities: anything that has a physical presence in the world. Examples are:
> - mechanical equipment such as air handling units, variable air volume boxes, luminaires and lighting systems
> - networked devices like electric meters, thermostats, electric vehicle chargers
> - spatial elements like buildings, floors and rooms
> - Virtual Entities: anything whose representation is based in software. Examples are:
> - sensing and status points which allow software to read the current state of the world (such as the value of a temperature sensor, the speed of a fan or the energy consumption of a space heater)
> - actuation points which allow software to write values (such as temperature setpoints or brightness of a lighting fixture)

## CQB23 [slots_facets] Which property records when something was built?

- grounding: `skos:definition brick:yearBuilt`; anchors ['yearBuilt']; L0=False L1=False (sections 0) L2=False (best answer-term fraction 0.0)
- expected_answer (bank): brick:yearBuilt; an owl:ObjectProperty and brick:EntityProperty. Definition: 'Four digit year that a building was first built. (adopted from Project Haystack)'

**P1** (score 1; Brick developer documentation (docs.brickschema.org) / Aliases and Equivalent Classes :: Aliases; c0.s1#0)

> Aliases identify the preferred class among a set of interchangeable (equivalent) classes.
> Non-preferred classes will have a brick:aliasOf property which indicates the preferred class.

**P2** (score 1; Brick developer documentation (docs.brickschema.org) / Aliases and Equivalent Classes :: Aliases; c0.s1#1)

> See below a snippet of Brick 1.4 containing definitions of AHU, Air_Handler_Unit and Air_Handling_Unit. Only brick:Air_Handling_Unit is missing the brick:aliasOf property, so it is the preferred class. The other classes have a brick:aliasOf property pointing to this preferred class.

**P3** (score 1; Brick developer documentation (docs.brickschema.org) / Aliases and Equivalent Classes :: Equivalent Classes; c0.s4#0)

> Groups of duplicate classes (e.g., AHU, Air_Handler_Unit and Air_Handling_Unit) will also be marked as equivalent classes using the owl:equivalentClass property.
> There are two SHACL rules in Brick (bsh:OWLEquivalentClassRule1 and bsh:OWLEquivalentClassRule2) which handle the semantics of equivalent classes: when SHACL inference is run on a Brick model, these rules will add all the equivalent classes to each entity.

## CQB24 [slots_facets] How is a Point linked to the quantity it measures?

- grounding: `prop:hasQuantity`; anchors ['hasQuantity']; L0=True L1=True (sections 1) L2=True (best answer-term fraction 0.667)
- expected_answer (bank): brick:hasQuantity to brick:Quantity/QUDT quantity kinds.

**P1** (score 4; Brick website (brickschema.org) / Release Notes :: v1.3.0; c40.s0#2)

> - adding useful semantic annotations to all Brick Point classes with the brick:hasSubstance and brick:hasQuantity properties
> - unit tests added to all Brick examples to ensure they are up-to-date with correct Brick usage
> - additional classes covering, among other things, different kinds of fans, sensors, PV systems
> - return/supply/discharge water have been swapped for entering (return) and leaving (supply/discharge) water
> - instances of deprecated concepts are now marked with warnings during SHACL validation
> Many of these major features are documented at .

**P2** (score 2; Brick developer documentation (docs.brickschema.org) / External Representation :: BACnet; c14.s1#0)

> The BACnet reference object is linked to a Brick Point with the ref:hasExternalReference relationship pointing to a ref:BACnetReference object.
> There are two possible forms of the BACnet reference object:

**P3** (score 2; Brick developer documentation (docs.brickschema.org) / Meters :: Meters; c20.s0#0)

> This feature is new in Brick v1.3
> Brick provides a basic but flexible model for describing meters, submeter hierarchies, and their relationships to the building.
> Meters are equipment (they are subclasses of the Brick Equipment class) that measure the consumption or production of energy, steam, gas or other "substances" in the building.
> The data produced by meters can be found in instances of the Brick Point class that are associated with the Meter.
> These include power, energy, water and gas consumption sensors and the like.

## CQB25 [instances] Which entities does the rec:BuildingElement definition list as examples?

- grounding: `rdfs:comment rec:BuildingElement`; anchors ['BuildingElement']; L0=False L1=False (sections 0) L2=False (best answer-term fraction 0.0)
- expected_answer (bank): Facade, Wall, Slab, Roof.

**P1** (score 5; Brick developer documentation (docs.brickschema.org) / Relationships :: Definitions; c3.s0#0)

> An Entity is a digital representation of any physical, logical or virtual item; the actual "things" in and around a building. Brick defines how entities can be classified and related to one another. There are several flavors of entities:
> - Physical Entities: anything that has a physical presence in the world. Examples are:
> - mechanical equipment such as air handling units, variable air volume boxes, luminaires and lighting systems
> - networked devices like electric meters, thermostats, electric vehicle chargers
> - spatial elements like buildings, floors and rooms
> - Virtual Entities: anything whose representation is based in software. Examples are:
> - sensing and status points which allow software to read the current state of the world (such as the value of a temperature sensor, the speed of a fan or the energy consumption of a space heater)
> - actuation points which allow software to write values (such as temperature setpoints or brightness of a lighting fixture)

**P2** (score 5; Brick website (brickschema.org) / Definitions :: Definitions; c52.s0#0)

> An Entity is a digital representation of any physical, logical or virtual item; the actual "things" in and around a building. Brick defines how entities can be classified and related to one another. There are several flavors of entities:
> - Physical Entities: anything that has a physical presence in the world. Examples are:
> - mechanical equipment such as air handling units, variable air volume boxes, luminaires and lighting systems
> - networked devices like electric meters, thermostats, electric vehicle chargers
> - spatial elements like buildings, floors and rooms
> - Virtual Entities: anything whose representation is based in software. Examples are:
> - sensing and status points which allow software to read the current state of the world (such as the value of a temperature sensor, the speed of a fan or the energy consumption of a space heater)
> - actuation points which allow software to write values (such as temperature setpoints or brightness of a lighting fixture)

**P3** (score 4; Brick developer documentation (docs.brickschema.org) / Core Concepts :: Entity; c1.s1#0)

> An entity is an abstraction of any physical, logical or virtual item; the actual "things" in a building.
> Physical entities are anything that has a physical presence in the world.
> Examples are mechanical equipment such as air handling units, variable air volume boxes, luminaires and lighting systems, networked devices like electric meters, thermostats and electrical vehicle chargers, and spatial elements like rooms and floors.

## CQB26 [instances] Which events does the rec:Event definition give as examples?

- grounding: `rdfs:comment rec:Event`; anchors ['Event']; L0=True L1=True (sections 1) L2=False (best answer-term fraction 0.0)
- expected_answer (bank): An observation, a lease, a construction project; may be instantaneous or have temporal extent.

**P1** (score 4; Brick website (brickschema.org) / Table of Contents :: 2020; c53.s4#0)

> Shepherding Metadata Through the Building Lifecycle
> Gabe Fierro, Anand Krishnan Prakash, Cory Mosiman, Marco Pritoni, Paul Raftery, Michael Wetter, David E Culler. In Proceedings of the 7th ACM International Conference on Systems for Energy-Efficient Buildings, Cities, and Transportation (BuildSys 2020). November 18, 2020, Virtual Event.
> DOI:

**P2** (score 4; Brick website (brickschema.org) / Table of Contents :: 2020; c53.s4#1)

> Demo Abstract: Interactive Metadata Integration with Brick
> Gabe Fierro, Anand Krishnan Prakash, Cory Mosiman, Marco Pritoni, Paul Raftery, Michael Wetter, David E Culler. In Proceedings of the 7th ACM International Conference on Systems for Energy-Efficient Buildings, Cities, and Transportation (BuildSys 2020). November 18, 2020, Virtual Event.
> DOI:

**P3** (score 2; Brick repository v1.4.4 documents / Contributing to Brick :: Reporting Bugs and Issues; c25.s2#1)

> Bug reports are most helpful when they fully explain the problem and include as many details as possible.
> Some suggestions:
> - Use a clear and descriptive title for the issue that identifies the problem
> - Include as many details as possible about the problem, including any relevant Brick/SPARQL queries, RDF triples, segments of Turtle files, Python code, etc
> - Describe the observed and expected behavior: for example, what query did you run, what were the results, and what did you expect the results to be? What definition exists and what definition would you expect?
> - Describe the exact steps to reproducing the problem where it is appropriate: did you execute a query and
> - Make sure you are using the most recent version of the Brick repository

## CQB27 [instances] What does rec:PointEvent exemplify?

- grounding: `rdfs:comment rec:PointEvent`; anchors ['PointEvent']; L0=False L1=False (sections 0) L2=False (best answer-term fraction 0.0)
- expected_answer (bank): An event emanating from or targeting a Point; e.g. an individual Observation from a Sensor point, or an Actuation sent to a Command point.

**P1** (score 1; Brick developer documentation (docs.brickschema.org) / Core Concepts :: Entity; c1.s1#1)

> Virtual entities are anything whose representation is based in software.
> Examples are sensing and status points which allow software to read the current state of the world (such as the value of a temperature sensor, the speed of a fan, or the energy consumption of a space heater), and actuation points which allow software to write values (such as temperature setpoints or the brightness of a lighting fixture).

**P2** (score 1; Brick developer documentation (docs.brickschema.org) / Core Concepts :: Brick Model; c1.s6#1)

> The blue nodes represent entities that are instances of Brick classes.These are the "things" inside our example building. They range from equipment (AHU1A, VAV2-4), points (VAV2-4.DPRPOS), locations (Room 410) and logical collections (VAV2-3Zone). The colored boxes connected to the instances with dashed lines represent Brick classes; the dashed line represents the "is an instance of" relationship (rdf:type). The rest of the class structure has been elided for simplicity. Lastly, the solid directed edges represent Brick relationships between entities.

**P3** (score 1; Brick developer documentation (docs.brickschema.org) / Ontology Versioning :: Ontology Versioning; c12.s0#3)

> Ontology imports are properties of the owl:Ontology entity which point to other graphs via the owl:imports relationship.

## CQB28 [instances] What organizations does the rec:Organization definition cite?

- grounding: `rdfs:comment rec:Organization`; anchors ['Organization']; L0=True L1=True (sections 8) L2=True (best answer-term fraction 0.6)
- expected_answer (bank): A business, association, project, consortium, tribe.

**P1** (score 5; Papers / Fierro et al. 2020, Formalizing Tag-Based Metadata With the Brick Ontology (Frontiers in Big Data) :: 5. BRICK+ IMPLEMENTATION; c55.s6#26)

> Because the Brick+ ontology is meant to generalize to many different kinds of buildings, subsystems, equipment and organizations thereof, the ontology definition makes very few statements about what information is required to be present in a given building instance for it to be considered valid.
> Idioms fill this gap by encoding “best practices” of what should be contained in a given model.

**P2** (score 4; Brick developer documentation (docs.brickschema.org) / Meters :: Associating Meters; c20.s4#2)

> Metering rec:Collections: useful when the Meter is measuring the consumption/production of many entities that are not necessarily grouped by location. Recall that a rec:Collection is a named group of entities. This could represent the equipment in a particular air loop, in a particular chilled water system, all of the devices owned by a particular individual, or any other organization.

**P3** (score 4; Brick developer documentation (docs.brickschema.org) / Automation and Point Collections :: Relationship Roles; c21.s3#0)

> Use collection membership for organization, and use the normal Brick relationships for the model semantics:
> - Use rec:includes to put an entity into an Automation Collection or Point Collection.
> - Use brick:hasPart for physical or structural composition, such as an AHU having a fan or coil.
> - Use brick:hasPoint / brick:isPointOf to attach a point to the equipment, location, or zone it describes.
> - Use brick:hostsPoint / brick:isHostedBy to describe the ICT equipment, controller, gateway, or device that hosts or exposes a point.
> - Use brick:controls / brick:isControlledBy for control relationships between controllers and the equipment they supervise.

## CQB29 [instances] What containment example does the rec:Space definition give?

- grounding: `rdfs:comment rec:Space`; anchors ['Space']; L0=True L1=True (sections 16) L2=True (best answer-term fraction 0.833)
- expected_answer (bank): A Region can contain many Sites, which in turn can contain many Buildings.

**P1** (score 6; Brick developer documentation (docs.brickschema.org) / Relationships :: Definitions; c3.s0#0)

> An Entity is a digital representation of any physical, logical or virtual item; the actual "things" in and around a building. Brick defines how entities can be classified and related to one another. There are several flavors of entities:
> - Physical Entities: anything that has a physical presence in the world. Examples are:
> - mechanical equipment such as air handling units, variable air volume boxes, luminaires and lighting systems
> - networked devices like electric meters, thermostats, electric vehicle chargers
> - spatial elements like buildings, floors and rooms
> - Virtual Entities: anything whose representation is based in software. Examples are:
> - sensing and status points which allow software to read the current state of the world (such as the value of a temperature sensor, the speed of a fan or the energy consumption of a space heater)
> - actuation points which allow software to write values (such as temperature setpoints or brightness of a lighting fixture)

**P2** (score 6; Brick website (brickschema.org) / Definitions :: Definitions; c52.s0#0)

> An Entity is a digital representation of any physical, logical or virtual item; the actual "things" in and around a building. Brick defines how entities can be classified and related to one another. There are several flavors of entities:
> - Physical Entities: anything that has a physical presence in the world. Examples are:
> - mechanical equipment such as air handling units, variable air volume boxes, luminaires and lighting systems
> - networked devices like electric meters, thermostats, electric vehicle chargers
> - spatial elements like buildings, floors and rooms
> - Virtual Entities: anything whose representation is based in software. Examples are:
> - sensing and status points which allow software to read the current state of the world (such as the value of a temperature sensor, the speed of a fan or the energy consumption of a space heater)
> - actuation points which allow software to write values (such as temperature setpoints or brightness of a lighting fixture)

**P3** (score 5; Brick developer documentation (docs.brickschema.org) / Core Concepts :: Entity; c1.s1#1)

> Virtual entities are anything whose representation is based in software.
> Examples are sensing and status points which allow software to read the current state of the world (such as the value of a temperature sensor, the speed of a fan, or the energy consumption of a space heater), and actuation points which allow software to write values (such as temperature setpoints or the brightness of a lighting fixture).

## CQB30 [instances] What does the rec:Portfolio definition list as groupable members?

- grounding: `rdfs:comment rec:Portfolio`; anchors ['Portfolio']; L0=True L1=True (sections 3) L2=False (best answer-term fraction 0.357)
- expected_answer (bank): Buildings, sites, apartments, campuses sharing a business-relevant commonality (same manager, same tenant, shared utilization or legal definition).

**P1** (score 5; Brick website (brickschema.org) / new members press release :: new members press release; c33.s0#14)

> With a history of more than 135 years of innovation, Johnson Controls delivers the blueprint of the future for industries such as healthcare, schools, data centers, airports, stadiums, manufacturing and beyond through its comprehensive digital offering, OpenBlue. With a global team of 100,000 experts in more than 150 countries, Johnson Controls offers the world&#39;s largest portfolio of building technology, software as well as service solutions with some of the most trusted names in the industry. For more information, visit or follow us @johnsoncontrols on Twitter.

**P2** (score 4; Brick developer documentation (docs.brickschema.org) / Collections, Systems and Loops :: Collections, Systems and Loops; c17.s0#1)

> Brick defines multiple kinds of collections and allows modelers to create their own.
> Examples of Brick collections include:
> - Portfolio: a group of brick:Site
> - Loop: a group of brick:Equipment and brick:Point
> - System: a group of brick:Equipment, brick:Point and brick:Loop
> - Photovoltaic Array: a group of brick:PV_Panel

**P3** (score 4; Brick developer documentation (docs.brickschema.org) / Collections, Systems and Loops :: Collections, Systems and Loops; c17.s0#2)

> Several kinds of systems are also defined, including brick:Lighting_System, brick:HVAC_System, brick:Chilled_Water_System and brick:Energy_Generation_System.
> Typically, collections can only contain equipment and points. The main exception is a Portfolio which can only contain brick:Site.

## CQB31 [methodology] How does the schema advise handling rec:ArchitectureArea measurements?

- grounding: `rdfs:comment rec:ArchitectureArea`; anchors ['ArchitectureArea']; L0=False L1=False (sections 0) L2=False (best answer-term fraction 0.0)
- expected_answer (bank): Requirements vary case to case and jurisdiction to jurisdiction, so subclassing and specializing the definition is encouraged.

**P1** (score 2; Brick website (brickschema.org) / The Brick Consortium :: The Technical Committee, Technical Services Committee, and Communications Committee; c49.s3#0)

> The main work of the Brick Consortium is managed by three committees.
> The Technical Committee oversees the development of the Brick Schema.
> The Technical Committee, from time to time, determines when the Brick Schema should be put out to the full Consortium membership for a vote for a new release.
> The Technical Committee can also propose new areas for the Consortium to work in, subject to approval by the Steering Committee.

**P2** (score 1; Brick developer documentation (docs.brickschema.org) / Aliases and Equivalent Classes :: Aliases and Equivalent Classes; c0.s0#0)

> This feature was introduced in Brick v1.4.
> Over its history, Brick has accumulated several duplicate class names. For example: brick:AHU, brick:Air_Handler_Unit and brick:Air_Handling_Unit can all be found in the Brick 1.4 release.
> Brick retains all of these classes for backwards-compatibility; however, in Brick 1.4 it became necessary to denote a preferred class among a set of interchangeable classes.
> At the same time, downstream tools and consumers should remain agnostic to whichever class was chosen by a modeler.
> Brick handles both of these features through two mechanisms: equivalent classes and aliases.

**P3** (score 1; Brick developer documentation (docs.brickschema.org) / Aliases and Equivalent Classes :: Aliases; c0.s1#1)

> See below a snippet of Brick 1.4 containing definitions of AHU, Air_Handler_Unit and Air_Handling_Unit. Only brick:Air_Handling_Unit is missing the brick:aliasOf property, so it is the preferred class. The other classes have a brick:aliasOf property pointing to this preferred class.

## CQB32 [methodology] How should deprecated terms be handled in Brick?

- grounding: `prop:deprecation`; anchors ['deprecation']; L0=True L1=True (sections 1) L2=False (best answer-term fraction 0.429)
- expected_answer (bank): brick:deprecation + brick:isReplacedBy + deprecationMitigationRule point to replacement terms.

**P1** (score 5; Brick developer documentation (docs.brickschema.org) / Using Brick and RealEstateCore Together :: Locations; c5.s1#0)

> All Brick Location classes have been deprecated as of 1.4 and replaced with equivalents in RealEstateCore.
> These deprecations appear like this in the Turtle file:

**P2** (score 2; Brick developer documentation (docs.brickschema.org) / Using Tags :: Using Tags; c15.s0#0)

> A tag is an atomic term that is used to annotate an entity in a Brick model.
> The set of tags associated with a Brick entity can be queried by users and applications; Brick also supports the automatic association of tags with entities based on which Brick class they are an instance of.

**P3** (score 2; Brick developer documentation (docs.brickschema.org) / Collections, Systems and Loops :: Custom Collections; c17.s2#0)

> As of Brick v1.5, custom collections use rec:Collection and rec:includes. The brick:Collection class is deprecated.
> It is possible for a modeler to create their own ad-hoc collections, depending on how they want to organize entities in the model. The generic rec:Collection class is available for this purpose.
> These can be created by instantiating a new entity that is of type rec:Collection; it is recommended to use rdfs:label to name the collection.

## CQB33 [methodology] How is a virtual metering hierarchy modeled?

- grounding: `prop:hasSubMeter`; anchors ['hasSubMeter']; L0=True L1=True (sections 1) L2=False (best answer-term fraction 0.25)
- expected_answer (bank): brick:hasSubMeter/isSubMeterOf plus brick:isVirtualMeter flag.

**P1** (score 3; Brick developer documentation (docs.brickschema.org) / Meters :: Meters and Submeters; c20.s2#0)

> Meters are instances of the brick:Meter class or any of its subclasses.
> Submeter hierarchies are defined through the brick:hasSubMeter and brick:isSubMeterOf relationships.
> In fact, meters can only be related to each other via these relationships.

**P2** (score 1; Brick developer documentation (docs.brickschema.org) / Core Concepts :: Entity; c1.s1#0)

> An entity is an abstraction of any physical, logical or virtual item; the actual "things" in a building.
> Physical entities are anything that has a physical presence in the world.
> Examples are mechanical equipment such as air handling units, variable air volume boxes, luminaires and lighting systems, networked devices like electric meters, thermostats and electrical vehicle chargers, and spatial elements like rooms and floors.

**P3** (score 1; Brick developer documentation (docs.brickschema.org) / Core Concepts :: Entity; c1.s1#1)

> Virtual entities are anything whose representation is based in software.
> Examples are sensing and status points which allow software to read the current state of the world (such as the value of a temperature sensor, the speed of a fan, or the energy consumption of a space heater), and actuation points which allow software to write values (such as temperature setpoints or the brightness of a lighting fixture).

## CQB34 [methodology] When should a rec:Collection be used?

- grounding: `rdfs:comment rec:Collection`; anchors ['Collection']; L0=True L1=True (sections 29) L2=False (best answer-term fraction 0.417)
- expected_answer (bank): For an administrative grouping of entities addressed and treated as a unit; spatial contiguity is possible but not required (e.g. a distributed campus).

**P1** (score 4; Brick developer documentation (docs.brickschema.org) / Core Concepts :: Entity; c1.s1#2)

> Logical entities are those entities or collections of entities that are defined by a set of rules.
> Examples are HVAC zones and Lighting zones.
> Concepts such as class names and tags (defined below) also fall into this category.

**P2** (score 4; Brick developer documentation (docs.brickschema.org) / Core Concepts :: Brick Model; c1.s6#1)

> The blue nodes represent entities that are instances of Brick classes.These are the "things" inside our example building. They range from equipment (AHU1A, VAV2-4), points (VAV2-4.DPRPOS), locations (Room 410) and logical collections (VAV2-3Zone). The colored boxes connected to the instances with dashed lines represent Brick classes; the dashed line represents the "is an instance of" relationship (rdf:type). The rest of the class structure has been elided for simplicity. Lastly, the solid directed edges represent Brick relationships between entities.

**P3** (score 4; Brick developer documentation (docs.brickschema.org) / Collections, Systems and Loops :: Collections, Systems and Loops; c17.s0#0)

> A collection is a group of related entities, typically organized around a fixed use or function.
> A collection is modeled as an entity which contains other entities; the relationship between a collection and its contents is rec:includes. Collections allow a modeler to associate entities together to make them easier to find later. Systems and Loops are special kinds of Collections.

## CQB35 [methodology] How are measurement quantities represented on Points?

- grounding: `prop:hasQuantity-meth`; anchors ['hasQuantity']; L0=True L1=True (sections 1) L2=False (best answer-term fraction 0.143)
- expected_answer (bank): Via brick:hasQuantity to Quantity subclasses aligned with QUDT (hasQUDTReference), not free text.

**P1** (score 4; Brick website (brickschema.org) / Release Notes :: v1.3.0; c40.s0#2)

> - adding useful semantic annotations to all Brick Point classes with the brick:hasSubstance and brick:hasQuantity properties
> - unit tests added to all Brick examples to ensure they are up-to-date with correct Brick usage
> - additional classes covering, among other things, different kinds of fans, sensors, PV systems
> - return/supply/discharge water have been swapped for entering (return) and leaving (supply/discharge) water
> - instances of deprecated concepts are now marked with warnings during SHACL validation
> Many of these major features are documented at .

**P2** (score 2; Brick developer documentation (docs.brickschema.org) / Software Interfaces for Brick :: Software Interfaces for Brick; c24.s0#1)

> Recall that the intent of a Brick model is to describe the data sources in a building and their context.
> The data sources themselves are represented by instances of the Brick Point class, and the context of these data sources is provided by instances of locations, equipment, systems and other building entities.
> These instances are associated with data sources through Brick relationships.

**P3** (score 2; Brick developer documentation (docs.brickschema.org) / Software Interfaces for Brick :: Software Interfaces for Brick; c24.s0#2)

> This means that a Brick model can be used to find data sources and other entities.
> This is usually done through SPARQL queries against the Brick model graph.
> The information returned by these queries can be used to configure a piece of software.
> For example, a SPARQL query can return:
> - the configuration information required to access live or historical data through a time series database
> - the parameters for accessing an I/O point on a BMS network
> - the parameters for retrieving the geometry of an entity from an IFC model
> See the External Representations section for details and examples of how these references are represented in Brick.

## CQB36 [methodology] Which property links a Brick entity to an external vocabulary reference?

- grounding: `ref:hasExternalReference / brick:hasQUDTReference`; anchors ['hasExternalReference', 'hasQUDTReference']; L0=False L1=False (sections 0) L2=False (best answer-term fraction 0.0)
- expected_answer (bank): ref:hasExternalReference (Brick/ref# namespace) for BACnet/IFC references; brick:hasQUDTReference for QUDT units.

**P1** (score 7; Brick developer documentation (docs.brickschema.org) / Timeseries Storage :: Timeseries Storage; c16.s0#0)

> This feature is new in Brick v1.2
> It is possible to embed within a Brick model the metadata indicating where timeseries data is stored and how particular Points are identified --- this enables the automatic retrieval of timeseries data. This metadata is associated with Brick Point instances, which represent sources of data, through the ref:hasExternalReference property.
> These all use the ref-schema schema for external references; this schema is packaged with the Brick ontology.

**P2** (score 7; Brick website (brickschema.org) / Release Notes :: v1.3.0; c40.s0#1)

> The big features in Brick v1.3.0 are:
> - moving from an OWL-based ontology to a SHACL-based ontology. This allows Brick and Brick tooling to make use of the validation features of SHACL, which will help to ensure that Brick models are consistent and valid. We recommend using the pySHACL project to conduct validation of Brick models. The brickschema package also provides support for validation
> - ref:hasExternalReference is a new relationship that relates Brick entities to their representations in other digital forms, for example IFC models, BACnet networks and timeseries databases. This builds on work on the ref-schema, a new RDF schema for standardizing these external references
> - ability to model meter/submeter hierarchies, their relationships to devices and rooms, and the data they produce
> - ability to model the current value of Points, using brick:lastKnownValue
> - dramatically expanded sets of entity properties, capturing "nameplate" and other static characteristics of Brick entities

**P3** (score 6; Brick developer documentation (docs.brickschema.org) / External Representation :: External Representation; c14.s0#1)

> The generic relationship ref:hasExternalReference can be used to find these other references.
> A Brick Point can have any number of external references.
