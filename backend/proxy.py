"""backend/proxy.py — named URLs and password-protected shares.

An ASGI middleware in front of the dashboard that routes by Host header:

* ``<app-id>.localhost:<manager-port>``  → the running app (named URL)
* ``<app-id>.share.localhost``           → the app, behind a password page
  (used by protected public share links; cloudflared sends this Host)
* anything else                          → the Homeport dashboard / API

Browsers and the OS resolve every ``*.localhost`` name to this computer, so
named URLs need no hosts-file edits, DNS or accounts. HTTP is streamed both
ways and WebSockets (dev-server live reload) are proxied too.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import html
import re
import time
from typing import Callable, Optional
from urllib.parse import parse_qs, quote

import httpx

__all__ = ["HostProxyMiddleware", "named_host"]

# Wired by main.py
get_running_port: Optional[Callable[[str], Optional[int]]] = None
app_exists: Optional[Callable[[str], bool]] = None
# The page a single-file app opens on ("about.html"): "/" redirects there.
get_entry: Optional[Callable[[str], Optional[str]]] = None
tunnels = None  # share_routes.tunnels

_HOP = {
    b"connection", b"keep-alive", b"proxy-authenticate", b"proxy-authorization",
    b"te", b"trailer", b"trailers", b"transfer-encoding", b"upgrade", b"host",
}
_COOKIE = "homeport_share"
_LOGIN_PATH = "/__homeport/login"


_MAX_REWRITE = 8 * 1024 * 1024
_TEXT_TYPES = ("text/html", "text/css", "javascript", "application/json", "application/ld+json",
               "application/xml", "text/xml", "image/svg+xml", "application/manifest+json", "text/plain")


def _localhost_swaps(port: int, public_origin: str) -> list:
    """(old, new) byte pairs that turn the app's own localhost address into
    the address the visitor used — plain, protocol-relative and JSON-escaped."""
    public_origin = public_origin.rstrip("/")
    host = public_origin.split("://", 1)[-1]
    pairs = []
    for local in (f"localhost:{port}", f"127.0.0.1:{port}", f"[::1]:{port}", f"0.0.0.0:{port}"):
        pairs += [
            (f"http://{local}", public_origin),
            (f"https://{local}", public_origin),
            (f"http:\\/\\/{local}", public_origin.replace("/", "\\/")),
            (f"//{local}", f"//{host}"),
        ]
    table = {a.encode(): b.encode() for a, b in pairs}
    # longest first, and the port must end there (8000 must not match 80001)
    pattern = re.compile(b"(" + b"|".join(re.escape(k) for k in sorted(table, key=len, reverse=True)) + b")(?![0-9])")
    return [pattern, table]


def _apply(data: bytes, swaps: list) -> bytes:
    pattern, table = swaps
    return pattern.sub(lambda m: table[m.group(1)], data)


def _rewritable(resp: "httpx.Response", method: str) -> bool:
    if method == "HEAD" or resp.status_code in (204, 304):
        return False
    ctype = resp.headers.get("content-type", "").lower()
    if "event-stream" in ctype or not any(t in ctype for t in _TEXT_TYPES):
        return False
    if resp.headers.get("content-encoding", "identity").lower() not in ("", "identity"):
        return False
    length = resp.headers.get("content-length")
    return not (length and length.isdigit() and int(length) > _MAX_REWRITE)


def named_host(app_id: str, manager_port: int) -> str:
    return f"{app_id}.localhost:{manager_port}"


def _split_host(raw: str) -> tuple:
    host = (raw or "").strip().lower()
    if host.startswith("["):
        return host, ""
    name, _, port = host.partition(":")
    return name, port


def _route(host_header: str) -> Optional[tuple]:
    """('app'|'share', app_id) for proxied hosts, else None."""
    name, _ = _split_host(host_header)
    if not name.endswith(".localhost"):
        return None
    label = name[: -len(".localhost")]
    if label.endswith(".share"):
        app_id = label[: -len(".share")]
        return ("share", app_id) if app_id and "." not in app_id else None
    if not label or "." in label:
        return None
    return ("app", label)


def _token(secret: str, app_id: str) -> str:
    return hmac.new(secret.encode(), app_id.encode(), hashlib.sha256).hexdigest()


def _page(title: str, body: str, status: int = 200) -> tuple:
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(title)}</title>
<style>
:root{{--bg:#f3f3f4;--panel:#fff;--line:#e6e6e9;--text:#111214;--muted:#6b6b73;--ink:#111214;--on:#fff}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0c0c0e;--panel:#141416;--line:#26262b;--text:#f4f4f5;--muted:#a1a1aa;--ink:#f4f4f5;--on:#0b0b0d}}}}
*{{box-sizing:border-box}}body{{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--text);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;padding:16px}}
.card{{width:min(380px,100%);background:var(--panel);border:1px solid var(--line);border-radius:22px;padding:28px}}
h1{{font-size:20px;margin:14px 0 4px}}p{{margin:0 0 18px;color:var(--muted);font-size:14px}}
input{{width:100%;height:44px;padding:0 16px;border-radius:999px;border:1px solid var(--line);background:var(--bg);color:var(--text);font:inherit}}
button{{width:100%;height:44px;margin-top:10px;border:0;border-radius:999px;background:var(--ink);color:var(--on);font:600 15px inherit;cursor:pointer}}
.err{{color:#dc2626;font-size:13px;margin:8px 0 0}}.foot{{margin-top:18px;font-size:12px;color:var(--muted);text-align:center}}
svg{{width:36px;height:36px}}
</style></head><body><div class="card">
<svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="31" fill="currentColor"/><circle cx="32" cy="32" r="16" fill="none" stroke="var(--panel)" stroke-width="6"/><path d="M32 32 L40.5 23.5" stroke="var(--panel)" stroke-width="6" stroke-linecap="round"/></svg>
{body}<div class="foot">Shared with Homeport</div></div></body></html>"""
    return status, doc.encode("utf-8")


async def _send_page(send, status: int, content: bytes, extra_headers: Optional[list] = None) -> None:
    headers = [(b"content-type", b"text/html; charset=utf-8"), (b"cache-control", b"no-store"),
               (b"content-length", str(len(content)).encode())]
    await send({"type": "http.response.start", "status": status, "headers": headers + (extra_headers or [])})
    await send({"type": "http.response.body", "body": content})


class HostProxyMiddleware:
    def __init__(self, app):
        self.app = app
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(None, connect=10.0),
                                             follow_redirects=False, trust_env=False)
        return self._client

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        headers = {k.lower(): v for k, v in scope.get("headers") or []}
        host = headers.get(b"host", b"").decode("latin-1")
        route = _route(host)
        if route is None:
            return await self.app(scope, receive, send)

        kind, app_id = route
        if kind == "share":
            granted = await self._authorize_share(scope, receive, send, app_id, headers)
            if granted is None:
                return
            port, public_origin = granted
        else:
            if app_exists is None or not app_exists(app_id):
                if scope["type"] == "http":
                    st, body = _page("Not found", f"<h1>No app called “{html.escape(app_id)}”</h1>"
                                     "<p>Check the name in the Homeport dashboard.</p>", 404)
                    await _send_page(send, st, body)
                return
            port = get_running_port(app_id) if get_running_port else None
            if not port:
                if scope["type"] == "http":
                    st, body = _page("Not running", f"<h1>{html.escape(app_id)} isn’t running</h1>"
                                     "<p>Start it from the Homeport dashboard, then reload this page.</p>", 503)
                    await _send_page(send, st, body)
                return
            public_origin = "http://" + host

        entry = get_entry(app_id) if get_entry else None
        if (entry and scope["type"] == "http" and scope.get("path") == "/"
                and entry.lower() not in ("index.html", "index.htm", "index.php")):
            location = "/" + quote(entry)
            await send({"type": "http.response.start", "status": 302,
                        "headers": [(b"location", location.encode("latin-1")), (b"content-length", b"0"),
                                    (b"cache-control", b"no-store")]})
            await send({"type": "http.response.body", "body": b""})
            return

        if scope["type"] == "websocket":
            await self._proxy_ws(scope, receive, send, int(port))
        else:
            await self._proxy_http(scope, receive, send, int(port), public_origin)

    # ------------------------------------------------------------------
    # password-protected shares
    # ------------------------------------------------------------------
    async def _authorize_share(self, scope, receive, send, app_id, headers) -> Optional[tuple]:
        """(port, public_origin) when the visitor may pass, else None (a page
        was sent: closed link or password form)."""
        info = tunnels.share_info(app_id) if tunnels is not None else None
        if info is None:
            if scope["type"] == "http":
                st, body = _page("Link closed", "<h1>This link is closed</h1>"
                                 "<p>The owner stopped sharing this app or the link expired.</p>", 410)
                await _send_page(send, st, body)
            return None
        port = info["port"]
        public_origin = (info.get("url") or "").rstrip("/") or "https://" + app_id + ".share.localhost"
        if not info["protected"]:
            return port, public_origin
        secret = info["secret"]
        expected = _token(secret, app_id)
        cookies = headers.get(b"cookie", b"").decode("latin-1")
        jar = dict(part.strip().split("=", 1) for part in cookies.split(";") if "=" in part)
        if hmac.compare_digest(jar.get(_COOKIE, ""), expected):
            return port, public_origin
        if scope["type"] != "http":
            return None

        if scope["path"] == _LOGIN_PATH and scope["method"] == "POST":
            body = b""
            while True:
                msg = await receive()
                body += msg.get("body", b"")
                if not msg.get("more_body") or len(body) > 8192:
                    break
            password = parse_qs(body.decode("utf-8", "replace")).get("password", [""])[0]
            if tunnels.check_password(app_id, password):
                cookie = f"{_COOKIE}={expected}; Path=/; HttpOnly; Secure; SameSite=Lax"
                await send({"type": "http.response.start", "status": 303,
                            "headers": [(b"location", b"/"), (b"set-cookie", cookie.encode()),
                                        (b"content-length", b"0")]})
                await send({"type": "http.response.body", "body": b""})
                return None
            await asyncio.sleep(1.0)  # slow down guessing
            st, page = _page("Password required", _login_form(error=True), 401)
            await _send_page(send, st, page)
            return None

        st, page = _page("Password required", _login_form(error=False), 401)
        await _send_page(send, st, page)
        return None

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------
    async def _proxy_http(self, scope, receive, send, port: int, public_origin: str) -> None:
        path = scope.get("raw_path") or scope["path"].encode()
        qs = scope.get("query_string") or b""
        url = f"http://localhost:{port}{path.decode('latin-1')}" + (f"?{qs.decode('latin-1')}" if qs else "")
        public_host = public_origin.split("://", 1)[-1]
        public_proto = public_origin.split("://", 1)[0]
        fwd = [(k, v) for k, v in scope.get("headers") or []
               if k.lower() not in _HOP and k.lower() not in (b"accept-encoding", b"x-forwarded-host", b"x-forwarded-proto")]
        fwd.append((b"host", f"localhost:{port}".encode()))
        # Tell the app where visitors really are (Laravel, Django, WordPress… honour these).
        fwd.append((b"x-forwarded-host", public_host.encode("latin-1")))
        fwd.append((b"x-forwarded-proto", public_proto.encode()))
        # Ask for an uncompressed body so leftover localhost links can be fixed.
        fwd.append((b"accept-encoding", b"identity"))

        async def body_iter():
            while True:
                msg = await receive()
                if msg["type"] == "http.disconnect":
                    return
                chunk = msg.get("body", b"")
                if chunk:
                    yield chunk
                if not msg.get("more_body"):
                    return

        has_body = scope["method"] not in ("GET", "HEAD", "OPTIONS")
        try:
            req = self.client.build_request(scope["method"], url, headers=fwd,
                                            content=body_iter() if has_body else None)
            resp = await self.client.send(req, stream=True)
        except httpx.HTTPError as exc:
            st, page = _page("Can’t reach the app", "<h1>The app didn’t answer</h1>"
                             f"<p>{html.escape(type(exc).__name__)} on port {port}. It may still be starting.</p>", 502)
            await _send_page(send, st, page)
            return

        swaps = _localhost_swaps(port, public_origin)
        out = []
        for k, v in resp.headers.raw:
            lk = k.lower()
            if lk in _HOP:
                continue
            if lk in (b"location", b"content-location", b"refresh", b"link"):
                v = _apply(v, swaps)
            out.append((k, v))

        try:
            if _rewritable(resp, scope["method"]):
                body = b""
                async for chunk in resp.aiter_raw():
                    body += chunk
                    if len(body) > _MAX_REWRITE:
                        break
                if len(body) <= _MAX_REWRITE:
                    body = _apply(body, swaps)
                    out = [(k, v) for k, v in out if k.lower() != b"content-length"]
                    out.append((b"content-length", str(len(body)).encode()))
                    await send({"type": "http.response.start", "status": resp.status_code, "headers": out})
                    await send({"type": "http.response.body", "body": body})
                    return
                # too big to rewrite: send what we have, then stream the rest untouched
                await send({"type": "http.response.start", "status": resp.status_code, "headers": out})
                await send({"type": "http.response.body", "body": body, "more_body": True})
            else:
                await send({"type": "http.response.start", "status": resp.status_code, "headers": out})
            async for chunk in resp.aiter_raw():
                await send({"type": "http.response.body", "body": chunk, "more_body": True})
            await send({"type": "http.response.body", "body": b""})
        finally:
            await resp.aclose()

    # ------------------------------------------------------------------
    # WebSocket (dev-server live reload)
    # ------------------------------------------------------------------
    async def _proxy_ws(self, scope, receive, send, port: int) -> None:
        import websockets

        first = await receive()
        if first["type"] != "websocket.connect":
            return
        path = (scope.get("raw_path") or scope["path"].encode()).decode("latin-1")
        qs = (scope.get("query_string") or b"").decode("latin-1")
        url = f"ws://localhost:{port}{path}" + (f"?{qs}" if qs else "")
        subprotocols = list(scope.get("subprotocols") or []) or None
        try:
            upstream = await websockets.connect(url, subprotocols=subprotocols, max_size=None,
                                                open_timeout=10, ping_interval=None)
        except Exception:
            await send({"type": "websocket.close", "code": 1011})
            return
        await send({"type": "websocket.accept", "subprotocol": upstream.subprotocol})

        async def client_to_upstream():
            while True:
                msg = await receive()
                if msg["type"] == "websocket.receive":
                    data = msg.get("text") if msg.get("text") is not None else msg.get("bytes")
                    if data is not None:
                        await upstream.send(data)
                elif msg["type"] == "websocket.disconnect":
                    return

        async def upstream_to_client():
            try:
                async for data in upstream:
                    if isinstance(data, str):
                        await send({"type": "websocket.send", "text": data})
                    else:
                        await send({"type": "websocket.send", "bytes": data})
            except Exception:
                pass
            try:
                await send({"type": "websocket.close", "code": 1000})
            except Exception:
                pass

        tasks = [asyncio.ensure_future(client_to_upstream()), asyncio.ensure_future(upstream_to_client())]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in tasks:
                t.cancel()
            try:
                await upstream.close()
            except Exception:
                pass


def _login_form(error: bool) -> str:
    err = '<p class="err">Wrong password — try again.</p>' if error else ""
    return f"""<h1>Password required</h1><p>This app is shared privately. Enter the password you were given.</p>
<form method="post" action="{_LOGIN_PATH}"><input type="password" name="password" placeholder="Password" autofocus required autocomplete="current-password">
{err}<button type="submit">Continue</button></form>"""
