from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from hr_agent.agent import langgraph_agent as agent_mod


@pytest.fixture
def fake_messages(monkeypatch):
    @dataclass
    class FakeHumanMessage:
        content: str

    @dataclass
    class FakeAIMessage:
        content: str
        tool_calls: list[dict] | None = None

    @dataclass
    class FakeToolMessage:
        content: str
        tool_call_id: str

    @dataclass
    class FakeSystemMessage:
        content: str

    monkeypatch.setattr(agent_mod, "HumanMessage", FakeHumanMessage)
    monkeypatch.setattr(agent_mod, "AIMessage", FakeAIMessage)
    monkeypatch.setattr(agent_mod, "ToolMessage", FakeToolMessage)
    monkeypatch.setattr(agent_mod, "SystemMessage", FakeSystemMessage)

    return SimpleNamespace(
        HumanMessage=FakeHumanMessage,
        AIMessage=FakeAIMessage,
        ToolMessage=FakeToolMessage,
        SystemMessage=FakeSystemMessage,
    )


class _RecordingPolicyEngine:
    def __init__(self, allowed: bool):
        self.allowed = allowed
        self.contexts: list[agent_mod.PolicyContext] = []

    def is_allowed(self, context: agent_mod.PolicyContext) -> bool:
        self.contexts.append(context)
        return self.allowed


class _DummyTool:
    def __init__(self, result=None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.calls: list[dict] = []

    def invoke(self, args: dict):
        self.calls.append(args)
        if self.error is not None:
            raise self.error
        return self.result


class _DummyGraph:
    def __init__(self, result=None, error: Exception | None = None, stream_events=None):
        self.result = result or {}
        self.error = error
        self.stream_events = list(stream_events or [])
        self.invocations: list[tuple[dict, dict]] = []
        self.stream_calls: list[tuple[dict, dict, str | None]] = []

    def invoke(self, state: dict, config: dict):
        self.invocations.append((state, config))
        if self.error is not None:
            raise self.error
        return self.result

    def stream(self, state: dict, config: dict, stream_mode: str | None = None):
        self.stream_calls.append((state, config, stream_mode))
        if self.error is not None:
            raise self.error
        for event in self.stream_events:
            yield event


def _mock_employee_service():
    return SimpleNamespace(
        get_basic_info=lambda _employee_id: {"preferred_name": "Alex"},
        get_requester_context=lambda user_email: {
            "employee_id": 201,
            "user_email": user_email,
            "name": "Alex Kim",
            "role": "EMPLOYEE",
            "direct_reports": [],
        },
    )


def test_get_system_message_includes_requester_context(monkeypatch, fake_messages):
    monkeypatch.setattr(agent_mod, "get_employee_service", _mock_employee_service)

    message = agent_mod.get_system_message(
        {
            "messages": [],
            "user_email": "alex.kim@acme.com",
            "user_id": 201,
            "user_role": "EMPLOYEE",
            "tools_called": [],
            "current_date": "2026-03-21",
        }
    )

    assert isinstance(message, fake_messages.SystemMessage)
    assert "Alex" in message.content
    assert "alex.kim@acme.com" in message.content
    assert "2026-03-21" in message.content


def test_check_authorization_denies_disallowed_tool_call(monkeypatch, fake_messages):
    policy_engine = _RecordingPolicyEngine(allowed=False)
    monkeypatch.setattr(agent_mod, "get_policy_engine", lambda: policy_engine)

    result = agent_mod.check_authorization(
        {
            "messages": [
                SimpleNamespace(
                    tool_calls=[
                        {
                            "name": "get_compensation",
                            "args": {"employee_id": 999},
                            "id": "call-1",
                        }
                    ]
                )
            ],
            "user_id": 201,
            "user_email": "alex.kim@acme.com",
            "user_role": "EMPLOYEE",
        }
    )

    assert [ctx.target_id for ctx in policy_engine.contexts] == [999]
    denial = result["messages"][0]
    assert isinstance(denial, fake_messages.ToolMessage)
    assert denial.tool_call_id == "call-1"
    assert json.loads(denial.content)["error"] == "Access Denied"


def test_check_authorization_allows_manager_target_alias(monkeypatch):
    policy_engine = _RecordingPolicyEngine(allowed=True)
    monkeypatch.setattr(agent_mod, "get_policy_engine", lambda: policy_engine)

    result = agent_mod.check_authorization(
        {
            "messages": [
                SimpleNamespace(
                    tool_calls=[
                        {
                            "name": "get_pending_approvals",
                            "args": {"manager_employee_id": 10},
                            "id": "call-2",
                        }
                    ]
                )
            ],
            "user_id": 10,
            "user_email": "manager@acme.com",
            "user_role": "MANAGER",
        }
    )

    assert result == {}
    assert [ctx.target_id for ctx in policy_engine.contexts] == [10]


def test_tool_node_executes_tools_tracks_unique_calls_and_wraps_errors(
    monkeypatch, fake_messages
):
    ok_tool = _DummyTool(result={"ok": True})
    failing_tool = _DummyTool(error=RuntimeError("boom"))
    monkeypatch.setattr(
        agent_mod,
        "TOOL_MAP",
        {
            "ok_tool": ok_tool,
            "fail_tool": failing_tool,
        },
    )

    result = agent_mod.tool_node(
        {
            "messages": [
                SimpleNamespace(
                    tool_calls=[
                        {"name": "ok_tool", "args": {"value": 1}, "id": "call-1"},
                        {"name": "fail_tool", "args": {"value": 2}, "id": "call-2"},
                        {"name": "missing_tool", "args": {}, "id": "call-3"},
                        {"name": "ok_tool", "args": {"value": 3}, "id": "call-4"},
                    ]
                )
            ],
            "tools_called": ["already_called"],
        }
    )

    assert ok_tool.calls == [{"value": 1}, {"value": 3}]
    assert failing_tool.calls == [{"value": 2}]
    assert result["tools_called"] == [
        "already_called",
        "ok_tool",
        "fail_tool",
        "missing_tool",
    ]

    payloads = [json.loads(message.content) for message in result["messages"]]
    assert [type(message) for message in result["messages"]] == [
        fake_messages.ToolMessage,
        fake_messages.ToolMessage,
        fake_messages.ToolMessage,
        fake_messages.ToolMessage,
    ]
    assert payloads[0] == {"ok": True}
    assert payloads[1] == {"error": "boom"}
    assert payloads[2] == {"error": "Unknown tool: missing_tool"}
    assert payloads[3] == {"ok": True}


def test_routing_helpers_follow_tool_and_auth_paths(fake_messages):
    tool_call_message = SimpleNamespace(tool_calls=[{"name": "demo", "args": {}, "id": "1"}])
    plain_message = SimpleNamespace(tool_calls=[])

    assert agent_mod.should_continue({"messages": [tool_call_message]}) == "tools"
    assert agent_mod.should_continue({"messages": [plain_message]}) == "end"

    denied = fake_messages.ToolMessage(
        content=json.dumps({"error": "Access Denied"}),
        tool_call_id="call-1",
    )
    neutral = fake_messages.ToolMessage(
        content=json.dumps({"ok": True}),
        tool_call_id="call-2",
    )

    assert agent_mod.after_tools({"messages": [denied]}) == "agent"
    assert agent_mod.after_tools({"messages": [plain_message]}) == "end"
    assert agent_mod.check_auth_result({"messages": [denied]}) == "agent"
    assert agent_mod.check_auth_result({"messages": [neutral]}) == "execute"
    assert agent_mod.check_auth_result({"messages": []}) == "execute"


def test_load_history_from_turns_hydrates_only_non_blank_content(monkeypatch, fake_messages):
    monkeypatch.setattr(agent_mod, "get_employee_service", _mock_employee_service)
    monkeypatch.setattr(agent_mod, "compile_hr_agent", lambda: _DummyGraph())

    agent = agent_mod.HRAgentLangGraph("alex.kim@acme.com", session_id="session-1")
    agent.load_history_from_turns(
        [
            {"query": "First question", "response": "First answer"},
            {"query": " ", "response": "Reply only"},
            {"query": "Follow-up only", "response": ""},
        ]
    )

    assert [message.content for message in agent._message_history] == [
        "First question",
        "First answer",
        "Reply only",
        "Follow-up only",
    ]


def test_hr_agent_chat_returns_last_ai_message_and_tracks_callbacks(
    monkeypatch, fake_messages
):
    monkeypatch.setattr(agent_mod, "get_employee_service", _mock_employee_service)
    handler = SimpleNamespace(session_id=None, user_id=None, metadata=None)
    monkeypatch.setattr(agent_mod, "get_langfuse_handler", lambda: handler)

    graph = _DummyGraph(
        result={
            "tools_called": ["get_compensation"],
            "messages": [
                fake_messages.ToolMessage(
                    content=json.dumps({"ok": True}),
                    tool_call_id="call-1",
                ),
                fake_messages.AIMessage(content="Your salary details are ready."),
            ],
        }
    )
    monkeypatch.setattr(agent_mod, "compile_hr_agent", lambda: graph)

    agent = agent_mod.HRAgentLangGraph(
        "alex.kim@acme.com",
        session_id="session-42",
        trace_metadata={"source": "unit-test"},
    )
    response = agent.chat("What is my salary?")

    assert response == "Your salary details are ready."
    assert agent.tools_called == ["get_compensation"]
    assert [message.content for message in agent._message_history] == [
        "What is my salary?",
        "Your salary details are ready.",
    ]

    state, config = graph.invocations[0]
    assert state["user_email"] == "alex.kim@acme.com"
    assert state["user_id"] == 201
    assert state["user_role"] == "EMPLOYEE"
    assert state["messages"][0].content == "What is my salary?"
    assert config["configurable"]["thread_id"] == "session-42"
    assert config["metadata"]["user_id"] == 201
    assert config["callbacks"] == [handler]

    assert handler.session_id == "session-42"
    assert handler.user_id == "alex.kim@acme.com"
    assert handler.metadata["user_role"] == "EMPLOYEE"
    assert handler.metadata["source"] == "unit-test"


def test_hr_agent_chat_returns_fallback_when_no_ai_message(monkeypatch, fake_messages):
    monkeypatch.setattr(agent_mod, "get_employee_service", _mock_employee_service)
    monkeypatch.setattr(agent_mod, "get_langfuse_handler", lambda: None)
    monkeypatch.setattr(
        agent_mod,
        "compile_hr_agent",
        lambda: _DummyGraph(
            result={"tools_called": [], "messages": [SimpleNamespace(content="not-ai")]}
        ),
    )

    agent = agent_mod.HRAgentLangGraph("alex.kim@acme.com", session_id="session-2")

    assert agent.chat("Need help") == "I'm sorry, I couldn't process your request."


def test_hr_agent_chat_returns_error_message_when_graph_raises(
    monkeypatch, fake_messages
):
    monkeypatch.setattr(agent_mod, "get_employee_service", _mock_employee_service)
    monkeypatch.setattr(agent_mod, "get_langfuse_handler", lambda: None)
    monkeypatch.setattr(
        agent_mod,
        "compile_hr_agent",
        lambda: _DummyGraph(error=RuntimeError("graph exploded")),
    )

    errors: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        agent_mod.logger,
        "error",
        lambda message, **kwargs: errors.append((message, kwargs)),
    )

    agent = agent_mod.HRAgentLangGraph("alex.kim@acme.com", session_id="session-3")

    assert agent.chat("Need help") == "An error occurred: graph exploded"
    assert errors == [("Agent chat error", {"error": "graph exploded"})]


def test_run_hr_agent_loads_prior_turns_before_chat(monkeypatch):
    calls: dict[str, object] = {}

    class FakeAgent:
        def __init__(self, user_email: str, session_id: str | None = None, trace_metadata=None):
            calls["init"] = {
                "user_email": user_email,
                "session_id": session_id,
                "trace_metadata": trace_metadata,
            }

        def load_history_from_turns(self, turns):
            calls["prior_turns"] = turns

        def chat(self, question: str) -> str:
            calls["question"] = question
            return "final-answer"

    monkeypatch.setattr(agent_mod, "HRAgentLangGraph", FakeAgent)

    result = agent_mod.run_hr_agent(
        user_email="alex.kim@acme.com",
        question="What happened last time?",
        session_id="session-77",
        prior_turns=[{"query": "Hello", "response": "Hi"}],
    )

    assert result == "final-answer"
    assert calls["init"] == {
        "user_email": "alex.kim@acme.com",
        "session_id": "session-77",
        "trace_metadata": None,
    }
    assert calls["prior_turns"] == [{"query": "Hello", "response": "Hi"}]
    assert calls["question"] == "What happened last time?"
