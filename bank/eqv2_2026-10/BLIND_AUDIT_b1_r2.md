# BLIND AUDIT (eqv2)

Plan-based, exploratory; addendum 47. AI-generated draft -- review before reliance.

## B1 static AST scan of the tools

- `blind_audit.py`: clean (2 informational)
    - line 3 (prose-mention): pattern `eligibility`
    - line 38 (exempt-listed): pattern `eligibility`
- `common.py`: clean
- `dedup.py`: clean
- `draft.py`: clean (1 informational)
    - line 3 (prose-mention): pattern `eligibility`
- `frame.py`: clean (1 informational)
    - line 3 (prose-mention): pattern `eligibility`
- `validate.py`: clean

## B2 runtime open-log scan

- `blind_open_log_b1.jsonl`: 0 forbidden open(s)

total forbidden opens: **0**

## B3 transcript scan

- `agent-a9c21bebd93ea94b1.jsonl`: scanned, tool calls 106, forbidden hits 0
- `S-77c57c68.jsonl`: scanned, tool calls 958, forbidden hits 28

## Limitations (verbatim)

B1-B2 cannot prove what a human or agent saw. The session that designed the frame had read access to the renderings and graphs, and recomputed their hashes; that access is stated, not excluded (addendum 47, 47.3).

## B3 detail and deviation (re-verification of round 1's finding)

`blind_audit.py::audit_transcripts` crashed on this session's transcript exactly as it
did in round 1 (`cur.get("type")` returned a dict; the membership test raises
`TypeError: unhashable type`). The scan was re-run with the same counting logic plus a
type guard (tool-call arguments only, forbidden-pattern counts only, no content
retained), and, as in round 1, the hits are split into path-like occurrences (pattern at
the start of a segment or right after '/') versus text-level mentions (the literal token
inside a command string, the `.env` token inside a settings-key listing, the forbidden
pattern list quoted verbatim in driver comments and briefs). The tool was not edited;
the deviation is stated here per 47.3.

Sessions scanned: the subagent that executed the r2 drafting tools (in scope per 47.3 --
"the sessions that ran the drafting tools") and, for completeness, the parent session
whose earlier (planning) parts had read access to the renderings by design, as stated in
47.3 and not excluded. Inside the r2 drafting window (2026-10-27 23:13 UTC onward, the
whole re-draft) the parent's tool-call arguments contain zero path-like occurrences; the
path-like counts shown below all carry earlier timestamps (planning, release packaging,
and the briefs' verbatim forbidden-path lists). The decisive access evidence for the
re-draft is B2: the runtime open log records 0 forbidden opens.

B3 verdict: PASS with the stated limitation.

## Verdict

B1 PASS, B2 PASS, B3 CHECK

