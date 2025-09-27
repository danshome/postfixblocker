from __future__ import annotations

import pytest

try:
    from sqlalchemy import create_engine
except Exception:  # pragma: no cover - SQLAlchemy may be missing in minimal envs
    create_engine = None  # type: ignore

from postfix_blocker.db.migrations import init_db
from postfix_blocker.web.app_factory import create_app


@pytest.mark.unit
@pytest.mark.skipif(create_engine is None, reason='SQLAlchemy not installed')
def test_test_reset_blueprint_dump_and_reset(monkeypatch):
    # Enable test reset blueprint
    monkeypatch.setenv('TEST_RESET_ENABLE', '1')

    eng = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(eng)

    app = create_app()
    app.testing = True
    app.config['db_engine'] = eng
    app.config['ensure_db_ready'] = lambda: True

    with app.test_client() as c:
        # Dump initial state (should be empty arrays or seeded props)
        d = c.get('/test/dump')
        assert d.status_code == 200
        js = d.get_json() or {}
        assert 'blocked' in js and 'props' in js

        # Reset and seed one entry
        r = c.post(
            '/test/reset',
            json={'seeds': [{'pattern': 'seed@example.com', 'is_regex': False, 'test_mode': True}]},
        )
        assert r.status_code == 200
        # Dump again to verify seed present
        d2 = c.get('/test/dump')
        assert any(
            it['pattern'] == 'seed@example.com' for it in (d2.get_json() or {}).get('blocked', [])
        )
