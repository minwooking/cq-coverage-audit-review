"""Tests for the human-labeling assistant.

ALL DATA HERE IS SYNTHETIC scaffolding material; none of it is a study label.
No long-lived ports: HTTP tests bind ephemeral 127.0.0.1:0 and close in the
same test. Validation logic is exercised directly on Store.save where possible.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager
from typing import Any
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
# harness test convention (see test_analyze_holdout.py): sibling-module import via
# sys.path; pyright cannot model the path hack, so the rule is scoped to this line.
import label_assist as la  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]

HEADER = ["cell_id", "cq_id", "cluster_id", "category", "variant", "cq_text",
          "judge_evidence_span", "rendered_view_path", "evidence_span_verbatim",
          "A", "rater_L1", "note"]


def make_views(tmp_path: Path) -> Path:
    views = tmp_path / "views"
    views.mkdir(parents=True, exist_ok=True)
    lines = []
    for v in "ABCDEF":
        name = f"rendered_view_{v}.txt"
        (views / name).write_bytes(
            f"VIEW {v}\nbrick:Zone — definition anchor for variant {v}\nline3\n".encode("utf-8"))
        digest = hashlib.sha256((views / name).read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}")
    (views / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return views


def make_sheet(tmp_path: Path, n: int = 5) -> Path:
    rows = [HEADER]
    for i in range(1, n + 1):
        variant = "ABCDEF"[(i - 1) % 6]
        span = "multi,line\nembedded-newline \"quote\", comma" if i == 2 else ""
        rows.append([f"cat:{variant}:CQB{i:02d}", f"CQB{i:02d}", f"CQB{i:02d}",
                     "concept_definition", variant, f"What is thing {i}?", span,
                     "/abs/stale/rendered_view.txt", "", "", "", ""])
    path = tmp_path / "sheet.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    return path


def make_store(tmp_path: Path, n: int = 5) -> tuple[la.Store, Path, Path]:
    sheet, views = make_sheet(tmp_path, n), make_views(tmp_path)
    out = tmp_path / "labels" / "working.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    return la.Store(sheet, out, la.verify_views(views)), sheet, out


def payload(idx: int, cell_id: str, a: int, span: str = "", rater: str = "",
            note: str | None = None, **extra: object) -> dict[str, object]:
    base: dict[str, object] = {"row": idx, "cell_id": cell_id, "A": a,
                               "evidence_span_verbatim": span, "rater_L1": rater,
                               "note": "근거 요약" if note is None else note}  # note is required now
    base.update(extra)
    return base


def read_rows(path: Path) -> list[list[str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh))


@contextmanager
def http_server(store: la.Store, ttl_dir: Path | None = None):
    server = la.make_server(store, ("127.0.0.1", 0), ttl_dir)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def http_get(base: str, path: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(base + path, timeout=5) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def http_post(base: str, path: str,
              obj: dict[str, object] | None) -> tuple[int, dict[str, Any]]:
    data = json.dumps(obj).encode("utf-8") if obj is not None else b""
    # a browser always sends a same-origin Origin on a POST; the server now requires it
    req = urllib.request.Request(base + path, data=data, method="POST",
                                 headers={"Content-Type": "application/json", "Origin": base})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read())


# 1. repo-out safety ---------------------------------------------------------
def test_out_inside_repo_rejected(tmp_path: Path) -> None:
    la.check_out_path(tmp_path / "working.csv")  # tmp path allowed
    fake_repo = tmp_path / "fake_repo"
    fake_repo.mkdir()
    with pytest.raises(la.OutInsideRepo):
        la.check_out_path(fake_repo / "labels" / "out.csv", repo_root=fake_repo)
    with pytest.raises(la.OutInsideRepo):
        la.check_out_path(tmp_path / ".claude" / "worktrees" / "wt" / "out.csv")
    # CLI level: same rejection must be a nonzero start refusal.
    sheet, views = make_sheet(tmp_path), make_views(tmp_path)
    rc = la.main(["--sheet", str(sheet), "--views", str(views),
                  "--out", str(tmp_path / ".claude" / "worktrees" / "wt" / "out.csv")])
    assert rc == 1


# 2. view sha256 verification --------------------------------------------------
def test_view_verification_failure_exits_nonzero(tmp_path: Path) -> None:
    views = make_views(tmp_path)
    sheet = make_sheet(tmp_path)
    (views / "rendered_view_C.txt").write_bytes(b"TAMPERED")
    with pytest.raises(la.ViewMismatch):
        la.verify_views(views)
    out = tmp_path / "labels" / "working.csv"
    rc = la.main(["--sheet", str(sheet), "--views", str(views), "--out", str(out)])
    assert rc == 1
    assert not out.exists()  # refused before touching anything


# 3. save roundtrip ------------------------------------------------------------
def test_save_changes_only_label_columns(tmp_path: Path) -> None:
    store, sheet, out = make_store(tmp_path)
    assert out.read_bytes() == sheet.read_bytes()  # exact byte-copy seed
    code, body = store.save(payload(1, "cat:A:CQB01", 1, span="anchor for variant A",
                                    rater="2", note="ok"))
    assert code == 200 and body["ok"] and body["next"] == 2
    original, after = read_rows(sheet), read_rows(out)
    assert after[0] == original[0]  # header
    for idx in (1, 2, 3, 4, 5):
        assert after[idx][:8] == original[idx][:8]  # every non-label column identical
        if idx != 1:
            assert after[idx][8:] == original[idx][8:]  # only row 1's labels moved
    assert after[1][8:] == ["anchor for variant A", "1", "2", "ok"]
    # cell_id mismatch: rejected, file untouched
    before = out.read_bytes()
    with pytest.raises(la.SaveError):
        store.save(payload(3, "wrong:cell:id", 1, span="x"))
    assert out.read_bytes() == before
    # atomic write leaves no stray tmp files; only out + the two sidecars exist
    assert {p.name for p in out.parent.iterdir()} == {
        "working.csv", "working.csv.audit.jsonl", "working.csv.session_log.txt"}


# 4. server-side validation ----------------------------------------------------
def test_server_side_span_and_note_rules(tmp_path: Path) -> None:
    store, _, out = make_store(tmp_path)
    with pytest.raises(la.SaveError):
        store.save(payload(1, "cat:A:CQB01", 1, note=""))  # A=1 without span
    with pytest.raises(la.SaveError):
        store.save(payload(1, "cat:A:CQB01", 0, note=""))  # A=0 without note
    code, _ = store.save(payload(2, "cat:B:CQB02", 0, span="judge claim junk",
                                 note="핵심 관계가 뷰에 없음"))
    assert code == 200
    assert read_rows(out)[2][8:] == ["", "0", "", "핵심 관계가 뷰에 없음"]  # span force-cleared
    with pytest.raises(la.SaveError):
        store.save(payload(1, "cat:A:CQB01", 5, span="x"))  # bad A value


# 5. no per-session cap (removed 2026-10-08 by the labeler's decision) ------------
def test_no_per_session_save_cap(tmp_path: Path) -> None:
    store, _, _ = make_store(tmp_path, n=70)
    for idx in range(1, 71):
        code, _ = store.save(payload(idx, f"cat:{'ABCDEF'[(idx-1) % 6]}:CQB{idx:02d}",
                                     0, note="no support"))
        assert code == 200
    assert store.status()["session_saved"] == 70
    assert store.status()["gated_reason"] is None
    with http_server(store) as base:
        _, page = http_get(base, "/?row=1")
        text = page.decode("utf-8")
        assert "가이드 상한: 세션당 60행" not in text and 'id="psess"' not in text


# 5b. --defer-controls: control rows are neither served nor saved -------------------
def test_defer_controls_hides_and_blocks_control_rows(tmp_path: Path) -> None:
    sheet, views = make_sheet(tmp_path, 6), make_views(tmp_path)
    with open(sheet, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    rows[2][0] = "ablated_control:B:CQB02"
    rows[4][0] = "preserved_control:D:CQB04"
    with open(sheet, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    out = tmp_path / "labels" / "working.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    store = la.Store(sheet, out, la.verify_views(views), defer_prefixes=la.CONTROL_PREFIXES)
    assert store.deferred == frozenset({2, 4})
    assert store.served() == [1, 3, 5, 6]
    assert store.clamp_row(2) == 3 and store.clamp_row(4) == 5 and store.clamp_row(6) == 6
    assert store.nav(1) == (1, 3) and store.nav(3) == (1, 5) and store.nav(6) == (5, 6)
    with pytest.raises(la.SaveError):
        store.save(payload(2, "ablated_control:B:CQB02", 0, note="x"))
    code, body = store.save(payload(1, "cat:A:CQB01", 0, note="x"))
    assert code == 200 and body["next"] == 3  # the deferred row 2 is skipped
    assert store.status()["deferred"] == 2
    with http_server(store) as base:
        _, page = http_get(base, "/?row=3")
        text = page.decode("utf-8")
        assert "<b>2/4</b>" in text  # position counts served rows only
        assert "cell_id <code>" not in text and "ablated_control" not in text.split("<script")[0]
    assert "deferred=2" in Path(str(out) + ".session_log.txt").read_text(encoding="utf-8")


def test_defer_controls_off_by_default(tmp_path: Path) -> None:
    store, _, _ = make_store(tmp_path, n=4)
    assert store.deferred == frozenset() and store.served() == [1, 2, 3, 4]


# 6. 12-hour inter-session gate ---------------------------------------------------
def test_no_12h_gate_right_after_a_session(tmp_path: Path) -> None:
    # The 12h inter-session gap was removed 2026-10-08 (labeler's decision): a session
    # that ended a moment ago must not block saving, and there is no /ack route.
    sheet, views = make_sheet(tmp_path), make_views(tmp_path)
    out = tmp_path / "labels" / "working.csv"
    out.parent.mkdir(parents=True)
    recent = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    Path(str(out) + ".session_log.txt").write_text(
        f"SESSION start=2026-01-01T00:00:00+09:00 pid=1\nSESSION end={recent} pid=1 saved=10\n",
        encoding="utf-8")
    store = la.Store(sheet, out, la.verify_views(views))
    assert store.status()["gated_reason"] is None
    with http_server(store) as base:
        _, page = http_get(base, "/?row=1")
        assert "12시간 규칙 — 저장 차단" not in page.decode("utf-8")
        assert http_post(base, "/ack", None)[0] == 404
        code, body = http_post(base, "/save", payload(1, "cat:A:CQB01", 1,
                                                      span="anchor for variant A"))
        assert code == 200 and body["ok"]


# 7. edit auditing ------------------------------------------------------------------
def test_edit_requires_reason_and_logs(tmp_path: Path) -> None:
    store, _, out = make_store(tmp_path)
    store.save(payload(1, "cat:A:CQB01", 1, span="anchor for variant A"))
    with pytest.raises(la.SaveError):  # silent revision forbidden
        store.save(payload(1, "cat:A:CQB01", 0, note="생각을 바꿈"))
    code, _ = store.save(payload(1, "cat:A:CQB01", 0, note="생각을 바꿈",
                                 edit_reason="재검토: 관계 문구 없음"))
    assert code == 200
    log = Path(str(out) + ".session_log.txt").read_text(encoding="utf-8")
    line = [l for l in log.splitlines() if l.startswith("EDIT ")][0]
    # the free-text reason is JSON-encoded in the log (it can no longer start another record)
    assert re.match(r'^EDIT cat:A:CQB01 1->0 reason="재검토: 관계 문구 없음" ts=\d{4}-\d\d-\d\dT', line)
    assert store.row(1).cells[9] == "0"


# 8. audit record contents -------------------------------------------------------------
def test_audit_entry_fields(tmp_path: Path) -> None:
    store, _, out = make_store(tmp_path)
    store.save(payload(1, "cat:A:CQB01", 1, span="anchor", note="n"))  # no first_opened, first save
    opened = datetime.now(timezone.utc) - timedelta(seconds=90)
    store.save(payload(2, "cat:B:CQB02", 0, note="no support",
                       first_opened=opened.isoformat(timespec="seconds")))
    entries = [json.loads(line) for line in
               Path(str(out) + ".audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(entries) == 2
    first, second = entries
    required = {"ts", "cell_id", "row", "A", "span_chars", "rater_L1",
                "first_opened_ts", "elapsed_s", "session_id"}
    assert required <= set(first) and required <= set(second)
    assert first["elapsed_s"] is None and first["first_opened_ts"] is None  # nothing to compare against
    assert second["elapsed_s"] is not None and 85.0 <= second["elapsed_s"] <= 120.0
    assert second["span_chars"] == 0 and second["A"] == 0 and second["row"] == 2
    store.log_session_end()
    log = Path(str(out) + ".session_log.txt").read_text(encoding="utf-8")
    assert "SESSION end=" in log and "saved=2" in log
    assert "SESSION start=" in log.splitlines()[0]


def test_future_first_opened_reports_unknown_elapsed(tmp_path: Path) -> None:
    store, _, out = make_store(tmp_path)
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    code, _ = store.save(payload(1, "cat:A:CQB01", 1, span="anchor",
                                 first_opened=future.isoformat(timespec="seconds")))
    assert code == 200
    entry = json.loads(Path(str(out) + ".audit.jsonl")
                       .read_text(encoding="utf-8").splitlines()[0])
    assert entry["elapsed_s"] is None
    assert entry["first_opened_ts"] == future.isoformat(timespec="seconds")


# 9. HTTP surface: status / page / export -----------------------------------------------
def test_status_page_and_export(tmp_path: Path) -> None:
    store, _, out = make_store(tmp_path)
    with http_server(store) as base:
        _, raw = http_get(base, "/status")
        status = json.loads(raw)
        assert status["progress"] == {"labeled": 0, "total": 5}
        assert status["gated_reason"] is None
        code, page = http_get(base, "/")  # defaults to first unlabeled row = row 1
        text = page.decode("utf-8")
        assert code == 200 and "What is thing 1?" in text
        assert "참고용 — judge의 인용 주장" in text and "rendered_view_C" not in text
        code, csv_bytes = http_get(base, "/export")
        assert code == 200 and csv_bytes == out.read_bytes()
    # save via HTTP advances the default row
    store.save(payload(1, "cat:A:CQB01", 1, span="anchor for variant A"))
    with http_server(store) as base:
        _, page = http_get(base, "/")
        assert "What is thing 2?" in page.decode("utf-8")


# ---------------------------------------------------------------------------
# redesigned single-screen surface: graph tab / help tab / input bar.
# ALL TTL DATA HERE IS SYNTHETIC scaffolding material.
# ---------------------------------------------------------------------------

TTL_MINI = ("""@prefix g: <http://test.org/g#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
g:Thing rdfs:label "thing" .
g:Thing g:hasPart g:Sub1 .
g:Sub1 g:hasPart g:Sub2 .
g:Filler1 rdfs:label "pad body 1" .
g:Filler2 rdfs:label "pad body 2" .
g:Filler3 rdfs:label "pad body 3" .
g:Filler4 rdfs:label "pad body 4" .
g:Filler5 rdfs:label "pad body 5" .
g:Filler6 rdfs:label "pad body 6" .
""")


def make_ttl_variants_min(ttl_root: Path) -> Path:
    for v in "ABCDEF":
        (ttl_root / v).mkdir(parents=True, exist_ok=True)
        (ttl_root / v / f"graph_{v}.ttl").write_text(TTL_MINI, encoding="utf-8")
    return ttl_root


# 10. /graph serves the ego JSON in a synthetic ttl env
def test_graph_endpoint_serves_ego_json(tmp_path: Path) -> None:
    store, _, _ = make_store(tmp_path)
    ttl = make_ttl_variants_min(tmp_path / "variants")
    with http_server(store, ttl) as base:
        code, raw = http_get(base, "/graph?row=1")
        assert code == 200
        j = json.loads(raw)
        assert j["ok"] and j["info"] is None
        ids = {n["id"] for n in j["graph"]["nodes"]}
        assert "http://test.org/g#Thing" in ids, "CQ token 'thing' must open a root"
        assert "http://test.org/g#Sub1" in ids
        assert {"s": "http://test.org/g#Thing", "p": "hasPart", "o": "http://test.org/g#Sub1"} \
            in j["graph"]["edges"]


# 11. ttl-absent path: info, not error — page and tool stay fully functional
def test_graph_absent_ttl_dir_degrades_to_info(tmp_path: Path) -> None:
    store, _, _ = make_store(tmp_path)
    with http_server(store) as base:  # no ttl_dir at all
        code, raw = http_get(base, "/graph?row=1")
        j = json.loads(raw)
        assert code == 200 and j["ok"] and j["graph"] is None
        assert "TTL 없음" in str(j["info"])
        code2, page = http_get(base, "/")
        assert code2 == 200 and "What is thing 1?" in page.decode("utf-8")


# 12. a TTL load failure (e.g. rdflib missing, corrupt ttl) also degrades
def test_graph_load_failure_degrades(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store, _, _ = make_store(tmp_path)
    ttl = make_ttl_variants_min(tmp_path / "variants")

    def boom(path: Path):
        raise la.gv.TtlLoadError("rdflib를 불러올 수 없습니다: simulated")

    monkeypatch.setattr(la.gv, "load_variant_ttl", boom)
    with http_server(store, ttl) as base:
        _, raw = http_get(base, "/graph?row=1")
        j = json.loads(raw)
        assert j["ok"] and j["graph"] is None and "TTL 로드 실패" in str(j["info"])
    monkeypatch.undo()


# 13. human labels come LIVE from the current out CSV (server advantage)
def test_graph_overlay_reflects_saved_labels_immediately(tmp_path: Path) -> None:
    store, _, _ = make_store(tmp_path)
    ttl = make_ttl_variants_min(tmp_path / "variants")
    with http_server(store, ttl) as base:
        _, raw = http_get(base, "/graph?row=1")
        assert "lab_ev" not in json.loads(raw)["overlay"]  # unlabeled yet
        code, body = http_post(base, "/save", payload(1, "cat:A:CQB01", 1,
                                                      span="saved anchor", rater="2"))
        assert code == 200 and body["ok"]
        _, raw = http_get(base, "/graph?row=1")
        assert json.loads(raw)["overlay"] == {"badge": "1", "lab_ev": "saved anchor"}
        code, _ = http_post(base, "/save", payload(2, "cat:B:CQB02", 0, note="근거 없음"))
        assert code == 200
        _, raw = http_get(base, "/graph?row=2")
        assert json.loads(raw)["overlay"] == {"badge": "0", "lab_note": "근거 없음"}


# 14. the redesigned screen: two-pane input bar + 3 tabs, all in one page
def test_page_contains_input_bar_and_tabs(tmp_path: Path) -> None:
    store, _, _ = make_store(tmp_path)
    with http_server(store) as base:
        _, page = http_get(base, "/")
        text = page.decode("utf-8")
        for marker in ('data-a="1"', "A=1 근거 있음", "A=0 근거 없음", 'data-r="3"',
                      'id="span"', 'id="note"', 'id="submit"', "저장 후 다음 미라벨 행",
                      "rater_L1", ">텍스트<kbd>t</kbd></button>", ">그래프<kbd>g</kbd></button>", ">도움말</button>",
                      "선택을 span으로", "labeled", "session", "그래프 패널 문장은 재구성이라"):
            assert marker in text, f"missing marker: {marker}"
        assert "참고용 — judge의 인용 주장" in text  # judge box semantics unchanged


# 15. 도움말 tab: guide text + the fixed verdict/rater/gate sections
def test_help_tab_embedded_with_guide_and_markers(tmp_path: Path) -> None:
    store, _, _ = make_store(tmp_path)
    with http_server(store) as base:
        _, page = http_get(base, "/")
        text = page.decode("utf-8")
        assert "LABELER_GUIDE.md 전문" in text
        assert "verbatim" in text  # came from the real guide file
        for marker in ("경계", "A=1", "rater_L1 앵커", "60행", "12시간", "~90초",
                       "edit_reason", "audit.jsonl", "G7", "블라인드"):
            assert marker in text, f"missing help marker: {marker}"


# 16. ?tab= restores the requested tab; saving from 그래프 keeps it (auto-advance)
def test_tab_selection_and_save_preserves_graph_tab(tmp_path: Path) -> None:
    store, _, _ = make_store(tmp_path)
    with http_server(store) as base:
        _, page = http_get(base, "/?row=1&tab=graph")
        assert 'let tab="graph"' in page.decode("utf-8")
        _, page = http_get(base, "/?row=1&tab=help")
        assert 'let tab="help"' in page.decode("utf-8")
        _, page = http_get(base, "/?row=1&tab=bogus")
        assert 'let tab="text"' in page.decode("utf-8")  # unknown falls back
        code, body = http_post(base, "/save", payload(1, "cat:A:CQB01", 1, span="anchor"))
        assert code == 200 and body["next"] == 2  # auto-advance contract unchanged


# 17. save-gate regression on the new surface: HTTP 400 paths still reject
def test_http_save_gates_still_reject_on_new_page(tmp_path: Path) -> None:
    store, _, out = make_store(tmp_path)
    with http_server(store) as base:
        code, body = http_post(base, "/save", payload(1, "cat:A:CQB01", 1, note=""))
        assert code == 400 and "span" in body["error"]
        code, body = http_post(base, "/save", payload(1, "cat:A:CQB01", 0, note=""))
        assert code == 400 and "note" in body["error"]
        assert not any(r[9].strip() for r in read_rows(out)[1:])  # nothing half-saved

def test_host_flag_defaults_localhost_and_overrides() -> None:
    # old code (pre --host) raises SystemExit(2) here = RED for 3a3c824
    args = la.build_parser().parse_args(["--sheet", "s.csv", "--views", "v"])
    assert args.host == "127.0.0.1"  # default stays loopback-only
    args = la.build_parser().parse_args(
        ["--sheet", "s.csv", "--views", "v", "--host", "0.0.0.0"])
    assert args.host == "0.0.0.0"  # explicit opt-in for private network


# ---------------------------------------------------------------------------
# AI-DRAFT review mode (study registration AH: AI-drafted, human-revised).
# ALL DRAFT DATA HERE IS SYNTHETIC scaffolding material.
# ---------------------------------------------------------------------------

DRAFT_HEADER = ["cell_id", "A_draft", "rater_L1_draft", "span_draft",
                "note_draft", "model", "generated_at"]


def make_draft(tmp_path: Path, rows: list[list[str]], name: str = "draft_fixture.csv") -> Path:
    path = tmp_path / name
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(DRAFT_HEADER)
        w.writerows(rows)
    return path


def draft_row(cell_id: str, variant: str, a: str = "1", rater: str = "2",
              span: str | None = None, note: str = "",
              model: str = "draftmodel-v1", ts: str = "2026-10-01T09:00:00+09:00") -> list[str]:
    if span is None:
        span = f"anchor for variant {variant}"
    return [cell_id, a, rater, span, note, model, ts]


def make_draft_store(tmp_path: Path, rows: list[list[str]], n: int = 5,
                     name: str = "draft_fixture.csv") -> tuple[la.Store, Path]:
    draft = make_draft(tmp_path, rows, name)
    sheet, views = make_sheet(tmp_path, n), make_views(tmp_path)
    out = tmp_path / "labels" / "working.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    store = la.Store(sheet, out, la.verify_views(views),
                     drafts=la.load_drafts(draft), draft_name=draft.name)
    return store, out


# D1. draft card + prefill render when --draft covers the row; absent rows clean
def test_draft_mode_renders_card_and_prefills_inputs(tmp_path: Path) -> None:
    store, _ = make_draft_store(tmp_path, [draft_row("cat:A:CQB01", "A")], n=3)
    with http_server(store) as base:
        _, page = http_get(base, "/?row=1")
        text = page.decode("utf-8")
        assert "AI 초안 — 확인하거나 수정하세요 (drafted draftmodel-v1 @ 2026-10-01T09:00:00+09:00)" in text
        assert "anchor for variant A</textarea>" in text  # span prefilled
        assert "let a=1, rater=2" in text  # A/rater buttons active from draft
        _, page = http_get(base, "/?row=2")  # row 2 has no draft
        assert "AI 초안" not in page.decode("utf-8")
        assert "let a=null, rater=null" in page.decode("utf-8")


# D2. audit carries draft fields; changed=false on confirm, true on revision
def test_draft_audit_changed_flag_confirm_vs_revision(tmp_path: Path) -> None:
    store, out = make_draft_store(tmp_path, [
        draft_row("cat:A:CQB01", "A", note="초안 요약"),
        draft_row("cat:B:CQB02", "B", a="0", rater="1", span="", note="초안 사유"),
    ])
    # note is required now, so "confirmed as drafted" needs the draft's own note text
    code, _ = store.save(payload(1, "cat:A:CQB01", 1, span="anchor for variant A", rater="2",
                                 note="초안 요약"))
    assert code == 200
    code, _ = store.save(payload(2, "cat:B:CQB02", 1, span="anchor for variant B",
                                 rater="3", note="사람이 판정을 바꿈"))
    assert code == 200
    entries = [json.loads(line) for line in
               Path(str(out) + ".audit.jsonl").read_text(encoding="utf-8").splitlines()]
    first, second = entries
    assert first["draft_A"] == "1" and first["draft_L1"] == "2"
    assert first["changed"] is False
    assert first["draft_model"] == "draftmodel-v1"
    assert first["draft_generated_at"] == "2026-10-01T09:00:00+09:00"
    assert second["draft_A"] == "0" and second["changed"] is True
    # edits get the same draft fields
    code, _ = store.save(payload(1, "cat:A:CQB01", 1, span="anchor for variant A",
                                 rater="3", note="초안 요약", edit_reason="rater 상향"))
    assert code == 200
    third = [json.loads(line) for line in
             Path(str(out) + ".audit.jsonl").read_text(encoding="utf-8").splitlines()][2]
    assert third["changed"] is True and third["draft_A"] == "1"


# D3. draft mode active but the row is missing from the file -> null fields
def test_draft_mode_missing_row_yields_null_draft_fields(tmp_path: Path) -> None:
    store, out = make_draft_store(tmp_path, [draft_row("cat:A:CQB01", "A")])
    code, _ = store.save(payload(2, "cat:B:CQB02", 0, note="초안에 없는 행"))
    assert code == 200
    entry = json.loads(Path(str(out) + ".audit.jsonl")
                       .read_text(encoding="utf-8").splitlines()[0])
    for key in ("draft_A", "draft_L1", "changed", "draft_model", "draft_generated_at"):
        assert key in entry and entry[key] is None


# D4. without --draft the audit line stays exactly the pre-draft format
def test_no_draft_mode_leaves_audit_format_untouched(tmp_path: Path) -> None:
    store, _, out = make_store(tmp_path)
    store.save(payload(1, "cat:A:CQB01", 1, span="anchor for variant A"))
    entry = json.loads(Path(str(out) + ".audit.jsonl")
                       .read_text(encoding="utf-8").splitlines()[0])
    assert not any(k.startswith("draft_") for k in entry)
    assert "changed" not in entry


# D5. every save gate still fires with draft mode active (400s unchanged)
def test_save_gates_still_reject_with_draft_active(tmp_path: Path) -> None:
    store, out = make_draft_store(tmp_path, [draft_row("cat:A:CQB01", "A")])
    with http_server(store) as base:
        code, body = http_post(base, "/save", payload(1, "cat:A:CQB01", 1, note=""))  # empty span
        assert code == 400 and "span" in body["error"]
        code, body = http_post(base, "/save", payload(1, "cat:A:CQB01", 0, note=""))  # no note
        assert code == 400 and "note" in body["error"]
        assert not any(r[9].strip() for r in read_rows(out)[1:])


# D6. session log records the draft file name
def test_session_log_notes_draft_file(tmp_path: Path) -> None:
    store, out = make_draft_store(tmp_path, [draft_row("cat:A:CQB01", "A")],
                                  name="draft_224.csv")
    store.log_session_end()
    log = Path(str(out) + ".session_log.txt").read_text(encoding="utf-8")
    assert "draft=draft_224.csv" in log.splitlines()[0]


# D7. CLI surface: --draft optional; missing file is a startup refusal
def test_draft_cli_flag_and_startup_refusal(tmp_path: Path) -> None:
    args = la.build_parser().parse_args(["--sheet", "s.csv", "--views", "v"])
    assert args.draft is None  # absent => today's behavior
    args = la.build_parser().parse_args(["--sheet", "s.csv", "--views", "v",
                                         "--draft", "d.csv"])
    assert str(args.draft) == "d.csv"
    sheet, views = make_sheet(tmp_path), make_views(tmp_path)
    rc = la.main(["--sheet", str(sheet), "--views", str(views),
                  "--out", str(tmp_path / "labels" / "w.csv"),
                  "--draft", str(tmp_path / "ghost_draft.csv")])
    assert rc == 1  # fail closed: registered draft mode cannot silently run without drafts


# K1. draft-untouched indicator + keyboard shortcuts render; /save payload unchanged
def test_untouched_indicator_and_shortcuts_render(tmp_path: Path) -> None:
    store, _ = make_draft_store(tmp_path, [draft_row("cat:A:CQB01", "A")], n=3)
    with http_server(store) as base:
        _, page = http_get(base, "/?row=1")
        text = page.decode("utf-8")
        assert '"a": 1, "rater": 2, "span": "anchor for variant A"' in text  # D snapshot
        for marker in ("#inbar.untouched", "초안 그대로(미수정)", "초안에서 수정됨",
                       'addEventListener("keydown"', "ev.ctrlKey||ev.metaKey||ev.altKey",
                       'aria-keyshortcuts="1"', 'aria-keyshortcuts="s"', 'aria-keyshortcuts="/"',
                       "<kbd>q</kbd>", "키보드 단축키"):
            assert marker in text, f"missing marker: {marker}"
        # save payload fields untouched: exactly the pre-existing keys, no draft/D field
        body_line = next(ln for ln in text.splitlines() if ln.startswith(" const body={"))
        assert body_line.strip() == ("const body={row:ROW,cell_id:CELL,A:a,"
                                     "evidence_span_verbatim:spanEl.value,rater_L1:rater,"
                                     "note:noteEl.value,first_opened:firstOpened};")
        _, page2 = http_get(base, "/?row=2")  # no draft -> D is null
        assert "const D=null;" in page2.decode("utf-8")


# K2. setTab sets explicit display values (empty string fell back to CSS display:none on help)
def test_settab_uses_explicit_display_values(tmp_path: Path) -> None:
    store, _, _ = make_store(tmp_path)
    with http_server(store) as base:
        _, page = http_get(base, "/?tab=help")
        text = page.decode("utf-8")
        assert 'panels.help.style.display=t==="help"?"block":"none"' in text
        assert 'panels.text.style.display=t==="text"?"block":"none"' in text
        assert 't==="help"?""' not in text


# K3. real browser: help panel visible on ?tab=help, shortcuts work (skipped w/o playwright)
def test_browser_help_visible_and_shortcuts(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    store, _ = make_draft_store(tmp_path, [draft_row("cat:A:CQB01", "A")], n=3)
    with http_server(store) as base, sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as exc:  # no browser binary installed
            pytest.skip(f"chromium unavailable: {exc}")
        page = browser.new_page()
        page.goto(base + "/?row=1&tab=help")
        assert page.is_visible("#tabhelp")
        assert "키보드 단축키" in page.inner_text("#tabhelp")
        page.goto(base + "/?row=1")
        assert page.is_visible("#dchip") and "초안 그대로" in page.inner_text("#dchip")
        page.keyboard.press("0")  # A=0 differs from draft A=1
        assert "초안에서 수정됨" in page.inner_text("#dchip")
        page.keyboard.press("1")
        assert "초안 그대로" in page.inner_text("#dchip")
        page.keyboard.press("e")
        assert page.get_attribute("[data-r='2']", "class") == "on"
        page.keyboard.press("g")
        assert page.is_visible("#tabgraph") and not page.is_visible("#tabtext")
        page.keyboard.press("t")
        page.keyboard.press("/")
        assert page.evaluate("document.activeElement.id") == "q"
        page.keyboard.type("1")  # typing in input must not trigger shortcuts
        assert page.input_value("#q") == "1"
        browser.close()


# U1. P1/P2 render: progress, aria, responsive, wording, invalid-row notice
def test_ux_pass_markup_and_notice(tmp_path: Path) -> None:
    store, _ = make_draft_store(tmp_path, [draft_row("cat:A:CQB01", "A")], n=3)
    with http_server(store) as base:
        _, page = http_get(base, "/?row=1")
        text = page.decode("utf-8")
        for marker in ('name="viewport"', "@media(max-width:900px)", "@media(max-width:767px)",
                       'id="pall"', 'role="tablist"', 'role="tab"', 'role="tabpanel"',
                       'aria-pressed="false"', 'aria-label="뷰 내부 검색"', 'aria-label="note"',
                       'aria-label="evidence_span_verbatim"', 'aria-keyshortcuts="["', "초안 span 위치",
                       "judge 인용 위치", 'id="gzin"', 'role="img"', "<details id=\"glegend\"",
                       "beforeunload", "저장 중…", ":focus-visible", "모든 행 완료"):
            assert marker in text, f"missing marker: {marker}"
        assert text.index('id="cq"') < text.index('id="hdr"')  # CQ is the topmost left element
        assert "alert(" not in text.split("<script>")[1].split("const gwrap")[0]
        assert "큰 소리으로" not in text
        _, bad = http_get(base, "/?row=999")
        assert "요청한 행 999 은(는) 유효하지 않아" in bad.decode("utf-8")
        _, bad2 = http_get(base, "/?row=abc")
        assert "요청한 행 abc " in bad2.decode("utf-8")
        assert "요청한 행" not in text


# U2. browser: search keeps selection + hit count, jump highlights, zoom, mobile layout
def test_browser_ux_pass(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    store, _ = make_draft_store(tmp_path, [draft_row("cat:A:CQB01", "A")], n=3)
    with http_server(store) as base, sync_api.sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception as exc:
            pytest.skip(f"chromium unavailable: {exc}")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        dialogs: list[str] = []
        page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
        page.goto(base + "/?row=1")
        before = page.evaluate("document.getElementById('view').textContent")
        page.fill("#q", "a")
        page.keyboard.press("Enter")
        assert "건" in page.inner_text("#hitcount")
        assert page.evaluate("document.getElementById('view').textContent") == before  # view text untouched
        page.evaluate("""()=>{const v=document.getElementById('view');const r=document.createRange();
            r.setStart(v.firstChild,0);r.setEnd(v.firstChild,3);const s=getSelection();s.removeAllRanges();s.addRange(r);}""")
        sel = page.evaluate("getSelection().toString()")
        page.click("text=검색")  # button click must not drop the selection
        assert page.evaluate("getSelection().toString()") == sel and sel
        page.click("text=judge 인용 위치")
        assert page.evaluate("document.getElementById('view').textContent") == before
        page.keyboard.press("g")
        page.click("#gzin")  # zoom buttons exist and do not throw
        page.keyboard.press("t")
        assert not dialogs  # no alert/confirm used by normal interactions
        page.keyboard.press("]")
        page.wait_for_url("**row=2*")
        page.set_viewport_size({"width": 390, "height": 800})
        assert page.is_visible("#narrow") and page.is_visible("#inbar")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        browser.close()


# N1. note is required for A=1 too; Korean note round-trips through the CSV
def test_note_required_for_every_row_and_korean_roundtrip(tmp_path: Path) -> None:
    store, sheet, out = make_store(tmp_path)
    with pytest.raises(la.SaveError, match="note"):
        store.save(payload(1, "cat:A:CQB01", 1, span="verbatim span", note=""))
    with pytest.raises(la.SaveError, match="note"):
        store.save(payload(1, "cat:A:CQB01", 1, span="verbatim span", note="   "))
    with pytest.raises(la.SaveError, match="note"):
        store.save(payload(1, "cat:A:CQB01", 0, note=""))
    assert read_rows(out)[1][9] == ""  # nothing was written
    code, _ = store.save(payload(1, "cat:A:CQB01", 1, span="verbatim span", rater="3",
                                 note="핵심 개념과 관계가 직접 진술됨 — 한글 note"))
    assert code == 200
    reloaded = la.Store(sheet, out, store.views)
    assert reloaded.rows[1][11] == "핵심 개념과 관계가 직접 진술됨 — 한글 note"
    assert read_rows(out)[1][11] == "핵심 개념과 관계가 직접 진술됨 — 한글 note"


# N2. client mirrors the rule; graph legend/draft highlighting markup present
def test_note_rule_and_graph_legend_markup(tmp_path: Path) -> None:
    store, _ = make_draft_store(tmp_path, [draft_row("cat:A:CQB01", "A")], n=3)
    with http_server(store) as base:
        text = http_get(base, "/?row=1")[1].decode("utf-8")
        assert "note(근거 요약/사유)를 반드시 적어야 합니다 (언어 무관)" in text
        assert "note — 언어 무관 (A=1: 근거 요약 / A=0: 사유)" in text
        assert "한국어로" not in text
        assert 'else if(a===0&&!noteEl.value.trim())' not in text
        for marker in ("draftSpan:", "초안 span에 이름 등장", "굵은 청록 점선", "굵은 금색 실선",
                       "관계 보증 아님", "gdr[e[0]]&&gdr[e[1]]", "초안 span 이름 일치 노드"):
            assert marker in text, f"missing marker: {marker}"


# ---- per-cell external-LLM assist record (domain-gated; PREREG addendum 15 sec.15.6) -----------
def make_iof_store(tmp_path: Path, clock=None, n: int = 5) -> tuple[la.Store, Path, Path]:
    sheet, views = make_sheet(tmp_path, n), make_views(tmp_path)
    out = tmp_path / "labels" / "working.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {"domain": "iof"}
    if clock is not None:
        kwargs["clock"] = clock
    return la.Store(sheet, out, la.verify_views(views), **kwargs), sheet, out


def audit_lines(out: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in Path(str(out) + ".audit.jsonl").read_text(encoding="utf-8").splitlines()]


def test_iof_requires_llm_assist_choice_server_side(tmp_path: Path) -> None:
    store, _, out = make_iof_store(tmp_path)
    with pytest.raises(la.SaveError, match="외부 LLM"):
        store.save(payload(1, "cat:A:CQB01", 0))
    with pytest.raises(la.SaveError, match="external_llm_assist"):
        store.save(payload(1, "cat:A:CQB01", 0, external_llm_assist="maybe"))
    assert read_rows(out)[1][9] == "" and not Path(str(out) + ".audit.jsonl").exists()  # nothing written
    code, _ = store.save(payload(1, "cat:A:CQB01", 0, external_llm_assist="none",
                                 external_llm_tool="ignored when none"))
    assert code == 200
    code, _ = store.save(payload(2, "cat:B:CQB02", 1, span="anchor", external_llm_assist="consulted",
                                 external_llm_tool="  Claude\n chat  "))
    first, second = audit_lines(out)
    assert first["external_llm_assist"] == "none" and first["external_llm_tool"] is None
    assert first["domain"] == "iof"
    assert second["external_llm_assist"] == "consulted" and second["external_llm_tool"] == "Claude chat"
    assert len(read_rows(out)[0]) == 12  # CSV schema unchanged


def test_iof_consulted_without_tool_is_allowed(tmp_path: Path) -> None:
    store, _, out = make_iof_store(tmp_path)
    store.save(payload(1, "cat:A:CQB01", 0, external_llm_assist="consulted"))
    assert audit_lines(out)[0]["external_llm_tool"] is None


def test_iof_client_mirrors_required_choice(tmp_path: Path) -> None:
    store, _, _ = make_iof_store(tmp_path)
    with http_server(store) as base:
        text = http_get(base, "/?row=1")[1].decode("utf-8")
        assert 'data-l="none"' in text and 'data-l="consulted"' in text and 'id="llm_tool"' in text
        assert "외부 LLM 상담 여부(없음/상담함)를 반드시 선택해야 합니다" in text  # refresh() why-line
        assert "body.external_llm_assist=llm" in text and 'id="tmsg"' in text
        assert "G7 기준 20초 미만 (기록만 됨, 저장은 가능)" in text


def test_brick_domain_is_unchanged(tmp_path: Path) -> None:
    store, _, out = make_store(tmp_path)
    assert store.domain == "brick" and not store.llm_assist_required
    # keys are ignored, never required, never stored; a fast save adds no warning
    t = datetime.now(timezone.utc).isoformat(timespec="seconds")
    code, res = store.save(payload(1, "cat:A:CQB01", 1, span="anchor", first_opened=t,
                                   external_llm_assist="consulted", external_llm_tool="x"))
    assert code == 200 and set(res) == {"ok", "next"}
    entry = audit_lines(out)[0]
    assert not ({"external_llm_assist", "external_llm_tool", "domain", "under_g7_min"} & set(entry))
    with http_server(store) as base:
        text = http_get(base, "/?row=2")[1].decode("utf-8")
        for marker in ("data-l=", "llm_tool", "tmsg", "external_llm", "setL("):
            assert marker not in text
    (tmp_path / "x").mkdir()
    with pytest.raises(la.SafetyError):
        la.Store(make_sheet(tmp_path / "x"), tmp_path / "x" / "o.csv", store.views, domain="nope")


def test_iof_under_20s_warns_and_records_but_does_not_block(tmp_path: Path) -> None:
    now = [1_000_000.0]
    store, _, out = make_iof_store(tmp_path, clock=lambda: now[0])

    def fo(secs: float) -> str:
        return datetime.fromtimestamp(now[0] - secs, timezone.utc).isoformat(timespec="seconds")

    code, res = store.save(payload(1, "cat:A:CQB01", 0, first_opened=fo(5), external_llm_assist="none"))
    assert code == 200 and any("20초 미만" in w for w in res["warnings"])
    code, res = store.save(payload(2, "cat:B:CQB02", 0, first_opened=fo(45), external_llm_assist="none"))
    assert code == 200 and "warnings" not in res
    store.last_save_ts = None  # no client timestamp and no prior save: unknown, not "fast"
    code, res = store.save(payload(3, "cat:C:CQB03", 0, external_llm_assist="none"))
    assert code == 200 and "warnings" not in res
    a, b, c = audit_lines(out)
    assert a["elapsed_s"] == 5.0 and a["under_g7_min"] is True
    assert b["elapsed_s"] == 45.0 and b["under_g7_min"] is False
    assert c["elapsed_s"] is None and c["under_g7_min"] is None
    assert read_rows(out)[1][9] == "0"  # the fast save was stored
