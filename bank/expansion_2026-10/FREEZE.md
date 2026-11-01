# FREEZE — Brick expansion CQ bank v1 (78 rows; categories 5x14 + methodology 8 — imbalance recorded)

> **FROZEN** in this commit, tagged `access2026-cqbank-brick-expansion-v1-freeze` (annotated). Frozen from
> `cq_bank_brick_expansion_draft_v1.csv` (84 rows, sha-identified draft, `#` draft-comment line dropped) by the
> scope decision recorded below. No edit to `cq_bank_brick_expansion_v1.csv` afterwards without a new dated freeze.

Author (scope) decision, 2026-10-24, recorded in the planning session: **78 rows frozen — methodology-frame rows
`CQX71`–`CQX76` dropped** (same template repeated six times; correlated questions would be clustered as if
independent and so would flatter the clustered CI), **and the four `screen_dup=REVIEW` rows `CQX19`, `CQX23`,
`CQX28`, `CQX43` kept** (the machine screen judged each factually distinct from the nearest existing bank row;
the per-row evidence table is being kept in `REVIEW_PACKET.md`). Category balance is 13 per category (6 x 13),
the freeze target stated in the parent README (6x13 = 78) was reached in total count only: because all six dropped rows came from the methodology category, the frozen distribution is five categories x 14 plus methodology x 8. Category-level balance was NOT restored; this should be remembered when comparing category-clustered sensitivity analyses (study 11 style) on this bank against the evenly balanced original banks, and any future top-up freeze should account for the 6-row methodology deficit if 6x13 is later wanted.

Scope approval, not row-by-row reading: the author approved the freeze scope (which rows are dropped, which
kept) on 2026-10-24 without reading all 78 question texts. The `author_review` column therefore carries
`approved-2026-10-24 (scope: drop CQX71-76 methodology frames; CQX19/23/28/43 kept per screen evidence)` on
every row; this documents a scope-level decision, and row-level naturalness review was NOT performed (the
rows carry their 3-channel machine screen results and the `screen_dup`/`screen_notes` evidence, and the
parent README's known-limits paragraph applies: the machine channels check existence and ASK truth only).

| field | value |
|---|---|
| Frozen (local time) | 2026-10-24 |
| Bank file | `bank/expansion_2026-10/cq_bank_brick_expansion_v1.csv` (78 rows, 6 categories x 13) |
| Bank SHA-256 | `66fec29f69fa776641d61397c5b2b991af114b6e5f4382c5f5a7e714a47212b8` |
| Source draft | `cq_bank_brick_expansion_draft_v1.csv` (84 rows; draft header line dropped at freeze, per parent README checklist step 5) |
| Dropped rows | `CQX71`, `CQX72`, `CQX73`, `CQX74`, `CQX75`, `CQX76` (methodology frame repetition) |
| Kept despite `screen_dup=REVIEW` | `CQX19`, `CQX23`, `CQX28`, `CQX43` (evidence table in `REVIEW_PACKET.md`) |
| ai noted | This freeze was executed by an AI assistant under the author's scope decision; the expansion rows remain AI-generated questions (parent README banner). |

Change record: draft SHA-256 (post-header) is not separately stamped because the draft file itself remains
in place unmodified as the provenance record; the frozen file is the reproducible minus-6 projection of it.
