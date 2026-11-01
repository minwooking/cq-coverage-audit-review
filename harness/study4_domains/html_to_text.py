"""HTML (ReSpec / W3C TR pages) -> heading-marked plain text for the chunker (addendum 35 PLAN 35.3).  AI-generated; review before reuse.

Rules (fixed in PLAN.md): headings -> '#' lines; paragraphs, list items (as '- '), definition-table rows as 'Label: text';
dropped: script/style/nav/pre/figure/svg, tables of contents, example blocks, simple (prefix / IRI) tables, citations, section numbers,
and the sections whose heading matches SKIP_HEADING.  Deterministic, offline, stdlib only.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

SKIP_HEADING = re.compile(
    r"^(\d+(\.\d+)*\.?\s*|[A-Z]\.(\d+\.?)*\s*)?(acknowledge?ments?|change history|changes since|changes|references|examples?|conformance|"
    r"status of this document|table of contents|namespaces|security and privacy|accessibility|appendix|alignment with schema\.org|"
    r"normative references|informative references|copyright|compliance|cross reference)", re.I)
DROP_TAGS = {"script", "style", "nav", "pre", "figure", "svg", "cite", "head", "button", "select", "option", "noscript", "img"}
BLOCK = {"p", "div", "section", "article", "aside", "ul", "ol", "dl", "table", "tr", "li", "dt", "dd", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "header", "footer", "body", "html", "main"}
HEAD = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}


VOID = {"meta", "link", "br", "hr", "img", "input", "source", "area", "base", "col", "embed", "param", "track", "wbr"}


class _P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.buf: list[str] = []
        self.drop_depth = 0          # inside a DROP_TAGS / dropped-class element
        self.drop_stack: list[str] = []
        self.skip_level: int | None = None   # heading level of the section being skipped
        self.cur_head: int | None = None
        self.cell: list[str] | None = None
        self.row: list[str] = []
        self.in_th = False
        self.table_kind: list[str] = []
        self.li_depth = 0

    # ---- helpers
    def _dropping(self) -> bool:
        return self.drop_depth > 0 or self.skip_level is not None and self.cur_head is None

    def flush(self, prefix: str = "") -> None:
        t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
        self.buf = []
        if t and not self._dropping():
            self.out.append(prefix + t)
            self.out.append("")

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        ident = a.get("id") or ""
        if self.drop_depth and tag in VOID:
            return
        if self.drop_depth:
            self.drop_stack.append(tag)
            self.drop_depth += 1
            return
        drop = (tag in DROP_TAGS or "example" in cls or "example-title" in cls or "toc" in cls or ident in ("toc", "sotd", "references", "toc-nav")
                or "self-link" in cls or "secno" in cls or "header-wrapper" == "" or (tag == "bdi" and "secno" in cls)
                or "prop-list" in cls or (tag == "table" and "simple" in cls) or "note-title" in cls or "ednote" in cls or "issue" in cls and tag == "div" and "issue-container" not in ident)
        if drop and tag not in ("br", "img"):
            self.drop_depth = 1
            self.drop_stack = [tag]
            return
        if tag in HEAD:
            self.flush()
            self.cur_head = HEAD[tag]
        elif tag == "li":
            self.flush("- " if self.li_depth else "")
            self.li_depth += 1
        elif tag == "table":
            self.table_kind.append("def" if "def" in cls else "other")
        elif tag == "tr":
            self.flush()
            self.row = []
        elif tag in ("th", "td"):
            self.cell = []
            self.in_th = tag == "th"
        elif tag == "br":
            self.buf.append(" ")
        elif tag in BLOCK:
            self.flush("- " if self.li_depth else "")

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if self.drop_depth:
            self.drop_depth -= 1
            if self.drop_stack:
                self.drop_stack.pop()
            return
        if tag in HEAD:
            t = re.sub(r"\s+", " ", "".join(self.buf)).strip()
            self.buf = []
            lvl = HEAD[tag]
            self.cur_head = None
            if self.skip_level is not None and lvl <= self.skip_level:
                self.skip_level = None
            if SKIP_HEADING.match(t) and self.skip_level is None:
                self.skip_level = lvl
            if t and self.skip_level is None:
                self.out.append("#" * min(lvl, 4) + " " + t)
                self.out.append("")
        elif tag in ("th", "td") and self.cell is not None:
            self.row.append(re.sub(r"\s+", " ", "".join(self.cell)).strip())
            self.cell = None
        elif tag == "tr":
            if self.row and not self._dropping():
                cells = [c for c in self.row if c]
                if len(cells) >= 2 and self.table_kind and self.table_kind[-1] == "def":
                    lab = cells[0].rstrip(":")
                    if not lab.startswith("RDF "):          # 'RDF Class: dcat:Dataset' only restates the IRI
                        self.out.append(f"{lab}: {' '.join(cells[1:])}")
                        self.out.append("")
                elif cells and self.table_kind and self.table_kind[-1] != "def":
                    self.out.append(" | ".join(cells))
                    self.out.append("")
            self.row = []
        elif tag == "table":
            if self.table_kind:
                self.table_kind.pop()
        elif tag == "li":
            self.flush("- " if self.li_depth > 1 else "")
            self.li_depth = max(0, self.li_depth - 1)
        elif tag in BLOCK:
            self.flush("- " if self.li_depth else "")

    def handle_data(self, data):
        if self.drop_depth:
            return
        (self.cell if self.cell is not None else self.buf).append(data)


def convert(html_text: str) -> str:
    p = _P()
    p.feed(html_text)
    p.flush()
    text = "\n".join(p.out)
    text = re.sub(r"\s*\[\s*\]", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    return text
