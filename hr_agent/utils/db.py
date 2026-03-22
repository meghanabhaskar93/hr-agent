from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from ..configs.config import settings

_engine: Engine | None = None


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


def _resolve_db_settings() -> tuple[str, dict]:
    turso_url = settings.turso_database_url.strip()
    turso_token = settings.turso_auth_token.strip()
    configured_db_url = settings.db_url.strip()

    if turso_url:
        db_url = _normalize_libsql_url(turso_url)
        connect_args = {"auth_token": turso_token} if turso_token else {}
        return db_url, connect_args

    if configured_db_url.startswith(("libsql://", "sqlite+libsql://", "https://", "http://")):
        db_url = _normalize_libsql_url(configured_db_url)
        connect_args = {"auth_token": turso_token} if turso_token else {}
        return db_url, connect_args

    return configured_db_url, {}


def create_engine_from_url(db_url: str, auth_token: str = "") -> Engine:
    normalized_input = db_url.strip()
    token = auth_token.strip()
    if normalized_input.startswith(("libsql://", "sqlite+libsql://", "https://", "http://")):
        normalized_input = _normalize_libsql_url(normalized_input)
    create_kwargs = {"future": True}
    if token:
        create_kwargs["connect_args"] = {"auth_token": token}
    return create_engine(normalized_input, **create_kwargs)


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        db_url, connect_args = _resolve_db_settings()
        _engine = create_engine_from_url(
            db_url,
            auth_token=str(connect_args.get("auth_token", "")) if connect_args else "",
        )
    return _engine
