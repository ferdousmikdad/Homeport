"""Named URLs, recipes, crash diagnosis, git, discovery and workspaces."""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import sys

import pytest

from _helpers import sleep_cmd, wait_until

from backend import detect, diagnose, gitinfo, proxy, recipes, shellenv


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --- named URLs -----------------------------------------------------------------
@pytest.mark.parametrize("host,expected", [
    ("blog.localhost:7777", ("app", "blog")),
    ("blog.localhost", ("app", "blog")),
    ("blog.share.localhost", ("share", "blog")),
    ("localhost:7777", None),
    ("127.0.0.1:7777", None),
    ("a.b.localhost", None),
    ("example.com", None),
])
def test_proxy_routes_by_host(host, expected):
    assert proxy._route(host) == expected


def test_named_url_serves_running_app(client, isolated_registry, tmp_path):
    (tmp_path / "index.html").write_text("<h1>hello from the app</h1>")
    port = _free_port()
    cmd = f'"{sys.executable}" -m http.server {port} --bind 127.0.0.1'
    isolated_registry.add({"name": "Site", "path": str(tmp_path), "command": cmd, "port": port})
    host = {"Host": "site.localhost:7777"}

    assert client.get("/", headers=host).status_code == 503  # not running yet
    assert client.post("/api/apps/site/start").status_code == 200
    assert wait_until(lambda: client.get("/api/apps/site").json()["status"] == "running", timeout=15)
    resp = client.get("/", headers=host)
    assert resp.status_code == 200 and "hello from the app" in resp.text
    assert client.get("/", headers={"Host": "nope.localhost:7777"}).status_code == 404
    assert client.get("/api/health").status_code == 200  # dashboard unaffected
    client.post("/api/apps/site/stop")


# --- recipes --------------------------------------------------------------------
def test_recipe_matching_rules(tmp_path):
    recipe = {
        "name": "Thing", "command": "thing serve --port {port}", "port": 4321,
        "match": {"all": ["thing.toml|thing.yaml"], "any": ["src", "pages"], "none": ["package.json"],
                  "contains": {"thing.toml": "engine\\s*="}},
    }
    (tmp_path / "thing.toml").write_text("engine = 2")
    assert recipes.match_recipe(str(tmp_path), windows=False, which=lambda t: t, recipes=[recipe]) is None
    (tmp_path / "src").mkdir()
    assert recipes.match_recipe(str(tmp_path), windows=False, which=lambda t: t, recipes=[recipe])
    (tmp_path / "package.json").write_text("{}")
    assert recipes.match_recipe(str(tmp_path), windows=False, which=lambda t: t, recipes=[recipe]) is None


def test_recipe_requires_tool(tmp_path):
    recipe = {"name": "X", "command": "x", "requires": ["xtool"], "match": {"all": ["x.cfg"]}}
    (tmp_path / "x.cfg").write_text("")
    assert recipes.match_recipe(str(tmp_path), windows=False, which=lambda t: None, recipes=[recipe]) is None


def test_user_recipe_drives_detection(tmp_path, monkeypatch):
    rdir = tmp_path / "recipes"
    rdir.mkdir()
    (rdir / "widget.json").write_text(json.dumps({
        "name": "Widget", "port": 4100, "match": {"all": ["widget.conf"]},
        "setup": [{"unless": "deps", "run": "widget install"}],
        "command": "widget serve --port {port}", "command_windows": "widget.exe serve --port {port}",
    }))
    monkeypatch.setattr(recipes, "RECIPE_DIRS", [str(rdir)])
    monkeypatch.setattr(recipes, "_cache", {"at": 0.0, "recipes": []})
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "widget.conf").write_text("")
    r = detect.detect(str(proj))
    assert r == {"type": "Widget", "port": 4100, "command": "widget install && widget serve --port 4100"}
    monkeypatch.setattr(detect, "WINDOWS", True)
    assert detect.detect(str(proj))["command"].endswith("widget.exe serve --port 4100")


def test_shipped_recipes_are_valid():
    shipped = recipes.load_recipes([recipes.RECIPE_DIRS[0]])
    assert {r["name"] for r in shipped} >= {"Hugo", "Jekyll", "MkDocs", "Phoenix"}


# --- crash diagnosis --------------------------------------------------------------
def _ids(cfg, lines, **kw):
    return [f["id"] for f in diagnose.diagnose(cfg, lines, **kw)]


@pytest.mark.parametrize("line,expected", [
    ("Error: listen EADDRINUSE: address already in use :::3000", "port_in_use"),
    ("sh: php: command not found", "missing_tool"),
    ("'composer' is not recognized as an internal or external command,", "missing_tool"),
    ("ModuleNotFoundError: No module named 'flask'", "python_deps"),
    ("npm error Missing script: \"dev\"", "missing_script"),
    ("SQLSTATE[HY000] [2002] Connection refused", "database_down"),
    ("No application encryption key has been specified.", "laravel_key"),
])
def test_diagnosis_patterns(tmp_path, line, expected):
    assert expected in _ids({"path": str(tmp_path)}, ["[manager] x started pid=1 cmd=y", line])


def test_node_packages_missing(tmp_path):
    (tmp_path / "package.json").write_text("{}")
    lines = ["npm error npx canceled due to missing packages and no YES option: [\"vite@5\"]"]
    finding = diagnose.diagnose({"path": str(tmp_path)}, lines)[0]
    assert finding["id"] == "node_modules"
    assert [f["action"] for f in finding["fixes"]] == ["install_node"]


def test_diagnosis_only_reads_latest_run(tmp_path):
    lines = ["ModuleNotFoundError: No module named 'old'", "[manager] t started pid=2 cmd=x", "all good"]
    assert _ids({"path": str(tmp_path)}, lines) == ["unknown"]


def test_fix_copies_env_and_rejects_unknown_actions(tmp_path):
    (tmp_path / ".env.example").write_text("KEY=1")
    assert diagnose.run_fix({"path": str(tmp_path)}, "copy_env")["ok"]
    assert (tmp_path / ".env").read_text() == "KEY=1"
    with pytest.raises(ValueError):
        diagnose.run_fix({"path": str(tmp_path)}, "rm -rf /")


def test_fix_route_runs_only_known_actions(client, isolated_registry, tmp_path):
    isolated_registry.add({"name": "App", "path": str(tmp_path), "command": sleep_cmd(1)})
    assert client.post("/api/apps/app/fix", json={"action": "echo hi"}).status_code == 400
    (tmp_path / ".env.example").write_text("A=1")
    assert client.post("/api/apps/app/fix", json={"action": "copy_env"}).json()["ok"] is True
    assert "findings" in client.get("/api/apps/app/diagnose").json()


# --- git ----------------------------------------------------------------------------
@pytest.mark.skipif(not shutil.which("git"), reason="git not installed")
def test_git_status_on_a_repo(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q", "-b", "main")
    git("-c", "user.email=t@example.com", "-c", "user.name=T", "commit", "-q", "--allow-empty", "-m", "init")
    (tmp_path / "new.txt").write_text("x")
    info = gitinfo.read(str(tmp_path))
    assert info["branch"] == "main" and info["dirty"] == 1
    assert gitinfo.read(str(tmp_path / "missing")) is None


# --- discovery & workspaces ----------------------------------------------------------
def test_discover_lists_projects(client, isolated_registry, tmp_path):
    (tmp_path / "blog").mkdir()
    (tmp_path / "blog" / "index.html").write_text("hi")
    (tmp_path / "api").mkdir()
    (tmp_path / "api" / "manage.py").write_text("")
    (tmp_path / "notes").mkdir()
    isolated_registry.add({"name": "Blog", "path": str(tmp_path / "blog"), "command": "x"})
    res = client.post("/api/discover", json={"path": str(tmp_path)}).json()
    by_name = {p["name"]: p for p in res["projects"]}
    assert set(by_name) == {"Api", "Blog"}
    assert by_name["Blog"]["registered"] and not by_name["Api"]["registered"]
    assert by_name["Api"]["type"] == "Django"


def test_workspace_starts_group_in_order(client, isolated_registry, tmp_path):
    for name in ("One", "Two"):
        isolated_registry.add({"name": name, "path": str(tmp_path), "command": sleep_cmd(30), "category": "Stack"})
    isolated_registry.add({"name": "Other", "path": str(tmp_path), "command": sleep_cmd(30)})
    assert client.post("/api/groups/start", json={"category": "Stack"}).json()["ids"] == ["one", "two"]
    running = lambda: {a["id"] for a in client.get("/api/apps").json() if a["status"] == "running"}  # noqa: E731
    assert wait_until(lambda: running() == {"one", "two"}, timeout=20)
    client.post("/api/groups/stop", json={"category": "Stack"})
    assert wait_until(lambda: not running(), timeout=15)
    assert client.post("/api/groups/start", json={"category": "Nope"}).status_code == 404
