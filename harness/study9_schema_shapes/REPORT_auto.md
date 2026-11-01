# Study 9 -- schema-anchored and internal-consistency SHACL shapes (auto-generated)

> AI-generated; review before relying on it. Prereg addendum 39 (`PLAN.md`), post hoc, no model call. Verdict rule (fixed in advance): pass = focus nodes > 0 and violations = 0; focus nodes = 0 -> not applicable (vacuous). Second domain and development corpus: numbers only.

## 1. Shape counts

| Domain | official full set: node shapes / property shapes / minCount>=1 / sh:class / sh:datatype / nodeKind | required pairs |
|---|---|---|
| development | no official ontology | - |
| Brick holdout | 242 / 477 / 207 / 1450 / 613 / 2 | 207 |
| DCAT | 8 / 29 / 14 / 15 / 0 / 1 | 14 |
| SOSA/SSN | 12 / 44 / 11 / 51 / 3 / 0 | 11 |
| PROV | 18 / 75 / 2 / 72 / 5 / 2 | 2 |
| second domain (counts only) | no official ontology | - |

Per-variant shape sets (official: only classes the variant references; internal: from the variant's own declarations):

| Domain | Var | official: refs (R1/R2) / node / prop / minCount>=1 / class / datatype | internal: node / prop / class / datatype / nodeKind / minCount>=1 |
|---|---|---|---|
| development | A | - | 51 / 51 / 94 / 8 / 4 / 0 |
| development | B | - | 0 / 0 / 0 / 0 / 0 / 0 |
| development | C | - | 179 / 179 / 335 / 23 / 0 / 0 |
| development | D | - | 142 / 142 / 263 / 21 / 0 / 0 |
| development | E | - | 134 / 134 / 249 / 19 / 0 / 0 |
| development | F | - | 134 / 134 / 249 / 19 / 0 / 0 |
| Brick holdout | A | 1/1635 / 207 / 414 / 191 / 1335 / 556 | 4 / 4 / 2 / 2 / 0 / 0 |
| Brick holdout | B | 0/1546 / 135 / 278 / 57 / 1283 / 201 | 0 / 0 / 0 / 0 / 0 / 0 |
| Brick holdout | C | 0/1546 / 135 / 278 / 57 / 1283 / 201 | 86 / 86 / 165 / 7 / 0 / 0 |
| Brick holdout | D | 0/1546 / 135 / 278 / 57 / 1283 / 201 | 81 / 81 / 156 / 6 / 0 / 0 |
| Brick holdout | E | 0/1546 / 135 / 278 / 57 / 1283 / 201 | 74 / 74 / 142 / 6 / 0 / 0 |
| Brick holdout | F | 0/1546 / 135 / 278 / 57 / 1283 / 201 | 74 / 74 / 142 / 6 / 0 / 0 |
| DCAT | A | 8/1 / 8 / 29 / 14 / 15 / 0 | 220 / 209 / 406 / 93 / 18 / 0 |
| DCAT | B | 0/9 / 8 / 29 / 14 / 15 / 0 | 0 / 0 / 0 / 0 / 0 / 0 |
| DCAT | C | 0/9 / 8 / 29 / 14 / 15 / 0 | 173 / 173 / 323 / 23 / 0 / 0 |
| DCAT | D | 0/9 / 8 / 29 / 14 / 15 / 0 | 164 / 164 / 311 / 17 / 0 / 0 |
| DCAT | E | 0/9 / 8 / 29 / 14 / 15 / 0 | 158 / 158 / 300 / 16 / 0 / 0 |
| DCAT | F | 0/9 / 8 / 29 / 14 / 15 / 0 | 158 / 158 / 300 / 16 / 0 / 0 |
| SOSA/SSN | A | 11/9 / 12 / 44 / 11 / 51 / 3 | 92 / 90 / 215 / 7 / 0 / 0 |
| SOSA/SSN | B | 0/19 / 12 / 44 / 11 / 51 / 3 | 0 / 0 / 0 / 0 / 0 / 0 |
| SOSA/SSN | C | 0/19 / 12 / 44 / 11 / 51 / 3 | 165 / 165 / 319 / 11 / 0 / 0 |
| SOSA/SSN | D | 0/19 / 12 / 44 / 11 / 51 / 3 | 152 / 152 / 287 / 17 / 0 / 0 |
| SOSA/SSN | E | 0/19 / 12 / 44 / 11 / 51 / 3 | 144 / 144 / 270 / 18 / 0 / 0 |
| SOSA/SSN | F | 0/19 / 12 / 44 / 11 / 51 / 3 | 144 / 144 / 270 / 18 / 0 / 0 |
| PROV | A | 5/26 / 14 / 64 / 0 / 63 / 5 | 191 / 187 / 413 / 40 / 0 / 0 |
| PROV | B | 0/31 / 14 / 64 / 0 / 63 / 5 | 0 / 0 / 0 / 0 / 0 / 0 |
| PROV | C | 0/31 / 14 / 64 / 0 / 63 / 5 | 233 / 233 / 428 / 38 / 0 / 0 |
| PROV | D | 0/31 / 14 / 64 / 0 / 63 / 5 | 217 / 217 / 412 / 22 / 0 / 0 |
| PROV | E | 2/29 / 14 / 64 / 0 / 63 / 5 | 211 / 211 / 400 / 22 / 0 / 0 |
| PROV | F | 2/29 / 14 / 64 / 0 / 63 / 5 | 203 / 203 / 385 / 21 / 0 / 0 |
| second domain (counts only) | A | - | 79 / 79 / 191 / 8 / 0 / 0 |
| second domain (counts only) | B | - | 0 / 0 / 0 / 0 / 0 / 0 |
| second domain (counts only) | C | - | 7 / 7 / 13 / 1 / 0 / 0 |
| second domain (counts only) | B' | - | 0 / 0 / 0 / 0 / 0 / 0 |

## 2. Per variant: official shapes (L1 strict, headline) and internal-consistency shapes

| Domain | Var | triples | official L1: focus / viol / per 1k / verdict | internal: focus / viol / per 1k / verdict | official L2 (punning sens.): focus / viol / verdict |
|---|---|---|---|---|---|
| development | A | 599 | no official ontology | 40 / 73 / 121.87 / fail | - |
| development | B | 4425 | no official ontology | 0 / 0 / 0.00 / NA (vacuous) | - |
| development | C | 6059 | no official ontology | 195 / 205 / 33.83 / fail | - |
| development | D | 5209 | no official ontology | 184 / 174 / 33.40 / fail | - |
| development | E | 5727 | no official ontology | 167 / 141 / 24.62 / fail | - |
| development | F | 5727 | no official ontology | 167 / 141 / 24.62 / fail | - |
| Brick holdout | A | 6841 | 0 / 0 / 0.00 / NA (vacuous) | 0 / 0 / 0.00 / NA (vacuous) | 0 / 0 / NA (vacuous) |
| Brick holdout | B | 35668 | 0 / 0 / 0.00 / NA (vacuous) | 0 / 0 / 0.00 / NA (vacuous) | 2585 / 118 / fail |
| Brick holdout | C | 44796 | 0 / 0 / 0.00 / NA (vacuous) | 1888 / 4708 / 105.10 / fail | 2583 / 118 / fail |
| Brick holdout | D | 44659 | 0 / 0 / 0.00 / NA (vacuous) | 1888 / 4619 / 103.43 / fail | 2583 / 118 / fail |
| Brick holdout | E | 52056 | 0 / 0 / 0.00 / NA (vacuous) | 1525 / 854 / 16.41 / fail | 2764 / 218 / fail |
| Brick holdout | F | 52056 | 0 / 0 / 0.00 / NA (vacuous) | 1525 / 854 / 16.41 / fail | 2764 / 218 / fail |
| DCAT | A | 1877 | 6 / 9 / 4.79 / fail | 21 / 194 / 103.36 / fail | 6 / 9 / fail |
| DCAT | B | 4271 | 0 / 0 / 0.00 / NA (vacuous) | 0 / 0 / 0.00 / NA (vacuous) | 14 / 32 / fail |
| DCAT | C | 5902 | 0 / 0 / 0.00 / NA (vacuous) | 211 / 194 / 32.87 / fail | 14 / 32 / fail |
| DCAT | D | 5766 | 0 / 0 / 0.00 / NA (vacuous) | 206 / 194 / 33.65 / fail | 14 / 32 / fail |
| DCAT | E | 6334 | 0 / 0 / 0.00 / NA (vacuous) | 191 / 167 / 26.37 / fail | 14 / 32 / fail |
| DCAT | F | 6334 | 0 / 0 / 0.00 / NA (vacuous) | 191 / 167 / 26.37 / fail | 14 / 32 / fail |
| SOSA/SSN | A | 2057 | 0 / 0 / 0.00 / NA (vacuous) | 4 / 19 / 9.24 / fail | 0 / 0 / NA (vacuous) |
| SOSA/SSN | B | 5922 | 0 / 0 / 0.00 / NA (vacuous) | 0 / 0 / 0.00 / NA (vacuous) | 32 / 35 / fail |
| SOSA/SSN | C | 7816 | 0 / 0 / 0.00 / NA (vacuous) | 343 / 393 / 50.28 / fail | 32 / 35 / fail |
| SOSA/SSN | D | 7542 | 0 / 0 / 0.00 / NA (vacuous) | 334 / 397 / 52.64 / fail | 32 / 35 / fail |
| SOSA/SSN | E | 8547 | 0 / 0 / 0.00 / NA (vacuous) | 298 / 299 / 34.98 / fail | 32 / 35 / fail |
| SOSA/SSN | F | 8547 | 0 / 0 / 0.00 / NA (vacuous) | 298 / 299 / 34.98 / fail | 32 / 35 / fail |
| PROV | A | 2398 | 5 / 0 / 0.00 / pass | 108 / 369 / 153.88 / fail | 5 / 0 / pass |
| PROV | B | 6015 | 0 / 0 / 0.00 / NA (vacuous) | 0 / 0 / 0.00 / NA (vacuous) | 61 / 0 / pass |
| PROV | C | 8106 | 0 / 0 / 0.00 / NA (vacuous) | 307 / 315 / 38.86 / fail | 61 / 0 / pass |
| PROV | D | 7880 | 0 / 0 / 0.00 / NA (vacuous) | 300 / 318 / 40.36 / fail | 60 / 0 / pass |
| PROV | E | 8719 | 153 / 0 / 0.00 / pass | 284 / 273 / 31.31 / fail | 213 / 0 / pass |
| PROV | F | 8671 | 153 / 0 / 0.00 / pass | 276 / 264 / 30.45 / fail | 213 / 2 / fail |
| second domain (counts only) | A | 769 | no official ontology | 27 / 229 / 297.79 / fail | - |
| second domain (counts only) | B | 365 | no official ontology | 0 / 0 / 0.00 / NA (vacuous) | - |
| second domain (counts only) | C | 364 | no official ontology | 3 / 12 / 32.97 / fail | - |
| second domain (counts only) | B' | 1124 | no official ontology | 0 / 0 / 0.00 / NA (vacuous) | - |

## 3. Top violated constraints (top 5 per variant; public domains with path and shape, others component only)

* **development A internal**: Class x65; Datatype x8
* **development C internal**: Class x205
* **development D internal**: Class x174
* **development E internal**: Class x141
* **development F internal**: Class x141
* **Brick holdout C internal**: Class `p_subclass` x1081; Class (node-level/domain) x875; Class (node-level/domain) x797; Class (node-level/domain) x731; Class `p_define` x479
* **Brick holdout D internal**: Class `p_subclass` x1109; Class (node-level/domain) x879; Class (node-level/domain) x799; Class (node-level/domain) x695; Class `p_define` x467
* **Brick holdout E internal**: Class (node-level/domain) x695; Class (node-level/domain) x63; Class (node-level/domain) x35; Class `p_be` x31; Class `p_measure` x3
* **Brick holdout F internal**: Class (node-level/domain) x695; Class (node-level/domain) x63; Class (node-level/domain) x35; Class `p_be` x31; Class `p_measure` x3
* **DCAT A official L1**: MinCount `description` x4; MinCount `title` x4; MinCount `accessURL` x1
* **DCAT A internal**: Class (node-level/domain) x81; Class `hasEditor` x36; Class (node-level/domain) x9; Class `hasSubClass` x9; Class `hasExtension` x9
* **DCAT C internal**: Class `p_is` x21; Class (node-level/domain) x16; Class `p_include` x10; Class `p_provide` x10; Class `p_represent` x9
* **DCAT D internal**: Class `p_be` x23; Class (node-level/domain) x17; Class `p_represent` x11; Class `p_include` x11; Class `p_provide` x9
* **DCAT E internal**: Class `p_be` x23; Class (node-level/domain) x17; Class `p_represent` x11; Class `p_provide` x9; Class (node-level/domain) x8
* **DCAT F internal**: Class `p_be` x23; Class (node-level/domain) x17; Class `p_represent` x11; Class `p_provide` x9; Class (node-level/domain) x8
* **SOSA/SSN A internal**: Class `isSampleOf` x4; Class `isHostedBy` x3; Class `hasDeployment` x2; Class `hasSubSystem` x2; Class (node-level/domain) x1
* **SOSA/SSN C internal**: Class (node-level/domain) x56; Class `p_is` x38; Class `p_include` x30; Class `p_subclass` x20; Class `p_equivalent-property` x18
* **SOSA/SSN D internal**: Class `p_be` x69; Class (node-level/domain) x53; Class `p_include` x34; Class `p_subclass` x19; Class (node-level/domain) x16
* **SOSA/SSN E internal**: Class `p_be` x69; Class (node-level/domain) x53; Class (node-level/domain) x16; Class `p_equivalent-property` x16; Class (node-level/domain) x12
* **SOSA/SSN F internal**: Class `p_be` x69; Class (node-level/domain) x53; Class (node-level/domain) x16; Class `p_equivalent-property` x16; Class (node-level/domain) x12
* **PROV A internal**: Class (node-level/domain) x35; Class (node-level/domain) x30; Class `hasCorrespondingPROVNProduction` x28; Class `hasCorrespondingPROVOClass` x28; Class (node-level/domain) x21
* **PROV C internal**: Class `p_is` x24; Class (node-level/domain) x19; Class `p_define` x14; Class (node-level/domain) x9; Class (node-level/domain) x7
* **PROV D internal**: Class `p_be` x30; Class (node-level/domain) x24; Class `p_define` x14; Class `p_use` x11; Class (node-level/domain) x10
* **PROV E internal**: Class `p_be` x30; Class (node-level/domain) x24; Class `p_use` x11; Class (node-level/domain) x9; Class `p_provide` x8
* **PROV F internal**: Class `p_be` x30; Class (node-level/domain) x24; Class `p_use` x11; Class (node-level/domain) x9; Class `p_provide` x8
* **second domain (counts only) A internal**: Class x229
* **second domain (counts only) C internal**: Class x12

## 4. Internal-consistency violations by kind

* development A: range_untyped_object 27, domain_untyped_subject 26, domain_wrong_typed_subject 10, range_wrong_datatype_or_kind 8, range_wrong_typed_object 2
* development C: range_wrong_typed_object 104, domain_wrong_typed_subject 101
* development D: domain_wrong_typed_subject 88, range_wrong_typed_object 86
* development E: domain_wrong_typed_subject 74, range_wrong_typed_object 67
* development F: domain_wrong_typed_subject 74, range_wrong_typed_object 67
* Brick holdout C: domain_wrong_typed_subject 2968, range_wrong_typed_object 1740
* Brick holdout D: domain_wrong_typed_subject 2942, range_wrong_typed_object 1677
* Brick holdout E: domain_wrong_typed_subject 802, range_wrong_typed_object 52
* Brick holdout F: domain_wrong_typed_subject 802, range_wrong_typed_object 52
* DCAT A: domain_untyped_subject 99, range_untyped_object 86, domain_wrong_typed_subject 7, range_literal_where_class_expected 2
* DCAT C: range_wrong_typed_object 111, domain_wrong_typed_subject 83
* DCAT D: range_wrong_typed_object 114, domain_wrong_typed_subject 80
* DCAT E: range_wrong_typed_object 98, domain_wrong_typed_subject 69
* DCAT F: range_wrong_typed_object 98, domain_wrong_typed_subject 69
* SOSA/SSN A: range_untyped_object 9, domain_untyped_subject 5, range_wrong_typed_object 4, domain_wrong_typed_subject 1
* SOSA/SSN C: range_wrong_typed_object 210, domain_wrong_typed_subject 183
* SOSA/SSN D: range_wrong_typed_object 228, domain_wrong_typed_subject 169
* SOSA/SSN E: range_wrong_typed_object 163, domain_wrong_typed_subject 136
* SOSA/SSN F: range_wrong_typed_object 163, domain_wrong_typed_subject 136
* PROV A: domain_wrong_typed_subject 119, domain_untyped_subject 118, range_untyped_object 99, range_wrong_typed_object 23, range_literal_where_class_expected 6, range_wrong_datatype_or_kind 4
* PROV C: domain_wrong_typed_subject 159, range_wrong_typed_object 156
* PROV D: range_wrong_typed_object 161, domain_wrong_typed_subject 157
* PROV E: range_wrong_typed_object 137, domain_wrong_typed_subject 136
* PROV F: range_wrong_typed_object 133, domain_wrong_typed_subject 131
* second domain (counts only) A: range_wrong_typed_object 84, domain_wrong_typed_subject 84, range_untyped_object 37, domain_untyped_subject 24
* second domain (counts only) C: range_literal_where_class_expected 7, range_wrong_typed_object 4, domain_wrong_typed_subject 1

## 5. Step 2 -- stage-C artefact (C-F with internal violations)

* **development C**: 47 of 179 declared properties carry >=1 violation (26.3%); top 10 carry 63.9% of attributed violations.
* **development D**: 32 of 142 declared properties carry >=1 violation (22.5%); top 10 carry 73.6% of attributed violations.
* **development E**: 27 of 134 declared properties carry >=1 violation (20.1%); top 10 carry 79.4% of attributed violations.
* **development F**: 27 of 134 declared properties carry >=1 violation (20.1%); top 10 carry 79.4% of attributed violations.
* **Brick holdout C**: 25 of 86 declared properties carry >=1 violation (29.1%); top 10 carry 99.5% of attributed violations.
    * `p_subclass` domain ['Class_artifact'] range ['Class_artifact']: 1980 triples, 1750 subjects, violations {'domain': 875, 'range_class': 1081}, share of subjects typed as declared domain 0.50, actual subject classes [('Class_artifact', 875), ('Class_property', 682), ('Class_class', 124)]
    * `p_define` domain ['Class_artifact'] range ['Class_process']: 969 triples, 965 subjects, violations {'domain': 450, 'range_class': 479}, share of subjects typed as declared domain 0.53, actual subject classes [('Class_artifact', 515), ('Class_property', 351), ('Class_class', 79)]
    * `p_class-schema` domain ['Class_artifact'] range ['Class_concept']: 1398 triples, 1398 subjects, violations {'domain': 731, 'range_class': 152}, share of subjects typed as declared domain 0.48, actual subject classes [('Class_artifact', 667), ('Class_property', 582), ('Class_class', 94)]
    * `p_label` domain ['Class_artifact'] range ['string']: 1640 triples, 1640 subjects, violations {'domain': 797}, share of subjects typed as declared domain 0.51, actual subject classes [('Class_artifact', 843), ('Class_property', 607), ('Class_class', 123)]
    * `p_class` domain ['Class_artifact'] range ['Class_concept']: 112 triples, 112 subjects, violations {'domain': 65}, share of subjects typed as declared domain 0.42, actual subject classes [('Class_artifact', 47), ('Class_property', 42), ('Class_class', 13)]
* **Brick holdout D**: 25 of 81 declared properties carry >=1 violation (30.9%); top 10 carry 99.4% of attributed violations.
    * `p_subclass` domain ['Class_artifact'] range ['Class_artifact']: 1980 triples, 1750 subjects, violations {'domain': 879, 'range_class': 1109}, share of subjects typed as declared domain 0.50, actual subject classes [('Class_artifact', 871), ('Class_property', 694), ('Class_class', 100)]
    * `p_define` domain ['Class_artifact'] range ['Class_process']: 969 triples, 965 subjects, violations {'domain': 449, 'range_class': 467}, share of subjects typed as declared domain 0.53, actual subject classes [('Class_artifact', 516), ('Class_property', 365), ('Class_class', 65)]
    * `p_label` domain ['Class_artifact'] range ['string']: 1639 triples, 1639 subjects, violations {'domain': 799}, share of subjects typed as declared domain 0.51, actual subject classes [('Class_artifact', 840), ('Class_property', 628), ('Class_class', 98)]
    * `p_class-schema` domain ['Class_artifact'] range ['Class_concept']: 1285 triples, 1285 subjects, violations {'domain': 695, 'range_class': 43}, share of subjects typed as declared domain 0.46, actual subject classes [('Class_artifact', 590), ('Class_property', 574), ('Class_class', 67)]
    * `p_be` domain ['Class_property'] range ['Class_property']: 78 triples, 78 subjects, violations {'domain': 35, 'range_class': 31}, share of subjects typed as declared domain 0.55, actual subject classes [('Class_property', 43), ('Class_relation', 30), ('Class_artifact', 4)]
* **Brick holdout E**: 18 of 74 declared properties carry >=1 violation (24.3%); top 10 carry 98.8% of attributed violations.
    * `p_class-schema` domain ['Class_artifact'] range ['string']: 1285 triples, 1285 subjects, violations {'domain': 695}, share of subjects typed as declared domain 0.46, actual subject classes [('Class_artifact', 590), ('Class_property', 574), ('Class_class', 67)]
    * `p_be` domain ['Class_property'] range ['Class_property']: 78 triples, 78 subjects, violations {'domain': 35, 'range_class': 31}, share of subjects typed as declared domain 0.55, actual subject classes [('Class_property', 43), ('Class_relation', 30), ('Class_artifact', 4)]
    * `p_class` domain ['Class_artifact'] range ['Class_concept']: 112 triples, 112 subjects, violations {'domain': 63}, share of subjects typed as declared domain 0.44, actual subject classes [('Class_artifact', 49), ('Class_property', 43), ('Class_class', 12)]
    * `p_inverse` domain ['Class_relation'] range ['Class_relation']: 10 triples, 10 subjects, violations {'domain': 1, 'range_class': 2}, share of subjects typed as declared domain 0.90, actual subject classes [('Class_relation', 9), ('Class_artifact', 1)]
    * `p_represent` domain ['Class_concept'] range ['Class_concept']: 4 triples, 3 subjects, violations {'domain': 2, 'range_class': 1}, share of subjects typed as declared domain 0.33, actual subject classes [('Class_property', 1), ('Class_process', 1), ('Class_concept', 1)]
* **Brick holdout F**: 18 of 74 declared properties carry >=1 violation (24.3%); top 10 carry 98.8% of attributed violations.
    * `p_class-schema` domain ['Class_artifact'] range ['string']: 1285 triples, 1285 subjects, violations {'domain': 695}, share of subjects typed as declared domain 0.46, actual subject classes [('Class_artifact', 590), ('Class_property', 574), ('Class_class', 67)]
    * `p_be` domain ['Class_property'] range ['Class_property']: 78 triples, 78 subjects, violations {'domain': 35, 'range_class': 31}, share of subjects typed as declared domain 0.55, actual subject classes [('Class_property', 43), ('Class_relation', 30), ('Class_artifact', 4)]
    * `p_class` domain ['Class_artifact'] range ['Class_concept']: 112 triples, 112 subjects, violations {'domain': 63}, share of subjects typed as declared domain 0.44, actual subject classes [('Class_artifact', 49), ('Class_property', 43), ('Class_class', 12)]
    * `p_inverse` domain ['Class_relation'] range ['Class_relation']: 10 triples, 10 subjects, violations {'domain': 1, 'range_class': 2}, share of subjects typed as declared domain 0.90, actual subject classes [('Class_relation', 9), ('Class_artifact', 1)]
    * `p_represent` domain ['Class_concept'] range ['Class_concept']: 4 triples, 3 subjects, violations {'domain': 2, 'range_class': 1}, share of subjects typed as declared domain 0.33, actual subject classes [('Class_property', 1), ('Class_process', 1), ('Class_concept', 1)]
* **DCAT C**: 42 of 173 declared properties carry >=1 violation (24.3%); top 10 carry 69.6% of attributed violations.
    * `p_is` domain ['Class_property'] range ['Class_class']: 26 triples, 21 subjects, violations {'domain': 16, 'range_class': 21}, share of subjects typed as declared domain 0.24, actual subject classes [('Class_class', 7), ('Class_property', 5), ('Class_concept', 4)]
    * `p_include` domain ['Class_concept'] range ['Class_property']: 21 triples, 10 subjects, violations {'domain': 8, 'range_class': 10}, share of subjects typed as declared domain 0.20, actual subject classes [('Class_class', 3), ('Class_property', 2), ('Class_concept', 2)]
    * `p_represent` domain ['Class_class'] range ['Class_artifact']: 14 triples, 14 subjects, violations {'domain': 8, 'range_class': 9}, share of subjects typed as declared domain 0.43, actual subject classes [('Class_class', 6), ('Class_artifact', 4), ('Class_property', 2)]
    * `p_provide` domain ['Class_class'] range ['Class_process']: 13 triples, 10 subjects, violations {'domain': 6, 'range_class': 10}, share of subjects typed as declared domain 0.40, actual subject classes [('Class_class', 4), ('Class_artifact', 2), ('Class_relation', 1)]
    * `p_use` domain ['Class_property'] range ['Class_property']: 8 triples, 7 subjects, violations {'domain': 4, 'range_class': 6}, share of subjects typed as declared domain 0.43, actual subject classes [('Class_property', 3), ('Class_class', 2), ('Class_concept', 1)]
* **DCAT D**: 38 of 164 declared properties carry >=1 violation (23.2%); top 10 carry 69.1% of attributed violations.
    * `p_be` domain ['Class_property'] range ['Class_concept']: 30 triples, 25 subjects, violations {'domain': 17, 'range_class': 23}, share of subjects typed as declared domain 0.32, actual subject classes [('Class_property', 8), ('Class_artifact', 5), ('Class_concept', 5)]
    * `p_represent` domain ['Class_class'] range ['Class_property']: 14 triples, 14 subjects, violations {'domain': 8, 'range_class': 11}, share of subjects typed as declared domain 0.43, actual subject classes [('Class_class', 6), ('Class_artifact', 4), ('Class_property', 3)]
    * `p_include` domain ['Class_property'] range ['Class_property']: 21 triples, 10 subjects, violations {'domain': 7, 'range_class': 11}, share of subjects typed as declared domain 0.30, actual subject classes [('Class_class', 4), ('Class_property', 3), ('Class_relation', 1)]
    * `p_provide` domain ['Class_class'] range ['Class_class']: 13 triples, 10 subjects, violations {'domain': 5, 'range_class': 9}, share of subjects typed as declared domain 0.50, actual subject classes [('Class_class', 5), ('Class_artifact', 2), ('Class_relation', 1)]
    * `p_define` domain ['Class_class'] range ['Class_relation']: 7 triples, 7 subjects, violations {'domain': 4, 'range_class': 5}, share of subjects typed as declared domain 0.43, actual subject classes [('Class_class', 3), ('Class_property', 2), ('Class_artifact', 2)]
* **DCAT E**: 36 of 158 declared properties carry >=1 violation (22.8%); top 10 carry 70.1% of attributed violations.
    * `p_be` domain ['Class_property'] range ['Class_concept']: 30 triples, 25 subjects, violations {'domain': 17, 'range_class': 23}, share of subjects typed as declared domain 0.32, actual subject classes [('Class_property', 8), ('Class_artifact', 5), ('Class_concept', 5)]
    * `p_represent` domain ['Class_class'] range ['Class_property']: 14 triples, 14 subjects, violations {'domain': 8, 'range_class': 11}, share of subjects typed as declared domain 0.43, actual subject classes [('Class_class', 6), ('Class_artifact', 4), ('Class_property', 3)]
    * `p_provide` domain ['Class_class'] range ['Class_class']: 13 triples, 10 subjects, violations {'domain': 5, 'range_class': 9}, share of subjects typed as declared domain 0.50, actual subject classes [('Class_class', 5), ('Class_artifact', 2), ('Class_relation', 1)]
    * `p_correspond` domain ['Class_property'] range ['Class_class']: 8 triples, 8 subjects, violations {'domain': 4, 'range_class': 5}, share of subjects typed as declared domain 0.50, actual subject classes [('Class_property', 4), ('Class_artifact', 3), ('Class_process', 1)]
    * `p_use` domain ['Class_class'] range ['Class_property']: 10 triples, 6 subjects, violations {'domain': 5, 'range_class': 4}, share of subjects typed as declared domain 0.17, actual subject classes [('Class_property', 3), ('Class_class', 1), ('Class_artifact', 1)]
* **DCAT F**: 36 of 158 declared properties carry >=1 violation (22.8%); top 10 carry 70.1% of attributed violations.
    * `p_be` domain ['Class_property'] range ['Class_concept']: 30 triples, 25 subjects, violations {'domain': 17, 'range_class': 23}, share of subjects typed as declared domain 0.32, actual subject classes [('Class_property', 8), ('Class_artifact', 5), ('Class_concept', 5)]
    * `p_represent` domain ['Class_class'] range ['Class_property']: 14 triples, 14 subjects, violations {'domain': 8, 'range_class': 11}, share of subjects typed as declared domain 0.43, actual subject classes [('Class_class', 6), ('Class_artifact', 4), ('Class_property', 3)]
    * `p_provide` domain ['Class_class'] range ['Class_class']: 13 triples, 10 subjects, violations {'domain': 5, 'range_class': 9}, share of subjects typed as declared domain 0.50, actual subject classes [('Class_class', 5), ('Class_artifact', 2), ('Class_relation', 1)]
    * `p_correspond` domain ['Class_property'] range ['Class_class']: 8 triples, 8 subjects, violations {'domain': 4, 'range_class': 5}, share of subjects typed as declared domain 0.50, actual subject classes [('Class_property', 4), ('Class_artifact', 3), ('Class_process', 1)]
    * `p_use` domain ['Class_class'] range ['Class_property']: 10 triples, 6 subjects, violations {'domain': 5, 'range_class': 4}, share of subjects typed as declared domain 0.17, actual subject classes [('Class_property', 3), ('Class_class', 1), ('Class_artifact', 1)]
* **SOSA/SSN C**: 51 of 165 declared properties carry >=1 violation (30.9%); top 10 carry 74.6% of attributed violations.
    * `p_is` domain ['Class_property'] range ['Class_relation']: 91 triples, 69 subjects, violations {'domain': 56, 'range_class': 38}, share of subjects typed as declared domain 0.19, actual subject classes [('Class_relation', 22), ('Class_property', 13), ('Class_class', 10)]
    * `p_subclass` domain ['Class_property'] range ['Class_class']: 42 triples, 31 subjects, violations {'domain': 17, 'range_class': 20}, share of subjects typed as declared domain 0.45, actual subject classes [('Class_property', 14), ('Class_class', 8), ('Class_process', 4)]
    * `p_include` domain ['Class_property'] range ['Class_class']: 44 triples, 10 subjects, violations {'domain': 6, 'range_class': 30}, share of subjects typed as declared domain 0.40, actual subject classes [('Class_property', 4), ('Class_artifact', 3), ('Class_process', 1)]
    * `p_equivalent-class` domain ['Class_property'] range ['Class_property']: 28 triples, 28 subjects, violations {'domain': 13, 'range_class': 16}, share of subjects typed as declared domain 0.54, actual subject classes [('Class_property', 15), ('Class_class', 5), ('Class_process', 3)]
    * `p_equivalent-property` domain ['Class_relation'] range ['Class_relation']: 32 triples, 32 subjects, violations {'domain': 9, 'range_class': 18}, share of subjects typed as declared domain 0.72, actual subject classes [('Class_relation', 23), ('Class_property', 6), ('Class_process', 3)]
* **SOSA/SSN D**: 50 of 152 declared properties carry >=1 violation (32.9%); top 10 carry 77.6% of attributed violations.
    * `p_be` domain ['Class_relation'] range ['Class_property']: 101 triples, 76 subjects, violations {'domain': 53, 'range_class': 69}, share of subjects typed as declared domain 0.30, actual subject classes [('Class_relation', 23), ('Class_property', 20), ('Class_class', 9)]
    * `p_include` domain ['Class_property'] range ['Class_process']: 44 triples, 10 subjects, violations {'domain': 6, 'range_class': 34}, share of subjects typed as declared domain 0.40, actual subject classes [('Class_property', 4), ('Class_class', 2), ('Class_artifact', 2)]
    * `p_subclass` domain ['Class_property'] range ['Class_class']: 42 triples, 31 subjects, violations {'domain': 15, 'range_class': 19}, share of subjects typed as declared domain 0.52, actual subject classes [('Class_property', 16), ('Class_class', 7), ('Class_process', 3)]
    * `p_equivalent-property` domain ['Class_relation'] range ['Class_property']: 32 triples, 32 subjects, violations {'domain': 9, 'range_class': 16}, share of subjects typed as declared domain 0.72, actual subject classes [('Class_relation', 23), ('Class_property', 6), ('Class_process', 3)]
    * `p_equivalent-class` domain ['Class_property'] range ['Class_property']: 28 triples, 28 subjects, violations {'domain': 12, 'range_class': 11}, share of subjects typed as declared domain 0.57, actual subject classes [('Class_property', 16), ('Class_class', 9), ('Class_relation', 1)]
* **SOSA/SSN E**: 44 of 144 declared properties carry >=1 violation (30.6%); top 10 carry 78.6% of attributed violations.
    * `p_be` domain ['Class_relation'] range ['Class_property']: 101 triples, 76 subjects, violations {'domain': 53, 'range_class': 69}, share of subjects typed as declared domain 0.30, actual subject classes [('Class_relation', 23), ('Class_property', 20), ('Class_class', 9)]
    * `p_equivalent-property` domain ['Class_relation'] range ['Class_property']: 32 triples, 32 subjects, violations {'domain': 9, 'range_class': 16}, share of subjects typed as declared domain 0.72, actual subject classes [('Class_relation', 23), ('Class_property', 6), ('Class_process', 3)]
    * `p_equivalent-class` domain ['Class_property'] range ['Class_property']: 28 triples, 28 subjects, violations {'domain': 12, 'range_class': 11}, share of subjects typed as declared domain 0.57, actual subject classes [('Class_property', 16), ('Class_class', 9), ('Class_relation', 1)]
    * `p_sub-property` domain ['Class_relation'] range ['Class_relation']: 31 triples, 31 subjects, violations {'domain': 16, 'range_class': 5}, share of subjects typed as declared domain 0.48, actual subject classes [('Class_relation', 15), ('Class_property', 11), ('Class_process', 3)]
    * `p_link` domain ['Class_process'] range ['Class_property']: 11 triples, 8 subjects, violations {'domain': 6, 'range_class': 7}, share of subjects typed as declared domain 0.25, actual subject classes [('Class_concept', 2), ('Class_process', 2), ('Class_relation', 2)]
* **SOSA/SSN F**: 44 of 144 declared properties carry >=1 violation (30.6%); top 10 carry 78.6% of attributed violations.
    * `p_be` domain ['Class_relation'] range ['Class_property']: 101 triples, 76 subjects, violations {'domain': 53, 'range_class': 69}, share of subjects typed as declared domain 0.30, actual subject classes [('Class_relation', 23), ('Class_property', 20), ('Class_class', 9)]
    * `p_equivalent-property` domain ['Class_relation'] range ['Class_property']: 32 triples, 32 subjects, violations {'domain': 9, 'range_class': 16}, share of subjects typed as declared domain 0.72, actual subject classes [('Class_relation', 23), ('Class_property', 6), ('Class_process', 3)]
    * `p_equivalent-class` domain ['Class_property'] range ['Class_property']: 28 triples, 28 subjects, violations {'domain': 12, 'range_class': 11}, share of subjects typed as declared domain 0.57, actual subject classes [('Class_property', 16), ('Class_class', 9), ('Class_relation', 1)]
    * `p_sub-property` domain ['Class_relation'] range ['Class_relation']: 31 triples, 31 subjects, violations {'domain': 16, 'range_class': 5}, share of subjects typed as declared domain 0.48, actual subject classes [('Class_relation', 15), ('Class_property', 11), ('Class_process', 3)]
    * `p_link` domain ['Class_process'] range ['Class_property']: 11 triples, 8 subjects, violations {'domain': 6, 'range_class': 7}, share of subjects typed as declared domain 0.25, actual subject classes [('Class_concept', 2), ('Class_process', 2), ('Class_relation', 2)]
* **PROV C**: 66 of 233 declared properties carry >=1 violation (28.3%); top 10 carry 48.9% of attributed violations.
    * `p_is` domain ['Class_artifact'] range ['Class_process']: 32 triples, 24 subjects, violations {'domain': 19, 'range_class': 24}, share of subjects typed as declared domain 0.21, actual subject classes [('Class_property', 5), ('Class_concept', 5), ('Class_artifact', 5)]
    * `p_define` domain ['Class_concept'] range ['Class_property']: 19 triples, 14 subjects, violations {'domain': 9, 'range_class': 14}, share of subjects typed as declared domain 0.36, actual subject classes [('Class_artifact', 6), ('Class_concept', 5), ('Class_class', 1)]
    * `p_provide` domain ['Class_property'] range ['Class_relation']: 11 triples, 11 subjects, violations {'domain': 7, 'range_class': 7}, share of subjects typed as declared domain 0.36, actual subject classes [('Class_property', 4), ('Class_artifact', 4), ('Class_relation', 2)]
    * `p_describe` domain ['Class_property'] range ['Class_concept']: 10 triples, 10 subjects, violations {'domain': 6, 'range_class': 7}, share of subjects typed as declared domain 0.40, actual subject classes [('Class_property', 4), ('Class_artifact', 2), ('Class_relation', 2)]
    * `p_denote` domain ['Class_relation'] range ['Class_property']: 9 triples, 9 subjects, violations {'domain': 6, 'range_class': 7}, share of subjects typed as declared domain 0.33, actual subject classes [('Class_relation', 3), ('Class_class', 3), ('Class_concept', 3)]
* **PROV D**: 60 of 217 declared properties carry >=1 violation (27.6%); top 10 carry 53.8% of attributed violations.
    * `p_be` domain ['Class_process'] range ['Class_process']: 38 triples, 30 subjects, violations {'domain': 24, 'range_class': 30}, share of subjects typed as declared domain 0.20, actual subject classes [('Class_concept', 7), ('Class_relation', 7), ('Class_process', 6)]
    * `p_define` domain ['Class_artifact'] range ['Class_relation']: 19 triples, 14 subjects, violations {'domain': 10, 'range_class': 14}, share of subjects typed as declared domain 0.29, actual subject classes [('Class_concept', 5), ('Class_artifact', 4), ('Class_class', 2)]
    * `p_use` domain ['Class_process'] range ['Class_example']: 14 triples, 13 subjects, violations {'domain': 9, 'range_class': 11}, share of subjects typed as declared domain 0.31, actual subject classes [('Class_process', 4), ('Class_property', 2), ('Class_class', 2)]
    * `p_provide` domain ['Class_property'] range ['Class_relation']: 11 triples, 11 subjects, violations {'domain': 7, 'range_class': 8}, share of subjects typed as declared domain 0.36, actual subject classes [('Class_property', 4), ('Class_artifact', 3), ('Class_relation', 2)]
    * `p_represent` domain ['Class_class'] range ['Class_process']: 8 triples, 8 subjects, violations {'domain': 5, 'range_class': 6}, share of subjects typed as declared domain 0.38, actual subject classes [('Class_artifact', 3), ('Class_class', 3), ('Class_concept', 2)]
* **PROV E**: 54 of 211 declared properties carry >=1 violation (25.6%); top 10 carry 56.0% of attributed violations.
    * `p_be` domain ['Class_process'] range ['Class_process']: 38 triples, 30 subjects, violations {'domain': 24, 'range_class': 30}, share of subjects typed as declared domain 0.20, actual subject classes [('Class_concept', 7), ('Class_relation', 7), ('Class_process', 6)]
    * `p_use` domain ['Class_process'] range ['Class_example']: 14 triples, 13 subjects, violations {'domain': 9, 'range_class': 11}, share of subjects typed as declared domain 0.31, actual subject classes [('Class_process', 4), ('Class_property', 2), ('Class_class', 2)]
    * `p_provide` domain ['Class_property'] range ['Class_relation']: 11 triples, 11 subjects, violations {'domain': 7, 'range_class': 8}, share of subjects typed as declared domain 0.36, actual subject classes [('Class_property', 4), ('Class_artifact', 3), ('Class_relation', 2)]
    * `p_represent` domain ['Class_class'] range ['Class_process']: 8 triples, 8 subjects, violations {'domain': 5, 'range_class': 6}, share of subjects typed as declared domain 0.38, actual subject classes [('Class_artifact', 3), ('Class_class', 3), ('Class_concept', 2)]
    * `p_describe` domain ['Class_property'] range ['Class_process']: 9 triples, 9 subjects, violations {'domain': 5, 'range_class': 5}, share of subjects typed as declared domain 0.44, actual subject classes [('Class_property', 4), ('Class_artifact', 2), ('Class_relation', 2)]
* **PROV F**: 52 of 203 declared properties carry >=1 violation (25.6%); top 10 carry 57.6% of attributed violations.
    * `p_be` domain ['Class_process'] range ['Class_process']: 38 triples, 30 subjects, violations {'domain': 24, 'range_class': 30}, share of subjects typed as declared domain 0.20, actual subject classes [('Class_concept', 7), ('Class_relation', 7), ('Class_process', 6)]
    * `p_use` domain ['Class_process'] range ['Class_example']: 14 triples, 13 subjects, violations {'domain': 9, 'range_class': 11}, share of subjects typed as declared domain 0.31, actual subject classes [('Class_process', 4), ('Class_property', 2), ('Class_class', 2)]
    * `p_provide` domain ['Class_property'] range ['Class_relation']: 11 triples, 11 subjects, violations {'domain': 7, 'range_class': 8}, share of subjects typed as declared domain 0.36, actual subject classes [('Class_property', 4), ('Class_artifact', 3), ('Class_relation', 2)]
    * `p_represent` domain ['Class_class'] range ['Class_process']: 8 triples, 8 subjects, violations {'domain': 5, 'range_class': 6}, share of subjects typed as declared domain 0.38, actual subject classes [('Class_artifact', 3), ('Class_class', 3), ('Class_concept', 2)]
    * `p_describe` domain ['Class_property'] range ['Class_process']: 9 triples, 9 subjects, violations {'domain': 5, 'range_class': 5}, share of subjects typed as declared domain 0.44, actual subject classes [('Class_property', 4), ('Class_artifact', 2), ('Class_relation', 2)]
* **second domain (counts only) C**: 1 of 7 declared properties carry >=1 violation (14.3%); top 10 carry 100.0% of attributed violations.

## 6. Reading notes (checked against the data)

* Official shapes, L1: under B-F the pipeline's instances carry `ct:` classes, so no node is an instance of an official class: focus nodes = 0 in Brick, DCAT and SOSA/SSN for every variant B-F (and for Brick/SOSA A, whose official classes are declared, not instantiated) -> **not applicable (vacuous)**, not valid. Variant A of DCAT has instances of official classes and fails (missing dct:title / dct:description / dcat:accessURL).
* PROV E and F pass the official shapes with 153 focus nodes; these are the `prov:Entity` chunk nodes (152) and one `prov:Activity` that the pipeline's own PROV stage emits (checked by listing the shapes with focus nodes), i.e. the provenance annotation layer, not the domain concepts. C, D (no PROV stage) are vacuous. PROV A passes on 5 focus nodes.
* L2 (concepts typed by label as instances of official classes) is a sensitivity, not a validation: it makes the shapes applicable and then shows violations dominated by missing required properties (minCount) on label-typed concept nodes, which are class-concepts and not instances.
* Internal consistency (set b) is non-vacuous in every variant that declares domain/range (A, C-F) and fails in every one of them; B declares none (vacuous). Violations are typed-but-wrong (`wrong_typed`), i.e. the declared domain/range is the most frequent class, not the class of all subjects/objects; A (baseline) violations are mostly untyped subjects/objects.
* Counts: violations are counted per (focus node, constraint, value); a node-level domain violation is one result per declared property the node is a subject of.
