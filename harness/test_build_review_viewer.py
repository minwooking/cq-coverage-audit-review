"""Tests for the read-only review viewer generator.

ALL DATA HERE IS SYNTHETIC scaffolding material. Generation runs against tiny
synthetic sheets in tmp_path; nothing is written outside tmp_path.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_review_viewer as brv  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
import label_assist as la  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
from test_label_assist import make_views  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]

DATA_RE = re.compile(r'<script id="data" type="application/json">(.*?)</script>', re.S)


def make_tiny_sheet(tmp_path: Path) -> Path:
    rows = [brv.EXPECTED_HEADER]
    rows.append(["x:A:C1", "CQ1", "CQ1", "concept_definition", "A", "CQ one question?",
                 "['alpha anchor', 'beta']", "/stale", "", "", "", ""])
    rows.append(["y:A:C2", "CQ2", "CQ2", "taxonomy", "A", "CQ two question?",
                 "unparseable list [", "/stale", "", "", "", ""])
    rows.append(["z:B:C3", "CQ3", "CQ3", "slots_facets", "B", "CQ three question?",
                 "", "/stale", "", "", "", ""])
    path = tmp_path / "tiny.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    return path


def make_working(tmp_path: Path, sheet: Path, labels: dict[int, str],
                 verbatims: dict[int, str] | None = None,
                 notes: dict[int, str] | None = None) -> Path:
    with open(sheet, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    for idx, value in labels.items():
        rows[idx][9] = value
    for idx, value in (verbatims or {}).items():
        rows[idx][8] = value
    for idx, value in (notes or {}).items():
        rows[idx][11] = value
    path = tmp_path / "working.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    return path


def generate(tmp_path: Path, *extra: str) -> tuple[Path, dict[str, Any]]:
    out = tmp_path / "dist" / "viewer.html"
    argv = ["--sheet", str(make_tiny_sheet(tmp_path)), "--views", str(make_views(tmp_path)),
            "--out", str(out), *extra]
    brv.main(argv)
    html_text = out.read_text(encoding="utf-8")
    match = DATA_RE.search(html_text)
    assert match is not None, "embedded data script block not found"
    return out, json.loads(match.group(1))


def test_generate_embeds_all_rows_when_working_given(tmp_path: Path) -> None:
    working = make_working(tmp_path, make_tiny_sheet(tmp_path), {1: "1", 2: "0"})
    out, data = generate(tmp_path, "--working", str(working))
    assert out.is_file()
    html_text = out.read_text(encoding="utf-8")
    for cell_id in ("x:A:C1", "y:A:C2", "z:B:C3"):
        assert cell_id in html_text
    assert len(data["rows"]) == 3 and data["total"] == 3
    assert data["labeled"] == 2
    assert [r["badge"] for r in data["rows"]] == ["1", "0", None]
    assert [r["idx"] for r in data["rows"]] == [1, 2, 3]
    assert data["views"]["A"].startswith("VIEW A") and data["views"]["B"].startswith("VIEW B")
    assert data["rows"][2]["variant"] == "B"


def test_badges_come_from_sheet_when_no_working(tmp_path: Path) -> None:
    _, data = generate(tmp_path)
    assert data["labeled"] == 0
    assert all(r["badge"] is None for r in data["rows"])


def test_judge_fragments_parsed_when_list_repr(tmp_path: Path) -> None:
    _, data = generate(tmp_path)
    rows = data["rows"]
    assert rows[0]["frags"] == ["alpha anchor", "beta"]
    assert rows[1]["frags"] == ["unparseable list ["]
    assert rows[2]["frags"] == []


def test_repo_out_rejected_reuses_label_assist_check() -> None:
    assert brv.check_out_path is la.check_out_path  # same pure check, no reimplementation


def test_repo_out_path_exits_nonzero(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as caught:
        brv.main(["--sheet", str(make_tiny_sheet(tmp_path)), "--views", str(make_views(tmp_path)),
                  "--out", str(tmp_path / ".claude" / "worktrees" / "wt" / "viewer.html")])
    assert caught.value.code == 1


def test_view_sha_mismatch_exits_nonzero(tmp_path: Path) -> None:
    views = make_views(tmp_path)
    (views / "rendered_view_A.txt").write_bytes(b"TAMPERED")
    with pytest.raises(SystemExit) as caught:
        brv.main(["--sheet", str(make_tiny_sheet(tmp_path)), "--views", str(views),
                  "--out", str(tmp_path / "v.html")])
    assert caught.value.code == 1
    assert not (tmp_path / "v.html").exists()


# ---------------------------------------------------------------------------
# ego-graph tests. Synthetic TTLs for four variants; A and B share g:Widget.
# graph_A.ttl: Widget -hasPart-> Part1 -> Part2 -> Part3 (Part3 is 3 hops away),
# Widget -note-> literal, Gadget -refers-> Other, Hub with 130 Cap_i children
# each with a Grand_i child (node-cap pruning), plus 30 Filler_i nodes so the
# per-variant 15% generic-token rule never hits the matched tokens by accident.
# graph_D.ttl: 10 "alpha concept" nodes + BetaAnchor — 'alpha' is generic there
# (>15% of labels) and must not open roots. graph_E.ttl: 30 "squeezed item"
# nodes among 220 fillers (squeezed = 12%, not generic) — 30 label matches must
# be trimmed to the 25-root cap.
# ---------------------------------------------------------------------------

G_NS = ("@prefix g: <http://test.org/g#> .\n"
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n")

TTL_A_BODY = """
g:Widget rdfs:label "Widget" .
g:Widget g:hasPart g:Part1 .
g:Part1 g:hasPart g:Part2 .
g:Part2 g:hasPart g:Part3 .
g:Widget g:note "a widget note" .
g:Gadget rdfs:label "Gadget" .
g:Gadget g:refers g:Other .
g:Hub skos:prefLabel "Central Hub" .
"""

TTL_B_BODY = """
g:Widget skos:prefLabel "Widget kind anchor" .
g:Widget g:hasKind g:WKind .
g:KindWidget rdfs:label "Kind widget" .
"""

FILLER30 = "".join(f'g:Filler{i:02d} rdfs:label "filler body {i}" .\n' for i in range(1, 31))
TTL_D_BODY = ("".join(f'g:A{i} rdfs:label "alpha concept {i}" .\n' for i in range(10))
              + 'g:BetaAnchor rdfs:label "beta anchor" .\n')
TTL_E_BODY = ("".join(f'g:Sq{i:02d} rdfs:label "squeezed item {i}" .\n' for i in range(1, 31))
              + "".join(f'g:Body{i:03d} rdfs:label "filler body {i}" .\n' for i in range(1, 221)))

G = "http://test.org/g#"


def make_ttl_variants(tmp_path: Path) -> Path:
    root = tmp_path / "variants"
    for v in "ABDE":
        (root / v).mkdir(parents=True)
    cap = "".join(f"g:Hub g:hasPart g:Cap_{i:03d} .\n"
                  f"g:Cap_{i:03d} g:hasPart g:Grand_{i:03d} .\n"
                  for i in range(1, 131))
    (root / "A" / "graph_A.ttl").write_text(G_NS + TTL_A_BODY + cap + FILLER30, encoding="utf-8")
    (root / "B" / "graph_B.ttl").write_text(G_NS + TTL_B_BODY + FILLER30, encoding="utf-8")
    (root / "D" / "graph_D.ttl").write_text(G_NS + TTL_D_BODY, encoding="utf-8")
    (root / "E" / "graph_E.ttl").write_text(G_NS + TTL_E_BODY, encoding="utf-8")
    return root


def graph_rows() -> list[list[str]]:
    stale = "/stale"
    return [
        ["g1:A:C1", "CQ1", "CQ1", "concept_definition", "A", "What is a widget?",
         f"['{G}Gadget | widget gadget rendered', '{G}missing | ghost']",
         stale, "", "", "", ""],
        ["g2:B:C2", "CQ2", "CQ2", "taxonomy", "B", "Which widget kind?", "", stale,
         "", "", "", ""],
        ["g3:A:C3", "CQ3", "CQ3", "relations", "A", "zzz qqq nowhere?",
         f"['{G}missing | nope']", stale, "", "", "", ""],
        ["g4:A:C4", "CQ4", "CQ4", "taxonomy", "A", "What does the central hub connect?",
         "", stale, "", "", "", ""],
        ["g5:B:C5", "CQ5", "CQ5", "instances", "B", "What is a widget?", "", stale,
         "", "", "", ""],
        ["g7:D:C7", "CQ7", "CQ7", "taxonomy", "D", "What is alpha beta?", "", stale,
         "", "", "", ""],
        ["g8:E:C8", "CQ8", "CQ8", "relations", "E", "What is squeezed thing?", "", stale,
         "", "", "", ""],
    ]


def write_graph_sheet(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([brv.EXPECTED_HEADER, *graph_rows()])
    return path


def run_graph_build(tmp_path: Path, nested: bool = False, *extra: str) -> dict[str, Any]:
    """Run the generator with TTL graphs available; return the parsed payload.

    nested=False passes --ttl-dir explicitly; nested=True reproduces the real
    layout (sheet at …/real_run/annotation_pending/, variants sibling of
    real_run) so the default ../../variants resolution is exercised.
    """
    views = make_views(tmp_path)
    make_ttl_variants(tmp_path)
    if nested:
        sheet = write_graph_sheet(tmp_path / "real_run" / "annotation_pending" / "g.csv")
        argv = ["--sheet", str(sheet), "--views", str(views), "--out", str(tmp_path / "g.html")]
    else:
        sheet = write_graph_sheet(tmp_path / "graph_sheet.csv")
        argv = ["--sheet", str(sheet), "--views", str(views), "--out", str(tmp_path / "g.html"),
                "--ttl-dir", str(tmp_path / "variants")]
    brv.main([*argv, *extra])
    match = DATA_RE.search((tmp_path / "g.html").read_text(encoding="utf-8"))
    assert match is not None
    return json.loads(match.group(1))


def test_ego_roots_found_by_cq_token_match(tmp_path: Path) -> None:
    data = run_graph_build(tmp_path)
    g = data["rows"][0]["graph"]
    by = {n["id"]: n for n in g["nodes"]}
    assert f"{G}Widget" in by, "CQ token 'widget' must open an ego root"
    assert by[f"{G}Widget"]["cls"] == "root"
    assert by[f"{G}Part1"]["cls"] == "hop1"
    assert by[f"{G}Part2"]["cls"] == "hop2"
    assert {"s": f"{G}Widget", "p": "hasPart", "o": f"{G}Part1"} in g["edges"]
    assert any(t.startswith("note") for t in by[f"{G}Widget"]["tips"]), \
        "literal object must attach as tooltip string"


def test_judge_uri_node_flagged(tmp_path: Path) -> None:
    data = run_graph_build(tmp_path)
    g = data["rows"][0]["graph"]
    by = {n["id"]: n for n in g["nodes"]}
    assert f"{G}Gadget" in by, "judge-quoted URI must become a root even un-matched by CQ"
    assert by[f"{G}Gadget"]["judge"] is True
    assert by[f"{G}Widget"]["judge"] is False
    assert f"{G}missing" not in by, "judge URI absent from graph must be dropped"


def test_depth_two_cap_excludes_hop3(tmp_path: Path) -> None:
    data = run_graph_build(tmp_path)
    ids = {n["id"] for n in data["rows"][0]["graph"]["nodes"]}
    assert f"{G}Part2" in ids
    assert f"{G}Part3" not in ids, "3rd-hop node must be excluded"


def test_node_cap_respected_prunes_farthest_first(tmp_path: Path) -> None:
    data = run_graph_build(tmp_path)
    g = data["rows"][3]["graph"]
    ids = {n["id"] for n in g["nodes"]}
    assert 119 <= len(g["nodes"]) <= 120, f"261 reachable nodes must be capped: {len(g['nodes'])}"
    assert not any(i.startswith(f"{G}Grand_") for i in ids), \
        "hop2 must be pruned before hop1 when trimming"
    assert f"{G}Hub" in ids


def test_empty_roots_gives_info_placeholder(tmp_path: Path) -> None:
    data = run_graph_build(tmp_path)
    assert data["rows"][2]["graph"] == {"info": "roots 없음"}


def test_graph_field_per_row_parses_and_shares_concept(tmp_path: Path) -> None:
    data = run_graph_build(tmp_path)
    assert all("graph" in r for r in data["rows"])
    b = data["rows"][1]["graph"]
    by = {n["id"]: n for n in b["nodes"]}
    assert f"{G}Widget" in by and f"{G}WKind" in by, \
        "shared concept must resolve in variant B too"
    assert by[f"{G}Widget"]["cls"] == "root" and by[f"{G}WKind"]["cls"] == "root"
    assert {"s": f"{G}Widget", "p": "hasKind", "o": f"{G}WKind"} in b["edges"]


def test_matched_roots_ranked_exact_local_before_label_tier(tmp_path: Path) -> None:
    data = run_graph_build(tmp_path)
    g = data["rows"][1]["graph"]
    roots = [n["id"] for n in g["nodes"] if n["cls"] == "root"]
    assert roots == [f"{G}KindWidget", f"{G}WKind", f"{G}Widget"], \
        "exact local-word matches (by token count, then IRI) precede label-only matches"


def test_generic_tokens_dropped_from_root_matching(tmp_path: Path) -> None:
    data = run_graph_build(tmp_path)
    ids = {n["id"] for n in data["rows"][5]["graph"]["nodes"]}
    assert f"{G}BetaAnchor" in ids
    assert f"{G}A0" not in ids, "'alpha' sits in >15% of variant D labels and must not open roots"


def test_roots_capped_at_25(tmp_path: Path) -> None:
    data = run_graph_build(tmp_path)
    g = data["rows"][6]["graph"]
    roots = [n["id"] for n in g["nodes"] if n["cls"] == "root"]
    assert len(roots) == 25 == len(g["nodes"]), \
        "30 label matches (12% share, non-generic) must trim to the 25-root cap, IRI order"


def test_judge_evidence_text_attached_to_node(tmp_path: Path) -> None:
    data = run_graph_build(tmp_path)
    by = {n["id"]: n for n in data["rows"][0]["graph"]["nodes"]}
    assert by[f"{G}Gadget"]["ev"] == "widget gadget rendered"
    assert "ev" not in by[f"{G}Widget"]


def test_inspan_badge_for_nodes_named_in_evidence(tmp_path: Path) -> None:
    data = run_graph_build(tmp_path)
    by = {n["id"]: n for n in data["rows"][0]["graph"]["nodes"]}
    assert by[f"{G}Widget"].get("inspan") is True, \
        "local name 'Widget' appears in the judge evidence text"
    assert not by[f"{G}Gadget"].get("inspan"), "the judge node itself is never in-span"


def test_human_label_overlay_and_note_from_working(tmp_path: Path) -> None:
    sheet = write_graph_sheet(tmp_path / "gs.csv")
    working = make_working(tmp_path, sheet, {1: "1", 2: "0"},
                           verbatims={1: "widget basis span"}, notes={2: "bad grounding"})
    out = tmp_path / "w.html"
    brv.main(["--sheet", str(sheet), "--views", str(make_views(tmp_path)), "--out", str(out),
              "--ttl-dir", str(make_ttl_variants(tmp_path)), "--working", str(working)])
    data = json.loads(DATA_RE.search(out.read_text(encoding="utf-8")).group(1))
    assert data["rows"][0]["lab_ev"] == "widget basis span"
    assert data["rows"][1]["lab_note"] == "bad grounding"
    assert "lab_ev" not in data["rows"][2]
    assert data["labeled"] == 2


def test_caption_and_overlay_markup_emitted(tmp_path: Path) -> None:
    run_graph_build(tmp_path)
    html_text = (tmp_path / "g.html").read_text(encoding="utf-8")
    for marker in ("gtip", "plab", "pinspan", 'gpanel.style.display="block"'):
        assert marker in html_text


def test_default_ttl_dir_resolved_from_sheet_layout(tmp_path: Path) -> None:
    data = run_graph_build(tmp_path, nested=True)
    assert "nodes" in data["rows"][0]["graph"], \
        "../../variants from …/real_run/annotation_pending must be found"


def test_missing_variant_ttl_exits_nonzero(tmp_path: Path) -> None:
    rows = graph_rows()
    rows.append(["g6:F:C6", "CQ6", "CQ6", "taxonomy", "F", "What is a gadget?", "",
                 "/stale", "", "", "", ""])
    sheet = tmp_path / "with_f.csv"
    with open(sheet, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([brv.EXPECTED_HEADER, *rows])
    with pytest.raises(SystemExit) as caught:
        brv.main(["--sheet", str(sheet), "--views", str(make_views(tmp_path)),
                  "--out", str(tmp_path / "f.html"),
                  "--ttl-dir", str(make_ttl_variants(tmp_path))])
    assert caught.value.code == 1
    assert not (tmp_path / "f.html").exists()


def test_no_graph_field_when_ttl_dir_absent(tmp_path: Path) -> None:
    _, data = generate(tmp_path)
    assert all("graph" not in r for r in data["rows"])
