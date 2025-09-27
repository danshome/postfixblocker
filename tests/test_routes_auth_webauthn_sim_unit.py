from __future__ import annotations

import base64

import pytest

try:
    from sqlalchemy import create_engine
except Exception:  # pragma: no cover - SQLAlchemy may be missing
    create_engine = None  # type: ignore

from postfix_blocker.db.admins import get_admin_by_username, set_admin_webauthn
from postfix_blocker.db.migrations import init_db
from postfix_blocker.web.app_factory import create_app


@pytest.mark.unit
@pytest.mark.skipif(create_engine is None, reason='SQLAlchemy not installed')
def test_simulated_webauthn_register_flow(monkeypatch):
    eng = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(eng)

    app = create_app()
    app.testing = True
    app.config['db_engine'] = eng
    app.config['ensure_db_ready'] = lambda: True

    # Monkeypatch routes_auth to simulate library behavior
    from postfix_blocker.web import routes_auth as ra

    class _Opts:
        def __init__(self, challenge: bytes):
            self.challenge = challenge

    monkeypatch.setattr(
        ra,
        'generate_registration_options',
        lambda **kwargs: _Opts(b'abcd'),
    )
    monkeypatch.setattr(ra, 'options_to_json', lambda options: {'ok': True, 'chal': 'abcd'})

    class _Cred:
        @staticmethod
        def parse_raw(data: bytes):
            return object()

    class _VerifyRes:
        credential_id = b'cid'
        credential_public_key = b'pk'
        sign_count = 5

    monkeypatch.setattr(ra, 'RegistrationCredential', _Cred)
    monkeypatch.setattr(ra, 'verify_registration_response', lambda **kwargs: _VerifyRes())

    with app.test_client() as c:
        # Set session user
        with c.session_transaction() as sess:
            sess['admin_user'] = 'admin'
        # Challenge
        r1 = c.get('/auth/register/challenge')
        assert r1.status_code == 200
        # Verify
        r2 = c.post('/auth/register/verify', data=b'{}', content_type='application/json')
        assert r2.status_code == 200

    # DB should now have WebAuthn info
    adm = get_admin_by_username(eng, 'admin') or {}
    assert adm.get('webauthn_credential_id')
    assert adm.get('webauthn_public_key')


@pytest.mark.unit
@pytest.mark.skipif(create_engine is None, reason='SQLAlchemy not installed')
def test_simulated_webauthn_login_flow(monkeypatch):
    eng = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(eng)

    # Seed admin with webauthn fields
    cid_b64 = base64.urlsafe_b64encode(b'cid').decode('ascii')
    pk_b64 = base64.urlsafe_b64encode(b'pk').decode('ascii')
    set_admin_webauthn(eng, 'admin', credential_id=cid_b64, public_key=pk_b64, sign_count=2)

    app = create_app()
    app.testing = True
    app.config['db_engine'] = eng
    app.config['ensure_db_ready'] = lambda: True

    from postfix_blocker.web import routes_auth as ra

    class _Opts:
        def __init__(self, challenge: bytes):
            self.challenge = challenge

    monkeypatch.setattr(ra, 'generate_authentication_options', lambda **kwargs: _Opts(b'xyz'))
    monkeypatch.setattr(ra, 'options_to_json', lambda options: {'ok': True, 'chal': 'xyz'})

    class _Cred:
        @staticmethod
        def parse_raw(data: bytes):
            return object()

    class _VerifyRes:
        new_sign_count = 7

    monkeypatch.setattr(ra, 'AuthenticationCredential', _Cred)
    monkeypatch.setattr(ra, 'verify_authentication_response', lambda **kwargs: _VerifyRes())

    with app.test_client() as c:
        # Challenge should be 200 (credential exists)
        r1 = c.get('/auth/login/challenge')
        assert r1.status_code == 200
        # Verify (library simulated)
        r2 = c.post('/auth/login/verify', data=b'{}', content_type='application/json')
        assert r2.status_code == 200
        body = r2.get_json() or {}
        assert body.get('authenticated') is True
        assert body.get('username') == 'admin'
