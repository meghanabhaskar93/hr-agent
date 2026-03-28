from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from ..configs.config import settings

_engine: Engine | None = None
_LIBSQL_PREFIXES = ("libsql://", "sqlite+libsql://", "https://", "http://")


def _ensure_query_param(url: str, key: str, value: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    if key not in query:
        query[key] = value
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


def _normalize_libsql_url(raw_url: str) -> str:
    normalized = raw_url.strip()
    if normalized.startswith("sqlite+libsql://"):
        return _ensure_query_param(normalized, "secure", "true")
    if normalized.startswith("libsql://"):
        return _ensure_query_param(
            f"sqlite+libsql://{normalized.removeprefix('libsql://')}",
            "secure",
            "true",
        )
    if normalized.startswith("https://"):
        return _ensure_query_param(
            f"sqlite+libsql://{normalized.removeprefix('https://')}",
            "secure",
            "true",
        )
    if normalized.startswith("http://"):
        return _ensure_query_param(
            f"sqlite+libsql://{normalized.removeprefix('http://')}",
            "secure",
            "false",
        )
    raise ValueError(
        "Invalid Turso DB URL. Expected libsql://<db>.turso.io or https://<db>.turso.io."
    )


def _is_libsql_like_url(url: str) -> bool:
    return url.startswith(_LIBSQL_PREFIXES)


def _resolve_db_settings() -> tuple[str, str]:
    turso_url = settings.turso_database_url.strip()
    turso_token = settings.turso_auth_token.strip()
    configured_db_url = settings.db_url.strip()

    if turso_url:
        return _normalize_libsql_url(turso_url), turso_token

    if configured_db_url:
        if _is_libsql_like_url(configured_db_url):
            return _normalize_libsql_url(configured_db_url), turso_token
        return configured_db_url, ""

    raise RuntimeError(
        "Database is not configured. Set TURSO_DATABASE_URL (recommended) "
        "or DB_URL for local/testing."
    )


def create_engine_from_url(db_url: str, auth_token: str = "") -> Engine:
    normalized_input = db_url.strip()
    token = auth_token.strip()
    if _is_libsql_like_url(normalized_input):
        normalized_input = _normalize_libsql_url(normalized_input)
    create_kwargs: dict[str, Any] = {"future": True}
    if token:
        create_kwargs["connect_args"] = {"auth_token": token}
    return create_engine(normalized_input, **create_kwargs)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        db_url, auth_token = _resolve_db_settings()
        _engine = create_engine_from_url(db_url, auth_token=auth_token)
    return _engine
