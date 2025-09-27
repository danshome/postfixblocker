# ruff: noqa: E402
from __future__ import annotations

"""Admin storage utilities (single-admin model).

Provides helpers to seed a default admin, lookup and update admin credentials,
including password and WebAuthn fields.
"""
import logging

from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from werkzeug.security import check_password_hash, generate_password_hash

from .schema import get_user_table

LOGGER = logging.getLogger(__name__)


def _ensure_um_table_on(engine: Engine) -> None:
    """Ensure the UM_USER table exists on the provided engine.

    This makes admin helpers robust when called with a test-provided Engine
    (e.g., SQLite in-memory) where migrations.init_db() may not have created
    the UM table on that same engine.
    """
    try:
        ut = get_user_table()
        # checkfirst avoids errors if the table already exists
        ut.create(engine, checkfirst=True)
    except Exception as exc:  # pragma: no cover - dialect specific
        LOGGER.debug('ensure UM_USER table failed (ignored): %s', exc)


def seed_default_admin(engine: Engine, username: str, default_password: str) -> None:
    """Ensure a single admin row exists.

    If no admin with the given username exists, insert one with a default password
    and must_change_password flag set.
    """
    _ensure_um_table_on(engine)
    at = get_user_table()
    with engine.begin() as conn:
        exists = False
        try:
            exists = bool(
                conn.execute(
                    select(func.count()).select_from(at).where(at.c.username == username),
                ).scalar()
                or 0,
            )
        except Exception:
            # Fallback attempt
            try:
                exists = bool(
                    conn.exec_driver_sql(
                        'SELECT 1 FROM um_user WHERE username = ?',
                        (username,),
                    ).first(),
                )
            except Exception as exc:
                LOGGER.debug('Admin exists probe failed: %s', exc)
        if exists:
            return
        LOGGER.info('Seeding default admin user %s', username)
        pwd_hash = generate_password_hash(default_password)
        conn.execute(
            at.insert().values(
                username=username,
                password_hash=pwd_hash,
                must_change_password=True,
                webauthn_credential_id=None,
                webauthn_public_key=None,
                webauthn_sign_count=None,
                created_at=func.current_timestamp(),
                updated_at=func.current_timestamp(),
            ),
        )


def get_admin_by_username(engine: Engine, username: str) -> dict | None:
    _ensure_um_table_on(engine)
    at = get_user_table()
    with engine.connect() as conn:
        row = conn.execute(select(at).where(at.c.username == username)).mappings().first()
        return dict(row) if row else None


def set_admin_password(
    engine: Engine,
    username: str,
    new_password: str,
    *,
    must_change: bool = False,
) -> None:
    _ensure_um_table_on(engine)
    at = get_user_table()
    pwd_hash = generate_password_hash(new_password)
    with engine.begin() as conn:
        rc = (
            conn.execute(
                at.update()
                .where(at.c.username == username)
                .values(
                    password_hash=pwd_hash,
                    must_change_password=must_change,
                    updated_at=func.current_timestamp(),
                ),
            ).rowcount
            or 0
        )
        if rc == 0:
            # Insert if missing
            conn.execute(
                at.insert().values(
                    username=username,
                    password_hash=pwd_hash,
                    must_change_password=must_change,
                    created_at=func.current_timestamp(),
                    updated_at=func.current_timestamp(),
                ),
            )


def check_admin_password(engine: Engine, username: str, candidate: str) -> bool:
    admin = get_admin_by_username(engine, username)
    if not admin or not admin.get('password_hash'):
        return False
    return check_password_hash(admin['password_hash'], candidate)


def set_admin_webauthn(
    engine: Engine,
    username: str,
    credential_id: str,
    public_key: str,
    sign_count: int,
) -> None:
    _ensure_um_table_on(engine)
    at = get_user_table()
    with engine.begin() as conn:
        rc = (
            conn.execute(
                at.update()
                .where(at.c.username == username)
                .values(
                    webauthn_credential_id=credential_id,
                    webauthn_public_key=public_key,
                    webauthn_sign_count=sign_count,
                    updated_at=func.current_timestamp(),
                ),
            ).rowcount
            or 0
        )
        if rc == 0:
            # Insert a new row if missing
            conn.execute(
                at.insert().values(
                    username=username,
                    password_hash=None,
                    must_change_password=True,
                    webauthn_credential_id=credential_id,
                    webauthn_public_key=public_key,
                    webauthn_sign_count=sign_count,
                    created_at=func.current_timestamp(),
                    updated_at=func.current_timestamp(),
                ),
            )


def update_admin_sign_count(engine: Engine, username: str, sign_count: int) -> None:
    _ensure_um_table_on(engine)
    at = get_user_table()
    with engine.begin() as conn:
        conn.execute(
            at.update()
            .where(at.c.username == username)
            .values(webauthn_sign_count=sign_count, updated_at=func.current_timestamp()),
        )
