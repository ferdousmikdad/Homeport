"""backend/shellenv.py — the PATH a user's own terminal would have.

When the manager is started from the .app bundle or a LaunchAgent it inherits
macOS's minimal PATH (/usr/bin:/bin:…), so tools installed through Homebrew,
Herd (php/composer), nvm, pnpm, cargo, uv … are "command not found".
``user_path()`` asks the user's login shell for its PATH once (cached) and
adds well-known tool folders that exist, so every kind of project can run.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import threading
from typing import Optional

__all__ = ["user_path", "which"]

_HOME = os.path.expanduser("~")

# Folders commonly holding dev tools; only the ones that exist are added.
_KNOWN_DIRS = (
    "/opt/homebrew/bin",
    "/opt/homebrew/sbin",
    "/usr/local/bin",
    "~/.local/bin",
    "~/.config/herd-lite/bin",
    "~/Library/Application Support/Herd/bin",
    "~/.composer/vendor/bin",
    "~/.config/composer/vendor/bin",
    "~/Library/pnpm",
    "~/.bun/bin",
    "~/.deno/bin",
    "~/.volta/bin",
    "~/.cargo/bin",
    "~/go/bin",
    "/usr/local/go/bin",
    "~/.dotnet/tools",
    "/usr/local/share/dotnet",
    "~/.rbenv/shims",
    "~/.pyenv/shims",
    "/Applications/Docker.app/Contents/Resources/bin",
    # Linux
    "/home/linuxbrew/.linuxbrew/bin",
    "~/.linuxbrew/bin",
    "/snap/bin",
    "~/.npm-global/bin",
    "~/.nix-profile/bin",
)


def _windows_dirs() -> list:
    """Common Windows tool folders (npm, Python launcher, Scoop, Cargo, Herd …)."""
    env = os.environ.get
    home = os.path.expanduser("~")
    appdata, local = env("APPDATA", ""), env("LOCALAPPDATA", "")
    dirs = [
        os.path.join(appdata, "npm"),
        os.path.join(home, "scoop", "shims"),
        os.path.join(home, ".cargo", "bin"),
        os.path.join(home, ".bun", "bin"),
        os.path.join(home, ".deno", "bin"),
        os.path.join(home, ".local", "bin"),
        os.path.join(home, ".config", "herd", "bin"),
        os.path.join(home, ".config", "herd-lite", "bin"),
        os.path.join(home, "go", "bin"),
        os.path.join(local, "Microsoft", "WindowsApps"),
        os.path.join(env("ProgramFiles", r"C:\Program Files"), "nodejs"),
        os.path.join(env("ProgramFiles", r"C:\Program Files"), "Docker", "Docker", "resources", "bin"),
        os.path.join(env("ProgramFiles", r"C:\Program Files"), "dotnet"),
        os.path.join(env("ProgramFiles", r"C:\Program Files"), "Git", "cmd"),
    ]
    dirs += sorted(glob.glob(os.path.join(local, "Programs", "Python", "Python3*")), reverse=True)[:1]
    dirs += sorted(glob.glob(os.path.join(local, "Programs", "Python", "Python3*", "Scripts")), reverse=True)[:1]
    return dirs

_MARK = "__LHM_PATH__"
_lock = threading.Lock()
_cached: Optional[str] = None


def _login_shell_path() -> list:
    if os.name == "nt":
        return []  # Windows passes the full user PATH to every process already
    shell = os.environ.get("SHELL") or ("/bin/zsh" if sys.platform == "darwin" else "/bin/bash")
    if not os.path.isfile(shell):
        return []
    try:
        res = subprocess.run(
            [shell, "-ilc", f'printf "{_MARK}%s{_MARK}" "$PATH"'],
            capture_output=True, text=True, timeout=8, stdin=subprocess.DEVNULL,
            cwd=_HOME,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    out = res.stdout or ""
    start = out.find(_MARK)
    end = out.find(_MARK, start + len(_MARK)) if start >= 0 else -1
    if start < 0 or end < 0:
        return []
    return [p for p in out[start + len(_MARK):end].split(os.pathsep) if p]


def _database_dirs() -> list:
    """Database servers that install outside the PATH (Postgres.app,
    keg-only Homebrew formulae, Windows Program Files)."""
    patterns = [
        "/Applications/Postgres.app/Contents/Versions/latest/bin",
        "/opt/homebrew/opt/postgresql@*/bin", "/usr/local/opt/postgresql@*/bin",
        "/opt/homebrew/opt/mysql*/bin", "/usr/local/opt/mysql*/bin",
        "/opt/homebrew/opt/mariadb*/bin", "/usr/local/opt/mariadb*/bin",
        "/opt/homebrew/opt/mongodb-community*/bin", "/usr/local/opt/mongodb-community*/bin",
        "/usr/lib/postgresql/*/bin",
    ]
    if os.name == "nt":
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        patterns = [
            os.path.join(pf, "PostgreSQL", "*", "bin"),
            os.path.join(pf, "MySQL", "MySQL Server *", "bin"),
            os.path.join(pf, "MariaDB *", "bin"),
            os.path.join(pf, "MongoDB", "Server", "*", "bin"),
            os.path.join(pf, "Redis"),
        ]
    found = []
    for pattern in patterns:
        found += sorted(glob.glob(pattern), reverse=True)  # newest version first
    return found


def _nvm_dirs() -> list:
    """Newest nvm-installed node, for shells where nvm loads lazily."""
    versions = glob.glob(os.path.join(_HOME, ".nvm", "versions", "node", "v*", "bin"))

    def key(p: str):
        try:
            return tuple(int(x) for x in p.split(os.sep)[-2].lstrip("v").split("."))
        except ValueError:
            return (0,)

    return sorted(versions, key=key, reverse=True)[:1]


def user_path() -> str:
    """Login-shell PATH + current PATH + known tool dirs (deduplicated)."""
    global _cached
    with _lock:
        if _cached is None:
            parts = _login_shell_path()
            parts += (os.environ.get("PATH") or "").split(os.pathsep)
            parts += _database_dirs()
            if os.name == "nt":
                parts += _windows_dirs()
            else:
                parts += _nvm_dirs()
                parts += [os.path.expanduser(d) for d in _KNOWN_DIRS]
            seen = set()
            cleaned = []
            for part in parts:
                key = os.path.normcase(part)
                if part and key not in seen and os.path.isdir(part):
                    seen.add(key)
                    cleaned.append(part)
            _cached = os.pathsep.join(cleaned)
        return _cached


def which(tool: str) -> Optional[str]:
    return shutil.which(tool, path=user_path())
