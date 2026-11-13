"""Visitor feedback on shared links: storage, share switch, proxy widget and endpoints."""
from __future__ import annotations

import socket

import pytest

from _helpers import explain, http_server_cmd, wait_until
from backend import feedback, proxy, share_routes
from test_share import tm  # noqa: F401  (fixture)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------
def test_add_validates_and_cleans():
    item = feedback.add("web", {"message": "  Button is broken \r\n ", "name": "x" * 200, "page": "about",
                                "selector": "#buy", "ox": 0.5, "oy": 2, "xp": -1, "y": 300})
    assert item["message"] == "Button is broken" and len(item["name"]) == feedback.MAX_NAME
    assert item["page"] == "/about" and item["status"] == "open" and item["source"] == "share"
    assert item["oy"] == 1 and item["xp"] == 0  # clamped
    with pytest.raises(ValueError):
        feedback.add("web", {"message": "   "})
    with pytest.raises(ValueError):
        feedback.add("../etc", {"message": "hi"})
    # a half-given element position is dropped, page coordinates stay
    loose = feedback.add("web", {"message": "hi", "selector": "#a", "xp": 0.2, "y": 10})
    assert loose["selector"] == "" and loose["ox"] is None and loose["xp"] == 0.2


def test_status_counts_and_delete():
    a = feedback.add("web", {"message": "one"})
    b = feedback.add("web", {"message": "two"})
    assert feedback.open_count("web") == 2
    assert feedback.set_status("web", a["id"], "resolved")["status"] == "resolved"
    assert feedback.open_count("web") == 1
    with pytest.raises(ValueError):
        feedback.set_status("web", b["id"], "done")
    assert feedback.set_status("web", "nope", "open") is None
    assert feedback.delete("web", status="resolved") == 1
    assert [i["id"] for i in feedback.items("web")] == [b["id"]]
    feedback.forget("web")
    assert feedback.items("web") == [] and feedback.open_count("web") == 0


def test_rate_limit_per_visitor(monkeypatch):
    monkeypatch.setattr(feedback, "RATE_LIMIT", (2, 600.0))
    assert not feedback.rate_limited("web", "1.1.1.1")
    assert not feedback.rate_limited("web", "1.1.1.1")
    assert feedback.rate_limited("web", "1.1.1.1")
    assert not feedback.rate_limited("web", "2.2.2.2")


def test_oldest_resolved_dropped_first(monkeypatch):
    monkeypatch.setattr(feedback, "MAX_ITEMS", 3)
    first = feedback.add("web", {"message": "1"})
    feedback.set_status("web", first["id"], "resolved")
    for n in range(2, 5):
        feedback.add("web", {"message": str(n)})
    assert [i["message"] for i in feedback.items("web")] == ["2", "3", "4"]


def test_inject_widget_only_in_full_pages():
    page = b"<!doctype html><html><body><h1>Hi</h1></body></html>"
    out = proxy._inject_widget(page, "visitor")
    assert out.index(b'/__homeport/fb.js" data-mode="visitor"') < out.index(b"</body>")
    assert proxy._inject_widget(b"<li>a fragment</li>", "visitor") == b"<li>a fragment</li>"
    assert b"data-mode=\"review\"" in proxy._inject_widget(b"<html><p>no body end", "review")


# ---------------------------------------------------------------------------
# dashboard API
# ---------------------------------------------------------------------------
def test_dashboard_routes(client, isolated_registry, tmp_path):
    isolated_registry.add({"name": "Web", "path": str(tmp_path), "command": "true"})
    item = feedback.add("web", {"message": "Logo is blurry"})
    data = client.get("/api/apps/web/feedback").json()
    assert data["open"] == 1 and data["items"][0]["message"] == "Logo is blurry"
    assert client.get("/api/apps").json()[0]["feedback_open"] == 1
    assert client.patch(f"/api/apps/web/feedback/{item['id']}", json={"status": "resolved"}).json()["status"] == "resolved"
    assert client.patch(f"/api/apps/web/feedback/{item['id']}", json={"status": "x"}).status_code == 400
    assert client.delete("/api/apps/web/feedback?status=resolved").json() == {"deleted": 1}
    assert client.delete(f"/api/apps/web/feedback/{item['id']}").status_code == 404
    assert client.get("/api/apps/ghost/feedback").status_code == 404
    # deleting the app deletes its feedback
    feedback.add("web", {"message": "again"})
    client.delete("/api/apps/web")
    assert feedback.items("web") == []


def test_share_feedback_switch(client, isolated_registry, tmp_path, monkeypatch, tm):  # noqa: F811
    monkeypatch.setattr(share_routes, "tunnels", tm)
    assert tm.start("web", 9)["feedback"] is False
    assert tm.start("web", 9, feedback=True)["feedback"] is True
    assert client.patch("/api/apps/web/share", json={"feedback": False}).json()["feedback"] is False
    assert tm.share_info("web")["feedback"] is False
    assert client.patch("/api/apps/web/share", json={"feedback": "yes"}).status_code == 400
    assert client.patch("/api/apps/other/share", json={"feedback": True}).status_code == 404


# ---------------------------------------------------------------------------
# proxy: widget, visitor notes, review mode (real app behind the proxy)
# ---------------------------------------------------------------------------
@pytest.fixture
def site(client, isolated_registry, tmp_path, monkeypatch, tm):  # noqa: F811
    (tmp_path / "index.html").write_text("<!doctype html><html><body><h1>Shop</h1></body></html>")
    port = _free_port()
    isolated_registry.add({"name": "Web", "path": str(tmp_path), "command": http_server_cmd(tmp_path, port), "port": port})
    monkeypatch.setattr(share_routes, "tunnels", tm)
    monkeypatch.setattr(proxy, "tunnels", tm)
    assert client.post("/api/apps/web/start").status_code == 200
    assert wait_until(lambda: client.get("/api/apps/web").json()["status"] == "running", timeout=20), \
        explain(client, "web")
    yield port
    client.post("/api/apps/web/stop")


def test_visitor_widget_and_notes(client, site, tm):  # noqa: F811
    share = {"Host": "web.share.localhost"}
    tm.start("web", site)  # feedback off
    assert "fb.js" not in client.get("/", headers=share).text
    assert client.get("/__homeport/fb.js", headers=share).status_code == 404
    assert client.post("/__homeport/fb", json={"message": "hi"}, headers=share).status_code == 404
    assert client.get("/__homeport/fb/list", headers=share).status_code == 404  # feedback off: nothing to read

    tm.set_feedback("web", True)
    page = client.get("/", headers=share).text
    assert "Shop" in page and 'src="/__homeport/fb.js" data-mode="visitor"' in page
    js = client.get("/__homeport/fb.js", headers=share)
    assert js.status_code == 200 and "javascript" in js.headers["content-type"]
    sent = client.post("/__homeport/fb", json={"message": "Price is wrong", "page": "/", "xp": 0.5, "y": 120},
                       headers={**share, "cf-connecting-ip": "203.0.113.9"})
    assert sent.status_code == 201
    assert client.post("/__homeport/fb", json={"message": ""}, headers=share).status_code == 400
    stored = feedback.items("web")
    assert stored[0]["message"] == "Price is wrong" and stored[0]["source"] == "share"
    # visitors see the open comments as pins (like Figma), with only what's needed to draw them
    feedback.set_status("web", feedback.add("web", {"message": "old, fixed", "page": "/"})["id"], "resolved")
    public = client.get("/__homeport/fb/list?page=/", headers=share).json()
    assert [i["message"] for i in public["items"]] == ["Price is wrong"] and public["can_manage"] is False
    assert set(public["items"][0]) <= {"id", "created_at", "message", "name", "page", "selector", "ox", "oy", "xp", "y", "status", "replies"}
    assert "ua" not in public["items"][0] and "url" not in public["items"][0]
    # owner-only endpoints are never reachable through the public link
    assert client.get("/__homeport/fb/review?on=1", headers=share).status_code == 404
    assert client.post(f"/__homeport/fb/{stored[0]['id']}", json={"status": "resolved"}, headers=share).status_code == 404


def test_review_mode_on_named_url(client, site):
    named = {"Host": "web.localhost:7777"}
    item = feedback.add("web", {"message": "Fix header", "page": "/"})
    assert "fb.js" not in client.get("/", headers=named).text  # plain view: no feedback
    on = client.get(f"/__homeport/fb/review?on=1&to=/&pin={item['id']}", headers=named, follow_redirects=False)
    assert on.status_code == 302 and on.headers["location"] == f"/#homeport-fb={item['id']}"
    assert "homeport_review=1" in on.headers["set-cookie"]
    cookie = {**named, "Cookie": "homeport_review=1"}
    assert 'data-mode="review"' in client.get("/", headers=cookie).text
    listed_all = client.get("/__homeport/fb/list?page=/", headers=named).json()
    assert listed_all["can_manage"] is True
    listed = listed_all["items"]
    assert [i["id"] for i in listed] == [item["id"]]
    assert client.post(f"/__homeport/fb/{item['id']}", json={"status": "resolved"}, headers=named).json()["status"] == "resolved"
    off = client.get("/__homeport/fb/review?on=0&to=//evil.example", headers=named, follow_redirects=False)
    assert off.headers["location"] == "/" and "Max-Age=0" in off.headers["set-cookie"]


# ---------------------------------------------------------------------------
# opening pages from the dashboard (used by "Open", "View with feedback")
# ---------------------------------------------------------------------------
def test_open_app_page_and_share_link(client, isolated_registry, tmp_path, monkeypatch, tm):  # noqa: F811
    from backend import osutil
    opened = []
    monkeypatch.setattr(osutil, "open_url", opened.append)
    monkeypatch.setattr(share_routes, "tunnels", tm)
    isolated_registry.add({"name": "Web", "path": str(tmp_path), "command": "true"})
    ok = client.post("/api/apps/web/open", json={"target": "app", "path": "/__homeport/fb/review?on=1&to=%2F"})
    assert ok.status_code == 200
    assert opened[-1].startswith("http://web.localhost:") and opened[-1].endswith("/__homeport/fb/review?on=1&to=%2F")
    for bad in ("//evil.example", "about", "/a b", "/x\\y"):
        assert client.post("/api/apps/web/open", json={"target": "app", "path": bad}).status_code == 400, bad
    assert client.post("/api/apps/web/open", json={"target": "share"}).status_code == 409
    tm.start("web", 9)
    tm._shares["web"].url = "https://example.trycloudflare.com"
    assert client.post("/api/apps/web/open", json={"target": "share"}).json()["url"] == "https://example.trycloudflare.com"
    assert opened[-1] == "https://example.trycloudflare.com"


def test_shared_pages_are_never_served_from_cache(client, site, tm):  # noqa: F811
    """Turning feedback on must show on the next reload, even for a page the
    visitor's browser had cached before (no 304, no heuristic freshness)."""
    share = {"Host": "web.share.localhost", "Accept": "text/html"}
    tm.start("web", site)
    first = client.get("/", headers=share)
    assert first.headers["cache-control"] == "no-cache"
    assert "last-modified" not in first.headers and "etag" not in first.headers
    tm.set_feedback("web", True)
    again = client.get("/", headers={**share, "If-Modified-Since": "Wed, 01 Jan 2031 00:00:00 GMT"})
    assert again.status_code == 200 and "/__homeport/fb.js" in again.text


def test_replies_make_a_thread(client, site, tm):  # noqa: F811
    share = {"Host": "web.share.localhost"}
    named = {"Host": "web.localhost:7777"}
    tm.start("web", site, feedback=True)
    fid = client.post("/__homeport/fb", json={"message": "Logo too big", "page": "/"}, headers=share).json()["id"]
    r = client.post(f"/__homeport/fb/{fid}/reply", json={"message": "Agree", "name": "Sam"}, headers=share)
    assert r.status_code == 201 and r.json()["name"] == "Sam"
    assert client.post(f"/__homeport/fb/{fid}/reply", json={"message": " "}, headers=share).status_code == 400
    assert client.post("/__homeport/fb/abc123/reply", json={"message": "x"}, headers=share).status_code == 404
    # the owner replies from the dashboard; visitors see the whole thread
    assert client.post(f"/api/apps/web/feedback/{fid}/reply", json={"message": "Fixing it", "name": "Owner"}).status_code == 200
    thread = client.get("/__homeport/fb/list?page=/", headers=share).json()["items"][0]["replies"]
    assert [x["message"] for x in thread] == ["Agree", "Fixing it"] and set(thread[0]) == {"id", "created_at", "message", "name"}
    # resolved: visitors can't reply any more, the owner still can
    feedback.set_status("web", fid, "resolved")
    assert client.post(f"/__homeport/fb/{fid}/reply", json={"message": "late"}, headers=share).status_code == 404
    assert client.post(f"/__homeport/fb/{fid}/reply", json={"message": "noted"}, headers=named).status_code == 201
