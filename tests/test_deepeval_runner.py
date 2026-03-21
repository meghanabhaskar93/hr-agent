from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

from evals.datasets import EvalCase, EvalDataset
from evals.metrics import EvalCategory, EvalDifficulty


ROOT = Path(__file__).resolve().parents[1]


def _load_deepeval_runner_module():
    module_name = "test_deepeval_runner_module"
    module_path = ROOT / "evals" / "deepeval_runner.py"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None

    fake_deepeval = types.ModuleType("deepeval")
    fake_deepeval.assert_test = lambda *args, **kwargs: None

    fake_metrics = types.ModuleType("deepeval.metrics")

    class FakeFaithfulnessMetric:
        def __init__(self, model=None):
            self.model = model

        def measure(self, test_case):
            return types.SimpleNamespace(score=0.9)

    class FakeToxicityMetric:
        def measure(self, test_case):
            return types.SimpleNamespace(score=0.0)

    fake_metrics.FaithfulnessMetric = FakeFaithfulnessMetric
    fake_metrics.ToxicityMetric = FakeToxicityMetric

    fake_models = types.ModuleType("deepeval.models")

    class FakeDeepEvalBaseLLM:
        pass

    fake_models.DeepEvalBaseLLM = FakeDeepEvalBaseLLM

    fake_test_case = types.ModuleType("deepeval.test_case")

    class FakeLLMTestCase:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    fake_test_case.LLMTestCase = FakeLLMTestCase

    previous = {
        name: sys.modules.get(name)
        for name in ["deepeval", "deepeval.metrics", "deepeval.models", "deepeval.test_case"]
    }
    sys.modules["deepeval"] = fake_deepeval
    sys.modules["deepeval.metrics"] = fake_metrics
    sys.modules["deepeval.models"] = fake_models
    sys.modules["deepeval.test_case"] = fake_test_case

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        for name, old in previous.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old

    return module


def _dataset() -> EvalDataset:
    return EvalDataset(
        name="eval_ds",
        cases=[
            EvalCase(
                id="pass-case",
                category=EvalCategory.EMPLOYEE_INFO,
                difficulty=EvalDifficulty.EASY,
                user_email="alex.kim@acme.com",
                query="pass query",
                expected_tools=["tool_a"],
                expected_answer_contains=["answer"],
            ),
            EvalCase(
                id="auth-case",
                category=EvalCategory.AUTHORIZATION,
                difficulty=EvalDifficulty.HARD,
                user_email="alex.kim@acme.com",
                query="auth query",
                expected_tools=[],
                expected_answer_contains=["denied"],
                should_be_denied=True,
            ),
            EvalCase(
                id="tool-case",
                category=EvalCategory.COMPENSATION,
                difficulty=EvalDifficulty.MEDIUM,
                user_email="alex.kim@acme.com",
                query="tool query",
                expected_tools=["needed_tool"],
                expected_answer_contains=["answer"],
            ),
        ],
    )


def test_deepeval_helper_functions_and_load_dataset():
    mod = _load_deepeval_runner_module()

    assert mod._is_access_denied("You are not authorized to view this")
    assert not mod._is_access_denied("Here is your holiday balance")
    assert mod._tool_selection_ok([], [])
    assert mod._tool_selection_ok(["tool_a"], ["tool_a", "tool_b"])
    assert not mod._tool_selection_ok(["tool_a"], ["tool_b"])

    default_dataset = mod._load_dataset("default")
    assert default_dataset.name == "hr_eval_v1"

    with pytest.raises(ValueError, match="Unknown dataset"):
        mod._load_dataset("unknown")


def test_run_deepeval_exports_results_and_langfuse_scores(tmp_path, monkeypatch):
    mod = _load_deepeval_runner_module()
    dataset = _dataset()
    export_path = tmp_path / "deepeval.json"

    class FakeAgent:
        def __init__(self, user_email, session_id=None, trace_metadata=None):
            self.session_id = session_id
            self.trace_metadata = trace_metadata
            self.tools_called = []

        def chat(self, query):
            if query == "pass query":
                self.tools_called = ["tool_a"]
                return "helpful answer"
            if query == "auth query":
                self.tools_called = []
                return "Access denied. You do not have permission."
            self.tools_called = ["wrong_tool"]
            return "helpful answer"

    class FakeClient:
        def __init__(self):
            self.scores = []
            self.flushed = False

        def create_score(self, **kwargs):
            self.scores.append(kwargs)

        def flush(self):
            self.flushed = True

    client = FakeClient()
    monkeypatch.setitem(sys.modules, "hr_agent.agent.langgraph_agent", types.SimpleNamespace(HRAgentLangGraph=FakeAgent))
    monkeypatch.setattr(mod, "get_langfuse_client", lambda: client)

    outcomes = mod.run_deepeval(
        dataset=dataset,
        sample=2,
        seed=1,
        sample_offset=0,
        use_llm_metrics=False,
        export_json=str(export_path),
    )

    assert len(outcomes) == 2
    reasons = {outcome.case_id: outcome.reason for outcome in outcomes}
    assert set(reasons.values()).issubset({"pass", "authorization", "tool_selection"})
    assert export_path.exists()
    exported = json.loads(export_path.read_text(encoding="utf-8"))
    assert len(exported) == 2
    assert client.flushed is True
    assert len(client.scores) >= 6


def test_deepeval_main_summarizes_and_returns_nonzero(monkeypatch, capsys):
    mod = _load_deepeval_runner_module()

    monkeypatch.setattr(mod, "_load_dataset", lambda name: EvalDataset(name="chosen", cases=[]))
    monkeypatch.setattr(
        mod,
        "run_deepeval",
        lambda **kwargs: [
            mod.CaseOutcome(case_id="a", category="employee_info", passed=True, reason="pass"),
            mod.CaseOutcome(case_id="b", category="authorization", passed=False, reason="authorization"),
            mod.CaseOutcome(case_id="c", category="compensation", passed=False, reason="tool_selection"),
        ],
    )

    rc = mod.main(["--dataset", "default", "--sample", "3", "--seed", "2"])

    out = capsys.readouterr().out
    assert rc == 1
    assert "Dataset: chosen" in out
    assert "Passed: 1/3 (33.3%)" in out
    assert "authorization: 1" in out
    assert "tool_selection: 1" in out
    assert "Failed case_ids:" in out


def test_databricks_llm_generate_and_helpers(monkeypatch):
    mod = _load_deepeval_runner_module()

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "grader output"}}]}

    class RequestsModule:
        @staticmethod
        def post(url, headers=None, json=None, timeout=None):
            return Response()

    monkeypatch.setitem(sys.modules, "requests", RequestsModule)

    llm = mod.DatabricksLLM("grader-model", "https://example.com", "secret")
    assert llm.generate("prompt") == "grader output"
    assert llm.load_model() is llm
    assert llm.get_model_name() == "grader-model"

    with pytest.raises(NotImplementedError):
        import asyncio

        asyncio.run(llm.a_generate("prompt"))
