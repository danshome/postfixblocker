from __future__ import annotations

import pytest

from postfix_blocker.db import migrations as mig


class _FakeResult:
    def __init__(self, first_val=None, rows=None):
        self._first_val = first_val
        self._rows = rows or []

    def first(self):
        return self._first_val

    def fetchall(self):
        return list(self._rows)


class _ConnCaseA:
    """Case A: TS _fetchone fails; BP wrong pagesize; TS missing."""

    def __init__(self, log):
        self.log = log

    def exec_driver_sql(self, sql: str, params=None):
        s = sql.upper().strip()
        self.log.append(s)
        if s.startswith('SELECT COUNT(*), COALESCE(MAX(PAGESIZE),0) FROM SYSCAT.TABLESPACES'):
            # Fail probe -> triggers except path (lines ~45-46)
            raise RuntimeError('probe fail')
        if s.startswith('SELECT COUNT(*), COALESCE(MAX(PAGESIZE),0) FROM SYSCAT.BUFFERPOOLS'):
            return _FakeResult(first_val=(1, 8192))
        if s.startswith("SELECT COUNT(*) FROM SYSCAT.TABLESPACES WHERE TBSPACE='TS32K'"):
            return _FakeResult(first_val=(0,))
        return _FakeResult()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _ConnCaseB:
    """Case B: TS exists with wrong pagesize and is safe to drop; BP wrong pagesize too."""

    def __init__(self, log):
        self.log = log

    def exec_driver_sql(self, sql: str, params=None):
        s = sql.upper().strip()
        self.log.append(s)
        if s.startswith('SELECT COUNT(*), COALESCE(MAX(PAGESIZE),0) FROM SYSCAT.TABLESPACES'):
            return _FakeResult(first_val=(1, 8192))
        if s.startswith('SELECT COUNT(*), COALESCE(MAX(PAGESIZE),0) FROM SYSCAT.BUFFERPOOLS'):
            return _FakeResult(first_val=(1, 16384))
        if s.startswith('SELECT T.TABSCHEMA, T.TABNAME FROM SYSCAT.TABLES'):
            # No user tables -> safe to drop
            return _FakeResult(rows=[])
        if s.startswith('SELECT COALESCE(CARD, 0) FROM SYSCAT.TABLES'):
            return _FakeResult(first_val=(0,))
        if s.startswith("SELECT COUNT(*) FROM SYSCAT.TABLESPACES WHERE TBSPACE='TS32K'"):
            # After drop probe, report missing -> allow create path later
            return _FakeResult(first_val=(0,))
        return _FakeResult()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, conn_factory):
        self.dialect = type('D', (), {'name': 'ibm_db_sa'})()
        self._log = []
        self._conn_factory = conn_factory

    def begin(self):
        return self._conn_factory(self._log)


@pytest.mark.unit
def test_db2_branch_case_a_bp_drop_then_create(monkeypatch):
    monkeypatch.setattr(mig, 'inspect', lambda _e: object())
    called = {'seed': False}
    monkeypatch.setattr(mig, 'seed_default_props', lambda _e: called.__setitem__('seed', True))

    eng = _FakeEngine(_ConnCaseA)
    mig.init_db(eng)  # type: ignore[arg-type]

    # Expect attempts to DROP BUFFERPOOL and CREATE BUFFERPOOL/TS
    joined = '\n'.join(eng._log)
    assert 'DROP BUFFERPOOL BP32K' in joined
    assert 'CREATE BUFFERPOOL BP32K' in joined
    assert 'CREATE TABLESPACE TS32K' in joined
    assert called['seed'] is True


@pytest.mark.unit
def test_db2_branch_case_b_ts_drop_and_bp_drop(monkeypatch):
    monkeypatch.setattr(mig, 'inspect', lambda _e: object())
    monkeypatch.setattr(mig, 'seed_default_props', lambda _e: None)

    eng = _FakeEngine(_ConnCaseB)
    mig.init_db(eng)  # type: ignore[arg-type]

    joined = '\n'.join(eng._log)
    # Should attempt DROP TABLESPACE and DROP BUFFERPOOL due to wrong sizes
    assert 'DROP TABLESPACE TS32K' in joined
    assert 'DROP BUFFERPOOL BP32K' in joined
