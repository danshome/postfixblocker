from __future__ import annotations

import pytest

from postfix_blocker.web import app_factory as af


@pytest.mark.unit
def test_ensure_db_ready_idempotent(monkeypatch):
    # Provide a fake engine and stub migrations.init_db
    class _FakeEngine:
        dialect = type('D', (), {'name': 'sqlite'})()

    calls = {'init': 0, 'get_engine': 0}

    def _fake_get_engine():
        calls['get_engine'] += 1
        return _FakeEngine()

    def _fake_init_db(_engine):  # pragma: no cover - tiny shim
        calls['init'] += 1

    monkeypatch.setattr(af, '_get_engine', _fake_get_engine)
    monkeypatch.setattr(af, '_init_db', _fake_init_db)

    app = af.create_app()

    # First call should create engine and init DB
    ensure = app.config.get('ensure_db_ready')
    assert callable(ensure)
    assert ensure() is True  # type: ignore[misc]
    assert calls['get_engine'] == 1
    assert calls['init'] == 1

    # Second call should be a no-op (idempotent)
    assert ensure() is True  # type: ignore[misc]
    assert calls['get_engine'] == 1
    assert calls['init'] == 1
