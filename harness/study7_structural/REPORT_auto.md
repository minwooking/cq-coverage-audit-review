# Study 7 - structural outputs per stage (auto-generated)

Source: released graph files, counted with rdflib; SHACL (project `stage5_shacl` shapes + pyshacl, rdfs inference) and OWL (`owlrl` closure, no `owl:Nothing`) via `chunktograph.metrics.validity`. No model calls. Second-domain graphs: numeric counts only.

| Domain | V | triples | classes | props | dom+range (n/share) | skos:broader | entity types | PROV derived/all | SHACL | OWL |
|---|---|---|---|---|---|---|---|---|---|---|
| development | A | 599 | 90 | 51 | 51/51 (100%) | 0 | 35 | 0/0 | yes | yes |
| development | B | 4425 | 9 | 179 | 0/179 (0%) | 654 | 488 | 0/0 | yes | yes |
| development | C | 6059 | 10 | 179 | 179/179 (100%) | 648 | 481 | 0/0 | yes | yes |
| development | D | 5209 | 9 | 142 | 142/142 (100%) | 554 | 422 | 0/0 | yes | yes |
| development | E | 5727 | 9 | 134 | 134/134 (100%) | 564 | 422 | 257/361 | yes | yes |
| development | F | 5727 | 9 | 134 | 134/134 (100%) | 564 | 422 | 257/361 | yes | yes |
| Brick holdout | A | 6841 | 1709 | 199 | 2/199 (1%) | 0 | 0 | 0/0 | yes | yes |
| Brick holdout | B | 35668 | 14 | 87 | 0/87 (0%) | 4542 | 4524 | 0/0 | yes | yes |
| Brick holdout | C | 44796 | 10 | 86 | 86/86 (100%) | 4515 | 4495 | 0/0 | yes | yes |
| Brick holdout | D | 44659 | 12 | 81 | 81/81 (100%) | 4515 | 4497 | 0/0 | yes | yes |
| Brick holdout | E | 52056 | 12 | 74 | 74/74 (100%) | 6522 | 4497 | 1898/3745 | yes | yes |
| Brick holdout | F | 52056 | 12 | 74 | 74/74 (100%) | 6522 | 4497 | 1898/3745 | yes | yes |
| DCAT | A | 1877 | 85 | 245 | 214/245 (87%) | 0 | 46 | 0/0 | yes | yes |
| DCAT | B | 4271 | 8 | 174 | 0/174 (0%) | 635 | 492 | 0/0 | yes | yes |
| DCAT | C | 5902 | 9 | 173 | 173/173 (100%) | 630 | 487 | 0/0 | yes | yes |
| DCAT | D | 5766 | 10 | 164 | 164/164 (100%) | 621 | 478 | 0/0 | yes | yes |
| DCAT | E | 6334 | 10 | 158 | 158/158 (100%) | 624 | 478 | 268/380 | yes | yes |
| DCAT | F | 6334 | 10 | 158 | 158/158 (100%) | 624 | 478 | 268/380 | yes | yes |
| SOSA/SSN | A | 2057 | 114 | 107 | 92/107 (86%) | 0 | 216 | 0/0 | yes | yes |
| SOSA/SSN | B | 5922 | 10 | 167 | 0/167 (0%) | 1012 | 650 | 0/0 | yes | yes |
| SOSA/SSN | C | 7816 | 11 | 165 | 165/165 (100%) | 1004 | 643 | 0/0 | yes | yes |
| SOSA/SSN | D | 7542 | 8 | 152 | 152/152 (100%) | 982 | 623 | 0/0 | yes | yes |
| SOSA/SSN | E | 8547 | 8 | 144 | 144/144 (100%) | 1032 | 623 | 477/669 | yes | yes |
| SOSA/SSN | F | 8547 | 8 | 144 | 144/144 (100%) | 1032 | 623 | 477/669 | yes | yes |
| PROV | A | 2398 | 119 | 201 | 198/201 (99%) | 0 | 110 | 0/0 | no (2) | yes |
| PROV | B | 6015 | 10 | 236 | 0/236 (0%) | 911 | 687 | 0/0 | yes | yes |
| PROV | C | 8106 | 9 | 233 | 233/233 (100%) | 887 | 664 | 0/0 | yes | yes |
| PROV | D | 7880 | 10 | 217 | 217/217 (100%) | 869 | 655 | 0/0 | yes | yes |
| PROV | E | 8719 | 10 | 211 | 211/211 (100%) | 878 | 655 | 416/569 | yes | yes |
| PROV | F | 8671 | 10 | 203 | 203/203 (100%) | 878 | 655 | 429/582 | yes | yes |
| Second domain | A | 769 | 94 | 79 | 79/79 (100%) | 0 | 40 | 0/0 | yes | yes |
| Second domain | B | 365 | 7 | 9 | 0/9 (0%) | 12 | 18 | 0/0 | yes | yes |
| Second domain | C | 364 | 7 | 7 | 7/7 (100%) | 8 | 14 | 0/0 | yes | yes |
| Second domain | B' | 1124 | 7 | 61 | 0/61 (0%) | 137 | 133 | 0/0 | yes | yes |

## Dedup at D and standards alignment (from logs)

| Domain | triples in->out (dropped) | predicates merged | entities merged | predicates aligned to standard (E) |
|---|---|---|---|---|
| development | 516->429 (87) | 6 | 0 | 8/142 |
| Brick holdout | 6354->6220 (134) | 4 | 1 | 7/81 |
| DCAT | 375->365 (10) | 5 | 0 | 6/164 |
| SOSA/SSN | 623->603 (20) | 2 | 0 | 8/152 |
| PROV | 582->544 (38) | 3 | 1 | 6/217 |
| second domain (counts only) | not logged | not logged | not logged | not recorded |

## Provenance of inputs (path, sha256)

- development A: `output/ontology_A.ttl` `b8bf7b536c5cd6cf`
- development B: `output/ontology_B.ttl` `7163629ac7fc375a`
- development C: `output/ontology_C.ttl` `7eca648bd8129016`
- development D: `output/ontology_D.ttl` `29e33b03a643ad9c`
- development E: `output/ontology_E.ttl` `90d57be26a3b3585`
- development F: `output/ontology_F.ttl` `1ec59cc90bde8788`
- Brick holdout A: `paper/access2026/harness/variants/A/graph_A.ttl` `1a5cc075065ac1f4`
- Brick holdout B: `paper/access2026/harness/variants/B/graph_B.ttl` `20d015a83b1158fd`
- Brick holdout C: `paper/access2026/harness/variants/C/graph_C.ttl` `c057252c5c5b3375`
- Brick holdout D: `paper/access2026/harness/variants/D/graph_D.ttl` `268a748b8c15d1bc`
- Brick holdout E: `paper/access2026/harness/variants/E/graph_E.ttl` `6283eb356de2a3f9`
- Brick holdout F: `paper/access2026/harness/variants/F/graph_F.ttl` `8fa73d3782bee329`
- DCAT A: `paper/access2026/harness/study4_domains/dcat/variants/A/graph_A.ttl` `833ad42cda809ff3`
- DCAT B: `paper/access2026/harness/study4_domains/dcat/variants/B/graph_B.ttl` `bbdd2e4714b4c6ba`
- DCAT C: `paper/access2026/harness/study5c_full_ladder/dcat/variants/C/graph_C.ttl` `58da1426e860c500`
- DCAT D: `paper/access2026/harness/study5c_full_ladder/dcat/variants/D/graph_D.ttl` `fc84858f95eef7de`
- DCAT E: `paper/access2026/harness/study5c_full_ladder/dcat/variants/E/graph_E.ttl` `bbd7bdce99433889`
- DCAT F: `paper/access2026/harness/study5_judge_panel/dcat/variants/F/graph_F.ttl` `51f138a53d43b87d`
- SOSA/SSN A: `paper/access2026/harness/study4_domains/ssn/variants/A/graph_A.ttl` `9f0a757198de8e57`
- SOSA/SSN B: `paper/access2026/harness/study4_domains/ssn/variants/B/graph_B.ttl` `858874c21f41b037`
- SOSA/SSN C: `paper/access2026/harness/study5c_full_ladder/ssn/variants/C/graph_C.ttl` `05b9aa4835727033`
- SOSA/SSN D: `paper/access2026/harness/study5c_full_ladder/ssn/variants/D/graph_D.ttl` `6772152b2a49e7e9`
- SOSA/SSN E: `paper/access2026/harness/study5c_full_ladder/ssn/variants/E/graph_E.ttl` `d9d37f23e59edef4`
- SOSA/SSN F: `paper/access2026/harness/study5_judge_panel/ssn/variants/F/graph_F.ttl` `a90e8606c0151941`
- PROV A: `paper/access2026/harness/study4_domains/prov/variants/A/graph_A.ttl` `821b6970b20d20fe`
- PROV B: `paper/access2026/harness/study4_domains/prov/variants/B/graph_B.ttl` `3b2ad00e9a725127`
- PROV C: `paper/access2026/harness/study5c_full_ladder/prov/variants/C/graph_C.ttl` `76f669c6bebec635`
- PROV D: `paper/access2026/harness/study5c_full_ladder/prov/variants/D/graph_D.ttl` `2da0b77421b96069`
- PROV E: `paper/access2026/harness/study5c_full_ladder/prov/variants/E/graph_E.ttl` `0e4d3e06b84cccf5`
- PROV F: `paper/access2026/harness/study5_judge_panel/prov/variants/F/graph_F.ttl` `b8299950189e3873`
- second domain (counts only) A: `output_mfg/ontology_A.ttl` `d743bbf9dda8bff5`
- second domain (counts only) B: `output_mfg/ontology_B.ttl` `9f5948b39a8923bb`
- second domain (counts only) C: `output_mfg/ontology_C.ttl` `bdb16f7ff026f5e8`
- second domain (counts only) B': `output_mfg/r34_bprime/ontology_Bp.ttl` `f59e85227d1f8b86`
- development dedup_file: `output/d_refine_report.json`
- development alignment_file: `output/standard_alignment.json`
- Brick holdout dedup_file: `paper/access2026/harness/variants/_work/d_refine_report.json`
- Brick holdout alignment_file: `paper/access2026/harness/variants/_work/standard_alignment.json`
- DCAT dedup_file: `paper/access2026/harness/study5_judge_panel/dcat/work/d_refine_report.json`
- DCAT alignment_file: `paper/access2026/harness/study5_judge_panel/dcat/work/standard_alignment.json`
- SOSA/SSN dedup_file: `paper/access2026/harness/study5_judge_panel/ssn/work/d_refine_report.json`
- SOSA/SSN alignment_file: `paper/access2026/harness/study5_judge_panel/ssn/work/standard_alignment.json`
- PROV dedup_file: `paper/access2026/harness/study5_judge_panel/prov/work/d_refine_report.json`
- PROV alignment_file: `paper/access2026/harness/study5_judge_panel/prov/work/standard_alignment.json`

Released F shapes (`shapes_F.ttl`) conformance: development=True, Brick holdout=True, DCAT=True, SOSA/SSN=True, PROV=True
