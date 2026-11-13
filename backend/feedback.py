"""backend/feedback.py — feedback that visitors leave on a shared app.

When a share link has feedback turned on, Homeport's proxy adds a small
"Feedback" button to the app's pages (see proxy.py and feedback_widget.js).
Visitors point at a spot on the page and write a note; it is stored here, on
this computer, per app: ``<data dir>/feedback/<app id>.json``.

The owner reads it in the dashboard, or opens the app with the notes pinned
on the page (review mode, only on this computer).

Dashboard API:
    GET    /api/apps/{id}/feedback                 -> {items, open}
    PATCH  /api/apps/{id}/feedback/{fid}  {status: "open"|"resolved"}
    POST   /api/apps/{id}/feedback/{fid}/reply  {message, name?}
    DELETE /api/apps/{id}/feedback/{fid}
    DELETE /api/apps/{id}/feedback?status=resolved  (or all)
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException, Query, Request

from . import paths

router = APIRouter()

# Wired by main.py: does this app exist?
app_exists: Optional[Callable[[str], bool]] = None

MAX_ITEMS = 1000          # per app; the oldest resolved go first
MAX_MESSAGE = 2000
MAX_NAME = 60
MAX_REPLIES = 100         # per comment
RATE_LIMIT = (30, 600.0)  # per visitor (IP) and app: 30 notes per 10 minutes

_lock = threading.RLock()
_open_counts: dict = {}   # app id -> open count (cache for the dashboard state)
_recent: dict = defaultdict(deque)  # (app id, ip) -> times of recent notes
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,80}$")


def _dir() -> str:
    return os.path.join(paths.DATA_DIR, "feedback")


def _file(app_id: str) -> str:
    if not _ID_RE.match(app_id or ""):
        raise ValueError("invalid app id")
    return os.path.join(_dir(), app_id + ".json")


def _load(app_id: str) -> list:
    try:
        with open(_file(app_id), encoding="utf-8") as fh:
            data = json.load(fh)
        items = data.get("items") if isinstance(data, dict) else None
        return items if isinstance(items, list) else []
    except (OSError, ValueError):
        return []


def _save(app_id: str, items: list) -> None:
    os.makedirs(_dir(), exist_ok=True)
    tmp = _file(app_id) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"items": items}, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, _file(app_id))
    _open_counts[app_id] = sum(1 for i in items if i.get("status") == "open")


def items(app_id: str) -> list:
    with _lock:
        return _load(app_id)


def open_count(app_id: str) -> int:
    with _lock:
        if app_id not in _open_counts:
            try:
                _open_counts[app_id] = sum(1 for i in _load(app_id) if i.get("status") == "open")
            except ValueError:
                return 0
        return _open_counts[app_id]


def _text(value: Any, limit: int) -> str:
    text = value if isinstance(value, str) else ""
    text = text.replace("\r\n", "\n").replace("\x00", "")
    return text.strip()[:limit]


def _num(value: Any, lo: float, hi: float) -> Optional[float]:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    if n != n:  # NaN
        return None
    return round(min(hi, max(lo, n)), 4)


def rate_limited(app_id: str, client: str) -> bool:
    limit, window = RATE_LIMIT
    now = time.monotonic()
    with _lock:
        q = _recent[(app_id, client)]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False


def add(app_id: str, data: dict, *, source: str = "share") -> dict:
    """Store one note from the page widget. Raises ValueError on bad input."""
    if not isinstance(data, dict):
        raise ValueError("send a JSON object")
    message = _text(data.get("message"), MAX_MESSAGE)
    if not message:
        raise ValueError("write a message")
    page = _text(data.get("page"), 500) or "/"
    if not page.startswith("/"):
        page = "/" + page
    item = {
        "id": uuid.uuid4().hex[:12],
        "created_at": time.time(),
        "status": "open",
        "source": "share" if source == "share" else "local",
        "message": message,
        "name": _text(data.get("name"), MAX_NAME),
        "page": page,
        "url": _text(data.get("url"), 1000),
        "title": _text(data.get("title"), 200),
        # where on the page: an element + offset inside it, plus page coordinates as a fallback
        "selector": _text(data.get("selector"), 400),
        "ox": _num(data.get("ox"), 0, 1),
        "oy": _num(data.get("oy"), 0, 1),
        "xp": _num(data.get("xp"), 0, 1),
        "y": _num(data.get("y"), 0, 10_000_000),
        "vw": _num(data.get("vw"), 0, 100_000),
        "vh": _num(data.get("vh"), 0, 100_000),
        "ua": _text(data.get("ua"), 300),
    }
    if item["selector"] == "" or item["ox"] is None or item["oy"] is None:
        item["selector"], item["ox"], item["oy"] = "", None, None
    with _lock:
        current = _load(app_id)
        current.append(item)
        if len(current) > MAX_ITEMS:  # drop the oldest resolved first, then the oldest
            resolved = [i for i in current if i.get("status") == "resolved"]
            drop = {i["id"] for i in (resolved or current)[: len(current) - MAX_ITEMS]}
            current = [i for i in current if i["id"] not in drop][-MAX_ITEMS:]
        _save(app_id, current)
    return item


def add_reply(app_id: str, fid: str, data: dict, *, source: str = "share", open_only: bool = False) -> Optional[dict]:
    """Add a reply to a comment (a thread, like in Figma). None if there's no such
    comment (or it's resolved and ``open_only``). Raises ValueError on bad input."""
    if not isinstance(data, dict):
        raise ValueError("send a JSON object")
    message = _text(data.get("message"), MAX_MESSAGE)
    if not message:
        raise ValueError("write a message")
    reply = {"id": uuid.uuid4().hex[:12], "created_at": time.time(), "message": message,
             "name": _text(data.get("name"), MAX_NAME), "source": "share" if source == "share" else "local"}
    with _lock:
        current = _load(app_id)
        for item in current:
            if item.get("id") == fid:
                if open_only and item.get("status") != "open":
                    return None
                replies = item.setdefault("replies", [])
                if len(replies) >= MAX_REPLIES:
                    raise ValueError("this comment has too many replies")
                replies.append(reply)
                _save(app_id, current)
                return reply
    return None


def set_status(app_id: str, fid: str, status: str) -> Optional[dict]:
    if status not in ("open", "resolved"):
        raise ValueError("status must be 'open' or 'resolved'")
    with _lock:
        current = _load(app_id)
        for item in current:
            if item.get("id") == fid:
                item["status"] = status
                item["resolved_at"] = time.time() if status == "resolved" else None
                _save(app_id, current)
                return item
    return None


def delete(app_id: str, fid: Optional[str] = None, status: Optional[str] = None) -> int:
    with _lock:
        current = _load(app_id)
        keep = [i for i in current
                if not ((fid and i.get("id") == fid) or (not fid and (status is None or i.get("status") == status)))]
        removed = len(current) - len(keep)
        if removed:
            _save(app_id, keep)
        return removed


def forget(app_id: str) -> None:
    """The app was deleted: remove its feedback too."""
    with _lock:
        _open_counts.pop(app_id, None)
        try:
            os.remove(_file(app_id))
        except (OSError, ValueError):
            pass


# ---------------------------------------------------------------------------
# dashboard routes
# ---------------------------------------------------------------------------
def _check_app(app_id: str) -> None:
    if app_exists is not None and not app_exists(app_id):
        raise HTTPException(status_code=404, detail=f"unknown app id: {app_id}")


@router.get("/api/apps/{app_id}/feedback")
async def list_feedback(app_id: str) -> dict:
    _check_app(app_id)
    found = items(app_id)
    found.sort(key=lambda i: i.get("created_at") or 0, reverse=True)
    return {"items": found, "open": sum(1 for i in found if i.get("status") == "open")}


@router.patch("/api/apps/{app_id}/feedback/{fid}")
async def update_feedback(app_id: str, fid: str, request: Request) -> dict:
    _check_app(app_id)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="request body must be valid JSON") from None
    try:
        item = set_status(app_id, fid, str((body or {}).get("status") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="no such feedback")
    return item


@router.post("/api/apps/{app_id}/feedback/{fid}/reply")
async def reply_feedback(app_id: str, fid: str, request: Request) -> dict:
    _check_app(app_id)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="request body must be valid JSON") from None
    try:
        reply = add_reply(app_id, fid, body, source="local")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if reply is None:
        raise HTTPException(status_code=404, detail="no such feedback")
    return reply


@router.delete("/api/apps/{app_id}/feedback/{fid}")
async def delete_feedback(app_id: str, fid: str) -> dict:
    _check_app(app_id)
    if not delete(app_id, fid=fid):
        raise HTTPException(status_code=404, detail="no such feedback")
    return {"deleted": 1}


@router.delete("/api/apps/{app_id}/feedback")
async def clear_feedback(app_id: str, status: Optional[str] = Query(default=None)) -> dict:
    _check_app(app_id)
    if status not in (None, "open", "resolved"):
        raise HTTPException(status_code=400, detail="status must be 'open' or 'resolved'")
    return {"deleted": delete(app_id, status=status)}
