"""backend/recipes.py — community project recipes (JSON, no code needed).

A recipe teaches Homeport how to run one kind of project. Recipes are read
from ``<repo>/recipes/*.json`` (shipped, contributed via pull requests) and
``~/.homeport/recipes/*.json`` (your own), and are checked before the built-in
detectors. Format (see recipes/README.md)::

    {
      "name": "Hugo",
      "match": {
        "all": ["hugo.toml|hugo.yaml|config.toml"],   # every entry must exist; "a|b" = either
        "any": ["content", "layouts"],                 # at least one must exist (optional)
        "none": ["package.json"],                      # none may exist (optional)
        "contains": {"config.toml": "baseURL"}         # file must contain this regex (optional)
      },
      "requires": ["hugo"],                            # tools that must be installed (optional)
      "port": 1313,
      "command": "hugo server --port {port} --bind 127.0.0.1",
      "command_windows": "...",                        # optional cmd.exe variant
      "setup": [{"unless": "node_modules", "run": "npm install"}]   # optional
    }

``{port}`` is replaced by the chosen port; ``{python}`` by the project's Python.
"""

from __future__ import annotations

import glob
import json
import os
import re
import threading
import time
from typing import Callable, Optional

from . import paths

__all__ = ["load_recipes", "match_recipe", "RECIPE_DIRS"]

RECIPE_DIRS = [
    paths.RECIPES_DIR,
    os.path.join(os.path.expanduser("~"), ".homeport", "recipes"),
]

_cache: dict = {"at": 0.0, "recipes": []}
_lock = threading.Lock()


def _valid(recipe) -> bool:
    return (
        isinstance(recipe, dict)
        and isinstance(recipe.get("name"), str)
        and isinstance(recipe.get("command"), str)
        and isinstance(recipe.get("match"), dict)
        and (recipe["match"].get("all") or recipe["match"].get("any"))
    )


def load_recipes(dirs: Optional[list] = None, ttl: float = 10.0) -> list:
    """All valid recipes (cached briefly). Broken files are skipped."""
    with _lock:
        if dirs is None and time.time() - _cache["at"] < ttl:
            return _cache["recipes"]
        found = []
        for directory in dirs or RECIPE_DIRS:
            for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
                try:
                    with open(path, encoding="utf-8") as fh:
                        recipe = json.load(fh)
                except (OSError, ValueError):
                    continue
                if _valid(recipe):
                    recipe = dict(recipe)
                    recipe["_file"] = path
                    found.append(recipe)
        if dirs is None:
            _cache.update(at=time.time(), recipes=found)
        return found


def _exists(root: str, pattern: str) -> bool:
    for alt in str(pattern).split("|"):
        alt = alt.strip()
        if not alt:
            continue
        if any(ch in alt for ch in "*?["):
            if glob.glob(os.path.join(root, alt)):
                return True
        elif os.path.exists(os.path.join(root, alt)):
            return True
    return False


def _matches(root: str, match: dict) -> bool:
    if not all(_exists(root, p) for p in match.get("all") or []):
        return False
    any_list = match.get("any") or []
    if any_list and not any(_exists(root, p) for p in any_list):
        return False
    if any(_exists(root, p) for p in match.get("none") or []):
        return False
    for rel, pattern in (match.get("contains") or {}).items():
        try:
            with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as fh:
                if not re.search(pattern, fh.read(256 * 1024)):
                    return False
        except (OSError, re.error):
            return False
    return True


def match_recipe(root: str, *, windows: bool, which: Callable[[str], Optional[str]],
                 recipes: Optional[list] = None) -> Optional[dict]:
    """The first recipe that matches ``root`` (and whose tools are installed)."""
    for recipe in recipes if recipes is not None else load_recipes():
        try:
            if not _matches(root, recipe["match"]):
                continue
        except Exception:
            continue
        if any(not which(tool) for tool in recipe.get("requires") or []):
            continue
        return recipe
    return None
