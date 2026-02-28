from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_module(rel_path: str, module_name: str):
    module_path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generate_is_deterministic_for_same_seed():
    mod = _load_module("evals/generate_dataset_standalone.py", "gen_ds_standalone")

    cases_a = mod.generate(60, seed=123)
    cases_b = mod.generate(60, seed=123)

    assert cases_a == cases_b


def test_generate_case_count_and_basic_distribution():
    mod = _load_module("evals/generate_dataset_standalone.py", "gen_ds_standalone_dist")

    n = 100
    cases = mod.generate(n, seed=7)

    assert len(cases) == n

    func = sum(1 for c in cases if c["id"].startswith("gen_func_"))
    edge = sum(1 for c in cases if c["id"].startswith("gen_edge_"))
    bias = sum(1 for c in cases if c["id"].startswith("gen_bias_"))

    assert func == 70
    assert edge == 20
    assert bias == 10


def test_generate_case_schema_and_unique_ids():
    mod = _load_module("evals/generate_dataset_standalone.py", "gen_ds_standalone_schema")

    cases = mod.generate(40, seed=99)

    required_keys = {
        "id",
        "category",
        "difficulty",
        "user_email",
        "query",
        "expected_tools",
        "expected_answer_contains",
        "expected_answer_not_contains",
        "alternate_tools",
        "alternate_answer_contains",
        "should_be_denied",
        "description",
    }

    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))

    for case in cases:
        assert required_keys.issubset(case.keys())
        assert isinstance(case["expected_tools"], list)
        assert isinstance(case["alternate_answer_contains"], list)
        assert isinstance(case["should_be_denied"], bool)


def test_main_writes_expected_json_payload(tmp_path, monkeypatch):
    mod = _load_module("evals/generate_dataset_standalone.py", "gen_ds_standalone_main")

    out = tmp_path / "generated.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_dataset_standalone.py", "--out", str(out), "--n", "25", "--seed", "5"],
    )

    rc = mod.main()

    assert rc == 0
    assert out.exists()

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["count"] == 25
    assert len(payload["cases"]) == 25
    assert payload["name"] == "hr_eval_generated_1000"
