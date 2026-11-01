"""Retrieval view of the labeler (addendum 32, PLAN.md 32.4).  AI-generated; review and test before use.

A pure function of (full rendering text, bank row grounding + question, located judge span strings): no model, no randomness.
Parameters are fixed in PLAN.md 32.4: N = 600, LINE_CAP = 4000, CAP_CHARS = 100000, MIN_CHARS = 2000, FALLBACK_CAP = 20000.
Never reads the bank's expected_answer (the term test below takes it from the caller, for coverage reporting only).
"""
from __future__ import annotations

import bisect
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parent
ACCESS = HARNESS.parent
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(HARNESS / "review6_natural"))
import grounding_check as GC  # noqa: E402
import run_holdout as rh  # noqa: E402

N = 600
LINE_CAP = 4000
CAP_CHARS = 100_000
MIN_CHARS = 2_000
FALLBACK_CAP = 20_000
MARKER = "[…]\n"
MIN_PIECE = 20
ANSWER_FRACTION = 0.5

VIEW_FILES = {v: HARNESS / "variants" / v / "rendered_view.txt" for v in "ABCDEF"}
_REND: dict[str, str] = {}
_IDX: dict[str, dict] = {}


def collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def rendering(variant: str) -> str:
    if variant not in _REND:
        _REND[variant] = VIEW_FILES[variant].read_text(encoding="utf-8")
    return _REND[variant]


class Index:
    """Per-rendering line table and the whitespace-normalised text with a line map (for span location)."""

    def __init__(self, text: str):
        self.lines = text.splitlines(keepends=True)
        self.start = []
        o = 0
        for ln in self.lines:
            self.start.append(o)
            o += len(ln)
        self.end = [s + len(ln) for s, ln in zip(self.start, self.lines)]
        parts, self.noff, self.nline = [], [], []
        pos = 0
        for i, ln in enumerate(self.lines):
            c = collapse(ln)
            if not c:
                continue
            if parts:
                pos += 1                              # the joining space
            self.noff.append(pos)
            self.nline.append(i)
            parts.append(c)
            pos += len(c)
        self.norm = " ".join(parts)

    def span_lines(self, span: str) -> tuple[list[int], int, int]:
        """Rendering line indices covered by the first occurrence of the span (or of its pieces) -> (lines, found, total)."""
        ns = collapse(span)
        if not ns:
            return [], 0, 0
        idx = self.norm.find(ns)
        if idx >= 0:
            return self._cover(idx, idx + len(ns)), 1, 1
        pieces = [collapse(p) for p in re.split(r"\.\.\.|…", span)]
        pieces = [p for p in pieces if len(p) >= MIN_PIECE]
        found, lines = 0, set()
        for p in pieces:
            k = self.norm.find(p)
            if k >= 0:
                found += 1
                lines.update(self._cover(k, k + len(p)))
        return sorted(lines), found, len(pieces)

    def _cover(self, a: int, b: int) -> list[int]:
        j = bisect.bisect_right(self.noff, a) - 1
        out = []
        while j < len(self.noff) and self.noff[j] < b:
            if j >= 0:
                out.append(self.nline[j])
            j += 1
        return out


def index_for(variant: str) -> Index:
    if variant not in _IDX:
        _IDX[variant] = Index(rendering(variant))
    return _IDX[variant]


def _cut(line: str, center: int) -> str:
    if len(line) <= LINE_CAP:
        return line
    s = max(0, min(center - LINE_CAP // 2, len(line) - LINE_CAP))
    t = line[s:s + LINE_CAP]
    return t if t.endswith("\n") else t + "\n"


def _center(line: str, probes: list[str]) -> int:
    low = line.lower()
    for p in probes:
        k = low.find(p.lower())
        if k >= 0:
            return k
    return 0


def _order_window(seed: int, idx: Index) -> list[int]:
    """Seed line first, then distance 1 before, 1 after, 2 before, ... inside the +-N character window."""
    lo_c, hi_c = idx.start[seed] - N, idx.end[seed] + N
    lo = seed
    while lo - 1 >= 0 and idx.end[lo - 1] > lo_c:
        lo -= 1
    hi = seed
    while hi + 1 < len(idx.lines) and idx.start[hi + 1] < hi_c:
        hi += 1
    out = [seed]
    for d in range(1, max(seed - lo, hi - seed) + 1):
        if seed - d >= lo:
            out.append(seed - d)
        if seed + d <= hi:
            out.append(seed + d)
    return out


def build_view(variant: str, grounding: str, question: str, spans: list[str] | None = None, *,
               rendering_text: str | None = None) -> dict:
    """Retrieval view of PLAN.md 32.4 -> {"text", stats...}.  ``rendering_text`` overrides the variant file (ablated controls)."""
    idx = Index(rendering_text) if rendering_text is not None else index_for(variant)
    text_all = rendering_text if rendering_text is not None else rendering(variant)
    info = rh._grounding_match_info(text_all, {"grounding": grounding})
    anchors = info["anchors"]
    match_lines = [n - 1 for n in info["matching_line_numbers"]]          # 0-based
    locals_ = [a.split(":", 1)[1] if ":" in a else a for a in anchors]
    locals_ = [a for a in locals_ if a and a not in ("sh", "path")]
    n_distinct = {}
    for i in match_lines:
        n_distinct[i] = sum(1 for a in anchors if rh._anchor_present(idx.lines[i], a))
    # B. span lines (union over the given span strings), probes for the line cut
    span_lines: list[int] = []
    probes: dict[int, list[str]] = {}
    found = total = 0
    for sp in (spans or []):
        ls, f, t = idx.span_lines(sp)
        found += f
        total += t
        for i in ls:
            if i not in span_lines:
                span_lines.append(i)
            probes.setdefault(i, []).append(collapse(sp)[:30])
    span_lines.sort()
    kept: dict[int, str] = {}
    total_chars = 0
    state = {"full": False}

    def add_seed(seed: int, stop_at: int | None = None):
        nonlocal total_chars
        center_probes = probes.get(seed, []) + locals_
        for i in _order_window(seed, idx):
            if i in kept:
                continue
            t = _cut(idx.lines[i], _center(idx.lines[i], center_probes if i == seed else []))
            if total_chars + len(t) > CAP_CHARS:
                if i == seed:
                    state["full"] = True
                break
            kept[i] = t
            total_chars += len(t)
            if stop_at is not None and total_chars >= stop_at:
                return True
        return False

    for s in span_lines:                                   # P0
        add_seed(s)
    for s in sorted(match_lines, key=lambda i: (-n_distinct[i], i)):   # P1
        if total_chars >= CAP_CHARS:
            break
        add_seed(s)
    fallback = False
    if total_chars < MIN_CHARS:                            # D
        fallback = True
        terms = GC.content_terms(question, set())
        res = [re.compile(r"(?<![a-z0-9])" + re.escape(t) + r"(?:s|es)?(?![a-z0-9])") for t in terms]
        cand = []
        for i, ln in enumerate(idx.lines):
            low = ln.lower()
            k = sum(1 for r in res if r.search(low))
            if k:
                cand.append((-k, i))
        cand.sort()
        for _, s in cand:
            if total_chars >= FALLBACK_CAP:
                break
            add_seed(s, stop_at=FALLBACK_CAP)
    # E. output
    out, prev = [], None
    for i in sorted(kept):
        if prev is not None and i != prev + 1:
            out.append(MARKER)
        out.append(kept[i])
        prev = i
    text = "".join(out)
    return {"text": text, "n_chars": len(text), "n_lines": len(kept), "n_anchor_lines": len(match_lines),
            "n_anchor_lines_included": sum(1 for i in match_lines if i in kept),
            "n_span_lines": len(span_lines), "n_span_lines_included": sum(1 for i in span_lines if i in kept),
            "span_given": len(spans or []), "span_pieces_found": found, "span_pieces_total": total,
            "fallback_used": fallback, "cap_reached": total_chars >= CAP_CHARS or state["full"],
            "can_ablate": bool(info["can_ablate"])}


# ---------------------------------------------------------------- term test (addendum 31 rule; verbatim copy of Crit)
def norm_lc(s) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


class Crit:
    """Anchors and answer terms of one bank row; the term test of one text unit (adjudicate.Crit, copied)."""

    def __init__(self, row: dict):
        self.cq_id = row["cq_id"]
        self.anchors = GC.local_anchors(row["grounding"])
        exclude = {w for a in self.anchors for f in GC.forms_of(a) for w in f.split(" ")}
        self.terms = GC.content_terms(row["expected_answer"], exclude)
        self.anchor_res = [[GC.form_regex(f) for f in GC.forms_of(a)] for a in self.anchors]
        self.term_res = [re.compile(r"(?<![a-z0-9])" + re.escape(t) + r"(?:s|es)?(?![a-z0-9])") for t in self.terms]

    def unit(self, t_lc: str) -> tuple[bool, float]:
        a = all(any(r.search(t_lc) for r in rs) for rs in self.anchor_res)
        if not a or not self.term_res:
            return a, 0.0
        return a, sum(1 for r in self.term_res if r.search(t_lc)) / len(self.term_res)

    def passes(self, t_lc: str) -> tuple[bool, float]:
        a, f = self.unit(t_lc)
        return bool(a and f >= ANSWER_FRACTION), (f if a else 0.0)

    def best_line(self, lines_lc: list[str]) -> tuple[bool, float]:
        best, ok = 0.0, False
        for ln in lines_lc:
            p, f = self.passes(ln)
            ok = ok or p
            best = max(best, f)
        return ok, best


def holds_terms(view_text: str, crit: Crit) -> tuple[bool, float]:
    """The view holds the expected-answer terms iff one view line passes the term test (marker lines ignored)."""
    lines = [norm_lc(x) for x in view_text.splitlines() if x.strip() and x.strip() != "[…]"]
    return crit.best_line(lines)
