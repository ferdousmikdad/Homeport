"""homeport.json: reading, checking, setting up and saving a project (docs/V1.2.md §1)."""
from __future__ import annotations

import json

import pytest

from _helpers import sleep_cmd, wait_until
from backend import project_file


def _repo(tmp_path, data, folders=("api", "web")):
    root = tmp_path / "shop"
    root.mkdir()
    for f in folders:
        (root / f).mkdir()
    (root / "web" / "index.html").write_text("<h1>web</h1>") if "web" in folders else None
    (root / "homeport.json").write_text(json.dumps(data))
    return root


def test_parse_checks_the_file(tmp_path):
    good = _repo(tmp_path, {"name": "Shop", "services": ["postgres", "nosql"],
                            "apps": [{"name": "API", "path": "api", "env": {"DB": "{redis.url}"}}, {"path": "web"}]})
    p = project_file.parse(str(good / "homeport.json"))
    assert p["name"] == "Shop" and p["services"] == ["postgres"] and [a["name"] for a in p["apps"]] == ["API", "web"]
    assert any("nosql" in w for w in p["warnings"]) and any("redis" in w for w in p["warnings"])
    bad = [
        {"apps": []},
        {"apps": [{"path": "../outside"}]},
        {"apps": [{"path": "/etc"}]},
        {"apps": [{"path": "api", "port": 70000}]},
        {"apps": [{"path": "api", "health": "up"}]},
        {"apps": [{"path": "api", "env": {"bad key": "x"}}]},
        {"apps": [{"name": "A", "path": "api"}, {"name": "a", "path": "web"}]},
    ]
    for i, data in enumerate(bad):
        (good / "homeport.json").write_text(json.dumps(data))
        with pytest.raises(project_file.ProjectError):
            project_file.parse(str(good / "homeport.json"))
    (good / "homeport.json").write_text("{not json")
    with pytest.raises(project_file.ProjectError):
        project_file.parse(str(good / "homeport.json"))


def test_inspect_detects_commands_and_existing_apps(client, isolated_registry, tmp_path):
    root = _repo(tmp_path, {"name": "Shop", "apps": [{"name": "Web", "path": "web"}, {"name": "API", "path": "api", "command": "x --port {port}", "port": 8123}]})
    isolated_registry.add({"name": "Already", "path": str(root / "api"), "command": "true"})
    data = client.get("/api/project", params={"path": str(root)}).json()
    assert data["found"] and data["name"] == "Shop"
    web, api = data["apps"]
    assert web["detected"] and web["command"] and web["registered"] is None
    assert api["registered"] and api["command"] == "x --port {port}"
    assert client.get("/api/project", params={"path": str(tmp_path)}).json() == {"found": False}
    (root / "homeport.json").write_text("[]")
    assert "error" in client.get("/api/project", params={"path": str(root)}).json()


def test_setup_adds_apps_reuses_databases_and_fills_values(client, isolated_registry, tmp_path):
    isolated_registry.add({"name": "PostgreSQL", "path": str(tmp_path), "command": "", "port": 5433,
                           "category": "Services",
                           "service": {"kind": "postgres", "url": "postgresql://postgres@127.0.0.1:5433/postgres"}})
    root = _repo(tmp_path, {"name": "Shop", "services": ["postgres"], "apps": [
        {"name": "API", "path": "api", "command": "serve --port {port}", "port": 8123,
         "env": {"DB_PORT": "{postgres.port}", "DATABASE_URL": "{postgres.url}", "MODE": "dev"}, "health": "/up"},
        {"name": "Web", "path": "web"},
    ]})
    r = client.post("/api/project/setup", json={"path": str(root), "start": False})
    assert r.status_code == 200, r.text
    res = r.json()
    assert [a["name"] for a in res["created"]] == ["API", "Web"] and res["reused_services"] == ["PostgreSQL"]
    api = next(a for a in isolated_registry.list() if a["name"] == "API")
    assert api["category"] == "Shop" and api["env"] == {"DB_PORT": "5433", "DATABASE_URL": "postgresql://postgres@127.0.0.1:5433/postgres", "MODE": "dev"}
    assert api["command"] == f"serve --port {api['port']}" and api["health_url"] == f"http://127.0.0.1:{api['port']}/up"
    web = next(a for a in isolated_registry.list() if a["name"] == "Web")
    assert web["command"] and web["category"] == "Shop"
    # running it again adds nothing twice
    again = client.post("/api/project/setup", json={"path": str(root)}).json()
    assert again["created"] == [] and sorted(again["skipped"]) == ["API", "Web"]


def test_setup_can_start_the_group_in_order(client, tmp_path):
    root = _repo(tmp_path, {"name": "Demo", "apps": [{"name": "One", "path": "api", "command": sleep_cmd(30)}]}, folders=("api",))
    assert client.post("/api/project/setup", json={"path": str(root), "start": True}).status_code == 200
    assert wait_until(lambda: client.get("/api/apps").json()[0]["status"] in ("running", "starting"), timeout=15)
    client.post("/api/groups/stop", json={"category": "Demo"})


def test_export_round_trip(client, isolated_registry, tmp_path):
    isolated_registry.add({"name": "Redis", "path": str(tmp_path), "command": "", "port": 6390, "category": "Services",
                           "service": {"kind": "redis", "url": "redis://127.0.0.1:6390"}})
    root = tmp_path / "proj"
    (root / "api").mkdir(parents=True)
    (root / "web").mkdir()
    (root / "web" / "index.html").write_text("<h1>x</h1>")
    isolated_registry.add({"name": "API", "path": str(root / "api"), "command": f"{root / 'api'}/.venv/bin/python app.py --port 9001",
                           "port": 9001, "category": "Proj", "env": {"REDIS_URL": "redis://127.0.0.1:6390", "X": "1"},
                           "health_url": "http://127.0.0.1:9001/health"})
    r = client.post("/api/project/export", json={"category": "Proj"}).json()
    data = json.loads(r["text"])
    assert r["root"] == str(root / "api") or r["root"] == str(root)  # one app: its own folder
    assert data["services"] == ["redis"]
    app = data["apps"][0]
    assert app["command"] == "./.venv/bin/python app.py --port {port}" and app["env"]["REDIS_URL"] == "{redis.url}"
    assert app["health"] == "/health" and str(tmp_path) not in r["text"]
    isolated_registry.add({"name": "Web", "path": str(root / "web"), "command": "", "category": "Proj"})
    two = client.post("/api/project/export", json={"category": "Proj", "write": True}).json()
    assert two["root"] == str(root) and (root / "homeport.json").exists()
    assert [a["path"] for a in json.loads(two["text"])["apps"]] == ["api", "web"]
    assert client.post("/api/project/export", json={"category": "Proj", "write": True}).status_code == 409
    assert client.post("/api/project/export", json={"category": "Proj", "write": True, "overwrite": True}).status_code == 200
    assert client.post("/api/project/export", json={"category": "Nope"}).status_code == 400
    # and the saved file reads back
    assert project_file.parse(str(root / "homeport.json"))["name"] == "Proj"


def test_discover_flags_a_project_file(client, tmp_path):
    root = _repo(tmp_path, {"apps": [{"path": "web"}]}, folders=("web",))
    assert client.post("/api/discover", json={"path": str(root)}).json()["project_file"] is True
    assert client.post("/api/discover", json={"path": str(root / "web")}).json()["project_file"] is False


def test_detected_apps_get_matching_free_ports(client, tmp_path):
    root = tmp_path / "two"
    for name in ("a", "b"):
        (root / name).mkdir(parents=True)
        (root / name / "index.html").write_text("<h1>%s</h1>" % name)
    (root / "homeport.json").write_text(json.dumps({"name": "Two", "apps": [{"path": "a"}, {"path": "b"}]}))
    review = client.get("/api/project", params={"path": str(root)}).json()
    assert all("{port}" in a["command"] for a in review["apps"])  # the review doesn't promise a port
    assert client.post("/api/project/setup", json={"path": str(root)}).status_code == 200
    apps = client.get("/api/apps").json()
    assert len({a["port"] for a in apps}) == 2  # two different ports
    for a in apps:
        assert str(a["port"]) in a["command"]  # each command uses its own port
