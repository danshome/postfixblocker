from __future__ import annotations

import pytest

try:
    from sqlalchemy import create_engine
except Exception:  # pragma: no cover - SQLAlchemy may be missing
    create_engine = None  # type: ignore

from postfix_blocker.db.migrations import init_db
from postfix_blocker.web.app_factory import create_app


@pytest.mark.unit
@pytest.mark.skipif(create_engine is None, reason='SQLAlchemy not installed')
def test_webauthn_register_endpoints_require_session_and_return_503(monkeypatch):
    # Ensure auth decorator does not block, but register endpoints still require session user
    monkeypatch.setenv('API_AUTH_REQUIRED', '0')

    eng = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(eng)

    app = create_app()
    app.testing = True
    app.config['db_engine'] = eng
    app.config['ensure_db_ready'] = lambda: True

    with app.test_client() as c:
        # Without session user -> unauthorized
        r401 = c.get('/auth/register/challenge')
        assert r401.status_code == 401

        # With session user -> library unavailable -> 503
        with c.session_transaction() as sess:
            sess['admin_user'] = 'admin'
        # Force library-unavailable branch by monkeypatching generator to None
        from postfix_blocker.web import routes_auth as ra

        monkeypatch.setattr(ra, 'generate_registration_options', None)
        r503 = c.get('/auth/register/challenge')
        assert r503.status_code == 503

        # Verify endpoint also returns 503 when library is unavailable
        monkeypatch.setattr(ra, 'verify_registration_response', None)
        monkeypatch.setattr(ra, 'RegistrationCredential', None)
        r503v = c.post('/auth/register/verify', data=b'{}', content_type='application/json')
        assert r503v.status_code == 503


@pytest.mark.unit
@pytest.mark.skipif(create_engine is None, reason='SQLAlchemy not installed')
def test_webauthn_login_challenge_and_verify(monkeypatch):
    monkeypatch.setenv('API_AUTH_REQUIRED', '0')
    eng = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(eng)

    app = create_app()
    app.testing = True
    app.config['db_engine'] = eng
    app.config['ensure_db_ready'] = lambda: True

    with app.test_client() as c:
        # No credential registered -> 404
        r404 = c.get('/auth/login/challenge')
        assert r404.status_code == 404

        # verify endpoint returns 503 when library unavailable (first guard)
        from postfix_blocker.web import routes_auth as ra

        monkeypatch.setattr(ra, 'verify_authentication_response', None)
        r503 = c.post('/auth/login/verify', data=b'{}', content_type='application/json')
        assert r503.status_code == 503
