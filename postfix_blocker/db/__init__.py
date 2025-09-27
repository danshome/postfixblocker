"""Database access helpers for Postfix Blocker (refactor shim).

This package provides stable import locations for DB-related utilities while
preserving backward compatibility with existing code that imports directly
from postfix_blocker.blocker.
"""

from __future__ import annotations

# Export real implementations from refactored modules (no legacy blocker deps)
from .engine import get_engine
from .migrations import init_db
from .props import get_prop, set_prop
from .schema import get_blocked_table, get_props_table

__all__ = [
    'get_blocked_table',
    'get_engine',
    'get_prop',
    'get_props_table',
    'init_db',
    'set_prop',
]
