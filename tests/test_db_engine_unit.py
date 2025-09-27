from __future__ import annotations

import pytest


@pytest.mark.unit
def test_get_engine_uses_env_url_and_options(monkeypatch):
    # Use a lightweight SQLite URL to avoid real DB drivers
    monkeypatch.setenv('BLOCKER_DB_URL', 'sqlite:///:memory:')

    # Capture parameters passed to sqlalchemy.create_engine
    calls: dict = {}

    class _Dummy:
        dialect = type('D', (), {'name': 'sqlite'})()

    def fake_create_engine(url, **kwargs):
        calls['url'] = url
        calls['kwargs'] = kwargs
        return _Dummy()

    from postfix_blocker.db import engine as eng

    monkeypatch.setattr(eng, 'create_engine', fake_create_engine)

    e = eng.get_engine()
    assert isinstance(e, _Dummy)
    assert calls['url'] == 'sqlite:///:memory:'
    # Verify a few important pool kwargs are wired
    assert calls['kwargs'].get('pool_pre_ping') is True
    assert calls['kwargs'].get('pool_use_lifo') is True
    assert isinstance(calls['kwargs'].get('pool_size'), int)
