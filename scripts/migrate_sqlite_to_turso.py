#!/usr/bin/env python3
"""
Copy local SQLite data (hr_demo.db) to a Turso database.

Usage:
  python scripts/migrate_sqlite_to_turso.py \
    --source ./hr_demo.db \
    --target-url libsql://<db>-<org>.turso.io \
    --target-token <token>

Or use env vars:
  TURSO_DATABASE_URL=libsql://... TURSO_AUTH_TOKEN=... \
  python scripts/migrate_sqlite_to_turso.py
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from hr_agent.utils.db import create_engine_from_url


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _make_create_if_not_exists(sql: str) -> str:
    return re.sub(
        r"^\s*CREATE\s+TABLE\s+",
        "CREATE TABLE IF NOT EXISTS ",
        sql,
        flags=re.IGNORECASE,
        count=1,
    )


def _make_create_index_if_not_exists(sql: str) -> str:
    return re.sub(
        r"^\s*CREATE\s+(UNIQUE\s+)?INDEX\s+",
        r"CREATE \1INDEX IF NOT EXISTS ",
        sql,
        flags=re.IGNORECASE,
        count=1,
    )


def _copy_schema(source_engine, target_engine) -> list[str]:
    with source_engine.begin() as src_con:
        tables = src_con.execute(
            text(
                """
                SELECT name, sql
                FROM sqlite_master
                WHERE type='table'
                  AND name NOT LIKE 'sqlite_%'
                  AND sql IS NOT NULL
                ORDER BY name
                """
            )
        ).mappings().all()
        indexes = src_con.execute(
            text(
                """
                SELECT name, sql
                FROM sqlite_master
                WHERE type='index'
                  AND name NOT LIKE 'sqlite_%'
                  AND sql IS NOT NULL
                ORDER BY name
                """
            )
        ).mappings().all()

    with target_engine.begin() as dst_con:
        for row in tables:
            dst_con.execute(text(_make_create_if_not_exists(str(row["sql"]))))
        for row in indexes:
            dst_con.execute(text(_make_create_index_if_not_exists(str(row["sql"]))))

    return [str(row["name"]) for row in tables]


def _copy_table_data(source_engine, target_engine, table_name: str) -> int:
    quoted_table = _quote_ident(table_name)
    with source_engine.begin() as src_con:
        columns = [
            str(row["name"])
            for row in src_con.execute(text(f"PRAGMA table_info({quoted_table})")).mappings().all()
        ]
        if not columns:
            return 0
        quoted_cols = ", ".join(_quote_ident(col) for col in columns)
        rows = src_con.execute(
            text(f"SELECT {quoted_cols} FROM {quoted_table}")
        ).mappings().all()

    with target_engine.begin() as dst_con:
        dst_con.execute(text(f"DELETE FROM {quoted_table}"))
        if not rows:
            return 0
        params_sql = ", ".join(f":{col}" for col in columns)
        insert_sql = text(
            f"INSERT INTO {quoted_table} ({quoted_cols}) VALUES ({params_sql})"
        )
        dst_con.execute(insert_sql, [dict(row) for row in rows])
    return len(rows)


def migrate(source_db_path: Path, target_url: str, target_token: str) -> None:
    source_url = f"sqlite:///{source_db_path}"
    source_engine = create_engine_from_url(source_url)
    target_engine = create_engine_from_url(target_url, auth_token=target_token)

    if not source_db_path.exists():
        raise FileNotFoundError(f"Source SQLite DB not found: {source_db_path}")

    tables = _copy_schema(source_engine, target_engine)
    total_rows = 0
    for table in tables:
        copied = _copy_table_data(source_engine, target_engine, table)
        total_rows += copied
        print(f"Copied {copied:5d} rows -> {table}")
    print(f"\nDone. Copied {total_rows} rows across {len(tables)} tables.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate local SQLite data to Turso.")
    parser.add_argument(
        "--source",
        default="./hr_demo.db",
        help="Path to local SQLite DB (default: ./hr_demo.db)",
    )
    parser.add_argument(
        "--target-url",
        default=os.getenv("TURSO_DATABASE_URL", ""),
        help="Turso URL (libsql://... or https://...)",
    )
    parser.add_argument(
        "--target-token",
        default=os.getenv("TURSO_AUTH_TOKEN", ""),
        help="Turso auth token",
    )
    args = parser.parse_args()
    if not args.target_url:
        parser.error("--target-url is required (or set TURSO_DATABASE_URL).")
    return args


if __name__ == "__main__":
    cli_args = _parse_args()
    migrate(
        source_db_path=Path(cli_args.source).expanduser().resolve(),
        target_url=cli_args.target_url,
        target_token=cli_args.target_token,
    )
