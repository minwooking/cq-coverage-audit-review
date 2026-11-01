"""Serving-safety, durability and process tests for label_assist (both modes).

Covers the security and blinding review: a per-launch token cookie, Host allow-list,
same-origin JSON-only POSTs, a body cap and a socket timeout; atomic and durable saves (audit
line first, copy-then-swap, fsync); log-line integrity and field caps; the single-writer flock
and SIGHUP/SIGTERM shutdown; and the repository guard that must know the main checkout and
every worktree. ALL DATA HERE IS SYNTHETIC. HTTP tests bind an ephemeral 127.0.0.1:0 port and
close it in the same test; nothing polls with sleep (sockets block, processes are waited on).
"""
from __future__ import annotations

import http.client
import http.cookiejar
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import label_assist as la  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
import test_label_assist_packet as tp  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]

HARNESS = Path(__file__).resolve().parent
LS, PS, NEL = chr(0x2028), chr(0x2029), chr(0x85)


@contextmanager
def serve(store: la.Store, *, auth: la.TokenAuth | None = None, extra_hosts=(),
          timeout: float = la.HTTP_TIMEOUT_S, ttl_dir: Path | None = None):
    server = la.make_server(store, ("127.0.0.1", 0), ttl_dir, auth=auth, extra_hosts=extra_hosts,
                            timeout=timeout)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "127.0.0.1", server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def raw(host: str, port: int, method: str, path: str, *, headers: dict[str, str] | None = None,
        body: bytes | None = None) -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPConnection(host, port, timeout=5)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, resp.read()
    finally:
        conn.close()


def post(host: str, port: int, path: str, obj: object, *, cookie: str = "",
         extra: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    headers = {"Content-Type": "application/json", "Origin": f"http://{host}:{port}"}
    if cookie:
        headers["Cookie"] = f"{la.COOKIE_NAME}={cookie}"
    headers.update(extra or {})
    return raw(host, port, "POST", path, headers=headers, body=json.dumps(obj).encode("utf-8"))


def redeem(host: str, port: int, auth: la.TokenAuth) -> str:
    status, headers, _ = raw(host, port, "GET", f"/?token={auth.launch_token}")
    assert status == 302
    return re.match(rf"{la.COOKIE_NAME}=([^;]+);", headers["set-cookie"]).group(1)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# 1. token + cookie
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("packet", [False, True])
def test_every_route_needs_the_token_cookie(tmp_path: Path, packet: bool) -> None:
    store = tp.make_packet_store(tmp_path)[0] if packet else tp.make_store(tmp_path)
    auth = la.TokenAuth()
    rows_before = [list(r) for r in store.rows]
    with serve(store, auth=auth) as (h, p):
        for path in ("/", "/status", "/export", "/graph?row=1", "/nope", "/?row=2", "/?token=wrong",
                     f"/export?token={auth.launch_token}", f"/status?token={auth.launch_token}"):
            status, headers, body = raw(h, p, "GET", path)
            assert status == 401, path
            assert "set-cookie" not in headers and b"VIEW" not in body and b"cell_id" not in body
        cell = store.rows[1][0]
        for route, obj in (("/save", tp.payload(1, cell, 0, note="x", rater="1")),
                           ("/ai_use", {"skipped": True}), ("/nope", {})):
            status, _, _ = post(h, p, route, obj)
            assert status == 401, route
    assert store.rows == rows_before and not Path(str(store.out) + ".audit.jsonl").exists()


def test_the_one_time_url_exchanges_the_token_for_an_httponly_samesite_cookie(tmp_path: Path) -> None:
    store = tp.make_store(tmp_path)
    auth = la.TokenAuth()
    with serve(store, auth=auth) as (h, p):
        status, headers, _ = raw(h, p, "GET", f"/?row=2&tab=help&token={auth.launch_token}")
        assert status == 302 and headers["location"] == "/?row=2&tab=help"      # the token leaves the URL
        cookie_line = headers["set-cookie"]
        assert "HttpOnly" in cookie_line and "SameSite=Strict" in cookie_line and "Path=/" in cookie_line
        assert f"Max-Age={la.COOKIE_MAX_AGE_S}" in cookie_line and "Secure" not in cookie_line
        cookie = re.match(rf"{la.COOKIE_NAME}=([^;]+);", cookie_line).group(1)  # type: ignore[union-attr]
        assert cookie != auth.launch_token and len(cookie) >= 40               # a fresh secret, not the URL's
        # the printed URL works once: a second visit without the cookie is refused
        assert raw(h, p, "GET", f"/?token={auth.launch_token}")[0] == 401
        # with the cookie every route answers; the token parameter is then ignored
        headers_ok = {"Cookie": f"{la.COOKIE_NAME}={cookie}"}
        for path in ("/", "/status", "/export", "/graph?row=1", "/?token=anything"):
            assert raw(h, p, "GET", path, headers=headers_ok)[0] == 200, path
        assert raw(h, p, "GET", "/nope", headers=headers_ok)[0] == 404
        # a wrong or foreign cookie value is refused
        for bad in ("", "x" * 43, cookie[:-1], auth.launch_token, cookie + "A"):
            assert raw(h, p, "GET", "/status", headers={"Cookie": f"{la.COOKIE_NAME}={bad}"})[0] == 401, bad
        assert raw(h, p, "GET", "/status", headers={"Cookie": "other=1"})[0] == 401
        assert raw(h, p, "GET", "/status", headers={"Cookie": "; ;=; la_token"})[0] == 401
        # the cookie of ANOTHER launch is worthless here
        other = la.TokenAuth()
    with serve(tp.make_store(tmp_path / "second"), auth=other) as (h2, p2):
        assert raw(h2, p2, "GET", "/status", headers={"Cookie": f"{la.COOKIE_NAME}={cookie}"})[0] == 401


def test_the_token_is_only_redeemable_on_get_slash_and_by_the_right_value() -> None:
    auth = la.TokenAuth("launch-token-value")
    assert auth.redeem("") is None and auth.redeem("launch-token-valuf") is None
    assert auth.redeem("launch-token-valueé") is None            # non-ASCII input must not raise
    cookie = auth.redeem("launch-token-value")
    assert cookie and auth.valid_cookie(cookie) and not auth.valid_cookie(cookie + "x")
    assert not auth.valid_cookie("") and not auth.valid_cookie("héllo")
    assert auth.redeem("launch-token-value") is None                  # one time only
    assert auth.valid_cookie(cookie)                                  # the session survives the exchange
    assert la.TokenAuth().launch_token != la.TokenAuth().launch_token and len(la.TokenAuth().launch_token) >= 40


def test_token_cannot_be_redeemed_by_a_post_or_another_path(tmp_path: Path) -> None:
    store = tp.make_store(tmp_path)
    auth = la.TokenAuth()
    with serve(store, auth=auth) as (h, p):
        assert raw(h, p, "GET", f"/status?token={auth.launch_token}")[0] == 401
        assert post(h, p, "/save", {}, extra={"X-Token": auth.launch_token})[0] == 401
        assert raw(h, p, "POST", f"/?token={auth.launch_token}", headers={
            "Content-Type": "application/json", "Origin": f"http://{h}:{p}"}, body=b"{}")[0] == 401
        assert raw(h, p, "GET", "/status", headers={"Authorization": f"Bearer {auth.launch_token}"})[0] == 401
        redeem(h, p, auth)                                             # the launch token is still unspent


def test_a_full_browser_like_flow_from_the_printed_url(tmp_path: Path) -> None:
    store = tp.make_store(tmp_path)
    auth = la.TokenAuth()
    with serve(store, auth=auth) as (h, p):
        base = f"http://{h}:{p}"
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        with opener.open(f"{base}/?token={auth.launch_token}", timeout=5) as resp:   # follows the 302
            page = resp.read().decode("utf-8")
            assert resp.status == 200 and "token" not in resp.geturl() and "What is thing 1?" in page
        assert [c.name for c in jar] == [la.COOKIE_NAME]
        assert any("HttpOnly" in str(c._rest) or c.has_nonstandard_attr("HttpOnly") for c in jar)
        req = urllib.request.Request(
            f"{base}/save", method="POST", headers={"Content-Type": "application/json", "Origin": base},
            data=json.dumps(tp.payload(1, "cat:A:CQB01", 0, note="saved with the cookie")).encode("utf-8"))
        with opener.open(req, timeout=5) as resp:
            assert resp.status == 200 and json.loads(resp.read())["ok"]
        assert tp.read_rows(store.out)[1][9] == "0"
        fresh = urllib.request.build_opener()                                       # no cookie: no way in
        with pytest.raises(urllib.error.HTTPError) as err:
            fresh.open(f"{base}/?token={auth.launch_token}", timeout=5)
        assert err.value.code == 401


def test_responses_carry_cache_and_sniffing_headers(tmp_path: Path) -> None:
    store = tp.make_store(tmp_path)
    with serve(store) as (h, p):
        for path in ("/", "/export", "/status", "/nope"):
            _, headers, _ = raw(h, p, "GET", path)
            assert headers["cache-control"] == "no-store" and headers["x-content-type-options"] == "nosniff"


# ---------------------------------------------------------------------------
# 1. Host allow-list
# ---------------------------------------------------------------------------
def test_allowed_hosts_for_and_loopback_detection() -> None:
    assert la.allowed_hosts_for("127.0.0.1", 8000) == {"127.0.0.1:8000", "localhost:8000", "[::1]:8000"}
    wild = la.allowed_hosts_for("0.0.0.0", 8000)
    assert wild == {"127.0.0.1:8000", "localhost:8000", "[::1]:8000"}      # a wildcard names nobody
    assert la.allowed_hosts_for("::", 1) == la.allowed_hosts_for("0.0.0.0", 1)
    got = la.allowed_hosts_for("192.0.2.7", 9, extra=["Lab.Internal", " 2001:db8::1 ", ""])
    assert {"192.0.2.7:9", "lab.internal:9", "[2001:db8::1]:9"} <= got and "0.0.0.0:9" not in got
    for host in ("127.0.0.1", "127.9.9.9", "::1", "[::1]", "localhost", "LOCALHOST"):
        assert la.is_loopback_host(host), host
    for host in ("0.0.0.0", "192.168.1.5", "::", "example.org", "", "2001:db8::1", "evil-localhost"):
        assert not la.is_loopback_host(host), host


def test_host_allow_list_blocks_foreign_and_rebound_hosts_on_every_route(tmp_path: Path) -> None:
    store = tp.make_store(tmp_path)
    auth = la.TokenAuth()
    with serve(store, auth=auth, extra_hosts=["lab.internal"]) as (h, p):
        cookie = redeem(h, p, auth)
        ck = {"Cookie": f"{la.COOKIE_NAME}={cookie}"}
        for ok in (f"127.0.0.1:{p}", f"localhost:{p}", f"LOCALHOST:{p}", f"[::1]:{p}", f"lab.internal:{p}",
                   f"LAB.internal:{p}"):
            assert raw(h, p, "GET", "/status", headers={**ck, "Host": ok})[0] == 200, ok
        for bad in (f"evil.example:{p}", f"127.0.0.1:{p + 1}", "127.0.0.1", "localhost", f"lab.internal.evil:{p}",
                    f"x@127.0.0.1:{p}", f"127.0.0.1:{p}.evil.example", f"lab.internal:{p},evil.example", ""):
            for method, path in (("GET", "/"), ("GET", "/export"), ("GET", "/status"), ("GET", "/nope")):
                status, _, body = raw(h, p, method, path, headers={**ck, "Host": bad})
                assert status == 403, (bad, path)
                assert b"VIEW" not in body and b"cell_id" not in body        # the export is not served
            assert post(h, p, "/save", {}, cookie=cookie, extra={"Host": bad})[0] == 403, bad
        # no Host header at all (HTTP/1.0 style) is refused too
        conn = http.client.HTTPConnection(h, p, timeout=5)
        conn.putrequest("GET", "/export", skip_host=True)
        for k, v in ck.items():
            conn.putheader(k, v)
        conn.endheaders()
        assert conn.getresponse().status == 403
        conn.close()
    with serve(store) as (h, p):                                              # no extra host: lab.internal refused
        assert raw(h, p, "GET", "/status", headers={"Host": f"lab.internal:{p}"})[0] == 403


# ---------------------------------------------------------------------------
# 1. POST rules, body cap, timeout
# ---------------------------------------------------------------------------
def test_post_must_be_json_with_a_same_origin_origin(tmp_path: Path) -> None:
    store = tp.make_store(tmp_path)
    cell = store.rows[1][0]
    good = json.dumps(tp.payload(1, cell, 0, note="x")).encode("utf-8")
    with serve(store) as (h, p):
        origin = f"http://{h}:{p}"
        base = {"Content-Type": "application/json", "Origin": origin}

        def attempt(**override: str | None) -> int:
            headers = dict(base)
            for key, value in override.items():
                name = key.replace("_", "-")
                if value is None:
                    headers.pop(name, None)
                else:
                    headers[name] = value
            return raw(h, p, "POST", "/save", headers=headers, body=good)[0]

        # the reviewer's attack: a foreign-origin simple (text/plain) POST
        assert attempt(Content_Type="text/plain", Origin="http://evil.example") == 415
        assert attempt(Content_Type="text/plain") == 415
        assert attempt(Content_Type=None) == 415
        assert attempt(Content_Type="application/x-www-form-urlencoded") == 415
        assert attempt(Content_Type="application/jsonx") == 415
        for origin_bad in (None, "http://evil.example", "null", f"http://{h}:{p + 1}", f"https://{h}:{p}",
                           f"http://localhost:{p}", f"http://{h}:{p}/", f"http://{h}"):
            assert attempt(Origin=origin_bad) == 403, origin_bad
        assert tp.read_rows(store.out)[1][9] == ""                       # nothing was saved by any of them
        assert not Path(str(store.out) + ".audit.jsonl").exists()
        assert attempt(Content_Type="application/json; charset=utf-8") == 200   # the browser's own form
        assert tp.read_rows(store.out)[1][9] == "0"
        # a foreign-origin /ai_use cannot forge a report either
    store2, _, _, out2 = tp.make_packet_store(tmp_path / "packet")
    with serve(store2) as (h, p):
        status, _, _ = raw(h, p, "POST", "/ai_use", headers={"Content-Type": "text/plain", "Origin": "http://evil.example"},
                           body=json.dumps({"used": False}).encode("utf-8"))
        assert status == 415 and not tp.ai_entries(out2)
        assert post(h, p, "/ai_use", {"used": False}, extra={"Origin": "http://evil.example"})[0] == 403
        assert not tp.ai_entries(out2)


def test_post_length_rules_and_the_64kb_body_cap(tmp_path: Path) -> None:
    store = tp.make_store(tmp_path)
    cell = store.rows[1][0]
    assert la.MAX_BODY_BYTES == 64 * 1024
    with serve(store) as (h, p):
        base = {"Content-Type": "application/json", "Origin": f"http://{h}:{p}"}
        # Content-Length missing / garbage / negative / chunked
        conn = http.client.HTTPConnection(h, p, timeout=5)
        conn.putrequest("POST", "/save")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Origin", base["Origin"])
        conn.endheaders()
        assert conn.getresponse().status == 411
        conn.close()
        for bad_length in ("abc", "-5", "1e3", " ", "1" * 13, "0x10", "5 5"):
            assert raw(h, p, "POST", "/save", headers={**base, "Content-Length": bad_length})[0] == 400, bad_length
        # an Arabic-Indic digit is not a length (http.client cannot even send it, so use a raw socket)
        sock = socket.create_connection((h, p), timeout=5)
        sock.sendall((f"POST /save HTTP/1.1\r\nHost: {h}:{p}\r\nContent-Type: application/json\r\n"
                      f"Origin: {base['Origin']}\r\n").encode("ascii") + "Content-Length: ٣\r\n\r\n".encode("utf-8"))
        assert b" 400 " in sock.recv(4096).split(b"\r\n")[0]
        sock.close()
        assert raw(h, p, "POST", "/save", headers={**base, "Transfer-Encoding": "chunked"}, body=b"0\r\n\r\n")[0] == 411
        # Transfer-Encoding next to a Content-Length (the request-smuggling shape) is refused as well
        assert raw(h, p, "POST", "/save", headers={**base, "Transfer-Encoding": "chunked", "Content-Length": "2"},
                   body=b"{}")[0] == 411
        # too big: refused on the declared length, without waiting for (or reading) the body
        sock = socket.create_connection((h, p), timeout=5)
        sock.sendall((f"POST /save HTTP/1.1\r\nHost: {h}:{p}\r\nContent-Type: application/json\r\n"
                      f"Origin: {base['Origin']}\r\nContent-Length: 8000000\r\n\r\n").encode("ascii"))
        reply = sock.recv(4096)
        assert reply.startswith(b"HTTP/1.0 413") or reply.startswith(b"HTTP/1.1 413"), reply[:40]
        sock.close()
        status, _, body = raw(h, p, "POST", "/save", headers=base, body=b"x" * (la.MAX_BODY_BYTES + 1))
        assert status == 413 and b"65536" in body
        # exactly at the cap the body is read and judged on its content (a 400 here, not a 413)
        pad = json.dumps({"row": 1, "cell_id": cell, "note": "n", "pad": ""}).encode("utf-8")
        padded = pad.replace(b'"pad": ""', b'"pad": "' + b"x" * (la.MAX_BODY_BYTES - len(pad)) + b'"')
        assert len(padded) == la.MAX_BODY_BYTES
        status, _, body = raw(h, p, "POST", "/save", headers=base, body=padded)
        assert status == 400 and b"A:" in body                       # reached validation: A is missing
        # a body shorter than its Content-Length is not accepted as complete
        sock = socket.create_connection((h, p), timeout=5)
        sock.sendall((f"POST /save HTTP/1.1\r\nHost: {h}:{p}\r\nContent-Type: application/json\r\n"
                      f"Origin: {base['Origin']}\r\nContent-Length: 50\r\n\r\n{{\"row\": 1}}").encode("ascii"))
        sock.shutdown(socket.SHUT_WR)
        assert b" 400 " in sock.recv(4096).split(b"\r\n")[0]
        sock.close()
    assert tp.read_rows(store.out)[1][9] == "" and not Path(str(store.out) + ".audit.jsonl").exists()


def test_a_stalled_client_is_dropped_after_the_socket_timeout(tmp_path: Path) -> None:
    assert la.Handler.timeout == la.HTTP_TIMEOUT_S == 30
    store = tp.make_store(tmp_path)
    with serve(store, timeout=0.4) as (h, p):
        # 1. never finishes the request line
        sock = socket.create_connection((h, p), timeout=10)
        sock.sendall(b"GET / HT")
        started = time.monotonic()
        assert sock.recv(100) == b""                                   # the server closed it
        assert time.monotonic() - started < 5
        sock.close()
        # 2. sends headers promising a body, then stalls mid-body
        sock = socket.create_connection((h, p), timeout=10)
        sock.sendall((f"POST /save HTTP/1.1\r\nHost: {h}:{p}\r\nContent-Type: application/json\r\n"
                      f"Origin: http://{h}:{p}\r\nContent-Length: 100\r\n\r\n{{\"row\"").encode("ascii"))
        started = time.monotonic()
        assert sock.recv(100) == b""
        assert time.monotonic() - started < 5
        sock.close()
        assert raw(h, p, "GET", "/status")[0] == 200                   # the server itself is fine
    server_default = la.make_server(store, ("127.0.0.1", 0))
    assert server_default.RequestHandlerClass.timeout == 30
    server_default.server_close()


# ---------------------------------------------------------------------------
# 1. CLI: token on by default, no-token only on loopback, printed one-time URL
# ---------------------------------------------------------------------------
class DummyServer:
    server_address = ("127.0.0.1", 4321)

    def serve_forever(self) -> None:
        raise KeyboardInterrupt

    def server_close(self) -> None:
        pass


def cli_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, packet: bool = False):
    seen: dict[str, Any] = {}
    # main() installs SIGTERM/SIGHUP handlers and an atexit hook: keep both out of the pytest process
    monkeypatch.setattr(la.signal, "signal", lambda *a, **k: None)
    monkeypatch.setattr(la.atexit, "register", lambda *a, **k: None)

    def fake_make_server(store, addr, ttl_dir=None, **kwargs):
        seen.update(addr=addr, **kwargs)
        return DummyServer()

    monkeypatch.setattr(la, "make_server", fake_make_server)
    if packet:
        sheet, vdir = tp.make_packet_sheet(tmp_path), tp.make_packet_views(tmp_path)
        base = ["--packet", "--sheet", str(sheet), "--views", str(vdir)]
    else:
        base = ["--sheet", str(tp.make_sheet(tmp_path)), "--views", str(tp.make_views(tmp_path))]
    return seen, base + ["--out", str(tmp_path / "labels" / "w.csv")]


@pytest.mark.parametrize("packet", [False, True])
def test_cli_refuses_a_non_loopback_host_without_the_token(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                           capsys: pytest.CaptureFixture[str], packet: bool) -> None:
    seen, argv = cli_env(tmp_path, monkeypatch, packet)
    for host in ("0.0.0.0", "192.0.2.7", "::", "example.org"):
        assert la.main([*argv, "--host", host, "--no-token"]) == 1, host
        assert "토큰 인증을 끌 수 없습니다" in capsys.readouterr().err
    assert not seen and not (tmp_path / "labels").exists()             # refused before anything was created


@pytest.mark.parametrize("packet", [False, True])
def test_cli_token_is_on_by_default_and_the_one_time_url_is_printed(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], packet: bool) -> None:
    seen, argv = cli_env(tmp_path, monkeypatch, packet)
    assert la.main([*argv, "--host", "0.0.0.0", "--allow-host", "lab.internal", "--port", "0"]) == 0
    out = capsys.readouterr().out
    auth = seen["auth"]
    assert isinstance(auth, la.TokenAuth) and seen["extra_hosts"] == ["lab.internal"]
    assert f"http://lab.internal:4321/?token={auth.launch_token}" in out        # an off-box URL, one-time token
    assert "한 번만 쓸 수 있습니다" in out and "token=off" not in out
    (tmp_path / "labels" / "w.csv.lock").unlink()
    # loopback default: still token auth, the URL names the bind address
    assert la.main([*argv, "--host", "127.0.0.1"]) == 0
    assert re.search(r"http://127\.0\.0\.1:4321/\?token=[A-Za-z0-9_-]{40,}", capsys.readouterr().out)
    # a wildcard bind with no --allow-host prints a loopback URL (the only Host that would be accepted)
    assert la.main([*argv, "--host", "0.0.0.0"]) == 0
    assert "http://127.0.0.1:4321/?token=" in capsys.readouterr().out


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_cli_no_token_is_allowed_on_loopback_only_and_prints_a_plain_url(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], host: str) -> None:
    seen, argv = cli_env(tmp_path, monkeypatch)
    assert la.main([*argv, "--host", host, "--no-token"]) == 0
    out = capsys.readouterr().out
    assert seen["auth"] is None and "?token=" not in out and "token=off" in out
    shown = f"[{host}]" if ":" in host else host
    assert f"http://{shown}:4321/" in out


# ---------------------------------------------------------------------------
# 4. atomic, durable saves
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("packet", [False, True])
def test_a_failed_csv_write_leaves_memory_and_disk_alike(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                         packet: bool) -> None:
    store = tp.make_packet_store(tmp_path)[0] if packet else tp.make_store(tmp_path)
    save = tp.pp if packet else tp.payload
    cell = store.rows[1][0]
    disk_before, row_before = store.out.read_bytes(), list(store.rows[1])
    real = la._write_rows_atomic

    def boom(out: Path, rows: list[list[str]]) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(la, "_write_rows_atomic", boom)
    with pytest.raises(OSError):
        store.save(save(1, cell, 1, span="anchor", note="n"))
    monkeypatch.setattr(la, "_write_rows_atomic", real)
    assert store.out.read_bytes() == disk_before and store.rows[1] == row_before   # memory still matches disk
    assert store.labeled_count() == 0 and store.first_unlabeled() == 1
    # the audit line was written first, so the failed attempt is on record (an orphan, never a lost label)
    assert len(tp.audit_entries(store.out)) == 1
    # the retry needs no edit reason (the row was never labeled) and is stored once
    code, _ = store.save(save(1, cell, 1, span="anchor", note="n"))
    assert code == 200 and tp.read_rows(store.out)[1][9] == "1" and store.rows[1][9] == "1"
    assert len(tp.audit_entries(store.out)) == 2
    assert not [p for p in store.out.parent.iterdir() if ".tmp" in p.name]


def test_a_failed_audit_write_changes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = tp.make_store(tmp_path)
    disk_before, row_before = store.out.read_bytes(), list(store.rows[1])
    real = la._append_text

    def selective(path: Path, line: str) -> None:
        if str(path).endswith(".audit.jsonl"):
            raise OSError("audit disk full")
        real(path, line)

    monkeypatch.setattr(la, "_append_text", selective)
    with pytest.raises(OSError):
        store.save(tp.payload(1, "cat:A:CQB01", 0, note="x"))
    assert store.out.read_bytes() == disk_before and store.rows[1] == row_before
    assert not Path(str(store.out) + ".audit.jsonl").exists()
    assert store.last_save_ts is None


@pytest.mark.parametrize("packet", [False, True])
def test_a_write_failure_is_a_json_500_and_the_retry_works(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                           packet: bool) -> None:
    store = tp.make_packet_store(tmp_path)[0] if packet else tp.make_store(tmp_path)
    save = tp.pp if packet else tp.payload
    cell, disk, real = store.rows[1][0], store.out.read_bytes(), la._write_rows_atomic
    monkeypatch.setattr(la, "_write_rows_atomic", lambda out, rows: (_ for _ in ()).throw(OSError("disk full: /x")))
    with serve(store) as (h, p):
        status, _, body = post(h, p, "/save", save(1, cell, 0, note="x"))
        assert status == 500 and json.loads(body) == {"ok": False, "error": la.WRITE_FAILED_MSG}
        assert b"disk full" not in body                                   # no server detail leaks to the page
        assert store.out.read_bytes() == disk and store.rows[1][9] == ""
        monkeypatch.setattr(la, "_write_rows_atomic", real)
        assert post(h, p, "/save", save(1, cell, 0, note="x"))[0] == 200  # the server survived; the retry works
    assert tp.read_rows(store.out)[1][9] == "0"


def test_a_failed_ai_use_write_is_a_500_and_leaves_no_gap_in_report_seq(tmp_path: Path,
                                                                        monkeypatch: pytest.MonkeyPatch) -> None:
    store, _, _, out = tp.make_packet_store(tmp_path)
    real = la._append_text
    monkeypatch.setattr(la, "_append_text", lambda path, line: (_ for _ in ()).throw(OSError("full")))
    with serve(store) as (h, p):
        status, _, body = post(h, p, "/ai_use", {"used": False})
        assert status == 500 and json.loads(body)["error"] == la.WRITE_FAILED_MSG
        assert (store.report_seq, store.ai_use, store.sitting_n) == (0, None, 1)   # nothing half-recorded
        monkeypatch.setattr(la, "_append_text", real)
        assert post(h, p, "/ai_use", {"used": False})[0] == 200
        assert post(h, p, "/ai_use", {"skipped": True})[0] == 200
    assert [(e["report_seq"], e["used"]) for e in tp.ai_entries(out)] == [(1, "no"), (2, "not recorded")]


def test_save_order_is_audit_then_csv_then_edit_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = tp.make_store(tmp_path)
    calls: list[str] = []
    real_append, real_write = la._append_text, la._write_rows_atomic

    def spy_append(path: Path, line: str) -> None:
        name = Path(path).name
        calls.append("audit" if name.endswith(".audit.jsonl") else
                     "edit_log" if name.endswith(".session_log.txt") else name)
        real_append(path, line)

    def spy_write(out: Path, rows: list[list[str]]) -> None:
        calls.append("csv")
        real_write(out, rows)

    store.save(tp.payload(1, "cat:A:CQB01", 1, span="anchor", note="n"))          # first save, unspied
    monkeypatch.setattr(la, "_append_text", spy_append)
    monkeypatch.setattr(la, "_write_rows_atomic", spy_write)
    store.save(tp.payload(1, "cat:A:CQB01", 0, note="n2", edit_reason="why"))
    assert calls == ["audit", "csv", "edit_log"]


@pytest.mark.skipif(not Path("/proc/self/fd").exists(), reason="needs /proc to name the synced file")
def test_saves_fsync_the_audit_line_the_temp_file_and_then_the_directory(tmp_path: Path,
                                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    store = tp.make_store(tmp_path)
    synced: list[str] = []
    real_fsync = os.fsync

    def spy(fd: int) -> None:
        try:
            synced.append(os.readlink(f"/proc/self/fd/{fd}"))
        except OSError:
            synced.append("?")
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", spy)
    store.save(tp.payload(1, "cat:A:CQB01", 0, note="x"))
    names = [Path(t).name if Path(t).name else t for t in synced]
    assert any(n.endswith(".audit.jsonl") for n in names)
    tmp_index = next(i for i, t in enumerate(synced) if ".tmp" in Path(t).name)      # the CSV temp file
    dir_index = next(i for i, t in enumerate(synced) if Path(t) == store.out.parent)  # then the directory
    assert tmp_index < dir_index
    assert next(i for i, t in enumerate(synced) if t.endswith(".audit.jsonl")) < tmp_index   # audit before CSV
    assert not [p for p in store.out.parent.iterdir() if ".tmp" in p.name]


def test_a_failure_while_replacing_removes_the_temp_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "w.csv"
    out.write_text("old", encoding="utf-8")
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("rename failed")))
    with pytest.raises(OSError):
        la._write_rows_atomic(out, [["a", "b"]])
    monkeypatch.undo()
    assert out.read_text(encoding="utf-8") == "old" and [p.name for p in tmp_path.iterdir()] == ["w.csv"]


# ---------------------------------------------------------------------------
# 5. log-line integrity and field caps
# ---------------------------------------------------------------------------
FORGE = ('x\nAI_USE {"phase":"end","used":"no","tool":"","approx_cells":0,"how":"answered","sitting_id":"forged"}\n'
         "SESSION start=2020-01-01T00:00:00+09:00 pid=1 session_id=forged\r\n"
         "SESSION end=2020-01-01T00:00:00+09:00 pid=1 saved=999" + LS + "tail" + PS + NEL + "end")


@pytest.mark.parametrize("packet", [False, True])
def test_an_edit_reason_cannot_forge_log_records(tmp_path: Path, packet: bool) -> None:
    store = tp.make_packet_store(tmp_path)[0] if packet else tp.make_store(tmp_path)
    save = tp.pp if packet else tp.payload
    cell = store.rows[1][0]
    store.save(save(1, cell, 1, span="anchor", note="n"))
    store.save(save(1, cell, 0, note="n2", edit_reason=FORGE))
    text = Path(str(store.out) + ".session_log.txt").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert text.count("\n") == len(lines)                              # no break char survived inside a record
    assert len([l for l in lines if l.startswith("SESSION start")]) == 1
    assert not any(l.startswith("SESSION end") or l.startswith("AI_USE") for l in lines)
    edit = next(l for l in lines if l.startswith("EDIT "))
    match = re.match(r'^EDIT (\S+) (\d)->(\d) reason=(".*") ts=(\S+)$', edit)
    assert match is not None and match.group(1) == cell
    assert json.loads(match.group(4)) == FORGE                         # the reason is stored whole, as JSON
    assert tp.audit_entries(store.out)[1]["edit_reason"] == FORGE      # (the audit line is JSON already)
    if packet:
        assert tp.ai_entries(store.out) == []                          # no forged report, no real one yet


def test_one_line_escapes_every_line_break_and_keeps_json_lines_parseable() -> None:
    for ch in ("\n", "\r", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e", NEL, LS, PS):
        out = la.one_line(f"a{ch}b")
        assert out == "a\\u%04xb" % ord(ch) and len(out.splitlines()) == 1
    assert la.one_line("plain 텍스트 \t tab") == "plain 텍스트 \t tab"
    record = {"note": "x" + LS + NEL + "y", "n": 1}
    line = la.one_line(json.dumps(record, ensure_ascii=False))
    assert len(line.splitlines()) == 1 and json.loads(line) == record


def test_append_text_writes_one_physical_line_and_flushes(tmp_path: Path) -> None:
    path = tmp_path / "log.txt"
    la._append_text(path, "A\r\nB" + LS + "C")
    la._append_text(path, "D")
    data = path.read_bytes()
    assert data == b"A\\u000d\\u000aB\\u2028C\nD\n"


@pytest.mark.parametrize("packet", [False, True])
def test_label_text_fields_are_capped(tmp_path: Path, packet: bool) -> None:
    store = tp.make_packet_store(tmp_path)[0] if packet else tp.make_store(tmp_path)
    save = tp.pp if packet else tp.payload
    cell = store.rows[1][0]
    disk = store.out.read_bytes()
    for kwargs, field in (({"span": "s" * (la.MAX_SPAN_CHARS + 1), "note": "n"}, "span"),
                          ({"span": "ok", "note": "n" * (la.MAX_NOTE_CHARS + 1)}, "note")):
        with pytest.raises(la.SaveError, match=field):
            store.save(save(1, cell, 1, **kwargs))
    assert store.out.read_bytes() == disk and not Path(str(store.out) + ".audit.jsonl").exists()
    assert store.save(save(1, cell, 1, span="s" * la.MAX_SPAN_CHARS, note="n" * la.MAX_NOTE_CHARS))[0] == 200
    with pytest.raises(la.SaveError, match="edit_reason"):
        store.save(save(1, cell, 0, note="x", edit_reason="r" * (la.MAX_EDIT_REASON_CHARS + 1)))
    assert store.save(save(1, cell, 0, note="x", edit_reason="r" * la.MAX_EDIT_REASON_CHARS))[0] == 200
    # a browser's JSON.stringify keeps non-ASCII text as raw UTF-8 (at most 4 bytes a character), so a
    # payload whose three free-text fields are all at their caps still fits the 64 KB request cap
    astral = chr(0x1D49C)
    worst = len(json.dumps({"span": astral * la.MAX_SPAN_CHARS, "note": astral * la.MAX_NOTE_CHARS,
                            "edit_reason": astral * la.MAX_EDIT_REASON_CHARS},
                           ensure_ascii=False).encode("utf-8"))
    assert worst < la.MAX_BODY_BYTES


# ---------------------------------------------------------------------------
# 8. single-writer lock and clean shutdown
# ---------------------------------------------------------------------------
def test_a_second_writer_on_the_same_out_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "labels" / "w.csv"
    out.parent.mkdir()
    first = la.acquire_out_lock(out)
    assert first is not None and Path(str(out) + ".lock").read_text(encoding="utf-8").strip() == str(os.getpid())
    with pytest.raises(la.OutLocked):
        la.acquire_out_lock(out)
    # the CLI refuses to start (exit 1) and does not touch the working CSV
    sheet, views = tp.make_sheet(tmp_path), tp.make_views(tmp_path)
    assert la.main(["--sheet", str(sheet), "--views", str(views), "--out", str(out)]) == 1
    assert "이미" in capsys.readouterr().err and not out.exists()
    # ... and so does a separate PROCESS
    run = subprocess.run([sys.executable, str(HARNESS / "label_assist.py"), "--sheet", str(sheet), "--views",
                          str(views), "--out", str(out), "--port", "0"], capture_output=True, text=True, timeout=60)
    assert run.returncode == 1 and "이미" in run.stderr and not out.exists()
    first.close()                                                      # releasing the lock lets the next one in
    second = la.acquire_out_lock(out)
    assert second is not None
    second.close()


def reset_sighup() -> None:
    """Child-side hook: a parent that ignores SIGHUP (nohup, a CI runner) would leave this server with the
    inherited "ignore" -- label_assist keeps that on purpose -- and the hang-up tests could not exercise the
    handler. The test of the ignored case starts its own server (below) with SIGHUP ignored explicitly."""
    signal.signal(signal.SIGHUP, signal.SIG_DFL)


def start_server_process(tmp_path: Path, packet: bool) -> tuple[subprocess.Popen, Path, int, str]:
    if packet:
        sheet, vdir = tp.make_packet_sheet(tmp_path), tp.make_packet_views(tmp_path)
        argv = ["--packet", "--sheet", str(sheet), "--views", str(vdir)]
    else:
        argv = ["--sheet", str(tp.make_sheet(tmp_path)), "--views", str(tp.make_views(tmp_path))]
    out = tmp_path / "labels" / "w.csv"
    proc = subprocess.Popen([sys.executable, "-u", str(HARNESS / "label_assist.py"), *argv, "--out", str(out),
                             "--port", "0"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                            preexec_fn=reset_sighup)
    watchdog = threading.Timer(90, proc.kill)
    watchdog.start()
    try:
        first = proc.stdout.readline()                                  # blocks until the server is up
    finally:
        watchdog.cancel()
    match = re.search(r"http://127\.0\.0\.1:(\d+)/\?token=([A-Za-z0-9_-]+)", first)
    assert match, (first[:60], proc.poll())
    return proc, out, int(match.group(1)), match.group(2)


@pytest.mark.parametrize("packet", [False, True])
@pytest.mark.parametrize("sig", [signal.SIGHUP, signal.SIGTERM])
def test_hangup_and_terminate_end_the_session_cleanly(tmp_path: Path, packet: bool, sig: signal.Signals) -> None:
    proc, out, _port, _token = start_server_process(tmp_path, packet)
    try:
        proc.send_signal(sig)
        assert proc.wait(timeout=60) == 0                              # a graceful exit, not death by signal
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.stdout.close()
        proc.stderr.close()
    lines = tp.log_lines(out)
    assert lines[0].startswith("SESSION start=") and lines[-1].startswith("SESSION end=")
    assert "saved=0" in lines[-1]
    if packet:
        reports = tp.ai_entries(out)
        assert len(reports) == 1 and (reports[0]["used"], reports[0]["how"]) == ("not recorded", "unanswered")
        assert lines[-2].startswith("AI_USE ")
    else:
        assert not any(l.startswith("AI_USE") for l in lines)


def test_a_hangup_after_a_save_reports_the_unreported_sitting(tmp_path: Path) -> None:
    proc, out, port, token = start_server_process(tmp_path, packet=True)
    try:
        # the browser's way in: the printed one-time URL, then a save carrying the cookie it got
        status, headers, _ = raw("127.0.0.1", port, "GET", f"/?token={token}")
        assert status == 302
        cookie = re.match(rf"{la.COOKIE_NAME}=([^;]+);", headers["set-cookie"]).group(1)  # type: ignore[union-attr]
        cell = tp.PACKET_ROWS[0][0]
        status, _, body = post("127.0.0.1", port, "/save", tp.pp(1, cell, 0, note="x", dwell_ms=4200), cookie=cookie)
        assert status == 200, body
        proc.send_signal(signal.SIGHUP)                                # the terminal closes without an end form
        assert proc.wait(timeout=60) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.stdout.close()
        proc.stderr.close()
    lines = tp.log_lines(out)
    assert lines[-1].startswith("SESSION end=") and "saved=1" in lines[-1]
    report = tp.ai_entries(out)[-1]
    assert (report["used"], report["how"], report["saves_since_last_report"]) == ("not recorded", "unanswered", 1)
    audit = tp.audit_entries(out)
    assert len(audit) == 1 and audit[0]["dwell_ms"] == 4200
    assert audit[0]["sitting_id"] == report["sitting_id"] and lines[-1].endswith(f"sitting_id={report['sitting_id']}")


@pytest.mark.skipif(shutil.which("sh") is None, reason="needs a POSIX shell to start the server with SIGHUP ignored")
def test_a_server_started_with_sighup_ignored_keeps_running_like_nohup(tmp_path: Path) -> None:
    sheet, views = tp.make_sheet(tmp_path), tp.make_views(tmp_path)
    out = tmp_path / "labels" / "w.csv"
    proc = subprocess.Popen(
        ["sh", "-c", 'trap "" HUP; exec "$0" "$@"', sys.executable, "-u", str(HARNESS / "label_assist.py"),
         "--sheet", str(sheet), "--views", str(views), "--out", str(out), "--port", "0"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    watchdog = threading.Timer(90, proc.kill)
    watchdog.start()
    try:
        first = proc.stdout.readline()
        match = re.search(r"http://127\.0\.0\.1:(\d+)/\?token=([A-Za-z0-9_-]+)", first)
        assert match, first[:60]
        proc.send_signal(signal.SIGHUP)                              # the terminal closes ...
        status, _, _ = raw("127.0.0.1", int(match.group(1)), "GET", f"/?token={match.group(2)}")
        assert status == 302 and proc.poll() is None                 # ... and the server is still serving
        proc.send_signal(signal.SIGTERM)                             # SIGTERM still ends it cleanly
        assert proc.wait(timeout=60) == 0
    finally:
        watchdog.cancel()
        if proc.poll() is None:
            proc.kill()
        proc.stdout.close()
        proc.stderr.close()
    assert tp.log_lines(out)[-1].startswith("SESSION end=")


# ---------------------------------------------------------------------------
# 3. the repository guard knows the main checkout and every worktree
# ---------------------------------------------------------------------------
def git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args], cwd=cwd,
                   check=True, capture_output=True, text=True)


@pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
def test_repo_roots_name_the_main_checkout_and_every_worktree(tmp_path: Path) -> None:
    main = tmp_path / "main"
    main.mkdir()
    git(["init", "-q"], main)
    (main / "f").write_text("x", encoding="utf-8")
    git(["add", "f"], main)
    git(["commit", "-qm", "x"], main)
    wt1, wt2 = tmp_path / "wt1", tmp_path / "deep" / "wt2"
    git(["worktree", "add", "-q", str(wt1), "-b", "b1"], main)
    git(["worktree", "add", "-q", str(wt2), "-b", "b2"], main)
    la._repo_roots_cached.cache_clear()
    expected = {main.resolve(), wt1.resolve(), wt2.resolve()}
    (wt1 / "sub").mkdir()
    for start in (wt1, wt1 / "sub", main, wt2):
        assert expected <= set(la.repo_roots(start=start)), start
    # the old lookup from inside a worktree found only that worktree: the main checkout slipped through
    assert la.detect_repo_root(wt1 / "x") == wt1 and main not in {la.detect_repo_root(wt1 / "x")}
    roots = la.repo_roots(start=wt1)
    for inside in (main / "labels" / "out.csv", main / "sealed", wt1 / "x" / "o.csv", wt2 / "o.csv",
                   main / ".git" / "objects" / "x", main):
        with pytest.raises(la.OutInsideRepo):
            la.check_out_path(inside, roots=roots)
    la.check_out_path(tmp_path / "elsewhere" / "o.csv", roots=roots)
    # a sibling directory whose name merely starts like a root is not inside it
    la.check_out_path(tmp_path / "main_other" / "o.csv", roots=roots)


def test_the_real_checkouts_are_refused_for_out_and_sealed_paths() -> None:
    roots = la.repo_roots()
    assert roots and Path(la.__file__).resolve().is_relative_to(roots[0]) or any(
        Path(la.__file__).resolve().is_relative_to(r) for r in roots)
    for root in roots:
        with pytest.raises(la.OutInsideRepo):
            la.check_out_path(root / "never_created" / "out.csv")
        with pytest.raises(la.OutInsideRepo):
            la.check_out_path(root)
    if shutil.which("git"):                                            # the main checkout, from any worktree
        common = subprocess.run(["git", "-C", str(HARNESS), "rev-parse", "--git-common-dir"],
                                capture_output=True, text=True, check=True).stdout.strip()
        main_root = (HARNESS / common).resolve().parent if not os.path.isabs(common) else Path(common).parent
        with pytest.raises(la.OutInsideRepo):
            la.check_out_path(main_root / "labels_must_not_go_here" / "w.csv")


def test_repo_roots_fall_back_to_the_git_directory_lookup_without_git(tmp_path: Path,
                                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "plain"
    (repo / ".git").mkdir(parents=True)
    (repo / "sub").mkdir()
    la._repo_roots_cached.cache_clear()
    monkeypatch.setattr(la, "_git", lambda *a, **k: None)             # git missing or not a repository
    assert la.repo_roots(start=repo / "sub") == [repo.resolve()]
    la._repo_roots_cached.cache_clear()
