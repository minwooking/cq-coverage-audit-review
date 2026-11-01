# Domain data freeze — Access holdout domains (2026-09-12)

Pre-registered snapshot record. Do not swap sources after CQ authoring starts.

## Domain 2 (primary new): building-automation / industrial — Brick Schema

- Source: https://github.com/BrickSchema/Brick (release v1.4.4, published 2025-05-02)
- File: brick-v1.4.4.ttl (1,749,633 bytes)
- SHA256: b65720b7b9b64c646745c689777e6138c0d59ce0088df0aeb78fbd444d04d8e7
- License: BSD-3-Clause (Brick Consortium) — verified from LICENSE at repo root (raw.githubusercontent.com/BrickSchema/Brick/master/LICENSE)
- Reference KG: the schema itself (TBox) + Brick/Brick-shape validation as executable CQ oracle;
  example Brick models from the same release serve as ABox variants.
- Document->CQ mapping: Brick documentation pages + term definitions (same license scope).
- Leakage note: schema is public since 2016; CQs must target version-specific/class-level facts and
  be authored blind from this frozen snapshot only.

## Domain 3 (corpus scale / later, TKDE-leaning): scholarly — Wikidata scholarly graph

- Endpoint: https://query-scholarly.wikidata.org/sparql (verified reachable 2026-09-12)
- Dump path for corpus-scale runs: https://dumps.wikimedia.org/wikidatawiki/entities/ (dated dumps; record snapshot date + checksum at pull time)
- License: CC0 for structured data in main/Property/Lexeme/EntitySchema namespaces
  (https://www.wikidata.org/wiki/Wikidata:Licensing). Attribution not legally required; recommended.
- Operational: descriptive User-Agent, serialized requests, honor 429 Retry-After; prefer dated dumps over WDQS stress.

## Ruled out for a fully-public Access domain (evidence in session audit)

- UMLS/SNOMED CT: redistribution prohibited except licensed-app patterns -> IDs-only designs only.
- BioASQ: CC BY 2.5 but commercial use needs written permission; registration required.
- OPC UA companion specs: redistribution/license unclear -> backup only.

## Status

- [x] Brick v1.4.4 pulled, hashed, committed under paper/access2026/data/
- [x] CQ bank (36 holdout, primary scored set) authored blind from frozen Brick docs,
      three-channel eligibility screen performed (0/60 rejected), and frozen
      2026-09-12T12:22:32Z, tag `access2026-cqbank-brick-v1-freeze`, SHA256
      `993c5e1164540dce0f2f9bf2e6ed397cf45910da7889300feeaad6543edb8507`
      (`cq_bank_brick_v1.csv`). Details: `../bank/CQ_BANK_BRICK.md`.
- [ ] Wikidata scholarly snapshot date/checksum — deferred (TKDE track), not needed for Access pilot
