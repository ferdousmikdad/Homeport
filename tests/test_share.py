"""Public share links: validation, password protection, expiry (no real tunnels)."""

from __future__ import annotations

import time

import pytest

from _helpers import sleep_cmd

from backend import proxy, share_routes, tunnels as tunnels_mod


@pytest.fixture
def tm(monkeypatch):
    """A TunnelManager whose 'cloudflared' is a harmless long-running process."""
    manager = tunnels_mod.TunnelManager()
    monkeypatch.setattr(manager, "binary", lambda: "unused")

    class FakeProc:
        returncode = None
        stdout = iter(())
        pid = 0

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = 0

        def wait(self, timeout=None):
            return 0

        def kill(self):
            self.returncode = -9

    monkeypatch.setattr(manager, "_spawn", lambda cmd: FakeProc())
    yield manager
    manager.shutdown()


def test_missing_cloudflared_is_reported(monkeypatch):
    manager = tunnels_mod.TunnelManager()
    monkeypatch.setattr(manager, "binary", lambda: None)
    with pytest.raises(tunnels_mod.CloudflaredMissing):
        manager.start("app", 8000)
    assert manager.status()["cloudflared"] is False


def test_password_is_hashed_and_checked(tm):
    state = tm.start("web", 8000, password="open-sesame")
    assert state["protected"] is True
    salt, pw_hash, secret, port = tm.auth_info("web")
    assert "open-sesame" not in pw_hash and port == 8000
    assert tm.check_password("web", "open-sesame")
    assert not tm.check_password("web", "wrong")
    tm.stop("web")
    assert tm.auth_info("web") is None


def test_open_share_has_no_auth(tm):
    assert tm.start("web", 8000)["protected"] is False
    assert tm.auth_info("web") is None


def test_validation(tm):
    with pytest.raises(ValueError):
        tm.start("web", 8000, password="abc")
    with pytest.raises(ValueError):
        tm.start("web", 8000, expires_minutes=0.5)


def test_expired_shares_are_stopped(tm):
    tm.start("web", 8000, expires_minutes=1)
    tm._shares["web"].expires_at = time.time() - 1
    assert tm.stop_expired() == ["web"]
    assert not tm.is_sharing("web")


def test_share_route_needs_running_app(client, isolated_registry, tmp_path):
    isolated_registry.add({"name": "Web", "path": str(tmp_path), "command": sleep_cmd(60), "port": 9876})
    resp = client.post("/api/apps/web/share", json={})
    assert resp.status_code == 409
    assert "start the app first" in resp.json()["detail"]
    assert client.post("/api/apps/ghost/share", json={}).status_code == 404


def test_state_has_share_and_lan_fields(client, isolated_registry, tmp_path):
    isolated_registry.add({"name": "Web", "path": str(tmp_path), "command": sleep_cmd(60)})
    state = client.get("/api/apps").json()[0]
    assert state["share"] is None and state["lan"] is None
    assert client.delete("/api/apps/web/share").json() == {"ok": True, "stopped": False}


def test_protected_share_host_asks_for_password(client, isolated_registry, tmp_path, monkeypatch, tm):
    isolated_registry.add({"name": "Web", "path": str(tmp_path), "command": sleep_cmd(60)})
    monkeypatch.setattr(share_routes, "tunnels", tm)
    monkeypatch.setattr(proxy, "tunnels", tm)
    host = {"Host": "web.share.localhost"}
    assert client.get("/", headers=host).status_code == 410  # not shared
    tm.start("web", 9, password="open-sesame")
    assert client.get("/", headers=host).status_code == 401
    bad = client.post("/__homeport/login", data={"password": "nope"}, headers=host, follow_redirects=False)
    assert bad.status_code == 401
    # the app isn't really running, so the 1s tick may have closed the share
    # during the wrong-password delay: share it again
    tm.start("web", 9, password="open-sesame")
    ok = client.post("/__homeport/login", data={"password": "open-sesame"}, headers=host, follow_redirects=False)
    assert ok.status_code == 303 and "homeport_share=" in ok.headers["set-cookie"]


def test_qr_endpoint_returns_svg(client):
    resp = client.get("/api/qr", params={"text": "http://192.168.1.5:18000/"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert b"<svg" in resp.content
