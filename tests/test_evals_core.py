from __future__ import annotations

from datetime import datetime
import importlib
import sys

import pytest

from evals.datasets import (
    HR_EVAL_CASES,
    EvalCase,
    EvalDataset,
    get_default_dataset,
    get_quick_dataset,
)
from evals.metrics import EvalCategory, EvalDifficulty, EvalMetrics, EvalResult


def _make_result(
    *,
    case_id: str,
    category: EvalCategory = EvalCategory.EMPLOYEE_INFO,
    difficulty: EvalDifficulty = EvalDifficulty.EASY,
    passed: bool = True,
    tool_selection_correct: bool = True,
    answer_correct: bool = True,
    authorization_correct: bool = True,
    latency_ms: float = 100.0,
    num_steps: int = 1,
    error: str | None = None,
) -> EvalResult:
    return EvalResult(
        case_id=case_id,
        category=category,
        difficulty=difficulty,
        query=f"query {case_id}",
        expected_tools=["tool_a"],
        expected_answer_contains=["answer"],
        passed=passed,
        tool_selection_correct=tool_selection_correct,
        answer_correct=answer_correct,
        authorization_correct=authorization_correct,
        tools_called=["tool_a"],
        latency_ms=latency_ms,
        num_steps=num_steps,
        error=error,
    )


def test_eval_result_to_dict_serializes_enums_and_timestamp():
    result = EvalResult(
        case_id="case-1",
        category=EvalCategory.AUTHORIZATION,
        difficulty=EvalDifficulty.HARD,
        query="Can I see payroll?",
        expected_tools=["get_compensation"],
        expected_answer_contains=["denied"],
        passed=False,
        tool_selection_correct=True,
        answer_correct=False,
        authorization_correct=True,
        tools_called=["get_compensation"],
        error="permission denied",
        timestamp=datetime(2026, 3, 21, 10, 30, 0),
    )

    payload = result.to_dict()

    assert payload["category"] == "authorization"
    assert payload["difficulty"] == "hard"
    assert payload["tools_called"] == ["get_compensation"]
    assert payload["expected_tools"] == ["get_compensation"]
    assert payload["error"] == "permission denied"
    assert payload["timestamp"] == "2026-03-21T10:30:00"


def test_eval_metrics_summary_grouping_and_report():
    metrics = EvalMetrics(
        results=[
            _make_result(
                case_id="one",
                category=EvalCategory.EMPLOYEE_INFO,
                difficulty=EvalDifficulty.EASY,
                passed=True,
                tool_selection_correct=True,
                answer_correct=True,
                authorization_correct=True,
                latency_ms=100.0,
                num_steps=1,
            ),
            _make_result(
                case_id="two",
                category=EvalCategory.TIME_OFF,
                difficulty=EvalDifficulty.MEDIUM,
                passed=False,
                tool_selection_correct=False,
                answer_correct=False,
                authorization_correct=True,
                latency_ms=200.0,
                num_steps=2,
                error="tool mismatch",
            ),
            _make_result(
                case_id="three",
                category=EvalCategory.TIME_OFF,
                difficulty=EvalDifficulty.HARD,
                passed=True,
                tool_selection_correct=True,
                answer_correct=False,
                authorization_correct=False,
                latency_ms=300.0,
                num_steps=3,
            ),
        ]
    )

    assert metrics.total_cases == 3
    assert metrics.passed_cases == 2
    assert metrics.pass_rate == pytest.approx(2 / 3)
    assert metrics.tool_selection_accuracy == pytest.approx(2 / 3)
    assert metrics.answer_accuracy == pytest.approx(1 / 3)
    assert metrics.authorization_compliance == pytest.approx(2 / 3)
    assert metrics.avg_latency_ms == 200.0
    assert metrics.p50_latency_ms == 200.0
    assert metrics.p95_latency_ms == 300.0
    assert metrics.avg_steps == 2.0
    assert metrics.error_rate == pytest.approx(1 / 3)

    summary = metrics.summary()
    assert summary == {
        "total_cases": 3,
        "passed_cases": 2,
        "pass_rate": 66.7,
        "tool_selection_accuracy": 66.7,
        "answer_accuracy": 33.3,
        "authorization_compliance": 66.7,
        "avg_latency_ms": 200.0,
        "p50_latency_ms": 200.0,
        "p95_latency_ms": 300.0,
        "avg_steps": 2.0,
        "error_rate": 33.3,
    }

    by_category = metrics.by_category()
    assert set(by_category) == {EvalCategory.EMPLOYEE_INFO, EvalCategory.TIME_OFF}
    assert by_category[EvalCategory.TIME_OFF].total_cases == 2
    assert by_category[EvalCategory.TIME_OFF].passed_cases == 1

    by_difficulty = metrics.by_difficulty()
    assert set(by_difficulty) == {
        EvalDifficulty.EASY,
        EvalDifficulty.MEDIUM,
        EvalDifficulty.HARD,
    }

    report = metrics.detailed_report()
    assert "HR AGENT EVALUATION REPORT" in report
    assert "[two] query two" in report
    assert "tool mismatch" in report
    assert "time_off" in report
    assert "hard" in report


def test_eval_dataset_filters_and_helpers_return_expected_cases():
    default_dataset = get_default_dataset()
    quick_dataset = get_quick_dataset()

    assert default_dataset.name == "hr_eval_v1"
    assert default_dataset.cases is HR_EVAL_CASES
    assert quick_dataset.name == "hr_eval_quick"
    assert len(quick_dataset.cases) <= 10
    assert quick_dataset.cases
    assert all(case.difficulty == EvalDifficulty.EASY for case in quick_dataset.cases)

    dataset = EvalDataset(
        name="custom",
        cases=[
            HR_EVAL_CASES[0],
            HR_EVAL_CASES[5],
            HR_EVAL_CASES[12],
        ],
    )

    by_category = dataset.filter_by_category(EvalCategory.EMPLOYEE_INFO)
    by_difficulty = dataset.filter_by_difficulty(EvalDifficulty.EASY)

    assert by_category.name == "custom_employee_info"
    assert [case.id for case in by_category.cases] == [HR_EVAL_CASES[0].id]
    assert by_difficulty.name == "custom_easy"
    assert all(case.difficulty == EvalDifficulty.EASY for case in by_difficulty.cases)


def test_run_evals_main_uses_quick_limit_sample_and_exits_zero(monkeypatch):
    module = importlib.import_module("evals.runners.run_evals")

    cases = [
        EvalCase(
            id=f"case-{idx}",
            category=EvalCategory.EMPLOYEE_INFO,
            difficulty=EvalDifficulty.EASY,
            user_email="alex.kim@acme.com",
            query=f"query {idx}",
            expected_tools=["tool"],
            expected_answer_contains=["answer"],
        )
        for idx in range(4)
    ]
    dataset = EvalDataset(name="quick_ds", cases=cases)
    captured: dict[str, object] = {}

    class FakeRunner:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self):
            return type("Metrics", (), {"pass_rate": 0.85})()

    monkeypatch.setattr(module, "get_quick_dataset", lambda: dataset)
    monkeypatch.setattr(module, "EvalRunner", FakeRunner)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_evals.py",
            "--quick",
            "--limit",
            "3",
            "--sample",
            "2",
            "--seed",
            "11",
            "--sample-offset",
            "1",
            "--parallel",
            "--max-workers",
            "5",
            "--batch-tag",
            "smoke",
        ],
    )

    with pytest.raises(SystemExit) as excinfo:
        module.main()

    assert excinfo.value.code == 0
    runner_dataset = captured["dataset"]
    assert isinstance(runner_dataset, module.EvalDataset)
    assert runner_dataset.name == "quick_ds_limit_3_sample_2_seed_11_offset_1"
    assert len(runner_dataset.cases) == 2
    assert {case.id for case in runner_dataset.cases}.issubset({"case-0", "case-1", "case-2"})
    assert captured["parallel"] is True
    assert captured["max_workers"] == 5
    assert captured["batch_tag"] == "smoke"


def test_run_evals_main_exits_zero_for_empty_filtered_dataset(monkeypatch, capsys):
    module = importlib.import_module("evals.runners.run_evals")

    monkeypatch.setattr(
        module,
        "HR_EVAL_CASES",
        [
            EvalCase(
                id="only-comp",
                category=EvalCategory.COMPENSATION,
                difficulty=EvalDifficulty.HARD,
                user_email="mina.patel@acme.com",
                query="query",
                expected_tools=["tool"],
                expected_answer_contains=["answer"],
            )
        ],
    )
    monkeypatch.setattr(sys, "argv", ["run_evals.py", "--category", "authorization"])

    with pytest.raises(SystemExit) as excinfo:
        module.main()

    assert excinfo.value.code == 0
    assert "No test cases found for the selected criteria." in capsys.readouterr().out


def test_run_evals_main_exits_one_when_pass_rate_is_below_threshold(monkeypatch):
    module = importlib.import_module("evals.runners.run_evals")

    dataset = EvalDataset(name="default_ds", cases=HR_EVAL_CASES[:2])
    captured: dict[str, object] = {}

    class FakeRunner:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run(self):
            return type("Metrics", (), {"pass_rate": 0.79})()

    monkeypatch.setattr(module, "get_default_dataset", lambda: dataset)
    monkeypatch.setattr(module, "EvalRunner", FakeRunner)
    monkeypatch.setattr(sys, "argv", ["run_evals.py"])

    with pytest.raises(SystemExit) as excinfo:
        module.main()

    assert excinfo.value.code == 1
    assert captured["dataset"] is dataset
