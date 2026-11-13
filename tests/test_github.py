"""GitHub integration (docs/GITHUB.md) with a fake GitHub API and a local git repo."""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys

import httpx
import pytest

from backend import app_settings, github, gitinfo

TOKEN = "gho_" + "a" * 36
needs_git = pytest.mark.skipif(not shutil.which("git"), reason="git not installed")


class FakeGitHub:
    def __init__(self):
        self.device_polls = 0
        self.calls = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path))
        auth = request.headers.get("authorization", "")
        path = request.url.path
        if path == "/user":
            if auth != f"Bearer {TOKEN}":
                return httpx.Response(401, json={"message": "Bad credentials"})
            return httpx.Response(200, json={"login": "octo", "name": "Octo Cat", "avatar_url": "https://a/x.png"})
        if path == "/login/device/code":
            return httpx.Response(200, json={"device_code": "dc", "user_code": "ABCD-1234", "interval": 5,
                                             "expires_in": 900, "verification_uri": "https://github.com/login/device"})
        if path == "/login/oauth/access_token":
            self.device_polls += 1
            if self.device_polls == 1:
                return httpx.Response(200, json={"error": "authorization_pending"})
            return httpx.Response(200, json={"access_token": TOKEN, "token_type": "bearer"})
        if path == "/user/repos":
            return httpx.Response(200, json=[
                {"full_name": "octo/shop", "name": "shop", "owner": {"login": "octo"}, "private": True,
                 "description": "Online store", "language": "PHP", "pushed_at": "2026-11-01T00:00:00Z",
                 "default_branch": "main", "html_url": "https://github.com/octo/shop"},
                {"full_name": "octo/blog", "name": "blog", "owner": {"login": "octo"}, "private": False,
                 "description": "", "language": "Go", "default_branch": "main", "html_url": "https://github.com/octo/blog"},
            ])
        if path.endswith("/check-runs"):
            return httpx.Response(200, json={"check_runs": [
                {"status": "completed", "conclusion": "success", "html_url": "https://github.com/octo/shop/runs/1"},
                {"status": "completed", "conclusion": "failure", "html_url": "https://github.com/octo/shop/runs/2"}]})
        if path.endswith("/pulls"):
            return httpx.Response(200, json=[{"number": 1}, {"number": 2}, {"number": 3}])
        return httpx.Response(404, json={"message": "Not Found"})


@pytest.fixture
def gh(monkeypatch):
    fake = FakeGitHub()
    monkeypatch.setattr(github, "transport", httpx.MockTransport(fake))
    return fake


def test_parse_repo():
    ok = {"octo/shop": ("octo", "shop"), "https://github.com/octo/shop": ("octo", "shop"),
          "https://github.com/octo/shop.git": ("octo", "shop"), "git@github.com:octo/my.site.git": ("octo", "my.site"),
          "https://github.com/octo/shop/": ("octo", "shop")}
    for text, want in ok.items():
        assert github.parse_repo(text) == want, text
    for bad in ("", "shop", "https://gitlab.com/a/b", "octo/../x", "a/b/c", "octo/sh op"):
        assert github.parse_repo(bad) is None, bad


def test_not_connected_by_default(client, gh):
    st = client.get("/api/github/status").json()
    assert st["connected"] is False and st["source"] is None and st["user"] is None
    assert st["projects_dir"]
    assert client.get("/api/github/repos").status_code == 401


def test_token_is_checked_saved_privately_and_never_returned(client, gh):
    assert client.post("/api/github/token", json={"token": "nope"}).status_code == 400
    assert client.post("/api/github/token", json={"token": "ghp_" + "b" * 36}).status_code == 400  # GitHub says no
    r = client.post("/api/github/token", json={"token": TOKEN})
    assert r.status_code == 200 and r.json()["user"]["login"] == "octo"
    st = client.get("/api/github/status")
    assert st.json()["connected"] and st.json()["source"] == "homeport"
    assert TOKEN not in st.text
    if os.name != "nt":
        assert stat.S_IMODE(os.stat(github._file()).st_mode) == 0o600
    assert client.post("/api/github/disconnect").json()["disconnected"] is True
    assert client.get("/api/github/status").json()["connected"] is False


def test_device_flow(client, gh, monkeypatch):
    assert github.CLIENT_ID.startswith("Ov23")  # Homeport's public OAuth app (device flow)
    monkeypatch.setattr(github, "CLIENT_ID", "")
    assert client.post("/api/github/device/start").status_code == 501  # a build without one
    monkeypatch.setattr(github, "CLIENT_ID", "Iv1.test")
    assert client.get("/api/github/status").json()["device_flow"] is True
    start = client.post("/api/github/device/start").json()
    assert start["user_code"] == "ABCD-1234" and start["verification_uri"].startswith("https://github.com/")
    assert client.post("/api/github/device/poll").json()["status"] == "pending"
    done = client.post("/api/github/device/poll").json()
    assert done["status"] == "done" and done["user"]["login"] == "octo"
    assert json.load(open(github._file()))["how"] == "device"
    assert client.post("/api/github/device/poll").json()["status"] == "expired"  # nothing in progress any more


def test_gh_cli_login_is_used(client, gh, monkeypatch):
    monkeypatch.setattr(github, "_gh_token", lambda: TOKEN)
    st = client.get("/api/github/status").json()
    assert st["connected"] and st["source"] == "gh"


def test_repos_list_and_search(client, gh):
    github._save(TOKEN, "token")
    names = [r["full_name"] for r in client.get("/api/github/repos").json()["repos"]]
    assert names == ["octo/shop", "octo/blog"]
    found = client.get("/api/github/repos", params={"q": "store"}).json()["repos"]
    assert [r["full_name"] for r in found] == ["octo/shop"] and found[0]["private"] is True


def _make_repo(folder) -> str:
    folder.mkdir()
    (folder / "index.html").write_text("<h1>hello</h1>")
    run = lambda *a: subprocess.run(["git", *a], cwd=folder, check=True, capture_output=True)  # noqa: E731
    run("init", "-q")
    run("add", ".")
    run("-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-q", "-m", "init")
    return str(folder)


@needs_git
def test_clone_adds_the_app(client, gh, tmp_path, monkeypatch):
    source = _make_repo(tmp_path / "source")
    projects = tmp_path / "projects"
    app_settings.update({"projects_dir": str(projects)})
    monkeypatch.setattr(github, "clone_url", lambda owner, repo: source)
    r = client.post("/api/github/clone", json={"repo": "https://github.com/octo/landing-page", "start": False})
    assert r.status_code == 200, r.text
    app = r.json()["app"]
    assert app["name"] == "Landing page" and app["path"] == str(projects / "landing-page")
    assert (projects / "landing-page" / "index.html").exists() and app["command"]
    # never into a folder that exists and isn't empty
    again = client.post("/api/github/clone", json={"repo": "octo/landing-page"})
    assert again.status_code == 409
    assert client.post("/api/github/clone", json={"repo": "not a repo"}).status_code == 400
    assert client.post("/api/github/clone", json={"repo": "octo/x", "name": "../evil"}).status_code == 400


def test_projects_dir_setting_validation(client, tmp_path):
    assert client.patch("/api/settings", json={"projects_dir": str(tmp_path / "new")}).status_code == 200
    f = tmp_path / "file.txt"
    f.write_text("x")
    assert client.patch("/api/settings", json={"projects_dir": str(f)}).status_code == 400
    assert client.patch("/api/settings", json={"projects_dir": "/no/such/parent/here"}).status_code == 400


def test_checks_summary():
    s = github._summarize_checks
    assert s([], None) == (None, None)
    assert s([{"status": "completed", "conclusion": "success", "html_url": "u"}], None) == ("success", "u")
    assert s([{"status": "in_progress", "html_url": "p"}, {"status": "completed", "conclusion": "failure"}], None)[0] == "pending"
    assert s([{"status": "completed", "conclusion": "skipped"}, {"status": "completed", "conclusion": "failure", "html_url": "f"}], None) == ("failure", "f")
    assert s([], "error") == ("failure", None)


def test_card_info_from_github(gh):
    info = github._fetch_card("octo/shop", "main", TOKEN)
    assert info == {"ci": "failure", "ci_url": "https://github.com/octo/shop/runs/2", "prs": 3}


@needs_git
def test_card_state_reads_the_remote(tmp_path, gh, monkeypatch):
    repo = _make_repo(tmp_path / "app")
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/octo/shop.git"], cwd=repo, check=True)
    assert github._remote_repo(repo) == "octo/shop"
    # not connected: link only; the remote lookup runs in the background, so prime the cache
    github._remote_cache[("remote", repo)] = (9e18, "octo/shop")
    state = github.card_state(repo, {"branch": "main"})
    assert state["url"] == "https://github.com/octo/shop" and state["ci"] is None
    github._save(TOKEN, "token")
    github._card_cache[("card", "octo/shop", "main")] = (9e18, {"ci": "success", "ci_url": "u", "prs": 2})
    assert github.card_state(repo, {"branch": "main"})["prs"] == 2
    assert github.card_state(repo, None) is None


@needs_git
def test_pull_uses_the_login_for_github_remotes(tmp_path, gh):
    repo = _make_repo(tmp_path / "app")
    git = shutil.which("git")
    assert gitinfo._github_auth(git, repo) == {}  # no remote
    subprocess.run(["git", "remote", "add", "origin", "https://github.com/octo/shop.git"], cwd=repo, check=True)
    assert gitinfo._github_auth(git, repo) == {}  # not connected
    github._save(TOKEN, "token")
    env = gitinfo._github_auth(git, repo)
    assert env["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader" and TOKEN not in env["GIT_CONFIG_VALUE_0"]
    assert "x-access-token" not in open(os.path.join(repo, ".git", "config")).read()
