# ruff: noqa: E402
from __future__ import annotations

"""SQLAlchemy schema definitions (refactor implementation).

Defines metadata and tables for blocked addresses and properties.
"""


class _SchemaInitError(RuntimeError):
    """Base error raised when schema objects are not initialized."""


class BlockedTableNotInitializedError(_SchemaInitError):
    def __init__(self) -> None:
        super().__init__('blocked_addresses table not initialized')


class PropsTableNotInitializedError(_SchemaInitError):
    def __init__(self) -> None:
        super().__init__('cris_props table not initialized')


class AdminsTableNotInitializedError(_SchemaInitError):
    def __init__(self) -> None:
        super().__init__('admins table not initialized')


class UserTableNotInitializedError(_SchemaInitError):
    def __init__(self) -> None:
        super().__init__('um_user table not initialized')


class MetadataNotInitializedError(_SchemaInitError):
    def __init__(self) -> None:
        super().__init__('metadata not initialized')


from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    func,
)

_metadata: MetaData | None = None
_blocked_table: Table | None = None
_props_table: Table | None = None
_admins_table: Table | None = None
_user_table: Table | None = None


def _ensure_loaded() -> None:
    global _metadata, _blocked_table, _props_table, _admins_table, _user_table
    if (
        _metadata is not None
        and _blocked_table is not None
        and _props_table is not None
        and _admins_table is not None
        and _user_table is not None
    ):
        return
    _metadata = MetaData()
    _blocked_table = Table(
        'blocked_addresses',
        _metadata,
        Column('id', Integer, primary_key=True, autoincrement=True),
        Column('pattern', String(255), nullable=False),
        Column('is_regex', Boolean, nullable=False, default=False),
        Column('test_mode', Boolean, nullable=False, server_default='1'),
        Column(
            'updated_at',
            DateTime,
            server_default=func.current_timestamp(),
            onupdate=func.current_timestamp(),
        ),
    )
    _props_table = Table(
        'cris_props',
        _metadata,
        Column('key', String(1024), primary_key=True, quote=False),
        Column('value', String(1024), quote=False),
        Column(
            'update_ts',
            DateTime,
        ),
    )
    # Legacy admins table retained for backward compatibility but not used for UM
    _admins_table = Table(
        'admins',
        _metadata,
        Column('id', Integer, primary_key=True, autoincrement=True),
        Column('username', String(255), nullable=False, unique=True),
        Column('password_hash', String(255), nullable=True),
        Column('must_change_password', Boolean, nullable=False, server_default='1'),
        Column('webauthn_credential_id', String(1024), nullable=True),
        Column('webauthn_public_key', String(4096), nullable=True),
        Column('webauthn_sign_count', Integer, nullable=True),
        Column('created_at', DateTime, server_default=func.current_timestamp()),
        Column(
            'updated_at',
            DateTime,
            server_default=func.current_timestamp(),
            onupdate=func.current_timestamp(),
        ),
    )
    # Dedicated user-management table (SQLite): UM_USER
    _user_table = Table(
        'um_user',
        _metadata,
        Column('id', Integer, primary_key=True, autoincrement=True),
        Column('username', String(255), nullable=False, unique=True),
        Column('password_hash', String(255), nullable=True),
        Column('must_change_password', Boolean, nullable=False, server_default='1'),
        Column('webauthn_credential_id', String(1024), nullable=True),
        Column('webauthn_public_key', String(4096), nullable=True),
        Column('webauthn_sign_count', Integer, nullable=True),
        Column('created_at', DateTime, server_default=func.current_timestamp()),
        Column(
            'updated_at',
            DateTime,
            server_default=func.current_timestamp(),
            onupdate=func.current_timestamp(),
        ),
    )


def get_blocked_table() -> Table:
    _ensure_loaded()
    if _blocked_table is None:
        raise BlockedTableNotInitializedError
    return _blocked_table


def get_props_table() -> Table:
    _ensure_loaded()
    if _props_table is None:
        raise PropsTableNotInitializedError
    return _props_table


def get_admins_table() -> Table:
    _ensure_loaded()
    if _admins_table is None:
        raise AdminsTableNotInitializedError
    return _admins_table


def get_user_table() -> Table:
    _ensure_loaded()
    if _user_table is None:
        raise UserTableNotInitializedError
    return _user_table


# Public helper to access MetaData


def get_metadata():
    _ensure_loaded()
    if _metadata is None:
        raise MetadataNotInitializedError
    return _metadata


__all__ = [
    'get_admins_table',
    'get_blocked_table',
    'get_metadata',
    'get_props_table',
    'get_user_table',
]
