# ruff: noqa: E402
from __future__ import annotations

"""Engine factory (refactor implementation).

Provides a stable import path postfix_blocker.db.engine.get_engine and
removes the dependency on postfix_blocker.blocker.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    # Default to DB2 connection URL.
    db_url = os.environ.get('BLOCKER_DB_URL', 'ibm_db_sa://db2inst1:blockerpass@db2:50000/BLOCKER')
    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_use_lifo=True,
        pool_size=20,
        max_overflow=0,
        pool_recycle=3600,
    )


__all__ = ['get_engine']
