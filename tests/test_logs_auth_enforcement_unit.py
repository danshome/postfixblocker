from __future__ import annotations

import pytest

from postfix_blocker.web.app_factory import create_app


@pytest.mark.unit
def test_logs_endpoints_require_auth_when_enabled(monkeypatch):
    # Enforce authentication globally
    monkeypatch.setenv('API_AUTH_REQUIRED', '1')

    app = create_app()
    app.testing = True

    with app.test_client() as c:
        # /logs/tail requires auth
        r1 = c.get('/logs/tail', query_string={'name': 'api', 'lines': '5'})
        assert r1.status_code == 401

        # /logs/lines requires auth
        r2 = c.get('/logs/lines', query_string={'name': 'api'})
        assert r2.status_code == 401

        # /logs/refresh requires auth (GET)
        r3 = c.get('/logs/refresh/api')
        assert r3.status_code == 401

        # /logs/refresh requires auth (PUT)
        r4 = c.put('/logs/refresh/api', json={'interval_ms': 1000, 'lines': 200})
        assert r4.status_code == 401
