# Grounding check -- natural corpus vs frozen bank (addendum 27.4)

Corpus sha256 `b4ce971fc00bab8cfb979aa8010876b872c0af554c345b1f54828e5ace97ea13`; bank sha256 `993c5e1164540dce0f2f9bf2e6ed397cf45910da7889300feeaad6543edb8507`. The analyst read is NOT blind (the reader had the bank's expected answers).

- Automated: L0 (anchors anywhere) 28/36; L1 (anchors in one heading section) 28/36; L2 (L1 + >=50% of answer terms in that section) 16/36.
- Analyst read: full 15, partial 9, none 12 (of 36); answerable (full+partial) = 24/36 = 66.7%.
- Stop rule (answerable share < 20%): **not triggered**.

## By category (analyst read)

| category | full | partial | none |
|---|---:|---:|---:|
| concept_definition | 2 | 0 | 4 |
| taxonomy | 1 | 5 | 0 |
| relations | 6 | 0 | 0 |
| slots_facets | 2 | 2 | 2 |
| instances | 0 | 1 | 5 |
| methodology | 4 | 1 | 1 |

## Per question

| cq | category | L0 | L1 | L2 | analyst | span or near miss |
|---|---|:-:|:-:|:-:|---|---|
| CQB01 | concept_definition | y | y | y | full | Instances of the Brick Point class represent sources or sinks of telemetry. There are several major classes of telemetry in Brick: // Sensor: represents the value of a device or instrument designed to |
| CQB02 | concept_definition | y | y | y | full | Meters are equipment (they are subclasses of the Brick Equipment class) that measure the consumption or production of energy, steam, gas or other "substances" in the building. |
| CQB03 | concept_definition | y | y | y | none |  |
| CQB04 | concept_definition | y | y | n | none |  |
| CQB05 | concept_definition | y | y | n | none |  |
| CQB06 | concept_definition | n | n | n | none |  |
| CQB07 | taxonomy | y | y | y | partial | Instances of the Brick Point class represent sources or sinks of telemetry. There are several major classes of telemetry in Brick: // Sensor: represents the value of a device or instrument designed to |
| CQB08 | taxonomy | y | y | y | full | Instances of the Brick Point class represent sources or sinks of telemetry. There are several major classes of telemetry in Brick: // Sensor: represents the value of a device or instrument designed to |
| CQB09 | taxonomy | y | y | n | partial | Meters are equipment (they are subclasses of the Brick Equipment class) |
| CQB10 | taxonomy | y | y | y | partial | locations can be composed of other locations (e.g. a building is made up of floors and spaces) |
| CQB11 | taxonomy | y | y | y | partial | Sensor: represents the value of a device or instrument designed to detect and measure a variable // Alarm: represents signals that alert an operator to an off-normal condition which requires some form |
| CQB12 | taxonomy | y | y | n | partial | All Brick Location classes have been deprecated as of 1.4 and replaced with equivalents in RealEstateCore. // locations can be composed of other locations (e.g. a building is made up of floors and spa |
| CQB13 | relations | y | y | y | full | hasPoint describes telemetry associated with the equipment: // hasPoint / isPointOf |
| CQB14 | relations | y | y | y | full | hasLocation describes where the equipment is physically located // hasLocation / isLocationOf |
| CQB15 | relations | y | y | y | full | brick:feeds: the subject is arranged upstream of object, implying that some media flows from subject into object. // feeds / isFedBy |
| CQB16 | relations | y | y | y | full | hasPart / isPartOf |
| CQB17 | relations | y | y | n | full | brick:hasLocation / rec:locatedIn |
| CQB18 | relations | y | y | y | full | Tags are related to a Brick class via the brick:hasAssociatedTag relationship. |
| CQB19 | slots_facets | y | y | y | full | Units are associated with Brick Points with the brick:hasUnit relationship: |
| CQB20 | slots_facets | y | y | n | full | ability to model the current value of Points, using brick:lastKnownValue |
| CQB21 | slots_facets | n | n | n | partial | The initial release of entity properties include floor area (net and gross), electrical metering properties, and aggregations. |
| CQB22 | slots_facets | n | n | n | none |  |
| CQB23 | slots_facets | n | n | n | none |  |
| CQB24 | slots_facets | y | y | y | partial | adding useful semantic annotations to all Brick Point classes with the brick:hasSubstance and brick:hasQuantity properties |
| CQB25 | instances | n | n | n | none |  |
| CQB26 | instances | y | y | n | none |  |
| CQB27 | instances | n | n | n | none |  |
| CQB28 | instances | y | y | y | none |  |
| CQB29 | instances | y | y | y | none |  |
| CQB30 | instances | y | y | n | partial | Portfolio: a group of brick:Site |
| CQB31 | methodology | n | n | n | none |  |
| CQB32 | methodology | y | y | n | full | The brick:isReplacedBy property indicates the REC class that should be used in place of the deprecated Brick class. |
| CQB33 | methodology | y | y | n | full | Submeter hierarchies are defined through the brick:hasSubMeter and brick:isSubMeterOf relationships. // Brick supports modeling "virtual" meters using the brick:isVirtualMeter Entity Property. |
| CQB34 | methodology | y | y | n | full | Recall that a rec:Collection is a named group of entities. // Custom collections should now be typed as rec:Collection and use rec:includes to express membership |
| CQB35 | methodology | y | y | n | partial | adding useful semantic annotations to all Brick Point classes with the brick:hasSubstance and brick:hasQuantity properties |
| CQB36 | methodology | n | n | n | full | The generic relationship ref:hasExternalReference can be used to find these other references. // ref:hasExternalReference is a new relationship that relates Brick entities to their representations in  |

S_elig (24): CQB01, CQB02, CQB07, CQB08, CQB09, CQB10, CQB11, CQB12, CQB13, CQB14, CQB15, CQB16, CQB17, CQB18, CQB19, CQB20, CQB21, CQB24, CQB30, CQB32, CQB33, CQB34, CQB35, CQB36

S_elig_L1 (28): CQB01, CQB02, CQB03, CQB04, CQB05, CQB07, CQB08, CQB09, CQB10, CQB11, CQB12, CQB13, CQB14, CQB15, CQB16, CQB17, CQB18, CQB19, CQB20, CQB24, CQB26, CQB28, CQB29, CQB30, CQB32, CQB33, CQB34, CQB35
