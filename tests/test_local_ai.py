"""Tests for the local (Ollama) assistant, with a fake Ollama — no real models."""
from __future__ import annotations

import asyncio
import json
import sys

import httpx
import pytest

from backend import local_ai


def _ndjson(*events) -> bytes:
    return ("\n".join(json.dumps(e) for e in events) + "\n").encode()


class FakeOllama:
    """Answers /api/version, /api/tags, /api/pull, /api/delete and scripted /api/chat turns."""

    def __init__(self, chat_turns=None, running=True):
        self.chat_turns = list(chat_turns or [])
        self.running = running
        self.chat_payloads = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if not self.running:
            raise httpx.ConnectError("connection refused", request=request)
        path = request.url.path
        if path == "/api/version":
            return httpx.Response(200, json={"version": "0.12.0"})
        if path == "/api/tags":
            return httpx.Response(200, json={"models": [
                {"name": "qwen3:4b", "size": 2_500_000_000, "details": {"family": "qwen3", "parameter_size": "4B"}}]})
        if path == "/api/pull":
            return httpx.Response(200, content=_ndjson(
                {"status": "pulling manifest"},
                {"status": "pulling abc", "total": 100, "completed": 50},
                {"status": "success"}))
        if path == "/api/delete":
            return httpx.Response(200)
        if path == "/api/chat":
            self.chat_payloads.append(json.loads(request.content))
            turn = self.chat_turns.pop(0)
            return httpx.Response(200, content=_ndjson(*turn))
        return httpx.Response(404, json={"error": "not found"})


@pytest.fixture
def fake(monkeypatch):
    def install(**kw):
        f = FakeOllama(**kw)
        monkeypatch.setattr(local_ai, "ollama_transport", httpx.MockTransport(f))
        return f
    return install


def _events(response) -> list:
    out = []
    for line in response.iter_lines():
        if line.startswith("data: "):
            out.append(json.loads(line[6:]))
    return out


def _text(evt_list) -> str:
    return "".join(e["text"] for e in evt_list if e["type"] == "delta")


# ---------------------------------------------------------------------------
# skills
# ---------------------------------------------------------------------------
def test_every_finding_has_a_skill():
    skills = local_ai.load_skills()
    assert len(skills) >= 10
    for s in skills.values():
        assert s["title"] and s["body"], s["id"]
    covered = {f for s in skills.values() for f in s["findings"]}
    for fid in ("port_in_use", "node_modules", "missing_tool", "missing_script", "python_deps", "composer",
                "env_missing", "laravel_key", "bundle", "database_down", "permission", "killed", "unknown"):
        assert fid in covered, fid


def test_skills_only_name_real_tools():
    known = set(local_ai.READ_TOOLS) | set(local_ai.ACT_TOOLS)
    for s in local_ai.load_skills().values():
        for word in set(__import__("re").findall(r"\b([a-z]+_[a-z_]+)\b", s["body"])):
            if word.endswith("_app") or word in ("list_apps", "get_logs", "check_port", "list_files", "read_file",
                                                "read_skill", "run_fix"):
                assert word in known, (s["id"], word)


def test_pick_skills_findings_then_keywords():
    skills = local_ai.load_skills()
    assert local_ai.pick_skills(skills, ["port_in_use"], "")[0] == "port-in-use"
    picked = local_ai.pick_skills(skills, [], "Error: Cannot find module 'express'")
    assert "node-packages" in picked
    assert local_ai.pick_skills(skills, [], "hello there") == []


def test_think_filter_hides_reasoning_across_chunks():
    f = local_ai._ThinkFilter()
    out = "".join(f.feed(x) for x in ["Hi <thi", "nk>secret plan</th", "ink> there", "!"])
    assert out == "Hi  there!"


def test_ollama_host_normalisation(monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert local_ai.ollama_url() == "http://127.0.0.1:11434"
    monkeypatch.setenv("OLLAMA_HOST", "0.0.0.0")
    assert local_ai.ollama_url() == "http://127.0.0.1:11434"
    monkeypatch.setenv("OLLAMA_HOST", "http://box:9999/")
    assert local_ai.ollama_url() == "http://box:9999"


def test_inside_blocks_escaping_the_app_folder(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    assert local_ai._inside(str(tmp_path), "a.txt").endswith("a.txt")
    with pytest.raises(local_ai.ToolError):
        local_ai._inside(str(tmp_path), "../../etc/passwd")


# ---------------------------------------------------------------------------
# status / models
# ---------------------------------------------------------------------------
def test_status_when_ollama_is_down(client, fake):
    fake(running=False)
    st = client.get("/api/local-ai/status").json()
    assert st["running"] is False and st["models"] == []
    assert st["recommended"] in {c["id"] for c in local_ai.CATALOG}
    assert st["download_url"].startswith("https://ollama.com")
    assert client.post("/api/local-ai/ask", json={"prompt": "hi", "model": "qwen3:4b"}).status_code == 503


def test_status_lists_installed_models(client, fake):
    fake()
    st = client.get("/api/local-ai/status").json()
    assert st["running"] and st["version"] == "0.12.0"
    assert [m["name"] for m in st["models"]] == ["qwen3:4b"]
    assert next(c for c in st["catalog"] if c["id"] == "qwen3:4b")["installed"] is True
    assert next(c for c in st["catalog"] if c["id"] == "qwen3:8b")["installed"] is False


def _wait_pull(client, timeout=5.0):
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        pull = client.get("/api/local-ai/status").json()["pull"]
        if pull and not pull["active"]:
            return pull
        time.sleep(0.02)
    raise AssertionError("download didn't finish")


def test_pull_runs_in_background_and_delete(client, fake):
    fake()
    assert client.post("/api/local-ai/pull", json={"model": "qwen3:8b"}).json() == {"started": "qwen3:8b"}
    pull = _wait_pull(client)
    assert pull["done"] and pull["error"] is None and pull["completed"] == 50 and pull["total"] == 100
    # the first downloaded model becomes the selected one
    assert client.get("/api/settings").json()["local_model"] == "qwen3:8b"
    assert client.get("/api/local-ai/status").json()["selected"] == "qwen3:8b"
    assert client.post("/api/local-ai/pull", json={"model": "bad model; rm -rf"}).status_code == 400
    assert client.post("/api/local-ai/pull/cancel").json() == {"cancelled": False}
    # removing the selected model clears the choice
    assert client.post("/api/local-ai/delete", json={"model": "qwen3:8b"}).json() == {"deleted": "qwen3:8b"}
    assert client.get("/api/settings").json()["local_model"] is None


def test_pull_reports_ollama_errors(client, monkeypatch):
    def handler(request):
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "1"})
        return httpx.Response(200, content=_ndjson({"status": "pulling manifest"}, {"error": "model not found"}))
    monkeypatch.setattr(local_ai, "ollama_transport", httpx.MockTransport(handler))
    client.post("/api/local-ai/pull", json={"model": "nope:1b"})
    pull = _wait_pull(client)
    assert pull["error"] == "model not found" and not pull["done"]


def test_settings_roundtrip_and_validation(client):
    assert client.get("/api/settings").json() == {"ai_provider": None, "local_model": None, "projects_dir": None}
    assert client.patch("/api/settings", json={"ai_provider": "local", "local_model": "qwen3:4b"}).json() == \
        {"ai_provider": "local", "local_model": "qwen3:4b", "projects_dir": None}
    assert client.get("/api/settings").json()["ai_provider"] == "local"
    assert client.patch("/api/settings", json={"ai_provider": "gpt"}).status_code == 400
    assert client.patch("/api/settings", json={"theme": "x"}).status_code == 400
    assert client.patch("/api/settings", json={"local_model": "a b"}).status_code == 400
    assert client.patch("/api/settings", json={"local_model": None}).json()["local_model"] is None


def test_status_lists_skills(client, fake):
    fake()
    ids = {s["id"] for s in client.get("/api/local-ai/status").json()["skills"]}
    assert {"port-in-use", "node-packages", "database-down"} <= ids


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------
def _add_app(client, tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    (folder / "package.json").write_text('{"scripts": {"dev": "vite"}}')
    res = client.post("/api/apps", json={"name": "Shop", "path": str(folder),
                                         "command": f'"{sys.executable}" -c "print(1)"', "port": 4321})
    assert res.status_code in (200, 201), res.text
    return res.json()["id"]


def test_ask_runs_read_tools_and_streams_answer(client, fake, tmp_path):
    app_id = _add_app(client, tmp_path)
    f = fake(chat_turns=[
        [{"message": {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "read_file", "arguments": {"app_id": app_id, "file": "package.json"}}}]}, "done": False},
         {"message": {"role": "assistant", "content": ""}, "done": True}],
        [{"message": {"role": "assistant", "content": "Your dev script "}, "done": False},
         {"message": {"role": "assistant", "content": "runs vite."}, "done": True,
          "eval_count": 20, "eval_duration": 1_000_000_000}],
    ])
    with client.stream("POST", "/api/local-ai/ask",
                       json={"prompt": "what does dev run?", "model": "qwen3:4b", "mode": "ask"}) as r:
        evts = _events(r)
    types = [e["type"] for e in evts]
    assert types[0] == "session" and types[-1] == "done"
    assert any(e["type"] == "tool" and e["name"] == "read_file" for e in evts)
    assert not any(e["type"] == "tool_result" and e["error"] for e in evts)
    assert _text(evts) == "Your dev script runs vite."
    assert evts[-1]["tokens_per_s"] == 20.0
    # the file content went back to the model; ask mode offers no action tools
    second = f.chat_payloads[1]
    assert any(m["role"] == "tool" and '"dev": "vite"' in m["content"] for m in second["messages"])
    names = {t["function"]["name"] for t in second["tools"]}
    assert "read_file" in names and "update_app" not in names
    assert second["think"] is False and second["options"]["num_ctx"] == local_ai.CONTEXT_TOKENS


def _auto_answer(monkeypatch, approve):
    """Starlette's TestClient only returns a response once it has finished, so the
    browser's mid-stream approval can't be simulated; answer it in-process."""
    asked = []

    async def answer(run, emit, name, summary):
        asked.append(summary)
        await emit({"type": "confirm", "id": "x", "name": name, "summary": summary})
        return approve
    monkeypatch.setattr(local_ai, "_confirm", answer)
    return asked


def test_act_tool_runs_after_approval(client, fake, tmp_path, monkeypatch):
    app_id = _add_app(client, tmp_path)
    asked = _auto_answer(monkeypatch, True)
    fake(chat_turns=[
        [{"message": {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "update_app", "arguments": json.dumps({"app_id": app_id, "port": 4400})}}]},
          "done": True}],
        [{"message": {"role": "assistant", "content": "Moved it to 4400."}, "done": True}],
    ])
    with client.stream("POST", "/api/local-ai/ask",
                       json={"prompt": "fix the port", "model": "qwen3:4b", "mode": "act"}) as r:
        evts = _events(r)
    assert asked == ["Change \u201cShop\u201d: port \u2192 4400"]
    assert [e["type"] for e in evts if e["type"] in ("confirm", "tool_result", "done")] == ["confirm", "tool_result", "done"]
    assert client.get(f"/api/apps/{app_id}").json()["port"] == 4400


def test_declined_action_changes_nothing(client, fake, tmp_path, monkeypatch):
    app_id = _add_app(client, tmp_path)
    _auto_answer(monkeypatch, False)
    f = fake(chat_turns=[
        [{"message": {"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": "update_app", "arguments": {"app_id": app_id, "port": 4500}}}]}, "done": True}],
        [{"message": {"role": "assistant", "content": "OK, left it."}, "done": True}],
    ])
    with client.stream("POST", "/api/local-ai/ask",
                       json={"prompt": "fix the port", "model": "qwen3:4b", "mode": "act"}) as r:
        _events(r)
    assert client.get(f"/api/apps/{app_id}").json()["port"] == 4321
    assert any("declined" in m["content"] for m in f.chat_payloads[1]["messages"] if m["role"] == "tool")


def test_confirm_waits_for_the_answer():
    async def scenario():
        run = local_ai._Run()
        sent = []

        async def emit(evt):
            sent.append(evt)
        task = asyncio.create_task(local_ai._confirm(run, emit, "stop_app", "Stop \u201cShop\u201d"))
        await asyncio.sleep(0.01)
        assert sent[0]["type"] == "confirm" and not task.done()
        run.confirms[sent[0]["id"]].set_result(True)
        assert await task is True and run.confirms == {}
    asyncio.run(scenario())


def test_crash_context_and_guides_are_prefilled(client, fake, tmp_path):
    app_id = _add_app(client, tmp_path)
    f = fake(chat_turns=[[{"message": {"role": "assistant", "content": "Done."}, "done": True}]])
    with client.stream("POST", "/api/local-ai/ask", json={
            "prompt": "it crashed with EADDRINUSE", "model": "qwen3:4b", "mode": "ask", "app_id": app_id}) as r:
        _events(r)
    system = f.chat_payloads[0]["messages"][0]["content"]
    assert f"asking about app {app_id}" in system
    assert "Guide 'port-in-use'" in system
    assert app_id in system  # apps list


def test_model_without_tools_falls_back(client, fake):
    f = fake(chat_turns=[[{"message": {"role": "assistant", "content": "Try npm install."}, "done": True}]])
    with client.stream("POST", "/api/local-ai/ask",
                       json={"prompt": "help", "model": "gemma3:4b", "mode": "act"}) as r:
        evts = _events(r)
    assert "tools" not in f.chat_payloads[0]
    assert _text(evts) == "Try npm install."


def test_ask_validation(client, fake):
    fake()
    assert client.post("/api/local-ai/ask", json={"prompt": " ", "model": "qwen3:4b"}).status_code == 400
    assert client.post("/api/local-ai/ask", json={"prompt": "hi", "model": "x y"}).status_code == 400
    assert client.post("/api/local-ai/confirm", json={"id": "nope", "approve": True}).status_code == 404
    assert client.post("/api/local-ai/stop").json() == {"stopped": False}


def test_about_reports_data_folder(client, monkeypatch):
    from backend import osutil
    opened = []
    monkeypatch.setattr(osutil, "open_folder", opened.append)
    data = client.get("/api/about").json()
    assert data["data_dir"] and data["address"].startswith("http://localhost") and data["installed"] in (True, False)
    assert client.post("/api/about/open-data").json()["ok"] is True and opened == [data["data_dir"]]
