"""Database access helpers for Postfix Blocker (refactor shim).

This package provides stable import locations for DB-related utilities while
preserving backward compatibility with existing code that imports directly
from postfix_blocker.blocker.
"""

from __future__ import annotations

# Export real implementations from refactored modules (no legacy blocker deps)
from .engine import get_engine  # noqa: F401
from .migrations import init_db  # noqa: F401
from .props import get_prop, set_prop  # noqa: F401
from .schema import get_blocked_table, get_props_table  # noqa: F401

__all__ = [
    'get_engine',
    'init_db',
    'get_blocked_table',
    'get_props_table',
    'get_prop',
    'set_prop',
]
