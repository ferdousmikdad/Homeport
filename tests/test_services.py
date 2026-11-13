"""Databases & services as apps (command generation + API)."""

from __future__ import annotations

import pytest

from backend import services


def which_only(*tools):
    return lambda t: f"/bin/{t}" if t in tools else None


def test_postgres_native_posix_and_windows():
    w = which_only("postgres", "initdb")
    posix = services.plan("postgres", "pg", 5433, windows=False, which=w)
    assert posix["command"] == ("( [ -e data/PG_VERSION ] || initdb -D data -U postgres --auth=trust "
                                "--encoding=UTF8 >/dev/null ) && postgres -D data -p 5433 -h 127.0.0.1 -k ''")
    assert posix["service"]["url"] == "postgresql://postgres@127.0.0.1:5433/postgres"
    assert posix["service"]["env"]["DB_PORT"] == "5433"
    win = services.plan("postgres", "pg", 5433, windows=True, which=w)
    assert win["command"].startswith("(if not exist data\\PG_VERSION (initdb ")
    assert win["command"].endswith("&& postgres -D data -p 5433 -h 127.0.0.1")


def test_docker_fallback_and_mailpit_ports():
    w = which_only("docker")
    d = services.plan("redis", "redis", 6380, windows=False, which=w)
    assert d["service"]["mode"] == "docker"
    assert "docker run --rm --name homeport-redis -p 127.0.0.1:6380:6379" in d["command"]
    assert "-v homeport-redis:/data redis:7" in d["command"]
    m = services.plan("mailpit", "mailpit", 8025, smtp_port=1026, windows=True, which=w)
    assert "-p 127.0.0.1:1026:1025" in m["command"] and m["command"].startswith("docker rm -f homeport-mailpit >nul 2>&1 &")
    assert m["service"]["url"] == "smtp://127.0.0.1:1026"


def test_mariadb_preferred_when_present():
    w = which_only("mariadbd", "mariadb-install-db", "mysqld")
    p = services.plan("mysql", "db", 3307, windows=False, which=w)
    assert "mariadb-install-db" in p["command"] and "mariadbd --no-defaults" in p["command"]


def test_not_installed_raises():
    with pytest.raises(LookupError):
        services.plan("mongodb", "m", 27017, which=which_only())
    with pytest.raises(ValueError):
        services.plan("nope", "x", 1, which=which_only("docker"))


def test_catalog_reports_availability():
    cat = {s["kind"]: s for s in services.catalog(which=which_only("redis-server"))}
    assert cat["redis"]["native"] and not cat["postgres"]["native"]
    assert cat["mongodb"]["install"]


def test_api_add_service_creates_app(client, isolated_registry, tmp_path, monkeypatch):
    monkeypatch.setattr(services, "SERVICES_DIR", str(tmp_path / "services"))
    monkeypatch.setattr(services.shellenv, "which", which_only("redis-server"))
    st = client.post("/api/services", json={"kind": "redis", "start": False}).json()
    assert st["category"] == "Services" and st["service"]["kind"] == "redis"
    assert st["command"].startswith("redis-server --port ")
    assert (tmp_path / "services" / st["id"] / "icon.svg").exists()
    again = client.post("/api/services", json={"kind": "redis", "start": False}).json()
    assert again["name"] == "Redis 2" and again["port"] != st["port"]
    missing = client.post("/api/services", json={"kind": "mongodb"})
    assert missing.status_code == 409
    assert [a["name"] for a in client.get("/api/apps").json()] == ["Redis", "Redis 2"]
