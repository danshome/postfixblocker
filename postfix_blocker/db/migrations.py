# ruff: noqa: E402
from __future__ import annotations

"""Database initialization and lightweight migrations (refactor implementation)."""
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from .schema import _ensure_loaded, get_blocked_table, get_props_table  # type: ignore


def init_db(engine: Engine) -> None:
    """Create tables if needed and perform lightweight migrations.

    - Ensure both blocked_addresses and cris_props exist.
    - Ensure test_mode column exists with NOT NULL default.

    Notes:
    - Some dialects (e.g., DB2) can misreport table existence via Inspector.
      To avoid spurious CREATE TABLE errors (SQL0601N), we attempt creation
      unconditionally and ignore "already exists" errors in a portable way.
    """
    _ensure_loaded()
    insp = inspect(engine)

    # Create or verify tables with a robust, idempotent approach
    bt = get_blocked_table()
    pt = get_props_table()

    def _safe_create(table) -> None:
        try:
            # Force create without pre-checks; swallow "already exists" errors
            table.create(engine, checkfirst=False)
        except Exception as exc:  # pragma: no cover - dialect/driver specific
            msg = str(exc).lower()
            # Common patterns across backends for existing table
            if (
                ('already exists' in msg)
                or ('sql0601n' in msg)
                or ('object to be created is identical to the existing name' in msg)
            ):
                return
            # As a fallback, try create with checkfirst (may succeed on some dialects)
            try:
                table.create(engine, checkfirst=True)
                return
            except Exception:
                raise

    _safe_create(bt)
    _safe_create(pt)

    # Migration: ensure test_mode exists
    try:
        cols = insp.get_columns('blocked_addresses') or []
        existing = {c.get('name', '').lower() for c in cols}
    except Exception:
        existing = set()
    if 'test_mode' not in existing:
        with engine.begin() as conn:
            try:
                conn.exec_driver_sql(
                    'ALTER TABLE blocked_addresses ADD COLUMN test_mode BOOLEAN NOT NULL DEFAULT TRUE'
                )
            except Exception:
                conn.exec_driver_sql(
                    'ALTER TABLE blocked_addresses ADD COLUMN test_mode SMALLINT NOT NULL DEFAULT 1'
                )
            # Normalize legacy NULLs
            try:
                conn.exec_driver_sql(
                    'UPDATE blocked_addresses SET test_mode = 1 WHERE test_mode IS NULL'
                )
            except Exception:
                try:
                    conn.exec_driver_sql(
                        'UPDATE blocked_addresses SET test_mode = TRUE WHERE test_mode IS NULL'
                    )
                except Exception as exc:
                    import logging as _logging

                    _logging.getLogger(__name__).debug(
                        'Could not normalize legacy NULL test_mode values; continuing: %s', exc
                    )


__all__ = ['init_db']
