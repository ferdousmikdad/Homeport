"""backend/ai_routes.py — on-demand AI assistant backed by the local `claude` CLI.

Runs Claude Code headless (`claude -p`) with the user's logged-in Claude
account. Nothing runs in the background: a run starts only when the UI posts a
prompt, and stops when it finishes, is cancelled, or the client disconnects.

    GET  /api/ai/status  -> {available, cli, version, busy}
    POST /api/ai/ask     body {prompt, model?, session_id?, mode: "act"|"ask"}
                         -> SSE stream of simplified events (see _translate)
    POST /api/ai/stop    -> {stopped: bool}
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import signal
import subprocess
from typing import Any, Callable

import psutil
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from . import osutil

router = APIRouter()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Assigned by main.py: returns the current list[AppState].
get_states: Callable[[], list[dict]] | None = None

_EXTRA_PATHS = [
    "/opt/homebrew/bin",
    "/usr/local/bin",
    os.path.expanduser("~/.local/bin"),
    os.path.expanduser("~/.claude/local"),
] if not osutil.IS_WINDOWS else [
    os.path.join(os.environ.get("APPDATA", ""), "npm"),
    os.path.expanduser("~/.local/bin"),
    os.path.expanduser("~/.claude/local"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "claude"),
]
# Tools allowed in read-only "ask" mode; anything else is auto-denied by `claude -p`.
_ASK_TOOLS = ["Read", "Grep", "Glob", "Bash(curl:*)", "Bash(lsof:*)", "Bash(ps:*)", "Bash(cat:*)", "Bash(ls:*)"]

_proc: asyncio.subprocess.Process | None = None
_version: str | None = None


def find_cli() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    names = ("claude.exe", "claude.cmd", "claude") if osutil.IS_WINDOWS else ("claude",)
    for directory in _EXTRA_PATHS:
        for name in names:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate) and (osutil.IS_WINDOWS or os.access(candidate, os.X_OK)):
                return candidate
    return None


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    # The manager may itself have been launched from a Claude Code session or launchd.
    for key in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT", "ANTHROPIC_API_KEY"):
        env.pop(key, None)
    parts = env.get("PATH", "").split(os.pathsep)
    env["PATH"] = os.pathsep.join(parts + [p for p in _EXTRA_PATHS if p not in parts])
    return env


def _apps_summary(states: list[dict]) -> str:
    rows = []
    for s in states:
        rows.append({
            k: s.get(k)
            for k in ("id", "name", "status", "path", "command", "port", "detected_port",
                      "health_url", "healthy", "port_conflict", "last_error", "category")
            if s.get(k) not in (None, "", False)
        })
    by_port: dict[int, list[str]] = {}
    for s in states:
        port = s.get("port") or s.get("detected_port")
        if port:
            by_port.setdefault(int(port), []).append(s["id"])
    dupes = {p: ids for p, ids in by_port.items() if len(ids) > 1}
    text = json.dumps(rows, ensure_ascii=False, indent=1, default=str)
    if dupes:
        text += "\nApps sharing a port: " + json.dumps(dupes)
    return text


def system_prompt(base_url: str, states: list[dict], mode: str) -> str:
    lines = [
        "You are the built-in assistant of Homeport, a local dashboard that starts, stops and",
        f"monitors the user's localhost apps. The manager's API is running at {base_url} and its source",
        f"code is in {PROJECT_ROOT} (backend/ = FastAPI, ui/ = static index.html, app.js, style.css; SPEC.md documents everything).",
        "",
        "Manage apps ONLY through the HTTP API with curl (never edit data/apps.json by hand):",
        "  GET /api/apps | POST /api/apps {name,path,command?,port?,health_url?,category?,auto_restart?,autostart?,env?}",
        "  PATCH /api/apps/{id} {partial config} | DELETE /api/apps/{id}",
        "  POST /api/apps/{id}/start|stop|restart (start?kill_conflict=1 kills a foreign process on its port)",
        "  GET /api/apps/{id}/logs?tail=200 | GET /api/detect?path=...",
        "Health: an app is 'unhealthy' when its health_url returns >=500 or is unreachable; 'starting' means",
        "its port is not open yet. Check logs, the configured port vs detected_port, and `lsof -nP -iTCP:PORT -sTCP:LISTEN`.",
        "When fixing a port, prefer changing the app's config via PATCH (port, env PORT, command flags) and only",
        "edit an app's own source when that is the only way. Two apps must never share a port.",
        "UI/design changes: edit files in ui/ (the user reloads the page to see them). Keep the existing",
        "CSS tokens and light/dark theme working.",
        "Never stop, restart or kill the Homeport server itself (port "
        + base_url.rsplit(":", 1)[-1].rstrip("/") + "); if you change backend/*.py tell the user to restart the manager.",
        "Be concise: the reply is shown in a small chat panel. Say what you changed.",
    ]
    if mode == "ask":
        lines += ["", "READ-ONLY MODE: answer and diagnose, but do not change anything (only GET requests,",
                  "no file edits). If a change is needed, describe it and tell the user to switch to Act mode."]
    lines += ["", "Current apps snapshot:", _apps_summary(states)]
    return "\n".join(lines)


def build_command(cli: str, *, model: str | None, session_id: str | None, mode: str, sys_prompt: str) -> list[str]:
    cmd = [cli, "-p", "--output-format", "stream-json", "--verbose",
           "--append-system-prompt", sys_prompt]
    if model:
        cmd += ["--model", model]
    if session_id:
        cmd += ["--resume", session_id]
    if mode == "act":
        cmd += ["--dangerously-skip-permissions"]
    else:
        cmd += ["--allowedTools", *_ASK_TOOLS]
    return cmd


def _tool_summary(name: str, inp: dict) -> str:
    if not isinstance(inp, dict):
        return ""
    for key in ("command", "file_path", "pattern", "path", "url", "description"):
        if inp.get(key):
            return str(inp[key])[:300]
    return ""


def _translate(event: dict) -> list[dict]:
    """Map one `claude` stream-json event onto the UI's small event vocabulary:
    session, text, tool, tool_result, done, error."""
    kind = event.get("type")
    out: list[dict] = []
    if kind == "system" and event.get("subtype") == "init":
        out.append({"type": "session", "session_id": event.get("session_id"), "model": event.get("model")})
    elif kind == "assistant":
        for block in (event.get("message") or {}).get("content") or []:
            btype = block.get("type")
            if btype == "text" and block.get("text"):
                out.append({"type": "text", "text": block["text"]})
            elif btype == "tool_use":
                name = block.get("name") or "tool"
                out.append({"type": "tool", "id": block.get("id"), "name": name,
                            "summary": _tool_summary(name, block.get("input") or {})})
    elif kind == "user":
        for block in (event.get("message") or {}).get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                out.append({"type": "tool_result", "id": block.get("tool_use_id"),
                            "error": bool(block.get("is_error"))})
    elif kind == "result":
        out.append({
            "type": "error" if event.get("is_error") else "done",
            "message": event.get("result") if event.get("is_error") else None,
            "session_id": event.get("session_id"),
            "cost_usd": event.get("total_cost_usd"),
            "duration_ms": event.get("duration_ms"),
            "turns": event.get("num_turns"),
        })
    return out


def _sse(payload: dict) -> str:
    return "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"


_stop_requested = False


async def _kill(proc: asyncio.subprocess.Process) -> None:
    """Stop the assistant process and anything it started (any OS)."""
    if proc.returncode is not None:
        return
    tree = []
    with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
        root = psutil.Process(proc.pid)
        tree = [root] + root.children(recursive=True)
    if osutil.IS_WINDOWS:
        for p in tree:
            with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                p.terminate()
    else:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(proc.pid, signal.SIGTERM)
    try:
        await asyncio.wait_for(proc.wait(), 3.0)
    except asyncio.TimeoutError:
        for p in tree:
            with contextlib.suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                p.kill()


@router.get("/api/ai/status")
async def ai_status() -> dict:
    global _version
    cli = find_cli()
    if cli and _version is None:
        with contextlib.suppress(Exception):
            res = await asyncio.to_thread(
                subprocess.run, [cli, "--version"], capture_output=True, text=True, timeout=15, env=_child_env()
            )
            _version = (res.stdout or "").strip() or None
    return {"available": bool(cli), "cli": cli, "version": _version,
            "busy": _proc is not None and _proc.returncode is None}


@router.post("/api/ai/stop")
async def ai_stop() -> dict:
    global _stop_requested
    proc = _proc
    if proc is None or proc.returncode is not None:
        return {"stopped": False}
    _stop_requested = True
    await _kill(proc)
    return {"stopped": True}


@router.post("/api/ai/ask")
async def ai_ask(request: Request) -> StreamingResponse:
    global _proc, _stop_requested
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="request body must be valid JSON") from None
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be a JSON object")
    prompt = str(body.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    mode = "ask" if body.get("mode") == "ask" else "act"
    model = str(body.get("model") or "").strip() or None
    session_id = str(body.get("session_id") or "").strip() or None

    cli = find_cli()
    if not cli:
        raise HTTPException(status_code=503, detail="`claude` CLI not found — install Claude Code and run `claude` once to log in")
    if _proc is not None and _proc.returncode is None:
        raise HTTPException(status_code=409, detail="the assistant is already working on something")

    base_url = f"http://127.0.0.1:{request.url.port or 7777}"
    states = get_states() if get_states else []
    cmd = build_command(cli, model=model, session_id=session_id, mode=mode,
                        sys_prompt=system_prompt(base_url, states, mode))

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=PROJECT_ROOT,
        env=_child_env(),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **osutil.popen_group_kwargs(),
        limit=16 * 1024 * 1024,
    )
    _proc = proc
    _stop_requested = False
    assert proc.stdin is not None and proc.stdout is not None and proc.stderr is not None
    proc.stdin.write(prompt.encode("utf-8"))
    await proc.stdin.drain()
    proc.stdin.close()
    # Drain stderr concurrently so a chatty CLI can't block on a full pipe.
    stderr_task = asyncio.create_task(proc.stderr.read())

    async def stream():
        global _proc
        finished = False
        try:
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                for item in _translate(event):
                    finished = finished or item["type"] in ("done", "error")
                    yield _sse(item)
            await proc.wait()
            if not finished:
                err = (await stderr_task).decode("utf-8", "replace").strip()
                msg = err[-800:] if err else f"assistant exited with code {proc.returncode}"
                if _stop_requested:
                    msg = "stopped"
                yield _sse({"type": "error", "message": msg})
        finally:
            # Client went away or the run ended: never leave it burning tokens.
            await _kill(proc)
            stderr_task.cancel()
            if _proc is proc:
                _proc = None

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
