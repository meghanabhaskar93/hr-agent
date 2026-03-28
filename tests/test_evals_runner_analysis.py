from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module(module_name: str, relative_path: str):
    module_path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _bootstrap_evals_package():
    package = types.ModuleType("evals")
    package.__path__ = [str(ROOT / "evals")]

    fake_config = types.ModuleType("hr_agent.configs.config")
    fake_config.get_langfuse_client = lambda: None

    sys.modules["evals"] = package
    sys.modules["hr_agent.configs.config"] = fake_config
    metrics = _load_module("evals.metrics", "evals/metrics.py")
    datasets = _load_module("evals.datasets", "evals/datasets.py")
    logger = _load_module("evals.logger", "evals/logger.py")
    analysis = _load_module("evals.analysis", "evals/analysis.py")
    runner = _load_module("evals.runner", "evals/runner.py")

    package.metrics = metrics
    package.datasets = datasets
    package.logger = logger
    package.analysis = analysis
    package.runner = runner

    return analysis, datasets, logger, metrics, runner


def _load_runner_module_expect_import_error():
    package = types.ModuleType("evals")
    package.__path__ = [str(ROOT / "evals")]
    sys.modules["evals"] = package
    metrics = _load_module("evals.metrics", "evals/metrics.py")
    datasets = _load_module("evals.datasets", "evals/datasets.py")
    logger = _load_module("evals.logger", "evals/logger.py")
    package.metrics = metrics
    package.datasets = datasets
    package.logger = logger

    fake_agent_module = types.ModuleType("hr_agent.agent.langgraph_agent")
    fake_agent_module.HRAgentLangGraph = object
    sys.modules["hr_agent.agent.langgraph_agent"] = fake_agent_module

    module_path = ROOT / "evals" / "runner.py"
    spec = importlib.util.spec_from_file_location("evals.runner_import_check", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)

    with pytest.raises(ImportError, match="get_langfuse_client"):
        spec.loader.exec_module(module)


analysis_mod, datasets_mod, logger_mod, metrics_mod, runner_mod = _bootstrap_evals_package()

compare_runs = analysis_mod.compare_runs
generate_report = analysis_mod.generate_report
load_results = analysis_mod.load_results
plot_results = analysis_mod.plot_results
EvalCase = datasets_mod.EvalCase
EvalDataset = datasets_mod.EvalDataset
LogLevel = logger_mod.LogLevel
EvalCategory = metrics_mod.EvalCategory
EvalDifficulty = metrics_mod.EvalDifficulty
EvalMetrics = metrics_mod.EvalMetrics
EvalResult = metrics_mod.EvalResult
EvalRunner = runner_mod.EvalRunner
run_evals = runner_mod.run_evals


def test_runner_import_surfaces_missing_langfuse_client_symbol():
    _load_runner_module_expect_import_error()


def _case(case_id: str, *, denied: bool = False) -> EvalCase:
    return EvalCase(
        id=case_id,
        category=EvalCategory.AUTHORIZATION if denied else EvalCategory.EMPLOYEE_INFO,
        difficulty=EvalDifficulty.HARD if denied else EvalDifficulty.EASY,
        user_email="alex.kim@acme.com",
        query=f"query {case_id}",
        expected_tools=["tool_a"] if not denied else [],
        expected_answer_contains=["answer"] if not denied else ["not authorized"],
        should_be_denied=denied,
    )


def _result(case_id: str, *, passed: bool, latency_ms: float, steps: int, error: str | None = None) -> EvalResult:
    return EvalResult(
        case_id=case_id,
        category=EvalCategory.EMPLOYEE_INFO,
        difficulty=EvalDifficulty.EASY,
        query=f"query {case_id}",
        expected_tools=["tool_a"],
        expected_answer_contains=["answer"],
        passed=passed,
        tool_selection_correct=passed,
        answer_correct=passed,
        authorization_correct=passed,
        tools_called=["tool_a"] if passed else [],
        latency_ms=latency_ms,
        num_steps=steps,
        error=error,
    )


class _SilentLogger:
    def __init__(self):
        self.saved_output_dir: str | None = None
        self.errors: list[str] = []

    def start_run(self, **kwargs):
        self.start_kwargs = kwargs

    def end_run(self, metrics):
        self.ended_with = metrics

    def start_case(self, case):
        pass

    def end_case(self, result):
        pass

    def error(self, message):
        self.errors.append(message)

    def save_results(self, output_dir):
        self.saved_output_dir = output_dir


class _FakeLangfuseClient:
    def __init__(self):
        self.scores: list[dict] = []
        self.flushed = False

    def create_score(self, **kwargs):
        self.scores.append(kwargs)

    def flush(self):
        self.flushed = True


def test_eval_runner_helper_methods_cover_edge_cases():
    runner = EvalRunner(dataset=EvalDataset(name="d", cases=[]), log_level=LogLevel.QUIET)

    assert runner._is_rate_limit_error("Error code: 429 Too many requests")
    assert not runner._is_rate_limit_error("permission denied")

    assert runner._evaluate_tool_selection(["tool_a"], ["tool_a", "tool_b"])
    assert runner._evaluate_tool_selection(["missing"], ["alt_tool"], [["alt_tool"]])
    assert runner._evaluate_tool_selection([], [], [])
    assert not runner._evaluate_tool_selection(["missing"], ["other"], [])

    assert runner._evaluate_answer("The answer is present", ["answer"], [], [])
    assert runner._evaluate_answer("Alternative route", ["missing"], [], [["route"]])
    assert runner._evaluate_answer("Clean response", [], [], [])
    assert not runner._evaluate_answer("Contains secret", ["secret"], ["secret"], [])
    assert not runner._evaluate_answer("Nothing useful", ["expected"], [], [])

    assert runner._check_access_denied("You are not authorized to view this.")
    assert runner._check_access_denied("You can only view your own salary.")
    assert not runner._check_access_denied("Here is the current holiday balance.")


def test_run_single_case_success_and_langfuse_metrics(monkeypatch):
    client = _FakeLangfuseClient()
    agent_calls: list[tuple[str, str]] = []

    class FakeAgent:
        def __init__(self, user_email, session_id=None, trace_metadata=None):
            self.tools_called = ["tool_a"]
            agent_calls.append((user_email, session_id))

        def chat(self, query):
            return "Answer with answer keyword"

    monkeypatch.setattr("evals.runner.HRAgentLangGraph", FakeAgent)
    monkeypatch.setattr("evals.runner.get_langfuse_client", lambda: client)

    runner = EvalRunner(
        dataset=EvalDataset(name="sample", cases=[]),
        log_level=LogLevel.QUIET,
        batch_tag="batch-1",
    )

    result = runner._run_single_case(_case("c1"))

    assert result.passed is True
    assert result.tool_selection_correct is True
    assert result.answer_correct is True
    assert result.authorization_correct is True
    assert result.tools_called == ["tool_a"]
    assert result.num_steps == 1
    assert agent_calls == [("alex.kim@acme.com", "eval_c1")]
    assert len(client.scores) == 6
    assert {score["name"] for score in client.scores} == {
        "eval_pass",
        "eval_tool_selection",
        "eval_answer_quality",
        "eval_authorization",
        "eval_latency_ms",
        "eval_steps",
    }


def test_run_single_case_retries_on_rate_limit_and_denial_check(monkeypatch):
    client = _FakeLangfuseClient()
    attempts = {"count": 0}
    sleeps: list[float] = []

    class FakeAgent:
        def __init__(self, user_email, session_id=None, trace_metadata=None):
            self.tools_called = []

        def chat(self, query):
            attempts["count"] += 1
            if attempts["count"] == 1:
                return "Error code: 429 Too many requests"
            return "Access denied. You are not authorized."

    monkeypatch.setattr("evals.runner.HRAgentLangGraph", FakeAgent)
    monkeypatch.setattr("evals.runner.get_langfuse_client", lambda: client)
    monkeypatch.setattr("evals.runner.time.sleep", lambda delay: sleeps.append(delay))
    monkeypatch.setattr("evals.runner.random.random", lambda: 0.0)

    runner = EvalRunner(dataset=EvalDataset(name="sample", cases=[]), log_level=LogLevel.QUIET)

    result = runner._run_single_case(_case("denied", denied=True))

    assert attempts["count"] == 2
    assert sleeps == [1.0]
    assert result.passed is True
    assert result.authorization_correct is True
    assert result.answer_correct is True


def test_run_single_case_sets_error_on_terminal_exception(monkeypatch):
    class FakeAgent:
        def __init__(self, user_email, session_id=None, trace_metadata=None):
            self.tools_called = []

        def chat(self, query):
            raise ValueError("boom")

    monkeypatch.setattr("evals.runner.HRAgentLangGraph", FakeAgent)
    monkeypatch.setattr("evals.runner.get_langfuse_client", lambda: None)

    runner = EvalRunner(dataset=EvalDataset(name="sample", cases=[]), log_level=LogLevel.QUIET)

    result = runner._run_single_case(_case("bad"))

    assert result.passed is False
    assert result.error == "boom"


def test_run_parallel_preserves_order_and_wraps_future_failures(monkeypatch):
    dataset = EvalDataset(name="parallel", cases=[_case("first"), _case("second")])
    runner = EvalRunner(dataset=dataset, parallel=True, log_level=LogLevel.QUIET)
    runner.logger = _SilentLogger()

    def fake_run_single(case):
        if case.id == "second":
            raise RuntimeError("failed worker")
        return _result(case.id, passed=True, latency_ms=10.0, steps=1)

    monkeypatch.setattr(runner, "_run_single_case", fake_run_single)

    runner._run_parallel()

    assert [result.case_id for result in runner.results] == ["first", "second"]
    assert runner.results[0].passed is True
    assert runner.results[1].passed is False
    assert runner.results[1].error == "failed worker"
    assert runner.logger.errors == ["Execution failed for second: failed worker"]


def test_eval_runner_run_logs_summary_scores(monkeypatch):
    client = _FakeLangfuseClient()
    dataset = EvalDataset(name="runset", cases=[_case("one"), _case("two")])
    runner = EvalRunner(dataset=dataset, log_level=LogLevel.QUIET, batch_tag="batch-z")
    runner.logger = _SilentLogger()

    monkeypatch.setattr("evals.runner.get_langfuse_client", lambda: client)
    monkeypatch.setattr(
        runner,
        "_run_sequential",
        lambda: runner.results.extend(
            [
                _result("one", passed=True, latency_ms=100.0, steps=1),
                _result("two", passed=False, latency_ms=200.0, steps=2, error="oops"),
            ]
        ),
    )

    metrics = runner.run()

    assert metrics.total_cases == 2
    assert runner.logger.start_kwargs["dataset_name"] == "runset (LangGraph Agent)"
    assert runner.logger.ended_with is metrics
    assert len(client.scores) == 7
    assert client.flushed is True
    assert {score["name"] for score in client.scores} == {
        "eval_pass_rate",
        "eval_tool_selection_accuracy",
        "eval_answer_accuracy",
        "eval_authorization_compliance",
        "eval_avg_latency_ms",
        "eval_p95_latency_ms",
        "eval_avg_steps",
    }


def test_run_evals_writes_summary_results_and_logger_output(tmp_path, monkeypatch):
    metrics = EvalMetrics(results=[_result("one", passed=True, latency_ms=123.0, steps=2)])

    class FakeRunner:
        instances: list["FakeRunner"] = []

        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.logger = _SilentLogger()
            FakeRunner.instances.append(self)

        def run(self):
            return metrics

    monkeypatch.setattr("evals.runner.EvalRunner", FakeRunner)

    returned = run_evals(
        dataset=EvalDataset(name="saved", cases=[_case("one")]),
        parallel=False,
        verbose=True,
        log_level=LogLevel.NORMAL,
        save_results=True,
        output_dir=str(tmp_path),
    )

    assert returned is metrics
    summary_files = list(tmp_path.glob("eval_summary_*.json"))
    result_files = list(tmp_path.glob("eval_results_*.json"))
    assert len(summary_files) == 1
    assert len(result_files) == 1
    assert json.loads(summary_files[0].read_text())["pass_rate"] == 100.0
    assert json.loads(result_files[0].read_text())[0]["case_id"] == "one"
    assert FakeRunner.instances[0].logger.saved_output_dir == str(tmp_path)


def test_load_results_generate_report_compare_runs_and_plot_skip(tmp_path, monkeypatch, capsys):
    results_dir = tmp_path / "eval_results"
    results_dir.mkdir()

    older = results_dir / "eval_results_20260321_100000.json"
    newer = results_dir / "eval_results_20260321_110000.json"
    older.write_text("[]", encoding="utf-8")
    newer.write_text(
        json.dumps(
            [
                {
                    "case_id": "r1",
                    "category": "employee_info",
                    "difficulty": "easy",
                    "query": "What is my title?",
                    "expected_tools": ["tool_a"],
                    "passed": True,
                    "tool_selection_correct": True,
                    "answer_correct": True,
                    "authorization_correct": True,
                    "num_steps": 2,
                    "latency_ms": 55.0,
                    "tools_called": ["tool_a"],
                }
            ]
        ),
        encoding="utf-8",
    )
    newer.touch()

    loaded = load_results(str(results_dir))
    assert len(loaded) == 1
    assert loaded[0].case_id == "r1"
    assert loaded[0].category == EvalCategory.EMPLOYEE_INFO

    metrics = EvalMetrics(
        results=[
            _result("one", passed=True, latency_ms=100.0, steps=1),
            _result("two", passed=False, latency_ms=200.0, steps=3, error="bad answer"),
        ]
    )
    report_path = Path(generate_report(metrics, str(results_dir)))
    assert report_path.exists()
    report_html = report_path.read_text(encoding="utf-8")
    assert "HR Agent Evaluation Report" in report_html
    assert "Answer validation failed" in report_html or "bad answer" in report_html

    (results_dir / "eval_summary_20260321_100000.json").write_text(
        json.dumps(
            {
                "pass_rate": 70.0,
                "tool_selection_accuracy": 80.0,
                "answer_accuracy": 75.0,
                "avg_latency_ms": 150.0,
            }
        ),
        encoding="utf-8",
    )
    (results_dir / "eval_summary_20260321_110000.json").write_text(
        json.dumps(
            {
                "pass_rate": 90.0,
                "tool_selection_accuracy": 82.0,
                "answer_accuracy": 78.0,
                "avg_latency_ms": 120.0,
            }
        ),
        encoding="utf-8",
    )

    comparison = compare_runs(str(results_dir))
    assert comparison["latest_run"] == "20260321_110000"
    assert comparison["changes"]["pass_rate"]["direction"] == "↑"
    assert comparison["changes"]["avg_latency_ms"]["direction"] == "↓"

    monkeypatch.setattr("evals.analysis.HAS_MATPLOTLIB", False)
    plot_results(metrics, str(results_dir))
    assert "matplotlib not installed, skipping plots" in capsys.readouterr().out


def test_load_results_and_compare_runs_handle_missing_inputs(tmp_path):
    missing = tmp_path / "missing"
    assert load_results(str(missing)) == []
    assert compare_runs(str(missing)) == {}

    one_run = tmp_path / "one_run"
    one_run.mkdir()
    (one_run / "eval_summary_20260321_100000.json").write_text(
        json.dumps({"pass_rate": 80.0, "tool_selection_accuracy": 80.0, "answer_accuracy": 80.0, "avg_latency_ms": 100.0}),
        encoding="utf-8",
    )
    assert compare_runs(str(one_run)) == {"message": "Need at least 2 runs to compare"}
