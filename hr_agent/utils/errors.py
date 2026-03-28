"""
Error Handling and Retry Logic

Production-grade error handling with:
- Custom exception hierarchy
- Automatic retries with exponential backoff
- Circuit breaker pattern for external services
- Graceful degradation
"""

import time
import functools
from enum import Enum
from dataclasses import dataclass
from typing import Callable, TypeVar, Any
from datetime import datetime


# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================


class HRAgentError(Exception):
    """Base exception for all HR Agent errors."""

    def __init__(
        self, message: str, code: str | None = None, details: dict | None = None
    ):
        super().__init__(message)
        self.message = message
        self.code = code or "UNKNOWN_ERROR"
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class AuthorizationError(HRAgentError):
    """Raised when a user doesn't have permission for an action."""

    def __init__(
        self, message: str, action: str | None = None, user_email: str | None = None
    ):
        super().__init__(
            message,
            code="AUTHORIZATION_DENIED",
            details={"action": action, "user_email": user_email},
        )


class ValidationError(HRAgentError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str | None = None, value: Any = None):
        super().__init__(
            message,
            code="VALIDATION_ERROR",
            details={"field": field, "value": str(value) if value else None},
        )


class ResourceNotFoundError(HRAgentError):
    """Raised when a requested resource doesn't exist."""

    def __init__(self, resource_type: str, resource_id: Any):
        super().__init__(
            f"{resource_type} with ID {resource_id} not found",
            code="RESOURCE_NOT_FOUND",
            details={"resource_type": resource_type, "resource_id": str(resource_id)},
        )


class ExternalServiceError(HRAgentError):
    """Raised when an external service call fails."""

    def __init__(self, service: str, message: str, status_code: int | None = None):
        super().__init__(
            f"{service} error: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            details={"service": service, "status_code": status_code},
        )


class LLMError(ExternalServiceError):
    """Raised when LLM API calls fail."""

    def __init__(
        self, message: str, model: str | None = None, status_code: int | None = None
    ):
        super().__init__("LLM", message, status_code)
        self.details["model"] = model


class RateLimitError(HRAgentError):
    """Raised when rate limits are exceeded."""

    def __init__(self, service: str, retry_after: int | None = None):
        super().__init__(
            f"Rate limit exceeded for {service}",
            code="RATE_LIMIT_EXCEEDED",
            details={"service": service, "retry_after_seconds": retry_after},
        )


class ConfigurationError(HRAgentError):
    """Raised when there's a configuration problem."""

    def __init__(self, message: str, config_key: str | None = None):
        super().__init__(
            message,
            code="CONFIGURATION_ERROR",
            details={"config_key": config_key},
        )


# ============================================================================
# RETRY LOGIC WITH EXPONENTIAL BACKOFF
# ============================================================================


T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: tuple = (ExternalServiceError, ConnectionError, TimeoutError)


def retry_with_backoff(config: RetryConfig | None = None):
    """
    Decorator for automatic retries with exponential backoff.

    Usage:
        @retry_with_backoff(RetryConfig(max_attempts=5))
        def call_external_api():
            ...
    """
    config = config or RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e

                    if attempt == config.max_attempts:
                        break

                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay_seconds
                        * (config.exponential_base ** (attempt - 1)),
                        config.max_delay_seconds,
                    )

                    # Add jitter to prevent thundering herd
                    if config.jitter:
                        import random

                        delay = delay * (0.5 + random.random())

                    time.sleep(delay)

            if last_exception is not None:
                raise last_exception
            raise RuntimeError("Retry operation failed without a captured exception.")

        return wrapper

    return decorator


# ============================================================================
# CIRCUIT BREAKER PATTERN
# ============================================================================


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes to close from half-open
    timeout_seconds: float = 30.0  # Time in open state before half-open
    monitored_exceptions: tuple = (ExternalServiceError, ConnectionError, TimeoutError)


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests are rejected immediately
    - HALF_OPEN: Testing if service recovered, limited requests allowed
    """

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            # Check if timeout has passed
            if self._last_failure_time:
                elapsed = (datetime.utcnow() - self._last_failure_time).total_seconds()
                if elapsed >= self.config.timeout_seconds:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
        return self._state

    def record_success(self):
        """Record a successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self.config.success_threshold:
                self._state = CircuitState.CLOSED
                self._failure_count = 0
        elif self.state == CircuitState.CLOSED:
            self._failure_count = 0

    def record_failure(self):
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = datetime.utcnow()

        if self.state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
        elif self._failure_count >= self.config.failure_threshold:
            self._state = CircuitState.OPEN

    def allow_request(self) -> bool:
        """Check if a request should be allowed."""
        return self.state != CircuitState.OPEN

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Use as a decorator."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            if not self.allow_request():
                raise ExternalServiceError(
                    self.name,
                    f"Circuit breaker is open for {self.name}",
                )

            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except self.config.monitored_exceptions:
                self.record_failure()
                raise

        return wrapper


# ============================================================================
# GRACEFUL DEGRADATION
# ============================================================================


def with_fallback(fallback_value: T | Callable[..., T]):
    """
    Decorator that returns a fallback value on error.

    Usage:
        @with_fallback(fallback_value=[])
        def get_announcements():
            return api.fetch_announcements()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return func(*args, **kwargs)
            except Exception:
                if callable(fallback_value):
                    return fallback_value(*args, **kwargs)
                return fallback_value

        return wrapper

    return decorator


# ============================================================================
# ERROR CONTEXT MANAGER
# ============================================================================


class ErrorContext:
    """
    Context manager for handling errors with proper logging and metrics.

    Usage:
        with ErrorContext("fetching employee data", user_email=user.email):
            result = service.get_employee(employee_id)
    """

    def __init__(self, operation: str, **context):
        self.operation = operation
        self.context = context

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            # Log the error with context
            from ..tracing.observability import logger, metrics

            logger.error(
                f"Error during {self.operation}",
                error_type=exc_type.__name__,
                error_message=str(exc_val),
                **self.context,
            )

            metrics.increment(
                "errors",
                tags={"operation": self.operation, "error_type": exc_type.__name__},
            )

            # Don't suppress the exception
            return False
        return False


# ============================================================================
# SINGLETON CIRCUIT BREAKERS FOR EXTERNAL SERVICES
# ============================================================================

llm_circuit_breaker = CircuitBreaker(
    "llm_api",
    CircuitBreakerConfig(
        failure_threshold=3,
        timeout_seconds=60.0,
    ),
)

db_circuit_breaker = CircuitBreaker(
    "database",
    CircuitBreakerConfig(
        failure_threshold=5,
        timeout_seconds=30.0,
    ),
)
