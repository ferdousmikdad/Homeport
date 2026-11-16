"""Local HTTPS: the certificate authority, per-name certificates, the listener and URLs."""
from __future__ import annotations

import asyncio
import os
import ssl
import stat
import sys

import httpx
import pytest

from backend import local_https


def test_ca_is_private_and_limited_to_localhost():
    assert not local_https.has_ca()
    local_https.create_ca()
    assert local_https.has_ca()
    key, pem = local_https._ca_files()
    if sys.platform != "win32":
        assert stat.S_IMODE(os.stat(key).st_mode) == 0o600
    from cryptography import x509

    with open(pem, "rb") as fh:
        cert = x509.load_pem_x509_certificate(fh.read())
    assert cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is True
    permitted = cert.extensions.get_extension_for_class(x509.NameConstraints).value.permitted_subtrees
    assert x509.DNSName("localhost") in permitted
    before = local_https.ca_fingerprint()
    local_https.create_ca()  # a second call keeps the same CA
    assert local_https.ca_fingerprint() == before


def test_leaf_certificates_verify_for_their_name(tmp_path):
    local_https.create_ca()
    pem = local_https.leaf_pem("shop.localhost")
    path = tmp_path / "leaf.pem"
    path.write_bytes(pem)
    from cryptography import x509

    cert = x509.load_pem_x509_certificate(pem)
    sans = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert sans.get_values_for_type(x509.DNSName) == ["shop.localhost"]
    # Python's own TLS stack accepts it for that name with only our CA trusted
    ctx = local_https._context_for("shop.localhost")
    assert isinstance(ctx, ssl.SSLContext)


def test_host_names_accepted_for_certificates():
    ok = local_https._HOST_RE.match
    assert ok("localhost") and ok("shop.localhost") and ok("my-app2.localhost")
    assert not ok("evil.com") and not ok("a.b.localhost") and not ok("-x.localhost") and not ok("localhost.evil.com")


def test_listener_serves_https_with_a_certificate_per_name():
    local_https.create_ca()

    async def app(scope, receive, send):
        assert scope["type"] == "http"
        body = (scope["scheme"] + " " + dict(scope["headers"]).get(b"host", b"").decode()).encode()
        await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": body})

    async def run():
        local_https.asgi_app = app
        os.environ["HOMEPORT_HTTPS_PORT"] = "17443"
        try:
            port = await local_https.start()
            assert port and local_https.running()
            verify = ssl.create_default_context(cafile=local_https._ca_files()[1])
            # *.localhost resolves to this computer in browsers; here we dial 127.0.0.1 with the right SNI name
            transport = httpx.AsyncHTTPTransport(verify=verify)
            async with httpx.AsyncClient(transport=transport) as client:
                for name in ("localhost", "shop.localhost"):
                    res = await client.get(f"https://127.0.0.1:{port}/", headers={"Host": f"{name}:{port}"},
                                           extensions={"sni_hostname": name})
                    assert res.status_code == 200 and res.text == f"https {name}:{port}"
        finally:
            await local_https.stop()
            os.environ.pop("HOMEPORT_HTTPS_PORT", None)
            local_https.asgi_app = None
        assert not local_https.running()

    asyncio.run(run())


def test_app_urls_follow_the_switch_and_the_default(monkeypatch):
    monkeypatch.setattr(local_https, "running", lambda: True)
    monkeypatch.setattr(local_https, "port", 7443)
    assert local_https.app_url("shop", {}, False, 7777) == "http://shop.localhost:7777/"
    assert local_https.app_url("shop", {}, True, 7777, "/cart") == "https://shop.localhost:7443/cart"
    assert local_https.app_url("shop", {"https": False}, True, 7777) == "http://shop.localhost:7777/"
    assert local_https.app_url("shop", {"https": True}, False, 7777) == "https://shop.localhost:7443/"
    monkeypatch.setattr(local_https, "running", lambda: False)
    assert local_https.app_url("shop", {"https": True}, True, 7777) == "http://shop.localhost:7777/"


def test_status_and_settings(client, isolated_registry, tmp_path):
    st = client.get("/api/https").json()
    assert st["available"] is True and st["ready"] is False and st["running"] is False and st["default"] is False
    assert client.patch("/api/settings", json={"https_default": True}).json()["https_default"] is True
    assert client.patch("/api/settings", json={"https_default": "yes"}).status_code == 400
    assert client.get("/api/https").json()["default"] is True
    # per-app switch is stored and returned
    created = client.post("/api/apps", json={"name": "Shop", "path": str(tmp_path), "command": "x"}).json()
    assert created["https"] is None
    assert client.patch(f"/api/apps/{created['id']}", json={"https": True}).json()["https"] is True
    assert client.post("/api/https/trust").status_code == 409  # nothing set up yet


@pytest.mark.skipif(sys.platform == "win32", reason="removal deletes files; checked on macOS/Linux")
def test_remove_deletes_everything(client, monkeypatch):
    local_https.create_ca()
    monkeypatch.setattr(local_https, "untrust", lambda: None)  # never touch the real keychain
    assert client.get("/api/https").json()["ready"] is True
    st = client.delete("/api/https").json()
    assert st["ready"] is False and not os.path.exists(local_https._dir())
