"""
Observability Module - Logging, Metrics, and Tracing

Provides structured logging, performance metrics, and distributed tracing
for production monitoring and debugging.
"""

import logging
import time
import functools
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
from enum import Enum


# ============================================================================
# STRUCTURED LOGGING
# ============================================================================


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogContext:
    """Structured context for log entries."""

    request_id: str | None = None
    user_email: str | None = None
    session_id: str | None = None
    action: str | None = None
    extra: dict = field(default_factory=dict)


class StructuredLogger:
    """
    Structured logger that outputs JSON-formatted logs.

    In production, these logs can be shipped to:
    - Datadog
    - Splunk
    - Azure Monitor / Log Analytics
    - AWS CloudWatch
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._context = LogContext()

    def set_context(self, **kwargs):
        """Set context that will be included in all subsequent logs."""
        for key, value in kwargs.items():
            if hasattr(self._context, key):
                setattr(self._context, key, value)
            else:
                self._context.extra[key] = value

    def _format_log(self, level: str, message: str, **kwargs) -> dict:
        """Format log entry as structured JSON."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "request_id": self._context.request_id,
            "user_email": self._context.user_email,
            "session_id": self._context.session_id,
            "action": self._context.action,
            **self._context.extra,
            **kwargs,
        }

    def info(self, message: str, **kwargs):
        self.logger.info(self._format_log("INFO", message, **kwargs))

    def warning(self, message: str, **kwargs):
        self.logger.warning(self._format_log("WARNING", message, **kwargs))

    def error(self, message: str, **kwargs):
        self.logger.error(self._format_log("ERROR", message, **kwargs))

    def debug(self, message: str, **kwargs):
        self.logger.debug(self._format_log("DEBUG", message, **kwargs))


# ============================================================================
# METRICS COLLECTION
# ============================================================================


@dataclass
class MetricPoint:
    """A single metric data point."""

    name: str
    value: float
    timestamp: datetime
    tags: dict = field(default_factory=dict)


class MetricsCollector:
    """
    Collects and exposes metrics for monitoring.

    In production, integrate with:
    - Prometheus (via prometheus_client)
    - Datadog (via ddtrace)
    - Azure Monitor
    - MLflow (for model-specific metrics)
    """

    def __init__(self):
        self._counters: dict[str, int] = {}
        self._histograms: dict[str, list[float]] = {}
        self._gauges: dict[str, float] = {}

    def increment(self, name: str, value: int = 1, tags: dict | None = None):
        """Increment a counter metric."""
        key = self._make_key(name, tags)
        self._counters[key] = self._counters.get(key, 0) + value

    def histogram(self, name: str, value: float, tags: dict | None = None):
        """Record a value in a histogram (for latency, etc.)."""
        key = self._make_key(name, tags)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)

    def gauge(self, name: str, value: float, tags: dict | None = None):
        """Set a gauge metric (current value)."""
        key = self._make_key(name, tags)
        self._gauges[key] = value

    def _make_key(self, name: str, tags: dict | None) -> str:
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"

    def get_stats(self) -> dict[str, Any]:
        """Get current metric statistics."""
        stats: dict[str, Any] = {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {},
        }
        for key, values in self._histograms.items():
            if values:
                sorted_vals = sorted(values)
                stats["histograms"][key] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "p50": sorted_vals[len(sorted_vals) // 2],
                    "p95": (
                        sorted_vals[int(len(sorted_vals) * 0.95)]
                        if len(sorted_vals) > 1
                        else sorted_vals[0]
                    ),
                    "p99": (
                        sorted_vals[int(len(sorted_vals) * 0.99)]
                        if len(sorted_vals) > 1
                        else sorted_vals[0]
                    ),
                }
        return stats


# ============================================================================
# PERFORMANCE TRACING
# ============================================================================


@dataclass
class Span:
    """A trace span representing a unit of work."""

    name: str
    trace_id: str
    span_id: str
    parent_span_id: str | None
    start_time: datetime
    end_time: datetime | None = None
    tags: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    status: str = "OK"

    @property
    def duration_ms(self) -> float | None:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None


class Tracer:
    """
    Distributed tracing for request flows.

    In production, integrate with:
    - OpenTelemetry
    - Jaeger
    - Zipkin
    - Azure Application Insights
    """

    def __init__(self):
        self._spans: list[Span] = []
        self._current_trace_id: str | None = None

    @contextmanager
    def span(self, name: str, tags: dict | None = None):
        """Create a traced span for a block of code."""
        import uuid

        span = Span(
            name=name,
            trace_id=self._current_trace_id or str(uuid.uuid4()),
            span_id=str(uuid.uuid4()),
            parent_span_id=None,
            start_time=datetime.utcnow(),
            tags=tags or {},
        )

        try:
            yield span
            span.status = "OK"
        except Exception as e:
            span.status = "ERROR"
            span.events.append({"error": str(e), "type": type(e).__name__})
            raise
        finally:
            span.end_time = datetime.utcnow()
            self._spans.append(span)

    def get_recent_spans(self, limit: int = 100) -> list[Span]:
        """Get recent spans for debugging."""
        return self._spans[-limit:]


# ============================================================================
# DECORATORS FOR EASY INSTRUMENTATION
# ============================================================================


def timed(metric_name: str | None = None):
    """Decorator to measure function execution time."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = metric_name or f"{func.__module__}.{func.__name__}"
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                metrics.histogram(
                    f"{name}.duration_ms", (time.perf_counter() - start) * 1000
                )
                metrics.increment(f"{name}.success")
                return result
            except Exception as e:
                metrics.increment(
                    f"{name}.error", tags={"error_type": type(e).__name__}
                )
                raise

        return wrapper

    return decorator


def traced(span_name: str | None = None):
    """Decorator to create a trace span for a function."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = span_name or f"{func.__module__}.{func.__name__}"
            with tracer.span(name):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================================
# SINGLETONS
# ============================================================================

logger = StructuredLogger("hr_agent")
metrics = MetricsCollector()
tracer = Tracer()


# ============================================================================
# HR AGENT SPECIFIC METRICS
# ============================================================================


def record_agent_request(
    user_email: str, action: str, latency_ms: float, success: bool
):
    """Record metrics for an agent request."""
    tags = {"action": action, "success": str(success).lower()}
    metrics.increment("agent.requests", tags=tags)
    metrics.histogram("agent.latency_ms", latency_ms, tags={"action": action})

    if not success:
        metrics.increment("agent.errors", tags={"action": action})


def record_policy_decision(action: str, allowed: bool, rule_name: str | None):
    """Record metrics for policy decisions."""
    tags = {"action": action, "allowed": str(allowed).lower()}
    if rule_name:
        tags["rule"] = rule_name
    metrics.increment("policy.decisions", tags=tags)


def record_llm_call(model: str, latency_ms: float, tokens_used: int, success: bool):
    """Record metrics for LLM API calls."""
    tags = {"model": model, "success": str(success).lower()}
    metrics.increment("llm.calls", tags=tags)
    metrics.histogram("llm.latency_ms", latency_ms, tags={"model": model})
    metrics.increment("llm.tokens", tokens_used, tags={"model": model})
