#!/usr/bin/env python3
"""Addendum 27 step 2b: clean the fetched documentation and chunk it into the pipeline's input shape.

AI-generated; review before reuse.  Deterministic, offline, no model.  Rules are the ones frozen in
PLAN.md 27.3 (cleaning + chunking); the bank is never read here.

Input : corpus/raw/** and corpus/fetch_log.json (from fetch_sources.py)
Output: corpus/cleaned/<group>/<path>.txt   (cleaned prose, headings kept as '#' lines)
        corpus/natural_corpus.json           (nested chunking_result shape that `chunktograph extract` reads)
        corpus_stats.json, SOURCES.md
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics
import unicodedata
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "corpus" / "raw"
CLEAN = HERE / "corpus" / "cleaned"

ADMONITIONS = {"note", "warning", "tip", "important", "seealso", "attention", "caution", "hint", "danger"}
MIN_PROSE_CHARS = 200
MERGE_UNDER = 120
SPLIT_OVER = 1000
DROP_UNDER = 40


# ----------------------------------------------------------------------------- markdown / myst

FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})\s*(.*?)\s*$")


def _strip_fences(lines: list[str], stats: dict) -> list[str]:
    """Remove fenced code blocks; keep MyST admonition bodies (recursively)."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        m = FENCE_RE.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        marker, info = m.group(2), m.group(3)
        j = i + 1
        while j < len(lines):
            mc = FENCE_RE.match(lines[j])
            if mc and mc.group(2)[0] == marker[0] and len(mc.group(2)) >= len(marker) and not mc.group(3):
                break
            j += 1
        body = lines[i + 1:j]
        dm = re.match(r"\{([\w:-]+)\}", info)
        if dm and dm.group(1).lower() in ADMONITIONS:
            inner = [ln for ln in body if not re.match(r"^\s*:[\w-]+:", ln)]
            out.extend(_strip_fences(inner, stats))
        else:
            stats["code_blocks_removed"] += 1
            stats["code_chars_removed"] += sum(len(x) + 1 for x in body)
        i = j + 1
    return out


def _inline_md(text: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[\[[^\]]*\]\]", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\[[^\]]*\]", r"\1", text)
    text = re.sub(r"\{[\w:-]+\}`([^`]*)`", r"\1", text)
    text = re.sub(r"<[^>\n]+>", " ", text)
    text = re.sub(r"https?://[^\s)>\]]+", " ", text)
    text = re.sub(r"`([^`\n]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_\n]+)__", r"\1", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"\1", text)
    return text


def clean_markdown(raw: str, stats: dict) -> str:
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    if raw.startswith("---\n"):
        end = raw.find("\n---", 4)
        if end != -1:
            raw = raw[end + 4:]
    lines = _strip_fences(raw.split("\n"), stats)
    text = "\n".join(lines)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    lines = text.split("\n")
    out: list[str] = []
    for idx, ln in enumerate(lines):
        s = ln.rstrip()
        # setext headings
        if re.fullmatch(r"=+", s.strip()) and out and out[-1].strip() and not out[-1].lstrip().startswith("#"):
            out[-1] = "# " + out[-1].strip()
            continue
        if re.fullmatch(r"-{3,}", s.strip()):
            prev = out[-1].strip() if out else ""
            if prev and not prev.startswith(("#", "-", "*", "|")) and idx > 0 and lines[idx - 1].strip():
                out[-1] = "## " + prev
            continue  # horizontal rule dropped
        if re.match(r"^\s*\[[^\]]+\]:\s+\S+", s):
            continue  # link reference definition
        if "|" in s and re.fullmatch(r"[\s:|+=-]+", s) and "-" in s:
            continue  # table separator row (with or without outer pipes)
        # tables
        if s.lstrip().startswith("|"):
            if re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", s):
                continue
            cells = [c.strip() for c in s.strip().strip("|").split("|")]
            s = " | ".join(c for c in cells if c)
        out.append(s)
    text = "\n".join(out)
    text = _inline_md(text)
    return _tidy(_drop_code_paragraphs(text, stats))


# ----------------------------------------------------------------------------- rst

RST_UNDERLINE = re.compile(r"^([=\-~^\"'`#*+._:])\1{2,}\s*$")


def clean_rst(raw: str, stats: dict) -> str:
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.split("\n")
    out: list[str] = []
    levels: dict[str, int] = {}
    i = 0
    while i < len(lines):
        ln = lines[i]
        # directive / comment / hyperlink target
        m = re.match(r"^(\s*)\.\.(?:\s+([\w:-]+)::\s*(.*))?(?:\s+.*)?$", ln)
        if m and (ln.strip().startswith(".. ") or ln.strip() == ".."):
            indent = len(m.group(1))
            name = (m.group(2) or "").lower()
            j = i + 1
            body: list[str] = []
            while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > indent):
                body.append(lines[j])
                j += 1
            if name in ADMONITIONS:
                kept = [b.strip() for b in body if b.strip() and not b.strip().startswith(":")]
                if m.group(3):
                    kept.insert(0, m.group(3).strip())
                out.extend(kept + [""])
            else:
                stats["code_blocks_removed"] += 1 if name in {"code-block", "code", "sourcecode", "literalinclude", "ipython"} else 0
                stats["code_chars_removed"] += sum(len(b) + 1 for b in body) if name in {"code-block", "code", "sourcecode"} else 0
            i = j
            continue
        # headings: text line followed by underline
        if i + 1 < len(lines) and RST_UNDERLINE.match(lines[i + 1]) and ln.strip() and not RST_UNDERLINE.match(ln) \
                and len(lines[i + 1].strip()) >= min(len(ln.strip()), 3):
            ch = lines[i + 1].strip()[0]
            lvl = levels.setdefault(ch, len(levels) + 1)
            out.append("#" * min(lvl, 4) + " " + ln.strip())
            i += 2
            continue
        if RST_UNDERLINE.match(ln):  # overline or transition
            i += 1
            continue
        if re.match(r"^\s*\+[-=+]+\+\s*$", ln) or re.match(r"^\s*\|.*\|\s*$", ln):
            stats["code_chars_removed"] += len(ln) + 1  # grid-table example data
            i += 1
            continue
        # literal block after a paragraph ending with '::' (or a standalone '::')
        if ln.rstrip().endswith("::"):
            head = ln.rstrip()[:-2].rstrip()
            if head:
                out.append(head + ":")
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            block: list[str] = []
            while j < len(lines) and (not lines[j].strip() or lines[j].startswith((" ", "\t"))):
                block.append(lines[j])
                j += 1
            stats["code_blocks_removed"] += 1
            stats["code_chars_removed"] += sum(len(b) + 1 for b in block)
            i = j
            continue
        out.append(ln.rstrip())
        i += 1
    text = "\n".join(out)
    text = re.sub(r":[\w:-]+:`~?([^`<]*?)(?:\s*<[^>]*>)?`", r"\1", text)
    text = re.sub(r"`([^`<]+?)\s*<[^>]*>`_{1,2}", r"\1", text)
    text = re.sub(r"``([^`]*)``", r"\1", text)
    text = re.sub(r"`([^`]*)`_{0,2}", r"\1", text)
    text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)
    text = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"\1", text)
    text = re.sub(r"https?://[^\s)>\]]+", " ", text)
    return _tidy(_drop_code_paragraphs(text, stats))


# ----------------------------------------------------------------------------- pdf text

def clean_paper(raw: str, stats: dict) -> str:
    text = raw.replace("\r", "").replace("\x0c", "\n\n")
    lines = text.split("\n")
    # cut the bibliography: last 'References' heading line in the second half
    cut = None
    for idx in range(len(lines) // 2, len(lines)):
        if re.fullmatch(r"\s*(references|reference list|bibliography)\s*", lines[idx], flags=re.I):
            cut = idx
    if cut is not None:
        stats["references_chars_removed"] = sum(len(x) + 1 for x in lines[cut:])
        lines = lines[:cut]
    kept: list[str] = []
    for ln in lines:
        s = ln.strip()
        if not s:
            kept.append("")
            continue
        if re.fullmatch(r"[\d\s.,-]+", s) or len(s) <= 2:
            continue  # page numbers, stray glyphs
        if re.search(r"@[\w.-]+\.\w+", s):
            continue  # e-mail lines
        if re.fullmatch(r"(frontiers in|elsevier|softwarex|downloaded from|https?://\S+)", s, flags=re.I):
            continue
        kept.append(s)
    # re-flow: blocks separated by blank lines, de-hyphenate
    blocks: list[str] = []
    cur: list[str] = []
    for s in kept + [""]:
        if s:
            cur.append(s)
        elif cur:
            joined = ""
            for part in cur:
                if joined.endswith("-") and joined[-2:-1].islower() and part[:1].islower():
                    joined = joined[:-1] + part
                else:
                    joined = (joined + " " + part).strip()
            blocks.append(joined)
            cur = []
    out: list[str] = []
    for b in blocks:
        if len(b) <= 90 and re.match(r"^(\d+(\.\d+)*\.?\s+[A-Z]|[A-Z][A-Z \-]{4,}$|Abstract$)", b):
            out.append("## " + b)
        else:
            out.append(b)
    text = "\n\n".join(out)
    text = re.sub(r"https?://[^\s)>\]]+", " ", text)
    return _tidy(_drop_code_paragraphs(text, stats))


CODE_LINE = re.compile(
    r"^\s*(@prefix\b|@base\b|PREFIX\s+\w*:|SELECT\s+[?*]|WHERE\s*\{|CONSTRUCT\s|ASK\s*\{|>>>\s|import\s+\w|from\s+\S+\s+import\s)")
TTL_TRIPLE = re.compile(r"^\s*[\w.-]*:[\w.%-]+\s+(a|[\w.-]*:[\w.-]+)\s+\S.*[;.,]\s*$")


def _drop_code_paragraphs(text: str, stats: dict) -> str:
    """Remove paragraphs that are code dumps (TTL, SPARQL, Python) that survived the fence/literal-block rules."""
    paras = re.split(r"\n\s*\n", text)
    kept = []
    for para in paras:
        lines = [ln for ln in para.split("\n") if ln.strip()]
        code_lines = sum(1 for ln in lines if CODE_LINE.match(ln) or "@prefix " in ln)
        triple_lines = sum(1 for ln in lines if TTL_TRIPLE.match(ln))
        if code_lines >= 1 or triple_lines >= 2 or (len(lines) == 1 and TTL_TRIPLE.match(lines[0]) and len(lines[0]) < 200):
            stats["code_blocks_removed"] += 1
            stats["code_chars_removed"] += len(para)
            continue
        kept.append(para)
    return "\n\n".join(kept)


def _tidy(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


# ----------------------------------------------------------------------------- chunking

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
BULLET = re.compile(r"^\s*([-*+]|\d+[.)])\s+")


def _blocks(section_lines: list[str]) -> list[str]:
    """Paragraph units; a list block stays attached to the paragraph that introduces it."""
    units: list[list[str]] = []
    kinds: list[str] = []
    cur: list[str] = []
    cur_kind = ""

    def flush():
        nonlocal cur, cur_kind
        if cur:
            units.append(cur)
            kinds.append(cur_kind)
        cur, cur_kind = [], ""

    for ln in section_lines:
        if not ln.strip():
            flush()
            continue
        kind = "list" if BULLET.match(ln) else ("cont" if ln.startswith((" ", "\t")) and cur_kind == "list" else "para")
        if kind == "cont":
            cur.append(ln.strip())
            continue
        if cur and kind != cur_kind and not (cur_kind == "list" and kind == "list"):
            if cur_kind == "para" and kind == "list":
                cur_kind = "list"  # paragraph + its list form one unit
                cur.append(ln.strip())
                continue
            flush()
        cur_kind = cur_kind or kind
        cur.append(ln.strip())
    flush()
    # merge: a list-only unit directly after a paragraph that ends with ':' (blank line between them)
    merged: list[str] = []
    for u, k in zip(units, kinds):
        text = "\n".join(u)
        if merged and k == "list" and all(BULLET.match(x) for x in u[:1]) and merged[-1].rstrip().endswith(":"):
            merged[-1] = merged[-1] + "\n" + text
        else:
            merged.append(text)
    return merged


def _split_long(unit: str) -> list[str]:
    if len(unit) <= SPLIT_OVER:
        return [unit]
    atoms: list[str] = []
    for line in unit.split("\n"):
        atoms.extend(SENT_SPLIT.split(line) if len(line) > SPLIT_OVER else [line])
    pieces: list[str] = []
    cur = ""
    for a in atoms:
        if cur and len(cur) + 1 + len(a) > SPLIT_OVER:
            pieces.append(cur)
            cur = a
        else:
            cur = (cur + "\n" + a) if cur else a
    if cur:
        pieces.append(cur)
    return pieces


def chunk_section(section_lines: list[str]) -> list[str]:
    units = _blocks(section_lines)
    merged: list[str] = []
    carry = ""
    for u in units:
        u = (carry + "\n" + u).strip() if carry else u
        carry = ""
        if len(u) < MERGE_UNDER:
            carry = u
            continue
        merged.append(u)
    if carry:
        if merged:
            merged[-1] = merged[-1] + "\n" + carry
        else:
            merged.append(carry)
    out: list[str] = []
    for u in merged:
        out.extend(_split_long(u))
    return [c.strip() for c in out if len(c.strip()) >= DROP_UNDER]


def to_sections(cleaned: str, fallback_title: str) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    title, buf = fallback_title, []
    for ln in cleaned.split("\n"):
        m = re.match(r"^(#{1,6})\s+(.*\S)\s*$", ln)
        if m:
            if any(x.strip() for x in buf):
                sections.append((title, buf))
            title, buf = m.group(2).strip(), []
        else:
            buf.append(ln)
    if any(x.strip() for x in buf):
        sections.append((title, buf))
    return sections


def file_title(cleaned: str, path: str) -> str:
    for ln in cleaned.split("\n"):
        m = re.match(r"^#{1,2}\s+(.*\S)\s*$", ln)
        if m:
            return m.group(1).strip()
    return Path(path).stem.replace("-", " ").replace("_", " ")


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


GROUP_LABEL = {
    "brick-docs": "Brick developer documentation (docs.brickschema.org)",
    "brick-website": "Brick website (brickschema.org)",
    "py-brickschema": "py-brickschema documentation",
    "brick-v1.4.4": "Brick repository v1.4.4 documents",
    "paper-fierro2020": "Papers",
    "paper-brickllm2025": "Papers",
}


def main() -> int:
    log = json.loads((HERE / "corpus" / "fetch_log.json").read_text(encoding="utf-8"))
    licenses = log["licenses"]
    rows: list[dict] = []
    top_chunks: list[dict] = []
    all_lengths: list[int] = []
    toc: list[dict] = []
    dropped: list[dict] = []
    group_totals: dict[str, dict] = defaultdict(lambda: {"files": 0, "cleaned_chars": 0, "atomic_chunks": 0})
    n_atomic = 0
    ordered = sorted(log["files"], key=lambda r: (r["group"], r["path"]))
    for rec in ordered:
        group, rpath = rec["group"], rec["path"]
        stats = {"code_blocks_removed": 0, "code_chars_removed": 0}
        if rec["kind"] == "paper-pdf":
            raw = (RAW / group / "paper.txt").read_text(encoding="utf-8")
            cleaned = clean_paper(raw, stats)
            display = rec["title"]
            src_path = "paper.pdf"
        else:
            raw = (RAW / group / rpath).read_text(encoding="utf-8")
            cleaned = clean_rst(raw, stats) if rpath.endswith(".rst") else clean_markdown(raw, stats)
            display = None
            src_path = rpath
        out_path = CLEAN / group / (src_path + ".txt")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(cleaned, encoding="utf-8")
        prose_chars = len(re.sub(r"^#{1,6}\s+.*$", "", cleaned, flags=re.M).strip())
        row = {"group": group, "path": src_path, "url": rec["url"], "sha256_raw": rec["sha256"],
               "retrieved_utc": rec["retrieved_utc"], "cleaned_chars": len(cleaned),
               "prose_chars": prose_chars, **stats, "included": True, "atomic_chunks": 0}
        if prose_chars < MIN_PROSE_CHARS:
            row["included"] = False
            row["drop_reason"] = f"<{MIN_PROSE_CHARS} prose chars after cleaning"
            dropped.append({"group": group, "path": src_path, "prose_chars": prose_chars})
            rows.append(row)
            continue
        title = display or file_title(cleaned, src_path)
        sections = to_sections(cleaned, title)
        adv = []
        n_file = 0
        for sec_title, sec_lines in sections:
            chunks = chunk_section(sec_lines)
            if not chunks:
                continue
            adv.append({"title": sec_title, "status": "ok", "chunk_text": " ".join(chunks)[:4000],
                        "atomic_chunks": [{"content": {"text": c}} for c in chunks]})
            all_lengths.extend(len(c) for c in chunks)
            n_file += len(chunks)
        if not adv:
            row["included"] = False
            row["drop_reason"] = "no chunk >= %d chars" % DROP_UNDER
            dropped.append({"group": group, "path": src_path, "prose_chars": prose_chars})
            rows.append(row)
            continue
        label = GROUP_LABEL.get(group, group)
        ci = len(top_chunks)
        top_chunks.append({"toc_hierarchy": [label, title], "toc_index": f"{ci + 1}",
                           "child_chunks": {"advanced_chunking_result": adv}})
        toc.append({"title": f"{label} / {title}", "level": 2})
        row["atomic_chunks"] = n_file
        n_atomic += n_file
        g = group_totals[group]
        g["files"] += 1
        g["cleaned_chars"] += len(cleaned)
        g["atomic_chunks"] += n_file
        rows.append(row)

    corpus = {"toc": toc, "chunks": top_chunks,
              "_provenance": {"generated_from": "natural-language Brick documentation (see SOURCES.md); no TTL, nothing generated from the schema",
                              "n_top_level_chunks": len(top_chunks), "n_atomic_chunks": n_atomic,
                              "note": "Addendum 27 exploratory natural-document corpus; bank never read by the builder."}}
    out_json = HERE / "corpus" / "natural_corpus.json"
    out_json.write_text(json.dumps(corpus, ensure_ascii=False, indent=1), encoding="utf-8")
    corpus_sha = hashlib.sha256(out_json.read_bytes()).hexdigest()

    L = sorted(all_lengths)
    stats_out = {
        "corpus_file": "corpus/natural_corpus.json", "corpus_sha256": corpus_sha,
        "top_level_chunks": len(top_chunks), "atomic_chunks": n_atomic,
        "atomic_chars_total": sum(L),
        "atomic_len": {"mean": round(statistics.mean(L), 1), "median": statistics.median(L),
                       "p90": L[int(0.9 * len(L))], "max": L[-1], "min": L[0]},
        "reference_pipeline_sample_len": {"mean": 389, "median": 315, "p90": 692},
        "by_group": group_totals, "files_included": sum(1 for r in rows if r["included"]),
        "files_dropped": dropped,
        "code_blocks_removed": sum(r["code_blocks_removed"] for r in rows),
        "code_chars_removed": sum(r["code_chars_removed"] for r in rows),
        "papers_not_fetched": log.get("papers_not_fetched", []),
        "rules": {"merge_under": MERGE_UNDER, "split_over": SPLIT_OVER, "drop_under": DROP_UNDER,
                  "min_prose_chars": MIN_PROSE_CHARS},
    }
    (HERE / "corpus_stats.json").write_text(json.dumps(stats_out, indent=1, ensure_ascii=False), encoding="utf-8")

    # SOURCES.md
    def lic_for(group: str) -> str:
        info = licenses.get(group)
        if info:
            if info.get("is_mit"):
                return "MIT (text of LICENSE; sha256 %s)" % info["sha256"][:12]
            if info.get("has_neither_the_name"):
                return "BSD-3-Clause-style (text of LICENSE incl. non-endorsement clause; '%s'; sha256 %s)" % (
                    info["first_line"], info["sha256"][:12])
        return "see paper statement"
    md = ["# SOURCES -- natural-language Brick corpus (addendum 27, exploratory)", "",
          "Retrieved with plain `urllib` requests, default User-Agent, no e-mail or personal identifier in any header or URL.",
          f"Fetch log: `corpus/fetch_log.json` (retrieved {log['fetched_utc']}). Selection rule: PLAN.md 27.3, fixed before any fetch; "
          "no TTL/OWL/SHACL/CSV schema file and nothing generated from the schema is included.", "",
          "## Groups, pins and licenses", "",
          "| Group | Repository / paper | Pin | License | Files | Atomic chunks | Cleaned chars |", "|---|---|---|---|---:|---:|---:|"]
    pins = {"brick-docs": ("BrickSchema/docs", "main @ 3f92114a643078432c50bc7f9de3ffb8f5980fe1"),
            "brick-website": ("BrickSchema/brick-website", "master @ b9506a909d4ccc1abe3234147ce13377f17a6bf9"),
            "py-brickschema": ("BrickSchema/py-brickschema", "master @ 50c7670acce806baa4a1d2c47101bff9bf37162e"),
            "brick-v1.4.4": ("BrickSchema/Brick", "tag v1.4.4 @ 4b5be60d27f9b4d96fe477f45513fa71afebe684")}
    for g, (repo, pin) in pins.items():
        t = group_totals[g]
        md.append(f"| {g} | {repo} | {pin} | {lic_for(g)} | {t['files']} | {t['atomic_chunks']} | {t['cleaned_chars']} |")
    for rec in [r for r in log["files"] if r["kind"] == "paper-pdf"]:
        t = group_totals[rec["group"]]
        ev = "; ".join(rec.get("license_evidence_lines", [])[:2])
        md.append(f"| {rec['group']} | {rec['title']} | {rec['url']} | CC BY (text of the paper: \"{ev}\") | {t['files']} | {t['atomic_chunks']} | {t['cleaned_chars']} |")
    md += ["", "## Papers considered and not used", ""]
    md.append("Rule (PLAN 27.3): only a paper with an explicit CC BY (no NC/ND) statement and a PDF fetchable without login. "
              "Candidates seen in the search \"Brick schema building metadata paper open access CC BY license\" (2026-10-17) and excluded: "
              "Applied Energy 2018 Brick paper (CC BY-NC-ND manuscript), Energy & Buildings 2024 EMIS framework (CC BY-NC-ND), "
              "Data Clearing House preprint (CC BY-NC-ND), BuildGraph and Build2SPARQL (CC BY-NC). "
              "CC BY candidates that could not be fetched: " +
              "; ".join(f"{p['title']} ({p['url']}: {p['error'][:90]})" for p in log.get("papers_not_fetched", [])) +
              ". No request was retried with altered headers.")
    md += ["", "## Corpus", "",
           f"`corpus/natural_corpus.json` sha256 `{corpus_sha}`: {len(top_chunks)} top-level chunks (one per file), {n_atomic} atomic chunks, "
           f"{sum(L)} characters; atomic length mean {stats_out['atomic_len']['mean']}, median {stats_out['atomic_len']['median']}, "
           f"p90 {stats_out['atomic_len']['p90']}, max {stats_out['atomic_len']['max']} "
           "(pipeline upstream sample: mean 389, median 315, p90 692).",
           f"Code removed: {stats_out['code_blocks_removed']} fenced/literal blocks, {stats_out['code_chars_removed']} characters.", ""]
    if dropped:
        md += ["Files dropped for < 200 prose characters after cleaning: " + ", ".join(f"{d['group']}/{d['path']}" for d in dropped), ""]
    md += ["## Per-file record", "",
           "| Group | Path | URL | raw sha256 | retrieved (UTC) | cleaned chars | code blocks removed | code chars removed | atomic chunks |",
           "|---|---|---|---|---|---:|---:|---:|---:|"]
    for r in rows:
        md.append(f"| {r['group']} | {r['path']} | {r['url']} | `{r['sha256_raw']}` | {r['retrieved_utc']} | {r['cleaned_chars']} | "
                  f"{r['code_blocks_removed']} | {r['code_chars_removed']} | {r['atomic_chunks'] if r['included'] else 'DROPPED'} |")
    (HERE / "SOURCES.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({k: stats_out[k] for k in ("top_level_chunks", "atomic_chunks", "atomic_chars_total", "atomic_len", "by_group", "code_blocks_removed", "files_dropped")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
