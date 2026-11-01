"""Tests for the shared graph_view module (builder extracted from
build_review_viewer). ALL DATA HERE IS SYNTHETIC scaffolding material; nothing
is written outside tmp_path. The viewer's 22 tests remain the integration
proof; these pin the moved helpers directly.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import graph_view as gv  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]

NS = ("@prefix g: <http://test.org/g#> .\n"
      "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n")
G = "http://test.org/g#"


def test_split_fragments_covers_all_column_shapes() -> None:
    assert gv.split_fragments("") == ()
    assert gv.split_fragments("  ") == ()
    assert gv.split_fragments("['a b', 'c']") == ("a b", "c")
    assert gv.split_fragments("['keep', '', ' x ']") == ("keep", " x ")
    assert gv.split_fragments("'single string'") == ("single string",)
    assert gv.split_fragments("unparseable [") == ("unparseable [",)


def test_judge_ev_extracts_uris_and_evidence_text() -> None:
    jev = gv.judge_ev((f"{G}Widget | widget is the base concept",
                      f"{G}NoText", f"{G}Widget | later dup ignored", "no uri here"))
    assert jev.uris == (f"{G}Widget", f"{G}Widget"), \
        "URI without ' | ' has no evidence pipe and plain text never becomes a URI"
    assert jev.text == {f"{G}Widget": "widget is the base concept"}


def test_local_name_and_cq_tokens() -> None:
    assert gv.local_name(f"{G}Widget") == "Widget"
    assert gv.local_name("http://a.org/x:Y") == "Y"
    assert gv.local_name("no-separator") == "no-separator"
    assert gv.cq_tokens("What is a brick:Zone?") == {"brick", "zone"}


def test_resolve_ttl_dir_explicit_missing_raises() -> None:
    with pytest.raises(gv.TtlDirError):
        gv.resolve_ttl_dir(Path("whatever.csv"), Path("/nonexistent/ttl/dir"))


def test_resolve_ttl_dir_default_rule(tmp_path: Path) -> None:
    sheet = tmp_path / "run" / "pending" / "s.csv"
    assert gv.resolve_ttl_dir(sheet, None) is None
    (tmp_path / "variants").mkdir()
    assert gv.resolve_ttl_dir(sheet, None) == tmp_path / "variants"


def test_load_variant_ttl_and_ego_graph_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "graph_A.ttl"
    path.write_text(NS + """
g:Widget rdfs:label "Widget" .
g:Widget g:hasPart g:Part1 .
g:Part1 g:hasPart g:Part2 .
g:Part1 g:hasPart g:Part3 .
g:Widget g:note "a widget note" .
g:FillerA rdfs:label "pad body a" .
g:FillerB rdfs:label "pad body b" .
g:FillerC rdfs:label "pad body c" .
g:FillerD rdfs:label "pad body d" .
g:FillerE rdfs:label "pad body e" .
""", encoding="utf-8")
    vg = gv.load_variant_ttl(path)
    assert f"{G}Widget" in vg.labels
    jev = gv.judge_ev((f"{G}Part1 | widget part1 anchor",))
    eg = gv.ego_graph(vg, gv.cq_tokens("What is a widget?"), jev)
    by = {n["id"]: n for n in eg["nodes"]}
    assert by[f"{G}Widget"]["cls"] == "root"          # cq-token match
    assert by[f"{G}Part1"]["cls"] == "root"           # judge URI is always a root
    assert by[f"{G}Part1"]["judge"] is True
    assert by[f"{G}Part1"]["ev"] == "widget part1 anchor"
    assert any(t.startswith("note") for t in by[f"{G}Widget"]["tips"])
    assert {"s": f"{G}Widget", "p": "hasPart", "o": f"{G}Part1"} in eg["edges"]
    assert eg.get("info") is None


def test_ego_graph_empty_roots_info(tmp_path: Path) -> None:
    ttl = tmp_path / "graph_C.ttl"
    ttl.write_text(NS + 'g:Pad rdfs:label "just pad" .\n', encoding="utf-8")
    vg = gv.load_variant_ttl(ttl)
    assert gv.ego_graph(vg, gv.cq_tokens("zzz qqq"), gv.judge_ev(())) \
        == {"info": "roots 없음"}


def test_load_variant_ttl_corrupt_file_raises(tmp_path: Path) -> None:
    path = tmp_path / "graph_B.ttl"
    path.write_text("this is not turtle ][", encoding="utf-8")
    with pytest.raises(gv.TtlLoadError):
        gv.load_variant_ttl(path)


def test_assets_contain_shared_markup() -> None:
    canvas = gv.graph_canvas_html("배너 <b>escape</b>")
    assert "배너 &lt;b&gt;escape&lt;/b&gt;" in canvas  # banner is escaped
    for idiom in ("gcv", "glegend", "gpanel", "gtip"):
        assert idiom in canvas
    for cls in ("#gwrap", ".plab", ".pinspan"):
        assert cls in gv.GRAPH_CSS
    for hook in ("egoInvalidate", "egoRender", "EGOHOST", 'gpanel.style.display="block"',
                 "plab", "pinspan"):
        assert hook in gv.GRAPH_JS
