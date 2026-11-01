# Redaction log: PREREG.public.md

`PREREG.public.md` is a redacted copy of the registered `PREREG.md` (addenda 1-14). Nothing in the
registered analysis plan, the gates, the thresholds, the dates or the decisions was changed. The
redaction removes internal infrastructure identifiers and shortens verbatim chat quotations, as
PREREG section 12.7 requires before external release.

| file | sha256 |
|---|---|
| `PREREG.md` (original, not included in this package) | `05ad3e0f1840ee0a346356c47a3cc38e48060383418f6a13bc9700c0ba3eecf0` |
| `PREREG.public.md` (this package) | `c8079ee6c1031e0ed7525ac797f7fc645a3d613bb2381a576ab84887b4ece0fa` |

The unredacted original matches the `PREREG.md` content hash printed in the manuscript and is available
to editors and reviewers on request.

## How the copy was made

- Line-preserving: the copy has the same 1613 lines as the original; line N of the copy is line N of
  the original. Every `L###` reference inside the text therefore still points at the same place.
- Mechanical, rule-based substitutions (a fixed rule table tied to the exact original). The rules are
  not part of the package because they contain the strings that were removed.
- The original was not modified.
- 40 substitutions on 31 lines, listed below by original line number.

## Redacted lines by category

### internal service endpoint (6 substitutions)

Lines: 20, 150, 163, 184, 261, 972

### internal hostname (3 substitutions)

Lines: 161 (x2), 699

### absolute or home-relative local path (12 substitutions)

Lines: 162, 1075, 1135, 1197, 1240 (x3), 1322, 1324 (x3), 1597

### internal proxy / model-route name (5 substitutions)

Lines: 1321 (x2), 1463 (x3)

### chat quotation shortened to a decision summary (12 substitutions)

Lines: 1214, 1215, 1340, 1346, 1379, 1397, 1399, 1441, 1495 (x2), 1530, 1580

### public-copy notice (2 substitutions)

Lines: 1, 1523

## What replaced what

- Internal endpoints and proxy endpoints: the placeholders `<internal-endpoint>` and `<internal-proxy-endpoint>`.
- Internal hostnames, and the serving container and image names: `<internal-host>`, `<container>`, `<image>`; the host-to-container
  port mapping: `<host-port>-><container-port>`.
- Local paths (home directory files of the agent tooling and the labeling working directory): neutral
  placeholders (`<agent-session-database>`, `<proxy-usage-log>`, `<agent-config-file>`, `<labels>`, `<models>`); the
  read-only copy of the locked AH-pass files is named `locked_labels/` in this package.
- Internal proxy / model-route names: `<internal-proxy>` and `<route-name withheld>`.
- Chat quotations of the author's instructions (addenda 12-14, decision checklist 12.7, timeline in 12.0): replaced
  by a one-clause neutral summary of the decision, keeping the timestamp, the decision and its date. The
  decisions themselves (approval of the recommendations, removal of the session limit, permission of AI tools,
  no washout and no second annotation) are unchanged and stated in the same places.
- Line 1 and line 1523 carry a short notice that this is the public copy.

## Kept on purpose

- Model names that the manuscript itself prints (for example `qwen-next-flash`, `gemini-3.6-flash`,
  `gpt-5.6-luna`), commit hashes, sha256 digests, KST timestamps and file names inside the repository.
- References to files that are not in this package: `persona_pass` material and its seal ledger, the
  internal operations runbook, the addendum-12 draft, and the author's private working directory. They are
  named as in the original so that the cross-references stay intact. Their absence is intentional.
- One sentence quoted from the internal operations runbook in deviation D12 (a statement about the sealed
  auxiliary-check result). It is a document quotation, not a chat quotation, and contains no identifier.

## Check before further redistribution

The public copy was screened for IP addresses, loopback endpoints, internal hostnames, e-mail addresses,
token patterns, internal proxy names, session identifiers and absolute paths; none remains. Nothing in the
screening can certify the repository history, so the author reviews the copy before upload.
