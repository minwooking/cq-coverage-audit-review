#!/usr/bin/env python3
"""Shared ego-graph builder + graph view assets for the 224-cell labeling tools.

Extracted from build_review_viewer so the interactive label_assist server and
the static review viewer compute and render *identical* ego graphs. Import
direction is fixed and acyclic: build_review_viewer -> label_assist ->
graph_view; this module imports no harness sibling. rdflib is imported lazily
inside load_variant_ttl, so merely importing this module never requires rdflib
(the label_assist "TTL/rdflib absent" degradation depends on that).

Also hosts the dependency-free canvas graph assets (GRAPH_CSS,
graph_canvas_html, GRAPH_JS) shared by both frontends. The JS is written
against a tiny host protocol: the page defines `EGOHOST`
({graph, overlay, emptyInfo, visible}) before this script, and drives it via
egoInvalidate()/egoRender().
"""
# allow: SIZE_OK — owner-mandated single extraction module (brief fixes the
# file layout: ego builder + graph JS/CSS in one graph_view.py surface).
from __future__ import annotations

import ast
import html
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict


class TtlLoadError(RuntimeError):
    """TTL cannot be parsed or rdflib is unavailable -> caller degrades/fails."""


class TtlDirError(ValueError):
    """An explicit --ttl-dir path does not exist (CLI-level refusal, both tools)."""


def split_fragments(raw: str) -> tuple[str, ...]:
    """The judge span is a python-list repr; literal_eval is safe here (literals
    only) and keeps quoting rules identical to the builder that wrote it."""
    raw = raw.strip()
    if not raw:
        return ()
    try:
        parsed = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return (raw,)
    if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
        return tuple(x for x in parsed if x.strip())
    if isinstance(parsed, str) and parsed.strip():
        return (parsed,)
    return (raw,)


# ---------------------------------------------------------------------------
# ego-graph builder (deterministic: judge-URI + CQ-token roots, depth-2 BFS,
# fair-share node budget). The whole-graph variants are hairballs (D=44k
# triples), so only an ego neighborhood of each row's roots is ever rendered.
# ---------------------------------------------------------------------------

JUDGE_URI_RE = re.compile(r"\s*(https?://[^\s|]+)\s*\|")
MAX_NODES = 120
MAX_EDGES = 250
MAX_ROOTS = 25
MAX_TIPS_PER_NODE = 3
ROW_TIP_BUDGET = 60
TIP_VALUE_CHARS = 70
LABEL_CHARS = 120
GENERIC_SHARE = 0.15
EV_TEXT_CHARS = 500
INSPAN_MIN_LOCAL_CHARS = 4
WORD_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset("""a about above after again against all am an and any are as at be
because been before being below between both but by can cannot could did do does doing down
during each few for from further had has have having he her here hers herself him himself his
how i if in into is it its itself just many may might me more most my myself no nor not now of
off on once only or other our ours ourselves out over own please same shall she should so some
such tell than that the their theirs them themselves then there these they this those through
to too under until up very was we were what when where which while who whom why will with would
you your yours yourself yourselves describe show list give also""".split())


def _words(text: str) -> list[str]:
    out: list[str] = []
    for part in re.split(r"[^A-Za-z0-9]+", text):
        out += [w.lower() for w in
                re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z][a-z0-9]*|[a-z0-9]+", part)]
    return out


def local_name(iri: str) -> str:
    cut = max(iri.rfind("#"), iri.rfind(":"))
    return iri[cut + 1:] if cut >= 0 else iri


def cq_tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower())
            if len(t) >= 3 and t not in STOPWORDS}


@dataclass(frozen=True, slots=True)
class JudgeEvidence:
    uris: tuple[str, ...]
    text: dict[str, str]


def judge_ev(frags: tuple[str, ...]) -> JudgeEvidence:
    uris: list[str] = []
    text: dict[str, str] = {}
    for f in frags:
        m = JUDGE_URI_RE.match(f)
        if not m:
            continue
        uri = m.group(1)
        uris.append(uri)
        _, sep, body = f.partition(" | ")
        body = body.strip()[:EV_TEXT_CHARS]
        if sep and body and uri not in text:
            text[uri] = body
    return JudgeEvidence(tuple(uris), text)


class EgoNode(TypedDict, total=False):
    id: str
    label: str
    cls: str
    judge: bool
    tips: list[str]
    ev: str
    inspan: bool


class EgoEdge(TypedDict):
    s: str
    p: str
    o: str


class EgoGraph(TypedDict, total=False):
    info: str
    nodes: list[EgoNode]
    edges: list[EgoEdge]


@dataclass(slots=True)
class VariantGraph:
    sorted_nodes: list[str]
    adj: dict[str, list[tuple[str, str]]]
    radj: dict[str, list[tuple[str, str]]]
    tips: dict[str, list[str]]
    words: dict[str, frozenset[str]]
    labels: dict[str, str]
    label_words: dict[str, frozenset[str]]
    generic: frozenset[str]


def load_variant_ttl(path: Path) -> VariantGraph:
    # Lazy rdflib: importing graph_view must never require it (label_assist
    # degrades to "TTL 없음" instead of crashing). Any parse failure folds
    # into TtlLoadError so both callers degrade/fail through one type.
    try:
        from rdflib import Graph, Literal, RDFS, SKOS, URIRef
    except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
        raise TtlLoadError(f"rdflib를 불러올 수 없습니다: {exc}") from exc
    try:
        g = Graph().parse(str(path), format="turtle")
    except Exception as exc:  # rdflib raises many parser types at this boundary
        raise TtlLoadError(f"TTL 파싱 실패 ({path.name}): {exc}") from exc
    nodes: set[str] = set()
    adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
    radj: dict[str, list[tuple[str, str]]] = defaultdict(list)
    lits: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for s, p, o in g:
        if not isinstance(s, URIRef):
            continue
        s_str, pl = str(s), local_name(str(p))
        nodes.add(s_str)
        if isinstance(o, URIRef):
            o_str = str(o)
            nodes.add(o_str)
            adj[s_str].append((pl, o_str))
            radj[o_str].append((pl, s_str))
        elif isinstance(o, Literal) and (val := str(o).strip()):
            lits[s_str].append((pl, val[:TIP_VALUE_CHARS]))
    sorted_nodes = sorted(nodes)
    words: dict[str, frozenset[str]] = {}
    labels: dict[str, str] = {}
    label_words: dict[str, frozenset[str]] = {}
    counts: Counter[str] = Counter()
    for n in sorted_nodes:
        label = ""
        ref = URIRef(n)
        for pred in (RDFS.label, SKOS.prefLabel):
            for val in g.objects(ref, pred):
                label = str(val)
                break
            if label:
                break
        labels[n] = (label or local_name(n))[:LABEL_CHARS]
        words[n] = frozenset(_words(local_name(n)))
        label_words[n] = frozenset(WORD_RE.findall(labels[n].lower()))
        counts.update(words[n] | label_words[n])
    generic = frozenset(w for w, c in counts.items()
                        if len(w) >= 3 and c > GENERIC_SHARE * len(sorted_nodes))
    for lst in adj.values():
        lst.sort()
    for lst in radj.values():
        lst.sort()
    tips = {n: [f"{pl} {v}" for pl, v in sorted(lits[n])] for n in lits}
    return VariantGraph(sorted_nodes, dict(adj), dict(radj), tips, words, labels,
                        label_words, generic)


def ego_graph(vg: VariantGraph, tokens: set[str], jev: JudgeEvidence) -> EgoGraph:
    """Depth-2 ego graph around judge-quoted + CQ-token-matched nodes.

    Root selection (all deterministic): judge URIs first; then nodes whose
    local-name WORDS match eff-tokens, ranked by distinct exact-word count then
    IRI; then nodes whose label WORDS (full-token word-boundary, never
    fragments) match, in IRI order. eff-tokens drop generic tokens (>15% of the
    variant's label/local word share) so hub vocabulary like brick/air/sensor
    cannot flood the roots. Roots cap at 25. BFS depth 2 records each
    neighbor's best (lowest) root rank; the node budget beyond the roots goes
    to hop1 first, and within a hop round-robins across root ranks (fair-share)
    so one Brick hub cannot monopolize the view. A judge node carries its
    evidence line as 'ev'; a non-judge node whose local name (>=4 chars,
    case/separator-insensitive substring) appears in an evidence line is
    flagged 'inspan'. Edges keep subject->object direction, capped at 250,
    sorted by endpoint hop then (predicate, object).
    """
    eff = tokens - vg.generic
    judges = [u for u in dict.fromkeys(jev.uris) if u in vg.labels]
    judges_set = set(judges)
    exact: list[tuple[int, str]] = []
    label_tier: list[str] = []
    for n in vg.sorted_nodes:
        if n in judges_set:
            continue
        hits = sum(1 for t in eff if t in vg.words[n])
        if hits:
            exact.append((-hits, n))
        elif eff & vg.label_words[n]:
            label_tier.append(n)
    roots = (judges + [n for _, n in sorted(exact)] + label_tier)[:MAX_ROOTS]
    if not roots:
        return {"info": "roots 없음"}
    hop: dict[str, int] = dict.fromkeys(roots, 0)
    rank = {rt: ri for ri, rt in enumerate(roots)}
    frontier = list(roots)
    for depth in (1, 2):
        nxt: list[str] = []
        for n in frontier:
            for _, m in vg.adj.get(n, ()):
                if m not in hop:
                    hop[m] = depth
                    rank[m] = rank[n]
                    nxt.append(m)
            for _, m in vg.radj.get(n, ()):
                if m not in hop:
                    hop[m] = depth
                    rank[m] = rank[n]
                    nxt.append(m)
        frontier = nxt
    seen: Counter[tuple[int, int]] = Counter()
    keyed: list[tuple[int, int, int, str]] = []
    for n in sorted((n for n, d in hop.items() if d > 0), key=lambda x: (hop[x], rank[x], x)):
        pos = seen[(rank[n], hop[n])]
        seen[(rank[n], hop[n])] += 1
        keyed.append((hop[n], pos, rank[n], n))
    keyed.sort()
    budget = roots + [n for _, _, _, n in keyed][:MAX_NODES - len(roots)]
    keep = set(budget)
    cands = sorted((hop[s], hop[o], pl, s, o)
                   for s in budget for pl, o in vg.adj.get(s, ()) if o in keep)
    edges: list[EgoEdge] = [{"s": s, "p": pl, "o": o} for _, _, pl, s, o in cands[:MAX_EDGES]]
    ev_lowers = [t.lower() for t in (jev.text[u] for u in judges if u in jev.text)]
    tip_budget = ROW_TIP_BUDGET
    nodes_out: list[EgoNode] = []
    for n in budget:
        tips = vg.tips.get(n, [])[:min(MAX_TIPS_PER_NODE, tip_budget)]
        tip_budget -= len(tips)
        node: EgoNode = {"id": n, "label": vg.labels[n],
                         "cls": "root" if hop[n] == 0 else f"hop{hop[n]}",
                         "judge": n in judges_set, "tips": list(tips)}
        if n in judges_set:
            if (ev := jev.text.get(n)):
                node["ev"] = ev
        elif ev_lowers and len(ln := local_name(n)) >= INSPAN_MIN_LOCAL_CHARS:
            flat = ln.lower().replace("-", " ").replace("_", " ")
            if any(ln.lower() in t or flat in t for t in ev_lowers):
                node["inspan"] = True
        nodes_out.append(node)
    return {"nodes": nodes_out, "edges": edges}


def resolve_ttl_dir(sheet: Path, explicit: Path | None) -> Path | None:
    """Explicit --ttl-dir must exist (TtlDirError); the default is the
    …/../../variants root next to the sheet's run dir, None when absent.
    Callers own the exit-vs-degrade policy for TtlDirError."""
    if explicit is not None:
        if not explicit.is_dir():
            raise TtlDirError(f"--ttl-dir 없음: {explicit}")
        return explicit
    default = sheet.resolve().parent.parent.parent / "variants"
    return default if default.is_dir() else None


# ---------------------------------------------------------------------------
# shared front-end assets: graph CSS, canvas DOM, canvas force-layout engine.
# Host pages own the tab container layout and define EGOHOST before GRAPH_JS.
# ---------------------------------------------------------------------------

GRAPH_CSS = """\
#gbanner{background:#fef3c7;border:1px solid #f59e0b;padding:.4em .7em;margin-bottom:.4em;font-size:14px;border-radius:.3em}
#gwrap{position:relative;flex:1;min-height:0;border:1px solid #cbd5e1;background:#fff;overflow:hidden}
#gcv{position:absolute;left:0;top:0;cursor:grab}
#glegend{position:absolute;top:8px;right:8px;background:#f8fafc;border:1px solid #94a3b8;padding:.3em .6em;font-size:12px;line-height:1.6;border-radius:.3em;max-width:260px;z-index:2}
#glegend summary{cursor:pointer;font-weight:700}
#gzoom{position:absolute;left:10px;top:8px;z-index:2;display:flex;gap:.2em}
#gzoom button{min-width:32px;min-height:28px;font-size:14px;font-weight:700}
.ldot{display:inline-block;width:.7em;height:.7em;border-radius:.35em;margin-right:.3em;vertical-align:-.05em}
.lsq{display:inline-block;width:.7em;height:.7em;margin-right:.3em;vertical-align:-.05em}
.ltri{display:inline-block;width:.8em;height:.7em;margin-right:.3em;vertical-align:-.05em;clip-path:polygon(50% 0,0 100%,100% 100%)}
.lring{display:inline-block;width:.7em;height:.7em;border-radius:.35em;border:2px solid #d4af37;margin-right:.3em;vertical-align:-.05em}
#gpanel{position:absolute;left:10px;bottom:10px;max-width:430px;max-height:230px;overflow:auto;background:#0f172a;color:#f1f5f9;padding:.5em .7em;font-size:13px;display:none;white-space:pre-wrap;border-radius:.3em}
#gpanel button{margin:.2em .4em .2em 0;font-size:.9em}
#gpanel pre{margin:.3em 0;white-space:pre-wrap}
#gtip{position:absolute;display:none;background:#0f172a;color:#f1f5f9;padding:.35em .5em;font-size:13px;white-space:pre-wrap;max-width:340px;pointer-events:none;border-radius:.3em;z-index:3}
.pnote{color:#94a3b8;font-size:.9em}
.pev{color:#fbbf24;margin:.3em 0;white-space:pre-wrap}
.plab{color:#4ade80;margin:.3em 0;white-space:pre-wrap}
.pinspan{color:#d4af37;margin:.2em 0}
.pdraft{color:#5eead4;margin:.2em 0}
.lring2{display:inline-block;width:.7em;height:.7em;border-radius:.35em;border:2px dashed #0f766e;margin-right:.3em;vertical-align:-.05em}
.lline{display:inline-block;width:1.6em;height:0;margin-right:.3em;vertical-align:.25em}"""


def graph_canvas_html(banner: str) -> str:
    """The shared graph tab body: banner + canvas + legend + panels/tooltip.
    `banner` is host wording (the static viewer and the labeling server warn
    about different things), everything else is identical."""
    return (
        f'<div id="gbanner">{html.escape(banner)}</div>\n'
        '<div id="gwrap"><canvas id="gcv" role="img" aria-label="ego 그래프"></canvas>\n'
        '<div id="gzoom" role="group" aria-label="그래프 확대/축소">'
        '<button type="button" id="gzin" aria-label="확대" title="확대">+</button>'
        '<button type="button" id="gzout" aria-label="축소" title="축소">&minus;</button>'
        '<button type="button" id="gzreset" aria-label="보기 초기화" title="보기 초기화">1:1</button></div>\n'
        '<details id="glegend" open><summary>범례 (ego 그래프)</summary>'
        '<i class="lsq" style="background:#f97316"></i>root (직접 매칭, 네모)<br>'
        '<i class="ldot" style="background:#3b82f6"></i>hop1 (원)<br>'
        '<i class="ltri" style="background:#6b7280"></i>hop2 (삼각형, 라벨은 확대 시)<br>'
        '<b>노드</b> (네모/원/삼각형 = 형태)<br>'
        '<i class="lring"></i>judge 인용 노드 (금색 실선 링)<br>'
        '<i class="ldot" style="background:#d4af37"></i>in-span: judge 인용문에 이름 등장 (금색 점)<br>'
        '<i class="lring2"></i>초안 span에 이름 등장 (청록 점선 링, 초안이 있을 때만)<br>'
        '<i class="ldot" style="background:#16a34a"></i>내 라벨 근거<br>'
        '<b>엣지</b><br>'
        '<i class="lline" style="border-top:1px solid #cbd5e1"></i>일반<br>'
        '<i class="lline" style="border-top:3px solid #b8860b"></i>양끝이 judge 인용/in-span (굵은 금색 실선)<br>'
        '<i class="lline" style="border-top:3px dashed #0f766e"></i>양끝이 초안 span 일치 (굵은 청록 점선)<br>'
        '<small>이름 일치 기반 표시일 뿐 관계 보증 아님</small></details>\n'
        '<div id="gpanel"></div><div id="gtip"></div></div>'
    )


# Ego canvas engine. Protocol: the host page defines EGOHOST =
# {graph: EgoGraph|null, overlay: {lab_ev?,lab_note?,badge?}|null,
#  emptyInfo: str, visible: bool, draftSpan?: str} BEFORE this script, calls
# egoInvalidate(true) after changing graph/overlay or showing the tab.
GRAPH_JS = """\
const gwrap=document.getElementById("gwrap"),gcv=document.getElementById("gcv"),gpanel=document.getElementById("gpanel");
const gtip=document.getElementById("gtip");
const ctx=gcv.getContext("2d");
const GCOLOR={root:"#f97316",hop1:"#3b82f6",hop2:"#6b7280"};
let egoDirty=true,gcur=null,gpos=[],gedges=[],gidx={},gv={s:1,x:0,y:0};
let gdr=[],gjs=[];
function nameIn(id,text){if(!text)return false;const ln=loc(id);if(ln.length<4)return false;
 const l=ln.toLowerCase(),t=text.toLowerCase();return t.includes(l)||t.includes(l.replace(/[-_]/g," "));}
let gdrag=-1,gpan=false,gmoved=0,gpx=0,gpy=0,gedge=-1;
function egoInvalidate(renderIfVisible){egoDirty=true;if(renderIfVisible&&EGOHOST.visible)egoRender();}
function fitCanvas(){const w=gwrap.clientWidth||800,h=gwrap.clientHeight||600;
 if(gcv.width!==w||gcv.height!==h){gcv.width=w;gcv.height=h;}}
function trunc(s){return s.length>24?s.slice(0,23)+"…":s;}
function loc(u){const c=Math.max(u.lastIndexOf("#"),u.lastIndexOf(":"));return c<0?u:u.slice(c+1);}
function egoRender(){
 egoDirty=false;gedge=-1;gpanel.style.display="none";gtip.style.display="none";fitCanvas();
 gv={s:1,x:0,y:0};gdrag=-1;gpan=false;
 gcur=EGOHOST.graph||null;
 if(!gcur||!gcur.nodes){egoDraw();return;}
 const n=gcur.nodes.length;
 gidx={};gcur.nodes.forEach((nd,i)=>{gidx[nd.id]=i;});
 const cx=gcv.width/2,cy=gcv.height/2;
 gpos=gcur.nodes.map((nd,i)=>{const r=40+Math.min(gcv.width,gcv.height)/2.6*(0.25+0.75*i/n);
  return{x:cx+r*Math.cos(i*2.399963),y:cy+r*Math.sin(i*2.399963)};});
 gedges=gcur.edges.map(e=>[gidx[e.s],gidx[e.o],e.p]);
 gdr=gcur.nodes.map(nd=>nameIn(nd.id,EGOHOST.draftSpan));
 gjs=gcur.nodes.map(nd=>!!(nd.judge||nd.inspan));
 for(let t=0;t<600;t++)tickG();
 egoDraw();}
function tickG(){
 const n=gpos.length;const fx=new Float64Array(n),fy=new Float64Array(n);
 const cx=gcv.width/2,cy=gcv.height/2;
 for(let i=0;i<n;i++)for(let j=i+1;j<n;j++){
  let dx=gpos[i].x-gpos[j].x,dy=gpos[i].y-gpos[j].y;
  let d2=dx*dx+dy*dy;if(d2<0.01){dx=j-i;dy=1;d2=dx*dx+1;}
  const d=Math.sqrt(d2),f=2400/d2,ux=dx/d,uy=dy/d;
  fx[i]+=ux*f;fy[i]+=uy*f;fx[j]-=ux*f;fy[j]-=uy*f;}
 for(const e of gedges){const a=e[0],b=e[1];
  const dx=gpos[b].x-gpos[a].x,dy=gpos[b].y-gpos[a].y;
  const d=Math.max(1,Math.hypot(dx,dy)),f=(d-95)*0.02,ux=dx/d,uy=dy/d;
  fx[a]+=ux*f;fy[a]+=uy*f;fx[b]-=ux*f;fy[b]-=uy*f;}
 for(let i=0;i<n;i++){
  fx[i]+=(cx-gpos[i].x)*0.006;fy[i]+=(cy-gpos[i].y)*0.006;
  if(i===gdrag)continue;
  let mx=fx[i]*0.8,my=fy[i]*0.8;const m=Math.hypot(mx,my);
  if(m>14){mx*=14/m;my*=14/m;}
  gpos[i].x+=mx;gpos[i].y+=my;}}
function sx(x){return x*gv.s+gv.x;}
function sy(y){return y*gv.s+gv.y;}
function egoDraw(){
 ctx.clearRect(0,0,gcv.width,gcv.height);
 gcv.setAttribute("aria-label",(gcur&&gcur.nodes)?"ego 그래프: 노드 "+gcur.nodes.length+"개, 엣지 "+gcur.edges.length+"개. judge 인용 강조 노드 "+gjs.filter(Boolean).length+"개, 초안 span 이름 일치 노드 "+gdr.filter(Boolean).length+"개, 초안 일치 엣지 "+gedges.filter(e=>gdr[e[0]]&&gdr[e[1]]).length+"개. 이름 일치 기반이며 관계 보증 아님. 판정은 텍스트 탭의 원문으로 하세요.":"ego 그래프 없음");
 if(!gcur||!gcur.nodes){ctx.fillStyle="#64748b";ctx.font="15px sans-serif";
  ctx.textAlign="center";ctx.textBaseline="middle";
  const g=EGOHOST.graph;
  ctx.fillText(g?(g.info||"그래프 없음"):EGOHOST.emptyInfo,gcv.width/2,gcv.height/2);
  ctx.textAlign="left";ctx.textBaseline="alphabetic";return;}
 for(let i=0;i<gedges.length;i++){const e=gedges[i];
  const ax=sx(gpos[e[0]].x),ay=sy(gpos[e[0]].y),bx=sx(gpos[e[1]].x),by=sy(gpos[e[1]].y);
  const fj=gjs[e[0]]&&gjs[e[1]],fd=gdr[e[0]]&&gdr[e[1]];
  ctx.strokeStyle=fj?"#b8860b":(i===gedge?"#334155":"#cbd5e1");ctx.lineWidth=fj?3.5:(i===gedge?2:1);
  ctx.beginPath();ctx.moveTo(ax,ay);ctx.lineTo(bx,by);ctx.stroke();
  if(fd){ctx.save();ctx.strokeStyle="#0f766e";ctx.lineWidth=fj?1.5:3.5;ctx.setLineDash([6,4]);
   ctx.beginPath();ctx.moveTo(ax,ay);ctx.lineTo(bx,by);ctx.stroke();ctx.restore();}}
 ctx.font="12px sans-serif";ctx.fillStyle="#475569";ctx.textAlign="center";
 const showAll=gedges.length<=25;
 for(let i=0;i<gedges.length;i++){if(!showAll&&i!==gedge)continue;const e=gedges[i];
  ctx.fillText(e[2],(sx(gpos[e[0]].x)+sx(gpos[e[1]].x))/2,(sy(gpos[e[0]].y)+sy(gpos[e[1]].y))/2);}
 ctx.textAlign="left";
 for(let i=0;i<gpos.length;i++){const nd=gcur.nodes[i],px=sx(gpos[i].x),py=sy(gpos[i].y);
  const r=nd.cls==="root"?7:5.5;
  ctx.beginPath();
  if(nd.cls==="root"){ctx.rect(px-r,py-r,2*r,2*r);}
  else if(nd.cls==="hop2"){ctx.moveTo(px,py-r-1);ctx.lineTo(px+r+1,py+r);ctx.lineTo(px-r-1,py+r);ctx.closePath();}
  else{ctx.arc(px,py,r,0,6.2832);}
  ctx.fillStyle=GCOLOR[nd.cls]||"#6b7280";ctx.fill();
  if(nd.judge){ctx.beginPath();ctx.arc(px,py,r+3.5,0,6.2832);
   ctx.strokeStyle="#d4af37";ctx.lineWidth=2.5;ctx.stroke();}
  ctx.fillStyle="#0f172a";ctx.font="12px sans-serif";
  if(gdr[i]){ctx.save();ctx.beginPath();ctx.arc(px,py,r+7,0,6.2832);ctx.strokeStyle="#0f766e";
   ctx.lineWidth=2;ctx.setLineDash([3,2]);ctx.stroke();ctx.restore();}
  if(nd.cls!=="hop2"||gv.s>=1.5||nd.judge||nd.inspan||gdr[i])ctx.fillText(trunc(nd.label),px+r+3,py+4);
  if(nd.inspan){ctx.beginPath();ctx.arc(px+r*0.8,py-r*0.8,4,0,6.2832);
   ctx.fillStyle="#d4af37";ctx.fill();}}
 drawCaps();}
function truncEv(s){return s.length>90?s.slice(0,89)+"…":s;}
function wrapTxt(t,maxW){const words=t.split(" ");const lines=[];let cur="";
 for(const w of words){const cand=cur?cur+" "+w:w;
  if(ctx.measureText(cand).width>maxW&&cur){lines.push(cur);cur=w;}else cur=cand;}
 if(cur)lines.push(cur);
 if(lines.length>2){lines.length=2;lines[1]=lines[1].slice(0,40)+"…";}
 return lines;}
function drawCaps(){
 if(!gcur||!gcur.nodes)return;
 const caps=[];
 for(let i=0;i<gcur.nodes.length&&caps.length<4;i++)if(gcur.nodes[i].ev)caps.push(i);
 let slot=0;
 for(const i of caps)capBox(gpos[i],truncEv(gcur.nodes[i].ev),slot++,"#d4af37","#fdf6e3");
 const r=EGOHOST.overlay||{};
 if(r.lab_ev){const a=gcur.nodes.findIndex(n=>n.cls==="root"&&!n.judge);
  if(a>=0)capBox(gpos[a],"내 라벨 근거: "+truncEv(r.lab_ev),slot,"#16a34a","#f0fdf4");}}
function capBox(p,txt,slot,border,bg){
 const x=Math.min(sx(p.x)+10,gcv.width-160),y=sy(p.y)+12+slot*46;
 if(y>gcv.height-22)return;
 ctx.font="12px monospace";const maxW=gcv.width-x-10;
 const lines=wrapTxt(txt,maxW-12);const bh=lines.length*14+8;
 ctx.fillStyle=bg;ctx.fillRect(x,y,maxW,bh);
 ctx.strokeStyle=border;ctx.lineWidth=1.5;ctx.strokeRect(x,y,maxW,bh);
 ctx.fillStyle="#1f2937";
 lines.forEach((ln,k)=>ctx.fillText(ln,x+6,y+13+k*14));}
function copyText(s,btn){const ok=()=>{btn.textContent="복사됨";};
 const fb=()=>{const ta=document.createElement("textarea");ta.value=s;
  ta.style.position="fixed";ta.style.opacity="0";document.body.appendChild(ta);
  ta.select();document.execCommand("copy");ta.remove();ok();};
 if(navigator.clipboard&&navigator.clipboard.writeText){
  navigator.clipboard.writeText(s).then(ok,fb);}else{fb();}}
function evPos(e){const r=gcv.getBoundingClientRect();return[e.clientX-r.left,e.clientY-r.top];}
function pick(mx,my){for(let i=gpos.length-1;i>=0;i--){
 const dx=sx(gpos[i].x)-mx,dy=sy(gpos[i].y)-my;
 if(dx*dx+dy*dy<=100)return i;}return -1;}
function segDist(mx,my,ax,ay,bx,by){const dx=bx-ax,dy=by-ay;
 const L=dx*dx+dy*dy;if(L<=0)return Math.hypot(mx-ax,my-ay);
 let t=((mx-ax)*dx+(my-ay)*dy)/L;if(t<0)t=0;if(t>1)t=1;
 return Math.hypot(mx-ax-t*dx,my-ay-t*dy);}
function pickEdge(mx,my){if(gedges.length<=25)return -1;
 let best=-1,bd=7;for(let i=0;i<gedges.length;i++){const e=gedges[i];
  const d=segDist(mx,my,sx(gpos[e[0]].x),sy(gpos[e[0]].y),sx(gpos[e[1]].x),sy(gpos[e[1]].y));
  if(d<bd){bd=d;best=i;}}return best;}
function tipFor(i,p){const nd=gcur.nodes[i];
 const parts=[nd.label];
 if(nd.ev)parts.push(truncEv(nd.ev));
 if(nd.inspan)parts.push("in-span: 인용문에 이름 등장");
 if(gdr[i])parts.push("초안 span에 이름 등장 (관계 보증 아님)");
 for(const t of nd.tips)parts.push("· "+t);
 gtip.textContent=parts.join("\\n");gtip.style.display="block";
 gtip.style.left=Math.min(p[0]+14,Math.max(0,gcv.width-360))+"px";
 gtip.style.top=Math.min(p[1]+14,Math.max(0,gcv.height-140))+"px";}
function showPanel(i){
 const nd=gcur.nodes[i];const r=EGOHOST.overlay||{};
 gpanel.replaceChildren();
 const h=document.createElement("b");h.textContent=loc(nd.id)+" — "+nd.label;
 gpanel.appendChild(h);
 const sub=document.createElement("div");sub.className="pnote";
 sub.textContent="로컬명 재구성 — 원문 span 인용은 텍스트 탭에서";
 gpanel.appendChild(sub);
 if(nd.ev){const d=document.createElement("div");d.className="pev";
  d.textContent="judge 인용: "+nd.ev;gpanel.appendChild(d);
  const b=document.createElement("button");b.textContent="인용 복사";
  b.onclick=()=>copyText(nd.ev,b);gpanel.appendChild(b);}
 if(gdr[i]){const d=document.createElement("div");d.className="pdraft";
  d.textContent="초안 span에 이름 등장 — 관계 보증 아님";gpanel.appendChild(d);}
 if(nd.inspan){const d=document.createElement("div");d.className="pinspan";
  d.textContent="in-span: 인용문에 이름 등장 — 관계 보증 아님";gpanel.appendChild(d);}
 const lines=[];
 for(const e of gcur.edges)if(e.s===nd.id)lines.push(loc(e.s)+"  "+e.p+"  "+loc(e.o));
 for(const t of nd.tips){const k=t.indexOf(" ");
  lines.push(loc(nd.id)+"  "+t.slice(0,k)+'  "'+t.slice(k+1)+'"');}
 const pre=document.createElement("pre");
 pre.textContent=lines.join("\\n")||"(outgoing 트리플 없음)";gpanel.appendChild(pre);
 if(r.lab_ev){const d=document.createElement("div");d.className="plab";
  d.textContent="내 라벨 근거: "+r.lab_ev;gpanel.appendChild(d);
  const b=document.createElement("button");b.textContent="근거 복사";
  b.onclick=()=>copyText(r.lab_ev,b);gpanel.appendChild(b);}
 if(r.badge==="0"&&r.lab_note){const d=document.createElement("div");d.className="pnote";
  d.textContent="행 노트: "+r.lab_note;gpanel.appendChild(d);}
 gpanel.style.display="block";}
gcv.addEventListener("mousedown",e=>{if(!gcur||!gcur.nodes)return;
 const p=evPos(e);gdrag=pick(p[0],p[1]);gpan=gdrag<0;
 gmoved=0;gpx=e.clientX;gpy=e.clientY;gcv.style.cursor="grabbing";});
window.addEventListener("mousemove",e=>{if(!EGOHOST.visible)return;
 if(gpan){gtip.style.display="none";gv.x+=e.clientX-gpx;gv.y+=e.clientY-gpy;
  gmoved+=Math.abs(e.clientX-gpx)+Math.abs(e.clientY-gpy);
  gpx=e.clientX;gpy=e.clientY;egoDraw();return;}
 if(gdrag>=0){gtip.style.display="none";const p=evPos(e);
  gpos[gdrag].x=(p[0]-gv.x)/gv.s;gpos[gdrag].y=(p[1]-gv.y)/gv.s;
  gmoved+=10;egoDraw();return;}
 const p=evPos(e);const ni=(gcur&&gcur.nodes)?pick(p[0],p[1]):-1;
 if(ni>=0){tipFor(ni,p);}else{gtip.style.display="none";}
 const ne=pickEdge(p[0],p[1]);
 if(ne!==gedge){gedge=ne;egoDraw();}});
window.addEventListener("mouseup",e=>{
 if(EGOHOST.visible&&gmoved<4){const p=evPos(e);const i=pick(p[0],p[1]);
  if(i>=0)showPanel(i);else gpanel.style.display="none";}
 gdrag=-1;gpan=false;if(gcur&&gcur.nodes)gcv.style.cursor="grab";});
gcv.addEventListener("wheel",e=>{if(!gcur||!gcur.nodes)return;e.preventDefault();
 const p=evPos(e);const k=Math.exp(-e.deltaY*0.0015);
 const ns=Math.min(6,Math.max(0.2,gv.s*k));
 gv.x=p[0]-(p[0]-gv.x)*(ns/gv.s);gv.y=p[1]-(p[1]-gv.y)*(ns/gv.s);gv.s=ns;egoDraw();},{passive:false});
function zoomBy(k){if(!gcur||!gcur.nodes)return;const cx=gcv.width/2,cy=gcv.height/2;
 const ns=Math.min(6,Math.max(0.2,gv.s*k));
 gv.x=cx-(cx-gv.x)*(ns/gv.s);gv.y=cy-(cy-gv.y)*(ns/gv.s);gv.s=ns;egoDraw();}
[["gzin",()=>zoomBy(1.25)],["gzout",()=>zoomBy(0.8)],["gzreset",()=>{gv={s:1,x:0,y:0};if(gcur&&gcur.nodes)egoDraw();}]]
 .forEach(z=>{const b=document.getElementById(z[0]);if(b)b.addEventListener("click",z[1]);});
window.addEventListener("resize",()=>{if(EGOHOST.visible&&gcur){fitCanvas();egoDraw();}});"""
