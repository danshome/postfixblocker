from __future__ import annotations

import pytest

# Target under test
from postfix_blocker.db import migrations as mig


class _FakeResult:
    def __init__(self, first_val=None, rows=None):
        self._first_val = first_val
        self._rows = rows or []

    def first(self):  # mimic SQLAlchemy's Result.first()
        return self._first_val

    def fetchall(self):  # mimic SQLAlchemy's Result.fetchall()
        return list(self._rows)


class _FakeConn:
    def __init__(self, log: list[str]):
        self._log = log

    # Simulate exec_driver_sql used heavily in DB2 branch
    def exec_driver_sql(self, sql: str, params: tuple | None = None):
        self._log.append(sql)
        s = sql.upper().strip()
        # TS count + pagesize
        if s.startswith('SELECT COUNT(*), COALESCE(MAX(PAGESIZE),0) FROM SYSCAT.TABLESPACES'):
            # No TS exists
            return _FakeResult(first_val=(0, 0))
        # BP count + pagesize
        if s.startswith('SELECT COUNT(*), COALESCE(MAX(PAGESIZE),0) FROM SYSCAT.BUFFERPOOLS'):
            # No BP exists
            return _FakeResult(first_val=(0, 0))
        # Has any tables in TS32K? Return none to allow safe drop (though ts_count is 0 above)
        if s.startswith('SELECT T.TABSCHEMA, T.TABNAME FROM SYSCAT.TABLES'):
            return _FakeResult(rows=[])
        # TS count check (after create)
        if s.startswith("SELECT COUNT(*) FROM SYSCAT.TABLESPACES WHERE TBSPACE='TS32K'".upper()):
            return _FakeResult(first_val=(0,))
        # Everything else: return a benign result object
        return _FakeResult()

    # Context manager API used by engine.begin()
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeDialect:
    def __init__(self, name: str):
        self.name = name


class _FakeEngine:
    def __init__(self):
        self.dialect = _FakeDialect('ibm_db_sa')
        self._log: list[str] = []

    def begin(self):
        return _FakeConn(self._log)

    # For compatibility if called (not used in the DB2 path)
    def connect(self):  # pragma: no cover - not expected in this path
        return _FakeConn(self._log)


@pytest.mark.unit
def test_init_db_db2_path_executes_without_real_db(monkeypatch):
    """Exercise the DB2-specific branch in migrations.init_db using fakes.

    This ensures we have coverage for the logic that creates bufferpools,
    tablespaces, schema, tables, triggers, and aliases without requiring a
    real DB2 server/driver. We stub out SQLAlchemy's inspect() and the
    seed_default_props() helper to avoid real metadata work.
    """

    # Stub inspect(engine) to a harmless object since it's evaluated before branching
    monkeypatch.setattr(mig, 'inspect', lambda _engine: object())

    # Avoid executing real seed_default_props (which expects a real SQLAlchemy engine)
    called = {'seed': False}

    def _seed_stub(engine):
        called['seed'] = True

    monkeypatch.setattr(mig, 'seed_default_props', _seed_stub)

    eng = _FakeEngine()

    # Call under test — should not raise
    mig.init_db(eng)  # type: ignore[arg-type]

    # We should have executed at least some DDL statements in our fake log
    assert len(eng._log) > 0
    # Ensure we attempted to create bufferpool and tablespace (order not strictly enforced)
    joined = '\n'.join(eng._log).upper()
    assert 'CREATE BUFFERPOOL BP32K' in joined or 'DROP BUFFERPOOL BP32K' in joined
    assert (
        'CREATE TABLESPACE TS32K' in joined or 'ALTER TABLESPACE TS32K BUFFERPOOL BP32K' in joined
    )
    # And confirm we invoked the stubbed seeding function
    assert called['seed'] is True
