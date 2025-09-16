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
    """
    _ensure_loaded()
    insp = inspect(engine)

    # Create tables if missing
    # blocked_addresses
    try:
        has_blocked = insp.has_table('blocked_addresses')
    except Exception:
        has_blocked = False
    if not has_blocked:
        # create_all via metadata referenced by get_blocked_table
        bt = get_blocked_table()
        bt.metadata.create_all(engine)  # type: ignore[attr-defined]
    # cris_props
    try:
        has_props = insp.has_table('cris_props')
    except Exception:
        has_props = False
    if not has_props:
        pt = get_props_table()
        pt.create(engine, checkfirst=True)

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
