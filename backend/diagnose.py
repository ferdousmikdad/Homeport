"""backend/diagnose.py — explain why an app crashed and offer one-click fixes.

Works offline with no account: known error patterns from the app's log are
turned into plain-language findings. Each finding can carry fixes; a fix is
an *action name* — the command it runs is decided here, never taken from the
browser or the log, so nothing arbitrary can be executed.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from typing import Optional

from . import osutil, shellenv

__all__ = ["diagnose", "run_fix", "FIX_LABELS"]

FIX_LABELS = {
    "install_node": "Install packages",
    "install_python": "Install Python packages",
    "install_composer": "Run composer install",
    "copy_env": "Create .env from .env.example",
    "laravel_key": "Generate app key",
    "install_bundle": "Run bundle install",
    "free_port": "Stop what's using the port",
    "edit": "Edit command…",
}

_TOOL_HELP = {
    "php": "Install PHP — e.g. Laravel Herd (free) or php.net.",
    "composer": "Install Composer from getcomposer.org.",
    "node": "Install Node.js from nodejs.org (LTS).",
    "npm": "Install Node.js from nodejs.org (npm comes with it).",
    "npx": "Install Node.js from nodejs.org (npx comes with it).",
    "pnpm": "Install pnpm: npm install -g pnpm",
    "yarn": "Install Yarn: npm install -g yarn",
    "bun": "Install Bun from bun.sh.",
    "python": "Install Python 3 from python.org.",
    "python3": "Install Python 3 from python.org.",
    "uv": "Install uv from docs.astral.sh/uv.",
    "cargo": "Install Rust from rustup.rs.",
    "go": "Install Go from go.dev.",
    "ruby": "Install Ruby from ruby-lang.org.",
    "bundle": "Install Bundler: gem install bundler",
    "dotnet": "Install the .NET SDK from dot.net.",
    "java": "Install a JDK, e.g. adoptium.net.",
    "mvn": "Install Maven from maven.apache.org.",
    "docker": "Install Docker Desktop and start it.",
    "deno": "Install Deno from deno.com.",
    "mix": "Install Elixir from elixir-lang.org.",
}

_DB_PORTS = {"5432": "PostgreSQL", "3306": "MySQL", "6379": "Redis", "27017": "MongoDB", "1433": "SQL Server"}


def _has(path: str, *names: str) -> bool:
    return any(os.path.exists(os.path.join(path, n)) for n in names)


def _finding(fid: str, title: str, detail: str, fixes: list, line: str = "") -> dict:
    return {"id": fid, "title": title, "detail": detail,
            "fixes": [{"action": a, "label": FIX_LABELS[a]} for a in fixes], "evidence": line[-300:]}


def diagnose(cfg: dict, log_lines: list, exit_code: Optional[int] = None,
             port_conflict: Optional[dict] = None) -> list:
    """Findings for a crashed/failing app, most useful first."""
    path = cfg.get("path") or ""
    # Only the latest run matters: drop everything before the last start marker.
    for i in range(len(log_lines) - 1, -1, -1):
        if log_lines[i].startswith("[manager]") and " started pid=" in log_lines[i]:
            log_lines = log_lines[i + 1:]
            break
    text = "\n".join(log_lines[-200:])
    found: dict = {}

    def add(f: dict) -> None:
        found.setdefault(f["id"], f)

    def first(pattern: str, flags=re.I) -> Optional[re.Match]:
        return re.search(pattern, text, flags | re.M)

    if port_conflict:
        add(_finding("port_in_use", f"Port {cfg.get('port') or ''} is already in use",
                     f"Another program (PID {port_conflict.get('pid')}: {port_conflict.get('command') or 'unknown'}) "
                     "is listening on this app's port.", ["free_port", "edit"]))
    m = first(r"(EADDRINUSE|address already in use|port \d+ is (already )?in use|port is already allocated|"
              r"Only one usage of each socket address|Failed to listen on .*\(reason: Address in use\))")
    if m:
        add(_finding("port_in_use", "The port is already in use",
                     "Something else is using this app's port. Stop it, or change the port in the command.",
                     ["free_port", "edit"], m.group(0)))

    m = first(r"(?:^|[\s'\"])([\w.-]+)['\"]?: (?:command )?not found|"
              r"'([\w.-]+)' is not recognized as an internal or external command|"
              r"(?:spawn|exec) ([\w.-]+) ENOENT")
    if m:
        tool = next(g for g in m.groups() if g)
        node_bins = {"vite", "next", "nuxt", "nuxi", "astro", "react-scripts", "ng", "tsx", "ts-node",
                     "nodemon", "webpack", "parcel", "remix", "svelte-kit", "gatsby", "concurrently"}
        if tool in node_bins and _has(path, "package.json"):
            add(_finding("node_modules", "Project packages aren't installed",
                         f"`{tool}` comes from the project's packages, which haven't been installed yet.",
                         ["install_node"], m.group(0)))
        else:
            help_text = _TOOL_HELP.get(tool, f"Install `{tool}` and make sure it's on your PATH.")
            add(_finding("missing_tool", f"`{tool}` isn't installed",
                         f"The start command needs `{tool}`, which wasn't found. {help_text}", ["edit"], m.group(0)))

    m = first(r"Cannot find module|ERR_MODULE_NOT_FOUND|Cannot find package|"
              r"npx canceled due to missing packages|could not determine executable to run")
    if m and _has(path, "package.json"):
        add(_finding("node_modules", "Node packages are missing",
                     "The app can't find a package it imports. Installing the project's packages usually fixes it.",
                     ["install_node"], m.group(0)))

    m = first(r"npm (?:ERR!|error) Missing script: \"?([\w:.-]+)")
    if m:
        add(_finding("missing_script", f"There is no `{m.group(1)}` script",
                     "The command runs an npm script that package.json doesn't define. "
                     "Pick one of the project's scripts in Edit.", ["edit"], m.group(0)))

    m = first(r"ModuleNotFoundError: No module named ['\"]([\w.]+)['\"]|ImportError: No module named ([\w.]+)")
    if m:
        mod = next(g for g in m.groups() if g)
        add(_finding("python_deps", f"Python package `{mod}` is missing",
                     "Install the project's requirements into its own environment (.venv).",
                     ["install_python"], m.group(0)))

    m = first(r"vendor[/\\]autoload\.php")
    if m and _has(path, "composer.json"):
        add(_finding("composer", "PHP packages aren't installed",
                     "The vendor/ folder is missing — run composer install.", ["install_composer"], m.group(0)))

    m = first(r"\.env\b.*(not found|No such file|does not exist)|file_get_contents\(.*\.env\)|"
              r"failed to load \.env|MissingEnvFile")
    if (m or (not _has(path, ".env") and _has(path, ".env.example") and _has(path, "artisan"))) \
            and _has(path, ".env.example") and not _has(path, ".env"):
        add(_finding("env_missing", "The .env settings file is missing",
                     "This project ships an .env.example template. Copy it to .env (then review the values).",
                     ["copy_env"], m.group(0) if m else ""))

    m = first(r"No application encryption key has been specified|MissingAppKeyException")
    if m:
        add(_finding("laravel_key", "Laravel app key is not set",
                     "Generate one with php artisan key:generate.", ["laravel_key"], m.group(0)))

    m = first(r"Could not find gem|Bundler::GemNotFound|run `bundle install`")
    if m:
        add(_finding("bundle", "Ruby gems aren't installed", "Run bundle install.", ["install_bundle"], m.group(0)))

    m = first(r"(ECONNREFUSED|Connection refused).{0,40}?(?:127\.0\.0\.1|localhost|::1)?:(5432|3306|6379|27017|1433)|"
              r"SQLSTATE\[HY000\] \[2002\]|could not connect to server: Connection refused")
    if m:
        port = next((g for g in m.groups()[1:] if g), None) if m.groups() else None
        db = _DB_PORTS.get(port or "", "The database")
        f = _finding("database_down", f"{db} isn't running",
                     f"The app couldn't connect to {db.lower() if db != 'The database' else 'its database'}. "
                     "Start it — or add it to Homeport as a service in one click.", [], m.group(0))
        kind = {"5432": "postgres", "3306": "mysql", "6379": "redis", "27017": "mongodb"}.get(port or "")
        if kind is None and "SQLSTATE" in m.group(0):
            kind = "mysql"
        if kind:
            name = {"postgres": "PostgreSQL", "mysql": "MySQL", "redis": "Redis", "mongodb": "MongoDB"}[kind]
            f["fixes"].append({"action": "service:" + kind, "label": f"Add {name} service"})
        add(f)

    m = first(r"Permission denied|EACCES")
    if m:
        add(_finding("permission", "Permission denied",
                     "The app tried to use a file or port it isn't allowed to. Ports below 1024 need admin rights; "
                     "otherwise check the file permissions.", ["edit"], m.group(0)))

    if exit_code in (137, -9) and not found:
        add(_finding("killed", "The app was killed (out of memory?)",
                     "Exit code 137 usually means the system stopped it for using too much memory.", []))

    if not found:
        last_error = ""
        for line in reversed(log_lines[-80:]):
            if re.search(r"error|exception|traceback|fatal|failed", line, re.I) and not line.startswith("[manager]"):
                last_error = line.strip()
                break
        add(_finding("unknown", "No known cause found",
                     "Homeport didn't recognise this error. The last error line is shown below"
                     " — the app's logs have the full story.", [], last_error))
    return list(found.values())


# ---------------------------------------------------------------------------
# fixes
# ---------------------------------------------------------------------------
def _node_install(path: str) -> str:
    if _has(path, "pnpm-lock.yaml"):
        return "pnpm install"
    if _has(path, "yarn.lock"):
        return "yarn install"
    if _has(path, "bun.lockb", "bun.lock"):
        return "bun install"
    return "npm install"


def _python_install(path: str) -> str:
    if _has(path, "uv.lock") and shellenv.which("uv"):
        return "uv sync"
    for venv in (".venv", "venv", "env"):
        py = osutil.venv_python(os.path.join(path, venv))
        if os.path.isfile(py):
            target = "-r requirements.txt" if _has(path, "requirements.txt") else "-e ."
            return f'"{py}" -m pip install {target}'
    base = "python" if osutil.IS_WINDOWS else "python3"
    py = osutil.venv_python(".venv")
    target = "-r requirements.txt" if _has(path, "requirements.txt") else "-e ."
    return f'{base} -m venv .venv && "{py}" -m pip install {target}'


def _command_for(action: str, path: str) -> Optional[str]:
    return {
        "install_node": lambda: _node_install(path),
        "install_python": lambda: _python_install(path),
        "install_composer": lambda: "composer install",
        "laravel_key": lambda: "php artisan key:generate",
        "install_bundle": lambda: "bundle install",
    }.get(action, lambda: None)()


def run_fix(cfg: dict, action: str, log=None, timeout: float = 900) -> dict:
    """Run one predefined fix in the app's folder. ``log(line)`` gets output."""
    path = cfg.get("path") or ""
    if not os.path.isdir(path):
        raise ValueError("the app's folder doesn't exist")
    if action == "copy_env":
        src, dst = os.path.join(path, ".env.example"), os.path.join(path, ".env")
        if not os.path.isfile(src):
            raise ValueError("there is no .env.example to copy")
        if os.path.exists(dst):
            return {"ok": True, "output": ".env already exists — left unchanged."}
        shutil.copyfile(src, dst)
        return {"ok": True, "output": "Created .env from .env.example."}

    command = _command_for(action, path)
    if command is None:
        raise ValueError(f"unknown fix: {action}")
    if log:
        log(f"[homeport] fix: {command}")
    env = {**os.environ, "PATH": shellenv.user_path()}
    try:
        res = subprocess.run(command, shell=True, cwd=path, env=env, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=timeout,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if osutil.IS_WINDOWS else 0)
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": f"{command} timed out after {int(timeout)}s"}
    output = (res.stdout + res.stderr).strip()
    if log:
        for line in output.splitlines()[-200:]:
            log(line)
        log(f"[homeport] fix finished with exit code {res.returncode}")
    return {"ok": res.returncode == 0, "output": output[-4000:], "command": command}
