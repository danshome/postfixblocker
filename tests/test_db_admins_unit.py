from __future__ import annotations

import pytest

try:
    from sqlalchemy import create_engine
except Exception:  # pragma: no cover - SQLAlchemy may be missing in some minimal envs
    create_engine = None  # type: ignore

from postfix_blocker.db.admins import (
    check_admin_password,
    get_admin_by_username,
    seed_default_admin,
    set_admin_password,
    set_admin_webauthn,
    update_admin_sign_count,
)
from postfix_blocker.db.migrations import init_db


@pytest.mark.unit
@pytest.mark.skipif(
    create_engine is None,
    reason='SQLAlchemy not installed; admin unit tests require it.',
)
def test_admin_seed_and_password_and_webauthn_flow(monkeypatch):
    # Use an in-memory SQLite engine
    engine = create_engine('sqlite:///:memory:')  # type: ignore[misc]

    # Ensure a clean schema
    init_db(engine)

    # The generic init_db seeds default admin using ADMIN_USERNAME env (default: 'admin')
    username = 'admin'

    # Ensure seed helper is idempotent and does not crash when called again explicitly
    seed_default_admin(engine, username, 'postfixblocker')

    # Default password should be the seed value and must_change_password should be True
    admin = get_admin_by_username(engine, username) or {}
    assert admin, 'seeded admin should exist'
    assert admin.get('must_change_password') is True
    assert check_admin_password(engine, username, 'postfixblocker') is True
    assert check_admin_password(engine, username, 'wrongpass') is False

    # Update password and clear must_change flag
    set_admin_password(engine, username, 's3cret-new', must_change=False)
    admin2 = get_admin_by_username(engine, username) or {}
    assert admin2.get('must_change_password') is False
    assert check_admin_password(engine, username, 's3cret-new') is True
    assert check_admin_password(engine, username, 'postfixblocker') is False

    # Set WebAuthn details and verify
    set_admin_webauthn(engine, username, credential_id='credB64', public_key='pkB64', sign_count=5)
    admin3 = get_admin_by_username(engine, username) or {}
    assert admin3.get('webauthn_credential_id') == 'credB64'
    assert admin3.get('webauthn_public_key') == 'pkB64'
    assert int(admin3.get('webauthn_sign_count') or 0) == 5

    # Update sign counter only
    update_admin_sign_count(engine, username, 7)
    admin4 = get_admin_by_username(engine, username) or {}
    assert int(admin4.get('webauthn_sign_count') or 0) == 7
