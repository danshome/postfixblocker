from __future__ import annotations

import pytest

from postfix_blocker.web.app_factory import create_app
from postfix_blocker.web.auth import SESSION_USER_KEY, is_logged_in


@pytest.mark.unit
def test_is_logged_in_true_with_session_user(monkeypatch):
    monkeypatch.setenv('API_AUTH_REQUIRED', '1')
    app = create_app()
    app.testing = True
    with app.test_request_context('/'):
        # Set a logged-in user in the session
        from flask import session

        session[SESSION_USER_KEY] = 'admin'
        assert is_logged_in() is True
