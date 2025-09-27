from __future__ import annotations

import pytest

from postfix_blocker.web.app_factory import create_app
from postfix_blocker.web.auth import is_logged_in


@pytest.mark.unit
def test_is_logged_in_true_when_auth_disabled(monkeypatch):
    monkeypatch.setenv('API_AUTH_REQUIRED', '0')
    # Should not require a request context since it returns early
    assert is_logged_in() is True


@pytest.mark.unit
def test_auth_routes_me_logout_and_change_password_minimal(monkeypatch):
    # Auth disabled -> logout allowed; /auth/me anonymous; change-password missing payload -> 400
    monkeypatch.setenv('API_AUTH_REQUIRED', '0')
    app = create_app()
    app.testing = True
    with app.test_client() as c:
        # Anonymous session
        r = c.get('/auth/me')
        assert r.status_code == 200
        js = r.get_json() or {}
        assert js.get('authenticated') is False
        assert js.get('username', '') == ''

        # Logout allowed even when not logged in (no-op)
        r2 = c.post('/auth/logout')
        assert r2.status_code == 200
        assert (r2.get_json() or {}).get('ok') is True

        # Change password without required fields -> 400
        r3 = c.post('/auth/change-password', json={})
        assert r3.status_code == 400

    # Now require auth -> logout without session should be 401
    monkeypatch.setenv('API_AUTH_REQUIRED', '1')
    app2 = create_app()
    app2.testing = True
    with app2.test_client() as c2:
        r4 = c2.post('/auth/logout')
        assert r4.status_code == 401


@pytest.mark.unit
def test_logs_tail_and_lines_missing_files():
    app = create_app()
    app.testing = True
    with app.test_client() as c:
        r1 = c.get('/logs/tail', query_string={'name': 'api', 'lines': '5'})
        assert r1.status_code == 200
        js1 = r1.get_json() or {}
        assert js1.get('missing') is True

        r2 = c.get('/logs/lines', query_string={'name': 'api'})
        assert r2.status_code == 200
        js2 = r2.get_json() or {}
        assert js2.get('missing') is True
