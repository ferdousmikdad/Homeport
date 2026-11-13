"""backend/paths.py — where Homeport keeps its files.

* Running from source (run.sh / run.bat / launch.py): everything lives in the
  project folder, exactly as before — ``data/``, ``bin/``, ``ui/``, ``recipes/``.
* Installed app (PyInstaller bundle): the bundle is read-only, so data goes to
  the per-user application folder of each OS and ``ui/``/``recipes/`` are read
  from inside the bundle.
* ``HOMEPORT_DATA_DIR`` overrides the data folder in both cases.
"""

from __future__ import annotations

import os
import sys

__all__ = ["FROZEN", "SOURCE_ROOT", "RESOURCE_ROOT", "DATA_DIR", "BIN_DIR", "UI_DIR", "RECIPES_DIR",
           "user_data_dir"]

FROZEN = bool(getattr(sys, "frozen", False))
SOURCE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCE_ROOT = getattr(sys, "_MEIPASS", SOURCE_ROOT) if FROZEN else SOURCE_ROOT


def user_data_dir() -> str:
    """The standard per-user folder for app data on this OS."""
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Homeport")
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
        return os.path.join(base, "Homeport")
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "homeport")


DATA_DIR = os.environ.get("HOMEPORT_DATA_DIR") or (user_data_dir() if FROZEN else os.path.join(SOURCE_ROOT, "data"))
BIN_DIR = os.path.join(DATA_DIR, "bin") if FROZEN else os.path.join(SOURCE_ROOT, "bin")
UI_DIR = os.path.join(RESOURCE_ROOT, "ui")
RECIPES_DIR = os.path.join(RESOURCE_ROOT, "recipes")
