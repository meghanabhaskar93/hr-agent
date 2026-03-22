"""
Base Repository - Abstract interface for data access

Defines the contract that all repositories must implement.
This allows easy swapping of implementations (SQL, API, Mock, etc.)
"""

from abc import ABC
from typing import Any
from sqlalchemy import text
from ..utils.db import get_engine


class BaseRepository(ABC):
    """
    Abstract base repository defining common data access patterns.

    Subclasses can override _get_connection() to use different
    data sources (different databases, APIs, etc.)
    """

    def _get_engine(self):
        """Get the database engine. Override for different data sources."""
        return get_engine()

    def _execute_query(self, query: str, params: dict | None = None) -> list[dict]:
        """Execute a query and return results as list of dicts."""
        eng = self._get_engine()
        with eng.begin() as con:
            rows = con.execute(text(query), params or {}).mappings().all()
            return [dict(r) for r in rows]

    def _execute_query_one(self, query: str, params: dict | None = None) -> dict | None:
        """Execute a query and return single result as dict or None."""
        eng = self._get_engine()
        with eng.begin() as con:
            row = con.execute(text(query), params or {}).mappings().one_or_none()
            return dict(row) if row else None

    def _execute_scalar(self, query: str, params: dict | None = None) -> Any:
        """Execute a query and return scalar value."""
        eng = self._get_engine()
        with eng.begin() as con:
            return con.execute(text(query), params or {}).scalar_one_or_none()

    def _execute_insert(self, query: str, params: dict | None = None) -> int:
        """Execute an insert and return the last inserted ID."""
        eng = self._get_engine()
        with eng.begin() as con:
            con.execute(text(query), params or {})
            return int(con.execute(text("SELECT last_insert_rowid()")).scalar_one())

    def _execute_update(self, query: str, params: dict | None = None) -> int:
        """Execute an update and return rows affected."""
        eng = self._get_engine()
        with eng.begin() as con:
            result = con.execute(text(query), params or {})
            return int(result.rowcount or 0)
