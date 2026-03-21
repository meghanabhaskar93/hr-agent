from __future__ import annotations

import importlib
from pathlib import Path

from evals.metrics import EvalCategory, EvalDifficulty


def test_generate_cases_distribution_and_edge_properties():
    mod = importlib.import_module("evals.generate_dataset")

    cases = mod.generate_cases(20, seed=5)

    assert len(cases) == 20
    assert sum(1 for c in cases if c.id.startswith("gen_func_")) == 14
    assert sum(1 for c in cases if c.id.startswith("gen_edge_")) == 4
    assert sum(1 for c in cases if c.id.startswith("gen_bias_")) == 2

    edge_cases = [c for c in cases if c.id.startswith("gen_edge_")]
    assert edge_cases
    for case in edge_cases:
        assert case.difficulty == EvalDifficulty.HARD
        if case.category == EvalCategory.AUTHORIZATION:
            assert case.should_be_denied is True
            assert case.expected_tools == []
        else:
            assert case.category == EvalCategory.EDGE_CASES

    bias_cases = [c for c in cases if c.id.startswith("gen_bias_")]
    assert bias_cases
    for case in bias_cases:
        assert case.category == EvalCategory.EDGE_CASES
        assert "sure" in case.expected_answer_not_contains


def test_pick_phrase_variation_case_id_and_write_dataset(tmp_path):
    mod = importlib.import_module("evals.generate_dataset")
    rng = mod.random.Random(1)

    variation = mod._pick_phrase_variation("PTO holiday for my team", rng)
    assert isinstance(variation, str)
    assert variation
    assert mod._case_id("func", 12) == "gen_func_0012"

    cases = mod.generate_cases(3, seed=3)
    out_path = tmp_path / "generated_dataset.py"
    mod.write_dataset_py(str(out_path), cases, name="custom_eval")

    contents = out_path.read_text(encoding="utf-8")
    assert "AUTO-GENERATED DATASET - DO NOT EDIT MANUALLY" in contents
    assert "GENERATED_DATASET_1000 = EvalDataset(name='custom_eval', cases=GENERATED_CASES)" in contents
    assert "EvalCategory." in contents
    assert "alternate_answer_contains" in contents


def test_generate_dataset_main_writes_file_and_returns_zero(tmp_path, capsys):
    mod = importlib.import_module("evals.generate_dataset")
    out_path = tmp_path / "synthetic.py"

    rc = mod.main(["--out", str(out_path), "--n", "12", "--seed", "9", "--name", "batch"])

    assert rc == 0
    assert out_path.exists()
    assert "Wrote 12 cases to" in capsys.readouterr().out
    assert "batch" in out_path.read_text(encoding="utf-8")
