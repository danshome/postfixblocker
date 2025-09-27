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
def test_password_login_change_and_me(monkeypatch):
    # Ensure auth is considered required=0 so login_required passes freely except /register endpoints
    monkeypatch.setenv('API_AUTH_REQUIRED', '0')
    monkeypatch.delenv('ADMIN_USERNAME', raising=False)

    eng = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(eng)

    app = create_app()
    app.testing = True
    app.config['db_engine'] = eng
    app.config['ensure_db_ready'] = lambda: True

    with app.test_client() as c:
        # Default seed admin is 'admin' with password 'postfixblocker' and must_change_password=True
        r_login = c.post(
            '/auth/login/password',
            json={'username': 'admin', 'password': 'postfixblocker'},
        )
        assert r_login.status_code == 200
        js = r_login.get_json() or {}
        assert js.get('authenticated') is False
        assert js.get('mustChangePassword') is True

        # Change password -> should authenticate and clear mustChange
        r_change = c.post(
            '/auth/change-password',
            json={'old_password': 'postfixblocker', 'new_password': 'newpass'},
        )
        assert r_change.status_code == 200
        js2 = r_change.get_json() or {}
        assert js2.get('authenticated') is True
        assert js2.get('mustChangePassword') is False

        # /auth/me should now show authenticated session
        r_me = c.get('/auth/me')
        assert r_me.status_code == 200
        js3 = r_me.get_json() or {}
        assert js3.get('authenticated') is True
        assert (js3.get('username') or '') != ''

        # logout returns ok
        r_out = c.post('/auth/logout')
        assert r_out.status_code == 200
        assert (r_out.get_json() or {}).get('ok') is True
