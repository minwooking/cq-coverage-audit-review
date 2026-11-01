#!/usr/bin/env python3
"""READ-ONLY static review viewer for the 224-cell primary pass.

Presents all rows (CQ + judge's claimed span + rendered view) side-by-side,
searchable, in one self-contained HTML file openable from file://. It contains
no labeling capability and writes nothing but --out.

Run:  python build_review_viewer.py --sheet <224-row CSV> --views <views dir>
      --out <html path> [--working <working CSV>] [--ttl-dir <variants root>]

With a resolvable --ttl-dir (or the default …/../../variants next to --sheet)
each row also gets a build-time rdflib ego graph for the 그래프 tab; the
generated HTML itself stays dependency-free. The ego builder and the canvas
graph JS/CSS live in graph_view (shared verbatim with label_assist); this
module is the build-time orchestrator + static page shell.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

sys.path.insert(0, str(Path(__file__).resolve().parent))
# sibling-import via sys.path is the harness script convention (label_assist
# itself is the source of the safety checks); pyright cannot model the insert.
from label_assist import (  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
    SafetyError, check_out_path, verify_views)
# graph_view is label_assist's dependency (brv -> la -> graph_view, acyclic);
# reachable through the same sys.path insert.
import graph_view as gv  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]

EXPECTED_HEADER = ["cell_id", "cq_id", "cluster_id", "category", "variant", "cq_text",
                   "judge_evidence_span", "rendered_view_path", "evidence_span_verbatim",
                   "A", "rater_L1", "note"]


def fail(msg: str) -> NoReturn:
    print(f"[build_review_viewer] {msg}", file=sys.stderr)
    raise SystemExit(1)


@dataclass(frozen=True, slots=True)
class RowData:
    idx: int  # CSV row index (header is 0; data rows start at 1)
    cell_id: str
    category: str
    variant: str
    cq_text: str
    fragments: tuple[str, ...]
    badge: str | None
    lab_ev: str | None = None
    lab_note: str | None = None

    def to_json(self) -> dict[str, object]:
        out: dict[str, object] = {"idx": self.idx, "cell_id": self.cell_id,
                                  "category": self.category, "variant": self.variant,
                                  "cq": self.cq_text, "frags": list(self.fragments),
                                  "badge": self.badge}
        if self.lab_ev is not None:
            out["lab_ev"] = self.lab_ev
        if self.lab_note is not None:
            out["lab_note"] = self.lab_note
        return out


def parse_csv(path: Path) -> list[list[str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    if [c.strip() for c in rows[0]] != EXPECTED_HEADER:
        fail(f"헤더가 기대 12열과 다릅니다: {path}")
    return rows


def build_rows(sheet: Path, working: Path | None) -> list[RowData]:
    rows = parse_csv(sheet)
    labeled: dict[str, tuple[str, str, str]] = {}
    if working is not None:
        for w in parse_csv(working)[1:]:
            if w[9].strip():
                labeled[w[0]] = (w[9].strip(), w[8].strip(), w[11].strip())
    out: list[RowData] = []
    for i, r in enumerate(rows[1:], start=1):
        lab = labeled.get(r[0])
        ev = lab[1] if lab and lab[0] == "1" and lab[1] else None
        note = lab[2] if lab and lab[0] == "0" and lab[2] else None
        out.append(RowData(i, r[0], r[3], r[4], r[5], gv.split_fragments(r[6]),
                           lab[0] if lab else None, ev, note))
    return out


# ---------------------------------------------------------------------------
# build-time per-row ego graphs. The builder itself lives in graph_view (shared
# with label_assist); this is the batch orchestrator: one VariantGraph load per
# variant, one ego slice per row.
# ---------------------------------------------------------------------------

def build_graphs_for_rows(rows: list[RowData],
                          ttl_dir: Path | None) -> list[gv.EgoGraph] | None:
    if ttl_dir is None:
        return None
    cache: dict[str, gv.VariantGraph] = {}
    graphs: list[gv.EgoGraph] = []
    for r in rows:
        if r.variant not in cache:
            path = ttl_dir / r.variant / f"graph_{r.variant}.ttl"
            if not path.is_file():
                fail(f"시트가 참조하는 variant '{r.variant}'의 TTL 없음: {path}")
            cache[r.variant] = gv.load_variant_ttl(path)
            print(f"[build_review_viewer] variant {r.variant}: {len(cache[r.variant].sorted_nodes)} nodes loaded")
        graphs.append(gv.ego_graph(cache[r.variant], gv.cq_tokens(r.cq_text),
                                   gv.judge_ev(r.fragments)))
    return graphs


def build_html(rows: list[RowData], views: dict[str, Path],
               graphs: list[gv.EgoGraph] | None = None) -> str:
    rows_json = [r.to_json() for r in rows]
    if graphs is not None:
        for d, g in zip(rows_json, graphs):
            d["graph"] = g
    payloads: dict[str, object] = {
        "rows": rows_json,
        "views": {v: p.read_text(encoding="utf-8") for v, p in views.items()},
        "labeled": sum(1 for r in rows if r.badge is not None),
        "total": len(rows)}
    # "</" inside the data would terminate the <script> element; "<\/" is a legal
    # JSON escape for the same string content. U+2028/29 are line breaks to JS.
    data = json.dumps(payloads, ensure_ascii=False).replace("</", "<\\/") \
        .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    return PAGE % {"data": data, "graph_css": gv.GRAPH_CSS,
                   "graph_canvas": gv.graph_canvas_html(
                       "그래프는 탐색용 — 판정 근거는 텍스트 뷰의 원문 span"),
                   "graph_js": gv.GRAPH_JS}


PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>224-cell review (read-only)</title><style>
body{margin:0;font-family:sans-serif;display:flex;height:100vh;font-size:14px}
#side{width:340px;min-width:250px;overflow:auto;border-right:2px solid #cbd5e1;background:#f8fafc}
#prog{position:sticky;top:0;background:#0f172a;color:#fff;padding:.6em;font-weight:700}
.it{padding:.5em .7em;border-bottom:1px solid #e2e8f0;cursor:pointer}
.it:hover{background:#e0f2fe}.it.on{background:#bae6fd;border-left:4px solid #0284c7}
.bg1{color:#15803d;font-weight:700}.bg0{color:#b91c1c;font-weight:700}
#main{flex:1;overflow:hidden;padding:1em 1.4em;display:flex;flex-direction:column;min-width:0}
#cq{font-size:1.4em}
.chip{display:inline-block;background:#e0e7ff;border-radius:1em;padding:.15em .7em;margin:.1em;font-size:.85em}
#judgebox{background:#e5e7eb;border:1px solid #9ca3af;padding:.6em;margin:.6em 0}
.frag{display:block;text-align:left;margin:.3em 0;padding:.4em;font-size:.8em;
 background:#fff;border:1px dashed #6b7280;cursor:pointer;white-space:pre-wrap;word-break:break-all}
.frag:hover{background:#fef9c3}
#bar{position:sticky;top:0;background:#fafafa;padding:.4em 0;z-index:2}
#view{background:#fff;border:1px solid #cbd5e1;padding:.6em;white-space:pre-wrap;font-size:.8em}
mark{background:#fde047}
#hits{font-weight:700;margin:0 .6em}#copymsg{color:#15803d;margin-left:.5em}
#tabs{display:flex;gap:.4em;margin-bottom:.5em}
.tabb{padding:.35em 1.2em;border:1px solid #94a3b8;background:#e2e8f0;cursor:pointer;border-radius:.5em .5em 0 0;font-weight:700;font-size:1em}
.tabb.on{background:#0284c7;color:#fff}
#tabtext{overflow:auto;flex:1;min-height:0}
#tabgraph{flex:1;min-height:0;flex-direction:column;display:none}
%(graph_css)s
</style></head><body>
<div id="side"><div id="prog"></div><div id="list"></div></div>
<div id="main">
<div id="tabs"><button class="tabb on" id="btnt" onclick="setTab('text')">텍스트</button><button class="tabb" id="btng" onclick="setTab('graph')">그래프</button></div>
<div id="tabtext">
<h2 id="cq"></h2><div id="chips"></div><div id="judgebox"></div>
<div id="bar"><input id="q" size="42" placeholder="뷰 내부 검색 (대소문자 무시)">
<button onclick="runSearch()">검색</button><button onclick="stepSearch(-1)">이전</button>
<button onclick="stepSearch(1)">다음</button><span id="hits"></span>
<button onclick="copySel()">선택 복사</button><span id="copymsg"></span>
 · j/k·↑/↓ 행 이동</div>
<pre id="view"></pre>
</div>
<div id="tabgraph">
%(graph_canvas)s
</div>
</div>
<script id="data" type="application/json">%(data)s</script>
<script>
const D=JSON.parse(document.getElementById("data").textContent);
const pre=document.getElementById("view"),qEl=document.getElementById("q");
let cur=0,hits=[],hi=0,raw="";
function esc(s){return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
function badge(r){return r.badge==="1"?'<span class="bg1">✓ A=1</span>':
 (r.badge==="0"?'<span class="bg0">✗ A=0</span>':"");}
function go(k){cur=Math.max(0,Math.min(D.rows.length-1,k));render();}
function render(){
 const r=D.rows[cur];
 document.getElementById("prog").textContent=D.labeled+" labeled / "+D.total+" (읽기 전용)";
 document.getElementById("cq").textContent=r.cq;
 document.getElementById("chips").innerHTML='<span class="chip">'+esc(r.cell_id)+
  '</span><span class="chip">variant '+esc(r.variant)+'</span><span class="chip">'+
  esc(r.category)+'</span><span class="chip">'+badge(r)+'</span>';
 const jb=document.getElementById("judgebox");jb.replaceChildren();
 const t=document.createElement("b");
 t.textContent="judge의 인용 주장 — 뷰에 실제로 존재하는지 클릭으로 검증";jb.appendChild(t);
 if(!r.frags.length){const p=document.createElement("div");p.textContent="(judge span 없음)";
  jb.appendChild(p);}
 r.frags.forEach(f=>{const b=document.createElement("button");b.className="frag";
  b.textContent=f;b.onclick=()=>searchText(f);jb.appendChild(b);});
 raw=D.views[r.variant]??"";
 qEl.value="";hits=[];document.getElementById("hits").textContent="";pre.textContent=raw;
 document.getElementById("list").innerHTML=D.rows.map((x,k)=>'<div class="it'+
  (k===cur?" on":"")+'" onclick="go('+k+')"><b>'+x.idx+'</b> '+badge(x)+
  '<br>'+esc(x.cell_id)+' · '+esc(x.category)+'<br>'+esc(x.cq.slice(0,60))+'</div>').join("");
 const it=document.querySelectorAll("#list .it");
 if(it[cur])it[cur].scrollIntoView({block:"nearest"});
 EGOHOST.graph=D.rows[cur].graph||null;
 EGOHOST.overlay={lab_ev:r.lab_ev,lab_note:r.lab_note,badge:r.badge};
 egoInvalidate(tab==="graph");
}
function applyMarks(term){
 const low=raw.toLowerCase(),q=term.toLowerCase();hits=[];
 if(term){let i=low.indexOf(q);while(i>=0){hits.push(i);i=low.indexOf(q,i+q.length);}}
 hi=0;let out="",last=0;
 hits.forEach(h=>{out+=esc(raw.slice(last,h))+"<mark>"+esc(raw.slice(h,h+term.length))+
  "</mark>";last=h+term.length;});
 out+=esc(raw.slice(last));pre.innerHTML=out;
 document.getElementById("hits").textContent=term?(hits.length+"건"):"0건 — 뷰에 없음";
 if(hits.length)pre.getElementsByTagName("mark")[0].scrollIntoView({block:"center"});
}
function runSearch(){applyMarks(qEl.value);}
function stepSearch(d){if(!hits.length)return;hi=(hi+d+hits.length)%%hits.length;
 pre.getElementsByTagName("mark")[hi].scrollIntoView({block:"center"});}
function searchText(t){qEl.value=t;runSearch();}
function copySel(){
 const s=String(getSelection());const msg=document.getElementById("copymsg");
 if(!s){msg.textContent="뷰에서 드래그 선택하세요";msg.style.color="#b91c1c";return;}
 const ok=()=>{msg.textContent="복사됨 ("+s.length+"자)";msg.style.color="#15803d";};
 const fb=()=>{const ta=document.createElement("textarea");ta.value=s;
  ta.style.position="fixed";ta.style.opacity="0";document.body.appendChild(ta);
  ta.select();document.execCommand("copy");ta.remove();ok();};
 if(navigator.clipboard&&navigator.clipboard.writeText){
  navigator.clipboard.writeText(s).then(ok,fb);}else{fb();}
}
document.addEventListener("keydown",e=>{
 if(/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName))return;
 if(e.key==="j"||e.key==="ArrowDown"){e.preventDefault();go(cur+1);}
 else if(e.key==="k"||e.key==="ArrowUp"){e.preventDefault();go(cur-1);}
});
const EGOHOST={graph:null,overlay:null,emptyInfo:"TTL 미로드 — 그래프 탭 비활성",visible:false};
const tabtext=document.getElementById("tabtext"),tabgraph=document.getElementById("tabgraph");
let tab="text";
function setTab(t){tab=t;EGOHOST.visible=(t==="graph");
 tabtext.style.display=t==="text"?"":"none";
 tabgraph.style.display=t==="graph"?"flex":"none";
 document.getElementById("btnt").className="tabb"+(t==="text"?" on":"");
 document.getElementById("btng").className="tabb"+(t==="graph"?" on":"");
 if(t==="graph")egoInvalidate(true);}
go(0);
%(graph_js)s
</script></body></html>"""


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Read-only static review viewer generator")
    p.add_argument("--sheet", required=True, type=Path)
    p.add_argument("--views", required=True, type=Path)
    p.add_argument("--out", type=Path, default=Path("<labels>/share/review_viewer.html"))
    p.add_argument("--working", type=Path, default=None,
                   help="optional working CSV; read-only label badges + progress")
    p.add_argument("--ttl-dir", type=Path, default=None, help="variants root holding <V>/graph_<V>.ttl; default: …/../../variants resolved from --sheet; without a resolvable dir the graph tab stays inert")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    out = Path(args.out).expanduser().resolve()
    try:
        check_out_path(out)  # identical repo-inside rejection as label_assist
    except SafetyError as exc:
        fail(str(exc))
    if not args.sheet.is_file():
        fail(f"--sheet 없음: {args.sheet}")
    if args.working is not None and not args.working.is_file():
        fail(f"--working 없음: {args.working}")  # never silently drop the progress source
    try:
        views = verify_views(args.views)
    except SafetyError as exc:
        fail(f"뷰 검증 실패: {exc}")
    rows = build_rows(args.sheet, args.working.expanduser() if args.working else None)
    try:
        ttl_dir = gv.resolve_ttl_dir(args.sheet, args.ttl_dir)
    except gv.TtlDirError as exc:
        fail(str(exc))
    try:
        graphs = build_graphs_for_rows(rows, ttl_dir)
    except gv.TtlLoadError as exc:
        fail(str(exc))
    html = build_html(rows, views, graphs)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"[build_review_viewer] {out} written ({out.stat().st_size} bytes)")
    if graphs is not None:
        sizes: list[int] = []
        rootc: list[int] = []
        for g in graphs:
            if ns := g.get("nodes"):
                sizes.append(len(ns))
                rootc.append(sum(1 for n in ns if n.get("cls") == "root"))
        med = statistics.median(sizes) if sizes else 0
        medr = statistics.median(rootc) if rootc else 0
        at_cap = sum(1 for s in sizes if s >= gv.MAX_NODES)
        print(f"[build_review_viewer] graphs: {len(sizes)}/{len(graphs)} rows non-empty; "
              f"ego nodes median {med} max {max(sizes) if sizes else 0}; roots median {medr}; "
              f"rows at {gv.MAX_NODES} cap {at_cap}/{len(graphs)}")


if __name__ == "__main__":
    main()
