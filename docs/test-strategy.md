# HR Agent Test Strategy

## Purpose

This document defines a practical, understandable testing strategy for the `hr-agent` repository.  
It separates deterministic software correctness tests from LLM behavior evaluation and provides a phased rollout plan.

## Current State (Baseline)

As of March 1, 2026:

- Automated tests exist but are narrow in scope:
  - `tests/test_validation_and_security.py`
  - `tests/test_generate_dataset_standalone.py`
- `pytest` baseline: `9 passed`
- Coverage baseline (approx): `42%`
- Major coverage gaps:
  - `apps/api/server.py` (very low/none)
  - `hr_agent/agent/langgraph_agent.py` (low)
  - `hr_agent/services/*` and `hr_agent/repositories/*` (low)
- CI currently runs `uv run pytest` in a single Windows job.

## Testing Principles

- Test business-critical logic deterministically first.
- Keep LLM-based evaluation as a separate quality/regression signal.
- Prefer small, fast tests for PR confidence.
- Cover authorization behavior with explicit allow/deny matrices.
- Use realistic integration tests with SQLite for service/repository confidence.

## Test Pyramid for This Repo

### Layer A: Unit Tests (Fast, deterministic, no DB/LLM)

Focus on pure logic and control flow:

- `hr_agent/policies/policy_engine.py`
- `hr_agent/utils/validation.py`
- `hr_agent/utils/security.py`
- LangGraph node logic in `hr_agent/agent/langgraph_agent.py` (with mocks)

Primary goal: verify logic branches, error handling, and policy decisions without external dependencies.

### Layer B: Service + Repository Integration Tests (SQLite)

Focus on business rules and SQL behavior:

- `hr_agent/services/base.py`
- `hr_agent/repositories/*.py`
- `hr_agent/seed.py` (fixture-driven setup)

Primary goal: ensure DB-backed behavior matches expected HR workflows.

### Layer C: API Contract Tests (FastAPI TestClient)

Focus on API behavior and endpoint contracts:

- `apps/api/server.py`
- Authentication header handling
- Session lifecycle (`/sessions`)
- Error mapping and status codes
- Rate limit responses and headers

Primary goal: ensure stable, predictable API behavior for clients.

### Layer D: LLM Evaluation & Regression (Existing `evals/`)

Focus on model/tool-selection and answer quality:

- `evals/runner.py`
- `evals/test_suites.py`
- `evals/runners/run_evals.py`

Primary goal: detect agent quality drift.  
Note: these are not substitutes for deterministic tests.

## Priority Plan

## P0 (Do First)

1. Agent authorization + routing tests
2. Policy matrix tests from `policies.yaml`
3. Holiday workflow tests (`submit`, `approve`, `reject`, overlaps, invalid dates)
4. API endpoint tests for `/chat`, `/me`, `/sessions/*`

## P1 (Next)

1. Repository edge cases (empty sets, nulls, missing IDs)
2. Security behavior (minute/hour limits, audit query filters)
3. Config branches (Langfuse enabled/disabled)

## P2 (Then)

1. Streamlit helper unit tests (pure helpers only)
2. Expanded eval suite automation and trend tracking

## Recommended Test File Structure

```text
tests/
  conftest.py
  unit/
    test_policy_engine.py
    test_langgraph_nodes.py
    test_validation.py
    test_security.py
  integration/
    test_holiday_service.py
    test_employee_repository.py
    test_compensation_repository.py
  api/
    test_chat_endpoints.py
    test_sessions_endpoints.py
```

## Key Scenarios to Cover

### Authorization Matrix (Must Be Explicit)

- Employee can access own compensation
- Employee cannot access another employee’s compensation
- Manager can approve direct report requests
- Manager cannot approve non-report requests
- HR can access broad compensation actions
- Unknown actions default to deny

### Holiday Workflow Integrity

- Reject invalid date formats
- Reject past dates
- Reject overlapping requests
- Reject insufficient balance
- Approve/reject only when request is pending and manager is valid

### API Reliability

- Missing/invalid `X-User-Email` handling
- Session ownership checks (403 on foreign session)
- Correct status codes for known errors
- `Retry-After` header on rate limit

## CI Strategy

## Short-Term

- Keep current PR check, but split into:
  - Deterministic tests (required)
  - Eval smoke run (optional/non-blocking initially)

## Medium-Term

- Add coverage enforcement:
  - Initial threshold: `>=55%`
  - Raise target gradually: `>=70%`
- Run deterministic suite on every PR and merge to `main`
- Run larger eval suites on schedule or on-demand

## Tooling and Commands

### Deterministic tests

```bash
uv run pytest -vv
```

### Coverage

```bash
uv run pytest --cov=hr_agent --cov=apps --cov-report=term-missing
```

### Eval smoke

```bash
uv run python evals/runners/run_evals.py --quick --verbose
```

## Definition of Done (Testing)

A PR is considered test-complete when:

1. New/changed behavior has deterministic tests.
2. Authorization-impacting changes include explicit allow/deny test cases.
3. API changes include endpoint contract tests.
4. All required CI checks pass.
5. Coverage trend does not regress for touched critical modules.

## Ownership Model (Suggested)

- Policy and auth tests: backend/agent owners
- Service/repository integration tests: data/backend owners
- API contract tests: platform/backend owners
- Eval suites and thresholds: AI/ML owners with backend support

## Notes

- Keep eval failures actionable by attaching case IDs and expected tool/answer metadata.
- Prefer mocking LLM/tool bindings for unit tests to avoid flaky behavior.
- Use test fixtures to isolate DB state per test module or per test case.
