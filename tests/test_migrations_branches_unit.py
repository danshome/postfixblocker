from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any

import pytest


class _DummyCtx(AbstractContextManager):
    def __init__(self, recorder: list[str], fail_on: list[str] | None = None):
        self.recorder = recorder
        self.fail_on = fail_on or []

    def __enter__(self):  # pragma: no cover - exercised via init_db
        return self

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover - exercised via init_db
        return False

    # Mimic Connection.exec_driver_sql
    def exec_driver_sql(self, sql: str, params: Any = None):
        self.recorder.append(sql.strip())
        lowered = sql.lower()
        # Trigger failures for certain statements to exercise exception paths
        if any(tok in lowered for tok in self.fail_on):
            raise RuntimeError('forced error for coverage')

        # Return a simple object with first()/fetchall() if called
        class _R:
            def __init__(self, row):
                self._row = row

            def first(self):
                return self._row

            def fetchall(self):
                return []

        # Provide shape-sensitive rows
        if 'from syscat.tablespaces' in lowered or 'from syscat.bufferpools' in lowered:
            return _R((0, 32768))
        if 'from syscat.tablespaces where tbspace' in lowered:
            return _R((0,))
        return _R((0,))


@pytest.mark.unit
def test_init_db_postgres_branch(monkeypatch):
    try:
        from sqlalchemy import create_engine
    except Exception:  # pragma: no cover
        pytest.skip('SQLAlchemy not available')

    engine = create_engine('sqlite:///:memory:')
    # Force dialect name to postgres to take that branch
    monkeypatch.setattr(engine.dialect, 'name', 'postgresql')

    recorded: list[str] = []

    # Replace engine.begin with our dummy context manager
    def _fake_begin():
        return _DummyCtx(recorded, fail_on=['view blocked_addresses', 'view cris_props'])

    monkeypatch.setattr(engine, 'begin', _fake_begin)

    # Now import and run init_db
    from postfix_blocker.db.migrations import init_db

    init_db(engine)  # should run without raising, using our fake ctx

    # We should have attempted to create schema and tables
    assert any('create schema' in s.lower() for s in recorded)
    assert any('create table' in s.lower() for s in recorded)


@pytest.mark.unit
def test_init_db_db2_branch(monkeypatch):
    try:
        from sqlalchemy import create_engine
    except Exception:  # pragma: no cover
        pytest.skip('SQLAlchemy not available')

    engine = create_engine('sqlite:///:memory:')
    # Force dialect name to Db2 to take that branch
    monkeypatch.setattr(engine.dialect, 'name', 'ibm_db_sa')

    recorded: list[str] = []

    # Replace engine.begin with our dummy context manager; fail on various ops to
    # exercise the tolerant exception handling paths.
    def _fake_begin():
        return _DummyCtx(
            recorded,
            fail_on=[
                'drop tablespace',
                'drop bufferpool',
                'create bufferpool',
                'create tablespace',
                'alter tablespace',
                'create schema',
                'create table crisop.blocked_addresses',
                'create table crisop.cris_props',
                'create or replace trigger',
                'drop alias',
                'create alias',
            ],
        )

    monkeypatch.setattr(engine, 'begin', _fake_begin)

    from postfix_blocker.db.migrations import init_db

    init_db(engine)

    # At minimum, we recorded some SQL statements
    assert len(recorded) > 0
