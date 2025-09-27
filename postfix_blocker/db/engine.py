# ruff: noqa: E402
from __future__ import annotations

"""Engine factory (refactor implementation).

Provides a stable import path postfix_blocker.db.engine.get_engine and
removes the dependency on postfix_blocker.blocker.
Also provides a dedicated user-management engine (SQLite) via get_user_engine.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

# Module-level cache for the user-management engine to ensure a stable
# connection (especially important for SQLite in-memory URLs).
_UM_ENGINE: Engine | None = None
# When running under pytest, we isolate UM engines per test using the
# PYTEST_CURRENT_TEST environment value as a key, to avoid cross-test state
# leakage while preserving a stable engine within a single test.
_UM_ENGINES: dict[str, Engine] = {}


essqlite_prefixes = ('sqlite://', 'sqlite+pysqlite://')


def get_engine() -> Engine:
    # Default to DB2 connection URL for the main application data.
    db_url = os.environ.get('BLOCKER_DB_URL', 'ibm_db_sa://db2inst1:blockerpass@db2:50000/BLOCKER')
    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_use_lifo=True,
        pool_size=20,
        max_overflow=0,
        pool_recycle=3600,
    )


def _compute_um_db_url(test_key: str | None) -> str:
    db_url = os.environ.get('UM_DB_URL')
    if db_url:
        return db_url
    # Optionally allow UM_DB_PATH (file path) to be provided; otherwise, use a
    # project-local file. Using a file by default avoids issues with separate
    # connections to an in-memory DB.
    um_path = os.environ.get('UM_DB_PATH')
    if um_path:
        if um_path.startswith('sqlite'):
            return um_path
        # Treat as filesystem path
        return f'sqlite:///{um_path}'
    # During pytest runs, prefer an isolated in-memory database per test
    return 'sqlite:///:memory:' if test_key else 'sqlite:///./um.db'


def _ensure_um_table_exists(eng: Engine) -> None:
    """Best-effort creation of UM_USER table to avoid first-hit races in tests."""
    try:
        from .schema import get_user_table  # local import to avoid cycles

        ut = get_user_table()
        try:
            ut.create(eng, checkfirst=True)
        except Exception as exc:  # pragma: no cover - dialect specific
            import logging as _lg

            _lg.getLogger(__name__).debug('UM_USER create on engine init failed: %s', exc)
    except Exception as exc:  # pragma: no cover - optional
        # If schema import fails for any reason, defer to later initialization but record it
        import logging as _lg

        _lg.getLogger(__name__).debug('UM_USER early init skipped: %s', exc)


def get_user_engine() -> Engine:
    """Return the engine for user management (UM_USER table).

    By default this is a local SQLite database. Override with UM_DB_URL if needed.
    When running under pytest, a per-test in-memory engine is used (keyed by
    PYTEST_CURRENT_TEST) to avoid cross-test state leakage while keeping a stable
    connection within a single test.
    """
    # Pytest isolation: cache per-test
    test_key = os.environ.get('PYTEST_CURRENT_TEST')
    if test_key:
        eng = _UM_ENGINES.get(test_key)
        if eng is not None:
            return eng

    # Process-wide cache (non-pytest or when per-test engine not desired)
    global _UM_ENGINE
    if not test_key and _UM_ENGINE is not None:
        return _UM_ENGINE

    db_url = _compute_um_db_url(test_key)

    # For SQLite, allow cross-thread access which is common in Flask dev servers
    connect_args = {'check_same_thread': False} if db_url.startswith('sqlite') else {}

    eng = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)

    _ensure_um_table_exists(eng)

    # Store in appropriate cache
    if test_key:
        _UM_ENGINES[test_key] = eng
        return eng
    _UM_ENGINE = eng
    return eng


__all__ = ['get_engine', 'get_user_engine']
