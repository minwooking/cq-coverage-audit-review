# CP-1 author screen, batch b2 -- result

Protocol: addendum 47.3 'Batch 2' and `BATCH2_PROCEDURE.md` rule 8 (committed before any b2 drafting call, tag
`access2026-eqv2-b2-procedure`): 30 rows over the categories that hold b2 rows, 10 each, drawn with seed 20260915 by the
per-category procedure (ids sorted by number, one `Random(seed)`, canonical category order, the first 10 kept); five
criteria; **accept on <= 3 failures, reject on >= 4** (a rejected b2 would have left the study on b1 alone).

Sample: `screen_b2_sample.csv` (30 rows, 5 columns; reproduced byte for byte by `tools/screen_sample.py --preset b2`);
the blank sheet is `screen_b2_sheet.csv`.

## Record of how the result reached this file

The sheet the author saved, `screen_b2_sheet_filled.csv`, is **byte-identical to the blank sheet** (same sha256, saved
2026-10-28 20:32 local time): none of the five criteria columns carries a mark on any of the 30 rows. A blank sheet cannot
by itself show whether every row passed or the marks were not saved, so the maintainer did not read the blank cells as a
pass. It asked the author, who first answered that the labels were saved in `screen_b2_sheet_filled.csv`; the maintainer
re-read that file, found it still identical to the blank, and said so. The author then answered, in the working session
on 2026-10-28, that **the blank sheet as it stands is correct** ("지금 빈시트가 맞아"). The maintainer reads this as:
no row was marked, that is, **0 failures in the 30 rows**. The result below rests on that statement, not on the file. If
that reading is wrong the author is asked to say so before the freeze commit; after the commit it stands.

Rows that the maintainer had pointed out beforehand as possible criterion-1 or criterion-4 rows, so that the author
could look at them, were the three methodology rows whose question carries the term's definition (`CQE950`, `CQE975`,
`CQE985`); under the reading above none of them was marked.

## Result

**0 failures of 30 -> batch b2 accepted** (<= 3). No sampled row is dropped; `screen_b2.csv` (sampled failures dropped)
holds its header only. The unsampled rows stand.

## What this acceptance means and does not mean

* 30 of the 456 kept b2 rows were screened; **426 were not**. The rule bounds the bad-row rate; it is not a check of
  every row: at a true bad-row rate of 10% it would accept with probability 0.647, at 15% with 0.322 (addendum 47.10).
* Methodology is 17 rows of the bank's b2 part and 10 of them were in the sample; concept_definition and taxonomy are
  219 and 220 rows with 10 sampled each, so the screen is much thinner on those two categories than on methodology.
* The author read wording and snapshot agreement on the sample only; no eligibility, rendering, graph or judge
  information was shown or used at any step of this screen. The author knows the study's hypothesis.
* The b2 rows were drafted after the b1 eligibility counts were known (K1 = 66); the rules that fixed b2's composition
  are in `BATCH2_PROCEDURE.md` with their stated limits.

The bank items are AI-drafted (Qwen3.8-Flash-Next); nothing here is a human-checked answer key.
