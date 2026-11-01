# Provenance of the eqv2 bank, batch b1 (addendum 47, 47.3; manuscript Study 12)

> AI-generated draft; the author must review it before relying on it. Plan-based and exploratory; this is not a
> registration and attaches no pre-commitment label. Written before the freeze commit (C3), like the precedent files
> (`harness/study2_llm_labels/BANK_PROVENANCE.md`, `bank/expansion_2026-10/FREEZE.md`).

## How the questions were written

- **Blind drafting.** `tools/draft.py` drafted all 504 items (`CQE001`..`CQE504`, the same item list in both rounds)
  blind: the model saw only the category, the frame rank (3 frames per category, chosen with seed 20260913), the
  term's local name and `rdfs:label`, its definition sentence, and parent/child/property names -- all pulled by the
  script from `data/brick-v1.4.4.ttl`. Renderings, graphs, eligibility, manifests, judge records, annotation/key files
  and `.env` are in the forbidden set enforced by a runtime `sys.addaudithook` that logs every `open`/`listdir`/`scandir`
  and raises on a forbidden path (`tools/blind_patterns.json`).
- **Only the question sentence comes from the model.** `grounding`, `expected_answer` and the ASK query are built by the
  script, as in the expansion-bank precedent. The request is temperature 0, `max_tokens` 256, JSON output, no tools
  (asserted in code), thinking off, sent through the local <internal-proxy> gateway -- the model-supply policy is gateway-route only,
  so no endpoint value is ever written to any file and no host, port or key appears here or in any artifact of this study.
- **Model.** `Qwen3.8-Flash-Next`, the primary drafting route of the plan's model-supply rule (a remote shared engine,
  in-flight <= 8, hard cap 16; the <internal-host> fallback, in-flight <= 4, was not needed -- 47.A1.5 / `logs_r2/DEVIATIONS_r2.md` D4).
  The verbatim route identifier the tools recorded (`<internal-proxy>/Qwen/Qwen3.8-Flash-Next`) is kept unchanged in the bank's
  `draft_model` column; nothing else about the route's address is recorded anywhere.
- **What was and was not opened to build this.** The frame was designed in a session that had read access to the two
  renderings and both graphs and recomputed their hashes, and the session that wrote addendum 47 did the same -- that
  access is stated in 47.3, not excluded. The drafting run itself is covered by the blind hook (B2, below).

## Deviations from 47.3 as written (the whole set: D1--D7 of `logs_r2/DEVIATIONS_r2.md`, plus what round 1 did differently)

All of them are caller-side: no file under `tools/`, no frame item, no rule and no pinned hash was touched by any of them.

- **D1 -- thinking off was realised as `reasoning_effort: "none"`, not as the top-level `enable_thinking: false` that
  `draft.py` sends.** This is the deviation of *both* rounds (round 1's log carries the equivalent note); with the
  gateway's handling of `enable_thinking` the hidden reasoning eats the whole 256-token budget and the reply comes back
  `content: null` with `finish_reason: length`. `reasoning_effort: "none"` is honoured (verified: zero reasoning tokens).
  Everything else stayed `draft.py`'s: temperature 0, `max_tokens` 256, `json_object`, no tools.
- **D2 -- a `content: null` envelope under HTTP 200 is treated as retryable, not fatal.** `draft.py::draft_one` aborts
  the item; the driver retries inside the tool's own 4-attempt backoff. In round 1 this was load-bearing: 305 of its
  921 logged calls ended in `null content (gateway envelope)` and had to be retried, plus ~66 not-JSON (truncated
  output) errors. In the round-2 accepted run **no** attempt needed a retry -- every one of the 549 logged calls is
  `ok=true, attempt=1`, 45 of them the replacement-wave candidates.
- **D3 -- the gateway path shape (`/v1` suffix).** Round 1's configured endpoint already ended in `/v1`; this session's
  carried no path, so `draft.py`'s `/chat/completions` append landed on a non-OpenAI surface. The driver resolves to
  `<endpoint>/v1/chat/completions`, verified by a path probe before any generation call. The endpoint value itself is
  never written to any file.
- **D4 -- route-health check before the run** (required by 47.A1.5): `GET /v1/models` on the gateway listed the routes and
  six smoke calls (one per category) answered cleanly on the drafting route before the 504 rows were drafted.
- **D5 -- log directory**: the tools ran with `EQV2_LOG_DIR=logs_r2/`, so round 1's `logs/` was never appended to. File
  names inside `logs_r2/` are the tools' ordinary ones; output *names* follow 47.A1.5 (`*_r2`).
- **D6 -- the sample-draw procedure was corrected after the run, before the author saw any r2 sample.** The re-draft
  worker first drew the 30-row r2 sample with a *global* shuffle of all passing ids (seed 20260914) and claimed it
  reproduced the round-1 draw. It does not: the round-1 draw is reproduced exactly by the per-category procedure (one
  `Random(seed)`, categories in canonical order, each category's passing ids sorted then shuffled, first 5 kept, written
  in sorted id order). The rule fixed before the new draw was "the procedure that reproduces round 1", so the
  global-shuffle sample was redone. Those files stand as
  `screen_b1_r2_sample_globalshuffle_SUPERSEDED.csv` / `screen_b1_r2_sheet_globalshuffle_SUPERSEDED.csv`: never shown to
  the author, not used. The drawn sample is `screen_b1_r2_sample.csv` / `screen_b1_r2_sheet.csv`.
- **D7 -- a counting correction, not a change.** 47.A1.2 says 16 of the 25 round-1 relations questions that survived
  V1--V6 repeat the term; the exact counts are 18 of the 25 round-1 draft rows (16 of the 22 that were kept). The
  committed amendment is not edited.
- **Round 1's other deviation** was the B3 scanner crash below, present in both rounds.

## Blind checks (accepted round: `BLIND_AUDIT_b1_r2.md`)

- **B1** static AST scan of `draft.py`, `common.py`, `frame.py`, `validate.py`, `dedup.py`, `blind_audit.py`: clean; the
  few notes are prose mentions of the word `eligibility` in module docstrings and the exempt-list line (the two
  post-freeze scripts are exempted by name, and that is stated in the tool).
- **B2** the runtime open log contains **0 forbidden opens** (`logs_r2/blind_open_log_b1.jsonl`, 21,809 events); this is
  the decisive access evidence for the re-draft, since it records files opened, not text mentioned.
- **B3** transcript scan, restricted per 47.3 to the sessions that ran the drafting tools. The tool's own
  `audit_transcripts` crashed on the transcript nesting (`cur.get("type")` returned a dict; unhashable for the
  membership test) in both rounds, and the scan was re-run with the same counting logic plus a type guard -- tool-call
  arguments only, forbidden-pattern counts only, no content retained, the tool itself untouched (the deviation is
  stated rather than patched, per 47.3). The counts split path-like occurrences from text-level mentions (the `.env`
  token in a settings-key listing, the forbidden-pattern list quoted verbatim in driver comments and briefs). Inside the
  r2 drafting window the parent session's tool-call arguments hold **zero** path-like occurrences; the path-like counts
  all carry earlier timestamps (planning, release packaging, briefs). The drafting subagent: 106 tool calls, 0 forbidden
  hits. The parent session: 958 tool calls, 28 hits, all mention-level and outside the drafting window. **B3 verdict:
  PASS with the stated limitation.**
- **Limitation, quoted verbatim from `BLIND_AUDIT_b1_r2.md`:**
  > B1-B2 cannot prove what a human or agent saw. The session that designed the frame had read access to the renderings
  > and graphs, and recomputed their hashes; that access is stated, not excluded (addendum 47, 47.3).
- Round 1's audit (`BLIND_AUDIT_b1.md`) reported the same B1/B2 result with **B3 NOT RUN**; the r2 re-verification above
  supersedes it for the accepted run.

## Why round 1 was rejected, and what the revision changed

Round 1's 30-row screen (seed 20260913) returned **6 failures of 30, so the batch was rejected** (>= 4). Five of the six
were `relations` rows: `common.build_prompt` filled the relations `{owner}` slot from `props[0]`, which is the property
term itself, so the model was handed "Ask what rec:targetPoint records for rec:targetPoint." and wrote a doubled,
unspeakable sentence; one was an `instances` row whose singular "an example" frame asked for one of two enumerated
examples. The diagnosis, the file-and-line detail and the per-row table are in `harness/study29_eqv2_ab/AMENDMENT_47A1.md`
(47.A1.1--47.A1.2), which is the one prompt revision 47.3 allows.

Amendment 47.A1 (commit `67f5dcd`, committed before any re-draft) changed only: the three `relations` frames and the
`{owner}` slot (now the real shape owner from `owner_of_prop`, with a `shape owner:` line in the facts block); the third
`instances` frame (plural-aware "example(s) ... naming all of them when it names more than one"); a new form check
**V1f** on `relations` rows only (the row's own local name may appear at most once in the question); and the pinned-hash
lookup in `draft.py`, which prefers `prompt_sha256_r2.json` because `frame_summary.json` is committed and was not
rewritten. Unchanged by assertion in `tests/test_amendment_47a1.py`: the system prompt, the frames of the other four
categories, instances frames 0/1, the `CQE001..CQE504` item list and every category's `b1_terms` / `b1_frame_rank` /
`frame_tail`, the request body, both seeds, D1--D5 and `tau_emb`. Template hash: `baf4e1fe...` -> `a20414e1...`
(`prompt_sha256_r2.json`, whose `previous_sha256` is the round-1 value). The whole item list was re-drafted; the new
sample draws with seed 20260914. The amendment states its own limits before the run, among them that it was written by
an AI assistant with a hypothesis-aware author and that nothing in it was chosen because of a judge number.

## What the frozen file is and is not

- It is `validated_b1_r2.jsonl`'s 494 kept rows projected into the CSV, **question/grounding/expected_answer byte-identical
  to those rows** (verified by a round-trip over every row, not by eye), ordered by `cq_id`. See `BANK_FREEZE_b1.md` for
  the column and blank-cell policy, and for why `instances`/`relations`/`slots_facets` fall below the 84-per-category quota.
- 37 of the 494 rows were drafted from a **frame-tail term**, not from the term the frame had allocated to their `cq_id`
  (the validation replacement wave keeps the id and swaps the term, `validate.py`). In
  `logs_frozen/round2/draft_calls_b1.jsonl` the 549 calls are 504 first attempts plus **45 replacement-wave calls**,
  spread over 37 ids (29 called twice, 8 called three times -- a candidate that fails validation is answered by the
  next tail term). Each of the 37 rows' `term` value in `validated_b1_r2.jsonl` is a member of that row's own category
  frame tail, which is reproducible from the committed `frame_summary.json`; no sampling seed is involved.
- It is not a human-checked answer key. It carries no eligibility information: nothing from 47.4 (the renderings) was
  read or computed to make it. It says nothing about the planned judge, the full renderings, other domains, human
  labels, or support/over/under-credit (47.1).
- Files referenced but not part of this bank, by design: `frame_summary.json`, `tau_emb.json`, `prompt_sha256_r2.json`,
  the committed tools and tests (C2, `20b2a73`), `AMENDMENT_47A1.md` (`67f5dcd`), `SCREEN_b1_r2_RESULT.md` (the accepted
  round's screen verdict and its honest account of how that verdict was established), `logs_r2/DEVIATIONS_r2.md`,
  `validate_report_b1_r2.json`, `dedup_log_b1_r2.csv`.
- `SCREEN_b1_RESULT.md` is **not cited by this bank** and was not used for any part of it: its provenance is unknown and
  nothing in it can be tied to the protocol. Where round 1's screen matters, the record used is the filled sheet
  `screen_b1_sheet_filled_r1.csv` (committed in `67f5dcd`) and the reason table in `AMENDMENT_47A1.md` 47.A1.1.
