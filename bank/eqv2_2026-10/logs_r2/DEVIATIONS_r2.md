# DEVIATIONS r2 (re-draft of batch b1 under amendment 47.A1)

All deviations are caller-side only: no file under `tools/`, no frame item, no rule,
no request parameter other than those listed, and no pinned hash was touched. 74 tests
pass unchanged in `tools/tests`.

## D1 — thinking-off realised as `reasoning_effort: "none"` (also present in round 1)

The route ignores the top-level `enable_thinking: false` that `draft.py` sends: the
model's hidden reasoning then consumes the entire 256-token budget and the reply comes
back `content: null` with `finish_reason = "length"`. 47.3 requires thinking off, so the
driver additionally sends `"reasoning_effort": "none"`, which this gateway honours
(verified: zero reasoning tokens, clean JSON). This is the same intent and the same
deviation round 1 used; round 1's round-1 call log carries the equivalent note.
Everything else in the request is `draft.py`'s: temperature 0, max_tokens 256,
response_format json_object, no tools (asserted).

## D2 — null content under HTTP 200 is retryable (also present in round 1)

`draft.py::draft_one` aborts an item when the envelope has no content; on this gateway
that is a transient, not a permanent, failure. The driver classifies
`content = null` as retryable inside the tool's own 4-attempt exponential-backoff budget.
Round 1 recorded the same behaviour. In the r2 draft run no attempt needed this retry
(0 null contents out of 504).

## D3 — the chat/completions URL shape (`/v1` prefix)

`draft.py` builds the request URL by appending `/chat/completions` to the endpoint from
the environment. In round 1 the configured endpoint ended in `/v1`; in this session it
carries no path, so the same append produced a JSON-decoding endpoint that is not the
gateway's OpenAI-compatible surface. The driver resolves the URL to
`<endpoint>/v1/chat/completions` (verified by path probe before any generation call — a
GET that returns the OpenAI-shape 405/200 response). The endpoint value itself is never
written to any file.

## D4 — route-health check before the run

Per 47.A1.5 a model-supply check precedes the drafting: `GET /v1/models` on the same
gateway listed the routes, and the drafting route (`<internal-proxy>/Qwen/Qwen3.8-Flash-Next`)
answered six smoke calls (one per category) cleanly at the resolved URL before the 504
rows were drafted. The fallback route (the other engine, in-flight <= 4) was therefore
not needed.

## D5 — log directory

All tools and drivers ran with `EQV2_LOG_DIR` pointing at `logs_r2/`, so round 1's
`logs/` directory was never appended to. File names inside `logs_r2/` are the tools'
ordinary ones. Output names follow 47.A1.5 (`*_r2`).

## D6 (added by the maintainer after the run, before the author saw any r2 sample)
The re-draft worker drew the first r2 sample with a global shuffle of all passing ids (seed 20260914) and reported that
this reproduced the round-1 draw. Re-checking, it does not: the round-1 sample is reproduced exactly by the per-category
procedure (one `Random(seed)`, categories in canonical order, each category's passing ids sorted then shuffled, the first
5 kept, written in sorted id order), and that procedure with seed 20260914 over the r2 passing ids does not give the
global-shuffle sample. The rule, fixed before the new draw, was to use the procedure that reproduces round 1. The
global-shuffle files are kept as `screen_b1_r2_sample_globalshuffle_SUPERSEDED.csv` and
`screen_b1_r2_sheet_globalshuffle_SUPERSEDED.csv`, were never shown to the author, and are not used. The sample the
author screens is `screen_b1_r2_sample.csv` / `screen_b1_r2_sheet.csv`.
D7: amendment 47.A1.2 says 16 of the 25 relations questions that survived V1-V6 in round 1 repeat the term; the exact
counts are 18 of 25 round-1 draft rows (16 of the 22 that were kept). The amendment is committed and is not edited.
