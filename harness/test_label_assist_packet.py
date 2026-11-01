"""Tests for label_assist --packet (PREREG sec.12.3 washout / sec.12.4 second annotator)
and the regression guard that the AH-pass behaviour is unchanged without it.

ALL DATA HERE IS SYNTHETIC scaffolding material; none of it is a study label or a judge
value. No long-lived ports: HTTP tests bind an ephemeral 127.0.0.1:0 and close in the same
test. Serving-safety, atomicity and process tests live in test_label_assist_security.py.
"""
from __future__ import annotations

import csv
import hashlib
import html as html_lib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import label_assist as la  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]

HEADER = list(la.SHEET_COLUMNS)
LEGACY_HEADER = list(la.LEGACY_PACKET_COLUMNS)
PACKET_HEADER = list(la.PACKET_COLUMNS)
LS, PS, NEL = chr(0x2028), chr(0x2029), chr(0x85)  # line separators that str.splitlines() honours


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
def make_views(tmp_path: Path) -> Path:
    """The AH-pass view dir: six variant views + SHA256SUMS.txt."""
    views = tmp_path / "views"
    views.mkdir(parents=True, exist_ok=True)
    lines = []
    for v in "ABCDEF":
        name = f"rendered_view_{v}.txt"
        (views / name).write_bytes(
            f"VIEW {v}\nbrick:Zone — definition anchor for variant {v}\nline3\n".encode("utf-8"))
        lines.append(f"{hashlib.sha256((views / name).read_bytes()).hexdigest()}  {name}")
    (views / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return views


def make_sheet(tmp_path: Path, n: int = 5) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
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


def make_store(tmp_path: Path, n: int = 5, drafts=None, draft_name=None, defer=()) -> la.Store:
    sheet, views = make_sheet(tmp_path, n), make_views(tmp_path)
    out = tmp_path / "labels" / "working.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    return la.Store(sheet, out, la.verify_views(views), drafts=drafts,
                    draft_name=draft_name, defer_prefixes=defer)


def payload(idx: int, cell_id: str, a: int, span: str = "", rater: str = "",
            note: str = "근거 요약", **extra: object) -> dict[str, object]:
    base: dict[str, object] = {"row": idx, "cell_id": cell_id, "A": a,
                               "evidence_span_verbatim": span, "rater_L1": rater, "note": note}
    base.update(extra)
    return base


def pp(idx: int, cell_id: str, a: int, span: str = "", rater: str = "1",
       note: str = "근거 요약", **extra: object) -> dict[str, object]:
    """A --packet save: rater_L1 is required there, so it defaults to a value."""
    return payload(idx, cell_id, a, span, rater, note, **extra)


def read_rows(path: Path) -> list[list[str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# packet fixtures: rows carry their own view file ---------------------------------
PACKET_VIEWS = {
    "v_0a1b2c3d.txt": "ORIGINAL VIEW\nSensor is-a Point. The Sensor measures a quantity.\nline3\n",
    "v_9f8e7d6c.txt": "ABLATED VIEW\nline3 only; the supporting line was removed\n",
    "v_55aa55aa.txt": "ANOTHER ORIGINAL VIEW\nMeter is-a Equipment.\n",
}
# (opaque id, shown CQ text, judge span, view ref)
PACKET_ROWS = [
    ("wo-7f3a91c2d4e5b608", "How does Brick characterize its Sensor concept?", "Sensor is-a Point",
     "v_0a1b2c3d.txt"),
    ("wo-0c4d5e6f708192a3", "Which kind of device does the Brick Meter class describe?", "",
     "v_9f8e7d6c.txt"),
    ("wo-b1a2c3d4e5f60718", "How does REC define an Asset?", "Meter is-a Equipment",
     "v_55aa55aa.txt"),
    ("wo-a9b8c7d6e5f40312", "Another paraphrased question?", "Sensor is-a Point",
     "v_0a1b2c3d.txt"),  # same view as row 1: one file, two rows
]


def make_packet_views(root: Path, views: dict[str, str] | None = None) -> Path:
    vdir = root / "packet_views"
    vdir.mkdir(parents=True, exist_ok=True)
    lines = []
    for name, text in (views or PACKET_VIEWS).items():
        (vdir / name).write_bytes(text.encode("utf-8"))
        lines.append(f"{sha(text.encode('utf-8'))}  {name}")
    (vdir / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return vdir


def make_packet_sheet(root: Path, rows=PACKET_ROWS, name: str = "packet_sheet.csv",
                      columns: int = 12) -> Path:
    """Washout-shaped sheet: opaque id in cell_id, cq_id/cluster_id/category/variant blank.
    ``columns`` is 12 (the sheet), 13 (the earlier working layout) or 14 (the current one)."""
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    header = {12: HEADER, 13: LEGACY_HEADER, 14: PACKET_HEADER}[columns]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for opaque, text, span, ref in rows:
            w.writerow([opaque, "", "", "", "", text, span, ref, "", "", "", ""] + [""] * (columns - 12))
    return path


def make_packet_store(root: Path, rows=PACKET_ROWS, **kwargs: Any) -> tuple[la.Store, Path, Path, Path]:
    """A --packet store (the washout: the note is optional); ``require_note=True`` is the second annotator's."""
    sheet = make_packet_sheet(root, rows)
    vdir = make_packet_views(root)
    out = root / "labels" / "working.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    views = la.verify_packet_views(vdir, la.sheet_view_refs(sheet))
    return la.Store(sheet, out, views, packet=True, **kwargs), sheet, vdir, out


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


def http_post(base: str, path: str, obj: dict[str, object] | None) -> tuple[int, dict[str, Any]]:
    data = json.dumps(obj).encode("utf-8") if obj is not None else b""
    # a browser always sends a same-origin Origin on a POST; the server requires it
    req = urllib.request.Request(base + path, data=data, method="POST",
                                 headers={"Content-Type": "application/json", "Origin": base})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read())


def log_lines(out: Path) -> list[str]:
    return Path(str(out) + ".session_log.txt").read_text(encoding="utf-8").splitlines()


def ai_entries(out: Path) -> list[dict[str, Any]]:
    return [json.loads(line[len("AI_USE "):]) for line in log_lines(out) if line.startswith("AI_USE ")]


def audit_entries(out: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in
            Path(str(out) + ".audit.jsonl").read_text(encoding="utf-8").splitlines()]


# ---------------------------------------------------------------------------
# REGRESSION: without --packet the AH pass is byte-for-byte what it was.
# Hashes were taken from the label_assist.py at commit 15c9b50 (before packet mode).
# The only deliberate AH changes since are serving-safety ones (token, Host/Origin, size and time
# limits, atomic writes, log escaping); none of them touches a rendered page or an audit line.
# ---------------------------------------------------------------------------
DRAFT_HEADER = ["cell_id", "A_draft", "rater_L1_draft", "span_draft",
                "note_draft", "model", "generated_at"]

GOLDEN_AH = {
    "FIXED_HELP": "a0eba7f6ab2be6a987f4f3a9fc6d2b4868fe5189019ddf24f9660c46d7a77c96",
    "audit_keys": "A,cell_id,elapsed_s,first_opened_ts,rater_L1,row,session_id,span_chars,ts",
    "build_help_html_fixed_guide": "27844d4d8ae9a0408a0f6cb57076ca01fa598d8bf6103328670c11c80e988099",
    "build_help_html_missing_guide": "c299896f35bd344397e2088b0e7cc7800a72447f9f2f989c0248786db7d91dba",
    "defer_row3": "c668da79c8903167274de5f235eb06edc13aa4d2d979c01f6fc93874c522e645",
    "defer_row6": "24ce9e23818d6c07d74db594bfd9e2652ef1e5637e7fe78903d1f022e20b5423",
    "draft_row1": "d6013789402be04ba04fc666bd2adc8580d26ff91c75e4066b434a52ac2bf8c0",
    "draft_row2": "cb7f6a6beaaafcbbe7d5f3f330660fbb1dc11deaeb33d8694ef0317ea15953dc",
    "draft_row3": "62dc5c62ee299d3c2e0bb232883d8817e79d4cbd6aee725366b18011fb4635d7",
    "ko_row1": "5add1fe3db6cdf9938d59cac0c0f7a68cf4ae2d356cf1310bc32de6a64fa0654",
    "ko_row2": "140bbe412f1c214c45541d30e69f7f62943760507b3fbe19091826b12a057ee6",
    "plain_row1_labeled": "1fe4120b0058f1b7120001c784f371c8e1c3d9b0e1799591ca973ee578d29131",
    "plain_row1_notice": "46bef8b61baf159bf9a78e4653e471ada0312cfb8cd0408465346e6ff961378b",
    "plain_row1_text": "62ea2ab3c5375a7132d066acab59c9887b5aef2e736c406ee1f0f06d9fe1191d",
    "plain_row2_after_save": "ae310b08aa25fbb8a6bbc94871c6e360304ef4916346891169bb9a916c9367c1",
    "plain_row2_text": "140bbe412f1c214c45541d30e69f7f62943760507b3fbe19091826b12a057ee6",
    "plain_row3_graph": "cdec7c8d86bfe2e50a200482e7ea63575dac145fbfd26b4b002eecf5a7dc145b",
    "plain_row5_help": "3ecdd7be4fbcd6eaa33e047c6359c4c46f78e6261724bbf3aa02937b40e9a14e",
    "session_line_shape": "SESSION start pid session_id",
    "session_line_shape_defer": "SESSION start pid session_id deferred",
    "session_line_shape_draft": "SESSION start pid session_id draft",
    "status_keys": "deferred,gated_reason,progress,session_saved",
}


def ah_fingerprints() -> dict[str, str]:
    g: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        s = make_store(tmp / "plain")
        for idx, tab in ((1, "text"), (2, "text"), (3, "graph"), (5, "help")):
            g[f"plain_row{idx}_{tab}"] = sha(la.render_page(s, idx, tab, "", ""))
        g["plain_row1_notice"] = sha(la.render_page(s, 1, "text", "<p>help</p>", "요청한 행 9"))
        s.save(payload(1, "cat:A:CQB01", 1, span="anchor for variant A", rater="2", note="ok"))
        g["plain_row1_labeled"] = sha(la.render_page(s, 1, "text", "", ""))
        g["plain_row2_after_save"] = sha(la.render_page(s, 2, "text", "", ""))
        dpath = tmp / "draft.csv"
        with open(dpath, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(DRAFT_HEADER)
            w.writerow(["cat:A:CQB01", "1", "2", "anchor for variant A", "초안 요약",
                        "draftmodel-v1", "2026-10-01T09:00:00+09:00"])
            w.writerow(["cat:B:CQB02", "0", "1", "", "초안 사유",
                        "draftmodel-v1", "2026-10-01T09:00:00+09:00"])
        sd = make_store(tmp / "draft", drafts=la.load_drafts(dpath), draft_name=dpath.name)
        for idx in (1, 2, 3):
            g[f"draft_row{idx}"] = sha(la.render_page(sd, idx, "text", "", ""))
        sk = make_store(tmp / "ko")
        sk.cq_ko = {"CQB01": ["한국어 번역 문장"]}
        g["ko_row1"] = sha(la.render_page(sk, 1, "text", "", ""))
        g["ko_row2"] = sha(la.render_page(sk, 2, "text", "", ""))
        sheet = make_sheet(tmp / "defer", 6)
        with open(sheet, newline="", encoding="utf-8") as fh:
            rows = list(csv.reader(fh))
        rows[2][0] = "ablated_control:B:CQB02"
        rows[4][0] = "preserved_control:D:CQB04"
        with open(sheet, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows(rows)
        views = make_views(tmp / "defer")
        out = tmp / "defer" / "labels" / "working.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        sx = la.Store(sheet, out, la.verify_views(views), defer_prefixes=la.CONTROL_PREFIXES)
        g["defer_row3"] = sha(la.render_page(sx, 3, "text", "", ""))
        g["defer_row6"] = sha(la.render_page(sx, 6, "graph", "", ""))
        g["FIXED_HELP"] = sha(la.FIXED_HELP.encode("utf-8"))
        guide = tmp / "guide.md"
        guide.write_text("# 가이드\n\n- 항목 **굵게** `코드`\n\n1. 하나\n", encoding="utf-8")
        g["build_help_html_fixed_guide"] = sha(la.build_help_html(guide).encode("utf-8"))
        g["build_help_html_missing_guide"] = sha(
            la.build_help_html(tmp / "no_such_guide.md").encode("utf-8"))
        g["status_keys"] = ",".join(sorted(s.status()))
        g["audit_keys"] = ",".join(sorted(audit_entries(s.out)[0]))

        def shape(store: la.Store) -> str:
            return " ".join(p.split("=")[0] for p in log_lines(store.out)[0].split())

        g["session_line_shape"] = shape(s)
        g["session_line_shape_draft"] = shape(sd)
        g["session_line_shape_defer"] = shape(sx)
    return g


def test_ah_pass_output_is_unchanged_without_packet() -> None:
    now = ah_fingerprints()
    assert set(now) == set(GOLDEN_AH)
    changed = sorted(k for k in GOLDEN_AH if now[k] != GOLDEN_AH[k])
    assert not changed, f"AH-pass output changed for: {changed}"


def test_ah_mode_has_no_packet_surface(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    assert store.packet is False
    with http_server(store) as base:
        text = http_get(base, "/?row=1")[1].decode("utf-8")
        assert 'id="aipanel"' not in text and "const AI=" not in text and "aiSend" not in text
        assert 'id="aicell"' not in text and "body.ai_used" not in text
        script = text.split("<script>")[1]                              # (the help tab may quote the guide)
        assert "ROW_T0" not in script and "dwell_ms" not in script     # no client dwell clock either
        assert "rater_L1(0–3)을 선택하세요" not in script               # no packet-only requirement
        assert 'aria-label="AI 도구 사용 자기보고"' not in text       # (the help tab may quote the guide)
        assert 'id="aiend"' not in text and "AI 사용</label>" not in text
        assert '<span class="chip">category' in text  # the AH chips are still there
        code, body = http_post(base, "/ai_use", {"skipped": True})
        assert code == 404 and body["ok"] is False  # an unknown route, as before
        status = json.loads(http_get(base, "/status")[1])
        assert not {"ai_use", "sitting_id", "saves_since_last_report"} & set(status)
    assert la.PACKET_COLUMNS[:12] == la.SHEET_COLUMNS and la.PACKET_COLUMNS[12:] == ("ai_used", "dwell_ms")
    # packet-only payload keys are ignored in AH mode; a blank rater_L1 is still accepted there
    code, _ = store.save(payload(1, "cat:A:CQB01", 0, note="x", ai_used=True, dwell_ms=500))
    assert code == 200
    assert read_rows(store.out)[1] == read_rows(make_sheet(tmp_path / "again"))[1][:8] + ["", "0", "", "x"]
    assert set(audit_entries(store.out)[0]) == set(GOLDEN_AH["audit_keys"].split(","))
    store.log_session_end()
    assert not any(line.startswith("AI_USE") for line in log_lines(store.out))
    assert "mode=packet" not in log_lines(store.out)[0] and "sitting_id" not in log_lines(store.out)[0]
    assert "sitting_id" not in log_lines(store.out)[-1]


def test_ah_elapsed_s_formula_is_still_server_clock_minus_client_date(tmp_path: Path) -> None:
    """The AH pass (commit f855e62, G7) measured elapsed_s as round(server time - the client's
    Date at page load, 1), with the time since the previous save as the fallback and a negative
    value read as unknown. That formula is untouched."""
    store = make_store(tmp_path)
    opened = datetime.now(timezone.utc) - timedelta(seconds=90)
    store.save(payload(1, "cat:A:CQB01", 0, note="x", first_opened=opened.isoformat(timespec="seconds")))
    assert 85.0 <= audit_entries(store.out)[0]["elapsed_s"] <= 120.0
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    store.save(payload(2, "cat:B:CQB02", 0, note="x", first_opened=future.isoformat(timespec="seconds")))
    assert audit_entries(store.out)[1]["elapsed_s"] is None          # clock skew: unknown, not instant
    store.save(payload(3, "cat:C:CQB03", 0, note="x"))
    assert audit_entries(store.out)[2]["elapsed_s"] is not None      # fallback: since the previous save


def test_ah_mode_still_demands_the_12_column_header(tmp_path: Path) -> None:
    sheet = make_packet_sheet(tmp_path, columns=14)
    views = make_views(tmp_path)
    (tmp_path / "labels").mkdir()
    with pytest.raises(la.SafetyError, match="기대 12열"):
        la.Store(sheet, tmp_path / "labels" / "w.csv", la.verify_views(views))


def test_packet_flag_defaults_off_and_is_a_switch() -> None:
    args = la.build_parser().parse_args(["--sheet", "s.csv", "--views", "v"])
    assert args.packet is False and args.sums is None and args.no_token is False and args.allow_host == []
    assert args.require_note is False
    args = la.build_parser().parse_args(["--sheet", "s.csv", "--views", "v", "--packet",
                                         "--sums", "x.txt", "--allow-host", "a", "--allow-host", "b"])
    assert args.packet is True and str(args.sums) == "x.txt" and args.allow_host == ["a", "b"]


# ---------------------------------------------------------------------------
# verify_packet_views / packet_rows
# ---------------------------------------------------------------------------
def test_verify_packet_views_accepts_listed_matching_files(tmp_path: Path) -> None:
    vdir = make_packet_views(tmp_path)
    got = la.verify_packet_views(vdir, set(PACKET_VIEWS))
    assert set(got) == set(PACKET_VIEWS)
    assert got["v_9f8e7d6c.txt"].read_text(encoding="utf-8").startswith("ABLATED VIEW")


def test_verify_packet_views_reads_the_sums_from_a_separate_path(tmp_path: Path) -> None:
    """--sums: the digests live outside the views directory (server-side only)."""
    vdir = make_packet_views(tmp_path)
    elsewhere = tmp_path / "server" / "views.sums"
    elsewhere.parent.mkdir()
    shutil.move(str(vdir / "SHA256SUMS.txt"), elsewhere)
    with pytest.raises(la.ViewMismatch, match="SHA256SUMS"):           # the default location is now empty
        la.verify_packet_views(vdir, set(PACKET_VIEWS))
    assert set(la.verify_packet_views(vdir, set(PACKET_VIEWS), sums_path=elsewhere)) == set(PACKET_VIEWS)
    lines = elsewhere.read_text(encoding="utf-8").splitlines()
    digest, name = lines[0].split("  ")
    lines[0] = ("0" if digest[0] != "0" else "1") + digest[1:] + "  " + name     # one wrong digest
    elsewhere.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(la.ViewMismatch, match="sha256"):
        la.verify_packet_views(vdir, set(PACKET_VIEWS), sums_path=elsewhere)


def test_verify_packet_views_rejects_tamper_missing_unlisted_and_unsafe(tmp_path: Path) -> None:
    vdir = make_packet_views(tmp_path)
    (vdir / "v_0a1b2c3d.txt").write_bytes(b"TAMPERED")
    with pytest.raises(la.ViewMismatch, match="sha256"):
        la.verify_packet_views(vdir, {"v_0a1b2c3d.txt"})
    with pytest.raises(la.ViewMismatch, match="뷰 파일 없음"):
        la.verify_packet_views(vdir, {"v_absent.txt"})
    (vdir / "v_unlisted.txt").write_bytes(b"x")
    with pytest.raises(la.ViewMismatch, match="항목 없음"):
        la.verify_packet_views(vdir, {"v_unlisted.txt"})
    for bad in ("", "/etc/passwd", "../packet_views/v_55aa55aa.txt", " v_55aa55aa.txt",
                "sub\\v.txt", "a/../v_55aa55aa.txt"):
        with pytest.raises(la.ViewMismatch, match="안전하지 않은"):
            la.verify_packet_views(vdir, {bad})
    no_sums = tmp_path / "no_sums"
    no_sums.mkdir()
    with pytest.raises(la.ViewMismatch, match="SHA256SUMS"):
        la.verify_packet_views(no_sums, {"x.txt"})


def test_verify_packet_views_rejects_symlink_leaving_the_directory(tmp_path: Path) -> None:
    vdir = make_packet_views(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside the views dir")
    link = vdir / "v_link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    with (vdir / "SHA256SUMS.txt").open("a", encoding="utf-8") as fh:
        fh.write(f"{sha(b'outside the views dir')}  v_link.txt\n")
    with pytest.raises(la.ViewMismatch, match="밖"):
        la.verify_packet_views(vdir, {"v_link.txt"})


def test_packet_rows_normalise_12_13_and_14_column_files_to_14(tmp_path: Path) -> None:
    for columns in (12, 13, 14):
        sheet = make_packet_sheet(tmp_path, name=f"s{columns}.csv", columns=columns)
        rows = la.packet_rows(sheet)
        assert rows[0] == PACKET_HEADER
        assert all(len(r) == 14 and r[12:] == ["", ""] for r in rows[1:])
        assert la.sheet_view_refs(sheet) == set(PACKET_VIEWS)
    assert la.packet_rows(tmp_path / "s12.csv") == la.packet_rows(tmp_path / "s14.csv")
    bad = tmp_path / "bad.csv"
    bad.write_text("cell_id,cq_text\nx,y\n", encoding="utf-8")
    with pytest.raises(la.SafetyError):
        la.sheet_view_refs(bad)
    short = tmp_path / "short.csv"
    with open(short, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerow(["a", "b"])
    with pytest.raises(la.SafetyError):
        la.sheet_view_refs(short)


# ---------------------------------------------------------------------------
# the packet screen
# ---------------------------------------------------------------------------
def test_each_row_is_served_with_its_own_view(tmp_path: Path) -> None:
    store, *_ = make_packet_store(tmp_path)
    for idx, (_, _, _, ref) in enumerate(PACKET_ROWS, start=1):
        text = la.render_page(store, idx).decode("utf-8")
        body = re.search(r'<pre id="view">(.*?)</pre>', text, re.S)
        assert body is not None
        assert html_lib.unescape(body.group(1)) == PACKET_VIEWS[ref]
    # a row carrying its own (ablated) view never shows another row's view
    ablated = la.render_page(store, 2).decode("utf-8")
    assert "ABLATED VIEW" in ablated and "ORIGINAL VIEW" not in ablated


def test_packet_screen_has_no_draft_translation_chips_or_cell_id(tmp_path: Path) -> None:
    store, *_ = make_packet_store(tmp_path)
    store.cq_ko = {"": ["번역이 있어도 packet은 보이지 않는다"]}  # even if one is attached
    for idx, (opaque, text, _, _) in enumerate(PACKET_ROWS, start=1):
        page = la.render_page(store, idx).decode("utf-8")
        shown, _, script = page.partition("<script>")
        assert html_lib.unescape(text) in html_lib.unescape(shown)  # the CQ text, as given
        assert '<span class="chip">' not in page          # no cq_id/category/variant chip
        assert 'class="draftcard"' not in page and "AI 초안 — 확인하거나" not in page
        assert 'id="cqko"' not in page and "번역은 참고용" not in page
        assert opaque not in shown                        # no id on screen (only in the save payload)
        assert f'CELL="{opaque}"' in script               # the save contract is unchanged
        assert "초안 span 위치" not in page               # no draft jump button without a draft


def test_packet_screen_shows_cq_text_exactly_as_given_and_judge_span(tmp_path: Path) -> None:
    store, *_ = make_packet_store(tmp_path)
    page = la.render_page(store, 1).decode("utf-8")
    assert '<h2 id="cq">How does Brick characterize its Sensor concept?</h2>' in page
    assert "참고용 — judge의 인용 주장" in page and "Sensor is-a Point" in page
    page2 = la.render_page(store, 2).decode("utf-8")
    assert "(judge span 없음)" in page2


def test_second_annotator_ah_format_sheet_works_in_packet_mode(tmp_path: Path) -> None:
    """The 48-cell sheet is the AH 12-column format with real ids/variants; chips stay off."""
    views = make_views(tmp_path)
    sheet = tmp_path / "second.csv"
    with open(sheet, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        for i, v in enumerate("ABC", start=1):
            w.writerow([f"primary:{v}:CQB{i:02d}", f"CQB{i:02d}", f"CQB{i:02d}", "taxonomy", v,
                        f"What is thing {i}?", "", f"rendered_view_{v}.txt", "", "", "", ""])
    out = tmp_path / "labels" / "working.csv"
    out.parent.mkdir(parents=True)
    store = la.Store(sheet, out, la.verify_packet_views(views, la.sheet_view_refs(sheet)), packet=True)
    page = la.render_page(store, 2).decode("utf-8")
    assert "VIEW B" in page and '<span class="chip">' not in page
    assert "taxonomy" not in page.partition("<script>")[0]
    assert "primary:B:CQB02" not in page.partition("<script>")[0]


def test_packet_help_tab_states_the_washout_conditions(tmp_path: Path) -> None:
    guide = tmp_path / "guide.md"
    guide.write_text("# 가이드\n", encoding="utf-8")
    packet_help = la.build_help_html(guide, packet=True)
    ah_help = la.build_help_html(guide)
    for marker in ("D19", "D20", "기록되지 않음(not recorded)", "상한도 세션 간 최소 간격도 없다",
                   "AI 채팅 도구는 허용", "세션 종료 · AI 사용 보고", "'AI 사용' 체크는 선택 사항",
                   "A · rater_L1(0–3)는 모든 행에서 필수", "note는 선택이다 (washout)", "dwell_ms", "덧붙이기만",
                   "판정 4사례", "rater_L1 앵커", "블라인드 규칙"):
        assert marker in packet_help, marker
    assert "초안 그대로" not in packet_help and "60행" not in packet_help
    assert "note는 모든 행에서 필수" not in packet_help           # the washout does not require the note
    second_help = la.build_help_html(guide, packet=True, require_note=True)
    assert "A · rater_L1(0–3) · note는 모든 행에서 필수" in second_help and "note는 선택이다" not in second_help
    assert la.build_help_html(guide, require_note=True) == ah_help    # the AH help tab has no such switch
    assert "초안 그대로" in ah_help and "60행" in ah_help  # the AH help tab is untouched
    # one definition of the rubric/blind sections serves both
    assert la._HELP_RUBRIC in packet_help and la._HELP_RUBRIC in ah_help
    assert la._HELP_BLIND in packet_help and la._HELP_BLIND in ah_help
    for word in ("verified", "reference"):  # wording rule: never in UI text
        assert word not in packet_help.lower()


TTL_MINI = """@prefix g: <http://test.org/g#> .
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
"""


def test_second_annotator_sheet_gets_the_graph_tab_from_an_explicit_ttl_dir(tmp_path: Path) -> None:
    """The AH-format sheet keeps its variant column, so --ttl-dir turns the graph tab on as in the
    AH pass; the screen still shows no variant chip."""
    pytest.importorskip("rdflib")
    views = make_views(tmp_path)
    sheet = tmp_path / "second.csv"
    with open(sheet, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(HEADER)
        w.writerow(["primary:A:CQB01", "CQB01", "CQB01", "taxonomy", "A", "What is thing 1?", "",
                    "rendered_view_A.txt", "", "", "", ""])
    ttl = tmp_path / "variants"
    (ttl / "A").mkdir(parents=True)
    (ttl / "A" / "graph_A.ttl").write_text(TTL_MINI, encoding="utf-8")
    out = tmp_path / "labels" / "working.csv"
    out.parent.mkdir()
    store = la.Store(sheet, out, la.verify_packet_views(views, la.sheet_view_refs(sheet)), packet=True)
    with http_server(store, ttl) as base:
        j = json.loads(http_get(base, "/graph?row=1")[1])
        assert j["ok"] and j["info"] is None
        assert "http://test.org/g#Thing" in {n["id"] for n in j["graph"]["nodes"]}
        assert '<span class="chip">' not in http_get(base, "/?row=1")[1].decode("utf-8")


def test_graph_tab_is_off_without_variants_and_with_them_it_uses_the_row_variant(tmp_path: Path) -> None:
    store, *_ = make_packet_store(tmp_path)
    with http_server(store) as base:  # no ttl dir at all
        j = json.loads(http_get(base, "/graph?row=1")[1])
        assert j["ok"] and j["graph"] is None and "TTL 없음" in j["info"]
    ttl = tmp_path / "variants"
    ttl.mkdir()
    with http_server(store, ttl) as base:  # a ttl dir, but the washout row has no variant
        j = json.loads(http_get(base, "/graph?row=1")[1])
        assert j["graph"] is None and j["info"] == la.PACKET_NO_GRAPH_INFO


# ---------------------------------------------------------------------------
# saving: gates, rater_L1, dwell_ms and the audit sidecar
# ---------------------------------------------------------------------------
def test_packet_save_gates_audit_keys_and_edit_trail(tmp_path: Path) -> None:
    store, sheet, _, out = make_packet_store(tmp_path)
    ids = [r[0] for r in PACKET_ROWS]
    with pytest.raises(la.SaveError):
        store.save(pp(1, ids[0], 1, note=""))                    # A=1 needs a span (the note is optional here)
    with pytest.raises(la.SaveError):
        store.save(pp(1, "wrong-id", 0, note="x"))               # cell_id must match the row
    code, body = store.save(pp(1, ids[0], 1, span="Sensor is-a Point", rater="2", note="n", dwell_ms=91000))
    assert code == 200 and body["next"] == 2
    code, _ = store.save(pp(2, ids[1], 0, span="forced clear", note="no support"))
    assert code == 200
    with pytest.raises(la.SaveError):                            # an edit needs an audit reason
        store.save(pp(1, ids[0], 0, note="changed my mind"))
    store.save(pp(1, ids[0], 0, note="changed my mind", edit_reason="re-read the view"))
    entries = audit_entries(out)
    assert len(entries) == 3
    ah_keys = set(GOLDEN_AH["audit_keys"].split(","))
    assert set(entries[0]) == ah_keys | {"ai_used", "dwell_ms", "sitting_id"}
    assert entries[0]["dwell_ms"] == 91000 and entries[0]["elapsed_s"] == 91.0 and entries[0]["row"] == 1
    assert not any(k.startswith("draft_") or k == "changed" for e in entries for k in e)
    assert not any(k.startswith("prior_") for k in entries[0])    # a first save replaces nothing
    after = read_rows(out)
    assert after[2][8:12] == ["", "0", "1", "no support"]          # span force-cleared at A=0
    original = read_rows(sheet)
    for idx in range(1, len(PACKET_ROWS) + 1):
        assert after[idx][:8] == original[idx][:8]                # only label columns moved
    assert any(line.startswith("EDIT ") and "re-read the view" in line for line in log_lines(out))
    # the edit keeps what it replaced (A, L1, span, note of the first save)
    edit = entries[2]
    assert (edit["prior_A"], edit["prior_L1"], edit["prior_span"], edit["prior_note"]) == (
        1, "2", "Sensor is-a Point", "n")
    assert edit["edit_reason"] == "re-read the view" and edit["A"] == 0


def test_packet_save_requires_rater_L1_but_ah_does_not(tmp_path: Path) -> None:
    store, _, _, out = make_packet_store(tmp_path)
    ids = [r[0] for r in PACKET_ROWS]
    for blank in ("", None):
        with pytest.raises(la.SaveError, match="rater_L1"):
            store.save(payload(1, ids[0], 0, rater=blank, note="x"))
    with pytest.raises(la.SaveError, match="rater_L1"):
        store.save(payload(1, ids[0], 1, span="Sensor is-a Point", rater="", note="x"))
    with pytest.raises(la.SaveError):                         # still only 0..3
        store.save(payload(1, ids[0], 0, rater="4", note="x"))
    assert read_rows(out)[1][9] == "" and not Path(str(out) + ".audit.jsonl").exists()   # nothing written
    assert store.save(pp(1, ids[0], 0, rater="0", note="x"))[0] == 200
    ah = make_store(tmp_path / "ah")
    assert ah.save(payload(1, "cat:A:CQB01", 0, rater="", note="x"))[0] == 200   # AH: blank is fine
    page = la.render_page(store, 1).decode("utf-8")
    assert 'if(!why&&rater===null)why="rater_L1(0–3)을 선택하세요";' in page      # the button stays off
    assert "rater_L1(0–3)을 선택하세요" not in la.render_page(ah, 1).decode("utf-8").split("<script>")[1]


def test_packet_note_is_optional_in_the_washout_and_required_with_require_note(tmp_path: Path) -> None:
    ids = [r[0] for r in PACKET_ROWS]
    # the washout: --packet alone (PREREG sec.13.1 item 8)
    store, _, _, out = make_packet_store(tmp_path / "washout")
    assert store.require_note is False and store.note_required is False
    with pytest.raises(la.SaveError, match="span"):                  # A=1 still needs a span ...
        store.save(pp(1, ids[0], 1, note=""))
    with pytest.raises(la.SaveError, match="rater_L1") as no_rater:  # ... and every row needs A and rater_L1
        store.save(payload(1, ids[0], 0, rater="", note=""))
    assert str(no_rater.value) == la.RATER_REQUIRED_MSG
    assert "A와 rater_L1" in la.RATER_REQUIRED_MSG and "네 열 모두" not in la.RATER_REQUIRED_MSG   # not "all four columns"
    with pytest.raises(la.SaveError, match="A"):
        store.save({"row": 1, "cell_id": ids[0], "rater_L1": "1", "note": ""})
    assert not Path(str(out) + ".audit.jsonl").exists()               # none of the refusals wrote anything
    assert store.save(pp(1, ids[0], 0, note=""))[0] == 200            # A=0 without a note is taken
    assert store.save(pp(2, ids[1], 1, span="line3 only", note="   "))[0] == 200
    assert store.save(pp(3, ids[2], 1, span="Meter is-a Equipment", note=None))[0] == 200
    rows = read_rows(out)
    assert rows[1][8:12] == ["", "0", "1", ""]
    assert rows[2][8:12] == ["line3 only", "1", "1", ""]              # a blank note is stored empty
    assert rows[3][8:12] == ["Meter is-a Equipment", "1", "1", ""]
    assert len(audit_entries(out)) == 3 and store.save(pp(4, ids[3], 0, note="kept when given"))[0] == 200
    assert read_rows(out)[4][11] == "kept when given"                 # a note that is given is stored as typed
    # the second annotator: --require-note (DN-9, all four columns)
    second, _, _, out2 = make_packet_store(tmp_path / "second", require_note=True)
    assert second.require_note is True and second.note_required is True
    for blank in ("", "   ", None):
        with pytest.raises(la.SaveError) as exc:
            second.save(pp(1, ids[0], 0, note=blank))
        assert str(exc.value) == la.NOTE_REQUIRED_MSG and "note" in str(exc.value)   # it names what is missing
    with pytest.raises(la.SaveError, match="note"):
        second.save(pp(1, ids[0], 1, span="Sensor is-a Point", note=""))
    assert read_rows(out2)[1][9] == "" and not Path(str(out2) + ".audit.jsonl").exists()   # nothing written
    assert second.save(pp(1, ids[0], 0, note="reason"))[0] == 200
    # the AH pass has always required it and still does; --require-note has no meaning there
    ah = make_store(tmp_path / "ah")
    assert ah.require_note is False and ah.note_required is True
    with pytest.raises(la.SaveError, match="note"):
        ah.save(payload(1, "cat:A:CQB01", 0, note=""))
    sheet, views = make_sheet(tmp_path / "ah2"), make_views(tmp_path / "ah2")
    (tmp_path / "labels2").mkdir()
    with pytest.raises(la.SafetyError, match="--require-note"):
        la.Store(sheet, tmp_path / "labels2" / "w.csv", la.verify_views(views), require_note=True)


def test_require_note_over_http_says_what_is_missing(tmp_path: Path) -> None:
    ids = [r[0] for r in PACKET_ROWS]
    store, _, _, out = make_packet_store(tmp_path / "second", require_note=True)
    with http_server(store) as base:
        code, body = http_post(base, "/save", pp(1, ids[0], 0, note=""))
        assert code == 400 and body["ok"] is False and body["error"] == la.NOTE_REQUIRED_MSG
        assert "note" in body["error"]
        assert http_post(base, "/save", pp(1, ids[0], 0, note="reason"))[0] == 200
    washout, _, _, _ = make_packet_store(tmp_path / "washout")
    with http_server(washout) as base:
        assert http_post(base, "/save", pp(1, ids[0], 0, note=""))[0] == 200


def test_page_note_rule_follows_the_mode(tmp_path: Path) -> None:
    chain = 'else if(!noteEl.value.trim())why="note(근거 요약/사유)를 반드시 적어야 합니다 (언어 무관)";'
    washout, *_ = make_packet_store(tmp_path / "w")
    second, *_ = make_packet_store(tmp_path / "s", require_note=True)
    ah = make_store(tmp_path / "a")
    pages = {name: la.render_page(st, 1).decode("utf-8") for name, st in
             (("washout", washout), ("second", second), ("ah", ah))}
    assert chain not in pages["washout"] and chain in pages["second"] and chain in pages["ah"]
    assert "(선택)" in pages["washout"] and "(선택)" not in pages["second"] and "(선택)" not in pages["ah"]
    assert 'placeholder="note — 언어 무관 (A=1: 근거 요약 / A=0: 사유)">' in pages["second"]
    assert la.NOTE_CHECK_JS.strip() == chain                          # the AH expansion is today's text
    if shutil.which("node"):
        for name, page in pages.items():                              # every variant is valid JavaScript
            js = tmp_path / f"{name}.js"
            js.write_text(page_script(page), encoding="utf-8")
            assert subprocess.run(["node", "--check", str(js)], capture_output=True, text=True).returncode == 0
    # the --require-note help tab says so
    assert "note는 선택이다" in la.build_help_html(packet=True)
    assert "note는 모든 행에서 필수" in la.build_help_html(packet=True, require_note=True)


NODE_PAGE_HARNESS = r"""
const fs = require("fs");
const files = JSON.parse(process.argv[1]), scenarios = JSON.parse(process.argv[2]);   // node -e: no script slot
function makeEl(id) {
  return {id, value: "", textContent: "", disabled: false, checked: false, style: {}, dataset: {}, className: "",
    innerHTML: "", classList: {toggle(){}, add(){}, remove(){}}, setAttribute(){}, getAttribute(){ return null; },
    addEventListener(){}, removeEventListener(){}, scrollIntoView(){}, focus(){}, appendChild(){},
    getElementsByTagName(){ return []; }, getContext(){ return null; },
    getBoundingClientRect(){ return {width: 0, height: 0, left: 0, top: 0}; }};
}
const out = {};
for (const [name, path] of Object.entries(files)) {
  const els = {};
  globalThis.document = {getElementById: (id) => (els[id] = els[id] || makeEl(id)), querySelectorAll: () => [],
    querySelector: () => null, addEventListener(){}, createElement: () => makeEl("x"), activeElement: null};
  globalThis.window = {addEventListener(){}, requestAnimationFrame(){}, devicePixelRatio: 1};
  globalThis.location = {hash: "", href: ""};
  globalThis.getSelection = () => null;
  globalThis.performance = {now: () => 0};
  globalThis.fetch = async () => ({json: async () => ({ok: true})});
  globalThis.requestAnimationFrame = () => {};
  const api = new Function(fs.readFileSync(path, "utf8") +
    "\n;return {setA, setR, noteEl, spanEl, submitBtn, whyEl};")();
  out[name] = scenarios.map(([a, rater, span, note]) => {
    api.spanEl.value = span; api.noteEl.value = note; api.setA(a); api.setR(rater);
    return {disabled: api.submitBtn.disabled, why: api.whyEl.textContent};
  });
}
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_the_client_save_button_follows_the_note_rule(tmp_path: Path) -> None:
    """Run the page's own refresh() against a DOM stub: the washout page enables the save button with an
    empty note, the --require-note and AH pages keep it disabled and say that the note is missing."""
    stores = {"washout": make_packet_store(tmp_path / "w")[0],
              "second": make_packet_store(tmp_path / "s", require_note=True)[0],
              "ah": make_store(tmp_path / "a")}
    files = {}
    for name, store in stores.items():
        files[name] = str(tmp_path / f"{name}.js")
        Path(files[name]).write_text(page_script(la.render_page(store, 1).decode("utf-8")), encoding="utf-8")
    scenarios = [[None, None, "", "x"],       # 0: no A
                 [0, None, "", "x"],          # 1: no rater_L1
                 [0, 1, "", ""],              # 2: A=0, no note
                 [0, 1, "", "   "],           # 3: A=0, blank note
                 [0, 1, "", "reason"],        # 4: complete
                 [1, 1, "", "x"],             # 5: A=1 without span
                 [1, 1, "quoted", ""],        # 6: A=1 with span, no note
                 [1, 2, "quoted", "x"]]       # 7: complete
    run = subprocess.run(["node", "-e", NODE_PAGE_HARNESS, json.dumps(files), json.dumps(scenarios)],
                         capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    got = json.loads(run.stdout)
    for name in ("washout", "second", "ah"):
        assert got[name][0]["disabled"] and "A 값" in got[name][0]["why"]
        assert got[name][5]["disabled"] and "span" in got[name][5]["why"]
        assert not got[name][4]["disabled"] and got[name][4]["why"] == ""
        assert not got[name][7]["disabled"]
    for name in ("washout", "second"):                                 # --packet: rater_L1 is required
        assert got[name][1]["disabled"] and "rater_L1" in got[name][1]["why"]
    assert not got["ah"][1]["disabled"]                                 # the AH pass has no such rule
    for idx in (2, 3, 6):                                               # the note
        assert not got["washout"][idx]["disabled"] and got["washout"][idx]["why"] == "", idx
        for name in ("second", "ah"):
            assert got[name][idx]["disabled"] and "note" in got[name][idx]["why"], (name, idx)


def test_dwell_ms_is_client_measured_stored_in_csv_total_and_each_audit_line(tmp_path: Path) -> None:
    store, _, _, out = make_packet_store(tmp_path)
    ids = [r[0] for r in PACKET_ROWS]
    skew = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat(timespec="seconds")
    store.save(pp(1, ids[0], 0, note="x", dwell_ms=12345, first_opened=skew))    # a wildly wrong client Date
    store.save(pp(1, ids[0], 0, note="y", dwell_ms=5000, edit_reason="again"))   # an edit: another 5 s
    store.save(pp(2, ids[1], 0, note="x"))                                      # no dwell sent
    store.save(pp(3, ids[2], 0, note="x", dwell_ms=1234.6))                     # a float is rounded
    a1, a2, a3, a4 = audit_entries(out)
    assert (a1["dwell_ms"], a1["elapsed_s"], a1["first_opened_ts"]) == (12345, 12.3, skew)  # Date is not used
    assert (a2["dwell_ms"], a2["elapsed_s"]) == (5000, 5.0)
    assert (a3["dwell_ms"], a3["elapsed_s"]) == (None, None)                    # unknown, never a guess
    assert (a4["dwell_ms"], a4["elapsed_s"]) == (1235, 1.2)
    rows = read_rows(out)
    assert [rows[i][13] for i in (1, 2, 3, 4)] == ["17345", "", "1235", ""]      # the CSV: total over saves
    assert all(isinstance(e["dwell_ms"], (int, type(None))) for e in (a1, a2, a3, a4))


def test_dwell_ms_rejects_implausible_values() -> None:
    assert la.parse_dwell_ms(0) == 0 and la.parse_dwell_ms(86_399_000) == 86_399_000
    assert la.parse_dwell_ms(la.DWELL_MS_MAX) == la.DWELL_MS_MAX
    for bad in (-1, la.DWELL_MS_MAX + 1, float("nan"), float("inf"), "500", True, None, [5], {"a": 1}):
        assert la.parse_dwell_ms(bad) is None, bad
    assert la.parse_dwell_ms(2.5) == 2 and la.parse_dwell_ms(2.6) == 3


def test_page_carries_the_client_dwell_clock_in_packet_mode_only(tmp_path: Path) -> None:
    store, *_ = make_packet_store(tmp_path)
    page = la.render_page(store, 1).decode("utf-8")
    script = page.split("<script>")[1]
    assert "const ROW_T0=performance.now();" in script
    assert (' if(wasLabeled)body.edit_reason=editEl.value; body.ai_used=document.getElementById("aicell").checked;'
            ' body.dwell_ms=Math.round(performance.now()-ROW_T0);') in script
    assert script.index("const firstOpened=") < script.index("const ROW_T0=")


def test_packet_mode_has_no_session_cap_or_gap(tmp_path: Path) -> None:
    n = 70
    views = {f"v_{i % 3}.txt": f"VIEW {i % 3}\nline\n" for i in range(3)}
    rows = [(f"wo-{i:016x}", f"Question {i}?", "", f"v_{i % 3}.txt") for i in range(1, n + 1)]
    sheet = make_packet_sheet(tmp_path, rows)
    vdir = make_packet_views(tmp_path, views)
    out = tmp_path / "labels" / "working.csv"
    out.parent.mkdir(parents=True)
    # a session that "ended a moment ago" must not block (no 12 h gap)
    Path(str(out) + ".session_log.txt").write_text(
        "SESSION start=2026-01-01T00:00:00+09:00 pid=1\n"
        f"SESSION end={datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')} pid=1 saved=10\n",
        encoding="utf-8")
    store = la.Store(sheet, out, la.verify_packet_views(vdir, la.sheet_view_refs(sheet)), packet=True)
    for idx in range(1, n + 1):
        code, _ = store.save(pp(idx, rows[idx - 1][0], 0, note="no support"))
        assert code == 200
    assert store.status()["session_saved"] == n and store.status()["gated_reason"] is None
    assert "가이드 상한: 세션당 60행" not in la.render_page(store, 1).decode("utf-8")


def test_packet_store_refuses_ah_draft_and_defer_and_unverified_views(tmp_path: Path) -> None:
    sheet = make_packet_sheet(tmp_path)
    vdir = make_packet_views(tmp_path)
    views = la.verify_packet_views(vdir, la.sheet_view_refs(sheet))
    out = tmp_path / "labels" / "working.csv"
    out.parent.mkdir(parents=True)
    draft = tmp_path / "draft.csv"
    with open(draft, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([DRAFT_HEADER])
    with pytest.raises(la.SafetyError):
        la.Store(sheet, out, views, drafts=la.load_drafts(draft), draft_name="d.csv", packet=True)
    with pytest.raises(la.SafetyError):
        la.Store(sheet, out, views, defer_prefixes=la.CONTROL_PREFIXES, packet=True)
    partial = {k: v for k, v in views.items() if k != "v_9f8e7d6c.txt"}
    with pytest.raises(la.SafetyError, match="검증되지 않은"):
        la.Store(sheet, out, partial, packet=True)
    assert not out.exists()  # refused before the working copy was seeded


def test_resumed_out_naming_other_views_is_refused(tmp_path: Path) -> None:
    store, sheet, vdir, out = make_packet_store(tmp_path)
    rows = read_rows(out)
    rows[1][7] = "v_not_verified.txt"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    views = la.verify_packet_views(vdir, la.sheet_view_refs(sheet))
    with pytest.raises(la.SafetyError, match="--out의 뷰 참조"):
        la.Store(sheet, out, views, packet=True)


def test_resumed_out_must_come_from_this_sheet(tmp_path: Path) -> None:
    """Resume checks the cell ids (and CQ text, span, view name) against --sheet, not only that the
    view names verify."""
    store, sheet, vdir, out = make_packet_store(tmp_path)
    store.save(pp(1, PACKET_ROWS[0][0], 0, note="x"))
    views = la.verify_packet_views(vdir, la.sheet_view_refs(sheet))
    resumed = la.Store(sheet, out, views, packet=True)                     # the same sheet: fine
    assert read_rows(out)[1][9] == "0" and resumed.rows[1][9] == "0"
    other_rows = [("wo-ffffffffffffffff", PACKET_ROWS[0][1], PACKET_ROWS[0][2], PACKET_ROWS[0][3]),
                  *PACKET_ROWS[1:]]                                        # one different cell id
    other_sheet = make_packet_sheet(tmp_path / "other", other_rows)
    with pytest.raises(la.SafetyError, match="다른 시트"):
        la.Store(other_sheet, out, views, packet=True)
    edited = read_rows(out)
    edited[2][5] = "A different question text?"                            # a changed CQ text
    with open(out, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(edited)
    with pytest.raises(la.SafetyError, match="다른 시트"):
        la.Store(sheet, out, views, packet=True)
    swapped = read_rows(make_packet_sheet(tmp_path / "swap", [PACKET_ROWS[1], PACKET_ROWS[0], *PACKET_ROWS[2:]]))
    with open(out, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([PACKET_HEADER] + [r + ["", ""] for r in swapped[1:]])
    with pytest.raises(la.SafetyError, match="다른 시트"):                  # same ids, different order
        la.Store(sheet, out, views, packet=True)


# ---------------------------------------------------------------------------
# the working CSV: the 12-column sheet + ai_used + dwell_ms
# ---------------------------------------------------------------------------
def test_packet_working_csv_is_the_sheet_plus_two_empty_columns(tmp_path: Path) -> None:
    store, sheet, _, out = make_packet_store(tmp_path)
    rows = read_rows(out)
    assert rows[0] == PACKET_HEADER and rows[0][12:] == ["ai_used", "dwell_ms"]
    assert [r[:12] for r in rows] == read_rows(sheet)       # the sheet is intact in front of them
    assert all(r[12:] == ["", ""] for r in rows[1:])        # nothing ticked, no dwell yet
    # a 14-column sheet is seeded with the same content
    sheet14 = make_packet_sheet(tmp_path / "s14", columns=14)
    out14 = tmp_path / "labels14" / "working.csv"
    out14.parent.mkdir(parents=True)
    la.Store(sheet14, out14, la.verify_packet_views(make_packet_views(tmp_path / "s14"),
                                                    la.sheet_view_refs(sheet14)), packet=True)
    assert read_rows(out14) == rows
    # resuming from a 12- or 13-column working copy extends it in memory and on the first save
    for columns in (12, 13):
        out_old = tmp_path / f"labels{columns}" / "working.csv"
        out_old.parent.mkdir(parents=True)
        out_old.write_bytes(make_packet_sheet(tmp_path / f"s{columns}", columns=columns).read_bytes())
        views = la.verify_packet_views(tmp_path / "packet_views", la.sheet_view_refs(sheet))
        resumed = la.Store(sheet, out_old, views, packet=True)
        assert resumed.rows[0] == PACKET_HEADER
        resumed.save(pp(1, PACKET_ROWS[0][0], 0, note="x", ai_used=True, dwell_ms=700))
        assert read_rows(out_old)[0] == PACKET_HEADER
        assert read_rows(out_old)[1][12:] == ["yes", "700"]


def test_per_row_ai_tick_is_optional_stored_in_csv_and_audit(tmp_path: Path) -> None:
    store, _, _, out = make_packet_store(tmp_path)
    ids = [r[0] for r in PACKET_ROWS]
    store.save(pp(1, ids[0], 0, note="x", ai_used=True))      # ticked
    store.save(pp(2, ids[1], 0, note="x", ai_used=False))     # explicitly unticked
    store.save(pp(3, ids[2], 0, note="x"))                    # never touched
    rows = read_rows(out)
    assert [rows[i][12] for i in (1, 2, 3, 4)] == ["yes", "", "", ""]
    a1, a2, a3 = audit_entries(out)
    # a JSON boolean when ticked (analyze_washout reads true/false/yes/no); null = not recorded
    assert a1["ai_used"] is True and a2["ai_used"] is None and a3["ai_used"] is None
    # an edit re-sends the tick; unticking it later blanks the cell and the audit says so
    store.save(pp(1, ids[0], 0, note="x", edit_reason="r", ai_used=False))
    assert read_rows(out)[1][12] == "" and audit_entries(out)[3]["ai_used"] is None
    # anything but a boolean is refused before anything is written
    before = out.read_bytes()
    for bad in ("yes", 1, "1", 0, {}):
        with pytest.raises(la.SaveError, match="ai_used"):
            store.save(pp(4, ids[3], 0, note="x", ai_used=bad))
    assert out.read_bytes() == before


def test_audit_ai_flags_read_by_analyze_washout(tmp_path: Path) -> None:
    """The per-row tick lands in the audit line as a JSON boolean (or null), the vocabulary
    analyze_washout.load_audit_ai_flags reads; unticked rows give no flag (= not recorded)."""
    aw = pytest.importorskip("analyze_washout")
    if not hasattr(aw, "load_audit_ai_flags"):
        pytest.skip("analyze_washout has no load_audit_ai_flags")
    store, _, _, out = make_packet_store(tmp_path)
    ids = [r[0] for r in PACKET_ROWS]
    store.save(pp(1, ids[0], 0, note="x", ai_used=True))
    store.save(pp(2, ids[1], 0, note="x"))
    flags = aw.load_audit_ai_flags(Path(str(out) + ".audit.jsonl"))
    assert flags == {0: "yes"}                      # line 0 ticked; line 1 has no flag


def test_ai_tick_markup_prefill_and_save_hook(tmp_path: Path) -> None:
    store, _, _, out = make_packet_store(tmp_path)
    page = la.render_page(store, 1).decode("utf-8")
    assert '<input type="checkbox" id="aicell"> AI 사용</label>' in page
    assert page.index('id="aicell"') < page.index('id="submit"')   # inside the input bar
    assert page.index('id="inbar"') < page.index('id="aicell"')
    assert '<input type="checkbox" id="aicell" checked>' not in page
    store.save(pp(1, PACKET_ROWS[0][0], 0, note="x", ai_used=True))
    again = la.render_page(store, 1).decode("utf-8")
    assert '<input type="checkbox" id="aicell" checked> AI 사용</label>' in again  # follows the CSV
    other = la.render_page(store, 2).decode("utf-8")
    assert '<input type="checkbox" id="aicell"> AI 사용</label>' in other
    # the tick never gates saving, and the rest of the payload line is the AH pass's
    body_line = next(ln for ln in page.splitlines() if ln.startswith(" const body={"))
    assert body_line.strip() == ("const body={row:ROW,cell_id:CELL,A:a,"
                                 "evidence_span_verbatim:spanEl.value,rater_L1:rater,"
                                 "note:noteEl.value,first_opened:firstOpened};")
    with http_server(store) as base:
        code, body = http_post(base, "/save", pp(2, PACKET_ROWS[1][0], 0, note="x"))
        assert code == 200 and body["ok"]            # saved without any ai_used key at all
    assert read_rows(out)[2][12] == ""


# ---------------------------------------------------------------------------
# AI-use self-report at the end of a SITTING (PREREG D20; no start form; append-only)
# ---------------------------------------------------------------------------
def test_ai_use_end_report_is_logged_with_tool_approx_cells_and_its_sitting(tmp_path: Path) -> None:
    store, _, _, out = make_packet_store(tmp_path)
    ids = [r[0] for r in PACKET_ROWS]
    sitting1 = store.sitting_id
    assert sitting1 == f"{store.session_id}.1" and f"sitting_id={sitting1} mode=packet" in log_lines(out)[0]
    store.save(pp(1, ids[0], 0, note="x"))
    store.save(pp(2, ids[1], 0, note="x"))
    with http_server(store) as base:
        status = json.loads(http_get(base, "/status")[1])
        assert status["ai_use"] is None and status["sitting_id"] == sitting1
        assert status["saves_since_last_report"] == 2
        code, body = http_post(base, "/ai_use", {"used": True, "tool": "  ChatGPT  ", "approx_cells": " 30 "})
        assert code == 200 and body == {"ok": True, "used": "yes"}
        status = json.loads(http_get(base, "/status")[1])
        assert status["ai_use"] == "yes" and status["saves_since_last_report"] == 0
        assert status["sitting_id"] == f"{store.session_id}.2"
    e = ai_entries(out)[0]
    assert (e["phase"], e["used"], e["tool"], e["approx_cells"], e["how"]) == ("end", "yes", "ChatGPT", 30, "answered")
    assert (e["sitting_id"], e["saves_since_last_report"], e["report_seq"]) == (sitting1, 2, 1)
    assert e["session_id"] == store.session_id and e["ts"]
    store.log_session_end()
    assert len(ai_entries(out)) == 1          # it was answered and nothing was saved since
    assert log_lines(out)[-1].startswith("SESSION end=")
    assert log_lines(out)[-1].endswith(f"sitting_id={store.session_id}.2")


def test_ai_use_reports_are_append_only_and_each_covers_only_its_own_sitting(tmp_path: Path) -> None:
    store, _, _, out = make_packet_store(tmp_path)
    ids = [r[0] for r in PACKET_ROWS]
    store.save(pp(1, ids[0], 0, note="x"))
    store.record_ai_use({"used": True, "tool": "ChatGPT", "approx_cells": 1})     # sitting 1: AI used
    store.save(pp(2, ids[1], 0, note="x"))
    store.save(pp(3, ids[2], 0, note="x"))
    store.record_ai_use({"used": False})                                          # sitting 2: no AI
    store.save(pp(4, ids[3], 0, note="x"))                                        # sitting 3: never reported
    store.log_session_end()
    reports = ai_entries(out)
    assert [(r["sitting_id"].split(".")[-1], r["used"], r["saves_since_last_report"], r["report_seq"], r["how"])
            for r in reports] == [("1", "yes", 1, 1, "answered"), ("2", "no", 2, 2, "answered"),
                                  ("3", "not recorded", 1, 3, "unanswered")]
    audits = audit_entries(out)
    assert [a["sitting_id"].split(".")[-1] for a in audits] == ["1", "2", "2", "3"]     # saves name their sitting
    assert {a["sitting_id"] for a in audits} == {r["sitting_id"] for r in reports}
    for r in reports:                                                                  # counts match the audit
        assert r["saves_since_last_report"] == sum(1 for a in audits if a["sitting_id"] == r["sitting_id"])
    # append-only: the earlier "yes" is still there beside the later "no"
    assert [r["used"] for r in reports][:2] == ["yes", "no"]
    assert log_lines(out)[-2].startswith("AI_USE ") and log_lines(out)[-1].startswith("SESSION end=")


def test_ai_use_skip_and_no_answer_are_recorded_as_not_recorded(tmp_path: Path) -> None:
    store, _, _, out = make_packet_store(tmp_path)
    with http_server(store) as base:
        code, body = http_post(base, "/ai_use", {"skipped": True})
        assert code == 200 and body["used"] == "not recorded"
    entries = ai_entries(out)
    assert (entries[0]["used"], entries[0]["how"], entries[0]["tool"], entries[0]["approx_cells"]) == (
        "not recorded", "skipped", "", None)
    store2, _, _, out2 = make_packet_store(tmp_path / "second")
    store2.log_session_end()                  # the form was never answered (and nothing was saved)
    store2.log_session_end()                  # idempotent
    e = ai_entries(out2)
    assert len(e) == 1 and (e[0]["used"], e[0]["how"], e[0]["saves_since_last_report"]) == (
        "not recorded", "unanswered", 0)
    assert log_lines(out2)[-1].startswith("SESSION end=")   # SESSION end stays the last line


def test_ai_use_no_and_yes_without_a_number(tmp_path: Path) -> None:
    store, _, _, out = make_packet_store(tmp_path)
    store.record_ai_use({"used": False, "tool": "ignored", "approx_cells": "77"})
    store.record_ai_use({"used": "yes", "tool": "Claude", "approx_cells": ""})
    store.record_ai_use({"used": "yes", "tool": "Claude", "approx_cells": 12})
    got = [(e["used"], e["tool"], e["approx_cells"]) for e in ai_entries(out)]
    assert got == [("no", "", 0), ("yes", "Claude", None), ("yes", "Claude", 12)]
    assert store.ai_use is not None and store.ai_use["approx_cells"] == 12   # the last one is the status


def test_ai_use_validation_and_unicode_digits(tmp_path: Path) -> None:
    store, _, _, out = make_packet_store(tmp_path)
    for bad in ({},                                                  # neither an answer nor a skip
                {"used": "maybe", "tool": "x"},
                {"used": True, "tool": "   "},                        # yes needs a tool name
                {"used": True},
                {"used": True, "tool": "x", "approx_cells": -1},
                {"used": True, "tool": "x", "approx_cells": "3.5"},
                {"used": True, "tool": "x", "approx_cells": True},
                {"used": True, "tool": "x", "approx_cells": "①"},     # str.isdigit() is true for these
                {"used": True, "tool": "x", "approx_cells": "²³"},
                {"used": True, "tool": "x", "approx_cells": "٣"},     # an Arabic-Indic digit
                {"used": True, "tool": "x", "approx_cells": "9" * 400},
                {"used": True, "tool": "x", "approx_cells": la.AI_APPROX_CELLS_MAX + 1},
                {"phase": "start", "used": False}):                   # there is no start form
        with pytest.raises(la.SaveError):
            store.record_ai_use(bad)
    assert ai_entries(out) == []
    with http_server(store) as base:
        code, body = http_post(base, "/ai_use", {"used": True, "tool": ""})
        assert code == 400 and body["ok"] is False and "도구 이름" in body["error"]
        code, body = http_post(base, "/ai_use", {"used": True, "tool": "x", "approx_cells": "①"})
        assert code == 400 and body["ok"] is False                    # an error reply, not a dropped request
        code, _ = http_post(base, "/ai_use", {"used": "yes", "tool": "Claude"})
        assert code == 200                                            # "yes"/"no" strings are accepted
        code, _ = http_post(base, "/ai_use", {"phase": "end", "used": "no"})
        assert code == 200
    assert [e["used"] for e in ai_entries(out)] == ["yes", "no"]


def test_ai_use_tool_name_cannot_forge_log_lines(tmp_path: Path) -> None:
    store, _, _, out = make_packet_store(tmp_path)
    evil = ("Claude\nSESSION end=2026-01-01 pid=1 saved=999\r\nEDIT x 1->0" + LS + "AI_USE {}" + PS
            + "q" + NEL + "z" + "y" * 200)
    store.record_ai_use({"used": True, "tool": evil})
    lines = log_lines(out)
    assert len([l for l in lines if l.startswith("SESSION")]) == 1     # only the real start line
    assert not any(l.startswith("EDIT") for l in lines)
    entry = ai_entries(out)[0]
    assert not any(c in entry["tool"] for c in ("\n", "\r", LS, PS, NEL))
    assert len(entry["tool"]) <= la.AI_TOOL_MAX_CHARS and entry["tool"].startswith("Claude SESSION end")
    assert Path(str(out) + ".session_log.txt").read_text(encoding="utf-8").count("\n") == len(lines)


def test_ai_use_is_refused_outside_packet_mode(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(la.SaveError):
        store.record_ai_use({"used": False})


def test_ai_form_is_end_only_hidden_until_asked_and_follows_the_sitting(tmp_path: Path) -> None:
    store, _, _, _ = make_packet_store(tmp_path)
    page = la.render_page(store, 1).decode("utf-8")
    assert 'id="aipanel" class="notice" role="region" aria-label="AI 도구 사용 자기보고" style="display:none">' in page
    for marker in ('name="aiused" value="yes"', 'name="aiused" value="no"', 'id="aitool"', 'id="aicells"',
                   "aiSend(false)", "aiSend(true)", "건너뛰기", "세션 종료 · AI 사용 보고",
                   "AI 도구 사용 자기보고 — 세션 종료", 'const AI={done:false};',
                   'if(location.hash==="#done"&&!AI.done)aiShow();'):
        assert marker in page, marker
    assert "세션 시작" not in page and "phase" not in page.split("<script>")[1]   # no start form at all
    store.record_ai_use({"skipped": True})
    answered = la.render_page(store, 1).decode("utf-8")
    assert 'const AI={done:true};' in answered                    # reported, nothing saved since
    store.save(pp(1, PACKET_ROWS[0][0], 0, note="x"))
    assert 'const AI={done:false};' in la.render_page(store, 2).decode("utf-8")   # a new sitting is open
    assert page.index('id="aipanel"') < page.index('id="wrap"')   # a banner above the panes


def page_script(page: str) -> str:
    """The page's one script element: from the first <script> to the last </script> (a closing tag
    inside a string literal is escaped as <\\/script>, so the last one is the real end)."""
    start = page.index("<script>") + len("<script>")
    return page[start:page.rindex("</script>")]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
def test_packet_page_script_parses_and_the_client_logic_runs(tmp_path: Path) -> None:
    store, *_ = make_packet_store(tmp_path)
    script = page_script(la.render_page(store, 1).decode("utf-8"))
    js = tmp_path / "page.js"
    js.write_text(script, encoding="utf-8")
    parsed = subprocess.run(["node", "--check", str(js)], capture_output=True, text=True)
    assert parsed.returncode == 0, parsed.stderr
    # run the AI-form block and the dwell clock against a minimal DOM stub
    block = la.packet_js(store)
    harness = f"""
let now = 1000;
globalThis.performance = {{now: () => now}};
const els = {{}};
function el(id){{ return els[id] = els[id] || {{id, style:{{display:"none"}}, textContent:"", value:"", checked:false}}; }}
globalThis.document = {{
  getElementById: el,
  querySelector: () => (globalThis.checked ? {{value: globalThis.checked}} : null),
  querySelectorAll: () => [{{checked:true}}],
}};
globalThis.location = {{hash: "#done"}};
const posted = [];
globalThis.fetch = async (url, opts) => {{ posted.push([url, JSON.parse(opts.body)]);
  return {{json: async () => ({{ok: globalThis.serverOk, error: "서버 거부"}})}}; }};
// the dwell clock: ROW_T0 at row open, the save hook reads the delta
eval({json.dumps(la.PACKET_T0_JS.strip().replace("const ROW_T0", "var ROW_T0"))});
now = 3500;
const body = {{row: 1}}; let wasLabeled = false; const editEl = {{value: ""}};
eval({json.dumps(la.PACKET_BODY_JS)});
{block}
(async () => {{
  const openedOnDone = el("aipanel").style.display === "";
  globalThis.serverOk = false; globalThis.checked = "yes"; el("aitool").value = "ChatGPT"; el("aicells").value = "30";
  await aiSend(false);
  const rejected = el("aimsg").textContent, stillOpen = el("aipanel").style.display === "";
  globalThis.serverOk = true; await aiSend(false);
  const closed = el("aipanel").style.display === "none", done = AI.done;
  aiShow(); globalThis.checked = null; await aiSend(true);
  console.log(JSON.stringify({{posted, rejected, stillOpen, closed, done, openedOnDone, dwell: body.dwell_ms,
                              ai: body.ai_used}}));
}})();
"""
    run = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["dwell"] == 2500                           # performance.now() delta, row open -> save
    assert result["ai"] is False                             # the unticked checkbox is sent as false
    assert result["openedOnDone"] is True                    # all rows done: the form opens by itself
    assert result["posted"][0] == ["/ai_use", {"skipped": False, "used": True, "tool": "ChatGPT",
                                               "approx_cells": "30"}]
    assert result["posted"][2][1] == {"skipped": True, "used": None, "tool": "", "approx_cells": ""}
    assert result["rejected"] == "서버 거부" and result["stillOpen"] is True   # a refusal is shown, not swallowed
    assert result["closed"] is True and result["done"] is True


@pytest.mark.parametrize("packet", [False, True])
def test_a_cell_id_with_script_special_characters_survives_as_a_json_literal(tmp_path: Path, packet: bool) -> None:
    """CELL is emitted with json.dumps (and </ escaped): a backslash, quotes, & < > or a closing
    script tag in an id neither breaks the page nor makes the save fail as a cell_id mismatch."""
    tricky = 'cat:A\\x"q"&amp;\'<b>/</script><script>alert(1)</script>'
    root = tmp_path / ("p" if packet else "a")
    root.mkdir()
    if packet:
        sheet = make_packet_sheet(root, [(tricky, "What?", "", "v_0a1b2c3d.txt")])
        vdir = make_packet_views(root)
        out = root / "labels" / "working.csv"
        out.parent.mkdir()
        store = la.Store(sheet, out, la.verify_packet_views(vdir, la.sheet_view_refs(sheet)), packet=True)
        save = pp
    else:
        sheet = make_sheet(root, 1)
        rows = read_rows(sheet)
        rows[1][0] = tricky
        with open(sheet, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows(rows)
        out = root / "labels" / "working.csv"
        out.parent.mkdir()
        store = la.Store(sheet, out, la.verify_views(make_views(root)))
        save = payload
    page = la.render_page(store, 1).decode("utf-8")
    assert "</script><script>alert(1)" not in page          # no way out of the script element
    script = page_script(page)
    match = re.search(r"CELL=(\"(?:[^\"\\]|\\.)*\")", script)
    assert match is not None and json.loads(match.group(1)) == tricky
    if shutil.which("node"):
        js = root / "page.js"
        js.write_text(script, encoding="utf-8")
        assert subprocess.run(["node", "--check", str(js)], capture_output=True, text=True).returncode == 0
    with http_server(store) as base:
        code, body = http_post(base, "/save", save(1, tricky, 0, note="x"))
        assert code == 200 and body["ok"], body              # the id the page reports is the id the server holds


def test_unicode_digits_are_a_400_or_a_notice_never_a_server_error(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    with http_server(store) as base:
        circled = urllib.parse.quote("①")
        for path in (f"/?row={circled}", "/?row=%C2%B2", f"/graph?row={circled}", "/?row=" + "9" * 400):
            code, _ = http_get(base, path)
            assert code == 200, path
        text = http_get(base, f"/?row={circled}")[1].decode("utf-8")
        assert "요청한 행 ① 은(는) 유효하지 않아" in text
        for bad in ({"A": "①"}, {"rater_L1": "②"}, {"row": "①"}):
            body = payload(1, "cat:A:CQB01", 0, note="x")
            body.update(bad)
            code, reply = http_post(base, "/save", body)
            assert code == 400 and reply["ok"] is False, bad
    assert la.ascii_int("12") == 12 and la.ascii_int(" -3 ") == -3
    for bad in ("①", "²", "٣", "", "1.5", "+4", "9" * 10, "1_0"):
        assert la.ascii_int(bad) is None, bad


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
@pytest.fixture
def quiet_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() installs SIGTERM/SIGHUP handlers and an atexit hook: keep both out of the pytest process
    (the real handlers are exercised in a subprocess, see test_label_assist_security.py)."""
    monkeypatch.setattr(la.signal, "signal", lambda *a, **k: None)
    monkeypatch.setattr(la.atexit, "register", lambda *a, **k: None)


def test_cli_refuses_ah_only_options_with_packet(tmp_path: Path) -> None:
    sheet = make_packet_sheet(tmp_path)
    vdir = make_packet_views(tmp_path)
    out = tmp_path / "labels" / "w.csv"
    base = ["--packet", "--sheet", str(sheet), "--views", str(vdir), "--out", str(out)]
    for extra in (["--draft", str(tmp_path / "d.csv")], ["--cq-ko", str(tmp_path / "ko.json")],
                  ["--defer-controls"]):
        assert la.main(base + extra) == 1
        assert not out.exists()


def test_cli_refuses_unverifiable_views_and_inside_repo_out(tmp_path: Path) -> None:
    sheet = make_packet_sheet(tmp_path)
    vdir = make_packet_views(tmp_path)
    (vdir / "v_9f8e7d6c.txt").write_bytes(b"TAMPERED")
    out = tmp_path / "labels" / "w.csv"
    assert la.main(["--packet", "--sheet", str(sheet), "--views", str(vdir), "--out", str(out)]) == 1
    assert not out.exists()
    vdir2 = make_packet_views(tmp_path / "second")
    inside = tmp_path / ".claude" / "worktrees" / "wt" / "out.csv"
    assert la.main(["--packet", "--sheet", str(sheet), "--views", str(vdir2),
                    "--out", str(inside)]) == 1


def test_cli_sums_path_is_used_and_needs_packet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                capsys: pytest.CaptureFixture[str], quiet_process: None) -> None:
    sheet = make_packet_sheet(tmp_path)
    vdir = make_packet_views(tmp_path)
    sums = tmp_path / "server" / "views.sums"
    sums.parent.mkdir()
    shutil.move(str(vdir / "SHA256SUMS.txt"), sums)
    out = tmp_path / "labels" / "w.csv"
    base = ["--sheet", str(sheet), "--views", str(vdir), "--out", str(out)]
    assert la.main(["--packet", *base]) == 1                       # no sums where the default expects them
    assert la.main([*base, "--sums", str(sums)]) == 1              # --sums without --packet is refused
    assert "--sums" in capsys.readouterr().err
    assert not out.exists()

    class Dummy:
        server_address = ("127.0.0.1", 1)

        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def server_close(self) -> None:
            pass

    monkeypatch.setattr(la, "make_server", lambda store, addr, ttl_dir=None, **kw: Dummy())
    assert la.main(["--packet", *base, "--sums", str(sums)]) == 0


def test_cli_require_note_needs_packet_and_reaches_the_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                              capsys: pytest.CaptureFixture[str],
                                                              quiet_process: None) -> None:
    sheet, vdir = make_packet_sheet(tmp_path), make_packet_views(tmp_path)
    ah_sheet, ah_views = make_sheet(tmp_path / "ah"), make_views(tmp_path / "ah")
    out = tmp_path / "labels" / "w.csv"
    # --require-note without --packet is refused and nothing is created
    assert la.main(["--require-note", "--sheet", str(ah_sheet), "--views", str(ah_views), "--out", str(out)]) == 1
    assert "--require-note" in capsys.readouterr().err and not out.exists()
    seen: dict[str, Any] = {}

    class Dummy:
        server_address = ("127.0.0.1", 1)

        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def server_close(self) -> None:
            pass

    def fake_make_server(store: la.Store, addr, ttl_dir=None, **kwargs):
        seen["store"] = store
        return Dummy()

    monkeypatch.setattr(la, "make_server", fake_make_server)
    assert la.main(["--packet", "--require-note", "--sheet", str(sheet), "--views", str(vdir),
                    "--out", str(out)]) == 0
    assert seen["store"].require_note is True and seen["store"].note_required is True
    assert "require_note=on" in capsys.readouterr().out
    assert "require_note=yes" in log_lines(out)[0] and "mode=packet" in log_lines(out)[0]
    out2 = tmp_path / "labels2" / "w.csv"                               # the washout: no flag, no trace
    assert la.main(["--packet", "--sheet", str(sheet), "--views", str(vdir), "--out", str(out2)]) == 0
    assert seen["store"].require_note is False and seen["store"].note_required is False
    assert "require_note=on" not in capsys.readouterr().out and "require_note=yes" not in log_lines(out2)[0]


def test_cli_packet_start_prints_mode_and_serves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                 capsys: pytest.CaptureFixture[str], quiet_process: None) -> None:
    sheet = make_packet_sheet(tmp_path)
    vdir = make_packet_views(tmp_path)
    out = tmp_path / "labels" / "w.csv"
    seen: dict[str, Any] = {}

    class Dummy:
        server_address = ("127.0.0.1", 1)

        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def server_close(self) -> None:
            pass

    def fake_make_server(store: la.Store, addr, ttl_dir=None, **kwargs):
        seen.update(packet=store.packet, ttl_dir=ttl_dir, **kwargs)
        return Dummy()

    monkeypatch.setattr(la, "make_server", fake_make_server)
    assert la.main(["--packet", "--sheet", str(sheet), "--views", str(vdir), "--out", str(out)]) == 0
    assert seen["packet"] is True and seen["ttl_dir"] is None   # a washout sheet has no graph without --ttl-dir
    assert isinstance(seen["auth"], la.TokenAuth)                # the token is on by default
    assert "mode=packet" in capsys.readouterr().out
    first = log_lines(out)[0]
    assert "mode=packet" in first and f"sheet_sha256={sha(sheet.read_bytes())[:16]}" in first
    assert read_rows(out)[0] == PACKET_HEADER
