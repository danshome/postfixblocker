from __future__ import annotations

import pytest

try:
    from sqlalchemy import create_engine
except Exception:  # pragma: no cover - SQLAlchemy may be missing in minimal envs
    create_engine = None  # type: ignore

from postfix_blocker.db.migrations import init_db
from postfix_blocker.web import auth as web_auth
from postfix_blocker.web.app_factory import create_app


@pytest.mark.unit
@pytest.mark.skipif(create_engine is None, reason='SQLAlchemy not installed')
def test_logs_put_missing_level_and_db_not_ready(monkeypatch):
    eng = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(eng)
    app = create_app()
    app.testing = True
    app.config['db_engine'] = eng
    # Simulate DB not ready for first call
    app.config['ensure_db_ready'] = lambda: False
    with app.test_client() as c:
        # DB not ready -> 503
        r503 = c.get('/logs/level/api')
        assert r503.status_code == 503
        # Now make DB ready to test PUT missing-level 400
        app.config['ensure_db_ready'] = lambda: True
        r400 = c.put('/logs/level/api', json={})
        assert r400.status_code == 400


@pytest.mark.unit
def test_auth_required_and_login_required_denial(monkeypatch):
    # Enforce auth requirement
    monkeypatch.setenv('API_AUTH_REQUIRED', '1')

    # Build app and call a protected endpoint without session -> 401
    app = create_app()
    app.testing = True
    # is_logged_in should be False within a request context when no session user
    with app.test_request_context('/'):
        assert web_auth.is_logged_in() is False
    # Avoid DB init by forcing ensure_db_ready True and dummy engine when needed
    if create_engine is not None:
        eng = create_engine('sqlite:///:memory:')  # type: ignore[misc]
        init_db(eng)
        app.config['db_engine'] = eng
    app.config['ensure_db_ready'] = lambda: True
    with app.test_client() as c:
        r = c.get('/logs/level/api')
        assert r.status_code == 401


@pytest.mark.unit
@pytest.mark.skipif(create_engine is None, reason='SQLAlchemy not installed')
def test_addresses_column_inspection_fallback(monkeypatch):
    # Force the SQLAlchemy inspector to raise so the code takes the exception path
    from postfix_blocker.web import routes_addresses as ra

    eng = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(eng)
    app = create_app()
    app.testing = True
    app.config['db_engine'] = eng
    app.config['ensure_db_ready'] = lambda: True

    # Patch inspect() used inside add_address to raise
    monkeypatch.setattr(ra, 'inspect', lambda _e: (_ for _ in ()).throw(RuntimeError('oops')))

    with app.test_client() as c:
        r = c.post(
            '/addresses',
            json={'pattern': 'x@example.com', 'is_regex': False, 'test_mode': True},
        )
        assert r.status_code == 201
