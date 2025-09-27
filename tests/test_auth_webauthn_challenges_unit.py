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
def test_webauthn_login_challenge_404_and_register_challenge_requires_login(monkeypatch):
    # Ensure auth disabled globally (login_required no-op), but register endpoints enforce session
    monkeypatch.setenv('API_AUTH_REQUIRED', '0')

    eng = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(eng)

    app = create_app()
    app.testing = True
    app.config['db_engine'] = eng
    app.config['ensure_db_ready'] = lambda: True

    with app.test_client() as c:
        # No passkey registered by default -> login challenge should 404 (do not leak existence)
        r = c.get('/auth/login/challenge')
        assert r.status_code == 404

        # Register challenge without an authenticated session -> 401
        rr = c.get('/auth/register/challenge')
        assert rr.status_code == 401

        # Simulate a logged-in session to reach register challenge 200 path
        with c.session_transaction() as sess:
            sess['admin_user'] = 'admin'
        r2 = c.get('/auth/register/challenge')
        # If webauthn lib missing in runtime, endpoint returns 503; accept both 200 and 503
        assert r2.status_code in (200, 503)
        if r2.status_code == 200:
            js_raw = r2.get_json()
            # Endpoint may wrap an already-serialized JSON string; accept both forms
            if isinstance(js_raw, str):
                import json as _json

                js = _json.loads(js_raw)
            else:
                js = js_raw or {}
            # Simple shape check from options_to_json
            assert isinstance(js, dict) and ('challenge' in js or 'rp' in js)
