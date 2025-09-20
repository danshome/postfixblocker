# ruff: noqa: E402
from __future__ import annotations

"""SQLAlchemy schema definitions (refactor implementation).

Defines metadata and tables for blocked addresses and properties.
"""
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


def _ensure_loaded() -> None:
    global _metadata, _blocked_table, _props_table
    if _metadata is not None and _blocked_table is not None and _props_table is not None:
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
        Column('key', String(1024), primary_key=True),
        Column('value', String(1024)),
        Column(
            'update_ts',
            DateTime,
        ),
    )


def get_blocked_table() -> Table:
    _ensure_loaded()
    if _blocked_table is None:
        raise RuntimeError('blocked_addresses table not initialized')
    return _blocked_table


def get_props_table() -> Table:
    _ensure_loaded()
    if _props_table is None:
        raise RuntimeError('cris_props table not initialized')
    return _props_table


# Public helper to access MetaData


def get_metadata():
    _ensure_loaded()
    if _metadata is None:
        raise RuntimeError('metadata not initialized')
    return _metadata


__all__ = ['get_metadata', 'get_blocked_table', 'get_props_table']
