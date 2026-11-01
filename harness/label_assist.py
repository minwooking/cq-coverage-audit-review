#!/usr/bin/env python3
"""Human-labeling ASSISTANT for the pre-registered primary pass (224 cells).

The human makes every judgment; this tool only presents material, captures
input, and audits. python3.10+ (graph_view additionally needs rdflib, lazily).
UI never pre-excerpts views and never trusts client-side validation (the
server re-validates every save).

One screen reads AND submits: left pane = CQ + meta + judge-span verification
box; right pane tabs = 텍스트 (rendered view, search, selection capture) |
그래프 (ego graph from the variant TTLs, human labels overlaid live from the
current --out CSV) | 도움말 (LABELER_GUIDE.md + fixed rubric/gate sheet). The
bottom input bar (A / rater_L1 / span / note / 저장) is shared by the text and
graph tabs; the save gates (validation, edit-reason audit, sha256 view verify,
repo-out refusal) are unchanged. The 60/session cap and the 12h inter-session
gap were removed on 2026-10-08 at the labeler's request (a logged deviation).

Run:  python label_assist.py --sheet <csv> --views <dir> --out <working.csv>
      [--port 8765] [--ttl-dir <variants root>] [--draft <draft.csv>]
--draft (study mode AH: AI-drafted, human-revised): a machine draft per row is
shown as a card and prefills the input bar, but every save stays a human act
through the unchanged gates; the server itself looks the draft up by cell_id
at save time and stamps draft_A/draft_L1/changed/draft_model/draft_generated_at
on the audit line. Without --draft the behavior is today's, byte for byte.
--ttl-dir defaults to the …/../../variants root resolved from --sheet (same
rule as build_review_viewer); without a resolvable dir the 그래프 tab shows
"TTL 없음" and every other feature stays fully functional. Graphs are
computed lazily per row (VariantGraphs cached per variant), never at startup.

--packet (PREREG sec.12.3 washout, sec.12.4 second annotator): serves a packet
sheet (same 12-column header) in which every row names its OWN view file in
rendered_view_path -- a name relative to --views, listed and sha256-checked in
--sums (default --views/SHA256SUMS.txt; the washout builder keeps views and sums
server-side and gives the rater the sheet only, with one opaque file name per row).
The row's cq_text is shown as given. The screen has no AH draft card, no --cq-ko
translation, no cq_id/category/variant chips and no cell_id; --draft, --cq-ko and
--defer-controls are refused with it. Every save gate is the AH pass's, with no
session cap and no gap, and rater_L1 is required (PREREG DN-9: all four columns).
Dwell is measured on the client with performance.now() (row open to save) and
stored as integer milliseconds in `dwell_ms`, in the audit line (per save) and in
the working CSV (total over the row's saves); the AH-pass elapsed_s (server clock
minus the client's Date) is not used for packets because it carries the client's
clock skew. AI use (PREREG D20) is self-reported in two optional ways: a form at the
end of a SITTING (yes/no, tool name, about how many cells) appended to the session log
as an AI_USE line -- "not recorded" for a skip or no answer; reports are append-only and
each carries the sitting_id and the number of saves it covers -- and a per-row "AI 사용"
tick stored in the ai_used CSV column and in the audit line (unticked = "not recorded").
The working CSV is the 12-column sheet plus ai_used and dwell_ms. Without --packet the
rendering, the audit keys and the session-log line shapes are the AH pass's.
A and rater_L1 are required with every --packet save, and a span when A=1; the note is optional
(washout) unless --require-note is given (second annotator, DN-9: all four columns), PREREG sec.13.1
item 8. --require-note without --packet is refused: the AH pass always required the note.

Serving safety (both modes). The server demands a per-launch token: startup prints a
one-time URL whose token is exchanged for an HttpOnly SameSite=Strict cookie that every
route then requires (--no-token turns this off, loopback --host only). A Host allow-list
(loopback names, the bind address and --allow-host entries) blocks DNS rebinding. POSTs
need Content-Type application/json and a same-origin Origin header, bodies are capped at
64 KB and sockets time out after 30 s. A single-writer flock on <out>.lock stops a second
process from overwriting the labels; SIGHUP and SIGTERM both close the session cleanly (a SIGHUP
the parent set to ignore, as nohup does, stays ignored).
Saves are atomic: the audit line is written first, then the CSV (temp file + fsync +
rename + directory fsync); the in-memory row changes only after the write succeeded.
"""
from __future__ import annotations

import argparse
import atexit
import csv
import functools
import hashlib
import hmac
import html
import http.cookies
import ipaddress
import json
import math
import os
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar, Iterable

try:  # POSIX single-writer lock; absent elsewhere (then no lock is taken)
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

sys.path.insert(0, str(Path(__file__).resolve().parent))
# sibling-import via sys.path is the harness script convention; graph_view is
# this module's only child (brv -> la -> graph_view stays acyclic) and it
# imports no sibling, so no cycle is possible.
import graph_view as gv  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
# --draft mode shares the draft team's header contract with the standalone
# validator (one definition; drift between server and validator impossible).
import validate_draft as vd  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]

LABEL_COL_IDX = (8, 9, 10, 11)  # evidence_span_verbatim, A, rater_L1, note
SHEET_COLUMNS = ("cell_id", "cq_id", "cluster_id", "category", "variant", "cq_text",
                 "judge_evidence_span", "rendered_view_path", "evidence_span_verbatim",
                 "A", "rater_L1", "note")
LEGACY_PACKET_COLUMNS = SHEET_COLUMNS + ("ai_used",)  # the first --packet layout, still read
# --packet working CSV: the sheet + the optional per-row AI tick + the client-measured dwell
PACKET_COLUMNS = SHEET_COLUMNS + ("ai_used", "dwell_ms")
VIEW_REF_COL = 7  # rendered_view_path: in --packet mode the row's own view (file name under --views)
AI_USED_COL = 12  # --packet: "yes" = the labeler ticked "AI 사용" on this row; blank = not recorded
DWELL_MS_COL = 13  # --packet: total client-measured dwell on the row over all its saves, ms
AI_USED_YES = "yes"
AI_NOT_RECORDED = "not recorded"
AI_TOOL_MAX_CHARS = 80
# Domain config (--domain). brick = the locked Brick labeling: no per-cell external-LLM field, audit
# lines and page byte-for-byte as before. A domain that requires it (IOF holdout, PREREG addendum 15
# sec.15.6) must record, per cell, whether an external LLM chat was consulted (none / consulted, plus a
# free-text tool name) and flags a save made under G7_MIN_ELAPSED_S (record only, never a block).
DOMAIN_BRICK = "brick"
DOMAIN_CONFIG: dict[str, dict[str, bool]] = {
    DOMAIN_BRICK: {"require_llm_assist": False},
    "iof": {"require_llm_assist": True},
}
LLM_ASSIST_VALUES = ("none", "consulted")
LLM_ASSIST_REQUIRED_MSG = "외부 LLM 상담 여부(없음/상담함)를 반드시 선택해야 합니다"
LLM_ASSIST_BAD_MSG = "external_llm_assist: 'none' 또는 'consulted'여야 합니다"
G7_MIN_ELAPSED_S = 20.0
AI_APPROX_CELLS_MAX = 1_000_000
MAX_SPAN_CHARS = 8000          # one label's text fields are capped (a longer value is refused, not cut)
MAX_NOTE_CHARS = 4000
MAX_EDIT_REASON_CHARS = 1000
DWELL_MS_MAX = 7 * 24 * 3600 * 1000  # a dwell above a week is a stale tab, not a reading: unknown
HTTP_TIMEOUT_S = 30            # per-socket timeout (slow or stalled clients are dropped)
MAX_BODY_BYTES = 64 * 1024     # POST body cap
COOKIE_NAME = "la_token"
COOKIE_MAX_AGE_S = 30 * 24 * 3600
# one printable line: control characters, C1 controls and the Unicode line/paragraph separators
AI_TOOL_STRIP_RE = re.compile("[\x00-\x1f\x7f-\x9f" + chr(0x2028) + chr(0x2029) + "]+")
# every character str.splitlines() or a JSON-lines reader could take for a line break
LINEBREAK_RE = re.compile("[\r\n\x0b\x0c\x1c\x1d\x1e\x85" + chr(0x2028) + chr(0x2029) + "]")
ASCII_INT_RE = re.compile(r"-?[0-9]{1,9}")
# Control cells whose sheet material differs from what the judge saw (ablated view /
# paraphrased CQ); --defer-controls keeps them out of the queue until that is fixed.
CONTROL_PREFIXES = ("ablated_control:", "preserved_control:")
NOTE_REQUIRED_MSG = "note(근거 요약/사유)를 반드시 적어야 합니다 (언어 무관)"
SHA_RE = re.compile(r"^([0-9a-f]{64})\s+(\S+)$")
VIEW_NAMES = {v: f"rendered_view_{v}.txt" for v in "ABCDEF"}
VALID_TABS = frozenset({"text", "graph", "help"})
GRAPH_BANNER = "그래프 패널 문장은 재구성이라 span 입력 금지 — 원문 인용은 텍스트 탭"
NO_TTL_INFO = ("TTL 없음 — variant TTL 디렉터리를 찾지 못했습니다. "
               "그래프 탭은 비활성이지만 도구는 정상 동작합니다")
PACKET_NO_GRAPH_INFO = ("그래프 없음 — 이 packet 행에는 variant 참조가 없습니다. "
                        "판정 근거는 텍스트 탭의 뷰 원문뿐입니다")
GUIDE_PATH = (Path(__file__).resolve().parents[1]
              / "annotation" / "packet" / "LABELER_GUIDE.md")


class SafetyError(Exception):
    pass


class OutInsideRepo(SafetyError):
    pass


class OutLocked(SafetyError):
    """Another process already holds the single-writer lock on --out."""


class ViewMismatch(SafetyError):
    pass


class SaveError(Exception):
    """Server-side validation failure -> HTTP 400."""


class DraftError(SafetyError):
    pass


@dataclass(frozen=True)
class DraftEntry:
    a: str
    rater: str
    span: str
    note: str
    model: str
    generated_at: str

    def a_int(self) -> int | None:
        return ascii_int(self.a)

    def rater_int(self) -> int | None:
        return ascii_int(self.rater)


def load_drafts(path: Path) -> dict[str, DraftEntry]:
    """Structural load only (file + 7-field header + width); the full value
    contract is validate_draft.py's job and a draft may legitimately be
    partial while the parallel draft team is still generating rows."""
    drafts: dict[str, DraftEntry] = {}
    try:
        records = vd.load_draft_records(path)
    except vd.DraftContractError as exc:
        raise DraftError(str(exc)) from None
    for rec in records:
        if rec["cell_id"] not in drafts:  # first occurrence wins: deterministic
            drafts[rec["cell_id"]] = DraftEntry(rec["A_draft"], rec["rater_L1_draft"],
                                                rec["span_draft"], rec["note_draft"],
                                                rec["model"], rec["generated_at"])
    return drafts


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def ascii_int(text: str) -> int | None:
    """int of a plain ASCII decimal (optional minus, at most 9 digits), else None. str.isdigit()
    also accepts circled and superscript digits, which int() then rejects."""
    text = text.strip()
    return int(text) if ASCII_INT_RE.fullmatch(text) else None


def detect_repo_root(start: Path | None = None) -> Path | None:
    base = (start or Path(__file__).resolve()).parents
    for anc in base:
        if (anc / ".git").exists():
            return anc
    try:  # fallback per brief: harness/../.. is inside the repo tree
        return Path(__file__).resolve().parents[2]
    except IndexError:
        return None


def _git(base: Path, *args: str) -> str | None:
    try:
        res = subprocess.run(["git", "-C", str(base), *args], capture_output=True, text=True,
                             timeout=15, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return res.stdout if res.returncode == 0 else None


@functools.lru_cache(maxsize=32)
def _repo_roots_cached(base: str) -> tuple[Path, ...]:
    root = Path(base)
    found: list[Path] = []

    def add(raw: "str | Path") -> None:
        try:
            resolved = Path(raw).resolve()
        except OSError:
            return
        if resolved not in found:
            found.append(resolved)

    for anc in (root, *root.parents):          # the checkout this file sits in (a .git dir or file)
        if (anc / ".git").exists():
            add(anc)
            break
    top = _git(root, "rev-parse", "--show-toplevel")
    if top and top.strip():
        add(top.strip())
    common = _git(root, "rev-parse", "--git-common-dir")
    if common and common.strip():
        common_dir = Path(common.strip())
        common_dir = (common_dir if common_dir.is_absolute() else root / common_dir).resolve()
        add(common_dir)
        if common_dir.name == ".git":          # the main checkout holds the common .git directory
            add(common_dir.parent)
    listing = _git(root, "worktree", "list", "--porcelain")
    for line in (listing or "").splitlines():  # the main checkout first, then every linked worktree
        if line.startswith("worktree "):
            add(line[len("worktree "):])
    if not found:                              # no git at all: keep the old file-based guess
        fallback = detect_repo_root()
        if fallback is not None:
            add(fallback)
    return tuple(found)


def repo_roots(start: Path | None = None) -> list[Path]:
    """The main checkout and every linked worktree of the repository holding ``start`` (default:
    this file), from git itself (--git-common-dir, worktree list). A worktree knows only its own
    root from a .git lookup, so a path inside the MAIN checkout would pass a naive guard."""
    base = Path(start).resolve() if start is not None else Path(__file__).resolve().parent
    if base.is_file():
        base = base.parent
    return list(_repo_roots_cached(str(base)))


def check_out_path(out: Path, repo_root: Path | None = None,
                   roots: "Iterable[Path] | None" = None) -> None:
    """Refuse any path that resolves inside the repository: the main checkout or any of its
    worktrees (see repo_roots). A worktree also lives under /.claude/worktrees/, so the substring
    check stays. ``repo_root`` (tests) restricts the check to that one root, ``roots`` replaces the
    git-derived list."""
    resolved = Path(out).expanduser().resolve()
    if "/.claude/worktrees/" in str(resolved):
        raise OutInsideRepo(f"--out 저장소 내부(worktree) 금지: {resolved}")
    if repo_root is not None:
        checked: list[Path] = [Path(repo_root)]
    elif roots is not None:
        checked = [Path(r) for r in roots]
    else:
        checked = repo_roots()
    for root in checked:
        if resolved == root or root in resolved.parents:
            raise OutInsideRepo(f"--out 저장소 내부 금지 (repo root={root}): {resolved}")


def verify_views(views_dir: Path) -> dict[str, Path]:
    """Return variant -> path after sha256-checking all six views against
    views/SHA256SUMS.txt. Raise ViewMismatch on any missing entry or mismatch."""
    sums_path = views_dir / "SHA256SUMS.txt"
    if not sums_path.is_file():
        raise ViewMismatch(f"SHA256SUMS.txt 없음: {sums_path}")
    sums: dict[str, str] = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        m = SHA_RE.match(line.strip())
        if m:
            sums[m.group(2)] = m.group(1)
    for variant, name in VIEW_NAMES.items():
        path = views_dir / name
        if not path.is_file():
            raise ViewMismatch(f"뷰 파일 없음: {path}")
        if name not in sums:
            raise ViewMismatch(f"SHA256SUMS.txt에 {name} 항목 없음")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != sums[name]:
            raise ViewMismatch(f"sha256 불일치: {name} (기대 {sums[name][:12]}… 실제 {digest[:12]}…)")
    return {v: views_dir / n for v, n in VIEW_NAMES.items()}


def _parse_sha256sums(sums_path: Path) -> dict[str, str]:
    if not sums_path.is_file():
        raise ViewMismatch(f"SHA256SUMS.txt 없음: {sums_path}")
    sums: dict[str, str] = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        m = SHA_RE.match(line.strip())
        if m:
            sums[m.group(2)] = m.group(1)
    return sums


def _safe_view_ref(ref: str) -> bool:
    """A packet view name is a plain relative file name under --views: no
    surrounding blanks, no absolute path, no '..', no backslash, no NUL."""
    if not ref or ref != ref.strip() or ref.startswith("/") or "\\" in ref or "\x00" in ref:
        return False
    parts = Path(ref).parts
    return bool(parts) and ".." not in parts and parts[0] != "/"


def verify_packet_views(views_dir: Path, refs: "set[str] | frozenset[str] | list[str]",
                        sums_path: Path | None = None) -> dict[str, Path]:
    """--packet: ref -> path for every view name a sheet carries, each checked against the sums
    file (default views_dir/SHA256SUMS.txt; --sums puts it elsewhere, e.g. outside the views
    directory) -- listed, present, inside views_dir, sha256 equal. Unlike verify_views the names are
    the sheet's own, so a washout control can carry a regenerated view. Raise ViewMismatch on the
    first problem."""
    sums = _parse_sha256sums(sums_path if sums_path is not None else views_dir / "SHA256SUMS.txt")
    root = views_dir.resolve()
    out: dict[str, Path] = {}
    for ref in sorted(set(refs)):
        if not _safe_view_ref(ref):
            raise ViewMismatch(f"안전하지 않은 뷰 참조(rendered_view_path): {ref!r}")
        path = views_dir / ref
        if not path.is_file():
            raise ViewMismatch(f"뷰 파일 없음: {path}")
        if root not in path.resolve().parents:
            raise ViewMismatch(f"뷰 참조가 views 디렉터리 밖을 가리킴: {ref!r}")
        if ref not in sums:
            raise ViewMismatch(f"SHA256SUMS.txt에 {ref} 항목 없음")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != sums[ref]:
            raise ViewMismatch(f"sha256 불일치: {ref} (기대 {sums[ref][:12]}… 실제 {digest[:12]}…)")
        out[ref] = path
    return out


def packet_rows(path: Path) -> list[list[str]]:
    """Rows (header first) of a packet sheet or working CSV, always in the 14-column --packet
    layout: a 12-column sheet (or the earlier 13-column working CSV) gets the empty optional
    columns appended. Header and row widths are checked."""
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    header = [c.strip() for c in rows[0]] if rows else []
    if header not in (list(SHEET_COLUMNS), list(LEGACY_PACKET_COLUMNS), list(PACKET_COLUMNS)):
        raise SafetyError(f"{path}: 헤더가 기대 12열(또는 ai_used/dwell_ms가 붙은 13·14열)과 다릅니다")
    pad = [""] * (len(PACKET_COLUMNS) - len(header))
    out = [list(PACKET_COLUMNS)]
    for number, row in enumerate(rows[1:], start=2):
        if len(row) != len(header):
            raise SafetyError(f"{path} 행 {number}: 열 수 {len(row)} ({len(header)}열 필요)")
        out.append(row + pad)
    return out


def sheet_view_refs(*csv_paths: Path) -> set[str]:
    """The distinct rendered_view_path values of one or more packet sheets (header checked)."""
    refs: set[str] = set()
    for path in csv_paths:
        refs.update(row[VIEW_REF_COL] for row in packet_rows(path)[1:])
    return refs


@dataclass(frozen=True)
class Row:
    idx: int  # CSV row index (header is 0); ?row=N uses this space
    cell_id: str
    category: str
    variant: str
    cq_text: str
    judge_evidence_span: str
    cells: tuple[str, ...]


@dataclass
class AuditEntry:
    ts: str
    cell_id: str
    row: int
    a: int
    span_chars: int
    rater_l1: str
    first_opened_ts: str | None
    elapsed_s: float | None
    session_id: str
    edit_reason: str | None = None
    draft_fields: dict[str, object] | None = None
    extra_fields: dict[str, object] | None = None  # --packet: {"ai_used": true | null (not recorded)}

    def to_json(self) -> dict[str, object]:
        d: dict[str, object] = {
            "ts": self.ts, "cell_id": self.cell_id, "row": self.row, "A": self.a,
            "span_chars": self.span_chars, "rater_L1": self.rater_l1,
            "first_opened_ts": self.first_opened_ts, "elapsed_s": self.elapsed_s,
            "session_id": self.session_id}
        if self.edit_reason is not None:
            d["edit_reason"] = self.edit_reason
        if self.draft_fields is not None:  # present iff --draft mode; None = no draft
            d.update(self.draft_fields)
        if self.extra_fields is not None:  # present iff --packet mode
            d.update(self.extra_fields)
        return d


def one_line(text: str) -> str:
    """The text with every possible line break written as a visible \\uXXXX escape, so a free-text
    value can never start another log record (inside a JSON string that escape is the JSON one)."""
    return LINEBREAK_RE.sub(lambda m: "\\u%04x" % ord(m.group(0)), text)


def _fsync_dir(directory: Path) -> None:
    """Make a rename or a new file in ``directory`` durable (POSIX; a no-op where unsupported)."""
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _append_text(path: Path, line: str) -> None:
    """Append one line, flushed to disk. The line is forced onto a single physical line."""
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(one_line(line) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


def _write_rows_atomic(out: Path, rows: list[list[str]]) -> None:
    tmp = out.with_name(out.name + f".tmp{os.getpid()}")
    # Default csv dialect (CRLF terminator, QUOTE_MINIMAL) round-trips the
    # sealed sheet byte-for-byte, so untouched columns stay byte-identical.
    try:
        with open(tmp, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows(rows)
            fh.flush()
            os.fsync(fh.fileno())           # the bytes are on disk before the rename publishes them
        os.replace(tmp, out)
    except BaseException:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    _fsync_dir(out.parent)                  # and the rename itself survives a crash


def _coerce_int(val: object, field_name: str, allowed: set[int]) -> int:
    if isinstance(val, bool):
        raise SaveError(f"{field_name}: 정수여야 합니다")
    if isinstance(val, str) and ascii_int(val) is not None:
        val = ascii_int(val)
    if not isinstance(val, int) or val not in allowed:
        raise SaveError(f"{field_name}: 허용값 {sorted(allowed)} (받은 값 {val!r})")
    return val


def _coerce_row(val: object, n_rows: int) -> int:
    """Row index space: data rows are 1..n_rows-1 (header is 0, same as ?row=N)."""
    if isinstance(val, str) and ascii_int(val) is not None:
        val = ascii_int(val)
    if isinstance(val, bool) or not isinstance(val, int) or not 1 <= val < n_rows:
        raise SaveError(f"row: 1..{n_rows - 1} 정수여야 합니다 (받은 값 {val!r})")
    return val


RATER_REQUIRED_MSG = "rater_L1(0–3)을 선택해야 합니다 — packet 모드에서는 모든 행에 A와 rater_L1이 필요합니다"
WRITE_FAILED_MSG = ("서버가 파일에 쓰지 못했습니다 (디스크/권한) — 저장되지 않았습니다. "
                    "잠시 뒤 다시 시도하고, 계속되면 서버를 확인하세요")


def parse_dwell_ms(raw: object) -> int | None:
    """The client-measured dwell as integer milliseconds, or None when it is not a plausible
    reading (not a number, negative, NaN/inf, longer than a week)."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    if isinstance(raw, float) and not math.isfinite(raw):
        return None
    value = int(round(raw))
    return value if 0 <= value <= DWELL_MS_MAX else None


class Store:
    """Owns the working CSV + both sidecars. It is the ONLY writer."""

    def __init__(self, sheet: Path, out: Path, views: dict[str, Path],
                 clock=time.time, drafts: dict[str, DraftEntry] | None = None,
                 draft_name: str | None = None,
                 defer_prefixes: tuple[str, ...] = (), packet: bool = False,
                 require_note: bool = False, domain: str = DOMAIN_BRICK) -> None:
        # domain: key of DOMAIN_CONFIG; a require_llm_assist domain adds the per-cell external-LLM field.
        # packet=True (--packet): `views` maps each row's rendered_view_path to its file
        # (verify_packet_views); the AH draft and --defer-controls cannot be combined.
        # require_note (--packet only): an empty note is refused (second annotator, DN-9); without it
        # a --packet save takes the note as optional (washout, PREREG sec.13.1 item 8).
        self.out, self.views, self._clock = out, views, clock
        self.drafts, self.draft_name = drafts, draft_name
        self.packet = packet
        self.require_note = require_note
        if domain not in DOMAIN_CONFIG:
            raise SafetyError(f"알 수 없는 --domain: {domain!r} (가능: {sorted(DOMAIN_CONFIG)})")
        self.domain = domain
        self.llm_assist_required = DOMAIN_CONFIG[domain]["require_llm_assist"]
        if require_note and not packet:
            raise SafetyError("--require-note는 --packet과 함께만 쓸 수 있습니다 (AH 화면은 note가 늘 필수)")
        self.ai_use: dict[str, object] | None = None  # --packet: the latest AI-use self-report
        self.report_seq = 0       # --packet: AI_USE lines written by this process (append-only)
        self.sitting_n = 1        # --packet: a report closes a sitting; the next save opens the next
        self.sitting_saves = 0    # --packet: saves in the open sitting (what a report would cover)
        if packet:
            if drafts is not None or draft_name or defer_prefixes:
                raise SafetyError("--packet은 AH 초안·--defer-controls와 함께 쓸 수 없습니다")
            missing = sheet_view_refs(sheet) - set(views)
            if missing:
                raise SafetyError(f"뷰가 검증되지 않은 참조: {sorted(missing)[:3]}")
        self.audit_path = Path(str(out) + ".audit.jsonl")
        self.log_path = Path(str(out) + ".session_log.txt")
        self.session_id = f"{int(clock())}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self.lock = threading.Lock()
        self.last_save_ts: float | None = None
        if not out.exists():
            if packet:  # the working CSV is the sheet + the empty optional ai_used column
                _write_rows_atomic(out, packet_rows(sheet))
            else:
                out.write_bytes(sheet.read_bytes())  # exact byte-copy seed
        if packet:
            self.rows: list[list[str]] = packet_rows(out)
        else:
            with open(out, newline="", encoding="utf-8") as fh:
                self.rows = list(csv.reader(fh))
            if [c.strip() for c in self.rows[0]] != list(SHEET_COLUMNS):
                raise SafetyError(f"--out/--sheet 헤더가 기대 12열과 다릅니다: {self.rows[0]}")
        if packet:
            missing = {r[VIEW_REF_COL] for r in self.rows[1:]} - set(views)
            if missing:
                raise SafetyError(f"--out의 뷰 참조가 --sheet의 것과 다릅니다: {sorted(missing)[:3]}")
            # a resumed working CSV must come from THIS sheet: cell ids, CQ text, spans and view names
            front = VIEW_REF_COL + 1
            if [r[:front] for r in packet_rows(sheet)] != [r[:front] for r in self.rows]:
                raise SafetyError("--out이 다른 시트에서 만들어졌습니다: --sheet와 cell_id·CQ·뷰 열이 다릅니다")
        # Deferred rows are never served or saved; an empty tuple defers nothing.
        self.deferred = frozenset(i for i in range(1, len(self.rows))
                                  if defer_prefixes and self.rows[i][0].startswith(defer_prefixes))
        self._closed = False
        draft_tag = f" draft={self.draft_name}" if self.draft_name else ""
        defer_tag = f" deferred={len(self.deferred)}" if self.deferred else ""
        packet_tag = (f" sitting_id={self.sitting_id} mode=packet "
                      f"sheet_sha256={hashlib.sha256(sheet.read_bytes()).hexdigest()[:16]}"
                      f"{' require_note=yes' if require_note else ''}"
                      if packet else "")
        if self.llm_assist_required:
            packet_tag += f" domain={domain} llm_assist=required"
        _append_text(self.log_path,
                     f"SESSION start={now_iso()} pid={os.getpid()} "
                     f"session_id={self.session_id}{draft_tag}{defer_tag}{packet_tag}")

    @property
    def note_required(self) -> bool:
        """True when a save needs a non-empty note: always in the AH pass, and with --packet only
        under --require-note."""
        return (not self.packet) or self.require_note

    @property
    def sitting_id(self) -> str:
        """--packet: the id of the open sitting. A sitting is the run of saves between two AI-use
        reports; every audit line, the SESSION lines and the AI_USE lines name theirs, so a report
        covers only its own sitting's saves (session_id stays the per-process id)."""
        return f"{self.session_id}.{self.sitting_n}"

    # ---- read side -------------------------------------------------------
    def labeled_count(self) -> int:
        return sum(1 for r in self.rows[1:] if r[9].strip())

    def served(self) -> list[int]:
        return [i for i in range(1, len(self.rows)) if i not in self.deferred]

    def first_unlabeled(self) -> int | None:
        for i in self.served():
            if not self.rows[i][9].strip():
                return i
        return None

    def row(self, idx: int) -> Row:
        c = self.rows[idx]
        return Row(idx, c[0], c[3], c[4], c[5], c[6], tuple(c))

    def clamp_row(self, idx: int | None) -> int:
        served = self.served()
        if not served:
            raise SafetyError("제공할 행이 없습니다 (모든 행이 보류됨)")
        if idx is None:
            return self.first_unlabeled() or served[-1]
        idx = max(1, min(idx, len(self.rows) - 1))
        if idx in self.deferred:  # never render a deferred row; move to the nearest served one
            later = [i for i in served if i > idx]
            return later[0] if later else served[-1]
        return idx

    def nav(self, idx: int) -> tuple[int, int]:
        """(prev, next) over served rows, clamped at both ends."""
        served = self.served()
        before = [i for i in served if i < idx]
        after = [i for i in served if i > idx]
        return (before[-1] if before else idx), (after[0] if after else idx)

    def view_text(self, variant: str) -> str:
        return self.views[variant].read_text(encoding="utf-8")

    def row_view_text(self, r: Row) -> str:
        """The view a row is judged on: its variant's view (AH pass) or, with --packet,
        the file its own rendered_view_path names."""
        return self.views[r.cells[VIEW_REF_COL] if self.packet else r.variant].read_text(
            encoding="utf-8")

    def session_saved(self) -> int:
        if not self.audit_path.exists():
            return 0
        n = 0
        for line in self.audit_path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict) and entry.get("session_id") == self.session_id and "A" in entry:
                n += 1
        return n

    def gated_reason(self) -> str | None:
        return None  # no session gates remain (cap and 12h gap removed 2026-10-08)

    def status(self) -> dict[str, object]:
        status: dict[str, object] = {
            "progress": {"labeled": self.labeled_count(), "total": len(self.rows) - 1},
            "session_saved": self.session_saved(), "gated_reason": self.gated_reason(),
            "deferred": len(self.deferred)}
        if self.packet:  # keys only in --packet mode: the AH status JSON is unchanged
            status["ai_use"] = self.ai_use["used"] if self.ai_use else None
            status["sitting_id"] = self.sitting_id
            status["saves_since_last_report"] = self.sitting_saves
        return status

    def ai_report_done(self) -> bool:
        """--packet: True while the open sitting has no unreported save (a report was given and
        nothing was saved since)."""
        return self.ai_use is not None and self.sitting_saves == 0

    def _ai_use_entry(self, used: str, tool: str, approx: int | None, how: str) -> dict[str, object]:
        # report_seq is committed by the caller AFTER the line is on disk, so a failed write
        # leaves no gap in the numbering
        return {"phase": "end", "used": used, "tool": tool, "approx_cells": approx, "how": how,
                "ts": now_iso(), "session_id": self.session_id, "sitting_id": self.sitting_id,
                "saves_since_last_report": self.sitting_saves, "report_seq": self.report_seq + 1}

    def record_ai_use(self, payload: dict[str, object]) -> dict[str, object]:
        """--packet: the end-of-sitting AI-tool self-report (PREREG D20) -> one `AI_USE {json}`
        line in the session log. Reports are APPEND-ONLY: a later one never replaces an earlier one;
        each names the sitting it closes and how many saves that sitting holds
        (saves_since_last_report), and the next save opens a new sitting. Fields: used yes|no, tool
        (required for yes), approx_cells (about how many cells used it; optional for yes, 0 for no).
        A skip is stored as used="not recorded". The tool name is flattened to one line of
        printable text so it cannot forge another log line."""
        if not self.packet:
            raise SaveError("AI 사용 자기보고는 --packet 모드에서만 받습니다")
        if payload.get("phase", "end") != "end":
            raise SaveError("AI 사용 자기보고는 세션 종료 때만 받습니다 (시작 양식 없음)")
        skipped = payload.get("skipped") is True
        used_raw = payload.get("used")
        tool = ""
        approx: int | None = None
        if skipped:
            used = AI_NOT_RECORDED
        else:
            if isinstance(used_raw, str):
                used_raw = {"yes": True, "no": False}.get(used_raw.strip().lower(), used_raw)
            if not isinstance(used_raw, bool):
                raise SaveError("예/아니오 중 하나를 고르거나 '건너뛰기'를 누르세요")
            used = "yes" if used_raw else "no"
            if used_raw:
                tool = re.sub(r"\s+", " ", AI_TOOL_STRIP_RE.sub(" ", str(payload.get("tool") or ""))).strip()
                tool = tool[:AI_TOOL_MAX_CHARS].strip()
                if not tool:
                    raise SaveError("AI 도구를 썼다면 도구 이름을 적어 주세요 (또는 '건너뛰기')")
                raw_n = payload.get("approx_cells")
                if isinstance(raw_n, str):
                    raw_n = raw_n.strip()
                    raw_n = None if raw_n == "" else (ascii_int(raw_n) if ASCII_INT_RE.fullmatch(raw_n) else raw_n)
                if raw_n is not None:
                    if isinstance(raw_n, bool) or not isinstance(raw_n, int) or not 0 <= raw_n <= AI_APPROX_CELLS_MAX:
                        raise SaveError(f"대략 몇 셀: 0 이상 {AI_APPROX_CELLS_MAX} 이하의 정수 "
                                        f"(또는 비워 두기); 받은 값 {str(raw_n)[:20]!r}")
                    approx = raw_n
            else:
                approx = 0
        with self.lock:
            entry = self._ai_use_entry(used, tool, approx, "skipped" if skipped else "answered")
            _append_text(self.log_path, "AI_USE " + json.dumps(entry, ensure_ascii=False,
                                                              separators=(",", ":")))
            self.report_seq += 1
            self.ai_use = entry
            self.sitting_n += 1      # the report closes this sitting; the next save opens the next
            self.sitting_saves = 0
        return {"ok": True, "used": used}

    def draft_for(self, cell_id: str) -> DraftEntry | None:
        return self.drafts.get(cell_id) if self.drafts is not None else None

    def row_overlay(self, idx: int) -> dict[str, object]:
        """Current label state of a row in the live out CSV. The 그래프 tab
        overlays it immediately (a saved A=1 span shows as the green caption
        without any rebuild), exactly like --working badges in the viewer."""
        c = self.rows[idx]
        a = c[9].strip()
        ov: dict[str, object] = {"badge": a or None}
        if a == "1" and c[8].strip():
            ov["lab_ev"] = c[8].strip()
        if a == "0" and c[11].strip():
            ov["lab_note"] = c[11].strip()
        return ov

    # ---- write side ------------------------------------------------------
    def save(self, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        """One label save. Everything is validated first; then the audit line is written (durably),
        then the CSV is replaced atomically from a COPY of the rows, and only then does the in-memory
        row change -- a failed write leaves memory, CSV and next save consistent."""
        with self.lock:
            idx = _coerce_row(payload.get("row"), len(self.rows))
            if idx in self.deferred:
                raise SaveError("보류 중인 행입니다 — 지금은 저장할 수 없습니다")
            cells = self.rows[idx]
            if str(payload.get("cell_id", "")) != cells[0]:
                raise SaveError(f"cell_id 불일치: 시트={cells[0]!r} 요청={payload.get('cell_id')!r}")
            a = _coerce_int(payload.get("A"), "A", {0, 1})
            span = str(payload.get("evidence_span_verbatim") or "")
            note = str(payload.get("note") or "")
            rater_val = payload.get("rater_L1")
            rater = "" if rater_val in (None, "") else str(_coerce_int(rater_val, "rater_L1", {0, 1, 2, 3}))
            if self.packet and not rater:
                raise SaveError(RATER_REQUIRED_MSG)
            if len(span) > MAX_SPAN_CHARS:
                raise SaveError(f"span: 최대 {MAX_SPAN_CHARS}자 (받은 길이 {len(span)})")
            if len(note) > MAX_NOTE_CHARS:
                raise SaveError(f"note: 최대 {MAX_NOTE_CHARS}자 (받은 길이 {len(note)})")
            if a == 0:
                span = ""  # guide: unsupported rows keep the span empty
            elif not span.strip():
                raise SaveError("A=1이면 검증 대상 뷰에서 인용한 비어 있지 않은 span이 필요합니다")
            if self.note_required and not note.strip():  # A=0 reason / A=1 evidence summary
                raise SaveError(NOTE_REQUIRED_MSG)
            if not note.strip():  # only reachable where the note is optional: a blank note is stored empty
                note = ""
            llm_assist: str | None = None
            llm_tool: str | None = None
            if self.llm_assist_required:  # domain-gated: the brick path never reads these keys
                raw_assist = payload.get("external_llm_assist")
                if raw_assist in (None, ""):
                    raise SaveError(LLM_ASSIST_REQUIRED_MSG)
                if raw_assist not in LLM_ASSIST_VALUES:
                    raise SaveError(LLM_ASSIST_BAD_MSG)
                llm_assist = str(raw_assist)
                if llm_assist == "consulted":
                    llm_tool = re.sub(r"\s+", " ", AI_TOOL_STRIP_RE.sub(
                        " ", str(payload.get("external_llm_tool") or ""))).strip()[:AI_TOOL_MAX_CHARS].strip() or None
            ai_flag = payload.get("ai_used") if self.packet else None
            if ai_flag is not None and not isinstance(ai_flag, bool):
                raise SaveError("ai_used: true 또는 false (선택 사항)")
            dwell_ms = parse_dwell_ms(payload.get("dwell_ms")) if self.packet else None
            old_a, old_l1, old_span, old_note = cells[9].strip(), cells[10], cells[8], cells[11]
            edit_reason = str(payload.get("edit_reason") or "")
            if len(edit_reason) > MAX_EDIT_REASON_CHARS:
                raise SaveError(f"edit_reason: 최대 {MAX_EDIT_REASON_CHARS}자 (받은 길이 {len(edit_reason)})")
            if old_a and not edit_reason.strip():
                raise SaveError("이미 라벨된 행의 수정에는 감사 사유(edit_reason)가 필요합니다")
            t = self._clock()
            new_cells = list(cells)  # mutate a copy; self.rows changes only after the write succeeded
            new_cells[LABEL_COL_IDX[0]], new_cells[9], new_cells[10], new_cells[11] = span, str(a), rater, note
            first_opened = payload.get("first_opened")
            if isinstance(first_opened, str):
                first_opened = first_opened[:64]  # a timestamp is short; anything longer is junk
            elapsed: float | None = None
            audit_extra: dict[str, object] | None = None
            if self.packet:
                # "yes" = ticked; unticked or missing stays blank = not recorded
                new_cells[AI_USED_COL] = AI_USED_YES if ai_flag is True else ""
                # Dwell is the CLIENT's performance.now() delta (row open to save): immune to the
                # clock skew of an off-box device. The CSV keeps the total over the row's saves, the
                # audit line this save's own value; elapsed_s is that value in seconds (None = unknown).
                prior_total = ascii_int(cells[DWELL_MS_COL]) if len(cells) > DWELL_MS_COL else None
                if dwell_ms is not None:
                    new_cells[DWELL_MS_COL] = str((prior_total or 0) + dwell_ms)
                    elapsed = round(dwell_ms / 1000, 1)
                audit_extra = {"ai_used": True if ai_flag is True else None, "dwell_ms": dwell_ms,
                               "sitting_id": self.sitting_id}
                if old_a:  # an edit keeps what it replaced
                    audit_extra.update({"prior_A": ascii_int(old_a), "prior_L1": old_l1 or None,
                                        "prior_span": old_span, "prior_note": old_note})
            else:
                # elapsed_s preference: client-reported first_opened (dwell on the
                # row) wins; fallback is time since this session's previous save;
                # None on the first save with no timestamp (documented choice).
                if isinstance(first_opened, str) and first_opened:
                    try:
                        elapsed = round(t - datetime.fromisoformat(first_opened).timestamp(), 1)
                    except ValueError:
                        pass
                elif self.last_save_ts is not None:
                    elapsed = round(t - self.last_save_ts, 1)
                # Clock skew / future-dated client timestamps must not poison the
                # G7 under-20s statistic: a negative dwell is unknown, not instant.
                if elapsed is not None and elapsed < 0:
                    elapsed = None
            warnings: list[str] = []
            if self.llm_assist_required:
                under = None if elapsed is None else elapsed < G7_MIN_ELAPSED_S
                audit_extra = dict(audit_extra or {})
                audit_extra.update({"external_llm_assist": llm_assist, "external_llm_tool": llm_tool,
                                    "domain": self.domain, "under_g7_min": under})
                if under:
                    warnings.append(f"셀당 {elapsed}초 — G7 기준 {G7_MIN_ELAPSED_S:g}초 미만 (기록만 됨, 저장은 허용)")
            # The draft fact is server-side truth: the client never reports
            # whether a draft existed, so a tampered UI cannot erase the AH
            # provenance. changed compares the FINAL stored values (span is
            # post-force-clear) against the four draft fields.
            draft_fields: dict[str, object] | None = None
            if self.drafts is not None:
                d = self.drafts.get(cells[0])
                draft_fields = {
                    "draft_A": d.a if d else None, "draft_L1": d.rater if d else None,
                    "changed": (None if d is None else
                                (str(a) != d.a or rater != d.rater
                                 or span != d.span or note != d.note)),
                    "draft_model": d.model if d else None,
                    "draft_generated_at": d.generated_at if d else None}
            audit = AuditEntry(now_iso(), cells[0], idx, a, len(span), rater,
                               first_opened if isinstance(first_opened, str) else None,
                               elapsed, self.session_id, edit_reason or None,
                               draft_fields, audit_extra)
            _append_text(self.audit_path, json.dumps(audit.to_json(), ensure_ascii=False))  # audit first
            new_rows = list(self.rows)
            new_rows[idx] = new_cells
            _write_rows_atomic(self.out, new_rows)
            self.rows[idx] = new_cells
            if old_a:
                _append_text(self.log_path, f"EDIT {cells[0]} {old_a}->{a} "
                                            f"reason={json.dumps(edit_reason, ensure_ascii=False)} ts={audit.ts}")
            self.last_save_ts = t
            if self.packet:
                self.sitting_saves += 1
            result: dict[str, object] = {"ok": True, "next": self.first_unlabeled()}
            if warnings:  # only a require_llm_assist domain ever reaches this
                result["warnings"] = warnings
            return 200, result

    def log_session_end(self) -> None:
        if not self._closed:
            self._closed = True
            if self.packet and (self.sitting_saves > 0 or self.report_seq == 0):
                # an open sitting with saves, or a process that never reported at all, ends with an
                # explicit "unanswered" line: "not recorded", never silently absent
                entry = self._ai_use_entry(AI_NOT_RECORDED, "", None, "unanswered")
                _append_text(self.log_path, "AI_USE " + json.dumps(
                    entry, ensure_ascii=False, separators=(",", ":")))
                self.report_seq += 1
            sitting_tag = f" sitting_id={self.sitting_id}" if self.packet else ""
            _append_text(self.log_path,
                         f"SESSION end={now_iso()} pid={os.getpid()} saved={self.session_saved()}{sitting_tag}")


class GraphProvider:
    """Lazy per-row ego graphs (decision: lazy, not compute-at-startup —
    startup stays instant and the blank sheet's first row pays only its own
    VariantGraph parse; ego_graph itself is ms-scale so egos are not cached).
    Missing ttl-dir/rdflib/broken TTL degrades to info text: the labeling
    tool stays fully functional."""

    def __init__(self, store: Store, ttl_dir: Path | None) -> None:
        self.store, self.ttl_dir = store, ttl_dir
        self._cache: dict[str, gv.VariantGraph] = {}
        self._lock = threading.Lock()

    def graph_for(self, idx: int) -> tuple[gv.EgoGraph | None, str | None]:
        if self.ttl_dir is None:
            return None, NO_TTL_INFO
        r = self.store.row(idx)
        if self.store.packet and not r.variant.strip():  # a washout row carries no variant
            return None, PACKET_NO_GRAPH_INFO
        path = self.ttl_dir / r.variant / f"graph_{r.variant}.ttl"
        if not path.is_file():
            return None, f"TTL 없음 — {path.name} 파일이 없습니다"
        try:
            with self._lock:
                vg = self._cache.get(r.variant)
                if vg is None:
                    vg = self._cache[r.variant] = gv.load_variant_ttl(path)
        except gv.TtlLoadError as exc:
            return None, f"TTL 로드 실패 — {exc}"
        jev = gv.judge_ev(gv.split_fragments(r.judge_evidence_span))
        return gv.ego_graph(vg, gv.cq_tokens(r.cq_text), jev), None


# --------------------------------------------------------------------------
# 도움말: LABELER_GUIDE.md rendered + fixed rubric/gate sections
# --------------------------------------------------------------------------

def md_to_html(md: str) -> str:
    """Minimal markdown -> HTML for the guide: headings, bold, code, ordered
    and unordered lists, links degraded to text. Escapes first, so the only
    tags emitted are the ones matched here."""
    out: list[str] = []
    list_mode: str | None = None

    def close() -> None:
        nonlocal list_mode
        if list_mode:
            out.append(f"</{list_mode}>")
            list_mode = None

    def inline(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
        return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", s)

    for line in md.splitlines():
        t = line.strip()
        if not t:
            close()
        elif t.startswith("### "):
            close()
            out.append(f"<h6>{inline(t[4:])}</h6>")
        elif t.startswith("## "):
            close()
            out.append(f"<h5>{inline(t[3:])}</h5>")
        elif t.startswith("# "):
            close()
            out.append(f"<h4>{inline(t[2:])}</h4>")
        elif m := re.match(r"^[-*] (.*)", t):
            if list_mode != "ul":
                close()
                out.append("<ul>")
                list_mode = "ul"
            out.append(f"<li>{inline(m.group(1))}</li>")
        elif m := re.match(r"^\d+\. (.*)", t):
            if list_mode != "ol":
                close()
                out.append("<ol>")
                list_mode = "ol"
            out.append(f"<li>{inline(m.group(1))}</li>")
        else:
            close()
            out.append(f"<p>{inline(t)}</p>")
    close()
    return "\n".join(out)


_HELP_RUBRIC = """\
<h3>판정 4사례 — 인용 span 존재 × CQ 답지지</h3>
<table>
<tr><th>뷰에서 충분 span 인용 가능</th><th>CQ의 답을 지지</th><th>기록</th></tr>
<tr><td>예</td><td>예 — 개념+관계/정의의 직접 진술</td><td><b>A=1</b> + 최단 충분 span + note 근거 요약 (rater_L1=3 후보, '완전' 경계)</td></tr>
<tr><td>예</td><td>예 — 핵심 개념+관계 있음, 세부만 누락</td><td><b>A=1</b> + 그 span + note 근거 요약 (rater_L1=2 후보, '대체로' 경계)</td></tr>
<tr><td>예</td><td>아니오 — 관련 개념만 있고 핵심 관계 미진술</td><td><b>A=0</b> + note (주제 근접은 근거 아님, rater_L1=1 경계)</td></tr>
<tr><td>아니오</td><td>(어느 쪽이든)</td><td><b>A=0</b> + note. 답을 알 것 같아도 원문 인용이 불가하면 mentally repair하지 말고 A=0</td></tr>
</table>
<h3>rater_L1 앵커 (0–3)</h3>
<ul>
<li><b>0</b> — 답 없음: CQ에 답할 내용이 뷰에 전혀 없음 (A=0과 조합)</li>
<li><b>1</b> — 부분: 관련 개념만 보이지만 핵심 관계/계층 미진술 (A=0과 조합되는 경계)</li>
<li><b>2</b> — 대체로: 핵심 개념+관계 있고 세부만 누락 (A=1과 조합)</li>
<li><b>3</b> — 완전: CQ에 직접 답하는 진술 존재 (A=1과 조합)</li>
</ul>
<p><b>A</b>는 '근거 텍스트 존재' 여부, <b>rater_L1</b>은 '답 질 수준' — 다른 물음이다.
최종 L1* = J (A=1일 때), 그 외 min(J,1).</p>
<h3>키보드 단축키</h3>
<p>입력칸(검색·span·note·감사 사유)에 포커스가 있거나 Ctrl/Meta/Alt를 누르면 동작하지 않는다.</p>
<table>
<tr><th>키</th><th>동작</th></tr>
<tr><td><kbd>1</kbd> / <kbd>0</kbd></td><td>A=1 근거 있음 / A=0 근거 없음</td></tr>
<tr><td><kbd>q</kbd> <kbd>w</kbd> <kbd>e</kbd> <kbd>r</kbd></td><td>rater_L1 = 0 / 1 / 2 / 3</td></tr>
<tr><td><kbd>s</kbd></td><td>저장 후 다음 미라벨 행 (저장 단추가 활성일 때만)</td></tr>
<tr><td><kbd>/</kbd></td><td>뷰 내부 검색칸으로 이동</td></tr>
<tr><td><kbd>c</kbd></td><td>선택한 텍스트를 span으로 캡처</td></tr>
<tr><td><kbd>g</kbd> / <kbd>t</kbd></td><td>그래프 / 텍스트 탭</td></tr>
<tr><td><kbd>[</kbd> / <kbd>]</kbd></td><td>이전 / 다음 행</td></tr>
</table>
"""
_HELP_DRAFT_NOTE = """\
<p>미라벨 행에 초안이 채워져 있고 A·rater_L1·span이 모두 초안 그대로면 입력 바에
'초안 그대로(미수정)' 표시(노란 점선)가 뜬다. 표시일 뿐 저장을 막지 않는다.</p>
"""
_HELP_GATES = """\
<h3>게이트 요약</h3>
<ul>
<li><b>note는 모든 행에서 필수</b> — 언어 무관 (A=1: 근거 요약 / A=0: 사유). 비어 있으면 저장 불가</li>
<li>세션당 60행 상한과 세션 간 12시간 규칙은 2026-10-08 라벨러 결정으로 해제됨 (프로토콜 이탈로 기록)</li>
<li>목표 <b>~90초/행</b> — 어려운 케이스를 서두르지 말 것. dwell은 audit의 elapsed_s로 기록</li>
<li>이미 라벨된 행 수정에는 <b>edit_reason</b> 필수, EDIT 라인이 session_log에 남음</li>
<li>모든 저장·수정·오버라이드는 <b>audit.jsonl</b>에 — 20초 미만 저장 통계(G7)의 원본</li>
</ul>
"""
_HELP_BLIND = """\
<h3>블라인드 규칙</h3>
<p>judge의 J 점수·근거·응답 필드는 탐색/기록 금지. 왼쪽 회색 상자의
judge_evidence_span은 <b>검증 대상</b> 표시일 뿐 판단 근거가 아니다. 그래프
패널·외부 자료·자기 도메인 지식으로 공백을 메우지 말 것 — 판정 근거는 렌더된
뷰 원문뿐이다.</p>"""
# Byte-identical to the former single FIXED_HELP literal (the AH-pass help tab).
FIXED_HELP = _HELP_RUBRIC + _HELP_DRAFT_NOTE + _HELP_GATES + _HELP_BLIND

# --packet help: same rubric and blind rules; the draft note and the AH-pass gate summary
# are replaced by the washout / second-annotator conditions (PREREG sec.12, D19, D20).
_HELP_GATES_PACKET_TOP = """\
<h3>게이트 요약 (packet: washout · 2차 annotator)</h3>
<ul>
"""
_HELP_NOTE_REQUIRED = """\
<li><b>A · rater_L1(0–3) · note는 모든 행에서 필수</b> (A=1이면 span도) — 언어 무관. 비어 있으면 저장 불가 (2차 annotator: 네 열 모두, PREREG §13.1 8 · DN-9)</li>
"""
_HELP_NOTE_OPTIONAL = """\
<li><b>A · rater_L1(0–3)는 모든 행에서 필수</b> (A=1이면 span도). note는 선택이다 (washout) — 적으면 그대로 기록된다. 필수 칸이 비어 있으면 저장 불가 (PREREG §13.1 8)</li>
"""
_HELP_GATES_PACKET_REST = """\
<li>세션당 셀 수 상한도 세션 간 최소 간격도 없다 (PREREG §12 D19). 세션 시작·종료 시각과 셀별 체류 시간이 기록된다</li>
<li>체류 시간(dwell_ms)은 브라우저가 행을 연 순간부터 저장까지를 밀리초로 재어 audit과 CSV에 남긴다. 최소 체류는 강제하지 않는다</li>
<li>AI 채팅 도구는 허용된다. 한 번 앉은 자리를 마칠 때 오른쪽 위 '세션 종료 · AI 사용 보고'에 사용 여부(예/아니오), 도구 이름, 대략 몇 셀에 썼는지를 적는다. 건너뛰거나 적지 않으면 '기록되지 않음(not recorded)'으로 남는다. 보고는 덧붙이기만 되고(고치거나 덮어쓰지 못한다) 그 앉은 자리의 저장만 가리킨다. 각 행의 'AI 사용' 체크는 선택 사항이며 비워 두면 '기록되지 않음'이다 (PREREG §12 D20)</li>
<li>목표 <b>~90초/행</b> — 어려운 케이스를 서두르지 말 것</li>
<li>이미 라벨된 행 수정에는 <b>edit_reason</b> 필수, 수정 전 값은 audit에 남고 EDIT 라인이 session_log에 남음</li>
<li>모든 저장·수정은 <b>audit.jsonl</b>에 — 20초 미만 저장 통계(G7식 점검)의 원본</li>
<li>이 화면에는 AI 초안·한국어 번역·cq_id·category·variant·cell_id 표시가 없다</li>
</ul>
"""
_HELP_BLIND_PACKET_NOTE = """
<p>AI 채팅 도구를 써도 A=1의 근거는 렌더된 뷰 원문에서 verbatim으로 인용한 span뿐이다.
이 연구의 산출물(AH 초안, judge 출력, 저자의 라벨, 결과 수치)은 보지 않는다.</p>"""


def packet_fixed_help(require_note: bool = False) -> str:
    gates = (_HELP_GATES_PACKET_TOP + (_HELP_NOTE_REQUIRED if require_note else _HELP_NOTE_OPTIONAL)
             + _HELP_GATES_PACKET_REST)
    return _HELP_RUBRIC + gates + _HELP_BLIND + _HELP_BLIND_PACKET_NOTE


PACKET_FIXED_HELP = packet_fixed_help(False)               # washout: the note is optional
PACKET_FIXED_HELP_REQUIRE_NOTE = packet_fixed_help(True)   # second annotator: --require-note


def build_help_html(guide_path: Path = GUIDE_PATH, packet: bool = False, require_note: bool = False) -> str:
    """Assembled once at startup. Guide missing/unreadable -> fixed sections
    only (the tool must not die because a documentation file moved)."""
    try:
        guide = ("<h3>레이블러 가이드 — LABELER_GUIDE.md 전문</h3>\n"
                 + md_to_html(guide_path.read_text(encoding="utf-8")))
    except OSError:
        guide = "<h3>레이블러 가이드</h3><p>가이드 파일을 읽을 수 없어 고정 요약만 표시합니다.</p>"
    return guide + "\n" + ((PACKET_FIXED_HELP_REQUIRE_NOTE if require_note else PACKET_FIXED_HELP)
                          if packet else FIXED_HELP)


# --------------------------------------------------------------------------
# HTTP surface
# --------------------------------------------------------------------------
PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>label_assist 행 %(idx)d</title><style>
:root{--ink:#0f172a;--muted:#475569;--line:#cbd5e1;--accent:#0369a1;--accent-bg:#bfdbfe;--accent-ink:#1e3a8a;--warn:#b45309;--danger:#b91c1c;--draft-bg:#fefce8;--draft-line:#ca8a04;--ok:#15803d}
body{margin:0;font-family:sans-serif;background:#fafafa;color:var(--ink);font-size:14px;display:flex;flex-direction:column;height:100vh}
.banner{background:var(--danger);color:#fff;padding:.5em .8em;font-weight:700}
.banner summary{cursor:pointer}
.notice{background:#fef3c7;border-bottom:1px solid #f59e0b;padding:.4em .8em}
#narrow{display:none;background:#fef3c7;border-bottom:1px solid #f59e0b;padding:.4em .8em}
#wrap{flex:1;min-height:0;display:flex}
#left{width:38%%;min-width:280px;overflow:auto;padding:.8em 1em;border-right:2px solid var(--line);background:#f8fafc}
#right{flex:1;min-width:0;display:flex;flex-direction:column}
#hdr{line-height:1.8;font-size:14px}
#hdr a{display:inline-block;min-height:24px;line-height:24px;padding:0 .5em}
#hdr progress{width:9em;height:.9em;vertical-align:middle;accent-color:var(--accent)}
#hdr progress.warn{accent-color:var(--danger)}
#cq{font-size:26px;line-height:1.35;margin:.1em 0 .5em}
.chip{display:inline-block;background:#e0e7ff;border-radius:1em;padding:.15em .7em;margin:.1em;font-size:14px}
.graybox{background:#e5e7eb;border:1px solid #6b7280;padding:.6em;margin:.6em 0;font-size:14px;white-space:pre-wrap}
.draftcard{background:var(--draft-bg);border:2px solid var(--draft-line);border-radius:.4em;padding:.6em;margin:.6em 0;font-size:14px;white-space:pre-wrap}
.draftcard .dfh{font-weight:700}
#tabs{display:flex;gap:.4em;padding:.5em .8em 0}
.tabb{padding:.35em 1.2em;border:1px solid #64748b;background:#e2e8f0;cursor:pointer;border-radius:.5em .5em 0 0;font-weight:700;font-size:1em}
.tabb.on{background:var(--accent);color:#fff}
#tabtext{flex:1;min-height:0;overflow:auto;background:#fff;border-top:1px solid var(--line);padding:0 .8em .8em}
#bar{position:sticky;top:0;background:#fafafa;padding:.5em 0;z-index:2}
#hitcount{margin-left:.5em;color:var(--muted)}
#emptyview{background:#fee2e2;border:1px solid var(--danger);padding:.5em;margin-top:.4em}
#view{background:#fff;border:1px solid var(--line);padding:.6em;white-space:pre-wrap;font-size:15px;margin-top:.4em}
mark{background:#fde047}
mark.cur{background:#fb923c}
mark.jump{background:#6ee7b7}
#tabgraph{flex:1;min-height:0;flex-direction:column;display:none;padding:.5em .8em}
#tabhelp{flex:1;min-height:0;overflow:auto;background:#fff;border-top:1px solid var(--line);padding:.6em 1.2em;display:none;line-height:1.5}
#tabhelp table{border-collapse:collapse;margin:.5em 0}
#tabhelp td,#tabhelp th{border:1px solid #64748b;padding:.3em .6em;text-align:left;font-size:14px}
#inbar{border-top:3px solid var(--accent);background:#fff;padding:.5em .8em;display:flex;flex-wrap:wrap;gap:.4em .8em;align-items:flex-start;max-height:45vh;overflow:auto;flex-shrink:0}
#inbar .grp{display:flex;flex-wrap:wrap;align-items:center;gap:.2em;border:1px solid var(--line);border-radius:.4em;padding:.2em .5em}
#inbar textarea{font:inherit;flex:1 1 16em;min-width:10em}
#stat{flex:1 1 100%%;display:flex;flex-wrap:wrap;gap:.3em .8em;align-items:center;min-height:1.6em}
#inbar.untouched{border:3px dashed var(--draft-line);background:var(--draft-bg)}
#dchip{display:none;border-radius:1em;padding:.15em .7em;font-size:.85em;font-weight:700}
#inbar.untouched #dchip{display:inline-block;background:#fde68a;color:#713f12;border:1px solid var(--draft-line)}
#dchip.edited{display:inline-block;background:#dcfce7;color:#14532d;border:1px solid #16a34a}
#dwarn{color:var(--warn);font-weight:700}
#hint,#msg{color:var(--muted)}
kbd{font:.75em monospace;border:1px solid #64748b;border-bottom-width:2px;border-radius:.25em;padding:0 .35em;margin-left:.3em;background:#f1f5f9;color:#334155}
.tabb.on kbd{color:var(--ink)}
button{margin:.15em;padding:.4em .8em;cursor:pointer;min-height:28px}
button:disabled{opacity:.55;cursor:not-allowed}
button.on:not(.tabb){background:var(--accent-bg);border:2px solid var(--accent-ink);font-weight:700}
button.on:not(.tabb)::before{content:"\\2713 "}
button:focus-visible,a:focus-visible,input:focus-visible,textarea:focus-visible,summary:focus-visible{outline:3px solid #f59e0b;outline-offset:2px}
button.primary{margin-left:auto;background:var(--accent);color:#fff;border:1px solid #075985;font-weight:700;padding:.5em 1.2em}
button.primary:disabled{background:#64748b}
#why{color:var(--danger);font-weight:700}
label{font-weight:700}
@media(max-width:900px){
 #wrap{flex-direction:column}
 #left{width:auto;min-width:0;flex:0 0 auto;max-height:35vh;border-right:0;border-bottom:2px solid var(--line)}
 #right{min-height:0}
 #inbar textarea{flex:1 1 100%%}
 #cq{font-size:20px}
}
@media(max-width:767px){#narrow{display:block}}
%(graph_css)s
</style></head><body>
<div id="narrow" role="note">화면 폭이 768px 미만입니다 — 라벨링은 넓은 화면(데스크톱)에서 하는 것을 권장합니다.</div>
%(notice_html)s%(packet_panel)s
<div id="wrap">
<div id="left">
<h2 id="cq">%(cq_text)s</h2>%(cq_ko_html)s
<div id="hdr"><b>%(pos)d/%(total)d</b> · labeled %(labeled)d · session %(sess)d<br>
 <label>전체 <progress id="pall" max="%(total_max)d" value="%(labeled)d" aria-label="전체 라벨 진행"></progress></label><br>
 <a id="prevlink" href="/?row=%(prev)s&tab=%(init_tab)s" aria-keyshortcuts="[">이전<kbd>[</kbd></a> <a id="nextlink" href="/?row=%(next_nav)s&tab=%(init_tab)s" aria-keyshortcuts="]">다음<kbd>]</kbd></a>
 · <a href="/export">CSV 내보내기</a></div>
<div>%(chips)s</div>
<div class="graybox"><b>참고용 — judge의 인용 주장. 검증 대상일 뿐, 판단 근거로 쓰지 마시오</b>
%(judge_span)s</div>
%(draft_card)s
</div>
<div id="right">
<div id="tabs" role="tablist" aria-label="보기 전환">
<button class="tabb on" id="btnt" role="tab" aria-selected="true" aria-controls="tabtext" aria-keyshortcuts="t" onclick="setTab('text')">텍스트<kbd>t</kbd></button>
<button class="tabb" id="btng" role="tab" aria-selected="false" aria-controls="tabgraph" aria-keyshortcuts="g" onclick="setTab('graph')">그래프<kbd>g</kbd></button>
<button class="tabb" id="btnh" role="tab" aria-selected="false" aria-controls="tabhelp" onclick="setTab('help')">도움말</button></div>
<div id="tabtext" role="tabpanel" aria-labelledby="btnt">
<div id="bar"><input id="q" size="30" aria-label="뷰 내부 검색" aria-keyshortcuts="/" placeholder="뷰 내부 검색 (대소문자 무시) — / 키로 포커스, Enter로 다음">
<button onclick="doSearch(0)">검색</button><button onclick="doSearch(1)">다음</button><span id="hitcount" role="status"></span>
<button aria-keyshortcuts="c" onclick="capture()">선택을 span으로<kbd>c</kbd></button>%(jump_btns)s</div>
%(empty_view)s<pre id="view">%(view)s</pre>
</div>
<div id="tabgraph" role="tabpanel" aria-labelledby="btng">
%(graph_canvas)s
</div>
<div id="tabhelp" role="tabpanel" aria-labelledby="btnh">%(help_html)s</div>
<div id="inbar" role="group" aria-label="판정 입력">
<span id="dchip" role="status"></span>
<div class="grp" role="group" aria-labelledby="lbA"><label id="lbA">A</label>
<button data-a="1" aria-pressed="false" aria-keyshortcuts="1" onclick="setA(1)">A=1 근거 있음<kbd>1</kbd></button>
<button data-a="0" aria-pressed="false" aria-keyshortcuts="0" onclick="setA(0)">A=0 근거 없음<kbd>0</kbd></button></div>
<div class="grp" role="group" aria-labelledby="lbR"><label id="lbR">rater_L1</label>
<button data-r="0" aria-pressed="false" aria-keyshortcuts="q" onclick="setR(0)">0<kbd>q</kbd></button><button data-r="1" aria-pressed="false" aria-keyshortcuts="w" onclick="setR(1)">1<kbd>w</kbd></button><button data-r="2" aria-pressed="false" aria-keyshortcuts="e" onclick="setR(2)">2<kbd>e</kbd></button><button data-r="3" aria-pressed="false" aria-keyshortcuts="r" onclick="setR(3)">3<kbd>r</kbd></button></div>
<textarea id="span" rows="3" aria-label="evidence_span_verbatim" placeholder="evidence_span_verbatim — 검증 대상 뷰의 최단 충분 원문 인용 (수정 가능, 직접 입력도 허용)">%(span_v)s</textarea>
<textarea id="note" rows="2" aria-label="note" placeholder="note — 언어 무관 (A=1: 근거 요약 / A=0: 사유)%(note_opt)s">%(note_v)s</textarea>
%(llm_inbar)s<span id="editrow"%(edit_hidden)s>감사 사유(수정 필수): <input id="edit_reason" size="24" aria-label="감사 사유(edit_reason)"></span>%(packet_inbar)s
<button id="submit" class="primary" aria-keyshortcuts="s" onclick="save()">저장 후 다음 미라벨 행<kbd>s</kbd></button>
<div id="stat"><span id="dwarn" role="status"></span>%(llm_timer_html)s<span id="hint" role="status"></span><span id="msg" role="status" aria-live="polite"></span><span id="why" role="status" aria-live="polite"></span></div>
</div>
</div>
</div>
<script>
const ROW=%(idx)d, CELL=%(cell_js)s, view=document.getElementById("view");
const rawText=view.textContent, spanEl=document.getElementById("span");
const noteEl=document.getElementById("note"), whyEl=document.getElementById("why");
const hintEl=document.getElementById("hint"), msgEl=document.getElementById("msg");
const inbar=document.getElementById("inbar");
const submitBtn=document.getElementById("submit"), editEl=document.getElementById("edit_reason");
let a=%(a_js)s, rater=%(r_js)s;
const wasLabeled=%(was_js)s;
const D=%(draft_js)s; // draft snapshot {a,rater,span} for the untouched indicator only; never sent to /save
const JUDGE=%(judge_frag_js)s; // judge span fragments, only used to locate/highlight in the view
const a0=a, r0=rater, span0=spanEl.value, note0=noteEl.value;
let saved=false, saving=false;
const firstOpened=new Date().toISOString();%(packet_t0_js)s%(llm_state_js)s
function flash(t){msgEl.textContent=t;}
function isDirty(){return !saved&&(a!==a0||rater!==r0||spanEl.value!==span0||noteEl.value!==note0);}
window.addEventListener("beforeunload",function(ev){if(isDirty()){ev.preventDefault();ev.returnValue="";}});
function setA(v){a=v;refresh();} function setR(v){rater=v;refresh();}
function comboHint(){
 if(a===1&&rater!==null&&rater<2)return "참고: A=1은 보통 rater_L1 2-3과 조합됩니다 (강제 아님)";
 if(a===0&&rater!==null&&rater>=2)return "참고: A=0은 보통 rater_L1 0-1과 조합됩니다 (강제 아님)";
 return "";
}
function refresh(){
 document.querySelectorAll("[data-a]").forEach(b=>{const on=Number(b.dataset.a)===a;b.classList.toggle("on",on);b.setAttribute("aria-pressed",on?"true":"false");});
 document.querySelectorAll("[data-r]").forEach(b=>{const on=Number(b.dataset.r)===rater;b.classList.toggle("on",on);b.setAttribute("aria-pressed",on?"true":"false");});
 let why="";
 if(!why){
  if(a===null)why="A 값을 선택하세요";
  else if(a===1&&!spanEl.value.trim())why="A=1이면 span이 필요합니다";%(note_check_js)s
  else if(wasLabeled&&!editEl.value.trim())why="이미 라벨된 행: 감사 사유를 입력하세요";%(packet_why_js)s%(llm_why_js)s
 }
 whyEl.textContent=why; submitBtn.disabled=!!why||saving;
 hintEl.textContent=comboHint();
 draftMark();
}
function draftMark(){
 const chip=document.getElementById("dchip"), dw=document.getElementById("dwarn");
 dw.textContent="";
 if(!D||wasLabeled){inbar.classList.remove("untouched");chip.className="";chip.textContent="";return;}
 const same=(a===D.a&&rater===D.rater&&spanEl.value===D.span);
 inbar.classList.toggle("untouched",same);
 chip.className=same?"":"edited";
 chip.textContent=same?"초안 그대로(미수정)":"초안에서 수정됨";
 if(spanEl.value===D.span&&D.span&&!rawText.includes(D.span))dw.textContent="경고: 초안 span이 뷰 원문에 verbatim으로 없습니다 - 직접 확인하세요 (저장은 가능)";
}
function selOffsets(){
 const s=getSelection(); if(!s||!s.rangeCount)return null;
 const r=s.getRangeAt(0);
 if(r.collapsed||!view.contains(r.commonAncestorContainer))return null;
 const pre=document.createRange(); pre.selectNodeContents(view); pre.setEnd(r.startContainer,r.startOffset);
 const st=pre.toString().length; return [st,st+r.toString().length];
}
function restoreSel(o){
 if(!o)return;
 const w=document.createTreeWalker(view,NodeFilter.SHOW_TEXT), range=document.createRange();
 let pos=0,n,sset=false,eset=false;
 while((n=w.nextNode())){const L=n.nodeValue.length;
  if(!sset&&o[0]<=pos+L){range.setStart(n,o[0]-pos);sset=true;}
  if(sset&&o[1]<=pos+L){range.setEnd(n,o[1]-pos);eset=true;break;}
  pos+=L;}
 if(sset&&eset){const s=getSelection();s.removeAllRanges();s.addRange(range);}
}
function esc(s){return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
function renderMarks(rs){ // display-only highlight; textContent of #view never changes
 const so=selOffsets(); let out="",last=0;
 rs.forEach(r=>{out+=esc(rawText.slice(last,r[0]))+'<mark class="'+r[2]+'">'+esc(rawText.slice(r[0],r[1]))+"</mark>";last=r[1];});
 out+=esc(rawText.slice(last)); view.innerHTML=out; restoreSel(so);
}
function capture(){
 const s=getSelection(); if(!s||!s.rangeCount||s.isCollapsed){flash("뷰 원문에서 span으로 쓸 텍스트를 먼저 드래그 선택하세요.");return;}
 if(!view.contains(s.getRangeAt(0).commonAncestorContainer)){flash("뷰 영역 안에서 드래그 선택하세요.");return;}
 spanEl.value=s.toString(); flash(""); refresh();
}
let hits=[],hi=0,lastTerm="";
function doSearch(step){
 const term=document.getElementById("q").value; hits=[]; lastTerm=term;
 if(term){const low=rawText.toLowerCase(),q=term.toLowerCase();let i=low.indexOf(q);
  while(i>=0){hits.push(i);i=low.indexOf(q,i+q.length);} }
 if(hits.length)hi=((step>0&&hi+1<hits.length)?hi+1:0);
 renderMarks(hits.map((h,k)=>[h,h+term.length,k===hi?"cur":"hit"]));
 const hc=document.getElementById("hitcount");
 hc.textContent=term?(hits.length?(hi+1)+" / "+hits.length+"건":"0건"):"";
 if(hits.length)view.getElementsByTagName("mark")[hi].scrollIntoView({block:"center"});
}
function jumpTo(frags){
 const rs=[];
 frags.forEach(f=>{if(!f)return;const i=rawText.indexOf(f);if(i>=0)rs.push([i,i+f.length,"jump"]);});
 rs.sort((x,y)=>x[0]-y[0]);
 const clean=[]; rs.forEach(r=>{if(!clean.length||r[0]>=clean[clean.length-1][1])clean.push(r);});
 if(!clean.length){flash("뷰 원문에서 해당 span을 verbatim으로 찾지 못했습니다.");return;}
 setTab("text"); renderMarks(clean); hits=[]; document.getElementById("hitcount").textContent="";
 view.getElementsByTagName("mark")[0].scrollIntoView({block:"center"}); flash("");
}
async function save(){
 const body={row:ROW,cell_id:CELL,A:a,evidence_span_verbatim:spanEl.value,rater_L1:rater,note:noteEl.value,first_opened:firstOpened};
 if(wasLabeled)body.edit_reason=editEl.value;%(packet_body_js)s%(llm_body_js)s
 const orig=submitBtn.innerHTML; saving=true; submitBtn.disabled=true; submitBtn.textContent="저장 중…";
 try{
  const res=await fetch("/save",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const j=await res.json();
  if(j.ok){saved=true;
   const t=(tab==="graph"?"graph":"text");
   if(j.next===null){location.href="/?row="+ROW+"&tab="+t+"#done";location.reload();}
   else{location.href="/?row="+j.next+"&tab="+t;}
   return;}
  saving=false; submitBtn.innerHTML=orig; refresh();
  whyEl.textContent=j.error||"저장 거부됨"; submitBtn.disabled=true;
 }catch(err){
  saving=false; submitBtn.innerHTML=orig; refresh();
  whyEl.textContent="저장 요청 실패: "+(err&&err.message?err.message:err)+" - 네트워크/서버 확인 후 다시 시도하세요";
 }
}
["span","note","edit_reason"].forEach(id=>document.getElementById(id).addEventListener("input",refresh));
document.getElementById("q").addEventListener("keydown",function(ev){
 if(ev.key==="Enter"){ev.preventDefault();doSearch(ev.target.value===lastTerm&&hits.length?1:0);}});
refresh();
if(location.hash==="#done")flash("모든 행 완료 - 더 이상 미라벨 행이 없습니다.");
const EGOHOST={graph:null,overlay:null,draftSpan:(D&&!wasLabeled)?D.span:"",emptyInfo:"그래프 계산 중…",visible:false};
const panels={text:document.getElementById("tabtext"),graph:document.getElementById("tabgraph"),help:document.getElementById("tabhelp")};
const tabbtns={text:document.getElementById("btnt"),graph:document.getElementById("btng"),help:document.getElementById("btnh")};
let tab="%(init_tab)s",gloaded=false;
function setTab(t){tab=t;EGOHOST.visible=(t==="graph");
 panels.text.style.display=t==="text"?"block":"none";
 panels.graph.style.display=t==="graph"?"flex":"none";
 panels.help.style.display=t==="help"?"block":"none";
 for(const k in tabbtns){tabbtns[k].className="tabb"+(k===t?" on":"");tabbtns[k].setAttribute("aria-selected",k===t?"true":"false");}
 inbar.style.display=t==="help"?"none":"";
 if(t==="graph"){if(!gloaded)fetchGraph();else egoInvalidate(true);}}
async function fetchGraph(){gloaded=true;EGOHOST.emptyInfo="그래프 계산 중…";
 try{const res=await fetch("/graph?row="+ROW);const j=await res.json();
  EGOHOST.graph=j.graph||null;EGOHOST.emptyInfo=j.info||(j.graph?"":"그래프 없음");
  EGOHOST.overlay=j.overlay||null;}catch(err){EGOHOST.graph=null;EGOHOST.emptyInfo="그래프 요청 실패";}
 egoInvalidate(true);}
setTab(tab);
document.addEventListener("keydown",function(ev){
 if(ev.ctrlKey||ev.metaKey||ev.altKey||ev.isComposing)return;
 const el=document.activeElement,tg=el&&el.tagName;
 if(tg==="INPUT"||tg==="TEXTAREA"||tg==="SELECT"||(el&&el.isContentEditable))return;
 const k=ev.key.length===1?ev.key.toLowerCase():ev.key;
 if(k==="g"){setTab("graph");}
 else if(k==="t"){setTab("text");}
 else if(k==="["){const l=document.getElementById("prevlink");if(l)location.href=l.href;}
 else if(k==="]"){const l=document.getElementById("nextlink");if(l)location.href=l.href;}
 else if(tab==="help"){return;}
 else if(k==="1"){setA(1);}
 else if(k==="0"){setA(0);}
 else if(k==="q"){setR(0);} else if(k==="w"){setR(1);}
 else if(k==="e"){setR(2);} else if(k==="r"){setR(3);}
 else if(k==="s"){if(!submitBtn.disabled)save();}
 else if(k==="c"){capture();}
 else if(k==="/"){setTab("text");document.getElementById("q").focus();}
 else return;
 ev.preventDefault();
});
%(graph_js)s%(packet_js)s
</script></body></html>"""


PACKET_JS = """
// --packet: AI-tool self-report at SESSION END (PREREG D20). Never blocks labeling; a skip is "not recorded".
const AI={done:%(ai_done)s};
const aiPanel=document.getElementById("aipanel"), aiMsg=document.getElementById("aimsg");
const aiToolEl=document.getElementById("aitool"), aiCellsEl=document.getElementById("aicells");
function aiShow(){
 document.querySelectorAll('input[name="aiused"]').forEach(function(r){r.checked=false;});
 aiToolEl.value="";aiCellsEl.value="";aiMsg.textContent="";aiPanel.style.display="";}
async function aiSend(skip){
 const used=document.querySelector('input[name="aiused"]:checked');
 const body={skipped:!!skip,used:used?used.value==="yes":null,tool:aiToolEl.value,approx_cells:aiCellsEl.value};
 try{
  const res=await fetch("/ai_use",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const j=await res.json();
  if(j.ok){AI.done=true;aiMsg.textContent="";aiPanel.style.display="none";}
  else{aiMsg.textContent=j.error||"기록 실패";}
 }catch(err){aiMsg.textContent="요청 실패: "+(err&&err.message?err.message:err);}
}
if(location.hash==="#done"&&!AI.done)aiShow();
"""
PACKET_BODY_JS = (' body.ai_used=document.getElementById("aicell").checked;'
                  ' body.dwell_ms=Math.round(performance.now()-ROW_T0);')
# the dwell clock: performance.now() is monotonic and local to the browser, so a skewed wall clock on an
# off-box device cannot change it; ROW_T0 is taken when the row page's script starts (row open)
PACKET_T0_JS = " const ROW_T0=performance.now();"
# require_llm_assist domains only (IOF): a required none/consulted choice per cell, a free-text tool name,
# and a live G7 timer that warns under 20 s (the server records it; saving is never blocked). A brick page
# gets "" for all of these, so its HTML is byte-identical to before.
LLM_INBAR_HTML = (
    '<div class="grp" role="group" aria-labelledby="lbL"><label id="lbL">외부 LLM 상담</label>'
    '<button data-l="none" aria-pressed="false" onclick="setL(\'none\')">없음</button>'
    '<button data-l="consulted" aria-pressed="false" onclick="setL(\'consulted\')">상담함</button>'
    '<input id="llm_tool" size="16" maxlength="80" aria-label="external_llm_tool" '
    'placeholder="도구명 (선택)" style="display:none"></div>')
LLM_STATE_JS = (
    '\nlet llm=null; const llmToolEl=document.getElementById("llm_tool"), tmsg=document.getElementById("tmsg");'
    '\nfunction setL(v){llm=v;refresh();}'
    '\nllmToolEl.addEventListener("input",refresh);'
    '\nfunction tick(){const s=Math.round((Date.now()-Date.parse(firstOpened))/1000);'
    'tmsg.textContent=s<%(g7)d?"경과 "+s+"초 — G7 기준 %(g7)d초 미만 (기록만 됨, 저장은 가능)":"";}'
    '\nsetInterval(tick,1000); tick();')
LLM_WHY_JS = ('\n  if(!why&&llm===null)why="외부 LLM 상담 여부(없음/상담함)를 반드시 선택해야 합니다";'
              '\n  document.querySelectorAll("[data-l]").forEach(b=>{const on=b.dataset.l===llm;'
              'b.classList.toggle("on",on);b.setAttribute("aria-pressed",on?"true":"false");});'
              '\n  llmToolEl.style.display=llm==="consulted"?"":"none";')
LLM_BODY_JS = (' body.external_llm_assist=llm; if(llm==="consulted")body.external_llm_tool=llmToolEl.value;')
# The note rule of the input bar: the AH pass (and --packet --require-note) disables the save button
# while the note is empty; a --packet washout page has no such line (the note is optional, PREREG
# sec.13.1 item 8). For the AH page the expansion is today's text, byte for byte.
NOTE_CHECK_JS = '\n  else if(!noteEl.value.trim())why="note(근거 요약/사유)를 반드시 적어야 합니다 (언어 무관)";'
NOTE_OPTIONAL_PLACEHOLDER = " (선택)"
# the save button stays disabled until rater_L1 is chosen (PREREG DN-9: all four columns)
PACKET_WHY_JS = '\n  if(!why&&rater===null)why="rater_L1(0–3)을 선택하세요";'


def packet_panel_html(store: "Store") -> str:
    """--packet only: the session-end AI-use form (hidden until the 세션 종료 button, or until
    every row is done). Inline styles only, so the shared CSS (and the AH page) is untouched."""
    return ('<div id="aipanel" class="notice" role="region" aria-label="AI 도구 사용 자기보고" '
            'style="display:none">'
            '<b id="ailab">AI 도구 사용 자기보고 — 세션 종료</b> '
            '<label><input type="radio" name="aiused" value="yes"> 예</label> '
            '<label><input type="radio" name="aiused" value="no"> 아니오</label> '
            '<label>도구 이름 <input id="aitool" size="20" maxlength="80" '
            'aria-label="AI 도구 이름"></label> '
            '<label>대략 몇 셀 <input id="aicells" size="5" inputmode="numeric" '
            'aria-label="AI를 쓴 셀 수(대략)"></label> '
            '<button id="aisend" onclick="aiSend(false)">기록</button>'
            '<button id="aiskip" onclick="aiSend(true)">건너뛰기</button> '
            '<span id="aimsg" role="status"></span></div>'
            '<button id="aiend" onclick="aiShow()" style="position:fixed;right:.6em;top:.3em;'
            'z-index:5;margin:0;padding:.15em .6em;min-height:24px;font-size:12px">'
            '세션 종료 · AI 사용 보고</button>')


def packet_inbar_html(r: "Row") -> str:
    """--packet only: the optional per-row "AI 사용" tick (saved to the ai_used column and the
    audit line). Never required; unticked/missing means "not recorded"."""
    checked = (" checked" if len(r.cells) > AI_USED_COL
               and r.cells[AI_USED_COL].strip().lower() == AI_USED_YES else "")
    return ('<label class="grp" title="이 행의 판정에 AI 도구를 썼다면 체크 — 선택 사항, '
            '비워 두면 \'기록되지 않음\'">'
            f'<input type="checkbox" id="aicell"{checked}> AI 사용</label>')


def packet_js(store: "Store") -> str:
    return PACKET_JS % {"ai_done": json.dumps(store.ai_report_done())}


def _cq_ko_html(entry) -> str:
    if not entry:
        return ""
    ko = entry[0]
    return (f'<div id="cqko" lang="ko" style="margin:-4px 0 8px;font-size:15px">'
            f'<b>{html.escape(ko)}</b>'
            f'<br><small style="opacity:.6">번역은 참고용 — 판정은 영어 원문 CQ 기준</small></div>')


def draft_card_html(d: DraftEntry) -> str:
    return ('<div class="draftcard"><div class="dfh">AI 초안 — 확인하거나 수정하세요'
            f' (drafted {html.escape(d.model)} @ {html.escape(d.generated_at)})</div>'
            f'A={html.escape(d.a)} · rater_L1={html.escape(d.rater)}\n'
            f'span: {html.escape(d.span) or "(비어 있음)"}\n'
            f'note: {html.escape(d.note) or "(비어 있음)"}</div>')


def render_page(store: Store, idx: int, tab: str = "text", help_html: str = "",
                notice: str = "") -> bytes:
    r = store.row(idx)
    draft = store.draft_for(r.cell_id)
    labeled = bool(r.cells[9].strip())
    # --packet shows no cq_id/category/variant chip (PREREG sec.12.3 DN-2).
    chips = "" if store.packet else (f'<span class="chip">category {html.escape(r.category)}</span>'
                                     f'<span class="chip">variant {r.variant}</span>')
    view_text = store.row_view_text(r)  # AH: the variant's view; --packet: the row's own view
    # Header counts run over served rows only, so deferred rows leave no visible gap.
    served = store.served()
    prev_idx, next_idx = store.nav(idx)
    return (PAGE % {
        "notice_html": (f'<div class="notice" role="status">{html.escape(notice)}</div>'
                        if notice else ""),
        "total_max": max(1, len(served)),
        "jump_btns": ((' <button onclick="jumpTo(D?[D.span]:[])">초안 span 위치</button>'
                       if draft is not None and not labeled else "")
                      + ' <button onclick="jumpTo(JUDGE)">judge 인용 위치</button>'),
        "empty_view": ('<div id="emptyview" role="alert">뷰 원문이 비어 있습니다 — 이 행은 근거 인용이 '
                       '불가능합니다. 감독자에게 알리고 A=0 + note로 기록하세요.</div>'
                       if not view_text.strip() else ""),
        "judge_frag_js": json.dumps(list(gv.split_fragments(r.judge_evidence_span)),
                                    ensure_ascii=False).replace("</", "<\\/"),
        "idx": idx, "pos": served.index(idx) + 1 if idx in served else idx,
        "total": len(served),
        "labeled": sum(1 for i in served if store.rows[i][9].strip()),
        "sess": store.session_saved(),
        "cell_js": json.dumps(r.cell_id).replace("</", "<\\/"), "chips": chips,
        "cq_text": html.escape(r.cq_text),
        "cq_ko_html": _cq_ko_html({} if store.packet else getattr(store, "cq_ko", {}).get(r.cells[1])),
        "judge_span": html.escape(r.judge_evidence_span) or "(judge span 없음)",
        "view": html.escape(view_text),
        # Draft prefill applies only to unlabeled rows (AH: the draft is the
        # starting point a human confirms or edits); a labeled row keeps
        # today's saved-value prefill so editing stays an explicit revision.
        "span_v": html.escape(draft.span if draft is not None and not labeled else r.cells[8]),
        "note_v": html.escape(draft.note if draft is not None and not labeled else r.cells[11]),
        "a_js": json.dumps(int(r.cells[9]) if labeled else (draft.a_int() if draft else None)),
        "r_js": json.dumps(int(r.cells[10]) if r.cells[10].strip()
                           else (draft.rater_int() if draft else None)),
        "draft_card": draft_card_html(draft) if draft is not None else "",
        "was_js": "true" if r.cells[9].strip() else "false",
        # Untouched-indicator snapshot (display only; not part of /save payload).
        "draft_js": json.dumps(
            {"a": draft.a_int(), "rater": draft.rater_int(), "span": draft.span}
            if draft is not None and not labeled else None, ensure_ascii=False
        ).replace("</", "<\\/"),
        "edit_hidden": "" if r.cells[9].strip() else ' style="display:none"',
        "prev": prev_idx, "next_nav": next_idx,
        "init_tab": tab, "help_html": help_html,
        "graph_css": gv.GRAPH_CSS, "graph_canvas": gv.graph_canvas_html(GRAPH_BANNER),
        "graph_js": gv.GRAPH_JS,
        "packet_panel": packet_panel_html(store) if store.packet else "",
        "packet_js": packet_js(store) if store.packet else "",
        "packet_inbar": packet_inbar_html(r) if store.packet else "",
        "packet_body_js": PACKET_BODY_JS if store.packet else "",
        "packet_t0_js": PACKET_T0_JS if store.packet else "",
        "packet_why_js": PACKET_WHY_JS if store.packet else "",
        "note_check_js": NOTE_CHECK_JS if store.note_required else "",
        "note_opt": "" if store.note_required else NOTE_OPTIONAL_PLACEHOLDER,
        "llm_inbar": LLM_INBAR_HTML if store.llm_assist_required else "",
        "llm_state_js": (LLM_STATE_JS % {"g7": int(G7_MIN_ELAPSED_S)}) if store.llm_assist_required else "",
        "llm_why_js": LLM_WHY_JS if store.llm_assist_required else "",
        "llm_body_js": LLM_BODY_JS if store.llm_assist_required else "",
        "llm_timer_html": '<span id="tmsg" role="status"></span>' if store.llm_assist_required else "",
    }).encode("utf-8")


# --------------------------------------------------------------------------
# serving safety: per-launch token, Host allow-list, POST rules, size and time limits
# --------------------------------------------------------------------------
class TokenAuth:
    """Per-launch access token. The launch token is printed once, inside a URL; opening that URL
    exchanges it (one time only) for an HttpOnly SameSite=Strict session cookie, and every route
    then demands that cookie. A page on another site cannot read or send it, and a peer that never
    saw the printed URL cannot get one."""

    def __init__(self, launch_token: str | None = None) -> None:
        self.launch_token = launch_token or secrets.token_urlsafe(32)
        self._cookies: set[str] = set()
        self._redeemed = False
        self._lock = threading.Lock()

    def redeem(self, candidate: str) -> str | None:
        """The new session cookie value for the right launch token, once; None otherwise."""
        with self._lock:
            if self._redeemed or not hmac.compare_digest(candidate.encode("utf-8"),
                                                         self.launch_token.encode("utf-8")):
                return None
            self._redeemed = True
            cookie = secrets.token_urlsafe(32)
            self._cookies.add(cookie)
            return cookie

    def valid_cookie(self, value: str) -> bool:
        probe = value.encode("utf-8")
        with self._lock:
            return any(hmac.compare_digest(probe, known.encode("utf-8")) for known in self._cookies)


def is_loopback_host(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def _bracket(host: str) -> str:
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


def allowed_hosts_for(bind_host: str, port: int, extra: "Iterable[str]" = ()) -> frozenset[str]:
    """The Host header values a request may carry: the loopback names, the bind address when it
    is a concrete one, and the --allow-host entries (names or addresses, no port), each with the
    server's port. Anything else -- an attacker's domain rebinding to this machine -- is refused."""
    names = {"127.0.0.1", "localhost", "[::1]"}
    if bind_host and bind_host not in ("0.0.0.0", "::"):
        names.add(_bracket(bind_host.lower()))
    for entry in extra:
        entry = entry.strip().lower()
        if entry:
            names.add(_bracket(entry))
    return frozenset(f"{name}:{port}" for name in names)


class Handler(BaseHTTPRequestHandler):
    # injected per server via make_server() subclassing; never unset in practice
    store: ClassVar[Store]
    graphs: ClassVar[GraphProvider | None] = None
    help_html: ClassVar[str] = ""
    auth: ClassVar[TokenAuth | None] = None
    allowed_hosts: ClassVar[frozenset[str]] = frozenset()
    timeout = HTTP_TIMEOUT_S  # a stalled or trickling client is dropped after this many seconds

    def log_message(self, format: str, *args: object) -> None:  # keep test output clean
        pass

    def _send(self, code: int, body: bytes, ctype: str,
              extra: dict[str, str] | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: dict[str, object]) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _deny(self, code: int, message: str) -> None:
        self.close_connection = True
        self._json(code, {"ok": False, "error": message})

    # ---- gate -------------------------------------------------------------
    def _host_header(self) -> str:
        return (self.headers.get("Host") or "").strip().lower()

    def _cookie_value(self) -> str:
        raw = self.headers.get("Cookie")
        if not raw:
            return ""
        jar = http.cookies.SimpleCookie()
        try:
            jar.load(raw)
        except http.cookies.CookieError:
            return ""
        morsel = jar.get(COOKIE_NAME)
        return morsel.value if morsel is not None else ""

    def _authorize(self, method: str, parts: "urllib.parse.SplitResult") -> bool:
        """Host allow-list, then the token cookie (every route, GET and POST alike). True = go on;
        False = a response (401/403, or the 302 that sets the cookie) has been sent."""
        if self._host_header() not in self.allowed_hosts:
            self._deny(403, "Host가 허용 목록에 없습니다")
            return False
        if self.auth is None or self.auth.valid_cookie(self._cookie_value()):
            return True
        token = urllib.parse.parse_qs(parts.query).get("token", [""])[0]
        cookie = self.auth.redeem(token) if (method == "GET" and parts.path == "/" and token) else None
        if cookie is None:
            self._deny(401, "접속 토큰이 필요합니다 — 시작할 때 출력된 URL(?token=…)로 여십시오 "
                            "(그 URL은 한 번만 쓸 수 있습니다)")
            return False
        rest = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
                if k != "token"]
        location = "/" + (("?" + urllib.parse.urlencode(rest)) if rest else "")
        self._send(302, b"", "text/plain; charset=utf-8", {
            "Location": location,
            "Set-Cookie": f"{COOKIE_NAME}={cookie}; HttpOnly; SameSite=Strict; Path=/; "
                          f"Max-Age={COOKIE_MAX_AGE_S}"})
        return False

    def _post_length(self) -> int | None:
        """The POST body length after the content-type, same-origin and size rules; None after the
        refusal has been sent."""
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._deny(415, "Content-Type은 application/json이어야 합니다")
            return None
        origin = (self.headers.get("Origin") or "").strip().lower()
        if origin != f"http://{self._host_header()}":
            self._deny(403, "Origin이 같은 출처가 아닙니다")
            return None
        if self.headers.get("Transfer-Encoding"):
            self._deny(411, "Content-Length가 필요합니다 (chunked 본문은 받지 않습니다)")
            return None
        raw = self.headers.get("Content-Length")
        if raw is None:
            self._deny(411, "Content-Length가 필요합니다")
            return None
        if not re.fullmatch(r"[0-9]{1,12}", raw.strip()):
            self._deny(400, "Content-Length가 올바르지 않습니다")
            return None
        length = int(raw.strip())
        if length > MAX_BODY_BYTES:
            self._deny(413, f"본문은 {MAX_BODY_BYTES}바이트 이하여야 합니다")
            return None
        return length

    # ---- routes -----------------------------------------------------------
    def _row_notice(self, query: str) -> str:
        raw = urllib.parse.parse_qs(query).get("row", [None])[0]
        if raw is None:
            return ""
        wanted = ascii_int(raw)
        shown = self.store.clamp_row(wanted)
        if wanted is None or wanted != shown:
            return f"요청한 행 {raw[:40]} 은(는) 유효하지 않아 {shown}행을 표시합니다."
        return ""

    def _row_param(self, query: str) -> int:
        qs = urllib.parse.parse_qs(query)
        return self.store.clamp_row(ascii_int(qs.get("row", [""])[0]))

    def do_GET(self) -> None:
        parts = urllib.parse.urlsplit(self.path)
        if not self._authorize("GET", parts):
            return
        if parts.path == "/":
            tab = urllib.parse.parse_qs(parts.query).get("tab", ["text"])[0]
            self._send(200, render_page(self.store, self._row_param(parts.query),
                                        tab if tab in VALID_TABS else "text",
                                        self.help_html, self._row_notice(parts.query)),
                       "text/html; charset=utf-8")
        elif parts.path == "/graph":
            idx = self._row_param(parts.query)
            graph, info = (self.graphs.graph_for(idx) if self.graphs is not None
                           else (None, NO_TTL_INFO))
            self._json(200, {"ok": True, "graph": graph, "info": info,
                             "overlay": self.store.row_overlay(idx)})
        elif parts.path == "/status":
            self._json(200, self.store.status())
        elif parts.path == "/export":
            self._send(200, self.store.out.read_bytes(), "text/csv; charset=utf-8",
                       {"Content-Disposition": f'attachment; filename="{self.store.out.name}"'})
        else:
            self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        parts = urllib.parse.urlsplit(self.path)
        if not self._authorize("POST", parts):
            return
        length = self._post_length()
        if length is None:
            return
        if parts.path == "/save":
            payload = self._read_json(length)
            if payload is None:
                return
            try:
                code, body = self.store.save(payload)
            except (SaveError, ValueError) as exc:
                self._json(400, {"ok": False, "error": str(exc)})
                return
            except OSError:  # disk full / permissions: nothing was stored, say so instead of dropping the socket
                self._json(500, {"ok": False, "error": WRITE_FAILED_MSG})
                return
            self._json(code, body)
        elif parts.path == "/ai_use" and self.store.packet:  # AH mode: unknown route, 404 as before
            payload = self._read_json(length)
            if payload is None:
                return
            try:
                self._json(200, self.store.record_ai_use(payload))
            except (SaveError, ValueError) as exc:
                self._json(400, {"ok": False, "error": str(exc)})
            except OSError:
                self._json(500, {"ok": False, "error": WRITE_FAILED_MSG})
        else:
            self._json(404, {"ok": False, "error": "not found"})

    def _read_json(self, length: int) -> dict[str, object] | None:
        try:
            raw = self.rfile.read(length) if length else b""
        except OSError:  # includes the socket timeout: the client stalled mid-body
            self.close_connection = True
            return None
        try:
            if len(raw) != length:
                raise ValueError("본문이 Content-Length보다 짧습니다")
            payload = json.loads(raw or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("JSON object 필요")
            return payload
        except ValueError as exc:
            self._json(400, {"ok": False, "error": f"잘못된 JSON: {exc}"})
            return None


def make_server(store: Store, addr: tuple[str, int], ttl_dir: Path | None = None, *,
                auth: TokenAuth | None = None, extra_hosts: "Iterable[str]" = (),
                timeout: float = HTTP_TIMEOUT_S) -> ThreadingHTTPServer:
    """``auth`` None serves without a token (loopback development and the tests); the Host
    allow-list, the POST rules and the size/time limits always apply."""
    handler = type("BoundHandler", (Handler,), {
        "store": store,
        "graphs": GraphProvider(store, ttl_dir),
        "help_html": build_help_html(packet=store.packet, require_note=store.require_note),
        "auth": auth,
        "timeout": timeout})
    server = ThreadingHTTPServer(addr, handler)
    handler.allowed_hosts = allowed_hosts_for(addr[0], server.server_address[1], extra_hosts)
    return server


def acquire_out_lock(out: Path):
    """Single-writer lock: an exclusive non-blocking flock on <out>.lock for the life of the
    process. A second label_assist on the same --out would overwrite the first one's saves. Returns
    the open lock file (keep it referenced), or None where flock does not exist."""
    if fcntl is None:  # pragma: no cover
        return None
    lock_path = Path(str(out) + ".lock")
    fh = open(lock_path, "a+")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fh.close()
        raise OutLocked(f"다른 label_assist 프로세스가 이미 {out} 에 쓰고 있습니다 ({lock_path})") from None
    fh.seek(0)
    fh.truncate()
    fh.write(f"{os.getpid()}\n")
    fh.flush()
    return fh


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Human-labeling assistant (presents/captures/audits only)")
    p.add_argument("--sheet", required=True, type=Path, help="blank-or-working sealed sheet")
    p.add_argument("--views", required=True, type=Path, help="views dir with SHA256SUMS.txt")
    p.add_argument("--out", type=Path, default=Path("<labels>/primary_working.csv"),
                   help="working CSV (must be OUTSIDE the repo)")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--host", default="127.0.0.1",
                   help="bind 주소. 루프백이 아니면(예: 다른 기기에서 접속하려는 0.0.0.0) 토큰 인증이 필수이고 "
                        "접속에 쓸 이름/주소를 --allow-host로 허용해야 한다 (게이트는 서버측 유지)")
    p.add_argument("--no-token", action="store_true",
                   help="접속 토큰 인증을 끈다 (루프백 --host에서만 허용). 기본은 켜짐: 시작할 때 "
                        "한 번만 쓸 수 있는 URL(?token=…)이 출력되고 그것이 HttpOnly 쿠키로 바뀐다")
    p.add_argument("--allow-host", action="append", default=[], metavar="HOST",
                   help="Host 헤더 허용 목록에 더할 이름/주소 (포트 제외, 여러 번 가능). 루프백 이름과 "
                        "구체적인 --host 주소는 자동 허용 — 그 밖의 Host는 403 (DNS rebinding 방어)")
    p.add_argument("--ttl-dir", type=Path, default=None,
                   help="variants root holding <V>/graph_<V>.ttl; default: …/../../variants "
                        "resolved from --sheet; without a resolvable dir the graph tab shows "
                        "'TTL 없음' and everything else keeps working")
    p.add_argument("--defer-controls", action="store_true",
                   help="ablated/preserved control 행을 큐에서 보류(표시·저장 안 함) — "
                        "judge가 본 자료와 시트 자료가 다른 문제가 고쳐질 때까지")
    p.add_argument("--cq-ko", type=Path, default=None,
                   help="CQ 한국어 번역 JSON ({cq_id: [번역]}). 표시 전용, 시트·감사 무관")
    p.add_argument("--draft", type=Path, default=None,
                   help="AI 초안 CSV (7열 계약, cell_id 키). absent = 오늘의 동작 그대로; "
                        "present = 행별 초안 카드+프리필, audit에 draft 필드")
    p.add_argument("--packet", action="store_true",
                   help="packet 모드 (PREREG §12.3 washout / §12.4 2차 annotator): 행마다 자기 뷰 파일"
                        "(rendered_view_path = --views 아래 상대 이름, --sums로 검증)을 서빙하고, "
                        "AH 초안·번역·cq_id/category/variant 칩·cell_id를 화면에 내지 않으며, rater_L1을 "
                        "필수로 받고, 체류 시간을 클라이언트 performance.now()로 재서 dwell_ms에 기록하며, "
                        "AI 사용 자기보고(앉은 자리 끝, 건너뛰기 가능)와 행별 'AI 사용' 체크를 남긴다. "
                        "--draft/--cq-ko/--defer-controls와 함께 쓸 수 없다")
    p.add_argument("--require-note", action="store_true",
                   help="--packet: 모든 저장에 note 필수 (2차 annotator, PREREG §13.1 8 · DN-9: 네 열 모두). "
                        "없으면 --packet의 note는 선택 (washout). --packet 없이는 쓸 수 없다 "
                        "(AH 화면은 note가 늘 필수)")
    p.add_argument("--domain", choices=sorted(DOMAIN_CONFIG), default=DOMAIN_BRICK,
                   help="라벨링 도메인 (기본 brick = 잠긴 Brick 동작 그대로). iof: 셀마다 외부 LLM 상담 여부"
                        "(none/consulted + 도구명)를 필수로 받아 audit에 기록하고, 셀당 20초 미만 저장은 "
                        "경고만 하고 기록한다 (PREREG addendum 15 §15.6)")
    p.add_argument("--sums", type=Path, default=None,
                   help="--packet: 뷰 sha256 목록 파일 (기본 --views/SHA256SUMS.txt). washout packet은 "
                        "뷰와 목록을 서버 쪽에만 두고 rater에게는 시트만 준다")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        out = Path(args.out).expanduser().resolve()
        check_out_path(out)
    except OutInsideRepo as exc:
        print(f"[label_assist] 시작 거부: {exc}", file=sys.stderr)
        return 1
    if args.no_token and not is_loopback_host(args.host):
        print(f"[label_assist] 시작 거부: --host {args.host} 는 루프백이 아니므로 토큰 인증을 끌 수 없습니다 "
              "(--no-token 은 127.0.0.1/::1/localhost 에서만)", file=sys.stderr)
        return 1
    if args.sums is not None and not args.packet:
        print("[label_assist] 시작 거부: --sums 는 --packet 과 함께만 씁니다", file=sys.stderr)
        return 1
    if args.require_note and not args.packet:
        print("[label_assist] 시작 거부: --require-note 는 --packet 과 함께만 씁니다 "
              "(AH 화면은 note가 늘 필수)", file=sys.stderr)
        return 1
    if not args.sheet.is_file():
        print(f"[label_assist] --sheet 없음: {args.sheet}", file=sys.stderr)
        return 1
    if args.packet:
        clash = [flag for flag, given in (("--draft", args.draft is not None),
                                          ("--cq-ko", args.cq_ko is not None),
                                          ("--defer-controls", args.defer_controls)) if given]
        if clash:
            print(f"[label_assist] 시작 거부: --packet은 {', '.join(clash)}와 함께 쓸 수 없습니다 "
                  "(packet 화면에는 AH 초안·번역·보류 행이 없다)", file=sys.stderr)
            return 1
    try:
        if args.packet:
            refs = sheet_view_refs(args.sheet)
            if out.exists():  # a resumed working CSV must name the same views
                refs |= sheet_view_refs(out)
            views = verify_packet_views(args.views, refs, args.sums)
        else:
            views = verify_views(args.views)
    except (ViewMismatch, SafetyError) as exc:
        print(f"[label_assist] 뷰 검증 실패(시작 거부): {exc}", file=sys.stderr)
        return 1
    try:
        # --packet: a sheet without variants (washout) has no graph; only an explicit --ttl-dir turns it on
        ttl_dir = (None if args.packet and args.ttl_dir is None
                   else gv.resolve_ttl_dir(args.sheet, args.ttl_dir))
    except gv.TtlDirError as exc:
        print(f"[label_assist] 시작 거부: {exc}", file=sys.stderr)
        return 1
    drafts: dict[str, DraftEntry] | None = None
    draft_name: str | None = None
    if args.draft is not None:
        try:
            drafts = load_drafts(Path(args.draft).expanduser())
            draft_name = Path(args.draft).name
        except DraftError as exc:
            print(f"[label_assist] 시작 거부 (--draft): {exc}", file=sys.stderr)
            return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_fh = acquire_out_lock(out)  # one writer per --out; held until this process exits
    except OutLocked as exc:
        print(f"[label_assist] 시작 거부: {exc}", file=sys.stderr)
        return 1
    try:
        store = Store(args.sheet, out, views, drafts=drafts, draft_name=draft_name,
                      defer_prefixes=CONTROL_PREFIXES if args.defer_controls else (),
                      packet=args.packet, require_note=args.require_note, domain=args.domain)
    except SafetyError as exc:
        if not args.packet:
            raise  # the AH pass keeps its former failure behavior
        print(f"[label_assist] 시작 거부: {exc}", file=sys.stderr)
        return 1
    store.cq_ko = {}
    if args.cq_ko is not None:
        try:
            store.cq_ko = {k: v for k, v in json.loads(Path(args.cq_ko).expanduser().read_text(
                encoding="utf-8")).items() if not k.startswith("_")}
        except (OSError, ValueError) as exc:
            print(f"[label_assist] 시작 거부 (--cq-ko): {exc}", file=sys.stderr)
            return 1
    atexit.register(store.log_session_end)
    auth = None if args.no_token else TokenAuth()
    server = make_server(store, (args.host, args.port), ttl_dir, auth=auth,
                         extra_hosts=args.allow_host)
    try:
        # a closed terminal (SIGHUP) ends the session as cleanly as SIGTERM: SESSION end, AI_USE line.
        # A SIGHUP that the parent already set to "ignore" (nohup) keeps that meaning: the server
        # then outlives the terminal, as the operator asked.
        handled = [signal.SIGTERM]
        if signal.getsignal(signal.SIGHUP) != signal.SIG_IGN:
            handled.append(signal.SIGHUP)
        for sig in handled:
            signal.signal(sig, lambda *_s: sys.exit(0))
    except (ValueError, AttributeError, RuntimeError):
        pass  # not main thread / not POSIX: atexit still covers normal exits
    shown_host = (args.allow_host[0] if args.allow_host
                  else "127.0.0.1" if args.host in ("", "0.0.0.0", "::") else args.host)
    url = (f"http://{_bracket(shown_host)}:{server.server_address[1]}/"
           + (f"?token={auth.launch_token}" if auth is not None else ""))
    print(f"[label_assist] {url}  (out={out}, "
          f"session={store.session_id}, graphs={'lazy @ '+str(ttl_dir) if ttl_dir else 'TTL 없음'}"
          f"{', mode=packet' if args.packet else ''}{', require_note=on' if args.require_note else ''}{f', domain={args.domain}' if args.domain != DOMAIN_BRICK else ''}"
          f"{', token=off' if auth is None else ''})", flush=True)
    if auth is not None:
        print("[label_assist] 위 URL은 한 번만 쓸 수 있습니다: 열면 토큰이 HttpOnly 쿠키로 바뀌고 주소창에서 "
              "사라집니다. 다른 기기에서는 이 서버를 다시 시작해 새 URL을 받으십시오.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        del lock_fh  # (the lock is also released when the process exits)
    return 0


if __name__ == "__main__":
    sys.exit(main())
