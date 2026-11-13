"""backend/local_ai.py — optional offline assistant on a local model (Ollama).

The user installs Ollama (free) and downloads one open model (Qwen, Llama,
Gemma...). Nothing here runs in the background: a model answers only when
the UI posts a prompt, and Ollama unloads it from memory a few minutes later.

Small local models are guided by short written playbooks in ``skills/``: the
guides that match the crash-fixer's findings (and the question) are put in
front of the model, so it follows proven steps instead of guessing.

The model gets a small set of safe tools. Read-only tools (logs, diagnose,
files, ports) run directly. Every tool that changes something (predefined
fixes, port/command/env edits, start/stop) is shown to the user and runs only
after they approve it. There is no free-form shell access.

    GET  /api/local-ai/status              -> Ollama, models, catalog, RAM, disk
    POST /api/local-ai/start               -> start the Ollama server
    POST /api/local-ai/pull     {model}    -> starts a background download (progress in status)
    POST /api/local-ai/pull/cancel
    POST /api/local-ai/delete   {model}
    POST /api/local-ai/ask      {prompt, model, session_id?, mode, app_id?} -> SSE
    POST /api/local-ai/confirm  {id, approve}
    POST /api/local-ai/stop
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from typing import Any, Callable, Optional

import httpx
import psutil
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from . import app_settings, osutil, paths

router = APIRouter()

# Assigned by main.py.
get_states: Optional[Callable[[], list]] = None
asgi_app: Any = None  # the Homeport FastAPI app; tools call its API in-process

# Tests swap in an httpx.MockTransport for Ollama.
ollama_transport: Optional[httpx.AsyncBaseTransport] = None

SKILLS_DIR = os.path.join(paths.RESOURCE_ROOT, "skills")
DOWNLOAD_URL = "https://ollama.com/download"
MAX_TURNS = 10
CONTEXT_TOKENS = 8192
KEEP_ALIVE = "5m"  # Ollama frees the model's memory this long after the last answer
CONFIRM_TIMEOUT = 600.0

# Curated models. Sizes are Ollama's default (4-bit) downloads, approximate.
CATALOG = [
    {"id": "qwen3:4b", "name": "Qwen3 4B", "size_gb": 2.5, "ram_gb": 8, "tools": True,
     "note": "Fast, good all-rounder (recommended)"},
    {"id": "qwen2.5-coder:7b", "name": "Qwen2.5-Coder 7B", "size_gb": 4.7, "ram_gb": 16, "tools": True,
     "note": "Best at code and error logs"},
    {"id": "qwen3:8b", "name": "Qwen3 8B", "size_gb": 5.2, "ram_gb": 16, "tools": True,
     "note": "Stronger reasoning, slower"},
    {"id": "llama3.2:3b", "name": "Llama 3.2 3B", "size_gb": 2.0, "ram_gb": 8, "tools": True,
     "note": "Light and fast"},
    {"id": "qwen2.5-coder:1.5b", "name": "Qwen2.5-Coder 1.5B", "size_gb": 1.0, "ram_gb": 4, "tools": True,
     "note": "For computers with little memory"},
    {"id": "gemma3:4b", "name": "Gemma 3 4B", "size_gb": 3.3, "ram_gb": 8, "tools": False,
     "note": "Google's open model; gives advice, can't run fixes"},
]
_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9][\w.\-/]*(:[\w.\-]+)?$")


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------
def ollama_url() -> str:
    host = (os.environ.get("OLLAMA_HOST") or "").strip()
    if not host:
        return "http://127.0.0.1:11434"
    if "://" not in host:
        host = "http://" + host
    if host.startswith("http://0.0.0.0"):
        host = host.replace("0.0.0.0", "127.0.0.1", 1)
    if not re.search(r":\d+$", host.split("://", 1)[1].rstrip("/")):
        host = host.rstrip("/") + ":11434"
    return host.rstrip("/")


def _client(timeout: Any = 5.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=ollama_url(), timeout=timeout, transport=ollama_transport)


def _cli_candidates() -> list:
    if osutil.IS_WINDOWS:
        local = os.environ.get("LOCALAPPDATA", "")
        return [os.path.join(local, "Programs", "Ollama", "ollama.exe")]
    return ["/usr/local/bin/ollama", "/opt/homebrew/bin/ollama", "/usr/bin/ollama",
            "/Applications/Ollama.app/Contents/Resources/ollama",
            os.path.expanduser("~/Applications/Ollama.app/Contents/Resources/ollama")]


def find_cli() -> Optional[str]:
    found = shutil.which("ollama")
    if found:
        return found
    for candidate in _cli_candidates():
        if os.path.isfile(candidate):
            return candidate
    return None


def _mac_app() -> Optional[str]:
    for candidate in ("/Applications/Ollama.app", os.path.expanduser("~/Applications/Ollama.app")):
        if os.path.isdir(candidate):
            return candidate
    return None


async def _version() -> Optional[str]:
    try:
        async with _client(2.0) as c:
            r = await c.get("/api/version")
            if r.status_code == 200:
                return (r.json() or {}).get("version") or "unknown"
    except (httpx.HTTPError, ValueError):
        pass
    return None


async def _installed_models() -> list:
    try:
        async with _client(5.0) as c:
            r = await c.get("/api/tags")
            r.raise_for_status()
            data = r.json() or {}
    except (httpx.HTTPError, ValueError):
        return []
    out = []
    for m in data.get("models") or []:
        name = m.get("name") or m.get("model")
        if name:
            out.append({"name": name, "size": m.get("size") or 0,
                        "family": (m.get("details") or {}).get("family"),
                        "params": (m.get("details") or {}).get("parameter_size")})
    return out


def _same_model(a: str, b: str) -> bool:
    norm = lambda s: s if ":" in s else s + ":latest"  # noqa: E731
    return norm(a) == norm(b)


def recommended_model(ram_gb: float) -> str:
    return "qwen2.5-coder:1.5b" if ram_gb and ram_gb < 7 else "qwen3:4b"


def _disk_free_gb() -> Optional[float]:
    target = os.environ.get("OLLAMA_MODELS") or os.path.expanduser("~")
    with contextlib.suppress(OSError):
        return round(shutil.disk_usage(target).free / 1e9, 1)
    return None


@router.get("/api/local-ai/status")
async def status() -> dict:
    version = await _version()
    models = await _installed_models() if version else []
    ram_gb = round(psutil.virtual_memory().total / 2**30, 1)  # GiB: "8 GB" Macs report 8.0
    catalog = [dict(c, installed=any(_same_model(c["id"], m["name"]) for m in models)) for c in CATALOG]
    prefs = app_settings.load()
    return {
        "installed": bool(find_cli() or _mac_app() or version),
        "running": bool(version),
        "version": version,
        "url": ollama_url(),
        "models": models,
        "models_size_gb": round(sum(m.get("size") or 0 for m in models) / 1e9, 1),
        "catalog": catalog,
        "recommended": recommended_model(ram_gb),
        "selected": prefs.get("local_model"),
        "ram_gb": ram_gb,
        "disk_free_gb": _disk_free_gb(),
        "download_url": DOWNLOAD_URL,
        "busy": _run is not None,
        "pull": dict(_pull) if _pull else None,
        "skills": [{"id": k, "title": v["title"]} for k, v in load_skills().items()],
    }


@router.post("/api/local-ai/start")
async def start_server() -> dict:
    """Start Ollama if it's installed but not running (it keeps running after)."""
    if await _version():
        return {"running": True}
    app_bundle = _mac_app() if not osutil.IS_WINDOWS else None
    cli = find_cli()
    if not (app_bundle or cli):
        raise HTTPException(status_code=404, detail="Ollama isn't installed — download it from " + DOWNLOAD_URL)
    try:
        if app_bundle:
            subprocess.Popen(["open", "-g", "-a", app_bundle], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen([cli, "serve"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, **osutil.popen_group_kwargs())
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"couldn't start Ollama: {exc}") from exc
    for _ in range(40):
        await asyncio.sleep(0.5)
        if await _version():
            return {"running": True}
    raise HTTPException(status_code=504, detail="Ollama didn't start within 20 seconds")


def _sse(payload: dict) -> str:
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


def _check_model_name(name: str) -> str:
    name = (name or "").strip()
    if not name or len(name) > 120 or not _MODEL_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="invalid model name")
    return name


# The one model download in progress (or the last one's result), shared by
# every window. It runs on the server, so closing the page doesn't stop it.
_pull: Optional[dict] = None
_pull_task: Optional[asyncio.Task] = None


async def _pull_worker(model: str) -> None:
    state = _pull
    assert state is not None
    try:
        async with _client(httpx.Timeout(10.0, read=600.0)) as c:
            async with c.stream("POST", "/api/pull", json={"model": model, "name": model, "stream": True}) as r:
                if r.status_code != 200:
                    text = (await r.aread()).decode("utf-8", "replace")
                    state["error"] = _ollama_error(text) or f"HTTP {r.status_code}"
                    return
                async for line in r.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        evt = json.loads(line)
                    except ValueError:
                        continue
                    if evt.get("error"):
                        state["error"] = str(evt["error"])
                        return
                    state["status"] = evt.get("status") or state["status"]
                    if evt.get("total"):
                        state["total"] = evt["total"]
                        state["completed"] = evt.get("completed") or 0
                    if evt.get("status") == "success":
                        state["done"] = True
                        if not app_settings.load().get("local_model"):
                            app_settings.update({"local_model": model})
                        return
        state["error"] = "the download ended unexpectedly"
    except asyncio.CancelledError:
        state["error"] = "cancelled"
        state["cancelled"] = True
    except httpx.HTTPError as exc:
        state["error"] = f"download failed: {exc}"
    finally:
        state["active"] = False
        state["finished_at"] = time.time()


@router.post("/api/local-ai/pull")
async def pull(request: Request) -> dict:
    """Start downloading a model in the background; progress is in /status."""
    global _pull, _pull_task
    body = await _body(request)
    model = _check_model_name(str(body.get("model") or ""))
    if _pull and _pull.get("active"):
        raise HTTPException(status_code=409, detail=f"already downloading {_pull['model']}")
    if not await _version():
        raise HTTPException(status_code=503, detail="Ollama isn't running")
    _pull = {"model": model, "status": "starting", "completed": 0, "total": 0, "active": True,
             "done": False, "error": None, "started_at": time.time()}
    _pull_task = asyncio.create_task(_pull_worker(model))
    return {"started": model}


@router.post("/api/local-ai/pull/cancel")
async def cancel_pull() -> dict:
    task = _pull_task
    if not (_pull and _pull.get("active")) or task is None or task.done():
        return {"cancelled": False}
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await task
    return {"cancelled": True}


@router.post("/api/local-ai/delete")
async def delete_model(request: Request) -> dict:
    body = await _body(request)
    model = _check_model_name(str(body.get("model") or ""))
    try:
        async with _client(30.0) as c:
            r = await c.request("DELETE", "/api/delete", json={"model": model, "name": model})
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Ollama isn't reachable: {exc}") from exc
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code if r.status_code < 500 else 502,
                            detail=_ollama_error(r.text) or "delete failed")
    prefs = app_settings.load()
    if prefs.get("local_model") and _same_model(prefs["local_model"], model):
        app_settings.update({"local_model": None})
    return {"deleted": model}


def _ollama_error(text: str) -> str:
    with contextlib.suppress(ValueError, AttributeError):
        return str(json.loads(text).get("error") or "")
    return (text or "").strip()[:300]


async def _body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="request body must be valid JSON") from None
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be a JSON object")
    return body


# ---------------------------------------------------------------------------
# skills
# ---------------------------------------------------------------------------
def load_skills(directory: Optional[str] = None) -> dict:
    """{id: {title, findings[], keywords[], body}} from skills/*.md."""
    directory = directory or SKILLS_DIR
    out: dict = {}
    with contextlib.suppress(OSError):
        for fname in sorted(os.listdir(directory)):
            if not fname.endswith(".md") or fname.lower() == "readme.md":
                continue
            with contextlib.suppress(OSError, UnicodeDecodeError):
                with open(os.path.join(directory, fname), encoding="utf-8") as fh:
                    text = fh.read()
                meta: dict = {}
                body = text
                m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
                if m:
                    body = m.group(2)
                    for line in m.group(1).splitlines():
                        if ":" in line:
                            k, v = line.split(":", 1)
                            meta[k.strip().lower()] = v.strip()
                split = lambda v: [x.strip() for x in (v or "").split(",") if x.strip()]  # noqa: E731
                sid = fname[:-3]
                out[sid] = {"id": sid, "title": meta.get("title") or sid,
                            "findings": split(meta.get("findings")),
                            "keywords": split(meta.get("keywords")), "body": body.strip()}
    return out


def pick_skills(skills: dict, finding_ids: list, text: str, limit: int = 2) -> list:
    """Guides for the findings first, then by keyword hits in ``text``."""
    chosen: list = []
    for fid in finding_ids:
        for s in skills.values():
            if fid in s["findings"] and s["id"] not in chosen:
                chosen.append(s["id"])
    low = (text or "").lower()
    scored = []
    for s in skills.values():
        if s["id"] in chosen:
            continue
        hits = sum(1 for k in s["keywords"] if len(k) > 2 and k.lower() in low)
        if hits:
            scored.append((hits, s["id"]))
    for _, sid in sorted(scored, key=lambda t: -t[0]):
        chosen.append(sid)
    return chosen[:limit]


# ---------------------------------------------------------------------------
# the Homeport API, called in-process for tools
# ---------------------------------------------------------------------------
async def _api(method: str, path: str, **kw) -> tuple:
    if asgi_app is None:
        return 503, {"detail": "Homeport API not available"}
    transport = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1", timeout=1200.0) as c:
        r = await c.request(method, path, **kw)
    try:
        data = r.json()
    except ValueError:
        data = {"detail": r.text[:500]}
    return r.status_code, data


def _err(data: Any) -> str:
    if isinstance(data, dict) and data.get("detail"):
        return str(data["detail"])
    return "request failed"


async def _app_cfg(app_id: str) -> dict:
    code, data = await _api("GET", f"/api/apps/{app_id}")
    if code != 200:
        raise ToolError(f"no app with id {app_id!r}. Call list_apps for valid ids.")
    return data


class ToolError(Exception):
    pass


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + f"\n… (cut, {len(text) - limit} more characters)"


def _apps_lines(states: list) -> str:
    rows = []
    for s in states:
        bits = [s.get("status") or "?"]
        port = s.get("port") or s.get("detected_port")
        if port:
            bits.append(f"port {port}")
        if s.get("port_conflict"):
            bits.append("PORT CONFLICT")
        if s.get("last_error"):
            bits.append("error: " + str(s["last_error"])[:120])
        rows.append(f'- {s.get("id")} "{s.get("name")}": {", ".join(bits)}; '
                    f'path {s.get("path")}; command `{s.get("command") or "(auto)"}`')
    return "\n".join(rows) or "(no apps yet)"


_SKIP_DIRS = {"node_modules", ".git", "vendor", ".venv", "venv", "__pycache__", "dist", "build", ".next",
              "target", ".nuxt", ".cache"}
FIX_ACTIONS = ("install_node", "install_python", "install_composer", "copy_env", "laravel_key", "install_bundle")
_EDITABLE = ("port", "command", "env")


def _inside(root: str, rel: str) -> str:
    root = os.path.realpath(root)
    target = os.path.realpath(os.path.join(root, rel or "."))
    if os.path.commonpath([root, target]) != root:
        raise ToolError("that path is outside the app's folder")
    return target


async def tool_list_apps(**_) -> str:
    return _apps_lines(get_states() if get_states else [])


async def tool_get_logs(app_id: str, lines: int = 80, **_) -> str:
    n = max(10, min(int(lines or 80), 200))
    code, data = await _api("GET", f"/api/apps/{app_id}/logs", params={"tail": n})
    if code != 200:
        raise ToolError(_err(data))
    return _clip("\n".join(data.get("lines") or []) or "(log is empty)", 9000)


async def tool_diagnose(app_id: str, **_) -> str:
    code, data = await _api("GET", f"/api/apps/{app_id}/diagnose")
    if code != 200:
        raise ToolError(_err(data))
    findings = data.get("findings") or []
    parts = []
    for f in findings:
        fixes = ", ".join(x["action"] for x in f.get("fixes") or []) or "none"
        parts.append(f"* [{f.get('id')}] {f.get('title')}: {f.get('detail')}\n  evidence: {f.get('evidence') or '-'}\n"
                     f"  suggested fixes: {fixes}")
    skills = load_skills()
    guide_ids = pick_skills(skills, [f.get("id") for f in findings], "\n".join(data.get("log_tail") or []))
    for sid in guide_ids:
        parts.append(f"\nGuide '{sid}' ({skills[sid]['title']}):\n{skills[sid]['body']}")
    return "\n".join(parts) or "No findings."


async def tool_check_port(port: int, **_) -> str:
    port = int(port)
    pids = await asyncio.to_thread(osutil.listening_pids, port)
    if not pids:
        return f"Nothing is listening on port {port}."
    rows = []
    for pid in pids[:5]:
        try:
            p = psutil.Process(pid)
            cmd = " ".join(p.cmdline())[:200]
            cwd = ""
            with contextlib.suppress(psutil.Error):
                cwd = p.cwd()
            rows.append(f"PID {pid}: {p.name()} — `{cmd}`" + (f" (folder {cwd})" if cwd else ""))
        except psutil.Error:
            rows.append(f"PID {pid}")
    owners = [s for s in (get_states() if get_states else [])
              if port in (s.get("port"), s.get("detected_port")) and s.get("status") in ("running", "starting", "unhealthy")]
    if owners:
        rows.append("Homeport apps on this port: " + ", ".join(f'{s["id"]} ("{s["name"]}")' for s in owners))
    return "\n".join(rows)


async def tool_list_files(app_id: str, folder: str = ".", **_) -> str:
    cfg = await _app_cfg(app_id)
    target = _inside(cfg.get("path") or "", folder)
    if not os.path.isdir(target):
        raise ToolError("not a folder")
    entries = []
    for name in sorted(os.listdir(target))[:150]:
        full = os.path.join(target, name)
        if os.path.isdir(full):
            entries.append(name + "/" + (" (skipped contents)" if name in _SKIP_DIRS else ""))
        else:
            with contextlib.suppress(OSError):
                entries.append(f"{name} ({os.path.getsize(full)} bytes)")
    return "\n".join(entries) or "(empty folder)"


async def tool_read_file(app_id: str, file: str, **_) -> str:
    cfg = await _app_cfg(app_id)
    target = _inside(cfg.get("path") or "", file)
    if not os.path.isfile(target):
        raise ToolError(f"file not found: {file}")
    with open(target, "rb") as fh:
        raw = fh.read(60000)
    if b"\0" in raw[:4000]:
        raise ToolError("that's a binary file")
    return _clip(raw.decode("utf-8", "replace"), 12000)


async def tool_read_skill(skill: str, **_) -> str:
    skills = load_skills()
    s = skills.get(str(skill).strip().removesuffix(".md"))
    if not s:
        raise ToolError("unknown guide. Available: " + ", ".join(skills))
    return f"{s['title']}\n{s['body']}"


async def tool_run_fix(app_id: str, action: str, **_) -> str:
    if action not in FIX_ACTIONS:
        raise ToolError("action must be one of: " + ", ".join(FIX_ACTIONS))
    code, data = await _api("POST", f"/api/apps/{app_id}/fix", json={"action": action})
    if code != 200:
        raise ToolError(_err(data))
    return ("OK. " if data.get("ok") else "The fix reported a problem. ") + _clip(str(data.get("output") or ""), 3000)


async def tool_update_app(app_id: str, port: Any = None, command: Any = None, env: Any = None, **_) -> str:
    patch: dict = {}
    if port not in (None, ""):
        patch["port"] = int(port)
    if command not in (None, ""):
        patch["command"] = str(command)
    if isinstance(env, dict) and env:
        cfg = await _app_cfg(app_id)
        patch["env"] = {**(cfg.get("env") or {}), **{str(k): str(v) for k, v in env.items()}}
    if not patch:
        raise ToolError("nothing to change: give port, command or env")
    code, data = await _api("PATCH", f"/api/apps/{app_id}", json=patch)
    if code != 200:
        raise ToolError(_err(data))
    return "Saved: " + json.dumps(patch)


async def _lifecycle(app_id: str, action: str, query: str = "") -> str:
    code, data = await _api("POST", f"/api/apps/{app_id}/{action}{query}")
    if code != 200:
        raise ToolError(_err(data))
    return f"{action} done; status now: {data.get('status') or 'unknown'}"


async def tool_start_app(app_id: str, stop_port_blocker: bool = False, **_) -> str:
    return await _lifecycle(app_id, "start", "?kill_conflict=1" if stop_port_blocker else "")


async def tool_stop_app(app_id: str, **_) -> str:
    return await _lifecycle(app_id, "stop")


async def tool_restart_app(app_id: str, **_) -> str:
    return await _lifecycle(app_id, "restart")


def _fn(name: str, desc: str, props: dict, required: list) -> dict:
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required}}}


_APP = {"app_id": {"type": "string", "description": "the app's id from list_apps"}}
READ_TOOLS = {
    "list_apps": (tool_list_apps, _fn("list_apps", "List all apps with id, status, port, folder and command.", {}, [])),
    "diagnose": (tool_diagnose, _fn("diagnose", "Explain why an app crashed: known causes, suggested fixes and the matching guide.", _APP, ["app_id"])),
    "get_logs": (tool_get_logs, _fn("get_logs", "Read the last lines of an app's log.",
                                    {**_APP, "lines": {"type": "integer", "description": "10-200, default 80"}}, ["app_id"])),
    "check_port": (tool_check_port, _fn("check_port", "Show which program is listening on a TCP port.",
                                        {"port": {"type": "integer"}}, ["port"])),
    "list_files": (tool_list_files, _fn("list_files", "List files in the app's folder (or a subfolder of it).",
                                        {**_APP, "folder": {"type": "string", "description": "relative path, default ."}}, ["app_id"])),
    "read_file": (tool_read_file, _fn("read_file", "Read a text file inside the app's folder.",
                                      {**_APP, "file": {"type": "string", "description": "relative path, e.g. package.json"}}, ["app_id", "file"])),
    "read_skill": (tool_read_skill, _fn("read_skill", "Open a step-by-step troubleshooting guide by its id.",
                                        {"skill": {"type": "string"}}, ["skill"])),
}
ACT_TOOLS = {
    "run_fix": (tool_run_fix, _fn("run_fix", "Run a predefined fix in the app's folder (asks the user first).",
                                  {**_APP, "action": {"type": "string", "enum": list(FIX_ACTIONS)}}, ["app_id", "action"])),
    "update_app": (tool_update_app, _fn("update_app", "Change an app's port, start command or environment variables (asks the user first).",
                                        {**_APP, "port": {"type": "integer"}, "command": {"type": "string"},
                                         "env": {"type": "object", "description": "variables to set, e.g. {\"PORT\": \"3001\"}"}},
                                        ["app_id"])),
    "start_app": (tool_start_app, _fn("start_app", "Start an app (asks the user first). stop_port_blocker=true first stops a program that holds its port.",
                                      {**_APP, "stop_port_blocker": {"type": "boolean"}}, ["app_id"])),
    "stop_app": (tool_stop_app, _fn("stop_app", "Stop an app (asks the user first).", _APP, ["app_id"])),
    "restart_app": (tool_restart_app, _fn("restart_app", "Restart an app (asks the user first).", _APP, ["app_id"])),
}


def describe_action(name: str, args: dict, names: dict) -> str:
    app = names.get(args.get("app_id"), args.get("app_id") or "?")
    if name == "run_fix":
        from .diagnose import FIX_LABELS
        return f"{FIX_LABELS.get(args.get('action'), args.get('action'))} in “{app}”"
    if name == "update_app":
        bits = []
        if args.get("port") not in (None, ""):
            bits.append(f"port → {args['port']}")
        if args.get("command"):
            bits.append(f"command → {args['command']}")
        if isinstance(args.get("env"), dict) and args["env"]:
            bits.append("env → " + ", ".join(f"{k}={v}" for k, v in args["env"].items()))
        return f"Change “{app}”: " + ("; ".join(bits) or "(nothing)")
    if name == "start_app":
        return f"Start “{app}”" + (" and stop the program blocking its port" if args.get("stop_port_blocker") else "")
    return {"stop_app": "Stop", "restart_app": "Restart"}.get(name, name) + f" “{app}”"


# ---------------------------------------------------------------------------
# prompt
# ---------------------------------------------------------------------------
def system_prompt(states: list, mode: str, skills: dict, guide_ids: list, focus: str = "",
                  tools: bool = True) -> str:
    lines = [
        "You are the offline helper inside Homeport, an app that starts and watches the user's local",
        "development apps (web servers, APIs, databases). Your job: find why an app fails and fix it safely.",
        "",
        "Rules:",
    ]
    if tools:
        lines += [
            "- Look before you answer. For a crashed app call diagnose first, then get_logs if needed.",
            "- Follow the matching guide step by step. Open other guides with read_skill.",
            "- Never invent app ids, ports or file names: get them from tools.",
            "- Change things only with the action tools. The user approves every change; if they decline, accept it.",
        ]
        if mode == "ask":
            lines.append("- READ-ONLY MODE: only look and explain. Describe changes; the user can switch to Act mode.")
    else:
        lines += [
            "- You cannot run tools. Use the information below and give the user clear steps to do themselves.",
        ]
    lines += [
        "- Be brief: short plain sentences. Say what you found, what you changed and what to do next.",
        "",
        "Apps:",
        _apps_lines(states),
        "",
        "Guides (open with read_skill): " + ", ".join(f"{s['id']} ({s['title']})" for s in skills.values()),
    ]
    if focus:
        lines += ["", focus]
    for sid in guide_ids:
        if sid in skills:
            lines += ["", f"Guide '{sid}' — {skills[sid]['title']}:", skills[sid]["body"]]
    return "\n".join(lines)


async def _focus_context(app_id: str) -> tuple:
    """(text, finding ids, log text) about one app, gathered up front for the model."""
    code, data = await _api("GET", f"/api/apps/{app_id}/diagnose")
    if code != 200:
        return "", [], ""
    findings = data.get("findings") or []
    log = "\n".join(data.get("log_tail") or [])
    rows = [f"The user is asking about app {app_id}. Homeport's crash check found:"]
    for f in findings:
        fixes = ", ".join(x["action"] for x in f.get("fixes") or []) or "none"
        rows.append(f"* [{f.get('id')}] {f.get('title')}: {f.get('detail')} (suggested fixes: {fixes})")
    rows += ["Last log lines:", _clip(log, 4000) or "(empty)"]
    return "\n".join(rows), [f.get("id") for f in findings], log


# ---------------------------------------------------------------------------
# the chat run
# ---------------------------------------------------------------------------
class _Run:
    def __init__(self) -> None:
        self.stop = False
        self.confirms: dict = {}
        self.response: Optional[httpx.Response] = None


_run: Optional[_Run] = None
_sessions: dict = {}  # session id -> {"messages": [...], "ts": float}
_no_tools_models: set = set()


class _ThinkFilter:
    """Hide <think>…</think> blocks some models print inline."""

    def __init__(self) -> None:
        self.inside = False
        self.buf = ""

    def feed(self, text: str) -> str:
        self.buf += text
        out = ""
        while self.buf:
            tag = "</think>" if self.inside else "<think>"
            i = self.buf.find(tag)
            if i < 0:
                keep = 0
                for n in range(min(len(tag) - 1, len(self.buf)), 0, -1):
                    if tag.startswith(self.buf[-n:]):
                        keep = n
                        break
                if not self.inside:
                    out += self.buf[:len(self.buf) - keep]
                self.buf = self.buf[len(self.buf) - keep:]
                break
            if not self.inside:
                out += self.buf[:i]
            self.buf = self.buf[i + len(tag):]
            self.inside = not self.inside
        return out


def _args(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    with contextlib.suppress(ValueError, TypeError):
        val = json.loads(raw)
        if isinstance(val, dict):
            return val
    return {}


async def _chat_turn(run: _Run, model: str, messages: list, tools: Optional[list], emit) -> dict:
    """One streamed /api/chat call. Returns {content, tool_calls, stats}."""
    payload: dict = {"model": model, "messages": messages, "stream": True, "keep_alive": KEEP_ALIVE,
                     "options": {"num_ctx": CONTEXT_TOKENS, "temperature": 0.2}}
    if tools:
        payload["tools"] = tools
    if model.startswith("qwen3"):
        payload["think"] = False  # faster answers; thinking is slow on small machines
    content, calls, stats = "", [], {}
    filt = _ThinkFilter()
    async with _client(httpx.Timeout(10.0, read=300.0)) as c:
        async with c.stream("POST", "/api/chat", json=payload) as r:
            run.response = r
            if r.status_code != 200:
                text = (await r.aread()).decode("utf-8", "replace")
                raise _OllamaError(_ollama_error(text) or f"Ollama answered HTTP {r.status_code}", r.status_code)
            async for line in r.aiter_lines():
                if run.stop:
                    break
                if not line.strip():
                    continue
                try:
                    evt = json.loads(line)
                except ValueError:
                    continue
                if evt.get("error"):
                    raise _OllamaError(str(evt["error"]), 500)
                msg = evt.get("message") or {}
                piece = msg.get("content") or ""
                if piece:
                    shown = filt.feed(piece)
                    content += piece
                    if shown:
                        await emit({"type": "delta", "text": shown})
                for call in msg.get("tool_calls") or []:
                    fn = call.get("function") or {}
                    if fn.get("name"):
                        calls.append({"name": fn["name"], "arguments": _args(fn.get("arguments"))})
                if evt.get("done"):
                    stats = {"eval_count": evt.get("eval_count"), "eval_duration": evt.get("eval_duration")}
    run.response = None
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.S).strip()
    return {"content": content, "tool_calls": calls, "stats": stats}


class _OllamaError(Exception):
    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


async def _confirm(run: _Run, emit, name: str, summary: str) -> bool:
    cid = uuid.uuid4().hex[:12]
    fut: asyncio.Future = asyncio.get_running_loop().create_future()
    run.confirms[cid] = fut
    await emit({"type": "confirm", "id": cid, "name": name, "summary": summary})
    try:
        return bool(await asyncio.wait_for(fut, CONFIRM_TIMEOUT))
    except asyncio.TimeoutError:
        return False
    finally:
        run.confirms.pop(cid, None)


async def _agent(run: _Run, emit, *, model: str, prompt: str, mode: str, session_id: str, app_id: str) -> None:
    started = time.monotonic()
    states = get_states() if get_states else []
    skills = load_skills()
    focus, finding_ids, log = ("", [], "")
    if app_id:
        focus, finding_ids, log = await _focus_context(app_id)
    guide_ids = pick_skills(skills, finding_ids, prompt + "\n" + log)
    use_tools = model not in _no_tools_models and not any(
        c["id"] == model and not c["tools"] for c in CATALOG)

    session = _sessions.get(session_id) or {"messages": []}
    history = [m for m in session["messages"] if m.get("role") != "system"]
    messages = [{"role": "system", "content": system_prompt(states, mode, skills, guide_ids, focus, use_tools)}]
    messages += history[-24:]
    messages.append({"role": "user", "content": prompt})

    names = {s.get("id"): s.get("name") for s in states}
    tool_map = dict(READ_TOOLS)
    if mode == "act":
        tool_map.update(ACT_TOOLS)
    specs = [spec for _, spec in tool_map.values()]

    await emit({"type": "session", "session_id": session_id, "model": model})
    await emit({"type": "status", "text": "Thinking"})
    turns, stats = 0, {}
    try:
        while turns < MAX_TURNS and not run.stop:
            turns += 1
            try:
                res = await _chat_turn(run, model, messages, specs if use_tools else None, emit)
            except _OllamaError as exc:
                if use_tools and exc.status == 400 and "tool" in str(exc).lower():
                    _no_tools_models.add(model)
                    use_tools = False
                    messages[0]["content"] = system_prompt(states, mode, skills, guide_ids, focus, False)
                    turns -= 1
                    continue
                raise
            stats = res["stats"] or stats
            assistant = {"role": "assistant", "content": res["content"]}
            if res["tool_calls"]:
                assistant["tool_calls"] = [{"function": c} for c in res["tool_calls"]]
            messages.append(assistant)
            if not res["tool_calls"] or run.stop:
                break
            for call in res["tool_calls"]:
                if run.stop:
                    break
                name, args = call["name"], call["arguments"]
                tid = uuid.uuid4().hex[:10]
                entry = tool_map.get(name)
                summary = ", ".join(f"{k}={v}" for k, v in args.items())[:200]
                await emit({"type": "tool", "id": tid, "name": name, "summary": summary})
                if entry is None:
                    result, failed = f"Unknown tool {name}. Use only the listed tools.", True
                else:
                    approved = True
                    if name in ACT_TOOLS:
                        approved = await _confirm(run, emit, name, describe_action(name, args, names))
                    if not approved:
                        result, failed = "The user declined this change. Do not retry it; suggest another way or stop.", True
                    else:
                        try:
                            result, failed = await entry[0](**args), False
                        except ToolError as exc:
                            result, failed = f"Error: {exc}", True
                        except (TypeError, ValueError) as exc:
                            result, failed = f"Error: bad arguments ({exc})", True
                        except Exception as exc:  # a tool must never kill the chat
                            result, failed = f"Error: {exc}", True
                await emit({"type": "tool_result", "id": tid, "error": failed})
                messages.append({"role": "tool", "content": result, "tool_name": name})
            await emit({"type": "status", "text": "Thinking"})
        _sessions[session_id] = {"messages": messages[1:], "ts": time.time()}
        for sid in sorted(_sessions, key=lambda k: _sessions[k]["ts"])[:-10]:
            _sessions.pop(sid, None)
        tps = None
        if stats.get("eval_count") and stats.get("eval_duration"):
            tps = round(stats["eval_count"] / (stats["eval_duration"] / 1e9), 1)
        await emit({"type": "done", "session_id": session_id, "turns": turns,
                    "duration_ms": int((time.monotonic() - started) * 1000), "tokens_per_s": tps,
                    "stopped": run.stop})
    except _OllamaError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            msg = f"The model “{model}” isn't downloaded. Open Models to download it."
        await emit({"type": "error", "message": msg})
    except httpx.HTTPError as exc:
        await emit({"type": "error", "message": "stopped" if run.stop else f"Ollama isn't reachable ({exc}). Is it running?"})


@router.post("/api/local-ai/ask")
async def ask(request: Request) -> StreamingResponse:
    global _run
    body = await _body(request)
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    model = _check_model_name(str(body.get("model") or ""))
    mode = "ask" if body.get("mode") == "ask" else "act"
    session_id = str(body.get("session_id") or "").strip() or uuid.uuid4().hex
    app_id = str(body.get("app_id") or "").strip()
    if _run is not None:
        raise HTTPException(status_code=409, detail="the assistant is already working on something")
    if not await _version():
        raise HTTPException(status_code=503, detail="Ollama isn't running — open Models to start it")

    run = _Run()
    _run = run
    queue: asyncio.Queue = asyncio.Queue()

    async def emit(evt: dict) -> None:
        await queue.put(evt)

    async def worker() -> None:
        try:
            await _agent(run, emit, model=model, prompt=prompt, mode=mode, session_id=session_id, app_id=app_id)
        except Exception as exc:  # noqa: BLE001 - always end the stream with a message
            await emit({"type": "error", "message": f"assistant failed: {exc}"})
        finally:
            await queue.put(None)

    task = asyncio.create_task(worker())

    async def stream():
        global _run
        try:
            while True:
                evt = await queue.get()
                if evt is None:
                    break
                yield _sse(evt)
        finally:
            run.stop = True
            for fut in list(run.confirms.values()):
                if not fut.done():
                    fut.set_result(False)
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
            if _run is run:
                _run = None

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/api/local-ai/confirm")
async def confirm(request: Request) -> dict:
    body = await _body(request)
    run = _run
    fut = run.confirms.get(str(body.get("id") or "")) if run else None
    if fut is None or fut.done():
        raise HTTPException(status_code=404, detail="nothing is waiting for that answer")
    fut.set_result(bool(body.get("approve")))
    return {"ok": True}


@router.post("/api/local-ai/stop")
async def stop() -> dict:
    run = _run
    if run is None:
        return {"stopped": False}
    run.stop = True
    for fut in list(run.confirms.values()):
        if not fut.done():
            fut.set_result(False)
    if run.response is not None:
        with contextlib.suppress(Exception):
            await run.response.aclose()
    return {"stopped": True}
