"""
Input Validation Module

Centralized validation for all user inputs and API requests.
Prevents injection attacks, validates formats, and sanitizes data.
"""

import re
from datetime import datetime, date
from typing import Any, Callable
from dataclasses import dataclass


# ============================================================================
# VALIDATION RULES
# ============================================================================


@dataclass
class ValidationResult:
    """Result of a validation check."""

    is_valid: bool
    error_message: str | None = None
    sanitized_value: Any = None


class Validators:
    """Collection of reusable validators."""

    # Common patterns
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    SAFE_STRING_PATTERN = re.compile(r'^[a-zA-Z0-9\s\-_.,!?@#$%&*()\'"]+$')

    @staticmethod
    def validate_email(email: str) -> ValidationResult:
        """Validate email format."""
        if not email:
            return ValidationResult(False, "Email is required")

        email = email.strip().lower()

        if len(email) > 254:
            return ValidationResult(False, "Email is too long (max 254 characters)")

        if not Validators.EMAIL_PATTERN.match(email):
            return ValidationResult(False, "Invalid email format")

        return ValidationResult(True, sanitized_value=email)

    @staticmethod
    def validate_date(date_str: str, field_name: str = "date") -> ValidationResult:
        """Validate date format (YYYY-MM-DD)."""
        if not date_str:
            return ValidationResult(False, f"{field_name} is required")

        date_str = date_str.strip()

        if not Validators.DATE_PATTERN.match(date_str):
            return ValidationResult(False, f"{field_name} must be in YYYY-MM-DD format")

        try:
            parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
            return ValidationResult(True, sanitized_value=parsed)
        except ValueError:
            return ValidationResult(False, f"{field_name} is not a valid date")

    @staticmethod
    def validate_date_range(
        start_date: str,
        end_date: str,
        allow_past: bool = False,
        max_range_days: int = 365,
    ) -> ValidationResult:
        """Validate a date range."""
        start_result = Validators.validate_date(start_date, "start_date")
        if not start_result.is_valid:
            return start_result

        end_result = Validators.validate_date(end_date, "end_date")
        if not end_result.is_valid:
            return end_result

        start = start_result.sanitized_value
        end = end_result.sanitized_value

        if end < start:
            return ValidationResult(False, "end_date must be after start_date")

        if not allow_past and start < date.today():
            return ValidationResult(False, "start_date cannot be in the past")

        days_diff = (end - start).days
        if days_diff > max_range_days:
            return ValidationResult(
                False, f"Date range cannot exceed {max_range_days} days"
            )

        return ValidationResult(True, sanitized_value={"start": start, "end": end})

    @staticmethod
    def validate_employee_id(employee_id: Any) -> ValidationResult:
        """Validate employee ID."""
        if employee_id is None:
            return ValidationResult(False, "Employee ID is required")

        try:
            emp_id = int(employee_id)
            if emp_id <= 0:
                return ValidationResult(False, "Employee ID must be positive")
            if emp_id > 999999:
                return ValidationResult(False, "Employee ID is too large")
            return ValidationResult(True, sanitized_value=emp_id)
        except (ValueError, TypeError):
            return ValidationResult(False, "Employee ID must be a valid integer")

    @staticmethod
    def validate_year(
        year: Any, min_year: int = 2020, max_year: int = 2030
    ) -> ValidationResult:
        """Validate year value."""
        if year is None:
            return ValidationResult(True, sanitized_value=datetime.now().year)

        try:
            y = int(year)
            if y < min_year or y > max_year:
                return ValidationResult(
                    False, f"Year must be between {min_year} and {max_year}"
                )
            return ValidationResult(True, sanitized_value=y)
        except (ValueError, TypeError):
            return ValidationResult(False, "Year must be a valid integer")

    @staticmethod
    def validate_search_query(query: str, max_length: int = 200) -> ValidationResult:
        """Validate and sanitize a search query."""
        if not query:
            return ValidationResult(False, "Search query is required")

        query = query.strip()

        if len(query) > max_length:
            return ValidationResult(
                False, f"Query is too long (max {max_length} characters)"
            )

        if len(query) < 2:
            return ValidationResult(False, "Query must be at least 2 characters")

        # Remove potentially dangerous characters for SQL injection
        sanitized = re.sub(r'[;\'"\\%_]', "", query)

        return ValidationResult(True, sanitized_value=sanitized)

    @staticmethod
    def validate_reason(
        reason: str | None, required: bool = False, max_length: int = 500
    ) -> ValidationResult:
        """Validate a reason/comment field."""
        if not reason:
            if required:
                return ValidationResult(False, "Reason is required")
            return ValidationResult(True, sanitized_value=None)

        reason = reason.strip()

        if len(reason) > max_length:
            return ValidationResult(
                False, f"Reason is too long (max {max_length} characters)"
            )

        # Basic sanitization - remove control characters
        sanitized = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", reason)

        return ValidationResult(True, sanitized_value=sanitized)

    @staticmethod
    def validate_days(
        days: Any, min_days: float = 0.5, max_days: float = 30
    ) -> ValidationResult:
        """Validate number of days for holiday requests."""
        if days is None:
            return ValidationResult(False, "Number of days is required")

        try:
            d = float(days)
            if d < min_days:
                return ValidationResult(False, f"Days must be at least {min_days}")
            if d > max_days:
                return ValidationResult(False, f"Days cannot exceed {max_days}")
            # Round to nearest 0.5
            sanitized = round(d * 2) / 2
            return ValidationResult(True, sanitized_value=sanitized)
        except (ValueError, TypeError):
            return ValidationResult(False, "Days must be a valid number")

    @staticmethod
    def validate_department(department: str) -> ValidationResult:
        """Validate department name."""
        if not department:
            return ValidationResult(False, "Department is required")

        department = department.strip()

        # List of valid departments (could be loaded from DB)
        valid_departments = [
            "Engineering",
            "HR",
            "Finance",
            "Sales",
            "Marketing",
            "Operations",
            "Legal",
            "Product",
            "Design",
            "Support",
        ]

        # Case-insensitive match
        for valid in valid_departments:
            if department.lower() == valid.lower():
                return ValidationResult(True, sanitized_value=valid)

        return ValidationResult(
            False, f"Invalid department. Valid options: {', '.join(valid_departments)}"
        )

    @staticmethod
    def validate_limit(
        limit: Any, default: int = 10, max_limit: int = 100
    ) -> ValidationResult:
        """Validate pagination limit."""
        if limit is None:
            return ValidationResult(True, sanitized_value=default)

        try:
            limit_val = int(limit)
            if limit_val < 1:
                return ValidationResult(True, sanitized_value=1)
            if limit_val > max_limit:
                return ValidationResult(True, sanitized_value=max_limit)
            return ValidationResult(True, sanitized_value=limit_val)
        except (ValueError, TypeError):
            return ValidationResult(True, sanitized_value=default)


# ============================================================================
# VALIDATION DECORATORS
# ============================================================================


def validate_action_params(func):
    """
    Decorator to validate Action parameters before tool execution.

    Usage:
        @validate_action_params
        def execute_tool(action: Action) -> Any:
            ...
    """
    import functools

    @functools.wraps(func)
    def wrapper(self, action, *args, **kwargs):
        from .errors import ValidationError

        # Validate based on action type
        validators_map: dict[
            str, list[tuple[str, Callable[[Any], ValidationResult]]]
        ] = {
            "search_employee": [
                ("employee_query", lambda v: Validators.validate_search_query(v or "")),
            ],
            "get_employee_basic": [
                ("target_employee_id", Validators.validate_employee_id),
            ],
            "get_holiday_balance": [
                ("target_employee_id", Validators.validate_employee_id),
                ("year", Validators.validate_year),
            ],
            "submit_holiday_request": [
                (
                    "start_date",
                    lambda v: Validators.validate_date(v or "", "start_date"),
                ),
                ("end_date", lambda v: Validators.validate_date(v or "", "end_date")),
                ("days", Validators.validate_days),
                ("reason", lambda v: Validators.validate_reason(v, required=False)),
            ],
            "get_department_directory": [
                ("department", Validators.validate_department),
            ],
        }

        action_name = str(getattr(action, "action", ""))
        for field_name, validator in validators_map.get(action_name, []):
            value = getattr(action, field_name, None)
            result = validator(value)
            if not result.is_valid:
                raise ValidationError(
                    result.error_message or f"Invalid value for {field_name}",
                    field=field_name,
                    value=value,
                )

        return func(self, action, *args, **kwargs)

    return wrapper


# ============================================================================
# REQUEST SANITIZATION
# ============================================================================


def sanitize_user_input(text: str, max_length: int = 1000) -> str:
    """
    Sanitize user input text for safe processing.

    - Removes control characters
    - Truncates to max length
    - Normalizes whitespace
    """
    if not text:
        return ""

    # Remove control characters
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

    # Normalize whitespace
    text = " ".join(text.split())

    # Truncate
    if len(text) > max_length:
        text = text[:max_length] + "..."

    return text


def sanitize_for_logging(data: dict) -> dict:
    """
    Sanitize data for safe logging (remove sensitive fields).
    """
    sensitive_fields = {"password", "api_key", "token", "secret", "ssn", "salary"}

    def redact(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {
                k: "[REDACTED]" if k.lower() in sensitive_fields else redact(v)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [redact(item) for item in obj]
        return obj

    result = redact(data)
    return result if isinstance(result, dict) else {}
