"""
Decorators for Cross-Cutting Concerns

Provides reusable decorators for:
- Logging and timing
- Error handling and retries
- Input validation
- Authorization checks
- Caching (placeholder for Redis integration)

These decorators eliminate boilerplate code in service and tool implementations.
"""

import functools
import time
from typing import Callable, TypeVar, ParamSpec, Any, cast

from ..tracing.observability import logger, metrics, timed  # noqa: F401 (re-exported)
from .errors import ValidationError

P = ParamSpec("P")
T = TypeVar("T")


def log_execution(operation_name: str | None = None):
    """
    Decorator that logs function entry, exit, and errors.

    Usage:
        @log_execution("search_employee")
        def search_employee(query: str) -> list:
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        name = operation_name or func.__name__

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            start_time = time.time()

            # Log entry (without sensitive data)
            logger.debug(
                f"Entering {name}",
                args_count=len(args),
                kwargs_keys=list(kwargs.keys()),
            )

            try:
                result = func(*args, **kwargs)

                # Log success with timing
                duration_ms = (time.time() - start_time) * 1000
                logger.debug(f"Completed {name}", duration_ms=round(duration_ms, 2))
                metrics.histogram(f"function.{name}.duration_ms", duration_ms)
                metrics.increment(f"function.{name}.success")

                return result

            except Exception as e:
                # Log error
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"Failed {name}",
                    error=str(e),
                    error_type=type(e).__name__,
                    duration_ms=round(duration_ms, 2),
                )
                metrics.increment(
                    f"function.{name}.error", tags={"error_type": type(e).__name__}
                )
                raise

        return wrapper

    return decorator


def validate_params(**validators: Callable[[Any], bool]):
    """
    Decorator for parameter validation.

    Usage:
        @validate_params(
            employee_id=lambda x: isinstance(x, int) and x > 0,
            year=lambda x: 2000 <= x <= 2100
        )
        def get_holiday_balance(employee_id: int, year: int):
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Get parameter names from function signature
            import inspect

            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            # Validate each specified parameter
            for param_name, validator in validators.items():
                if param_name in bound.arguments:
                    value = bound.arguments[param_name]
                    if not validator(value):
                        raise ValidationError(
                            f"Invalid value for {param_name}: {value}",
                            field=param_name,
                            value=value,
                        )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_not_none(*param_names: str):
    """
    Decorator that validates specified parameters are not None.

    Usage:
        @require_not_none("employee_id", "year")
        def get_balance(employee_id, year):
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            import inspect

            sig = inspect.signature(func)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()

            for param_name in param_names:
                if (
                    param_name in bound.arguments
                    and bound.arguments[param_name] is None
                ):
                    raise ValidationError(
                        f"{param_name} cannot be None", field=param_name
                    )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def cache_result(ttl_seconds: int = 300, key_func: Callable[..., str] | None = None):
    """
    Simple in-memory caching decorator.

    In production, replace with Redis-backed implementation.

    Usage:
        @cache_result(ttl_seconds=60)
        def get_employee(employee_id: int):
            ...
    """
    cache: dict[str, tuple[Any, float]] = {}

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Generate cache key
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"

            # Check cache
            if key in cache:
                value, expiry = cache[key]
                if time.time() < expiry:
                    metrics.increment("cache.hit", tags={"function": func.__name__})
                    return cast(T, value)
                else:
                    del cache[key]

            metrics.increment("cache.miss", tags={"function": func.__name__})

            # Call function and cache result
            result = func(*args, **kwargs)
            cache[key] = (result, time.time() + ttl_seconds)

            return result

        # Add method to clear cache
        wrapper.clear_cache = cache.clear  # type: ignore

        return wrapper

    return decorator


def deprecated(message: str = "This function is deprecated"):
    """
    Mark a function as deprecated.

    Usage:
        @deprecated("Use get_employee_v2 instead")
        def get_employee(id):
            ...
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            import warnings

            warnings.warn(
                f"{func.__name__} is deprecated: {message}",
                DeprecationWarning,
                stacklevel=2,
            )
            logger.warning(
                f"Deprecated function called: {func.__name__}",
                deprecation_message=message,
            )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def async_safe(func: Callable[P, T]) -> Callable[P, T]:
    """
    Decorator to make a sync function safe to call from async context.

    Runs the function in a thread pool executor.

    Usage:
        @async_safe
        def blocking_operation():
            ...
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    executor = ThreadPoolExecutor(max_workers=4)

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in async context, run in executor
            return loop.run_in_executor(executor, lambda: func(*args, **kwargs))  # type: ignore
        else:
            # Normal sync context
            return func(*args, **kwargs)

    return wrapper


def rate_limit(calls_per_minute: int):
    """
    Rate limiting decorator for individual functions.

    Usage:
        @rate_limit(calls_per_minute=60)
        def expensive_api_call():
            ...
    """
    min_interval = 60.0 / calls_per_minute
    last_call_time: float = 0.0

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            nonlocal last_call_time

            elapsed = time.time() - last_call_time
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                time.sleep(sleep_time)

            last_call_time = time.time()
            return func(*args, **kwargs)

        return wrapper

    return decorator


def sanitize_output(*fields_to_mask: str):
    """
    Decorator that masks sensitive fields in dict/list outputs.

    Usage:
        @sanitize_output("salary", "ssn", "password")
        def get_employee_details(id):
            return {"name": "John", "salary": 100000}
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            result = func(*args, **kwargs)
            return cast(T, _mask_fields(result, fields_to_mask))

        return wrapper

    return decorator


def _mask_fields(data: Any, fields: tuple[str, ...]) -> Any:
    """Recursively mask specified fields in data structures."""
    if isinstance(data, dict):
        return {
            k: "***MASKED***" if k in fields else _mask_fields(v, fields)
            for k, v in data.items()
        }
    elif isinstance(data, list):
        return [_mask_fields(item, fields) for item in data]
    return data
