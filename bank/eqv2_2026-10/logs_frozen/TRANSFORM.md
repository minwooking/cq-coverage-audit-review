# Log transformation for the freeze copy (`logs_frozen/`)

> AI-generated draft; the author must review it before relying on it. Addendum 47, 47.3 freeze step: the drafting and
> open logs are committed, so the absolute machine paths that the audit hook recorded are replaced by tokens before
> they go into the repository. The originals in `logs/` and `logs_r2/` stand untouched; nothing in them was edited,
> moved or deleted for this copy.

## Rule applied

Applied to the `path` value of every line, in this order:

1. a path under the repository root (`paper/access2026/`) becomes **repository-relative** (`data/...`, `bank/...`, `harness/...`);
2. any other path under the workspace root becomes **`<WORKSPACE>/...`**;
3. a library path under the user's home becomes **`<HOME>/...`**;
4. a path under the system temporary directory becomes **`<TMP>/...`**;
5. anything else is left exactly as it is (`/usr/...`, `/proc/...`, `/dev/null`, `/etc/...`, and paths already written relative).

Nothing else was changed. **Line count, line order, the `event` and `ts` fields and every other field are preserved
line-for-line, and no line was dropped, merged or reordered** — verified by comparing the two files line by line and
asserting `ts` and `event` equality at every index. Only lines whose `path` changed were rewritten, and their JSON was
re-emitted with the same field set.

## Before / after

| file | lines | lines with `path` replaced | sha256 before | sha256 after |
|---|---|---|---|---|
| `logs/blind_open_log_b1.jsonl` → `logs_frozen/round1/blind_open_log_b1.jsonl` | 34,587 | 30,811 | `83a89ed7b8ee3a4c613fc2bb56057aeddd1f8aa362842e6f88181dfda0e9840e` | `44d8266570419b3684262674fc82f2a9ed6dfe0c01a1fbde9680edb8835b59e3` |
| `logs_r2/blind_open_log_b1.jsonl` → `logs_frozen/round2/blind_open_log_b1.jsonl` | 21,809 | 19,800 | `848e65517fe5a039afa5a28a51253f26140f39fecd1323180fae428c9ddb8f23` | `969924ee753c827ce9365bdebc2dd2c9162fdbd23b36dc541ac3ec781f785851` |

Which substitution fired, per line:

| substitution | round 1 | round 2 |
|---|---|---|
| repo-root prefix → repo-relative | 1,427 | 640 |
| home library prefix → `<HOME>/` | 29,213 | 19,136 |
| system-temp prefix → `<TMP>/` | 167 | 24 |
| workspace prefix → `<WORKSPACE>/` | 4 | 0 |
| unchanged (system / device / already-relative) | 3,776 | 2,009 |

The repo-relative results are all inside `data/` (the snapshot), `bank/eqv2_2026-10/` (this bank's own inputs and
outputs) and `harness/` (the imported anchor module); the 4 workspace-prefixed lines in round 1 are the repository
parent's `.pytest_cache` files that the test harness touched.

## The two draft-call logs are copied unchanged

`logs_frozen/round1/draft_calls_b1.jsonl` and `logs_frozen/round2/draft_calls_b1.jsonl` are byte-identical copies of
`logs/draft_calls_b1.jsonl` (`8f15bf49...`) and `logs_r2/draft_calls_b1.jsonl` (`263d0510...`). They need no path
substitution because they contain no filesystem paths: their fields are `ts`, `cq_id`, `category`, `term`,
`frame_rank`, `latency_s`, `model_id`, `ok`, `attempt`, `error`, `note`, and the `prompt` / `response` bodies. Prompts
and responses are kept verbatim, as 47.3 requires the drafting record to be complete.

## Scan after the transformation

- **Forbidden paths.** Re-scanned with the tool's own list (`tools/blind_patterns.json`, patterns plus boundary patterns
  anchored at a path-segment start): **0 hits on all four frozen files** (34,587 + 21,809 path values). Same verdict as
  the originals — the substitution does not hide anything, it only shortens prefixes.
- **Host, address, port, key.** 0 lines contain a host name, a dotted-quad address, a port-like `:NNNN`, a key or token
  string, or an endpoint URL, in any of the four files. What looks like a dotted-quad (<ip-address>, <ip-address>, <ip-address>,
  <ip-address>) is a **Python package version** inside `<HOME>/.local/lib/python3.12/site-packages/<pkg>-<version>.dist-info/entry_points.txt`
  — a false positive of a dotted-quad grep, no address anywhere. Likewise `sk-3.1.3` appears as part of
  `flask-3.1.3.dist-info`, and `.../tokenizer_config.json` of a local sentence-transformer snapshot is the whole of the
  "token" match. No credential appears in the drafting logs either (the gateway route is named only by the model
  identifier).
- **Session-directory names.** The scratchpad and session-store directories the test harness and the parent session
  touched encode the workspace path with the separators collapsed (`.../-data-workspace-interx-chunktograph/...`, inside
  `<HOME>/.claude/projects/` and `<TMP>/claude-1000/`). Those are directory *names*, not paths under `/home` or `/tmp`,
  and the same project directory name appears in already-committed files elsewhere in this repository, so no further
  substitution was made — recorded here so the author can decide.
- **`secret`.** The single `secret`-like match is `/usr/lib/python3.12/__pycache__/secrets.cpython-312.pyc`, the CPython
  standard-library module, opened while `secrets` was imported. Not a credential.
- **User name.** The substitution above removes the home prefix from every path that had one, but one incidental
  directory name survived this first pass: `<TMP>/pytest-of-<user>/pytest-NNN/...`, i.e. the login name inside a pytest
  temporary-directory name, on 116 lines of `logs_frozen/round1/blind_open_log_b1.jsonl` and 0 lines of round 2. The
  worker left it and reported it. **It was masked afterwards by the maintainer (last section), so the frozen copies
  carry no login name.** Nothing else in the frozen logs carries a personal name.

## Additional rule applied by the maintainer after the worker's report (before the freeze commit)

The worker left the login name inside pytest temporary-directory names (`<TMP>/pytest-of-<user>/...`) on 116 lines of
`logs_frozen/round1/blind_open_log_b1.jsonl` and reported it instead of changing it. Because a login name is a personal
identifier, the maintainer applied one more replacement in the **filtered copy only**: `pytest-of-<login>` becomes
`pytest-of-<USER>`. Line count, order, `ts` and `event` fields are unchanged (34,587 lines); the original
`logs/blind_open_log_b1.jsonl` is untouched. The digest of the filtered round-1 open log in the table above is the
digest **after** this replacement (before it: `435f9cd3e63c55bd602bc46f6da0045b6963773294c0b38a9a0cc03bf6ddc2a7`). Forbidden-path hits remain 0. Round 2 had no such line.
