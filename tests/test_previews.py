"""PR previews (git worktrees), PR comments, comments → issues, comment notifications."""
from __future__ import annotations

import json
import os
import shutil
import subprocess

import httpx
import pytest

from backend import app_settings, feedback, github, osutil

pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="git not installed")
TOKEN = "gho_" + "a" * 36


def _git(cwd, *args):
    return subprocess.run(["git", "-c", "user.email=t@e.com", "-c", "user.name=T", *args], cwd=cwd,
                          check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    """A clone whose origin has refs/pull/7/head, like GitHub."""
    work = tmp_path / "seed"
    work.mkdir()
    (work / "index.html").write_text("<h1>main</h1>")
    _git(work, "init", "-q", "-b", "main")
    _git(work, "add", ".")
    _git(work, "commit", "-q", "-m", "main")
    _git(work, "checkout", "-q", "-b", "feature")
    (work / "pr.txt").write_text("from the pull request")
    _git(work, "add", ".")
    _git(work, "commit", "-q", "-m", "pr")
    origin = tmp_path / "origin.git"
    _git(tmp_path, "clone", "-q", "--bare", str(work), str(origin))
    _git(origin, "update-ref", "refs/pull/7/head", "refs/heads/feature")
    app = tmp_path / "shop"
    _git(tmp_path, "clone", "-q", "-b", "main", str(origin), str(app))
    (app / ".env").write_text("SECRET=1")
    return app


class FakeGH:
    def __init__(self):
        self.posts = []

    def __call__(self, request):
        path = request.url.path
        if request.method == "POST":
            self.posts.append((path, json.loads(request.content)))
            if path.endswith("/comments"):
                return httpx.Response(201, json={"html_url": "https://github.com/octo/shop/pull/7#c1"})
            return httpx.Response(201, json={"number": 12, "html_url": "https://github.com/octo/shop/issues/12"})
        if path == "/repos/octo/shop/pulls":
            return httpx.Response(200, json=[{"number": 7, "title": "New hero", "user": {"login": "sam"},
                                              "head": {"ref": "feature"}, "html_url": "https://github.com/octo/shop/pull/7"}])
        return httpx.Response(404, json={"message": "Not Found"})


@pytest.fixture
def gh(monkeypatch):
    fake = FakeGH()
    monkeypatch.setattr(github, "transport", httpx.MockTransport(fake))
    monkeypatch.setattr(github, "_remote_repo", lambda path: "octo/shop")
    github._save(TOKEN, "token")
    return fake


def test_preview_runs_the_pr_next_to_your_copy(client, isolated_registry, repo, gh):
    isolated_registry.add({"name": "Shop", "path": str(repo), "command": "serve --port 8100", "port": 8100,
                           "category": "Web", "env": {"A": "1"}})
    listed = client.get("/api/apps/shop/pulls").json()["pulls"]
    assert listed[0]["number"] == 7 and listed[0]["preview"] is None

    r = client.post("/api/apps/shop/previews", json={"number": 7, "title": "New hero", "start": False})
    assert r.status_code == 200, r.text
    st = r.json()
    worktree = str(repo) + "-pr-7"
    assert st["name"] == "Shop · PR #7" and st["path"] == worktree and st["category"] == "Web"
    assert st["port"] != 8100 and str(st["port"]) in st["command"]
    assert st["preview"]["number"] == 7 and st["preview"]["of"] == "shop"
    assert open(os.path.join(worktree, "pr.txt")).read() == "from the pull request"
    assert not (repo / "pr.txt").exists() and _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"  # your copy untouched
    assert open(os.path.join(worktree, ".env")).read() == "SECRET=1"
    # again: the same preview, not a second one
    again = client.post("/api/apps/shop/previews", json={"number": 7, "start": False}).json()
    assert again["id"] == st["id"] and len(isolated_registry.list()) == 2
    assert client.get("/api/apps/shop/pulls").json()["pulls"][0]["preview"] == st["id"]

    # comment on the PR
    c = client.post(f"/api/apps/{st['id']}/preview/comment", json={"body": "Preview: https://x.trycloudflare.com"})
    assert c.json()["url"].endswith("#c1") and gh.posts[-1] == ("/repos/octo/shop/issues/7/comments", {"body": "Preview: https://x.trycloudflare.com"})
    assert client.post("/api/apps/shop/preview/comment", json={"body": "x"}).status_code == 400  # not a preview

    # remove: app, folder and ref are gone; your repo still fine
    assert client.delete(f"/api/apps/{st['id']}/preview").json()["ok"] is True
    assert not os.path.exists(worktree) and [a["id"] for a in isolated_registry.list()] == ["shop"]
    assert "refs/homeport/pr-7" not in _git(repo, "for-each-ref")
    assert client.delete("/api/apps/shop/preview").status_code == 400


def test_preview_errors(client, isolated_registry, repo, gh, tmp_path):
    isolated_registry.add({"name": "Shop", "path": str(repo), "command": "x"})
    assert client.post("/api/apps/shop/previews", json={"number": "7"}).status_code == 400
    assert client.post("/api/apps/shop/previews", json={"number": 99, "start": False}).status_code == 409  # no such PR
    plain = tmp_path / "plain"
    plain.mkdir()
    isolated_registry.add({"name": "Plain", "path": str(plain), "command": "x"})
    assert client.post("/api/apps/plain/previews", json={"number": 7}).status_code == 409  # not a git repo


def test_comment_becomes_an_issue(client, isolated_registry, repo, gh):
    isolated_registry.add({"name": "Shop", "path": str(repo), "command": "x"})
    item = feedback.add("shop", {"message": "Logo is blurry\nOn retina", "name": "Maria", "page": "/about",
                                 "vw": 390, "vh": 844, "url": "https://x.trycloudflare.com/about"})
    feedback.add_reply("shop", item["id"], {"message": "Same here", "name": "Sam"})
    draft = client.get(f"/api/apps/shop/feedback/{item['id']}/issue-draft").json()
    assert draft["title"] == "Logo is blurry" and "> On retina" in draft["body"]
    assert "Maria" in draft["body"] and "390×844" in draft["body"] and "**Sam:** Same here" in draft["body"]
    r = client.post(f"/api/apps/shop/feedback/{item['id']}/issue", json={"title": "Blurry logo", "body": draft["body"]})
    assert r.json()["issue"] == {"number": 12, "url": "https://github.com/octo/shop/issues/12"}
    assert gh.posts[-1][0] == "/repos/octo/shop/issues" and gh.posts[-1][1]["title"] == "Blurry logo"
    assert feedback.items("shop")[0]["issue"]["number"] == 12
    assert client.post(f"/api/apps/shop/feedback/{item['id']}/issue", json={"title": ""}).status_code == 400
    assert client.post("/api/apps/shop/feedback/nope/issue", json={"title": "x"}).status_code == 404


def test_new_visitor_comments_notify(client, isolated_registry, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(osutil, "notify", lambda title, message: shown.append((title, message)))
    monkeypatch.setattr("threading.Thread", lambda target, args, daemon: type("T", (), {"start": lambda self: target(*args)})())
    isolated_registry.add({"name": "Clipio", "path": str(tmp_path), "command": "x"})
    item = feedback.add("clipio", {"message": "Hero text is too long", "name": "Maria"})
    feedback.add_reply("clipio", item["id"], {"message": "Agreed", "name": "Sam"})
    feedback.add("clipio", {"message": "my own note"}, source="local")  # the owner's own: quiet
    assert shown == [("Maria commented on Clipio", "Hero text is too long"), ("Sam replied on Clipio", "Agreed")]
    app_settings.update({"notify_comments": False})
    feedback.add("clipio", {"message": "quiet now"})
    assert len(shown) == 2
