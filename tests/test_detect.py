"""Project-type detection (backend/detect.py via monitor.detect_command)."""

from __future__ import annotations

import json
import socket

import pytest

from backend import monitor, shellenv


def _make(root, files: dict):
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if content is None:
            path.mkdir(exist_ok=True)
        else:
            path.write_text(content)
    return str(root)


def _detect(root, files, **kw):
    return monitor.detect_command(_make(root, files), **kw)


@pytest.fixture(autouse=True)
def _no_optional_tools(monkeypatch):
    """Make results independent of what is installed on the test machine."""
    monkeypatch.setattr(shellenv, "which", lambda tool: None)


# --- PHP --------------------------------------------------------------------
def test_laravel(tmp_path):
    r = _detect(tmp_path, {"artisan": "", "composer.json": "{}", "vendor": None, ".env": ""})
    assert r == {
        "type": "Laravel",
        "port": 8000,
        "command": "php artisan serve --host=127.0.0.1 --port=8000",
    }


def test_laravel_fresh_clone_installs_first(tmp_path):
    r = _detect(tmp_path, {
        "artisan": "", "composer.json": "{}", ".env.example": "",
        "package.json": json.dumps({"scripts": {"dev": "vite", "build": "vite build"}}),
        "vite.config.js": "",
    })
    assert r["command"] == (
        "composer install && cp .env.example .env && php artisan key:generate"
        " && npm install && npm run build"
        " && php artisan serve --host=127.0.0.1 --port=8000"
    )


def test_laravel_beats_package_json(tmp_path):
    r = _detect(tmp_path, {"artisan": "", "vendor": None, "node_modules": None,
                           "package.json": json.dumps({"scripts": {"dev": "vite"}})})
    assert r["type"] == "Laravel"


def test_plain_php_and_public_docroot(tmp_path):
    assert _detect(tmp_path / "a", {"index.php": "<?php"})["command"] == "php -S 127.0.0.1:8000 -t ."
    assert _detect(tmp_path / "b", {"public/index.php": "<?php"})["command"] == (
        "php -S 127.0.0.1:8000 -t public"
    )


def test_symfony_without_cli(tmp_path):
    r = _detect(tmp_path, {"bin/console": "", "composer.json": "{}", "vendor": None, "public": None})
    assert r["type"] == "Symfony"
    assert r["command"] == "php -S 127.0.0.1:8000 -t public"


# --- Python -----------------------------------------------------------------
def test_django_with_venv(tmp_path):
    _make(tmp_path, {"manage.py": ""})
    venv_py = tmp_path / ".venv" / "bin" / "python"
    venv_py.parent.mkdir(parents=True)
    venv_py.write_text("")
    venv_py.chmod(0o755)
    r = monitor.detect_command(str(tmp_path))
    assert r["type"] == "Django"
    assert r["command"] == ".venv/bin/python manage.py runserver 127.0.0.1:8000"


def test_fastapi_without_main_guard_uses_uvicorn(tmp_path):
    r = _detect(tmp_path, {"main.py": "from fastapi import FastAPI\napi = FastAPI()\n"})
    assert r["type"] == "FastAPI"
    assert r["command"] == "python3 -m uvicorn main:api --host 127.0.0.1 --port 8000 --reload"


def test_fastapi_that_runs_itself_is_run_directly(tmp_path):
    r = _detect(tmp_path, {"app.py": (
        "import uvicorn\nfrom fastapi import FastAPI\napp = FastAPI()\n"
        "if __name__ == '__main__':\n    uvicorn.run(app)\n"
    )})
    assert r["command"] == "python3 app.py"


def test_flask_and_streamlit(tmp_path):
    flask = _detect(tmp_path / "f", {"app.py": "from flask import Flask\napp = Flask(__name__)\n"})
    assert flask["command"] == "python3 -m flask --app app:app run --port 5000 --debug"
    st = _detect(tmp_path / "s", {"app.py": "import streamlit as st\nst.write('hi')\n"})
    assert st["type"] == "Streamlit"
    assert "streamlit run app.py --server.port 8501" in st["command"]


def test_requirements_without_venv_creates_one(tmp_path):
    r = _detect(tmp_path, {"requirements.txt": "flask", "run.py": "print(1)"})
    assert r["command"] == (
        "python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt && .venv/bin/python run.py"
    )


def test_fastapi_in_subpackage(tmp_path):
    r = _detect(tmp_path, {"pyproject.toml": "", "backend/main.py": "app = FastAPI()\n"})
    assert r["command"] == "python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"


# --- JavaScript -------------------------------------------------------------
@pytest.mark.parametrize("script,expected", [
    ("next dev", "npm run dev -- -p 3000"),
    ("nuxt dev", "npm run dev -- --port 3000"),
    ("astro dev", "npm run dev -- --port 4321"),
    ("vite", "npm run dev -- --port 5173 --strictPort"),
    ("nodemon server.js", "PORT=3000 npm run dev"),
])
def test_node_frameworks(tmp_path, script, expected):
    r = _detect(tmp_path, {"node_modules": None,
                           "package.json": json.dumps({"scripts": {"dev": script}})})
    assert r["command"] == expected


def test_node_package_manager_from_lockfile_and_install(tmp_path):
    r = _detect(tmp_path, {"pnpm-lock.yaml": "",
                           "package.json": json.dumps({"scripts": {"dev": "vite"}})})
    assert r["command"] == "pnpm install && pnpm run dev --port 5173 --strictPort"


def test_node_follows_script_indirection(tmp_path):
    r = _detect(tmp_path, {"node_modules": None, "package.json": json.dumps(
        {"scripts": {"dev": "npm run serve:web", "serve:web": "next dev"}})})
    assert r["type"] == "Next.js"


def test_node_without_scripts_runs_main(tmp_path):
    r = _detect(tmp_path, {"node_modules": None, "server.js": "",
                           "package.json": json.dumps({"name": "x"})})
    assert r["command"] == "node server.js"


def test_build_only_package_json_is_not_runnable(tmp_path):
    r = _detect(tmp_path, {"package.json": json.dumps({"scripts": {"build": "tsc"}})})
    assert r["command"] is None


# --- other ecosystems ---------------------------------------------------------
@pytest.mark.parametrize("files,kind,command", [
    ({"go.mod": "", "main.go": ""}, "Go", "go run ."),
    ({"go.mod": "", "cmd/api/main.go": ""}, "Go", "go run ./cmd/api"),
    ({"Cargo.toml": ""}, "Rust", "cargo run"),
    ({"bin/rails": ""}, "Rails", "(bundle check || bundle install) && bin/rails server -b 127.0.0.1 -p 3000"),
    ({"pom.xml": "spring-boot", "mvnw": ""}, "Spring Boot", "SERVER_PORT=8080 ./mvnw spring-boot:run"),
    ({"App.csproj": ""}, ".NET", "dotnet run --urls http://127.0.0.1:5000"),
    ({"compose.yaml": "services:\n  web:\n    ports:\n      - \"8088:80\"\n"}, "Docker Compose",
     "docker compose up --build"),
    ({"Makefile": "build:\n\techo\nserve:\n\techo\n"}, "Makefile", "make serve"),
    ({"start.sh": ""}, "Shell script", "bash start.sh"),
    ({"Procfile": "web: gunicorn app:app -b :$PORT\n"}, "Procfile", "PORT=5000 gunicorn app:app -b :5000"),
    ({"index.html": ""}, "Static site", "python3 -m http.server 8080 --bind 127.0.0.1"),
    ({"dist/index.html": ""}, "Static site", "python3 -m http.server 8080 --bind 127.0.0.1 --directory dist"),
    ({"page.html": ""}, "Static site", "python3 -m http.server 8080 --bind 127.0.0.1"),
])
def test_other_project_types(tmp_path, files, kind, command):
    r = _detect(tmp_path, files)
    assert (r["type"], r["command"]) == (kind, command)


def test_compose_port_comes_from_mapping(tmp_path):
    r = _detect(tmp_path, {"docker-compose.yml": "ports:\n  - 8088:80\n"})
    assert r["port"] == 8088


# --- sub-folders & ports ------------------------------------------------------
def test_project_in_subfolder(tmp_path):
    r = _detect(tmp_path, {"README.md": "hi", "app/artisan": "", "app/vendor": None})
    assert r["type"] == "Laravel (in app/)"
    assert r["command"] == "cd app && php artisan serve --host=127.0.0.1 --port=8000"


def test_documented_port_wins_over_default(tmp_path):
    r = _detect(tmp_path, {"artisan": "", "vendor": None, "README.md": "open localhost:8123"})
    assert r["port"] == 8123 and r["command"].endswith("--port=8123")


def test_pick_free_port_skips_busy_and_registered(tmp_path):
    files = {"artisan": "", "vendor": None}
    assert _detect(tmp_path, files, pick_free_port=True, avoid_ports={8000, 8001})["port"] >= 8002

    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        taken = busy.getsockname()[1]
        r = _detect(tmp_path / "x", {"artisan": "", "vendor": None,
                                     "README.md": f"localhost:{taken}"}, pick_free_port=True)
        assert r["port"] != taken


def test_system_ports_are_ignored(tmp_path):
    assert _detect(tmp_path, {"main.py": "", "README.md": "listens on port 127.0.0.1"})["port"] is None


# --- Windows command forms (cmd.exe) -----------------------------------------
@pytest.fixture
def windows(monkeypatch):
    from backend import detect
    monkeypatch.setattr(detect, "WINDOWS", True)


def test_windows_env_prefix_and_python(tmp_path, windows):
    r = _detect(tmp_path / "n", {"node_modules": None,
                                 "package.json": json.dumps({"scripts": {"start": "node app.js"}})})
    assert r["command"] == "set PORT=3000&& npm run start"
    r = _detect(tmp_path / "s", {"index.html": ""})
    assert r["command"] == "python -m http.server 8080 --bind 127.0.0.1"


def test_windows_venv_and_requirements(tmp_path, windows):
    r = _detect(tmp_path / "a", {"requirements.txt": "flask", "run.py": "print(1)"})
    assert r["command"] == (
        "python -m venv .venv && .venv\\Scripts\\python.exe -m pip install -r requirements.txt"
        " && .venv\\Scripts\\python.exe run.py"
    )
    b = tmp_path / "b"
    _make(b, {"manage.py": "", ".venv/Scripts/python.exe": ""})
    assert monitor.detect_command(str(b))["command"] == (
        ".venv\\Scripts\\python.exe manage.py runserver 127.0.0.1:8000"
    )


def test_windows_laravel_copy_and_wrappers(tmp_path, windows):
    r = _detect(tmp_path / "l", {"artisan": "", "vendor": None, ".env.example": ""})
    assert r["command"].startswith("copy /Y .env.example .env && php artisan key:generate && ")
    r = _detect(tmp_path / "m", {"pom.xml": "spring-boot", "mvnw.cmd": ""})
    assert r["command"] == "set SERVER_PORT=8080&& mvnw.cmd spring-boot:run"
    r = _detect(tmp_path / "g", {"build.gradle": "", "gradlew.bat": ""})
    assert r["command"] == "gradlew.bat run"
    r = _detect(tmp_path / "r", {"bin/rails": ""})
    assert "ruby bin/rails server" in r["command"]


def test_windows_batch_launchers_and_quoting(tmp_path, windows):
    assert _detect(tmp_path / "b", {"start.bat": ""})["command"] == "call start.bat"
    assert _detect(tmp_path / "p", {"run.ps1": ""})["command"] == (
        "powershell -NoProfile -ExecutionPolicy Bypass -File run.ps1"
    )
    # .sh launchers need bash, which plain Windows doesn't have
    assert _detect(tmp_path / "s", {"start.sh": ""})["command"] is None
    r = _detect(tmp_path / "q", {"README.md": "x", "my app/artisan": "", "my app/vendor": None})
    assert r["command"].startswith('cd "my app" && php artisan serve')
