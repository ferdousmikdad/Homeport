import importlib
import sys

from fastapi.testclient import TestClient


def _reload_paths(monkeypatch, frozen, data_dir=None):
    from backend import paths
    if frozen:
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", "/bundle", raising=False)
    else:
        monkeypatch.delattr(sys, "frozen", raising=False)
    if data_dir:
        monkeypatch.setenv("HOMEPORT_DATA_DIR", data_dir)
    else:
        monkeypatch.delenv("HOMEPORT_DATA_DIR", raising=False)
    return importlib.reload(paths)


def test_source_layout_unchanged(monkeypatch):
    p = _reload_paths(monkeypatch, frozen=False)
    assert p.DATA_DIR.endswith("data") and p.DATA_DIR.startswith(p.SOURCE_ROOT)
    assert p.UI_DIR.startswith(p.SOURCE_ROOT)
    _reload_paths(monkeypatch, frozen=False)


def test_installed_app_uses_user_folder(monkeypatch):
    p = _reload_paths(monkeypatch, frozen=True)
    assert p.DATA_DIR == p.user_data_dir()
    assert p.UI_DIR.startswith("/bundle") and p.BIN_DIR.startswith(p.DATA_DIR)
    monkeypatch.undo()
    _reload_paths(monkeypatch, frozen=False)


def test_data_dir_override(monkeypatch, tmp_path):
    p = _reload_paths(monkeypatch, frozen=False, data_dir=str(tmp_path))
    assert p.DATA_DIR == str(tmp_path)
    monkeypatch.undo()
    _reload_paths(monkeypatch, frozen=False)


def test_quit_endpoint(monkeypatch):
    from backend import main
    called = []
    client = TestClient(main.app)
    monkeypatch.setattr(main, "request_quit", None)
    assert client.post("/api/quit").status_code == 501
    monkeypatch.setattr(main, "request_quit", lambda: called.append(1))
    assert client.post("/api/quit", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/quit", headers={"Origin": "http://localhost:7777"}).json() == {"ok": True}
    assert client.get("/api/health").json()["can_quit"] is True
