from __future__ import annotations

import pytest
from flask import Flask

from postfix_blocker.web.auth import SESSION_USER_KEY, login_required


@pytest.mark.unit
def test_login_required_allows_when_user_present(monkeypatch):
    # Require auth
    monkeypatch.setenv('API_AUTH_REQUIRED', '1')

    app = Flask(__name__)
    app.secret_key = 'test-key'

    @app.route('/ping')
    @login_required
    def ping():  # type: ignore[no-untyped-def]
        return 'ok'

    # Use test client and set session value within a request context
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess[SESSION_USER_KEY] = 'admin'
        resp = client.get('/ping')
        assert resp.status_code == 200
        assert resp.get_data(as_text=True) == 'ok'

    # Cleanup
    monkeypatch.delenv('API_AUTH_REQUIRED', raising=False)
