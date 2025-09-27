from __future__ import annotations

import logging
import os
from typing import Any, Optional, cast

from flask import Blueprint, current_app, jsonify, request, session
from sqlalchemy.engine import Engine

from ..db.admins import (
    check_admin_password,
    get_admin_by_username,
    seed_default_admin,
    set_admin_password,
    set_admin_webauthn,
    update_admin_sign_count,
)
from ..db.engine import get_user_engine
from .auth import clear_login, login_required, set_logged_in


def _get_um_engine() -> Engine:
    """Resolve the engine to use for user management.

    Preference order:
      1) app.config['um_engine'] if provided (tests can inject a custom engine)
      2) app.config['db_engine'] if available (used in unit tests for isolation)
      3) get_user_engine() default (SQLite file or per-test in-memory)
    """
    eng = cast(Optional[Engine], current_app.config.get('um_engine'))
    if eng is not None:
        return eng
    eng = cast(Optional[Engine], current_app.config.get('db_engine'))
    if eng is not None:
        return eng
    return get_user_engine()


# WebAuthn (duo-labs py_webauthn)
try:
    import webauthn as _webauthn
    from webauthn import helpers as _wa_helpers

    _wa_structs = _wa_helpers.structs
except Exception:  # pragma: no cover - optional dep in unit tests
    _webauthn = None  # type: ignore[assignment]
    _wa_structs = None  # type: ignore[assignment]

# Expose globals for tests to monkeypatch while keeping optional import pattern
# Functions
generate_registration_options = (
    getattr(_webauthn, 'generate_registration_options', None) if _webauthn else None
)
options_to_json = getattr(_webauthn, 'options_to_json', None) if _webauthn else None
verify_registration_response = (
    getattr(_webauthn, 'verify_registration_response', None) if _webauthn else None
)
generate_authentication_options = (
    getattr(_webauthn, 'generate_authentication_options', None) if _webauthn else None
)
verify_authentication_response = (
    getattr(_webauthn, 'verify_authentication_response', None) if _webauthn else None
)
# Classes/structs
RegistrationCredential = getattr(_webauthn, 'RegistrationCredential', None) if _webauthn else None
AuthenticationCredential = (
    getattr(_webauthn, 'AuthenticationCredential', None) if _webauthn else None
)
PublicKeyCredentialDescriptor = (
    getattr(_wa_structs, 'PublicKeyCredentialDescriptor', None) if _wa_structs else None
)
AuthenticatorSelectionCriteria = (
    getattr(_wa_structs, 'AuthenticatorSelectionCriteria', None) if _wa_structs else None
)
UserVerificationRequirement = (
    getattr(_wa_structs, 'UserVerificationRequirement', None) if _wa_structs else None
)
AttestationConveyancePreference = (
    getattr(_wa_structs, 'AttestationConveyancePreference', None) if _wa_structs else None
)


bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.route('/password/login', methods=['POST'])
@bp.route('/login/password', methods=['POST'])
def password_login():
    data: dict[str, Any] = cast(dict[str, Any], request.get_json(force=True) or {})
    username = (data.get('username') or os.environ.get('ADMIN_USERNAME', 'admin')).strip()
    password = (data.get('password') or '').strip()

    # Use the dedicated user engine, allow app override via 'um_engine' or fallback to db_engine
    eng: Engine = _get_um_engine()

    # Ensure a default admin exists on this engine for first-run scenarios
    try:
        admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
        seed_default_admin(eng, admin_username, 'postfixblocker')
    except Exception as exc:
        logging.getLogger('api').debug('Seed default admin skipped/failed: %s', exc)

    if not check_admin_password(eng, username, password):
        return jsonify({'error': 'invalid credentials'}), 401

    admin = get_admin_by_username(eng, username) or {}
    must_change = bool(admin.get('must_change_password'))

    if must_change:
        # Don't set a full session yet; client must call password/change
        session['pending_username'] = username
        # Frontend expects SessionInfo shape
        return jsonify(
            {'authenticated': False, 'username': username, 'mustChangePassword': True},
        ), 200

    set_logged_in(username)
    return jsonify(
        {
            'authenticated': True,
            'username': username,
            'mustChangePassword': False,
            'hasWebAuthn': bool(admin.get('webauthn_credential_id')),
        },
    ), 200


@bp.route('/password/change', methods=['POST'])
@bp.route('/change-password', methods=['POST'])
def password_change():
    data: dict[str, Any] = cast(dict[str, Any], request.get_json(force=True) or {})
    username = (
        data.get('username')
        or session.get('pending_username')
        or os.environ.get('ADMIN_USERNAME', 'admin')
    ).strip()  # type: ignore[union-attr]
    old_password = (data.get('old_password') or '').strip()
    new_password = (data.get('new_password') or '').strip()

    if not username or not new_password:
        return jsonify({'error': 'username and new_password required'}), 400

    eng: Engine = _get_um_engine()

    # Require old password if set; otherwise allow first-time set
    if old_password and not check_admin_password(eng, username, old_password):
        return jsonify({'error': 'invalid credentials'}), 401

    set_admin_password(eng, username, new_password, must_change=False)
    session.pop('pending_username', None)
    set_logged_in(username)
    admin = get_admin_by_username(eng, username) or {}
    return jsonify(
        {
            'authenticated': True,
            'username': username,
            'mustChangePassword': False,
            'hasWebAuthn': bool(admin.get('webauthn_credential_id')),
        },
    ), 200


@bp.route('/logout', methods=['POST'])
@login_required
def logout():
    clear_login()
    return jsonify({'ok': True})


@bp.route('/me', methods=['GET'])
@bp.route('/session', methods=['GET'])
def me():
    # Report anonymous session accurately without exposing default username
    username = session.get('admin_user')
    if not username:
        return jsonify(
            {
                'authenticated': False,
                'username': '',
                'mustChangePassword': False,
                'hasWebAuthn': False,
            },
        )
    eng: Engine = _get_um_engine()
    admin = get_admin_by_username(eng, username) or {}
    return jsonify(
        {
            'authenticated': True,
            'username': username,
            'mustChangePassword': bool(admin.get('must_change_password')),
            'hasWebAuthn': bool(admin.get('webauthn_credential_id')),
        },
    )


# ---- WebAuthn flows ----


def _rp_id() -> str:
    # Prefer explicit env; else derive from Host header
    host = request.headers.get('Host', '')
    env_id = os.environ.get('RP_ID')
    if env_id:
        return env_id
    # Strip port
    return host.split(':', 1)[0]


def _origin() -> str:
    return os.environ.get('ORIGIN') or f'https://{request.headers.get("Host")}'


@bp.route('/register/challenge', methods=['GET'])
@login_required
def register_challenge():
    # Enforce an actual authenticated session even if API auth is globally disabled
    username = session.get('admin_user')
    if not username:
        return jsonify({'error': 'unauthorized'}), 401
    if (
        generate_registration_options is None
        or options_to_json is None
        or AttestationConveyancePreference is None
        or AuthenticatorSelectionCriteria is None
        or UserVerificationRequirement is None
    ):
        return jsonify({'error': 'webauthn_unavailable'}), 503

    # Store a user handle (stable) for the single admin
    user_id = (os.environ.get('ADMIN_USER_ID') or 'admin-user-1').encode('utf-8')

    options = generate_registration_options(
        rp_id=_rp_id(),
        rp_name='Postfix Blocker',
        user_id=user_id,
        user_name=username,
        user_display_name=username,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    # Store b64url challenge string in session for JSON-safe transport
    try:
        import base64 as _b64

        chal_b64 = _b64.urlsafe_b64encode(options.challenge).decode('ascii')  # type: ignore[attr-defined]
    except Exception:
        chal_b64 = ''
    session['webauthn_current_challenge'] = chal_b64
    return jsonify(options_to_json(options))


@bp.route('/register/verify', methods=['POST'])
@login_required
def register_verify():
    # Enforce an actual authenticated session even if API auth is globally disabled
    username = session.get('admin_user')
    if not username:
        return jsonify({'error': 'unauthorized'}), 401
    if verify_registration_response is None:
        return jsonify({'error': 'webauthn_unavailable'}), 503
    if RegistrationCredential is None:
        return jsonify({'error': 'webauthn_unavailable'}), 503
    cred = RegistrationCredential.parse_raw(request.data)

    # Decode challenge from session (base64url)
    import base64 as _b64

    chal_b64 = session.get('webauthn_current_challenge') or ''
    try:
        expected_chal: bytes = _b64.urlsafe_b64decode(chal_b64.encode('ascii'))
    except Exception:
        expected_chal = b''

    verification = verify_registration_response(
        credential=cred,
        expected_challenge=expected_chal,
        expected_rp_id=_rp_id(),
        expected_origin=_origin(),
        require_user_verification=False,
    )

    # Persist credential (store as base64url strings)
    eng: Engine = _get_um_engine()
    cred_id_b64 = _b64.urlsafe_b64encode(verification.credential_id).decode('ascii')  # type: ignore[attr-defined]
    pubkey_b64 = _b64.urlsafe_b64encode(verification.credential_public_key).decode('ascii')  # type: ignore[attr-defined]
    set_admin_webauthn(
        eng,
        username,
        credential_id=cred_id_b64,
        public_key=pubkey_b64,
        sign_count=verification.sign_count,  # type: ignore[attr-defined]
    )

    admin = get_admin_by_username(eng, username) or {}
    return jsonify(
        {
            'authenticated': True,
            'username': username,
            'mustChangePassword': False,
            'hasWebAuthn': bool(admin.get('webauthn_credential_id')),
        },
    )


@bp.route('/login/challenge', methods=['GET'])
def login_challenge():
    """Public endpoint to start passkey login.

    Returns 404 if no passkey is registered to avoid probing.
    """
    if (
        generate_authentication_options is None
        or options_to_json is None
        or PublicKeyCredentialDescriptor is None
        or UserVerificationRequirement is None
    ):
        return jsonify({'error': 'webauthn_unavailable'}), 503
    eng: Engine = _get_um_engine()
    username = os.environ.get('ADMIN_USERNAME', 'admin')
    admin = get_admin_by_username(eng, username)
    if not admin or not admin.get('webauthn_credential_id'):
        # Hide existence
        return jsonify({'error': 'not found'}), 404

    # Decode stored credential id (base64url) to bytes for allowCredentials
    import base64 as _b64

    try:
        cred_id_bytes = _b64.urlsafe_b64decode(
            (admin['webauthn_credential_id'] or '').encode('ascii'),
        )
    except Exception:
        cred_id_bytes = b''
    allow = [
        PublicKeyCredentialDescriptor(
            id=cred_id_bytes,
            type='public-key',  # type: ignore[arg-type]
        ),
    ]
    options = generate_authentication_options(
        rp_id=_rp_id(),
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    # Store b64url challenge string in session
    try:
        import base64 as _b64

        chal_b64 = _b64.urlsafe_b64encode(options.challenge).decode('ascii')  # type: ignore[attr-defined]
    except Exception:
        chal_b64 = ''
    session['webauthn_current_challenge'] = chal_b64
    return jsonify(options_to_json(options))


@bp.route('/login/verify', methods=['POST'])
def login_verify():
    if verify_authentication_response is None:
        return jsonify({'error': 'webauthn_unavailable'}), 503
    if AuthenticationCredential is None:
        return jsonify({'error': 'webauthn_unavailable'}), 503
    eng: Engine = _get_um_engine()
    username = os.environ.get('ADMIN_USERNAME', 'admin')
    admin = get_admin_by_username(eng, username) or {}
    if not admin or not admin.get('webauthn_public_key'):
        return jsonify({'error': 'not found'}), 404

    cred = AuthenticationCredential.parse_raw(request.data)

    # Decode challenge from session (base64url)
    import base64 as _b64

    chal_b64 = session.get('webauthn_current_challenge') or ''
    try:
        expected_chal: bytes = _b64.urlsafe_b64decode(chal_b64.encode('ascii'))
    except Exception:
        expected_chal = b''

    # Decode stored public key (base64url) back to bytes
    try:
        pubkey_bytes = _b64.urlsafe_b64decode((admin['webauthn_public_key'] or '').encode('ascii'))
    except Exception:
        pubkey_bytes = b''

    verification = verify_authentication_response(
        credential=cred,
        expected_challenge=expected_chal,
        expected_rp_id=_rp_id(),
        expected_origin=_origin(),
        credential_public_key=pubkey_bytes,
        credential_current_sign_count=admin.get('webauthn_sign_count') or 0,
        require_user_verification=False,
    )

    # Update counter and set session
    update_admin_sign_count(eng, username, verification.new_sign_count)  # type: ignore[attr-defined]
    set_logged_in(username)
    admin = get_admin_by_username(eng, username) or {}
    return jsonify(
        {
            'authenticated': True,
            'username': username,
            'mustChangePassword': False,
            'hasWebAuthn': bool(admin.get('webauthn_credential_id')),
        },
    )
