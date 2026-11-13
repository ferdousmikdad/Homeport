"""The update check: version parsing, GitHub's latest release, settings."""
from __future__ import annotations

import re

import httpx

from backend import updates
from backend.version import __version__


def _github(tag="v9.9.9", status=200, body="## What's Changed\n* Add GitHub by @x in https://github.com/p/1\n**Full Changelog**: https://x"):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(status, json={"tag_name": tag, "html_url": f"https://github.com/r/releases/tag/{tag}",
                                            "body": body, "published_at": "2026-12-01T00:00:00Z"})
    return httpx.MockTransport(handler), calls


def test_version_matches_the_website_changelog():
    html = open("site/changelog/index.html", encoding="utf-8").read()
    newest = re.search(r'<span class="v">v([\d.]+)</span>', html).group(1)
    assert newest == __version__, "bump backend/version.py and add the release to site/changelog together"
    plist = open("Homeport.app/Contents/Info.plist", encoding="utf-8").read()
    assert f"<string>{__version__}</string>" in plist


def test_compare_versions():
    assert updates.newer("1.2.0", "1.1.0") and updates.newer("v1.10.0", "1.9.9") and updates.newer("2", "1.9")
    assert not updates.newer("1.1.0", "1.1.0") and not updates.newer("1.0.9", "1.1.0")
    assert updates.parse("v1.2.3-beta.1") == (1, 2, 3) and updates.parse("nonsense") == (0,)


def test_newer_release_is_reported(client, monkeypatch):
    transport, calls = _github("v9.9.9")
    monkeypatch.setattr(updates, "transport", transport)
    st = client.post("/api/update/check").json()
    assert st["available"] is True and st["latest"] == "9.9.9" and st["current"] == __version__
    assert st["changelog"].endswith("#v9-9-9")
    assert st["notes"] == "What's Changed\nAdd GitHub"  # links and markdown stripped
    assert st["how"]["kind"] in ("desktop", "script", "source")
    # cached: the dashboard asking again doesn't hit GitHub
    assert client.get("/api/update").json()["available"] is True and len(calls) == 1


def test_same_or_older_release_is_not_an_update(client, monkeypatch):
    monkeypatch.setattr(updates, "transport", _github("v" + __version__)[0])
    assert client.post("/api/update/check").json()["available"] is False
    monkeypatch.setattr(updates, "transport", _github("v0.1.0")[0])
    assert client.post("/api/update/check").json()["available"] is False


def test_daily_limit_and_errors(client, monkeypatch):
    transport, calls = _github("v9.9.9")
    monkeypatch.setattr(updates, "transport", transport)
    import asyncio
    asyncio.run(updates.check())
    asyncio.run(updates.check())  # within a day: no second request
    assert len(calls) == 1
    monkeypatch.setattr(updates, "transport", httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("offline"))))
    st = client.post("/api/update/check").json()
    assert "couldn't reach GitHub" in st["error"] and st["latest"] == "9.9.9"  # keeps the last known answer


def test_setting_and_install_instructions(client, monkeypatch):
    assert client.get("/api/update").json()["enabled"] is True
    assert client.patch("/api/settings", json={"check_updates": False}).json()["check_updates"] is False
    assert client.get("/api/update").json()["enabled"] is False
    assert client.patch("/api/settings", json={"check_updates": "no"}).status_code == 400
    assert updates.how_to_update("desktop")["download"].startswith("https://github.com/")
    assert "install" in updates.how_to_update("script")["command"]
    assert updates.how_to_update("source")["command"] == "git pull"
