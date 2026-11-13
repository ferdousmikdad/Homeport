"""backend/registry.py — persisted AppConfig store (owner: worker C).

The registry is the single source of truth for the apps the manager knows
about.  It is a plain JSON file (``data/apps.json`` by default) holding a list
of AppConfig dicts, read and written under a lock.  Writes are atomic
(tmp file in the same directory + ``os.replace``) so a crash or a concurrent
reader never sees a half-written file.

Public surface (see SPEC.md)::

    Registry(path="data/apps.json")
        .list()                -> list[dict]
        .get(app_id)           -> dict | None
        .add(cfg)              -> dict
        .update(app_id, patch) -> dict
        .remove(app_id)        -> bool
        .reorder(ids)          -> list[dict]

AppConfig::

    {id, name, path, command, port, health_url, color, auto_restart, env}

``id`` is a unique slug of ``name``.  Adding an app whose name already exists
raises ``ValueError``; unknown ids raise ``KeyError`` from ``update``.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import unicodedata
from typing import Any

__all__ = ["Registry", "slugify", "DEFAULT_PATH", "COLORS"]

# Default location: <repo>/data/apps.json, independent of the current cwd.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(_PROJECT_ROOT, "data", "apps.json")

DEFAULT_CONFIG: dict[str, Any] = {
    "id": "",
    "name": "",
    "path": "",
    "command": "",
    "port": None,
    "health_url": None,
    "description": "",
    "category": "",
    "color": "",
    "auto_restart": False,
    "autostart": False,
    "notify": True,
    "env": {},
}

# Fields a client may set; ``id`` is always derived, never patched.
_WRITABLE = (
    "name",
    "path",
    "command",
    "port",
    "health_url",
    "description",
    "category",
    "color",
    "auto_restart",
    "autostart",
    "notify",
    "env",
    "service",
    "created_at",
    "updated_at",
)

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")

# Card highlight colours; "" means no highlight.
COLORS = ("", "red", "green", "blue")


def slugify(value: str) -> str:
    """Lowercase ASCII slug: ``"My Cool App!"`` -> ``"my-cool-app"``."""
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = _SLUG_STRIP.sub("-", text).strip("-")
    return text or "app"


def _opt_int(value: Any) -> int | None:
    """Coerce to int, treating None/"" as None.  Raises ValueError otherwise."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f"expected an integer, got {value!r}") from None


def _opt_port(value: Any) -> int | None:
    port = _opt_int(value)
    if port is not None and not (0 <= port <= 65535):
        raise ValueError(f"port out of range: {port}")
    return port


def _opt_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _opt_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_env(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("env must be an object of string values")
    return {str(key): str(val) for key, val in value.items()}


def _color(value: Any) -> str:
    """Unknown colours fall back to none; the API rejects them before this."""
    text = str(value or "").strip().lower()
    return text if text in COLORS else ""


def _normalize(cfg: dict, *, app_id: str) -> dict:
    """Build a complete AppConfig from a partial dict, filling defaults."""
    name = str(cfg.get("name") or "").strip()
    if not name:
        raise ValueError("name is required")
    path = str(cfg.get("path") or "").strip()
    if not path:
        raise ValueError("path is required")

    created_at = cfg.get("created_at")
    updated_at = cfg.get("updated_at")
    if os.path.exists(path):
        try:
            st = os.stat(path)
            if created_at is None:
                created_at = getattr(st, "st_birthtime", st.st_ctime)
            if updated_at is None:
                updated_at = st.st_mtime
        except OSError:
            pass

    return {
        "id": app_id,
        "name": name,
        "path": path,
        "command": str(cfg.get("command") or ""),
        "port": _opt_port(cfg.get("port")),
        "health_url": _opt_str(cfg.get("health_url")),
        "description": str(cfg.get("description") or "").strip(),
        "category": str(cfg.get("category") or "").strip(),
        "color": _color(cfg.get("color")),
        "auto_restart": bool(cfg.get("auto_restart", False)),
        "autostart": bool(cfg.get("autostart", False)),
        "notify": bool(cfg.get("notify", True)),
        "env": _coerce_env(cfg.get("env")),
        "service": cfg.get("service") if isinstance(cfg.get("service"), dict) else None,
        "created_at": _opt_float(created_at),
        "updated_at": _opt_float(updated_at),
    }


class Registry:
    """Thread-safe JSON-backed collection of AppConfig records."""

    def __init__(self, path: str = DEFAULT_PATH):
        self.path = os.path.abspath(os.path.expanduser(str(path)))
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def list(self) -> list[dict]:
        """All apps, in registration order (fresh copies)."""
        with self._lock:
            return [self._copy(app) for app in self._read()]

    def get(self, app_id: str) -> dict | None:
        """One app by id, or None."""
        key = str(app_id)
        with self._lock:
            for app in self._read():
                if app["id"] == key:
                    return self._copy(app)
        return None

    def add(self, cfg: dict) -> dict:
        """Register a new app, deriving a unique slug id from its name.

        Raises ValueError for a duplicate name or missing/invalid fields.
        """
        if not isinstance(cfg, dict):
            raise ValueError("app config must be an object")
        data = {key: cfg[key] for key in _WRITABLE if key in cfg}
        data.setdefault("name", cfg.get("name"))
        data.setdefault("path", cfg.get("path"))

        with self._lock:
            apps = self._read()
            name = str(data.get("name") or "").strip()
            if not name:
                raise ValueError("name is required")
            if any(app["name"].casefold() == name.casefold() for app in apps):
                raise ValueError(f"an app named {name!r} already exists")

            app_id = slugify(name)
            taken = {app["id"] for app in apps}
            if app_id in taken:
                suffix = 2
                while f"{app_id}-{suffix}" in taken:
                    suffix += 1
                app_id = f"{app_id}-{suffix}"

            app = _normalize(data, app_id=app_id)
            apps.append(app)
            self._write(apps)
            return self._copy(app)

    def update(self, app_id: str, patch: dict) -> dict:
        """Apply a partial AppConfig to an existing app and return the result.

        Raises KeyError for an unknown id and ValueError for invalid values or
        a name that collides with another app.  The id never changes.
        """
        if not isinstance(patch, dict):
            raise ValueError("patch must be an object")
        key = str(app_id)

        with self._lock:
            apps = self._read()
            target = next((app for app in apps if app["id"] == key), None)
            if target is None:
                raise KeyError(key)

            merged = dict(target)
            for field in _WRITABLE:
                if field in patch:
                    merged[field] = patch[field]

            new_name = str(merged.get("name") or "").strip()
            if any(
                app["id"] != key and app["name"].casefold() == new_name.casefold()
                for app in apps
            ):
                raise ValueError(f"an app named {new_name!r} already exists")

            updated = _normalize(merged, app_id=key)
            index = apps.index(target)
            apps[index] = updated
            self._write(apps)
            return self._copy(updated)

    def remove(self, app_id: str) -> bool:
        """Delete an app.  Returns False when the id was not registered."""
        key = str(app_id)
        with self._lock:
            apps = self._read()
            remaining = [app for app in apps if app["id"] != key]
            if len(remaining) == len(apps):
                return False
            self._write(remaining)
            return True

    def reorder(self, ids: list) -> list[dict]:
        """Persist a manual ordering.  ``ids`` lists app ids in the desired
        order; unknown ids are ignored and unlisted apps keep their relative
        order after the listed ones."""
        if not isinstance(ids, list):
            raise ValueError("ids must be a list")
        with self._lock:
            apps = self._read()
            by_id = {app["id"]: app for app in apps}
            ordered: list[dict] = []
            for app_id in ids:
                app = by_id.pop(str(app_id), None)
                if app is not None:
                    ordered.append(app)
            ordered.extend(app for app in apps if app["id"] in by_id)
            self._write(ordered)
            return [self._copy(app) for app in ordered]

    # ------------------------------------------------------------------
    # storage
    # ------------------------------------------------------------------
    def _copy(self, app: dict) -> dict:
        copy = dict(app)
        copy["env"] = dict(app.get("env") or {})
        return copy

    def _read(self) -> list[dict]:
        """Load and normalize the file; missing file -> empty list."""
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"registry file is not valid JSON: {self.path}: {exc}") from exc

        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ValueError(f"registry file must contain a list: {self.path}")

        apps: list[dict] = []
        seen: set[str] = set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            app_id = str(item.get("id") or "").strip() or slugify(name)
            if app_id in seen:
                base = app_id
                suffix = 2
                while f"{base}-{suffix}" in seen:
                    suffix += 1
                app_id = f"{base}-{suffix}"
            seen.add(app_id)
            try:
                apps.append(_normalize(item, app_id=app_id))
            except ValueError:
                # Skip records that cannot be normalized instead of losing the
                # whole registry; they will be rewritten on the next mutation.
                continue
        return apps

    def _write(self, apps: list[dict]) -> None:
        """Atomically replace the registry file (tmp in same dir + rename)."""
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)

        payload = json.dumps(apps, indent=2, ensure_ascii=False) + "\n"
        fd, tmp_path = tempfile.mkstemp(
            prefix=".apps-", suffix=".json.tmp", dir=directory, text=True
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, self.path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        # Best-effort directory fsync so the rename itself is durable.
        try:
            dir_fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
