"""backend/github.py — optional GitHub integration (see docs/GITHUB.md).

Connect (device flow, GitHub CLI login, or a pasted token), list your repos,
clone one and add it as an app, and show CI + pull requests on app cards.
Homeport talks only to GitHub; the login is kept in ``<data dir>/github.json``
(mode 600) and never returned by the API.

    GET  /api/github/status
    POST /api/github/device/start      POST /api/github/device/poll
    POST /api/github/token {token}     POST /api/github/disconnect
    GET  /api/github/repos?q=
    POST /api/github/clone {repo, name?, start?}
"""
from __future__ import annotations

import base64
import contextlib
import json
import os
import re
import subprocess
import threading
import time
from typing import Any, Callable, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request

from . import app_settings, osutil, paths, shellenv

router = APIRouter()

# Public ID of Homeport's GitHub OAuth App (device flow has no secret). See docs/GITHUB.md §6.
CLIENT_ID = os.environ.get("HOMEPORT_GITHUB_CLIENT_ID", "").strip() or "Ov23liStlU8NN3otH60L"
SCOPES = "repo read:user"
API = "https://api.github.com"
WEB = "https://github.com"
CARD_TTL = 120.0      # seconds between GitHub checks per repo/branch
REMOTE_TTL = 60.0     # seconds between `git remote get-url` per folder

# Tests swap in an httpx.MockTransport (used for both sync and async clients).
transport: Any = None
# Assigned by main.py: the Homeport app, to add/start apps in-process.
asgi_app: Any = None

_lock = threading.RLock()
_gh_cache: dict = {"t": 0.0, "token": None}
_user_cache: dict = {}            # token fingerprint -> user dict
_device: dict = {}                # the sign-in in progress
_remote_cache: dict = {}          # path -> (time, "owner/repo" | None)
_card_cache: dict = {}            # (repo, branch) -> (time, {ci, ci_url, prs})
_busy: set = set()

_REPO_RE = re.compile(r"^(?:https?://github\.com/|git@github\.com:|ssh://git@github\.com/)?"
                      r"([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9._-]{1,100}?)(?:\.git)?/?$")


# ---------------------------------------------------------------------------
# the login
# ---------------------------------------------------------------------------
def _file() -> str:
    return os.path.join(paths.DATA_DIR, "github.json")


def _saved() -> Optional[dict]:
    try:
        with open(_file(), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) and data.get("token") else None
    except (OSError, ValueError):
        return None


def _save(token: str, how: str) -> None:
    os.makedirs(paths.DATA_DIR, exist_ok=True)
    tmp = _file() + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"token": token, "how": how, "saved_at": time.time()}, fh)
    os.replace(tmp, _file())
    with contextlib.suppress(OSError):
        os.chmod(_file(), 0o600)
    _forget_caches()


def _forget_caches() -> None:
    with _lock:
        _user_cache.clear()
        _card_cache.clear()


def gh_cli() -> Optional[str]:
    return shellenv.which("gh")


def _gh_token() -> Optional[str]:
    """The GitHub CLI's login, if `gh` is installed and logged in (cached 60 s)."""
    with _lock:
        if time.time() - _gh_cache["t"] < 60:
            return _gh_cache["token"]
    token = None
    gh = gh_cli()
    if gh:
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            res = subprocess.run([gh, "auth", "token", "--hostname", "github.com"], capture_output=True, text=True,
                                 timeout=8, env={**os.environ, "PATH": shellenv.user_path(), "GH_PROMPT_DISABLED": "1"},
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if osutil.IS_WINDOWS else 0)
            if res.returncode == 0 and res.stdout.strip():
                token = res.stdout.strip()
    with _lock:
        _gh_cache.update(t=time.time(), token=token)
    return token


def current() -> tuple:
    """(token, source): Homeport's own login first, then GitHub CLI's."""
    saved = _saved()
    if saved:
        return saved["token"], "homeport"
    tok = _gh_token()
    return (tok, "gh") if tok else (None, None)


def auth_env(token: Optional[str] = None) -> dict:
    """Environment that lets one git command use the login for github.com (never written to disk)."""
    token = token or current()[0]
    if not token:
        return {}
    basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    return {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
            "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {basic}"}


def _headers(token: Optional[str]) -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "Homeport"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _aclient(timeout: float = 15.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout, transport=transport, follow_redirects=True)


async def _user(token: str) -> Optional[dict]:
    key = token[-12:]
    with _lock:
        if key in _user_cache:
            return _user_cache[key]
    try:
        async with _aclient() as c:
            r = await c.get(API + "/user", headers=_headers(token))
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    d = r.json()
    user = {"login": d.get("login"), "name": d.get("name") or d.get("login"), "avatar_url": d.get("avatar_url")}
    with _lock:
        _user_cache[key] = user
    return user


def default_projects_dir() -> str:
    home = os.path.expanduser("~")
    for name in ("Projects", "Developer", "Code", "code", "dev", "src"):
        if os.path.isdir(os.path.join(home, name)):
            return os.path.join(home, name)
    return os.path.join(home, "Projects")


def projects_dir() -> str:
    return app_settings.load().get("projects_dir") or default_projects_dir()


# ---------------------------------------------------------------------------
# routes: connect
# ---------------------------------------------------------------------------
async def _body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="request body must be valid JSON") from None
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be a JSON object")
    return body


@router.get("/api/github/status")
async def status() -> dict:
    import asyncio

    token, source = await asyncio.to_thread(current)  # may ask the GitHub CLI: off the event loop
    user = await _user(token) if token else None
    if token and user is None:
        source = source + "-invalid"  # a login that GitHub no longer accepts
    return {
        "connected": bool(user),
        "source": source,
        "user": user,
        "device_flow": bool(CLIENT_ID),
        "gh_installed": bool(gh_cli()),
        "projects_dir": projects_dir(),
    }


@router.post("/api/github/device/start")
async def device_start() -> dict:
    if not CLIENT_ID:
        raise HTTPException(status_code=501, detail="Sign in with GitHub isn't set up in this build — use GitHub CLI or a token")
    try:
        async with _aclient() as c:
            r = await c.post(WEB + "/login/device/code", data={"client_id": CLIENT_ID, "scope": SCOPES},
                             headers={"Accept": "application/json", "User-Agent": "Homeport"})
        d = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"couldn't reach GitHub: {exc}") from exc
    if r.status_code != 200 or "device_code" not in d:
        raise HTTPException(status_code=502, detail=d.get("error_description") or "GitHub didn't start the sign-in")
    with _lock:
        _device.clear()
        _device.update(code=d["device_code"], interval=int(d.get("interval") or 5),
                       expires=time.time() + int(d.get("expires_in") or 900))
    return {"user_code": d["user_code"], "verification_uri": d.get("verification_uri") or WEB + "/login/device",
            "interval": int(d.get("interval") or 5), "expires_in": int(d.get("expires_in") or 900)}


@router.post("/api/github/device/poll")
async def device_poll() -> dict:
    with _lock:
        dev = dict(_device)
    if not dev:
        return {"status": "expired"}
    if time.time() > dev["expires"]:
        _device.clear()
        return {"status": "expired"}
    try:
        async with _aclient() as c:
            r = await c.post(WEB + "/login/oauth/access_token",
                             data={"client_id": CLIENT_ID, "device_code": dev["code"],
                                   "grant_type": "urn:ietf:params:oauth:grant-type:device_code"},
                             headers={"Accept": "application/json", "User-Agent": "Homeport"})
        d = r.json()
    except (httpx.HTTPError, ValueError):
        return {"status": "pending"}
    if d.get("access_token"):
        _save(d["access_token"], "device")
        _device.clear()
        return {"status": "done", "user": await _user(d["access_token"])}
    err = d.get("error")
    if err == "slow_down":
        with _lock:
            _device["interval"] = dev["interval"] + 5
        return {"status": "slow_down", "interval": dev["interval"] + 5}
    if err in ("expired_token", "token_expired"):
        _device.clear()
        return {"status": "expired"}
    if err == "access_denied":
        _device.clear()
        return {"status": "denied"}
    return {"status": "pending"}


@router.post("/api/github/token")
async def set_token(request: Request) -> dict:
    token = str((await _body(request)).get("token") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_\-.]{20,255}", token):
        raise HTTPException(status_code=400, detail="that doesn't look like a GitHub token")
    _forget_caches()
    user = await _user(token)
    if not user:
        raise HTTPException(status_code=400, detail="GitHub didn't accept this token")
    _save(token, "token")
    return {"connected": True, "user": user}


@router.post("/api/github/disconnect")
async def disconnect() -> dict:
    with contextlib.suppress(FileNotFoundError):
        os.remove(_file())
    _forget_caches()
    with _lock:
        _gh_cache.update(t=0.0, token=None)
    import asyncio

    token, source = await asyncio.to_thread(current)
    return {"disconnected": True, "still_connected_through": source}


# ---------------------------------------------------------------------------
# routes: repos and cloning
# ---------------------------------------------------------------------------
@router.get("/api/github/repos")
async def repos(q: str = "") -> dict:
    token, _ = current()
    if not token:
        raise HTTPException(status_code=401, detail="connect GitHub first (Settings → GitHub)")
    found: list = []
    try:
        async with _aclient(20.0) as c:
            for page in (1, 2, 3):
                r = await c.get(API + "/user/repos", headers=_headers(token),
                                params={"sort": "updated", "per_page": 100, "page": page,
                                        "affiliation": "owner,collaborator,organization_member"})
                if r.status_code != 200:
                    raise HTTPException(status_code=502, detail=f"GitHub answered {r.status_code}")
                batch = r.json()
                found += batch
                if len(batch) < 100:
                    break
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"couldn't reach GitHub: {exc}") from exc
    q = q.strip().lower()
    out = []
    for d in found:
        item = {"full_name": d.get("full_name"), "name": d.get("name"), "owner": (d.get("owner") or {}).get("login"),
                "private": bool(d.get("private")), "description": d.get("description") or "",
                "language": d.get("language"), "updated_at": d.get("pushed_at") or d.get("updated_at"),
                "default_branch": d.get("default_branch"), "html_url": d.get("html_url"),
                "archived": bool(d.get("archived")), "fork": bool(d.get("fork"))}
        if q and q not in (item["full_name"] or "").lower() and q not in item["description"].lower():
            continue
        out.append(item)
    return {"repos": out}


def parse_repo(text: str) -> Optional[tuple]:
    m = _REPO_RE.match((text or "").strip())
    if not m or m.group(2) in (".", ".."):
        return None
    return m.group(1), m.group(2)


def clone_url(owner: str, repo: str) -> str:
    return f"{WEB}/{owner}/{repo}.git"


def _git_env(extra: dict) -> dict:
    return {**os.environ, "PATH": shellenv.user_path(), "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C", **extra}


def _clone(url: str, target: str, token: Optional[str]) -> None:
    git = shellenv.which("git")
    if not git:
        raise RuntimeError("git isn't installed — get it from git-scm.com")
    os.makedirs(os.path.dirname(target), exist_ok=True)
    try:
        res = subprocess.run([git, "clone", "--quiet", url, target], capture_output=True, text=True, timeout=900,
                             env=_git_env(auth_env(token) if token else {}), encoding="utf-8", errors="replace",
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if osutil.IS_WINDOWS else 0)
    except subprocess.TimeoutExpired:
        raise RuntimeError("cloning took too long (15 minutes)") from None
    if res.returncode != 0:
        msg = (res.stderr or res.stdout).strip().splitlines()
        hint = " — is the repo private? Connect GitHub first." if any("not found" in m.lower() or "authentication" in m.lower() for m in msg) else ""
        raise RuntimeError((msg[-1] if msg else "git clone failed") + hint)


def _pretty(name: str) -> str:
    words = " ".join(name.replace("-", " ").replace("_", " ").split())
    return words[:1].upper() + words[1:] if words else name


async def _api(method: str, path: str, **kw) -> tuple:
    transport_ = httpx.ASGITransport(app=asgi_app)
    async with httpx.AsyncClient(transport=transport_, base_url="http://127.0.0.1", timeout=600.0) as c:
        r = await c.request(method, path, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"detail": r.text[:300]}


@router.post("/api/github/clone")
async def clone(request: Request) -> dict:
    import asyncio

    body = await _body(request)
    parsed = parse_repo(str(body.get("repo") or ""))
    if not parsed:
        raise HTTPException(status_code=400, detail="use a GitHub repo like owner/name or https://github.com/owner/name")
    owner, repo = parsed
    folder = str(body.get("name") or repo).strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", folder) or folder in (".", ".."):
        raise HTTPException(status_code=400, detail="folder name can only use letters, numbers, . _ and -")
    target = os.path.join(projects_dir(), folder)
    if os.path.exists(target) and (not os.path.isdir(target) or os.listdir(target)):
        raise HTTPException(status_code=409, detail=f"{target} already exists — pick another folder name")
    token, _ = current()
    try:
        await asyncio.to_thread(_clone, clone_url(owner, repo), target, token)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    code, app = await _api("POST", "/api/apps", json={"name": _pretty(repo), "path": target,
                                                       "description": str(body.get("description") or "")[:300]})
    if code not in (200, 201):
        raise HTTPException(status_code=code, detail=(app or {}).get("detail") or "cloned, but couldn't add the app")
    if body.get("start") and app.get("command"):
        code, started = await _api("POST", f"/api/apps/{app['id']}/start")
        if code == 200:
            app = started
    with _lock:
        _remote_cache.pop(("remote", target), None)
    return {"app": app, "path": target}


# ---------------------------------------------------------------------------
# GitHub on app cards (never blocks the dashboard: cached, refreshed in background)
# ---------------------------------------------------------------------------
def _remote_repo(path: str) -> Optional[str]:
    git = shellenv.which("git")
    if not git:
        return None
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        res = subprocess.run([git, "remote", "get-url", "origin"], cwd=path, capture_output=True, text=True, timeout=5,
                             env=_git_env({}),
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if osutil.IS_WINDOWS else 0)
        if res.returncode == 0:
            parsed = parse_repo(res.stdout.strip())
            if parsed:
                return f"{parsed[0]}/{parsed[1]}"
    return None


def _summarize_checks(runs: list, legacy_state: Optional[str]) -> tuple:
    """('success'|'failure'|'pending'|None, url)"""
    if runs:
        if any(r.get("status") != "completed" for r in runs):
            run = next(r for r in runs if r.get("status") != "completed")
            return "pending", run.get("html_url")
        bad = [r for r in runs if r.get("conclusion") in ("failure", "timed_out", "action_required", "startup_failure")]
        if bad:
            return "failure", bad[0].get("html_url")
        return "success", runs[0].get("html_url")
    if legacy_state in ("success", "failure", "error", "pending"):
        return ("failure" if legacy_state == "error" else legacy_state), None
    return None, None


def _fetch_card(repo: str, branch: str, token: str) -> dict:
    info: dict = {"ci": None, "ci_url": None, "prs": None}
    with httpx.Client(timeout=10.0, transport=transport, follow_redirects=True) as c:
        h = _headers(token)
        with contextlib.suppress(httpx.HTTPError, ValueError):
            r = c.get(f"{API}/repos/{repo}/commits/{branch}/check-runs", headers=h, params={"per_page": 100})
            runs = r.json().get("check_runs", []) if r.status_code == 200 else []
            legacy = None
            if not runs:
                s = c.get(f"{API}/repos/{repo}/commits/{branch}/status", headers=h)
                if s.status_code == 200 and s.json().get("total_count"):
                    legacy = s.json().get("state")
            info["ci"], info["ci_url"] = _summarize_checks(runs, legacy)
            if info["ci"] and not info["ci_url"]:
                info["ci_url"] = f"{WEB}/{repo}/commits/{branch}"
        with contextlib.suppress(httpx.HTTPError, ValueError):
            r = c.get(f"{API}/repos/{repo}/pulls", headers=h, params={"state": "open", "per_page": 100})
            if r.status_code == 200:
                info["prs"] = len(r.json())
    return info


def _refresh(key: tuple, fn: Callable[[], Any], cache: dict) -> None:
    try:
        value = fn()
        with _lock:
            cache[key] = (time.time(), value)
    except Exception:  # never break the dashboard over GitHub
        with _lock:
            cache[key] = (time.time(), cache.get(key, (0, None))[1])
    finally:
        with _lock:
            _busy.discard(key)


def _cached(key: tuple, ttl: float, cache: dict, fn: Callable[[], Any]) -> Any:
    with _lock:
        hit = cache.get(key)
        if (hit is None or time.time() - hit[0] > ttl) and key not in _busy:
            _busy.add(key)
            threading.Thread(target=_refresh, args=(key, fn, cache), daemon=True).start()
    return hit[1] if hit else None


def card_state(path: str, git: Optional[dict]) -> Optional[dict]:
    """{repo, url, ci, ci_url, prs} for an app whose origin is on GitHub, else None."""
    if not path or not git:
        return None
    repo = _cached(("remote", path), REMOTE_TTL, _remote_cache, lambda: _remote_repo(path))
    if not repo:
        return None
    state = {"repo": repo, "url": f"{WEB}/{repo}", "ci": None, "ci_url": None, "prs": None}
    branch = git.get("branch")
    saved = _saved()
    token = saved["token"] if saved else _gh_cache.get("token")  # never runs `gh` on the dashboard tick
    if branch and token:
        info = _cached(("card", repo, branch), CARD_TTL, _card_cache, lambda: _fetch_card(repo, branch, token))
        if info:
            state.update(info)
    return state
