"""backend/detect.py — figure out how to run a project folder.

``detect(path)`` looks at the files in a project directory and returns
``{"command": str|None, "port": int|None, "type": str|None}``:

* ``command`` is a shell command run with cwd = the project folder.  When the
  project's dependencies are missing (no ``vendor/``, ``node_modules/``,
  virtualenv, ``.env`` …) the command is prefixed with a guarded install step,
  so a fresh clone runs on the first click.
* ``port`` is the port the app will listen on.  For frameworks whose port is
  set on the command line (Laravel, Django, Vite, Next, PHP's built-in
  server …) the port is written into the command, and with
  ``pick_free_port=True`` a port that is busy or in ``avoid_ports`` is skipped.
* ``type`` is a human label such as "Laravel", "Vite", "Django".

Detectors run in priority order; the first that matches wins.  Framework
markers (``artisan``, ``manage.py`` …) beat generic ones (``package.json``,
``index.html``) because a Laravel or Django project usually also has a
``package.json`` for its front-end assets.
"""

from __future__ import annotations

import glob
import json
import os
import re
import shlex
import socket
from typing import Callable, Iterable, Optional

from . import osutil, recipes, shellenv

__all__ = ["detect", "detect_file", "FILE_TYPES"]


# ---------------------------------------------------------------------------
# context shared by the detectors
# ---------------------------------------------------------------------------
class _Ctx:
    def __init__(self, path: str, names: set, scanned_port: Optional[int],
                 pick_free_port: bool, avoid_ports: set):
        self.path = path
        self.names = names
        self.scanned_port = scanned_port
        self.pick_free_port = pick_free_port
        self.avoid_ports = avoid_ports

    # files -------------------------------------------------------------
    def has(self, *rel: str) -> bool:
        return any(os.path.exists(os.path.join(self.path, r)) for r in rel)

    def isfile(self, rel: str) -> bool:
        return os.path.isfile(os.path.join(self.path, rel))

    def isdir(self, rel: str) -> bool:
        return os.path.isdir(os.path.join(self.path, rel))

    def read(self, rel: str, limit: int = 256 * 1024) -> str:
        try:
            with open(os.path.join(self.path, rel), encoding="utf-8", errors="replace") as fh:
                return fh.read(limit)
        except OSError:
            return ""

    def json(self, rel: str) -> dict:
        try:
            data = json.loads(self.read(rel, 2 * 1024 * 1024))
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    # ports -------------------------------------------------------------
    def port(self, default: Optional[int]) -> Optional[int]:
        """The port to put into a command: the one the project documents,
        else the framework default; bumped to a free one when asked."""
        preferred = self.scanned_port or default
        if preferred is None or not self.pick_free_port:
            return preferred
        return _free_port(preferred, self.avoid_ports)


def _port_busy(port: int) -> bool:
    for host in ("127.0.0.1", "::1"):
        family = socket.AF_INET6 if ":" in host else socket.AF_INET
        try:
            with socket.socket(family, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.2)
                if sock.connect_ex((host, port)) == 0:
                    return True
        except OSError:
            continue
    return False


def _free_port(preferred: int, avoid: set) -> int:
    port = preferred
    for _ in range(200):
        if port not in avoid and not _port_busy(port):
            return port
        port += 1
    return preferred


# Generated commands run in /bin/sh on macOS/Linux and cmd.exe on Windows.
# Tests flip this to check the Windows forms on any machine.
WINDOWS = osutil.IS_WINDOWS


def _q(value: str) -> str:
    if WINDOWS:
        return f'"{value}"' if any(c in value for c in ' &()^%!,;=') else value
    return shlex.quote(value)


def _env(var: str, value, command: str) -> str:
    """Run ``command`` with one extra environment variable."""
    if WINDOWS:
        return f"set {var}={value}&& {command}"  # no space before && (cmd keeps it)
    return f"{var}={value} {command}"


def _py() -> str:
    return "python" if WINDOWS else "python3"


def _venv_py(venv: str) -> str:
    return f"{venv}\\Scripts\\python.exe" if WINDOWS else f"{venv}/bin/python"


def _copy(src: str, dst: str) -> str:
    return f"copy /Y {src} {dst}" if WINDOWS else f"cp {src} {dst}"


def _wrapper(name: str, ctx: "_Ctx", fallback: str) -> str:
    """Project wrapper script (mvnw / gradlew) in the right form, else the tool."""
    if WINDOWS:
        for ext in (".cmd", ".bat"):
            if ctx.isfile(name + ext):
                return name + ext
        return fallback
    return f"./{name}" if ctx.isfile(name) else fallback


def _with_setup(steps: Iterable[str], command: str) -> str:
    """Prefix ``command`` with setup steps that must succeed first."""
    steps = [s for s in steps if s]
    if not steps:
        return command
    return " && ".join(list(steps) + [command])


def _result(kind: str, command: str, port: Optional[int]) -> dict:
    return {"command": command, "port": port, "type": kind}


# ---------------------------------------------------------------------------
# PHP
# ---------------------------------------------------------------------------
def _composer_setup(ctx: _Ctx) -> Optional[str]:
    if ctx.isfile("composer.json") and not ctx.isdir("vendor"):
        return "composer install"
    return None


def _laravel(ctx: _Ctx) -> Optional[dict]:
    if not ctx.isfile("artisan"):
        return None
    steps = [_composer_setup(ctx)]
    if not ctx.isfile(".env") and ctx.isfile(".env.example"):
        steps.append(_copy(".env.example", ".env") + " && php artisan key:generate")
    # Vite-based Laravel needs built assets (public/build) or the page errors.
    has_vite = any(ctx.isfile(f) for f in ("vite.config.js", "vite.config.ts", "vite.config.mjs"))
    if has_vite and ctx.isfile("package.json") and not ctx.isfile("public/build/manifest.json") \
            and not ctx.isfile("public/hot"):
        pm = _node_pm(ctx)
        steps.append(f"{pm} install && {_pm_run(pm, 'build')}")
    port = ctx.port(8000)
    return _result("Laravel", _with_setup(steps, f"php artisan serve --host=127.0.0.1 --port={port}"), port)


def _symfony(ctx: _Ctx) -> Optional[dict]:
    if not (ctx.isfile("bin/console") and ctx.isfile("composer.json")):
        return None
    port = ctx.port(8000)
    steps = [_composer_setup(ctx)]
    if shellenv.which("symfony"):
        cmd = f"symfony server:start --no-tls --port={port}"
    else:
        docroot = "public" if ctx.isdir("public") else "."
        cmd = f"php -S 127.0.0.1:{port} -t {docroot}"
    return _result("Symfony", _with_setup(steps, cmd), port)


def _plain_php(ctx: _Ctx) -> Optional[dict]:
    if ctx.isfile("public/index.php"):
        docroot = "public"
    elif ctx.isfile("index.php"):
        docroot = "."
    else:
        return None
    port = ctx.port(8000)
    kind = "WordPress" if ctx.isfile("wp-config.php") or ctx.isfile("wp-config-sample.php") else "PHP"
    cmd = f"php -S 127.0.0.1:{port} -t {docroot}"
    return _result(kind, _with_setup([_composer_setup(ctx)], cmd), port)


# ---------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------
_VENV_DIRS = (".venv", "venv", "env", ".qa")

# Ordered by foreground preference; launch.py often detaches, so it is last.
_ENTRY_FILES = ("run.py", "server.py", "panel.py", "app.py", "main.py", "launch.py")

# Sub-folders where an ASGI/WSGI app object commonly lives.
_PY_SUBDIRS = ("app", "backend", "api", "server", "src")


def _python(ctx: _Ctx) -> tuple:
    """(interpreter prefix, setup steps).  Prefers the project's own venv."""
    for venv in _VENV_DIRS:
        full = osutil.venv_python(os.path.join(ctx.path, venv), WINDOWS)
        if os.path.isfile(full) and (WINDOWS or os.access(full, os.X_OK)):
            return _venv_py(venv), []
    if ctx.isfile("uv.lock") and shellenv.which("uv"):
        return "uv run python", []
    if ctx.isfile("poetry.lock") and shellenv.which("poetry"):
        return "poetry run python", []
    if ctx.isfile("pyproject.toml") and shellenv.which("uv"):
        return "uv run python", []
    if ctx.isfile("requirements.txt"):
        setup = f"{_py()} -m venv .venv && {_venv_py('.venv')} -m pip install -r requirements.txt"
        return _venv_py(".venv"), [setup]
    return _py(), []


_FASTAPI_RE = re.compile(r"^(\w+)\s*(?::[^=]+)?=\s*(?:fastapi\.)?FastAPI\(", re.MULTILINE)
_STARLETTE_RE = re.compile(r"^(\w+)\s*(?::[^=]+)?=\s*Starlette\(", re.MULTILINE)
_FLASK_RE = re.compile(r"^(\w+)\s*(?::[^=]+)?=\s*(?:flask\.)?Flask\(", re.MULTILINE)
_MAIN_GUARD = re.compile(r"""if\s+__name__\s*==\s*['"]__main__['"]""")


def _module_name(rel_file: str) -> str:
    return rel_file[:-3].replace("/", ".")


def _python_web_app(ctx: _Ctx, rel_file: str, py: str) -> Optional[dict]:
    """Framework-aware command for one python file, or None."""
    text = ctx.read(rel_file)
    if not text:
        return None
    runs_itself = bool(_MAIN_GUARD.search(text)) and (
        "uvicorn.run" in text or ".run(" in text or "serve(" in text
    )

    if re.search(r"^\s*(import streamlit|from streamlit)", text, re.MULTILINE):
        port = ctx.port(8501)
        return _result(
            "Streamlit",
            f"{py} -m streamlit run {_q(rel_file)} --server.port {port} --server.headless true",
            port,
        )
    if runs_itself:
        return None
    for regex, kind in ((_FASTAPI_RE, "FastAPI"), (_STARLETTE_RE, "Starlette")):
        match = regex.search(text)
        if match:
            port = ctx.port(8000)
            target = f"{_module_name(rel_file)}:{match.group(1)}"
            return _result(kind, f"{py} -m uvicorn {target} --host 127.0.0.1 --port {port} --reload", port)
    match = _FLASK_RE.search(text)
    if match:
        port = ctx.port(5000)
        target = f"{_module_name(rel_file)}:{match.group(1)}"
        return _result("Flask", f"{py} -m flask --app {target} run --port {port} --debug", port)
    return None


def _django(ctx: _Ctx) -> Optional[dict]:
    if not ctx.isfile("manage.py"):
        return None
    py, setup = _python(ctx)
    port = ctx.port(8000)
    return _result("Django", _with_setup(setup, f"{py} manage.py runserver 127.0.0.1:{port}"), port)


def _python_entry(ctx: _Ctx) -> Optional[dict]:
    chosen = next((f for f in _ENTRY_FILES if ctx.isfile(f)), None)
    if chosen is None:
        return None
    py, setup = _python(ctx)

    web = _python_web_app(ctx, chosen, py)
    if web is not None:
        web["command"] = _with_setup(setup, web["command"])
        return web

    content = ctx.read(chosen, 64 * 1024)
    parts = [py, chosen]
    if "--no-open" in content:
        parts.append("--no-open")
    port = ctx.scanned_port
    if port is not None and ("--port" in content or 'add_argument("-p"' in content):
        port = ctx.port(port)
        parts.extend(["--port", str(port)])
    return _result("Python", _with_setup(setup, " ".join(parts)), port)


def _python_package(ctx: _Ctx) -> Optional[dict]:
    """A FastAPI/Flask app inside a sub-package, e.g. backend/main.py."""
    if not (ctx.has("pyproject.toml", "requirements.txt", "uv.lock", "Pipfile")
            or any(ctx.isdir(v) for v in _VENV_DIRS)):
        return None
    py, setup = _python(ctx)
    for sub in _PY_SUBDIRS:
        for name in ("main.py", "app.py", "server.py", "api.py", "asgi.py"):
            rel = f"{sub}/{name}"
            if ctx.isfile(rel):
                web = _python_web_app(ctx, rel, py)
                if web is not None:
                    web["command"] = _with_setup(setup, web["command"])
                    return web
    return None


# ---------------------------------------------------------------------------
# JavaScript / TypeScript
# ---------------------------------------------------------------------------
def _node_pm(ctx: _Ctx) -> str:
    """The package manager the project uses, by lockfile."""
    pkg = ctx.json("package.json")
    declared = str(pkg.get("packageManager") or "").split("@")[0]
    if declared in ("pnpm", "yarn", "bun", "npm"):
        return declared
    if ctx.isfile("pnpm-lock.yaml"):
        return "pnpm"
    if ctx.isfile("yarn.lock"):
        return "yarn"
    if ctx.isfile("bun.lockb") or ctx.isfile("bun.lock"):
        return "bun"
    return "npm"


def _pm_run(pm: str, script: str, args: str = "") -> str:
    if pm == "npm":
        base = f"npm run {script}"
        return f"{base} -- {args}" if args else base
    base = f"{pm} run {script}"
    return f"{base} {args}" if args else base


# (pattern in the script body, label, default port, how the port is passed)
#   "flag:<fmt>" -> extra CLI args, "env" -> PORT=<n> prefix, None -> not set
_NODE_TOOLS = (
    (r"\bnext\s+dev\b", "Next.js", 3000, "flag:-p {port}"),
    (r"\bnux[ti]\s+dev\b", "Nuxt", 3000, "flag:--port {port}"),
    (r"\bastro\s+dev\b", "Astro", 4321, "flag:--port {port}"),
    (r"\bng\s+serve\b", "Angular", 4200, "flag:--port {port}"),
    (r"\breact-scripts\s+start\b", "Create React App", 3000, "env"),
    (r"\bremix\s+vite:dev\b", "Remix", 5173, "flag:--port {port} --strictPort"),
    (r"\bremix\s+dev\b", "Remix", 3000, "env"),
    (r"\bvue-cli-service\s+serve\b", "Vue CLI", 8080, "flag:--port {port}"),
    (r"\bgatsby\s+develop\b", "Gatsby", 8000, "flag:-p {port}"),
    (r"\bsvelte-kit\s+dev\b", "SvelteKit", 5173, "flag:--port {port}"),
    (r"\bshopify\s+app\s+dev\b", "Shopify app", None, None),
    (r"\belectron\b", "Electron", None, None),
    (r"\bexpo\s+start\b", "Expo", 8081, "flag:--port {port}"),
    (r"\bwebpack(?:-dev-server|\s+serve)\b", "Webpack", 8080, "flag:--port {port}"),
    (r"\bparcel\b(?!\s+build)", "Parcel", 1234, "flag:--port {port}"),
    (r"\bvite\b(?!\s+build)", "Vite", 5173, "flag:--port {port} --strictPort"),
    (r"\b(?:nodemon|node|tsx|ts-node|bun)\b", "Node.js", 3000, "env"),
)

_SCRIPT_ORDER = ("dev", "start", "serve", "develop", "start:dev", "dev:server", "preview")


def _resolve_script(scripts: dict, name: str, depth: int = 0) -> str:
    """Follow ``npm run x`` indirections so we see the real tool."""
    body = str(scripts.get(name) or "")
    match = re.match(r"^\s*(?:npm run|pnpm(?: run)?|yarn(?: run)?|bun run)\s+([\w:.-]+)\s*$", body)
    if match and depth < 3 and match.group(1) in scripts:
        return _resolve_script(scripts, match.group(1), depth + 1)
    return body


def _node(ctx: _Ctx) -> Optional[dict]:
    if not ctx.isfile("package.json"):
        return None
    pkg = ctx.json("package.json")
    scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
    pm = _node_pm(ctx)
    setup = [] if ctx.isdir("node_modules") else [f"{pm} install"]

    script = next((s for s in _SCRIPT_ORDER if isinstance(scripts.get(s), str)), None)
    if script is None:
        main = pkg.get("main") if isinstance(pkg.get("main"), str) else None
        for candidate in [main, "server.js", "index.js", "app.js", "server.mjs", "index.mjs"]:
            if candidate and ctx.isfile(candidate):
                port = ctx.port(ctx.scanned_port)
                cmd = f"node {_q(candidate)}"
                if port is not None:
                    cmd = _env("PORT", port, cmd)
                return _result("Node.js", _with_setup(setup, cmd), port)
        return None

    body = _resolve_script(scripts, script)
    for pattern, label, default_port, how in _NODE_TOOLS:
        if re.search(pattern, body):
            break
    else:
        label, default_port, how = "Node.js", None, None

    if how is None:
        port = ctx.scanned_port
        cmd = _pm_run(pm, script)
    else:
        port = ctx.port(default_port)
        if how == "env":
            cmd = _env("PORT", port, _pm_run(pm, script))
        else:
            cmd = _pm_run(pm, script, how[len("flag:"):].format(port=port))
    return _result(label, _with_setup(setup, cmd), port)


def _deno(ctx: _Ctx) -> Optional[dict]:
    for name in ("deno.json", "deno.jsonc"):
        if ctx.isfile(name):
            tasks = ctx.json(name).get("tasks") or {}
            for task in ("dev", "start", "serve"):
                if task in tasks:
                    return _result("Deno", f"deno task {task}", ctx.scanned_port)
            for entry in ("main.ts", "server.ts", "mod.ts"):
                if ctx.isfile(entry):
                    return _result("Deno", f"deno run -A {entry}", ctx.scanned_port)
    return None


# ---------------------------------------------------------------------------
# other languages / tools
# ---------------------------------------------------------------------------
def _rails(ctx: _Ctx) -> Optional[dict]:
    if not ctx.isfile("bin/rails"):
        return None
    port = ctx.port(3000)
    rails = "ruby bin/rails" if WINDOWS else "bin/rails"
    return _result("Rails", f"(bundle check || bundle install) && {rails} server -b 127.0.0.1 -p {port}", port)


def _rack(ctx: _Ctx) -> Optional[dict]:
    if not (ctx.isfile("config.ru") and ctx.isfile("Gemfile")):
        return None
    port = ctx.port(9292)
    return _result("Ruby (Rack)", f"(bundle check || bundle install) && bundle exec rackup -p {port}", port)


def _go(ctx: _Ctx) -> Optional[dict]:
    if not ctx.isfile("go.mod"):
        return None
    target = "."
    if not glob.glob(os.path.join(ctx.path, "*.go")):
        mains = sorted(glob.glob(os.path.join(ctx.path, "cmd", "*", "main.go")))
        if mains:
            target = "./" + os.path.relpath(os.path.dirname(mains[0]), ctx.path)
    return _result("Go", f"go run {target}", ctx.scanned_port)


def _rust(ctx: _Ctx) -> Optional[dict]:
    if not ctx.isfile("Cargo.toml"):
        return None
    return _result("Rust", "cargo run", ctx.scanned_port)


def _java(ctx: _Ctx) -> Optional[dict]:
    if ctx.isfile("pom.xml"):
        mvn = _wrapper("mvnw", ctx, "mvn")
        if "spring-boot" in ctx.read("pom.xml"):
            port = ctx.port(8080)
            return _result("Spring Boot", _env("SERVER_PORT", port, f"{mvn} spring-boot:run"), port)
        return _result("Java (Maven)", f"{mvn} compile exec:java", ctx.scanned_port)
    for build in ("build.gradle", "build.gradle.kts"):
        if ctx.isfile(build):
            gradle = _wrapper("gradlew", ctx, "gradle")
            if "springframework.boot" in ctx.read(build):
                port = ctx.port(8080)
                return _result("Spring Boot", _env("SERVER_PORT", port, f"{gradle} bootRun"), port)
            return _result("Java (Gradle)", f"{gradle} run", ctx.scanned_port)
    return None


def _dotnet(ctx: _Ctx) -> Optional[dict]:
    if not any(n.endswith((".csproj", ".fsproj")) for n in ctx.names):
        return None
    port = ctx.port(5000)
    return _result(".NET", f"dotnet run --urls http://127.0.0.1:{port}", port)


_COMPOSE_FILES = ("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml")
_COMPOSE_PORT = re.compile(r"""^\s*-\s*["']?(?:[\d.]+:)?(\d{2,5}):\d{2,5}""", re.MULTILINE)


def _docker_compose(ctx: _Ctx) -> Optional[dict]:
    for name in _COMPOSE_FILES:
        if ctx.isfile(name):
            match = _COMPOSE_PORT.search(ctx.read(name))
            port = int(match.group(1)) if match else ctx.scanned_port
            return _result("Docker Compose", "docker compose up --build", port)
    return None


def _makefile(ctx: _Ctx) -> Optional[dict]:
    if not ctx.isfile("Makefile"):
        return None
    text = ctx.read("Makefile")
    for target in ("dev", "run", "serve", "start", "up"):
        if re.search(rf"^{target}\s*:", text, re.MULTILINE):
            return _result("Makefile", f"make {target}", ctx.scanned_port)
    return None


def _shell_launcher(ctx: _Ctx) -> Optional[dict]:
    if WINDOWS:
        for name in ("start.bat", "run.bat", "dev.bat", "serve.bat", "start.cmd", "run.cmd", "dev.cmd"):
            if ctx.isfile(name):
                return _result("Batch script", f"call {_q(name)}", ctx.scanned_port)
        for name in ("start.ps1", "run.ps1", "dev.ps1"):
            if ctx.isfile(name):
                return _result("PowerShell script",
                               f"powershell -NoProfile -ExecutionPolicy Bypass -File {_q(name)}", ctx.scanned_port)
        if not shellenv.which("bash"):  # Git Bash / WSL can still run .sh launchers
            return None
    command_files = sorted(n for n in ctx.names if n.endswith(".command") and ctx.isfile(n))
    if command_files:
        return _result("Shell script", f"bash '{command_files[0]}'", ctx.scanned_port)
    for name in ("start.sh", "run.sh", "dev.sh", "serve.sh", "bin/dev", "bin/start"):
        if ctx.isfile(name):
            return _result("Shell script", f"bash {_q(name)}", ctx.scanned_port)
    return None


def _procfile(ctx: _Ctx) -> Optional[dict]:
    for name in ("Procfile.dev", "Procfile"):
        if ctx.isfile(name):
            match = re.search(r"^web:\s*(.+)$", ctx.read(name), re.MULTILINE)
            if match:
                port = ctx.port(5000)
                cmd = match.group(1).strip().replace("${PORT}", str(port)).replace("$PORT", str(port))
                return _result("Procfile", _env("PORT", port, cmd), port)
    return None


def _static(ctx: _Ctx) -> Optional[dict]:
    for docroot in (".", "public", "dist", "docs", "site"):
        if ctx.isfile(os.path.join(docroot, "index.html")):
            port = ctx.port(8080)
            cmd = f"{_py()} -m http.server {port} --bind 127.0.0.1"
            if docroot != ".":
                cmd += f" --directory {docroot}"
            return _result("Static site", cmd, port)
    # a folder of loose .html pages (no index.html): serve the directory
    if any(n.lower().endswith((".html", ".htm")) for n in ctx.names):
        port = ctx.port(8080)
        return _result("Static site", f"{_py()} -m http.server {port} --bind 127.0.0.1", port)
    return None


def _recipe(ctx: _Ctx) -> Optional[dict]:
    """Community recipe (recipes/*.json, ~/.homeport/recipes/*.json)."""
    recipe = recipes.match_recipe(ctx.path, windows=WINDOWS, which=shellenv.which)
    if recipe is None:
        return None
    port = ctx.port(recipe.get("port")) if recipe.get("port") else ctx.scanned_port
    template = (recipe.get("command_windows") if WINDOWS else None) or recipe["command"]
    command = template.replace("{port}", str(port or "")).replace("{python}", _python(ctx)[0])
    steps = []
    for step in recipe.get("setup") or []:
        if isinstance(step, dict) and step.get("run") and not ctx.has(*(str(step.get("unless") or "").split("|") if step.get("unless") else [])):
            steps.append(str(step["run"]))
    return _result(str(recipe["name"]), _with_setup(steps, command), port)


_DETECTORS: tuple = (
    _recipe,
    _laravel,
    _symfony,
    _django,
    _rails,
    _python_entry,
    _node,
    _deno,
    _python_package,
    _plain_php,
    _go,
    _rust,
    _java,
    _dotnet,
    _rack,
    _docker_compose,
    _makefile,
    _shell_launcher,
    _procfile,
    _static,
)


# Sub-folders a project often lives in, tried (in this order) when nothing
# runnable sits at the top level — e.g. repo/app (Laravel), repo/frontend.
_PREFERRED_SUBDIRS = ("app", "web", "frontend", "client", "server", "backend",
                      "api", "site", "www", "website", "src")
_SKIP_SUBDIRS = {"node_modules", "vendor", "dist", "build", "target", "out",
                 "storage", "public", "docs", "tests", "test", "venv", "env"}


def _run_detectors(ctx: _Ctx, detectors: tuple) -> Optional[dict]:
    for detector in detectors:
        try:
            found = detector(ctx)
        except Exception:  # a weird file must never break detection
            found = None
        if found:
            return found
    return None


def _make_ctx(path: str, scanned_port, pick_free_port, avoid_ports) -> Optional[_Ctx]:
    try:
        names = set(os.listdir(path))
    except OSError:
        return None
    return _Ctx(path, names, scanned_port, pick_free_port, set(avoid_ports or ()))


def detect(path: str, scanned_port: Optional[int] = None, *,
           pick_free_port: bool = False, avoid_ports: Iterable[int] = (),
           subfolders: bool = True) -> dict:
    """See module docstring.  ``scanned_port`` is a port the README/source
    mentions (from ``monitor._detect_port``)."""
    ctx = _make_ctx(path, scanned_port, pick_free_port, avoid_ports)
    if ctx is None:
        return {"command": None, "port": None, "type": None}

    found = _run_detectors(ctx, _DETECTORS)
    if found or not subfolders:
        return found or {"command": None, "port": scanned_port, "type": None}

    # Nothing at the top level: look one folder down (repo/app, repo/web …),
    # skipping static-only matches there so a docs/ folder doesn't win.
    subdirs = sorted(
        (n for n in ctx.names
         if not n.startswith(".") and n not in _SKIP_SUBDIRS and ctx.isdir(n)),
        key=lambda n: (_PREFERRED_SUBDIRS.index(n) if n in _PREFERRED_SUBDIRS
                       else len(_PREFERRED_SUBDIRS), n.lower()),
    )
    for sub in subdirs[:12]:
        sub_ctx = _make_ctx(os.path.join(path, sub), scanned_port, pick_free_port, avoid_ports)
        if sub_ctx is None:
            continue
        found = _run_detectors(sub_ctx, _DETECTORS[:-1])
        if found:
            found["command"] = f"cd {_q(sub)} && {found['command']}"
            found["type"] = f"{found['type']} (in {sub}/)"
            return found
    return {"command": None, "port": scanned_port, "type": None}


# ---------------------------------------------------------------------------
# a single file (index.html, about.html, api.php, server.js, app.py …)
# ---------------------------------------------------------------------------
FILE_TYPES = (".html", ".htm", ".php", ".js", ".mjs", ".cjs", ".py")


def detect_file(file_path: str, *, pick_free_port: bool = False,
                avoid_ports: Iterable[int] = ()) -> dict:
    """How to run one file.  The app runs in the file's folder; ``entry`` is
    the page to open (for HTML/PHP), relative to that folder."""
    none = {"command": None, "port": None, "type": None, "entry": None}
    folder, name = os.path.split(os.path.abspath(file_path))
    ext = os.path.splitext(name)[1].lower()
    ctx = _make_ctx(folder, None, pick_free_port, avoid_ports)
    if ctx is None or ext not in FILE_TYPES or not os.path.isfile(file_path):
        return none
    if ext in (".html", ".htm"):
        port = ctx.port(8080)
        return {"command": f"{_py()} -m http.server {port} --bind 127.0.0.1", "port": port,
                "type": "HTML page", "entry": name}
    if ext == ".php":
        port = ctx.port(8000)
        return {"command": f"php -S 127.0.0.1:{port}", "port": port, "type": "PHP page", "entry": name}
    if ext in (".js", ".mjs", ".cjs"):
        port = ctx.port(3000)
        return {"command": _env("PORT", port, f"node {_q(name)}"), "port": port,
                "type": "Node script", "entry": None}
    # Python file
    source = ctx.read(name)
    python, setup = _python(ctx)
    if re.search(r"^\s*(import|from)\s+streamlit", source, re.MULTILINE):
        port = ctx.port(8501)
        cmd = f"{python} -m streamlit run {_q(name)} --server.port {port} --server.headless true"
        return {"command": _with_setup(setup, cmd), "port": port, "type": "Streamlit app", "entry": None}
    port = ctx.port(8000)
    return {"command": _with_setup(setup, _env("PORT", port, f"{python} {_q(name)}")), "port": None,
            "type": "Python script", "entry": None}
