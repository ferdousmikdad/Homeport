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


def test_antigravity_command_modes():
    act = ai_routes.build_agy_command("agy", model="gemini-3.8-flash-high", session_id="c1", mode="act", prompt="-fix it")
    assert act[0] == "agy" and act[-1] == "--print=-fix it"
    assert ["--model", "gemini-3.8-flash-high"] == act[act.index("--model"):act.index("--model") + 2]
    assert ["--conversation", "c1"] == act[act.index("--conversation"):act.index("--conversation") + 2]
    assert "--dangerously-skip-permissions" in act

    ask = ai_routes.build_agy_command("agy", model=None, session_id=None, mode="ask", prompt="why?")
    assert "--dangerously-skip-permissions" not in ask and "--model" not in ask and "--conversation" not in ask
    assert ["--mode", "plan"] == ask[ask.index("--mode"):ask.index("--mode") + 2]


def test_translate_antigravity_events():
    seen: set = set()
    init = {"event": "init", "conversation_id": "c1", "init": {"model": "gemini-3.8-flash-low"}}
    assert ai_routes._translate_agy(init, seen) == [{"type": "session", "session_id": "c1", "model": "gemini-3.8-flash-low"}]

    def step(**kw):
        return {"event": "step_update", "step_update": {"conversation_id": "c1", **kw}}

    tool = {"name": "run_command", "parameters": {"CommandLine": "echo hi"}}
    assert ai_routes._translate_agy(step(step_index=2, state="ACTIVE", step_type="tool", tool_name="run_command", tool_info=tool), seen) == [
        {"type": "tool", "id": "2", "name": "run_command", "summary": "echo hi"},
    ]
    # The finished step only reports its result: the row is already shown.
    assert ai_routes._translate_agy(step(step_index=2, state="DONE", step_type="tool", tool_name="run_command", tool_info=tool), seen) == [
        {"type": "tool_result", "id": "2", "error": False},
    ]
    assert ai_routes._translate_agy(step(step_index=3, state="ACTIVE", step_type="agent_response", text_delta="pong"), seen) == [
        {"type": "delta", "text": "pong"},
    ]
    assert ai_routes._translate_agy(step(step_index=0, state="DONE", step_type="user_input"), seen) == []

    done = ai_routes._translate_agy({"event": "result", "result": {"conversation_id": "c1", "status": "SUCCESS",
                                                                     "duration_seconds": 1.5, "num_turns": 1}}, seen)
    assert done == [{"type": "done", "message": None, "session_id": "c1", "duration_ms": 1500, "turns": 1}]
    failed = ai_routes._translate_agy({"event": "result", "result": {"status": "ERROR", "error": "quota"}}, seen)
    assert failed[0]["type"] == "error" and failed[0]["message"] == "quota"


def test_antigravity_ask_validation(client, monkeypatch):
    monkeypatch.setattr(ai_routes, "find_agy", lambda: None)
    assert client.post("/api/ai/ask", json={"prompt": "hi", "agent": "antigravity"}).status_code == 503
    assert client.get("/api/ai/status").json()["antigravity"]["available"] is False
    assert client.get("/api/ai/models").status_code == 503
    assert client.patch("/api/settings", json={"ai_provider": "antigravity"}).json()["ai_provider"] == "antigravity"


def test_prompt_length_limits(client, monkeypatch):
    monkeypatch.setattr(ai_routes, "find_cli", lambda: "/bin/true")
    too_long = "x" * (ai_routes.MAX_PROMPT + 1)
    res = client.post("/api/ai/ask", json={"prompt": too_long})
    assert res.status_code == 400 and "too long" in res.json()["detail"]


def test_antigravity_prompt_drops_snapshot_when_huge():
    many = [{"id": f"app{i}", "name": f"App {i}", "status": "stopped", "path": "/x/" + "p" * 200, "command": "npm run dev"}
            for i in range(200)]
    full = ai_routes.system_prompt("http://127.0.0.1:7777", many, "act")
    short = ai_routes.system_prompt("http://127.0.0.1:7777", many, "act", snapshot=False)
    assert len(ai_routes.agy_prompt(full, "hi")) > ai_routes.AGY_ARG_LIMIT
    assert len(ai_routes.agy_prompt(short, "hi" * 1000)) < ai_routes.AGY_ARG_LIMIT
    assert "GET /api/apps" in short and "app199" not in short
