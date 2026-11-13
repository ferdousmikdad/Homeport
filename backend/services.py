"""backend/services.py — databases & dev services as one-click apps.

Each service becomes a normal Homeport app (start/stop/logs/auto-restart all
work) whose folder is ``data/services/<id>/``. It runs with the server that
is already installed on this computer, or through Docker if that is
installed instead. Nothing needs an account; data stays in that folder (or a
named Docker volume).

Generated commands work in both ``sh`` and Windows ``cmd.exe``; first-run
setup (``initdb`` …) only runs when the data folder isn't initialised yet.
"""

from __future__ import annotations

import os
from typing import Callable, Optional

from . import osutil, shellenv

__all__ = ["CATALOG", "catalog", "plan", "SERVICES_DIR"]

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVICES_DIR = os.path.join(_PROJECT_ROOT, "data", "services")

_INSTALL = {
    "postgres": {
        "mac": "Postgres.app (free) — postgresapp.com, or: brew install postgresql@16",
        "windows": "winget install PostgreSQL.PostgreSQL.16",
        "linux": "sudo apt install postgresql",
    },
    "mysql": {
        "mac": "brew install mysql   (or mariadb)",
        "windows": "winget install Oracle.MySQL   (or MariaDB.Server)",
        "linux": "sudo apt install mariadb-server",
    },
    "redis": {
        "mac": "brew install redis",
        "windows": "Use Docker Desktop, or Memurai (Redis-compatible)",
        "linux": "sudo apt install redis-server",
    },
    "mongodb": {
        "mac": "brew tap mongodb/brew && brew install mongodb-community",
        "windows": "winget install MongoDB.Server",
        "linux": "See mongodb.com/docs/manual/administration/install-on-linux",
    },
    "mailpit": {
        "mac": "brew install mailpit",
        "windows": "Download from github.com/axllent/mailpit/releases",
        "linux": "sudo sh < <(curl -sL https://raw.githubusercontent.com/axllent/mailpit/develop/install.sh)",
    },
}

CATALOG = {
    "postgres": {
        "name": "PostgreSQL", "port": 5432, "description": "Relational database",
        "native": ["postgres", "initdb"], "image": "postgres:16", "container_port": 5432,
        "docker_env": {"POSTGRES_HOST_AUTH_METHOD": "trust"}, "volume": "/var/lib/postgresql/data",
        "url": "postgresql://postgres@127.0.0.1:{port}/postgres",
        "env": {"DB_CONNECTION": "pgsql", "DB_HOST": "127.0.0.1", "DB_PORT": "{port}",
                "DB_DATABASE": "postgres", "DB_USERNAME": "postgres", "DB_PASSWORD": "",
                "DATABASE_URL": "{url}"},
    },
    "mysql": {
        "name": "MySQL / MariaDB", "port": 3306, "description": "Relational database",
        "native": [], "image": "mysql:8.4", "container_port": 3306,
        "docker_env": {"MYSQL_ALLOW_EMPTY_PASSWORD": "yes"}, "volume": "/var/lib/mysql",
        "url": "mysql://root@127.0.0.1:{port}/",
        "env": {"DB_CONNECTION": "mysql", "DB_HOST": "127.0.0.1", "DB_PORT": "{port}",
                "DB_DATABASE": "app", "DB_USERNAME": "root", "DB_PASSWORD": "",
                "DATABASE_URL": "{url}app"},
    },
    "redis": {
        "name": "Redis", "port": 6379, "description": "Cache, queues & sessions",
        "native": ["redis-server"], "image": "redis:7", "container_port": 6379,
        "docker_env": {}, "volume": "/data",
        "url": "redis://127.0.0.1:{port}",
        "env": {"REDIS_HOST": "127.0.0.1", "REDIS_PORT": "{port}", "REDIS_URL": "{url}"},
    },
    "mongodb": {
        "name": "MongoDB", "port": 27017, "description": "Document database",
        "native": ["mongod"], "image": "mongo:7", "container_port": 27017,
        "docker_env": {}, "volume": "/data/db",
        "url": "mongodb://127.0.0.1:{port}",
        "env": {"MONGODB_URI": "{url}", "MONGO_URL": "{url}"},
    },
    "mailpit": {
        "name": "Mailpit", "port": 8025, "smtp_port": 1025, "description": "Catches outgoing email (web inbox)",
        "native": ["mailpit"], "image": "axllent/mailpit", "container_port": 8025, "container_smtp": 1025,
        "docker_env": {}, "volume": "/data",
        "url": "smtp://127.0.0.1:{smtp}",
        "env": {"MAIL_MAILER": "smtp", "MAIL_HOST": "127.0.0.1", "MAIL_PORT": "{smtp}",
                "SMTP_URL": "{url}"},
    },
}


def _mysql_flavour(which: Callable[[str], Optional[str]]) -> Optional[str]:
    if which("mariadbd") and (which("mariadb-install-db") or which("mysql_install_db")):
        return "mariadb"
    if which("mysqld"):
        return "mysql"
    return None


def availability(kind: str, which: Optional[Callable[[str], Optional[str]]] = None) -> dict:
    which = which or shellenv.which
    meta = CATALOG[kind]
    if kind == "mysql":
        native = _mysql_flavour(which) is not None
    else:
        native = all(which(tool) for tool in meta["native"])
    return {"native": native, "docker": bool(which("docker"))}


def catalog(which: Optional[Callable[[str], Optional[str]]] = None) -> list:
    which = which or shellenv.which
    system = osutil.platform_name()
    out = []
    for kind, meta in CATALOG.items():
        avail = availability(kind, which)
        out.append({
            "kind": kind, "name": meta["name"], "description": meta["description"],
            "port": meta["port"], "native": avail["native"], "docker": avail["docker"],
            "install": _INSTALL[kind].get(system, _INSTALL[kind]["linux"]),
        })
    return out


def _guard(windows: bool, marker: str, setup: str, run: str) -> str:
    """Run ``setup`` only when ``marker`` (relative path) is missing, then ``run``."""
    if windows:
        win_marker = marker.replace("/", "\\")
        return f"(if not exist {win_marker} ({setup})) && {run}"
    return f"( [ -e {marker} ] || {setup} ) && {run}"


def _native_command(kind: str, port: int, smtp: Optional[int], folder: str, windows: bool,
                    which: Callable[[str], Optional[str]]) -> str:
    quiet = ">nul" if windows else ">/dev/null"
    if kind == "postgres":
        sockets = "" if windows else " -k ''"
        return _guard(windows, "data/PG_VERSION",
                      f"initdb -D data -U postgres --auth=trust --encoding=UTF8 {quiet}",
                      f"postgres -D data -p {port} -h 127.0.0.1{sockets}")
    if kind == "mysql":
        datadir = os.path.join(folder, "data")
        q = f'"{datadir}"'
        if _mysql_flavour(which) == "mariadb":
            installer = "mariadb-install-db" if which("mariadb-install-db") else "mysql_install_db"
            setup = f"{installer} --datadir={q} --auth-root-authentication-method=normal --skip-test-db {quiet}"
            run = f"mariadbd --no-defaults --datadir={q} --port={port} --bind-address=127.0.0.1"
        else:
            setup = f"mysqld --no-defaults --initialize-insecure --datadir={q} {quiet}"
            run = f"mysqld --no-defaults --datadir={q} --port={port} --bind-address=127.0.0.1 --mysqlx=OFF"
        if not windows:
            run += f' --socket="{os.path.join(folder, "mysql.sock")}"'
        return _guard(windows, "data/mysql", setup, run)
    if kind == "redis":
        return f"redis-server --port {port} --bind 127.0.0.1 --dir data --save 60 1 --appendonly no"
    if kind == "mongodb":
        return f"mongod --dbpath data --port {port} --bind_ip 127.0.0.1"
    if kind == "mailpit":
        return f"mailpit --listen 127.0.0.1:{port} --smtp 127.0.0.1:{smtp} --database data/mailpit.db"
    raise ValueError(kind)


def _docker_command(kind: str, app_id: str, port: int, smtp: Optional[int], windows: bool) -> str:
    meta = CATALOG[kind]
    name = f"homeport-{app_id}"
    parts = ["docker run --rm", f"--name {name}", f"-p 127.0.0.1:{port}:{meta['container_port']}"]
    if smtp:
        parts.append(f"-p 127.0.0.1:{smtp}:{meta['container_smtp']}")
    for key, value in meta["docker_env"].items():
        parts.append(f"-e {key}={value}")
    parts.append(f"-v {name}:{meta['volume']}")
    parts.append(meta["image"])
    # a container left over from a crash would block the name
    cleanup = f"docker rm -f {name} >nul 2>&1 &" if windows else f"docker rm -f {name} >/dev/null 2>&1;"
    return f"{cleanup} {' '.join(parts)}"


def connection(kind: str, port: int, smtp: Optional[int] = None) -> dict:
    meta = CATALOG[kind]
    url = meta["url"].format(port=port, smtp=smtp or "")
    env = {k: v.format(port=port, smtp=smtp or "", url=url) for k, v in meta["env"].items()}
    return {"url": url, "env": env}


def plan(kind: str, app_id: str, port: int, *, smtp_port: Optional[int] = None,
         mode: Optional[str] = None, windows: Optional[bool] = None,
         which: Optional[Callable[[str], Optional[str]]] = None) -> dict:
    """Everything needed to register the service as an app."""
    which = which or shellenv.which
    if kind not in CATALOG:
        raise ValueError(f"unknown service: {kind}")
    win = osutil.IS_WINDOWS if windows is None else windows
    avail = availability(kind, which)
    if mode is None:
        mode = "native" if avail["native"] else "docker" if avail["docker"] else None
    if mode is None or not avail.get(mode):
        raise LookupError(f"{CATALOG[kind]['name']} isn't installed — install it or Docker first")
    folder = os.path.join(SERVICES_DIR, app_id)
    smtp = smtp_port if kind == "mailpit" else None
    if mode == "native":
        command = _native_command(kind, port, smtp, folder, win, which)
    else:
        command = _docker_command(kind, app_id, port, smtp, win)
    conn = connection(kind, port, smtp)
    return {
        "path": folder,
        "command": command,
        "port": port,
        "service": {"kind": kind, "mode": mode, "smtp_port": smtp, **conn},
    }
