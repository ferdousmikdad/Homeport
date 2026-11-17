"""Your own domain: home.<domain> = dashboard, <app-id>.<domain> = app, behind Cloudflare Access."""

from __future__ import annotations

from _helpers import sleep_cmd

from backend import proxy

ACCESS = {"Cf-Access-Jwt-Assertion": "token"}


def test_domain_setting_is_cleaned_and_validated(client):
    assert client.get("/api/settings").json()["public_domain"] is None
    resp = client.patch("/api/settings", json={"public_domain": "https://home.Example.com/"})
    assert resp.json()["public_domain"] == "example.com"
    assert client.patch("/api/settings", json={"public_domain": "not a domain"}).status_code == 400
    assert client.patch("/api/settings", json={"public_domain": "web.localhost"}).status_code == 400
    assert client.patch("/api/settings", json={"public_domain": ""}).json()["public_domain"] is None


def test_public_label():
    assert proxy._public_label("home.example.com", "example.com") == "home"
    assert proxy._public_label("Blog.Example.com:443", "example.com") == "blog"
    assert proxy._public_label("example.com", "example.com") == ""
    assert proxy._public_label("a.b.example.com", "example.com") == ""
    assert proxy._public_label("notexample.com", "example.com") is None
    assert proxy._public_label("blog.localhost:7777", "example.com") is None
    assert proxy._public_label("blog.example.com", None) is None


def test_domain_routes_dashboard_and_apps_behind_access(client, isolated_registry, tmp_path):
    isolated_registry.add({"name": "Web", "path": str(tmp_path), "command": sleep_cmd(60)})
    client.patch("/api/settings", json={"public_domain": "example.com"})

    # without the Access login nothing gets through, not even the dashboard
    assert client.get("/api/health", headers={"Host": "home.example.com"}).status_code == 403
    assert client.get("/", headers={"Host": "web.example.com"}).status_code == 403

    assert client.get("/api/health", headers={"Host": "home.example.com", **ACCESS}).json()["ok"] is True
    app_page = client.get("/", headers={"Host": "web.example.com", **ACCESS})
    assert app_page.status_code == 503 and "isn’t running" in app_page.text
    assert client.get("/", headers={"Host": "ghost.example.com", **ACCESS}).status_code == 404
    assert client.get("/", headers={"Host": "a.b.example.com", **ACCESS}).status_code == 404

    # localhost keeps working as before
    assert client.get("/api/health").json()["ok"] is True


def test_dashboard_refuses_requests_from_other_sites(client, isolated_registry):
    client.patch("/api/settings", json={"public_domain": "example.com"})
    host = {"Host": "home.example.com", **ACCESS}
    evil = client.post("/api/apps", json={}, headers={**host, "Origin": "https://web.example.com"})
    assert evil.status_code == 403
    same = client.post("/api/apps", json={}, headers={**host, "Origin": "https://home.example.com"})
    assert same.status_code != 403
