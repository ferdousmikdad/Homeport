"""backend/app_settings.py — small app-wide preferences shared by every window.

Stored in ``<data dir>/settings.json`` so the desktop app and every browser tab
see the same choice (unlike localStorage, which is per browser).

    GET   /api/settings  -> {ai_provider, local_model}
    PATCH /api/settings  body: any of those keys (null clears)
"""
from __future__ import annotations

import json
import os
import re
import threading
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from . import paths

router = APIRouter()

DEFAULTS: dict = {"ai_provider": None, "local_model": None}
_lock = threading.Lock()


def _file() -> str:
    return os.path.join(paths.DATA_DIR, "settings.json")


def load() -> dict:
    data: dict = {}
    try:
        with open(_file(), encoding="utf-8") as fh:
            raw = json.load(fh)
        if isinstance(raw, dict):
            data = raw
    except (OSError, ValueError):
        pass
    return {k: data.get(k, v) for k, v in DEFAULTS.items()}


def update(changes: dict) -> dict:
    with _lock:
        current = load()
        current.update(changes)
        os.makedirs(os.path.dirname(_file()), exist_ok=True)
        tmp = _file() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(current, fh, indent=2)
        os.replace(tmp, _file())
        return current


def _validate(key: str, value: Any) -> Any:
    if value is None:
        return None
    if key == "ai_provider":
        if value not in ("claude", "local"):
            raise HTTPException(status_code=400, detail="ai_provider must be 'claude' or 'local'")
        return value
    if key == "local_model":
        if not isinstance(value, str) or not re.match(r"^[A-Za-z0-9][\w.\-/]*(:[\w.\-]+)?$", value) or len(value) > 120:
            raise HTTPException(status_code=400, detail="invalid model name")
        return value
    raise HTTPException(status_code=400, detail=f"unknown setting: {key}")


@router.get("/api/settings")
async def get_settings() -> dict:
    return load()


@router.patch("/api/settings")
async def patch_settings(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="request body must be valid JSON") from None
    if not isinstance(body, dict) or not body:
        raise HTTPException(status_code=400, detail="send at least one setting")
    return update({k: _validate(k, v) for k, v in body.items()})
