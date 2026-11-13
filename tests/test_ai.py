"""Tests for the on-demand AI assistant routes (no real `claude` calls)."""
from __future__ import annotations

from backend import ai_routes


def test_translate_events():
    init = {"type": "system", "subtype": "init", "session_id": "s1", "model": "claude-sonnet-5-5"}
    assert ai_routes._translate(init) == [{"type": "session", "session_id": "s1", "model": "claude-sonnet-5-5"}]

    assistant = {"type": "assistant", "message": {"content": [
        {"type": "text", "text": "Checking"},
        {"type": "tool_use", "id": "t1", "name": "Bash", "input": {"command": "curl -s localhost:7777/api/apps"}},
    ]}}
    assert ai_routes._translate(assistant) == [
        {"type": "text", "text": "Checking"},
        {"type": "tool", "id": "t1", "name": "Bash", "summary": "curl -s localhost:7777/api/apps"},
    ]

    result = {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "t1", "is_error": True}]}}
    assert ai_routes._translate(result) == [{"type": "tool_result", "id": "t1", "error": True}]

    done = ai_routes._translate({"type": "result", "is_error": False, "session_id": "s1", "total_cost_usd": 0.01,
                                 "duration_ms": 900, "num_turns": 2})
    assert done[0]["type"] == "done" and done[0]["session_id"] == "s1"
    assert ai_routes._translate({"type": "rate_limit_event"}) == []


def test_build_command_modes():
    act = ai_routes.build_command("claude", model="opus", session_id="s1", mode="act", sys_prompt="X")
    assert act[:2] == ["claude", "-p"]
    assert ["--model", "opus"] == act[act.index("--model"):act.index("--model") + 2]
    assert ["--resume", "s1"] == act[act.index("--resume"):act.index("--resume") + 2]
    assert "--dangerously-skip-permissions" in act

    ask = ai_routes.build_command("claude", model=None, session_id=None, mode="ask", sys_prompt="X")
    assert "--dangerously-skip-permissions" not in ask and "--model" not in ask and "--resume" not in ask
    assert "--allowedTools" in ask and "Edit" not in ask


def test_system_prompt_flags_shared_ports():
    states = [
        {"id": "a", "name": "A", "status": "running", "port": 3000},
        {"id": "b", "name": "B", "status": "stopped", "port": None, "detected_port": 3000},
    ]
    text = ai_routes.system_prompt("http://127.0.0.1:7777", states, "ask")
    assert "Apps sharing a port" in text and "READ-ONLY" in text


def test_ask_validation(client, monkeypatch):
    assert client.post("/api/ai/ask", json={"prompt": "  "}).status_code == 400
    monkeypatch.setattr(ai_routes, "find_cli", lambda: None)
    assert client.post("/api/ai/ask", json={"prompt": "hi"}).status_code == 503
    assert client.get("/api/ai/status").json()["available"] is False
    assert client.post("/api/ai/stop").json() == {"stopped": False}
