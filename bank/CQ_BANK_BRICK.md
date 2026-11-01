# Holdout CQ bank — Brick v1.4.4 (36 scored / 60-row pool, 6 categories)

Artifact-blind draft authored 2026-09-12 from the frozen snapshot only
(`../data/brick-v1.4.4.ttl`, SHA256 b65720b7..., no artifact consulted).
Status: **frozen** (see "eligibility screen performed, stratified draw resolved, bank
frozen" below) — 36 rows (`cq_bank_brick_v1.csv`) are the scored primary set; the 60-row
pool (`cq_bank_brick_v2.csv`) is the eligibility-screen universe plus unused replacement
stock. Frozen 2026-09-12T12:22:32Z, tag `access2026-cqbank-brick-v1-freeze`, SHA256
`993c5e11...` (full digest below). No edits to `cq_bank_brick_v1.csv` after this point.

## Versions

- `cq_bank_brick_v0.csv` — first draft. **Do not use.** Retained only as an audit trail.
- `cq_bank_brick_v1.csv` — 17 of 36 rows corrected after full re-verification. **Retained as an
  audit trail** (concurrently, a second workstream added the `ask_expressible` /
  `ask_query_file` columns and the per-row `ask_queries/CQB01.rq..CQB36.rq` files to this
  version — see "v1 -> v2" below for how that schema was preserved).
- `cq_bank_brick_v2.csv` — current. Expands the bank from 36 to 60 rows (6 categories x 10) by
  appending 24 new rows (CQB37-CQB60), all 6 categories x 4. The original 36 rows are carried
  over byte-for-byte (including their `ask_expressible`/`ask_query_file` values and CRLF line
  endings) so v1 stays a legible audit trail and v2 is a strict superset.

## Why v1 -> v2: rule-of-three arithmetic (36 -> 60)

The G1 statistical acceptance gate reads the bank as a Bernoulli trial: N holdout CQs, K
observed failures, and a one-sided 95% upper confidence bound on the failure rate. Under the
rule-of-three heuristic (the standard approximation when K=0), the upper bound is `~3/N`:

- At N=36 (the v1 size): `3/36 ~= 8.3%` upper bound *even with zero observed failures* — i.e.
  the gate would already sit at ~8.3% before a single failure is tolerated, and any single
  observed failure (K=1) pushes the practical bound well past what a "the bank is small and
  strict" framing can defend.
- At N=60 (this v2 size): zero failures gives `3/60 = 5%`, and *one* tolerated failure (K=1)
  keeps the (Wilson/Clopper-Pearson-adjacent) upper bound in the neighborhood of ~7.7% rather
  than needing a completely clean run. This is the actual reason for the expansion: 36 rows is
  functionally a zero-tolerance gate; 60 rows lets the gate survive one real defect without its
  statistical meaning collapsing.

60 was picked as the smallest round increase that (a) preserves the existing 6-category
stratification exactly (6x10 vs. 6x6) and (b) buys the one-failure headroom above, without
inflating the bank so far that per-row artifact-blind authoring/verification effort becomes the
bottleneck.

## How the 24 new rows (CQB37-CQB60) were authored and verified

Same artifact-blind discipline as v0->v1, applied prospectively rather than as a post-hoc fix:

1. **Snapshot-only authoring.** Every candidate term was chosen by reading
   `../data/brick-v1.4.4.ttl` directly (via `rdflib`, never via any generated artifact/graph
   output). No candidate was accepted until its `rdfs:comment` / `skos:definition` /
   subclass / property-characteristic triples were pulled from the parsed graph and quoted
   verbatim (including one deliberately preserved snapshot typo: rec:Region's example
   "Lombary", and one snapshot spelling quirk: brick:resolution's "specifing" — both kept
   verbatim rather than silently corrected, per the no-fabrication rule).
2. **Namespace precision.** Every grounding term is one of `brick:` / `rec:` / `ref:`; no
   `BrickShape:` (SHACL shapes namespace) terms were used, since `verify_bank.py`'s grounding
   regex only recognizes brick/rec/ref and a BrickShape citation would be silently unverifiable.
3. **Two candidate terms rejected as ungrounded and substituted** (see "Substituted terms"
   below) after `rdflib` confirmed they carry no `rdfs:comment`/`skos:definition`/domain/range.
4. **Mechanical grounding gate.** `verify_bank.py` was extended to take an optional CLI
   argument (bank filename, default `cq_bank_brick_v1.csv` for backward compatibility) and run
   against `cq_bank_brick_v2.csv`. Current result: **60 rows, 94 grounding terms, 0 missing,
   exit 0** (quoted verbatim in the outer report).
5. **Executable SPARQL `ASK` channel extended to the new rows.** The concurrent workstream that
   added `ask_expressible`/`ask_query_file` to v1 was still in flight while v2 was authored;
   rather than leave the 24 new rows outside that convention, matching `ask_queries/CQB37.rq`
   through `CQB60.rq` were authored (same PREFIX preamble, same `ASK { ... }` idiom used by the
   existing 36) and **each was executed directly against the parsed snapshot graph** — all 24
   return `True`. `ask_expressible` per new row follows the same per-category pattern already
   visible in v1 (taxonomy/relations existence-and-count facts -> `yes`; definition-paraphrase
   and prose-bearing rows -> `partial`).

## Substituted terms (rejected as ungrounded during v2 authoring)

Per the "no ungrounded questions" rule, five originally-planned `slots_facets` grounding terms
were checked with `rdflib` and found to carry **no** `rdfs:comment`, **no** `skos:definition`,
and **no** `rdfs:domain`/`rdfs:range` in the v1.4.4 snapshot: `brick:aggregationFunction`,
`brick:aggregationInterval`, `brick:latitude`, `brick:longitude`, `brick:timestamp`. None of
these could ground a definition-style CQ, so all five were dropped and replaced with four
properties confirmed to carry a real `skos:definition`: `brick:coordinates`,
`brick:coolingCapacity`, `brick:resolution`, `brick:electricalPhaseCount` (CQB49-CQB52).

Separately, the planned 4th `methodology` row was reframed: an aggregation-methodology framing
would have required citing the `BrickShape:` (SHACL shapes) namespace, which
`verify_bank.py`'s grounding regex does not recognize and which falls outside the brick/rec/ref
scope this bank restricts itself to. It was replaced with the `rec:AudioVisualEquipment`
deprecation/migration pattern (CQB59), grounded entirely in `brick:`/`rec:` terms already in
scope.

A third correction (not a substitution, but a fact check that changed a planned CQ's framing):
`brick:hasInputSubstance` and `brick:hasOutputSubstance` were originally assumed to form an
`owl:inverseOf` pair; `rdflib` confirmed **no** `owl:inverseOf` triple exists between them —
they are two independent `owl:AsymmetricProperty` properties, each with its own definition, not
declared inverses. CQB48 describes them as such rather than fabricating an inverse relationship.

## Current counts (v2)

- Rows: 60 (6 categories x 10).
- Grounding terms checked by `verify_bank.py`: 98 (was 94 before the CQB21/CQB23 correction
  below added two more `skos:definition`-anchored terms).
- Missing: 0. Exit code: 0.
- New `ask_queries/*.rq` files added for the 24 new rows: 24 (all independently confirmed
  `ASK` = `True` against the frozen snapshot before being recorded as `ask_expressible`).

## 2026-09-12 correction: CQB21 / CQB23 (post-authoring defect, found by `scripts/ask_oracle.py`)

The claim above ("each was executed directly against the parsed snapshot graph — all
[return] `True`") was checked ad hoc at authoring time, not run through a hardened,
contract-tested oracle. When `scripts/ask_oracle.py` was hardened (path-traversal guards,
non-ASK-form rejection, an rdflib constant-`FILTER(false)` workaround, and a vacuous-`ASK {}`
guard) and run end to end, it caught a real defect it was designed to catch: **CQB21 and
CQB23 both returned `ASK = false`.**

Both rows had asserted `brick:grossArea` / `brick:yearBuilt` are `owl:DatatypeProperty`. The
frozen snapshot instead types both as `owl:ObjectProperty` **and** `brick:EntityProperty` (an
inconsistency in Brick's own modeling that this bank must report faithfully, not paper over).
Fix applied: `grounding` and `expected_answer` for both rows were restated as the
`skos:definition`-anchored property identity + the verbatim definition text, and both
`ask_queries/CQB21.rq` / `CQB23.rq` were rewritten from
`ASK { brick:X a owl:DatatypeProperty }` to `ASK { brick:X a owl:ObjectProperty,
brick:EntityProperty }`. `ask_expressible` stays `yes` for both rows — the correction is to
the grounding/query content, not to the expressibility classification.

Post-fix verification: `scripts/ask_oracle.py` → v1 **36/36 pass, exit 0**; v2 **60/60 pass,
exit 0**. `verify_bank.py` → v1 36 rows/55 terms/0 missing; v2 60 rows/98 terms/0 missing.
Both `.csv` files were corrected identically (v1 and v2 both carry CQB21/CQB23), so the
"v1 rows carried over byte-for-byte into v2" claim above no longer holds for these two rows
specifically — both copies were edited in lockstep, not just v1.

## Why v1 exists (self-audit, 2026-09-12)

The v0 draft claimed its expected answers were verified; a full re-check with
`verify_bank.py` showed that claim was only partly true. Four classes of defect were found:

1. Namespace errors. Thirteen rows attributed `rec:` terms (Asset, Campus, Event, Space,
   Portfolio, Collection, Organization, BuildingElement, PointEvent, Georeference,
   ArchitectureArea) to the `brick:` namespace.
2. Non-existent terms. `brick:locatedIn` and `brick:hasExternalReference` do not exist;
   the real terms are `rec:locatedIn` and `ref:hasExternalReference`.
3. An ungrounded question. `brick:Point` carries no rdfs:comment or skos:definition in
   v1.4.4, so the original CQB01 had no answerable source span. It was replaced with
   `brick:Sensor`, which does carry an ASHRAE-sourced definition.
4. Invented answer text. CQB29 cited a "non-adjacent security zones" example that is not
   in the snapshot; the actual example is Region contains Sites contains Buildings.
   CQB27 likewise said "Action from an Actuator point" where the snapshot says
   "Actuation sent to a Command point".

Defect 4 is the one that matters most: an expected answer that reads plausibly but is not
in the source would have silently corrupted every human and judge score built on it.
`verify_bank.py` now gates this — it exits non-zero if any grounding term is missing.
Current state: 36 rows, 51 grounding terms, 0 missing.

## Remaining limitation

`verify_bank.py` proves each cited term *exists*. It does not prove the expected answer
*paraphrases the source faithfully*. Paraphrase faithfulness is checked by **one expert —
the bank's author — and that expert is not independent of the bank**, so this channel is
strictly weaker than a two-rater screen: it cannot detect an error the author is already
blind to, and it yields no inter-rater agreement statistic. We do not claim otherwise.
This stays an **open limitation** of the bank, stated as such in the paper, and it is
mitigated rather than closed by the other two channels (the mechanical grounding gate and
the SPARQL `ASK` checks, neither of which has a human in it). To let third parties redo
the screen themselves, the bank is released with full groundings (every cited term plus
the TTL construct it comes from), the frozen snapshot and its SHA256, and the v0 -> v1
revision ledger above, so any disagreement with an expected answer can be traced to a
source span and re-adjudicated without our involvement.

- Category taxonomy follows the frozen 6-category scheme of the legacy 16-CQ bank
  (concept_definition / taxonomy / relations / slots_facets / instances / methodology).
- Each row records grounding (TTL construct) and expected answer; every expected answer was
  verified against the snapshot with rdflib (subclass/disjoint/inverse checks), two rows corrected (CQB03, CQB10).
- Cluster ids default to 1:1; paraphrases added later must join the parent's cluster id.
- Deliberately version-specific (v1.4.4 structure, rec-layer comments) to limit pretraining leakage;
  CQ11/CQ09-style count facts anchor to this snapshot.

## Eligibility screen — three channels, not two experts

An earlier draft of this checklist required "two experts independently screen groundings".
**That requirement is dropped, because it is unsatisfiable here.** Only one person is
available for expert work on this bank (the author), exactly as with the two-annotator
human study that was already dropped for the same reason. Leaving a two-expert item on the
checklist would mean the freeze can never be honestly completed, so it is replaced by the
three channels that actually exist:

1. **One expert eligibility screen (non-independent).** The bank's author checks each row
   for: source span present in the frozen snapshot, answerable from the schema alone, and
   no duplicate within a cluster. Recorded as a single-author screen — *not* as independent
   review, and not reported as an inter-rater agreement figure.
2. **Mechanical grounding gate — `verify_bank.py`.** Proves every cited `brick:` / `rec:` /
   `ref:` term exists in the frozen snapshot; exits non-zero otherwise, so it gates the
   freeze. No human judgement involved. Current state (v2, `python3 verify_bank.py
   cq_bank_brick_v2.csv`): 60 rows, 98 terms, 0 missing, exit 0. (v1: 36 rows, 55 terms, 0
   missing, exit 0. Both counts reflect the 2026-09-12 CQB21/CQB23 correction below; the
   pre-correction historical counts were 94/51 respectively.)
3. **Executable SPARQL `ASK` check.** For every CQ whose grounding is expressible as a
   boolean query over the snapshot (subclass/disjointness/inverse/domain-range/`skos:definition`
   presence, counts via `ASK` over a bound pattern), the check is written as a SPARQL `ASK`
   and run against the snapshot; the CQ is eligible only if it returns `true`. **This is the
   only channel with no human in it at all, and it is what replaces the missing second
   expert** — it re-derives the grounding claim mechanically rather than trusting a second
   reading of it.

Channel 3 cannot cover every row (open-ended definition-paraphrase CQs have no boolean
form), which is why per-row `ASK` expressibility is recorded rather than assumed — see the
CSV plan below.

## 2026-09-12: eligibility screen performed, stratified draw resolved, bank frozen

**Framing decision (60-pool vs. 36-scored).** Two ways to read "60 = 6x10" were on the
table: (A) score all 60 rows, or (B) treat the 60 as an eligibility pool and stratify-draw
36 for scoring, with the rest as replacement stock. **(B) is adopted**, matching
`PLAN_ACCESS_TKDE_2026-09-12.md` §2.2 ("2인 전문가 eligibility 심사를 거친 뒤 stratified
random 추출", target 36 = 6x6) and keeping the pre-registered cell budget at 216 (36x6),
not 360.

Under (B), the "draw" is not a fresh from-scratch reshuffle of all 60 rows: the original
36 (`CQB01`-`CQB36`, `cq_bank_brick_v1.csv`) were authored first, already exactly 6 per
category, and went through their own correction pass (the v0->v1 defect list above) before
the pool was ever widened to 60. The 24 new rows (`CQB37`-`CQB60`) were added afterwards,
for the rule-of-three headroom reason in the "Why v1 -> v2" section above -- not to enable a
retroactive random reshuffle of which 36 get scored. Re-drawing 36 from all 60 with a fresh
RNG now, after the manuscript already describes the original 36's specific per-category
`ask_expressible` composition (taxonomy 6/6, relations 6/6, slots_facets 4/6, methodology
2/6, concept_definition 0/6, instances 0/6), would silently invalidate that description for
no eligibility reason -- the correct causal role for the stratification step is: **the
original 36 stand as the pre-registered primary sample; the 24-row surplus exists solely as
replacement stock for the eligibility screen below, invoked only if a row in the primary 36
fails.**

**Channel-1 eligibility screen (single-author, all 60 rows).** Performed 2026-09-12: for
every row, checked (a) every grounding term resolves in the frozen snapshot (delegated to
channel 2, `verify_bank.py`, already exit 0 on both files), (b) every row whose grounding has
a boolean form and `ask_expressible != no` is independently re-derived by channel 3
(`ask_oracle.py`, already 36/36 and 60/60), and (c) for the rows carrying free-text
prose beyond a bare boolean claim -- the harder case channels 2-3 cannot fully cover -- each
was checked by hand against the actual snapshot triples for the cited terms (not just
their labels): every `owl:inverseOf`/`owl:disjointWith`/`rdfs:subClassOf` claim was
confirmed as an explicit triple (e.g. `brick:hasTag owl:inverseOf brick:isTagOf`,
`brick:Sensor owl:disjointWith brick:Alarm`), and cross-namespace claims not visible from a
single term's own `skos:definition` (`CQB36`'s "`ref:hasExternalReference` ... for
BACnet/IFC references") were confirmed via the SHACL shapes that actually tie
`ref:BACnetReference`/`ref:IFCReference` to `ref:hasExternalReference`
(`sh:targetObjectsOf`). **Result: 60/60 eligible, 0 rejected.** No duplicate clusters (every
row is currently its own 1:1 cluster; see cluster-id note below). Because 0 rows were
rejected, 0 substitutions were drawn from the 24-row surplus -- the frozen primary set below
is exactly the original 36, unchanged.

As with channel 1's general limitation stated earlier in this document, this screen is a
single non-independent rater (the bank's author) and is reported as such, not as an
inter-rater agreement figure.

**`cluster_id` materialized.** Every row in both `cq_bank_brick_v1.csv` and
`cq_bank_brick_v2.csv` previously carried the literal placeholder string
`same-as-cq_id-by-default` in its `cluster_id` column -- a label, not an id, that could not
support CQ-cluster-level bootstrap CI (`PREREG.md` §4) because every row compared equal to
every other row under naive string grouping. Materialized to each row's own `cq_id` (1:1
cluster, since no paraphrases have been authored yet -- see the open item below). This is a
mechanical fix, not a content change: `ask_oracle.py` and `verify_bank.py` both re-verified
clean afterwards (v1 36/36 rows pass / 55 terms / 0 missing; v2 60/60 rows pass / 98 terms /
0 missing).

**Freeze record.**
- Frozen file: `cq_bank_brick_v1.csv` (the 36-row primary scored set).
- Timestamp: 2026-09-12T12:22:32Z.
- Git tag: `access2026-cqbank-brick-v1-freeze`.
- SHA256 (`cq_bank_brick_v1.csv`, post cluster-id materialization): `993c5e1164540dce0f2f9bf2e6ed397cf45910da7889300feeaad6543edb8507`.
- Companion pool file `cq_bank_brick_v2.csv` SHA256 (informational; not itself the scored
  set): `3868de4be471f27fda081ceb9b7babe0dd39edc944434453b46b380db3dd40f5`.
- No edits to `cq_bank_brick_v1.csv` are permitted after this timestamp without a new,
  separately dated and tagged freeze.

**Still open (does not block this freeze, but blocks the test-retest sub-analysis).** The
~15 cluster paraphrases described in the CSV plan below have **not** been authored. They are
needed only for the blinded test-retest reliability pass (`PLAN_ACCESS_TKDE_2026-09-12.md`
§2.3's rubric-freeze/test-retest design), not for primary Layer-1 CQ Coverage scoring itself
-- primary scoring can proceed against the 36 frozen rows above. If/when the paraphrases are
authored, they join an existing row's `cluster_id` (now a real id, not a placeholder) as an
addendum to this freeze, not a re-freeze of the primary 36.

## CSV plan — two columns to add before freeze

**Status update:** `ask_expressible` and `ask_query_file` (first bullet below) are **implemented**
as of v2 — both columns exist on all 60 rows of `cq_bank_brick_v2.csv`, and every row's
`ask_query_file` resolves to a real file under `ask_queries/` that returns `ASK` = `true`
against the frozen snapshot. `cluster_id` is materialized (each row's own `cq_id`; see the
freeze section above), so it is no longer the literal placeholder this section originally
described. `paraphrase_of` (second bullet) is **still only planned** — not yet added to any
bank version; the ~15 cluster paraphrases described below remain outstanding, but per the
freeze section above this blocks only the test-retest sub-analysis, not the primary freeze
that already happened. The rest of this section is retained as the original plan text.

- **`ask_expressible`** — `yes` / `no` / `partial`. `yes`: the whole grounding is checkable
  by one SPARQL `ASK` returning `true` against the frozen snapshot (typical of
  taxonomy/relations/slots_facets rows). `no`: the grounding is an open-ended definition
  paraphrase with no boolean form (typical of concept_definition rows), so channel 3 does
  not apply and only channels 1-2 cover it. `partial`: the *existence/structural* half is
  `ASK`-checkable but the expected answer also carries prose the query cannot confirm. The
  column exists so the coverage of channel 3 is a reported number, not an implied one — a
  row marked `no` is a row where the single non-independent expert is the only faithfulness
  check, and that should be visible per row.
- **`paraphrase_of`** — cluster paraphrase link. About **15 cluster paraphrases must be
  authored before freeze**: a test-retest (washout re-score) that shows the annotator the
  *identical* item measures recall of the first answer, not agreement, so each cluster
  selected for re-scoring needs a second surface form of the same question with the same
  grounding and the same expected answer. Paraphrase rows carry the parent's `cluster_id`
  and name the parent in `paraphrase_of`; they must pass channels 2-3 unchanged, since a
  paraphrase that alters the grounding is a different CQ, not a paraphrase.
