# Brick v1 paraphrase freeze record

This record covers the separate test-retest paraphrase file
`cq_bank_brick_v1_paraphrases.csv`. It does **not** replace or modify the frozen
36-row scored sample `cq_bank_brick_v1.csv`.

## Current state

- File: `cq_bank_brick_v1_paraphrases.csv`
- SHA-256: `c02ecda3f2c6c3c27dc47e7f4845ac57739d5d85b059bfa813328c125682341f`
- Rows: 36 data rows (one for every `CQB01`--`CQB36` source row)
- Source bank SHA-256: `993c5e1164540dce0f2f9bf2e6ed397cf45910da7889300feeaad6543edb8507`
- Mechanical paraphrase verification: passed on 2026-09-13T10:57:31Z
  (`verify_paraphrases.py`, 36 rows, 0 errors)
- Source grounding verification: passed (`verify_bank.py`, 36 rows, 55 terms,
  0 missing)
- `uv run pytest bank -q`: passed, 5 tests
- Written at: 2026-09-13T10:57:31Z (UTC)

The draft remains at `cq_bank_brick_v1_paraphrases_draft.csv` and is not
silently deleted or overwritten.

## What the mechanical gate checks

`verify_paraphrases.py` checks all of the following against
`cq_bank_brick_v1.csv`:

1. Exactly 36 paraphrase rows are present.
2. `cq_id` values are unique and exactly match the 36 source cells; no source
   cell is missing and no unknown cell is added.
3. `cluster_id` is unchanged from the source row.
4. `grounding` is byte-for-byte equal to the source row. This protects the
   evidence/grounding term and therefore the intended answer target.
5. The paraphrase is non-empty, is not the normalized original sentence, and
   has token-set Jaccard overlap at most 0.60 with the original question.

The gate proves coverage, identity, grounding preservation, and surface change;
it cannot prove semantic equivalence or answer/category preservation by itself.
A human author review must confirm that each question asks the same thing, keeps
the same expected answer, and stays in the same category. The grounding and
source `cq_id` checks are the mechanical safeguards for that review.

## Freeze procedure

1. Keep the primary scored bank and its SHA-256 unchanged.
2. Review every paraphrase for meaning equivalence, unchanged evidence/grounding,
   unchanged expected answer, unchanged category, and adequate surface change.
3. Run the mechanical gates from `paper/access2026`:

   ```bash
   uv run python bank/verify_bank.py cq_bank_brick_v1.csv
   uv run python bank/verify_paraphrases.py
   uv run pytest bank -q
   sha256sum bank/cq_bank_brick_v1_paraphrases.csv
   ```

4. Record the resulting paraphrase SHA-256, row count, verification output, and
   UTC timestamp in this file.
5. Preserve the draft and keep the frozen paraphrase file separate from the
   primary scoring bank.

**The freeze declaration itself is a human decision.** This file records the
mechanical state and the procedure; it does not by itself declare the paraphrase
set frozen (the author's declaration of 2026-10-09 is recorded in the last
section of this file). Likewise, changing the manuscript's statement that the
paraphrases have “not been authored” is a human editorial decision and is
intentionally left for the author. No manuscript file is changed here.


## 사람 검토가 필요한 지점 (2026-09-13 메인 세션 점검)

패러프레이즈 36행 중 21행은 이 세션에서 생성되었고 15행은 기존 저자 초안이다.
동결 전에 저자가 **의미 동일성**을 행 단위로 확인해야 한다. 특히 다음을 본다.

1. **답의 형태를 문항이 미리 알려주지 않는가.** 점검에서 두 건을 발견해 고쳤다.
   - `CQB13`: "Which predicate represents an Equipment's contained Point and its reverse?"
     → 역관계가 존재한다는 사실을 문항이 노출했다. 개방형으로 되돌렸다.
   - `CQB33`: "Which relations and flag describe nested virtual meters?"
     → 답에 플래그가 포함된다는 것을 노출했다. 개방형으로 되돌렸다.
   이런 노출은 재채점 점수를 부풀려 G2 QWK를 낙관적으로 만든다.
2. **개방형이 폐쇄형으로 바뀌지 않았는가.** 원문 what/how → 패러프레이즈 which 로
   어간이 바뀐 행이 11개다. 대부분 무해하나(둘 다 개방형) 행 단위 확인이 필요하다.
3. **난이도가 한쪽으로 치우치지 않았는가.** 예: `CQB16`은 원문이 용어를 직접 주고
   패러프레이즈는 서술로 바꾸어 오히려 더 어려울 수 있다.

검증기는 형식(행 수, 근거 일치, 표면 중복률)만 보증한다. **의미 동일성은 기계가
보증하지 못하므로 동결 선언은 사람이 한다.**


## Freeze declaration (2026-10-09)

This section records the human freeze declaration that the sections above say
only a person can make (PREREG.md section 12.3, DN-2).

- **Declaration.** On 2026-10-09 the author declared the current bytes of
  `cq_bank_brick_v1_paraphrases.csv` frozen. The instruction was the author's
  “니 추천대로 다 해줘” (“do everything as you recommend”), given at 07:36:52 KST
  (conversation record; PREREG.md section 12.0). It approved the recommended
  options of the section 12 addendum, among them DN-2: the washout packet shows
  the paraphrase on every row.
- **Frozen bytes.** sha256
  `c02ecda3f2c6c3c27dc47e7f4845ac57739d5d85b059bfa813328c125682341f`, 36 data
  rows, source bank sha256
  `993c5e1164540dce0f2f9bf2e6ed397cf45910da7889300feeaad6543edb8507`. The
  file has one commit, `682bfe3` (2026-09-14), and its `sha256sum` equals the
  value above at the time of this entry. PREREG.md section 12.3 DN-2 records
  that the 12 preserved controls of the judge run used the same bytes.
  `build_washout_packet.py` refuses any other bytes.
- **The author did not read the rows.** The declaration was made without
  reading the paraphrase rows. It declares these bytes frozen; it does not
  say the rows are equivalent in meaning.
- **Still pending: the semantic-equivalence check by a person other than the
  rater.** The mechanical gate above says nothing about meaning. A person who
  is not the rater must check, row by row, that each paraphrase asks the same
  thing, keeps the expected answer and the category, and gives away nothing
  more than the original, and must finish before the washout starts. The rater
  must not read the paraphrases before the washout, because that would weaken
  the surface change the pass relies on. The result goes into a CSV with the
  columns `cq_id`, `verdict` (`pass` or `fail`), `checker` (a non-rater
  identifier or initials) and `date`, one row for each of the 36 paraphrase
  rows (PREREG.md section 13); `build_washout_packet.py` refuses to build
  without a complete file. If no such check is done by the washout date, the
  packet is built with `--no-paraphrase-fallback`: every row then shows the
  original CQ, and both manifests record it. A row that fails is not replaced: every washout row of its
  cluster (primary and control) then shows the original CQ, and the packet
  manifest records how many rows do. No new paraphrase is written after the
  first pass ended.
- The section above says 21 of the 36 rows were generated in the 2026-09-13
  working session and 15 are the author's earlier draft. The session records
  do not confirm this: the 36-row CSV was written by a GPT-5.6-series subagent
  in a Claude Code session at 10:55:24Z on 2026-09-13, and Claude Opus 5
  edited two rows at 11:00:05Z (tool-call metadata only; content not read).
  Whether 15 rows came from an author draft cannot be verified (PREREG.md
  section 13, item 15).
