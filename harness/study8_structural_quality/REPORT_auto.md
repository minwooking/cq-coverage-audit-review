# Study 8 - independent structural-quality measurements (auto-generated)

AI-generated; review before reliance. Post hoc, exploratory (prereg addendum 38 = `PLAN.md`). No model calls. No threshold or decision is attached to any number. Generated 2026-10-22T02:55:21Z; seed 20260913. Second domain: counts only.

External files (URL, sha256): brick/Brick.ttl `b65720b7b9b6`; dcat-ap-3.0.1/dcat-ap-SHACL.ttl `990d3e42721d`; dcat-ap-3.0.1/ranges.ttl `a6eed0fae8d0`

## Step 1 - external SHACL validation

Focus nodes = distinct nodes of the pipeline graph that a shape's target selects (class targets follow rdfs:subClassOf over graph + official ontology). `constraint` = shapes that carry at least one constraint component (rule-only shapes, e.g. Brick's inference rules, are counted separately). Results whose focus node belongs to the official ontology itself (pulled in as `ont_graph`) are not counted (column `ign`).

| Domain | shapes graph | V | conforms | viol | warn | ign | targeted shapes (constraint) | shapes with focus (constraint) | focus nodes (constraint) | top violated |
|---|---|---|---|---|---|---|---|---|---|---|
| Brick holdout | Brick.ttl (release shapes) | A | yes | 0 | 0 | 3 | 1747 (251) | 3 (0) | 49 (0) | - |
| Brick holdout | Brick.ttl (release shapes) | B | yes | 0 | 0 | 3 | 1747 (251) | 0 (0) | 0 (0) | - |
| Brick holdout | Brick.ttl (release shapes) | C | yes | 0 | 0 | 3 | 1747 (251) | 1 (0) | 86 (0) | - |
| Brick holdout | Brick.ttl (release shapes) | D | yes | 0 | 0 | 3 | 1747 (251) | 1 (0) | 81 (0) | - |
| Brick holdout | Brick.ttl (release shapes) | E | yes | 0 | 0 | 3 | 1747 (251) | 1 (0) | 74 (0) | - |
| Brick holdout | Brick.ttl (release shapes) | F | yes | 0 | 0 | 3 | 1747 (251) | 1 (0) | 74 (0) | - |
| DCAT | DCAT-AP 3.0.1 core | A | no | 33 | 0 | 1 | 33 (33) | 7 (7) | 18 (18) | MinCount description x7; MinCount title x7 |
| DCAT | DCAT-AP 3.0.1 core+ranges | A | no | 33 | 0 | 1 | 35 (35) | 7 (7) | 18 (18) | MinCount description x7; MinCount title x7 |
| DCAT | DCAT-AP 3.0.1 core | B | no | 1 | 0 | 0 | 33 (33) | 2 (2) | 548 (548) | MinCount title x1 |
| DCAT | DCAT-AP 3.0.1 core+ranges | B | no | 1 | 0 | 0 | 35 (35) | 2 (2) | 548 (548) | MinCount title x1 |
| DCAT | DCAT-AP 3.0.1 core | C | no | 1 | 0 | 0 | 33 (33) | 2 (2) | 543 (543) | MinCount title x1 |
| DCAT | DCAT-AP 3.0.1 core+ranges | C | no | 1 | 0 | 0 | 35 (35) | 2 (2) | 543 (543) | MinCount title x1 |
| DCAT | DCAT-AP 3.0.1 core | D | no | 1 | 0 | 0 | 33 (33) | 2 (2) | 534 (534) | MinCount title x1 |
| DCAT | DCAT-AP 3.0.1 core+ranges | D | no | 1 | 0 | 0 | 35 (35) | 2 (2) | 534 (534) | MinCount title x1 |
| DCAT | DCAT-AP 3.0.1 core | E | no | 1 | 0 | 0 | 33 (33) | 3 (3) | 535 (535) | MinCount title x1 |
| DCAT | DCAT-AP 3.0.1 core+ranges | E | no | 1 | 0 | 0 | 35 (35) | 3 (3) | 535 (535) | MinCount title x1 |
| DCAT | DCAT-AP 3.0.1 core | F | no | 1 | 0 | 0 | 33 (33) | 3 (3) | 535 (535) | MinCount title x1 |
| DCAT | DCAT-AP 3.0.1 core+ranges | F | no | 1 | 0 | 0 | 35 (35) | 3 (3) | 535 (535) | MinCount title x1 |

### Are the official shapes non-vacuous? (constraints in the shapes graph itself)

| Domain | shapes graph | node shapes | property shapes | minCount 0 | minCount >= 1 | sh:class | sh:datatype | sh:nodeKind | explicit targets | implicit class targets |
|---|---|---|---|---|---|---|---|---|---|---|
| Brick holdout | Brick.ttl (release shapes) | 1750 | 514 | 1 | 211 | 148 | 138 | 121 | 35 | 1712 |
| DCAT | DCAT-AP 3.0.1 core | 33 | 290 | 0 | 20 | 83 | 6 | 131 | 33 | 0 |
| DCAT | DCAT-AP 3.0.1 core+ranges | 35 | 292 | 0 | 20 | 85 | 6 | 131 | 35 | 0 |

### No official shapes graph

* development: none used.
* SOSA/SSN: none used; `sh:` terms in the official ontology files: 0.
* PROV: none used; `sh:` terms in the official ontology files: 0.
* second domain (counts only): none used.

### The paper's own `shapes_F.ttl` (auto-generated from the graph itself)

| Domain | property constraints with minCount 0 | with minCount >= 1 | nodeKind | datatype | sh:class | node shapes | F conforms (own shapes) |
|---|---|---|---|---|---|---|---|
| development | 194 | 0 | 150 | 44 | 0 | 9 | True |
| Brick holdout | 124 | 0 | 87 | 37 | 0 | 12 | True |
| DCAT | 221 | 0 | 183 | 38 | 0 | 10 | True |
| SOSA/SSN | 213 | 0 | 176 | 37 | 0 | 8 | True |
| PROV | 318 | 0 | 266 | 52 | 0 | 10 | True |

## Step 2 - domain/range quality against official ontologies

Mapped = pipeline property mapped to an official property (levels: alignment file, exact IRI, local name; `ambig` = more than one local-name hit, not mapped). Declared-level categories (domain | range) are exact / subclass / broader / mismatch / non-comparable (generic pipeline class) / official undeclared / not declared, counted over mapped properties only. Usage = triples of mapped properties whose subject/object resolves by label to an official class; `comp` = compatible share among resolved ends, `res` = share of ends that resolve.

| Domain | V | classes | props typed | dom+rng declared | mapped (align/IRI/name) | ambig | unmapped | domain e/s/b/m/nc/ou/nd | range e/s/b/m/nc/ou/nd | usage subj comp (res) | usage obj comp |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Brick holdout | A | 1709 | 199 | 2/4 | 111 (0/0/111) | 11 | 77 | 0/0/1/0/0/0/108 | 2/0/0/0/1/0/0 | - (-) | - |
| Brick holdout | B | 14 | 87 | 0/0 | 3 (2/0/1) | 0 | 84 | 0/0/0/0/0/0/3 | 0/0/0/0/0/0/0 | 100% (79%) | - |
| Brick holdout | C | 10 | 86 | 86/86 | 3 (2/0/1) | 0 | 85 | 0/0/0/0/1/2/0 | 0/0/0/0/0/3/0 | 100% (80%) | - |
| Brick holdout | D | 12 | 81 | 81/81 | 3 (2/0/1) | 0 | 80 | 0/0/0/0/1/2/0 | 0/0/0/0/0/3/0 | 100% (79%) | - |
| Brick holdout | E | 12 | 74 | 74/74 | 1 (0/0/1) | 0 | 75 | 0/0/0/0/1/0/0 | 0/0/0/0/0/1/0 | 100% (100%) | - |
| Brick holdout | F | 12 | 74 | 74/74 | 1 (0/0/1) | 0 | 75 | 0/0/0/0/1/0/0 | 0/0/0/0/0/1/0 | 100% (100%) | - |
| DCAT | A | 85 | 245 | 216/219 | 32 (0/0/32) | 2 | 213 | 3/0/0/0/5/14/10 | 6/4/1/0/2/8/0 | - (-) | - |
| DCAT | B | 8 | 174 | 0/0 | 0 (0/0/0) | 0 | 174 | 0/0/0/0/0/0/0 | 0/0/0/0/0/0/0 | - (-) | - |
| DCAT | C | 9 | 173 | 173/173 | 0 (0/0/0) | 0 | 175 | 0/0/0/0/0/0/0 | 0/0/0/0/0/0/0 | - (-) | - |
| DCAT | D | 10 | 164 | 164/164 | 0 (0/0/0) | 0 | 166 | 0/0/0/0/0/0/0 | 0/0/0/0/0/0/0 | - (-) | - |
| DCAT | E | 10 | 158 | 158/158 | 0 (0/0/0) | 0 | 160 | 0/0/0/0/0/0/0 | 0/0/0/0/0/0/0 | - (-) | - |
| DCAT | F | 10 | 158 | 158/158 | 0 (0/0/0) | 0 | 160 | 0/0/0/0/0/0/0 | 0/0/0/0/0/0/0 | - (-) | - |
| SOSA/SSN | A | 114 | 107 | 93/93 | 54 (0/9/45) | 0 | 67 | 16/0/0/2/7/19/10 | 16/0/0/3/5/20/0 | 50% (65%) | - |
| SOSA/SSN | B | 10 | 167 | 0/0 | 13 (2/0/11) | 0 | 154 | 0/0/0/0/0/0/13 | 0/0/0/0/0/0/0 | 75% (32%) | 88% |
| SOSA/SSN | C | 11 | 165 | 165/165 | 13 (2/0/11) | 0 | 154 | 0/0/0/0/5/8/0 | 0/0/0/0/5/8/0 | 75% (32%) | 88% |
| SOSA/SSN | D | 8 | 152 | 152/152 | 12 (2/0/10) | 0 | 142 | 0/0/0/0/5/7/0 | 0/0/0/0/5/7/0 | 71% (28%) | 86% |
| SOSA/SSN | E | 8 | 144 | 144/144 | 10 (0/0/10) | 0 | 136 | 0/0/0/0/5/5/0 | 0/0/0/0/5/5/0 | 71% (47%) | 86% |
| SOSA/SSN | F | 8 | 144 | 144/144 | 10 (0/0/10) | 0 | 136 | 0/0/0/0/5/5/0 | 0/0/0/0/5/5/0 | 71% (47%) | 86% |
| PROV | A | 119 | 201 | 198/201 | 61 (0/0/61) | 0 | 145 | 53/2/0/0/4/2/0 | 52/1/0/4/1/3/0 | - (0%) | - |
| PROV | B | 10 | 236 | 0/0 | 16 (0/0/16) | 0 | 220 | 0/0/0/0/0/0/16 | 0/0/0/0/0/0/0 | 63% (66%) | 100% |
| PROV | C | 9 | 233 | 233/233 | 16 (0/0/16) | 0 | 219 | 0/0/0/0/15/1/0 | 0/1/0/0/13/2/0 | 63% (68%) | 100% |
| PROV | D | 10 | 217 | 217/217 | 12 (0/0/12) | 0 | 207 | 0/0/0/0/11/1/0 | 0/1/0/0/9/2/0 | 58% (75%) | 100% |
| PROV | E | 10 | 211 | 211/211 | 12 (0/0/12) | 0 | 201 | 0/0/0/0/11/1/0 | 0/1/0/0/9/2/0 | 58% (75%) | 100% |
| PROV | F | 10 | 203 | 203/203 | 11 (0/0/11) | 0 | 194 | 0/0/0/0/10/1/0 | 0/1/0/0/8/2/0 | 64% (73%) | 100% |

Stem-extended mapping (post-plan sensitivity, labelled): number of mapped properties and declared-level exact+subclass share of mapped with a declared domain.

| Domain | V | mapped (plan) | mapped (stem) | domain exact+subclass / comparable (stem) |
|---|---|---|---|---|
| Brick holdout | A | 111 | 111 | 0 / 1 |
| Brick holdout | B | 3 | 3 | 0 / 0 |
| Brick holdout | C | 3 | 3 | 0 / 0 |
| Brick holdout | D | 3 | 3 | 0 / 0 |
| Brick holdout | E | 1 | 1 | 0 / 0 |
| Brick holdout | F | 1 | 1 | 0 / 0 |
| DCAT | A | 32 | 49 | 10 / 11 |
| DCAT | B | 0 | 0 | 0 / 0 |
| DCAT | C | 0 | 0 | 0 / 0 |
| DCAT | D | 0 | 0 | 0 / 0 |
| DCAT | E | 0 | 0 | 0 / 0 |
| DCAT | F | 0 | 0 | 0 / 0 |
| SOSA/SSN | A | 54 | 56 | 16 / 18 |
| SOSA/SSN | B | 13 | 13 | 0 / 0 |
| SOSA/SSN | C | 13 | 13 | 0 / 0 |
| SOSA/SSN | D | 12 | 12 | 0 / 0 |
| SOSA/SSN | E | 10 | 10 | 0 / 0 |
| SOSA/SSN | F | 10 | 10 | 0 / 0 |
| PROV | A | 61 | 67 | 56 / 58 |
| PROV | B | 16 | 16 | 0 / 0 |
| PROV | C | 16 | 16 | 0 / 0 |
| PROV | D | 12 | 12 | 0 / 0 |
| PROV | E | 12 | 12 | 0 / 0 |
| PROV | F | 11 | 11 | 0 / 0 |

### Most-frequent-class artifact (all domains; second domain counts only)

| Domain | V | classes declared | classes used as entity type | distinct declared domains | domain = most frequent declared domain | range = most frequent declared range | domain = most frequent entity class | most frequent class share of typed entities |
|---|---|---|---|---|---|---|---|---|
| development | A | 90 | 0 | 17 | 39% | 18% | 0% | - |
| development | B | 9 | 9 | 0 | - | - | - | 20% |
| development | C | 10 | 10 | 8 | 43% | 19% | 43% | 22% |
| development | D | 9 | 9 | 9 | 26% | 18% | 26% | 22% |
| development | E | 9 | 9 | 9 | 26% | 18% | 26% | 22% |
| development | F | 9 | 9 | 9 | 26% | 18% | 26% | 22% |
| Brick holdout | A | 1709 | 0 | 1 | 100% | 50% | 0% | - |
| Brick holdout | B | 14 | 14 | 0 | - | - | - | 42% |
| Brick holdout | C | 10 | 10 | 7 | 63% | 26% | 63% | 40% |
| Brick holdout | D | 12 | 12 | 6 | 68% | 27% | 68% | 40% |
| Brick holdout | E | 12 | 12 | 6 | 66% | 28% | 66% | 40% |
| Brick holdout | F | 12 | 12 | 6 | 66% | 28% | 66% | 40% |
| DCAT | A | 85 | 0 | 34 | 23% | 20% | 0% | - |
| DCAT | B | 8 | 8 | 0 | - | - | - | 31% |
| DCAT | C | 9 | 9 | 8 | 34% | 19% | 25% | 26% |
| DCAT | D | 10 | 10 | 8 | 32% | 20% | 26% | 28% |
| DCAT | E | 10 | 10 | 8 | 32% | 20% | 25% | 28% |
| DCAT | F | 10 | 10 | 8 | 32% | 20% | 25% | 28% |
| SOSA/SSN | A | 114 | 0 | 52 | 8% | 5% | 0% | - |
| SOSA/SSN | B | 10 | 10 | 0 | - | - | - | 20% |
| SOSA/SSN | C | 11 | 11 | 8 | 32% | 22% | 13% | 23% |
| SOSA/SSN | D | 8 | 8 | 7 | 30% | 20% | 9% | 23% |
| SOSA/SSN | E | 8 | 8 | 7 | 31% | 20% | 8% | 23% |
| SOSA/SSN | F | 8 | 8 | 7 | 31% | 20% | 8% | 23% |
| PROV | A | 119 | 0 | 44 | 24% | 24% | 0% | - |
| PROV | B | 10 | 10 | 0 | - | - | - | 22% |
| PROV | C | 9 | 9 | 9 | 22% | 16% | 22% | 21% |
| PROV | D | 10 | 10 | 7 | 28% | 18% | 28% | 23% |
| PROV | E | 10 | 10 | 7 | 27% | 18% | 27% | 23% |
| PROV | F | 10 | 10 | 7 | 26% | 19% | 26% | 23% |
| second domain (counts only) | A | 94 | 0 | 30 | 15% | 9% | 0% | - |
| second domain (counts only) | B | 7 | 7 | 0 | - | - | - | 39% |
| second domain (counts only) | C | 7 | 7 | 3 | 71% | 57% | 14% | 21% |
| second domain (counts only) | B' | 7 | 7 | 0 | - | - | - | 56% |

### Official ontologies used

* Brick holdout: 1786 classes, 204 properties; official domain declared for 191, range for 127.
* DCAT: 9 classes, 39 properties; official domain declared for 22, range for 27.
* SOSA/SSN: 22 classes, 52 properties; official domain declared for 23, range for 22.
* PROV: 51 classes, 89 properties; official domain declared for 61, range for 60.

## Step 3 - provenance coverage

Concepts = `skos:Concept` subjects. Chunk share = chunks referenced by a `prov:wasDerivedFrom` link / all atomic chunks of that build. Triples = all triples except `prov:` and `dct:source`; share = triples whose subject is a concept with at least one link. Spot check (variant E, seed 20260913, 30 links): strict = the concept's label (or its domain-word-dropped form) occurs in the chunk text after normalisation; loose = all non-stop tokens occur in any order.

| Domain | V | concepts | with prov | chunks ref. / total | links per linked concept (mean / median / max) | triples with prov subject | spot strict | spot loose |
|---|---|---|---|---|---|---|---|---|
| development | E | 506 | 184 (36%) | 102/202 (50%) | 1.40 / 1 / 8 | 36% | 14/30 (47%) | 20/30 (67%) |
| development | F | 506 | 184 (36%) | 102/202 (50%) | 1.40 / 1 / 8 | 36% | - | - |
| Brick holdout | E | 4505 | 1888 (42%) | 1845/1985 (93%) | 1.01 / 1 / 4 | 46% | 30/30 (100%) | 30/30 (100%) |
| Brick holdout | F | 4505 | 1888 (42%) | 1845/1985 (93%) | 1.01 / 1 / 4 | 46% | - | - |
| DCAT | E | 533 | 206 (39%) | 110/426 (26%) | 1.30 / 1 / 14 | 37% | 15/30 (50%) | 19/30 (63%) |
| DCAT | F | 533 | 206 (39%) | 110/426 (26%) | 1.30 / 1 / 14 | 37% | - | - |
| SOSA/SSN | E | 698 | 334 (48%) | 190/433 (44%) | 1.43 / 1 / 18 | 47% | 22/30 (73%) | 24/30 (80%) |
| SOSA/SSN | F | 698 | 334 (48%) | 190/433 (44%) | 1.43 / 1 / 18 | 47% | - | - |
| PROV | E | 709 | 300 (42%) | 151/458 (33%) | 1.39 / 1 / 11 | 40% | 18/30 (60%) | 21/30 (70%) |
| PROV | F | 709 | 300 (42%) | 151/458 (33%) | 1.43 / 1 / 12 | 40% | - | - |

Second domain: no E/F variant, no PROV links; nothing reported (counts only).
