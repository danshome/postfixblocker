from __future__ import annotations

import pytest

try:
    from sqlalchemy import create_engine
except Exception:  # pragma: no cover
    create_engine = None  # type: ignore

from postfix_blocker.db.migrations import init_db
from postfix_blocker.web.app_factory import create_app


@pytest.mark.unit
@pytest.mark.skipif(create_engine is None, reason='SQLAlchemy not installed')
def test_password_login_change_logout_flow(monkeypatch):
    # Ensure default admin is 'admin'
    monkeypatch.setenv('ADMIN_USERNAME', 'admin')

    eng = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(eng)

    app = create_app()
    app.config['db_engine'] = eng
    app.config['db_ready'] = True
    app.config['ensure_db_ready'] = lambda: True

    client = app.test_client()

    # Login with default password -> mustChangePassword True
    r1 = client.post(
        '/auth/login/password',
        json={'username': 'admin', 'password': 'postfixblocker'},
    )
    assert r1.status_code == 200
    body1 = r1.get_json() or {}
    assert body1.get('authenticated') is False
    assert body1.get('mustChangePassword') is True

    # Change password (first-time set allows old password blank)
    r2 = client.post('/auth/change-password', json={'new_password': 'newpass123'})
    assert r2.status_code == 200
    body2 = r2.get_json() or {}
    assert body2.get('authenticated') is True
    assert body2.get('mustChangePassword') is False

    # /auth/me reflects logged-in session
    me = client.get('/auth/me')
    assert me.status_code == 200
    assert (me.get_json() or {}).get('authenticated') is True

    # Logout
    lo = client.post('/auth/logout')
    assert lo.status_code == 200
    assert (lo.get_json() or {}).get('ok') is True

    # After logout, /auth/me is anonymous
    me2 = client.get('/auth/me')
    assert me2.status_code == 200
    assert (me2.get_json() or {}).get('authenticated') is False


@pytest.mark.unit
@pytest.mark.skipif(create_engine is None, reason='SQLAlchemy not installed')
def test_auth_required_toggle(monkeypatch):
    # When API_AUTH_REQUIRED=0, login_required should be no-op
    monkeypatch.delenv('API_AUTH_REQUIRED', raising=False)
    eng = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(eng)
    app = create_app()
    app.config['db_engine'] = eng
    app.config['db_ready'] = True
    app.config['ensure_db_ready'] = lambda: True
    c = app.test_client()
    # addresses should be accessible without session
    r = c.get('/addresses')
    assert r.status_code in (200,)

    # With API_AUTH_REQUIRED=1, expect 401s for protected endpoints when not logged in
    monkeypatch.setenv('API_AUTH_REQUIRED', '1')
    app2 = create_app()
    app2.config['db_engine'] = eng
    app2.config['db_ready'] = True
    app2.config['ensure_db_ready'] = lambda: True
    c2 = app2.test_client()
    r401 = c2.get('/addresses')
    assert r401.status_code == 401
