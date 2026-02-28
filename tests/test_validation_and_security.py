from __future__ import annotations

import importlib.util
from datetime import date, timedelta
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


def test_validate_email_normalizes_and_validates():
    mod = _load_module("hr_agent/utils/validation.py", "validation_mod")

    result = mod.Validators.validate_email("  Alex.Kim@ACME.com ")

    assert result.is_valid is True
    assert result.sanitized_value == "alex.kim@acme.com"


def test_validate_date_range_rejects_past_start_date():
    mod = _load_module("hr_agent/utils/validation.py", "validation_mod_dates")

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    result = mod.Validators.validate_date_range(yesterday, tomorrow, allow_past=False)

    assert result.is_valid is False
    assert "past" in result.error_message.lower()


def test_validate_days_rounds_to_half_day():
    mod = _load_module("hr_agent/utils/validation.py", "validation_mod_days")

    result = mod.Validators.validate_days(2.74)

    assert result.is_valid is True
    assert result.sanitized_value == 2.5


def test_rate_limiter_enforces_burst_limit():
    mod = _load_module("hr_agent/utils/security.py", "security_mod")

    limiter = mod.RateLimiter(
        mod.RateLimitConfig(requests_per_minute=1000, requests_per_hour=1000, burst_limit=2)
    )

    allowed_1, _ = limiter.is_allowed("user-1")
    allowed_2, _ = limiter.is_allowed("user-1")
    allowed_3, info_3 = limiter.is_allowed("user-1")

    assert allowed_1 is True
    assert allowed_2 is True
    assert allowed_3 is False
    assert info_3["reason"] == "burst_limit_exceeded"


def test_sensitive_action_mapping_and_masking_helpers():
    mod = _load_module("hr_agent/utils/security.py", "security_mod_helpers")

    assert mod.is_sensitive_action("get_compensation") is True
    assert mod.is_sensitive_action("get_company_policies") is False
    assert mod.get_sensitive_data_type("get_salary_history") == mod.SensitiveDataType.COMPENSATION
    assert mod.mask_email("ab@acme.com") == "a*@acme.com"
