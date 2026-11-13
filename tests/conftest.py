"""Pytest fixtures: an isolated registry file and a TestClient app."""

from __future__ import annotations

import sys

import pytest
from fastapi.testclient import TestClient

from backend import main, procman, registry as registry_module


@pytest.fixture(autouse=True)
def _isolate_logs_and_command_style(tmp_path_factory, monkeypatch):
    """Keep test logs out of data/logs, and expect sh-style generated
    commands unless a test asks for Windows forms explicitly."""
    from backend import detect

    monkeypatch.setattr(procman, "_DEFAULT_LOG_DIR", str(tmp_path_factory.mktemp("logs")))
    monkeypatch.setattr(detect, "WINDOWS", False)


@pytest.fixture
def isolated_registry(tmp_path, monkeypatch):
    """Point backend.main at a throw-away registry file for one test."""
    reg = registry_module.Registry(str(tmp_path / "data" / "apps.json"))
    monkeypatch.setattr(main, "registry", reg)
    return reg


@pytest.fixture
def client(isolated_registry):
    """FastAPI TestClient with its own registry; lifespan starts a fresh pm."""
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def demo_dir(tmp_path):
    """A directory containing a long-running script and a detected entry file."""
    directory = tmp_path / "demo-app"
    directory.mkdir()
    script = directory / "script.py"
    script.write_text(
        "import os, sys, time\n"
        "print('hello from demo', flush=True)\n"
        "print('stderr line', file=sys.stderr, flush=True)\n"
        "print('FOO=' + os.environ.get('FOO', ''), flush=True)\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    (directory / "run.py").write_text(
        "print('detected entry point')\n", encoding="utf-8"
    )
    return directory


@pytest.fixture
def long_command(demo_dir):
    """Explicit command (the venv interpreter) that stays alive for 60s."""
    return f"{sys.executable} -u {demo_dir / 'script.py'}"
