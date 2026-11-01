# Released graphs: development corpus and DCAT (variants A-F)

AI-generated documentation; review it before reuse. These files are research outputs of the Chunk-to-Graph pipeline. They are not production artefacts.

This folder holds the graph files of two of the five corpora of the structural study (Study 7) and of the judged ladders. The Brick graphs are in `../variants/`. The SOSA/SSN and PROV graphs are not released (the W3C document-use licence allows no derivative works); the archive holds their digests and counts.

Every file below is a byte-identical copy of the file that `../study7_structural/analyze.py` hashed, and the sha256 in `../study7_structural/results.json` equals the sha256 listed here (checked 2026-10-22). The originals stay where they were.

## development/ (source: *Ontology Development 101*)

Source document: N. F. Noy and D. L. McGuinness, *Ontology Development 101: A Guide to Creating Your First Ontology*, Stanford Knowledge Systems Laboratory Technical Report KSL-01-05 and Stanford Medical Informatics Technical Report SMI-2001-0880, 2001, publicly distributed by the authors' institutions. The paper cites it as `noy-mcguinness-2001-ontology101`. The source text is **not** part of this folder.

Provenance: built on 2026-06-03 from the 202 atomic chunks of that document with the paper's Qwen extractor, by the repository state of that day (the exact commit is not recorded in the build outputs). Original location in the working repository: `output/` (git-ignored). Variant A is the direct extraction; B to F follow Table 2 of the paper. `shapes_F.ttl` is the SHACL file generated for F; `d_refine_report.json` is the stage-D dedup report.

Content: the graphs hold concept labels (short stemmed noun phrases, at most 81 characters) with identifiers, `skos:broader` links, weights and chunk identifiers. Variant A also holds three one-sentence modelling statements of the document as `rdfs:label` values and the two document authors' institutional e-mail addresses as `ex:hasEmail` values; in the archive copy of `ontology_A.ttl` the two addresses are replaced by `<email>` (the file in the repository is unchanged). No other file contains an e-mail address, host name, or local path (scanned).

| file | bytes | sha256 (as built) |
|---|---:|---|
| `d_refine_report.json` | 2311 | `1c5338feffcd69395ec7bf46c4e139422a8ecdbfa021d503adb7b25adf8b8043` |
| `ontology_A.ttl` | 20678 | `b8bf7b536c5cd6cf8aa2292fce2fe3bead4b044edb61255098250066362010ab` (archive copy after masking: `cebcfd150080e44cb198b920ef7119373163586b2fefda402817c6670207d18e`) |
| `ontology_B.ttl` | 183622 | `7163629ac7fc375ac0a745f9212d7b8ee969d8642afe97ac46b51393766ee45c` |
| `ontology_C.ttl` | 230541 | `7eca648bd8129016c25c723f4ff538cf3328374f4eeeec1a778c8b982b9abd8f` |
| `ontology_D.ttl` | 198165 | `29e33b03a643ad9cf162fb6fa53a26016b06a62dbc528787590facc3441e0bf3` |
| `ontology_E.ttl` | 218147 | `90d57be26a3b35858d50711db63add01ee814b527773c26b0eb5d643cc6aa6c5` |
| `ontology_F.ttl` | 218147 | `1ec59cc90bde878806483a2d3ff84c4a896a7851b007710ca60c35c273842c77` |
| `shapes_F.ttl` | 20259 | `5d3385229f1e71e5a0f4e6f17485524f31c341a9dfd46e6a0068b8e967c07ac3` |

## dcat/ (source: W3C *Data Catalog Vocabulary (DCAT) - Version 3*)

Source document: W3C Recommendation "Data Catalog Vocabulary (DCAT) - Version 3". Its page states that the W3C liability, trademark and permissive document licence rules apply (W3C Software and Document Notice and License; copying, modification and redistribution with notice). The grounding ontology file carries `dcterms:license` CC BY 4.0 (record: `../study4_domains/PLAN.md`, section 35.2). Study 4 already committed the A and B graphs, views and manifests of this domain (`../study4_domains/dcat/variants/`). `graph_A.ttl` holds one `rdfs:label` that is the W3C public comments mailing-list address; in the archive copy it is replaced by `<email>`.

Provenance: A and B were built on 2026-10-20 (Study 4); C, D and E on 2026-10-20 (Study 5c); F on 2026-10-20 (Study 5, on top of each domain's B build), all with `Qwen/Qwen3-Next-80B-A3B-Instruct-FP8` and the repository HEAD source of that day (commit not recorded in the manifests; each variant's `MANIFEST.json` with its input-corpus digest is in the study directory named in `../study7_structural/results.json`). `shapes_F.ttl` and `d_refine_report.json` are the F-stage outputs of the Study 5 work directory.

| file | bytes | sha256 (as built) |
|---|---:|---|
| `d_refine_report.json` | 1572 | `8fb3d8bb6220342de5c28f2f215b240eee5a6f383a707ff60d8bc2be33cce8c1` |
| `graph_A.ttl` | 76703 | `833ad42cda809ff3c933add4ad9060a6ef878513e28d985bad4b427cefa47e97` (archive copy after masking: `b50543e129ebc197984fa9ba8e44ccb91993bd1b1f5d8c59ab16b09c29ed6389`) |
| `graph_B.ttl` | 166715 | `bbdd2e4714b4c6ba194c45fdaebe67653b89a03a0f7a02e6d7abf139e826da97` |
| `graph_C.ttl` | 213751 | `58da1426e860c5009a5ec67b903537435aa9101420e60a7dbf32404b4b41704e` |
| `graph_D.ttl` | 208902 | `fc84858f95eef7dec783ba96c8d46f70208354d3378605caec11162f9a89e3f3` |
| `graph_E.ttl` | 230930 | `bbd7bdce994338899d53ce8d6c80e6206bc87e439470321437ee9e2222d1781f` |
| `graph_F.ttl` | 230930 | `51f138a53d43b87d7e8d5bcf5f3d6b0d533ab4102cf06eb95098c2a26316fea4` |
| `shapes_F.ttl` | 23047 | `ce118bb7f479344d9d1504502829933f00e46f82877decc5030ff6d1cd5ae79a` |

## Licence

The graphs are released under CC BY 4.0, with attribution to the W3C DCAT 3 Recommendation (dcat/) and to Noy and McGuinness (2001) (development/). Rights in the underlying documents stay with their owners. The development graphs contain labels and structure, not the document text, apart from the three sentences named above, which are short quotations for the purpose of identification. If you are the rights holder of the source and object to the release, contact the corresponding author.

## Verify

```
sha256sum development/* dcat/*
```
