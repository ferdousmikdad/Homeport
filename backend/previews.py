"""backend/previews.py — pull-request previews and comments → GitHub issues.

See docs/V1.2.md §2 and docs/GITHUB.md §3–4.

A preview runs a pull request next to your own copy: Homeport fetches the PR
(`pull/<n>/head`) into a private ref, checks it out as a git **worktree** in a
sibling folder (`<repo>-pr-<n>`), and adds it as an app on its own port with
the same command and env. Your working folder is never touched. Removing the
preview stops it, removes the worktree and the ref.

Writes to GitHub (a PR comment, a new issue) only happen on a click, with the
text the user saw and could edit.

    GET    /api/apps/{id}/feedback/{fid}/issue-draft
    GET    /api/apps/{id}/pulls                      open PRs of the app's repo
    POST   /api/apps/{id}/previews {number, start}   add (or reuse) a preview
    DELETE /api/apps/{id}/preview                    remove a preview app + worktree
    POST   /api/apps/{id}/preview/comment {body}     comment on the preview's PR
    POST   /api/apps/{id}/feedback/{fid}/issue {title, body}
"""
from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request

from . import feedback, github, osutil, shellenv

router = APIRouter()

# Wired by main.py
get_app: Any = None        # (id) -> config or None
add_app: Any = None        # (config) -> config  (registry.add)
asgi_app: Any = None


class PreviewError(RuntimeError):
    pass


def _git(args: list, cwd: str, timeout: float = 300, auth: bool = False) -> subprocess.CompletedProcess:
    git = shellenv.which("git")
    if not git:
        raise PreviewError("git isn't installed")
    env = {**os.environ, "PATH": shellenv.user_path(), "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C",
           **(github.auth_env() if auth else {})}
    try:
        return subprocess.run([git, *args], cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env,
                              encoding="utf-8", errors="replace",
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if osutil.IS_WINDOWS else 0)
    except subprocess.TimeoutExpired:
        raise PreviewError("git took too long") from None


def _toplevel(path: str) -> str:
    res = _git(["rev-parse", "--show-toplevel"], path, timeout=10)
    if res.returncode != 0:
        raise PreviewError("this app's folder isn't a git repository")
    return os.path.normpath(res.stdout.strip())


def _cfg(app_id: str) -> dict:
    cfg = get_app(app_id) if get_app else None
    if not cfg:
        raise HTTPException(status_code=404, detail=f"unknown app id: {app_id}")
    return cfg


def _repo_of(cfg: dict) -> str:
    repo = github._remote_repo(cfg.get("path") or "")
    if not repo:
        raise HTTPException(status_code=409, detail="this app's code isn't on GitHub (no github.com origin remote)")
    return repo


def _token() -> str:
    token, _ = github.current()
    if not token:
        raise HTTPException(status_code=401, detail="connect GitHub first (Settings → GitHub)")
    return token


async def _gh(method: str, path: str, token: str, **kw) -> Any:
    try:
        async with httpx.AsyncClient(timeout=20.0, transport=github.transport, follow_redirects=True) as c:
            r = await c.request(method, github.API + path, headers=github._headers(token), **kw)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"couldn't reach GitHub: {exc}") from exc
    if r.status_code >= 400:
        try:
            msg = r.json().get("message")
        except ValueError:
            msg = None
        raise HTTPException(status_code=502 if r.status_code >= 500 else r.status_code,
                            detail=f"GitHub: {msg or r.status_code}")
    return r.json()


async def _body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="request body must be valid JSON") from None
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="request body must be a JSON object")
    return body


# ---------------------------------------------------------------------------
# pull requests and previews
# ---------------------------------------------------------------------------
@router.get("/api/apps/{app_id}/pulls")
async def pulls(app_id: str) -> dict:
    cfg = _cfg(app_id)
    repo = await asyncio.to_thread(_repo_of, cfg)
    data = await _gh("GET", f"/repos/{repo}/pulls", _token(), params={"state": "open", "per_page": 50})
    previews = {a["preview"]["number"]: a["id"] for a in _all_apps()
                if (a.get("preview") or {}).get("of") == app_id}
    return {"repo": repo, "pulls": [{
        "number": p.get("number"), "title": p.get("title") or "", "author": (p.get("user") or {}).get("login"),
        "branch": (p.get("head") or {}).get("ref"), "draft": bool(p.get("draft")), "url": p.get("html_url"),
        "updated_at": p.get("updated_at"), "preview": previews.get(p.get("number")),
    } for p in data]}


def _all_apps() -> list:
    from . import main
    return main.registry.list()


def _make_worktree(cfg: dict, number: int) -> tuple:
    """(worktree folder, app folder inside it). Reuses an existing worktree."""
    app_path = os.path.abspath(cfg["path"])
    top = _toplevel(app_path)
    sub = os.path.relpath(app_path, top)
    worktree = f"{top}-pr-{number}"
    ref = f"refs/homeport/pr-{number}"
    fetched = _git(["fetch", "--quiet", "origin", f"+pull/{number}/head:{ref}"], top, auth=True)
    if fetched.returncode != 0:
        raise PreviewError("couldn't fetch the pull request: " + (fetched.stderr.strip().splitlines() or ["git fetch failed"])[-1])
    if os.path.isdir(worktree):
        # bring an existing preview up to date with the PR (it's a detached checkout, never your work)
        _git(["checkout", "--quiet", "--detach", ref], worktree)
    else:
        added = _git(["worktree", "add", "--quiet", "--detach", worktree, ref], top)
        if added.returncode != 0:
            raise PreviewError("couldn't create the preview folder: " + (added.stderr.strip().splitlines() or ["git worktree failed"])[-1])
    folder = os.path.normpath(os.path.join(worktree, sub)) if sub != "." else worktree
    # untracked settings files aren't in a fresh checkout: bring the app's own
    for name in (".env", ".env.local"):
        src, dst = os.path.join(app_path, name), os.path.join(folder, name)
        if os.path.isfile(src) and not os.path.exists(dst) and os.path.isdir(folder):
            shutil.copyfile(src, dst)
    return worktree, folder


@router.post("/api/apps/{app_id}/previews")
async def add_preview(app_id: str, request: Request) -> dict:
    from . import main

    body = await _body(request)
    number = body.get("number")
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise HTTPException(status_code=400, detail="number must be the pull request number")
    cfg = _cfg(app_id)
    if cfg.get("preview"):
        raise HTTPException(status_code=400, detail="this app is already a preview")
    existing = next((a for a in _all_apps() if (a.get("preview") or {}).get("of") == app_id
                     and a["preview"].get("number") == number), None)

    title, url = body.get("title") or "", body.get("url") or ""
    try:
        worktree, folder = await asyncio.to_thread(_make_worktree, cfg, number)
    except PreviewError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if existing:
        app = existing
    else:
        port = cfg.get("port")
        new_port = await asyncio.to_thread(main.free_port, (port or 3000) + 100, main._registered_ports()) if port else None
        command = cfg.get("command") or ""
        if port and new_port and command:
            command = re.sub(rf"\b{port}\b", str(new_port), command)
        name = f"{cfg['name']} · PR #{number}"
        try:
            app = add_app({
                "name": name, "path": folder, "command": command, "port": new_port, "env": cfg.get("env") or {},
                "category": cfg.get("category") or "",
                "health_url": (cfg.get("health_url") or "").replace(f":{port}", f":{new_port}") if port and new_port else cfg.get("health_url"),
                "preview": {"of": app_id, "number": number, "title": title, "url": url, "worktree": worktree},
            })
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    if body.get("start", True) and app.get("command"):
        code, state = await _api("POST", f"/api/apps/{app['id']}/start")
        if code == 200:
            return state
    code, state = await _api("GET", f"/api/apps/{app['id']}")
    return state


async def _api(method: str, path: str, **kw) -> tuple:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=asgi_app), base_url="http://127.0.0.1",
                                 timeout=120.0) as c:
        r = await c.request(method, path, **kw)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {"detail": r.text[:300]}


def _remove_worktree(cfg: dict) -> None:
    pv = cfg.get("preview") or {}
    worktree, number = pv.get("worktree"), pv.get("number")
    if not worktree or not os.path.isdir(worktree):
        return
    original = get_app(pv.get("of")) if pv.get("of") else None
    top = _toplevel(original["path"]) if original and os.path.isdir(original.get("path") or "") else None
    if top is None:
        # the original app is gone: find the main repo from the worktree itself
        res = _git(["rev-parse", "--path-format=absolute", "--git-common-dir"], worktree, timeout=10)
        top = os.path.dirname(res.stdout.strip()) if res.returncode == 0 else None
    if top:
        _git(["worktree", "remove", "--force", worktree], top)
        if number:
            _git(["update-ref", "-d", f"refs/homeport/pr-{number}"], top)
    if os.path.isdir(worktree):  # git couldn't (e.g. already pruned): it's our folder, a checkout of the PR
        shutil.rmtree(worktree, ignore_errors=True)


@router.delete("/api/apps/{app_id}/preview")
async def remove_preview(app_id: str) -> dict:
    cfg = _cfg(app_id)
    if not cfg.get("preview"):
        raise HTTPException(status_code=400, detail="this app isn't a pull-request preview")
    code, _ = await _api("DELETE", f"/api/apps/{app_id}")
    if code != 200:
        raise HTTPException(status_code=code, detail="couldn't remove the app")
    try:
        await asyncio.to_thread(_remove_worktree, cfg)
    except PreviewError as exc:
        return {"ok": True, "warning": f"the app was removed, but not its folder: {exc}"}
    return {"ok": True}


@router.post("/api/apps/{app_id}/preview/comment")
async def comment_on_pr(app_id: str, request: Request) -> dict:
    cfg = _cfg(app_id)
    pv = cfg.get("preview")
    if not pv:
        raise HTTPException(status_code=400, detail="this app isn't a pull-request preview")
    text = str((await _body(request)).get("body") or "").strip()
    if not text or len(text) > 20000:
        raise HTTPException(status_code=400, detail="write the comment first")
    original = get_app(pv.get("of")) or cfg
    repo = await asyncio.to_thread(_repo_of, original)
    made = await _gh("POST", f"/repos/{repo}/issues/{pv['number']}/comments", _token(), json={"body": text})
    return {"ok": True, "url": made.get("html_url")}


# ---------------------------------------------------------------------------
# a visitor comment → a GitHub issue
# ---------------------------------------------------------------------------
@router.get("/api/apps/{app_id}/feedback/{fid}/issue-draft")
async def get_issue_draft(app_id: str, fid: str) -> dict:
    cfg = _cfg(app_id)
    item = next((i for i in feedback.items(app_id) if i.get("id") == fid), None)
    if item is None:
        raise HTTPException(status_code=404, detail="no such feedback")
    return issue_draft(cfg["name"], item, item.get("url"))


@router.post("/api/apps/{app_id}/feedback/{fid}/issue")
async def comment_to_issue(app_id: str, fid: str, request: Request) -> dict:
    cfg = _cfg(app_id)
    body = await _body(request)
    title = str(body.get("title") or "").strip()[:250]
    text = str(body.get("body") or "").strip()[:60000]
    if not title:
        raise HTTPException(status_code=400, detail="the issue needs a title")
    item = next((i for i in feedback.items(app_id) if i.get("id") == fid), None)
    if item is None:
        raise HTTPException(status_code=404, detail="no such feedback")
    original = get_app((cfg.get("preview") or {}).get("of")) if cfg.get("preview") else cfg
    repo = await asyncio.to_thread(_repo_of, original or cfg)
    made = await _gh("POST", f"/repos/{repo}/issues", _token(), json={"title": title, "body": text})
    issue = {"number": made.get("number"), "url": made.get("html_url")}
    feedback.set_issue(app_id, fid, issue)
    return {"ok": True, "issue": issue}


def issue_draft(app_name: str, item: dict, link: Optional[str]) -> dict:
    """A suggested issue for a comment (the UI shows it for editing before anything is sent)."""
    first = (item.get("message") or "").strip().splitlines()[0] if item.get("message") else "Feedback"
    lines = [f"> {line}" for line in (item.get("message") or "").splitlines()]
    lines.append("")
    lines.append(f"— {item.get('name') or 'A visitor'}, on `{item.get('page') or '/'}`"
                 + (f" ({int(item['vw'])}×{int(item.get('vh') or 0)} screen)" if item.get("vw") else ""))
    for r in item.get("replies") or []:
        lines.append(f"\n**{r.get('name') or 'Someone'}:** {r.get('message')}")
    if link:
        lines.append(f"\n[Open the page]({link})")
    lines.append(f"\n_From visitor feedback on {app_name}, via Homeport._")
    return {"title": first[:120], "body": "\n".join(lines)}
