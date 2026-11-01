# CP-1 author screen, batch b1 re-draft (round 2) -- result

Protocol: addendum 47.3 as revised by amendment 47.A1 (commit `67f5dcd`): 30-row sample, 5 per category, drawn with seed
20260914 over the ids that pass the amended V1-V6 (the per-category procedure that also reproduces the round-1 draw; see
`logs_r2/DEVIATIONS_r2.md` D6), five criteria, **accept on <= 3 failures, reject on >= 4**.

Sample: `screen_b1_r2_sample.csv` (30 rows, 5 columns); the blank sheet is `screen_b1_r2_sheet.csv`
(sha256 `15a2849cc87b4f58a63f342b...`, full digest in `SHA256SUMS` of the freeze commit).

## Record of how the result reached this file

The sheet that the author saved, `screen_b1_r2_sheet_filled.csv`, is **byte-identical to the blank sheet**: it carries no
mark in any of the five criteria columns, so it cannot by itself show whether the author passed all rows or did not
save the marks. The maintainer therefore did not read the blank cells as a pass; it asked, and on 2026-10-28 the author
answered in the working session, in these words in substance, that there were **0 failures in the 30 rows (all passed)**,
including row CQE275 ("1 direct subclasses: Wind_Direction_Sensor.", which the maintainer had pointed out beforehand as a
possible criterion-1 or criterion-4 row). The result below rests on that statement.

## Result

**0 failures of 30 -> batch b1 (round 2) accepted** (<= 3). No sampled row is dropped; the file `screen_b1.csv` (sampled
failures dropped, addendum 47.3) holds its header only. The unsampled rows stand. Round 1 of the same item list was
rejected (6 of 30, `screen_b1_sheet_filled_r1.csv`).

## What this acceptance means and does not mean

* 30 of the 494 kept rows were screened; 464 were not. The acceptance rule is a bound on the bad-row rate, not a check
  of every row: at a true bad-row rate of 10% the rule would have accepted with probability 0.647 (addendum 47.10).
* The author screened wording and snapshot agreement on the sample; no eligibility, rendering, graph or judge
  information was shown or used at any step of the screen.
* Both screens were done by the author who knows the hypothesis; the revision between them is stated in amendment 47.A1.
* The first screen's rejection and the single permitted revision are part of the record of this bank; a second
  rejection would have stopped the study.

The bank items are AI-drafted (Qwen3.8-Flash-Next); nothing here is a human-checked answer key.
