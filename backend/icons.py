"""backend/icons.py — find a project's own icon (favicon / app logo).

``find_icon(path)`` returns the absolute path of the best icon file inside a
project folder, or None.  Sources, best first:

1. ``<link rel="icon" href=…>`` declared in the project's index.html
2. well-known favicon / app-icon file names in well-known folders
   (public/, static/, assets/, Next.js app/, Electron build/, Tauri icons …),
   also one level down for projects living in a sub-folder (repo/app, repo/web)

Results are cached per path for a short while because the UI asks every tick.
"""

from __future__ import annotations

import os
import re
import time
from typing import Optional

__all__ = ["find_icon", "MEDIA_TYPES"]

MEDIA_TYPES = {
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

_MAX_BYTES = 3 * 1024 * 1024

_DIRS = (
    "", "public", "static", "assets", "src", "src/assets", "src/app", "app",
    "public/images", "public/img", "public/assets", "public/icons", "static/img",
    "static/images", "assets/images", "assets/img", "resources", "build",
    "src-tauri/icons", "icons", "www", "web", "docs", "images", "img",
)

# Ordered by quality: vector / large raster first, tiny .ico last.
_NAMES = (
    "favicon.svg", "icon.svg", "logo.svg",
    "apple-touch-icon.png", "apple-icon.png", "android-chrome-512x512.png",
    "android-chrome-192x192.png", "icon-512.png", "icon-192.png", "logo512.png",
    "logo192.png", "icon.png", "128x128@2x.png", "128x128.png", "logo.png",
    "favicon.png", "favicon-32x32.png", "app-icon.png", "favicon.ico",
)

_HTML_FILES = ("index.html", "public/index.html", "src/index.html", "app.html",
               "src/app.html", "resources/views/welcome.blade.php")

_SUBDIRS = ("app", "web", "frontend", "client", "site", "website", "www", "server")

_LINK_RE = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
_REL_ICON_RE = re.compile(r"""rel\s*=\s*["'][^"']*\bicon\b[^"']*["']""", re.IGNORECASE)
_HREF_RE = re.compile(r"""href\s*=\s*["']([^"'{}]+)["']""", re.IGNORECASE)

_TTL = 30.0
_cache: dict = {}


def _ok(file_path: str) -> bool:
    try:
        return (
            os.path.isfile(file_path)
            and os.path.splitext(file_path)[1].lower() in MEDIA_TYPES
            and 0 < os.path.getsize(file_path) <= _MAX_BYTES
        )
    except OSError:
        return False


def _from_html(root: str) -> Optional[str]:
    for rel in _HTML_FILES:
        html_path = os.path.join(root, rel)
        if not os.path.isfile(html_path):
            continue
        try:
            with open(html_path, encoding="utf-8", errors="replace") as fh:
                text = fh.read(128 * 1024)
        except OSError:
            continue
        for tag in _LINK_RE.findall(text):
            if not _REL_ICON_RE.search(tag):
                continue
            match = _HREF_RE.search(tag)
            if not match:
                continue
            href = match.group(1).split("?")[0].split("#")[0]
            if href.startswith(("http:", "https:", "data:", "//")):
                continue
            base = os.path.dirname(html_path)
            candidates = [os.path.join(base, href.lstrip("/"))]
            if href.startswith("/"):
                # "/favicon.ico" is served from the web root (public/ or static/)
                candidates += [os.path.join(root, d, href.lstrip("/"))
                               for d in ("public", "static", "")]
            for cand in candidates:
                cand = os.path.normpath(cand)
                if cand.startswith(os.path.normpath(root)) and _ok(cand):
                    return cand
    return None


def _from_names(root: str) -> Optional[str]:
    for name in _NAMES:
        for rel in _DIRS:
            cand = os.path.join(root, rel, name)
            if _ok(cand):
                return cand
    return None


def _search(root: str) -> Optional[str]:
    found = _from_html(root) or _from_names(root)
    if found:
        return found
    for sub_root in _sub_roots(root):
        found = _from_html(sub_root) or _from_names(sub_root)
        if found:
            return found
    return None


_SKIP = {"node_modules", "vendor", "dist", "build", "out", "target", "storage",
         "tests", "test", "venv", "env", "coverage", "tmp", "logs"}


def _sub_roots(root: str) -> list:
    """Sub-projects to try: preferred names, monorepo apps/* & packages/*,
    then any other folder (bounded, so huge trees stay cheap)."""
    try:
        names = sorted(n for n in os.listdir(root)
                       if not n.startswith(".") and n not in _SKIP
                       and os.path.isdir(os.path.join(root, n)))
    except OSError:
        return []
    ordered = [n for n in _SUBDIRS if n in names]
    for mono in ("apps", "packages"):
        if mono in names:
            try:
                kids = sorted(os.listdir(os.path.join(root, mono)))
            except OSError:
                kids = []
            ordered += [os.path.join(mono, k) for k in kids if not k.startswith(".")][:10]
    ordered += [n for n in names if n not in ordered and n not in ("apps", "packages")]
    return [os.path.join(root, n) for n in ordered[:24]]


def find_icon(path: str) -> Optional[str]:
    """Absolute path of the project's icon, or None (cached ~30 s)."""
    if not path:
        return None
    now = time.monotonic()
    hit = _cache.get(path)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    result = _search(path) if os.path.isdir(path) else None
    _cache[path] = (now, result)
    return result
