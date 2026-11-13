"""backend/share_routes.py — public share links for running apps.

    GET    /api/share/status               is cloudflared installed?
    POST   /api/share/install              download cloudflared into bin/
    POST   /api/apps/{id}/share            {password?, expires_minutes?} -> share state
    DELETE /api/apps/{id}/share            stop sharing
    POST   /api/apps/{id}/lan              Wi-Fi preview on  -> {url, ip, port}
    DELETE /api/apps/{id}/lan              Wi-Fi preview off
    GET    /api/qr?text=...                QR code (SVG) for a link

Links are Cloudflare Quick Tunnels: free and account-less.
"""

from __future__ import annotations

import asyncio
from typing import Callable, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from .lan import LanGateways
from .tunnels import CloudflaredMissing, TunnelManager

router = APIRouter()
tunnels = TunnelManager()
lan = LanGateways()

# Wired by main.py: app config lookup and the app's live port (None = not running).
get_app_config: Optional[Callable[[str], Optional[dict]]] = None
get_running_port: Optional[Callable[[str], Optional[int]]] = None


@router.get("/api/share/status")
async def share_status() -> dict:
    return await asyncio.to_thread(tunnels.status)


@router.post("/api/share/install")
async def share_install() -> dict:
    try:
        await asyncio.to_thread(tunnels.install)
    except Exception as exc:  # network, GitHub, disk …
        raise HTTPException(status_code=502, detail=f"could not install cloudflared: {exc}") from exc
    return await asyncio.to_thread(tunnels.status)


@router.post("/api/apps/{app_id}/share")
async def share_app(app_id: str, request: Request) -> dict:
    if get_app_config is None or get_running_port is None:
        raise HTTPException(status_code=500, detail="share routes not configured")
    if get_app_config(app_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown app id: {app_id}")
    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body if isinstance(body, dict) else {}
    password = body.get("password")
    expires = body.get("expires_minutes")
    if password is not None and not isinstance(password, str):
        raise HTTPException(status_code=400, detail="password must be text")
    if expires in ("", 0, "0"):
        expires = None
    manager_port = request.url.port or 7777

    port = get_running_port(app_id)
    if not port:
        raise HTTPException(
            status_code=409,
            detail="start the app first — sharing needs it running and listening on a port",
        )
    try:
        return await asyncio.to_thread(
            lambda: tunnels.start(app_id, int(port), manager_port=manager_port,
                                  password=password, expires_minutes=expires)
        )
    except CloudflaredMissing as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.delete("/api/apps/{app_id}/share")
async def unshare_app(app_id: str) -> dict:
    stopped = await asyncio.to_thread(tunnels.stop, app_id)
    return {"ok": True, "stopped": stopped}


@router.post("/api/apps/{app_id}/lan")
async def lan_on(app_id: str) -> dict:
    if get_app_config is None or get_running_port is None:
        raise HTTPException(status_code=500, detail="share routes not configured")
    if get_app_config(app_id) is None:
        raise HTTPException(status_code=404, detail=f"unknown app id: {app_id}")
    port = get_running_port(app_id)
    if not port:
        raise HTTPException(status_code=409, detail="start the app first")
    try:
        return await lan.start(app_id, int(port))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.delete("/api/apps/{app_id}/lan")
async def lan_off(app_id: str) -> dict:
    return {"ok": True, "stopped": await lan.stop(app_id)}


@router.get("/api/qr")
async def qr_code(text: str = Query(..., min_length=1, max_length=1024)) -> Response:
    """QR code as SVG, made locally (segno) — links never leave this computer."""
    import io

    import segno

    buf = io.BytesIO()
    segno.make(text, error="m").save(buf, kind="svg", scale=8, border=2,
                                     dark="#111214", light="#ffffff", xmldecl=False, svgns=True)
    return Response(buf.getvalue(), media_type="image/svg+xml", headers={"Cache-Control": "no-store"})
