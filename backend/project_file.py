"""backend/project_file.py — ``homeport.json``: a repo's whole setup in one file.

See docs/V1.2.md §1. A repo can describe its apps (folders, commands, ports,
env), the databases they need and the order they start in. Homeport shows
that setup for review — including every command — and adds it only when the
user clicks *Set up*. A group of apps can also be saved back as a file.

    GET  /api/project?path=            read + check a homeport.json (nothing changes)
    POST /api/project/setup {path, start}
    POST /api/project/export {category, write, overwrite}
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Request

from . import monitor, services

router = APIRouter()

FILENAME = "homeport.json"
MAX_APPS = 30
asgi_app: Any = None          # the Homeport app (main.py), for in-process API calls
registry_list: Any = None     # main.py: () -> list of app configs

_PLACEHOLDER = re.compile(r"\{([a-z]+)\.(port|host|url|smtp_port)\}")


class ProjectError(ValueError):
    pass


# ---------------------------------------------------------------------------
# reading and checking the file
# ---------------------------------------------------------------------------
def find(path: str) -> Optional[str]:
    """The homeport.json for ``path`` (a folder or the file itself), or None."""
    path = os.path.abspath(os.path.expanduser((path or "").strip()))
    if os.path.basename(path) == FILENAME and os.path.isfile(path):
        return path
    candidate = os.path.join(path, FILENAME)
    return candidate if os.path.isfile(candidate) else None


def _text(value: Any, limit: int) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""


def parse(file: str) -> dict:
    """The checked contents of a homeport.json. Raises ProjectError with a readable message."""
    try:
        with open(file, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ProjectError(f"homeport.json can't be read: {exc}") from exc
    if not isinstance(data, dict):
        raise ProjectError("homeport.json must be a JSON object")
    root = os.path.dirname(os.path.abspath(file))
    name = _text(data.get("name"), 80) or os.path.basename(root)
    warnings: list = []

    kinds: list = []
    for k in data.get("services") or []:
        if not isinstance(k, str) or k not in services.CATALOG:
            warnings.append(f"unknown database {k!r} — known: {', '.join(services.CATALOG)}")
        elif k not in kinds:
            kinds.append(k)

    raw_apps = data.get("apps")
    if not isinstance(raw_apps, list) or not raw_apps:
        raise ProjectError("homeport.json needs an \"apps\" list with at least one app")
    if len(raw_apps) > MAX_APPS:
        raise ProjectError(f"homeport.json lists more than {MAX_APPS} apps")
    apps: list = []
    seen: set = set()
    for i, a in enumerate(raw_apps, 1):
        if not isinstance(a, dict):
            raise ProjectError(f"app #{i} must be an object")
        rel = _text(a.get("path"), 300) or "."
        if os.path.isabs(rel) or rel.replace("\\", "/").split("/").count("..") or rel.startswith("~"):
            raise ProjectError(f"app #{i}: path must be a folder inside the repo, like \"api\" (got {rel!r})")
        full = os.path.normpath(os.path.join(root, rel))
        if os.path.commonpath([root, full]) != root:
            raise ProjectError(f"app #{i}: path leaves the repo folder")
        app_name = _text(a.get("name"), 80) or (os.path.basename(full) if rel != "." else name)
        if app_name.casefold() in seen:
            raise ProjectError(f"two apps are called {app_name!r}")
        seen.add(app_name.casefold())
        command = a.get("command")
        if command is not None and not isinstance(command, str):
            raise ProjectError(f"{app_name}: command must be text")
        port = a.get("port")
        if port is not None and (not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535):
            raise ProjectError(f"{app_name}: port must be a number from 1 to 65535")
        env = a.get("env") or {}
        if not isinstance(env, dict) or len(env) > 100 or not all(isinstance(k, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k) for k in env):
            raise ProjectError(f"{app_name}: env must be an object of VARIABLE: value")
        env = {k: str(v) for k, v in env.items()}
        for value in env.values():
            for kind, _ in _PLACEHOLDER.findall(value):
                if kind not in kinds:
                    warnings.append(f"{app_name}: {{{kind}.…}} is used but {kind!r} isn't in \"services\"")
        health = _text(a.get("health"), 200)
        if health and not health.startswith("/"):
            raise ProjectError(f"{app_name}: health must be a path like /up")
        if not os.path.isdir(full):
            warnings.append(f"{app_name}: folder {rel!r} doesn't exist")
        apps.append({"name": app_name, "rel": rel, "path": full, "command": (command or "").strip()[:2000] or None,
                     "port": port, "env": env, "health": health or None, "auto_restart": a.get("auto_restart") is True})
    return {"file": file, "root": root, "name": name, "services": kinds, "apps": apps, "warnings": warnings}


def _norm(p: str) -> str:
    return os.path.normcase(os.path.abspath(p))


def _existing() -> list:
    return list(registry_list()) if registry_list else []


def _service_apps() -> dict:
    """kind -> the first existing database app of that kind."""
    out: dict = {}
    for cfg in _existing():
        kind = (cfg.get("service") or {}).get("kind")
        if kind and kind not in out:
            out[kind] = cfg
    return out


def inspect(path: str) -> dict:
    file = find(path)
    if not file:
        return {"found": False}
    project = parse(file)
    registered = {_norm(a["path"]): a for a in _existing()}
    have = _service_apps()
    for a in project["apps"]:
        reg = registered.get(_norm(a["path"]))
        a["registered"] = reg["id"] if reg else None
        a["detected"] = False
        if not a["command"] and os.path.isdir(a["path"]):
            det = monitor.detect_command(a["path"])
            a["command"], a["detected"] = det.get("command") or None, bool(det.get("command"))
            # a free port is picked when it's added; show that instead of today's guess
            if a["detected"] and det.get("port") and not a["port"]:
                a["command"] = re.sub(rf"\b{det['port']}\b", "{port}", a["command"])
        if not a["command"] and not reg:
            project["warnings"].append(f"{a['name']}: no command given and Homeport can't tell how to run it")
    project["services"] = [{"kind": k, "name": services.CATALOG[k]["name"],
                            "existing": have[k]["id"] if k in have else None,
                            "existing_name": have[k]["name"] if k in have else None} for k in project["services"]]
    return {"found": True, **project}


# ---------------------------------------------------------------------------
# setting it up (through Homeport's own API, in-process)
# ---------------------------------------------------------------------------
async def _api(method: str, path: str, **kw) -> tuple:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=asgi_app), base_url="http://127.0.0.1",
                                 timeout=600.0) as c:
        r = await c.request(method, path, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"detail": r.text[:300]}


def _fill(value: str, svc: dict) -> str:
    """{postgres.port} → the database app's real value."""
    def sub(m):
        info = svc.get(m.group(1))
        if not info:
            return m.group(0)
        port = info.get("port")
        field = m.group(2)
        if field == "port":
            return str(port)
        if field == "host":
            return "127.0.0.1"
        if field == "smtp_port":
            return str((info.get("service") or {}).get("smtp_port") or "")
        return str((info.get("service") or {}).get("url") or "")
    return _PLACEHOLDER.sub(sub, value)


async def setup(path: str, start: bool) -> dict:
    from . import main  # late: main imports this module

    project = inspect(path)
    if not project.get("found"):
        raise ProjectError("there's no homeport.json in this folder")
    created_services, svc = [], {}
    have = _service_apps()
    for s in project["services"]:
        if s["existing"]:
            svc[s["kind"]] = have[s["kind"]]
            continue
        code, st = await _api("POST", "/api/services", json={"kind": s["kind"], "start": False})
        if code != 200:
            raise ProjectError(f"couldn't add {s['name']}: {st.get('detail')}")
        created_services.append(st)
        svc[s["kind"]] = st

    created, skipped = [], []
    for a in project["apps"]:
        if a["registered"]:
            skipped.append(a["name"])
            continue
        command = a["command"] or ""
        port = a["port"]
        if a["detected"]:  # Homeport detects the command and a free port itself, like Add app
            command, port = "", None
        if "{port}" in command:
            port = await asyncio.to_thread(main.free_port, port or 3000, main._registered_ports())
            command = command.replace("{port}", str(port))
        body = {"name": a["name"], "path": a["path"], "category": project["name"],
                "env": {k: _fill(v, svc) for k, v in a["env"].items()}, "auto_restart": a["auto_restart"]}
        if a["command"] and not a["detected"]:
            body["command"] = command
        if port:
            body["port"] = port
        if a["health"] and port:
            body["health_url"] = f"http://127.0.0.1:{port}{a['health']}"
        code, st = await _api("POST", "/api/apps", json=body)
        if code not in (200, 201):
            raise ProjectError(f"couldn't add {a['name']}: {st.get('detail')}")
        created.append(st)

    if start:
        for s in svc.values():
            if s.get("status") not in ("running", "starting"):
                await _api("POST", f"/api/apps/{s['id']}/start")
        await _api("POST", "/api/groups/start", json={"category": project["name"]})
    return {"name": project["name"], "created": created, "services": created_services,
            "reused_services": [s["existing_name"] for s in project["services"] if s["existing"]],
            "skipped": skipped, "started": bool(start)}


# ---------------------------------------------------------------------------
# saving a group as homeport.json
# ---------------------------------------------------------------------------
def export(category: str) -> dict:
    apps = [a for a in _existing() if (a.get("category") or "").strip() == category and not a.get("service")]
    if not apps:
        raise ProjectError("there are no apps in this group to save")
    paths = [os.path.abspath(a["path"]) for a in apps]
    try:
        root = os.path.commonpath(paths)
    except ValueError:
        raise ProjectError("these apps aren't in one folder (different drives)") from None
    if not os.path.isdir(root):
        root = os.path.dirname(root)
    if root in (os.path.abspath(os.sep), os.path.expanduser("~")):
        raise ProjectError("these apps don't share a project folder — put them under one folder first")

    # values of existing databases -> placeholders
    by_value: dict = {}
    for kind, cfg in _service_apps().items():
        if cfg.get("port"):
            by_value[str(cfg["port"])] = f"{{{kind}.port}}"
        url = (cfg.get("service") or {}).get("url")
        if url:
            by_value[url] = f"{{{kind}.url}}"
    used: list = []
    out_apps = []
    for a in apps:
        rel = os.path.relpath(os.path.abspath(a["path"]), root).replace(os.sep, "/")
        item: dict = {"name": a["name"], "path": rel}
        port = a.get("port")
        command = (a.get("command") or "").strip()
        if command:
            detected = (monitor.detect_command(a["path"]).get("command") or "").strip()
            same = lambda c: re.sub(r"\b\d{2,5}\b", "{n}", c.replace(os.path.abspath(a["path"]), "."))  # noqa: E731
            if not detected or same(detected) != same(command):
                portable = command.replace(os.path.abspath(a["path"]) + os.sep, "./").replace(os.path.abspath(a["path"]), ".")
                if port:
                    portable = re.sub(rf"\b{port}\b", "{port}", portable)
                item["command"] = portable
        if port and "command" in item:  # detected apps get a free port wherever they run
            item["port"] = port
        env = {}
        for k, v in (a.get("env") or {}).items():
            v = str(v)
            if v in by_value:
                kind = by_value[v][1:].split(".")[0]
                if kind not in used:
                    used.append(kind)
                v = by_value[v]
            env[k] = v
        if env:
            item["env"] = env
        health = a.get("health_url") or ""
        m = re.match(r"https?://(?:127\.0\.0\.1|localhost)(?::\d+)?(/.*)$", health)
        if m:
            item["health"] = m.group(1)
        if a.get("auto_restart"):
            item["auto_restart"] = True
        out_apps.append(item)
    data: dict = {"name": category}
    if used:
        data["services"] = used
    data["apps"] = out_apps
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    return {"root": root, "file": os.path.join(root, FILENAME), "text": text,
            "exists": os.path.exists(os.path.join(root, FILENAME))}


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
async def _body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="request body must be valid JSON") from None
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be a JSON object")
    return body


@router.get("/api/project")
async def get_project(path: str = Query(..., min_length=1, max_length=4096)) -> dict:
    try:
        return inspect(path)
    except ProjectError as exc:
        return {"found": True, "error": str(exc), "file": find(path)}


@router.post("/api/project/setup")
async def post_setup(request: Request) -> dict:
    body = await _body(request)
    try:
        return await setup(str(body.get("path") or ""), bool(body.get("start")))
    except ProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/project/export")
async def post_export(request: Request) -> dict:
    body = await _body(request)
    try:
        result = export(str(body.get("category") or "").strip())
    except ProjectError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if body.get("write"):
        if result["exists"] and not body.get("overwrite"):
            raise HTTPException(status_code=409, detail=f"{result['file']} already exists")
        try:
            with open(result["file"], "w", encoding="utf-8") as fh:
                fh.write(result["text"])
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"couldn't write the file: {exc}") from exc
        result["written"] = True
    return result
