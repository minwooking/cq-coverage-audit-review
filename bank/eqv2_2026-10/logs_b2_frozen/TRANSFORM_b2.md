# Log transformation for the b2 freeze copy (`logs_b2_frozen/`)

> AI-generated draft; the author must review it before relying on it. Addendum 47, 47.3 freeze step for batch b2: the
> drafting and open logs are committed, so the absolute machine paths that the audit hook recorded are replaced by tokens
> before they go into the repository. The originals in `logs_b2/` stand untouched; nothing in them was edited, moved or
> deleted for this copy. This file follows `logs_frozen/TRANSFORM.md` (the b1 freeze), with the user-name rule applied
> from the start instead of as a later patch.

## Rule applied

Applied to the `path` value of every line of the two open logs, in this order:

1. a path under the repository root (`paper/access2026/`) becomes **repository-relative** (`data/...`, `bank/...`, `harness/...`);
2. any other path under the workspace root becomes **`<WORKSPACE>/...`** (relative to the workspace root);
3. a path under the user's home becomes **`<HOME>/...`**;
4. a path under the system temporary directory becomes **`<TMP>/...`**;
5. anything else is left exactly as it is (`/usr/...`, `/proc/...`, `/dev/null`, `/etc/...`, and paths already written relative, such as `../draft_b2.jsonl`).

Then, on the result, every remaining occurrence of the login name becomes **`<USER>`**. The count of lines where this
last step changed anything is 0 in both files: in these logs the login name occurred only inside the home prefix that
rule 3 had already removed (and there is no pytest temporary directory named after the login, which was the one place it survived in b1).

Nothing else was changed. **Line count, line order, the `event` and `ts` fields, and the field set of every line are
preserved line-for-line, and no line was dropped, merged or reordered** -- verified by parsing both files and asserting,
at every index, equality of `ts` and `event` and of the key set; every line also re-serialises to itself
(`json.dumps(obj, ensure_ascii=False)` equals the source line), so the lines that were rewritten differ from the source
in the `path` value only. Lines whose path did not change are byte-identical copies.

## Before / after

| file | lines | lines with `path` replaced | sha256 before | sha256 after |
|---|---|---|---|---|
| `logs_b2/blind_open_log_b2.jsonl` -> `logs_b2_frozen/blind_open_log_b2.jsonl` | 32,291 | 29,380 | `eacce19d35b36c218ab5affb08f2c651fa0bbeff31360ea65224bd75c013e1bd` | `27aa2dfb732a6eb6024ab4ac8ac09834de31d3e2810e03d9bcf0a58b4a01b527` |
| `logs_b2/blind_open_log_b1.jsonl` -> `logs_b2_frozen/blind_open_log_b1.jsonl` | 167 | 46 | `77a06ee7e0346302f31a16dfebd7c0468d0b7345af455bbca305fd0931e435d5` | `7c6be671943b9029c7dbe623d4e1f3ba4d359c8055d9537b3c317c8345255cd8` |

(`blind_open_log_b1.jsonl` inside `logs_b2/` is the audit and plan runs' log, which the audit tool writes under that fixed
name -- `DEVIATIONS_b2.md` D9; it is not a b1 drafting log.)

Which substitution fired, per line:

| substitution | `blind_open_log_b2` | `blind_open_log_b1` (audit/plan runs) |
|---|---|---|
| repo-root prefix -> repo-relative | 947 | 45 |
| home prefix -> `<HOME>/` | 28,391 | 0 |
| system-temp prefix -> `<TMP>/` | 42 | 1 |
| workspace prefix -> `<WORKSPACE>/` | 0 | 0 |
| unchanged (system / device / already-relative) | 2,911 | 121 |
| login name -> `<USER>` after the above | 0 | 0 |

## The draft-call log and the deviations file are copied unchanged

`logs_b2_frozen/draft_calls_b2.jsonl` (875 lines, `531e9e28...`) and `logs_b2_frozen/DEVIATIONS_b2.md` (`1a288784...`) are
byte-identical copies of the files of the same names in `logs_b2/`. Neither contains a filesystem path, host, address,
port, key or the login name (grep count 0 for the home prefix, the temporary prefix and the login name in both). The draft-call log keeps the
prompts and responses verbatim, as 47.3 requires the drafting record to be complete.

## Scan after the transformation

- **Forbidden paths.** Re-scanned with the tool's own matcher (`common.forbidden_hit`, which applies `tools/blind_patterns.json`
  patterns and boundary patterns): **0 hits in both frozen open logs** (32,291 + 167 path values), and 0 hits in the
  originals. The substitution shortens prefixes; it hides nothing.
- **Path and name residue.** The home-directory prefix, the system-temporary-directory prefix and the login name: 0
  occurrences in every file of `logs_b2_frozen/` (this document included; it is written with the tokens instead). Pytest temporary directories named after the login: 0.
  (A loose substring grep for the temporary prefix still matches 27 lines of `blind_open_log_b2.jsonl`; those are
  the random temporary-directory names `<TMP>/tmp5o4k2j11/`, `<TMP>/tmp6f311ldh/`, `<TMP>/tmp8euzg4wx/`, not
  an absolute path. The anchored check, the prefix followed by a slash, gives 0.)
- **Host, address, port, key.** No endpoint URL, `localhost`, port-like `:NNNN` or key/token value appears in the open logs
  or the deviations file. The remaining pattern matches are false positives of a loose grep, listed so the author can
  check them: four dotted-quad-looking strings that are Python package versions inside
  `<HOME>/.local/lib/python3.12/site-packages/<pkg>-<version>.dist-info/entry_points.txt` (`opencv_python_headless-4.13.0.92`,
  `partial_json_parser-0.2.1.1`, `z3_solver-4.16.0.0`, `shellcheck_py-0.11.0.1`); `host` inside the library names
  `ssl_match_hostname` and `model_hosting_container_standards`; `token`/`secret` inside library file names (`tokenizers`,
  `tiktoken`, `tokens.cpython-312.pyc`, the standard-library `secrets` module); two Wikipedia URLs inside Brick
  definition sentences in the draft-call prompts; and, in `DEVIATIONS_b2.md`, the sentence "Host and port are in no
  file" and the word `key` meaning a dictionary key. No credential and no address of a service appears anywhere.
- **Session-directory names.** The scratchpad directory touched by the test harness appears as `<TMP>/claude-1000/-data-workspace-interx-chunktograph/...`:
  a directory *name* that encodes the workspace path (and a numeric account id), the same as in the b1 frozen logs and in
  already-committed files. No further substitution was made; recorded so the author can decide.
