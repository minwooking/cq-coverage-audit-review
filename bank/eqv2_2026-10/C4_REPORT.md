# C4 report: eligibility and judgeable pairs, bank b1 (addendum 47.4; plan-based, exploratory)

> AI-generated draft: a person must review and test the code and these numbers before use. Structure only:
> no model or judge call, no judge score; eligibility is the paper's rule applied to the full renderings,
> views are question-only subgraphs built by addendum 30's builder.

## Headline

| quantity | value |
|---|---|
| bank rows N1 | 494 |
| A eligible (can_ablate on full A) | 413 |
| B eligible (can_ablate on full B) | 91 |
| judgeable pairs K1 (A and B eligible, both views non-empty) | 66 |
| floor set (judgeable in exactly one of A, B) | 367 |
| eligible cells with no view, A / B | 5 / 0 |
| pair yield y1 = K1/N1 | 0.1336 (expansion bank 26/84 = 0.3095) |
| K1 >= 210 | no |

## By category

| category | rows | A elig. (rate) | B elig. (rate) | both elig. | pairs | pair yield | floor |
|---|---|---|---|---|---|---|---|
| concept_definition | 140 | 128 (0.91) | 12 (0.09) | 9 | 9 | 0.064 | 122 |
| instances | 28 | 22 (0.79) | 2 (0.07) | 1 | 1 | 0.036 | 22 |
| methodology | 140 | 109 (0.78) | 28 (0.20) | 23 | 22 | 0.157 | 88 |
| relations | 22 | 21 (0.95) | 16 (0.73) | 15 | 15 | 0.682 | 7 |
| slots_facets | 23 | 0 (0.00) | 6 (0.26) | 0 | 0 | 0.000 | 6 |
| taxonomy | 141 | 133 (0.94) | 27 (0.19) | 19 | 19 | 0.135 | 122 |

Rate = eligible / rows.

## Reasons per variant

| variant | eligibility reason | cells |
|---|---|---|
| A | eligible | 413 |
| A | missing_required_anchor | 10 |
| A | no_matching_line | 71 |
| B | eligible | 91 |
| B | missing_required_anchor | 53 |
| B | no_matching_line | 350 |

## View status per variant (eligible cells are built; ineligible cells are not)

| variant | view status | cells |
|---|---|---|
| A | no_matching_nodes | 5 |
| A | not_built_ineligible | 81 |
| A | ok | 408 |
| B | not_built_ineligible | 403 |
| B | ok | 91 |

## Items outside the pair set, by (A, B) cause

| cause | items |
|---|---|
| A judgeable / B missing_required_anchor | 40 |
| A judgeable / B no_matching_line | 302 |
| A missing_required_anchor / B missing_required_anchor | 9 |
| A missing_required_anchor / B no_matching_line | 1 |
| A no_matching_line / B judgeable | 24 |
| A no_matching_line / B no_matching_line | 47 |
| A no_matching_nodes / B judgeable | 1 |
| A no_matching_nodes / B missing_required_anchor | 4 |

## Batch 2 size (47.3)

K1 < 210: N2 = min(504, 6 * ceil((210 - 66) / 0.133603 * 1.15 / 6)) = **504**. Recorded in `BATCH2_SIZE.json`. No b2 drafting or call was made; that needs the author's approval.
