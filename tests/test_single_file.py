"""Single-file apps (about.html, api.php …) and the in-page file browser."""
from __future__ import annotations

import os

from backend import detect, main, monitor


def test_detect_file_kinds(tmp_path):
    for name, body in [("about.html", "<h1>x</h1>"), ("api.php", "<?php"), ("server.js", ""),
                       ("dash.py", "import streamlit as st"), ("notes.txt", "")]:
        (tmp_path / name).write_text(body)
    html = monitor.detect_command(str(tmp_path / "about.html"))
    assert html["type"] == "HTML page" and html["entry"] == "about.html" and "http.server" in html["command"]
    php = monitor.detect_command(str(tmp_path / "api.php"))
    assert php["entry"] == "api.php" and php["command"].startswith("php -S 127.0.0.1:")
    assert "node server.js" in monitor.detect_command(str(tmp_path / "server.js"))["command"]
    assert "streamlit run dash.py" in monitor.detect_command(str(tmp_path / "dash.py"))["command"]
    assert monitor.detect_command(str(tmp_path / "notes.txt"))["command"] is None


def test_add_single_file_app(client, tmp_path):
    page = tmp_path / "landing.html"
    page.write_text("<h1>hi</h1>")
    det = client.get("/api/detect", params={"path": str(page)}).json()
    assert det["is_file"] and det["entry"] == "landing.html" and det["folder"] == str(tmp_path)

    st = client.post("/api/apps", json={"name": "Landing", "path": str(page)}).json()
    assert st["path"] == str(tmp_path)          # runs from the file's folder
    assert st["entry"] == "landing.html"         # and opens that page
    assert "http.server" in st["command"] and st["port"]


def test_named_url_redirects_to_entry(client, tmp_path, monkeypatch):
    (tmp_path / "landing.html").write_text("<h1>hi</h1>")
    st = client.post("/api/apps", json={"name": "Landing", "path": str(tmp_path / "landing.html")}).json()
    from backend import proxy
    monkeypatch.setattr(proxy, "get_running_port", lambda aid: 65000)
    res = client.get("/", headers={"Host": f"{st['id']}.localhost:7777"}, follow_redirects=False)
    assert res.status_code == 302 and res.headers["location"] == "/landing.html"


def test_browse_lists_runnable_files(client, tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "page.html").write_text("x")
    (tmp_path / "readme.md").write_text("x")
    names = lambda r: [e["name"] for e in r.json()["entries"]]  # noqa: E731
    assert names(client.get("/api/browse", params={"path": str(tmp_path)})) == ["sub"]
    assert names(client.get("/api/browse", params={"path": str(tmp_path), "files": "1"})) == ["sub", "page.html"]
