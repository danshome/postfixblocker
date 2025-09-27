"""Backend smoke test for DB2 only.

Requires SQLAlchemy and DB2 driver. Configure DB URL via TEST_DB2_URL.
"""

import os
import time

import pytest

try:  # pragma: no cover - optional integration
    from sqlalchemy import create_engine
    from sqlalchemy.exc import OperationalError, ProgrammingError
except Exception:  # pragma: no cover - SQLAlchemy not installed
    create_engine = None  # type: ignore
    OperationalError = Exception  # type: ignore
    ProgrammingError = Exception  # type: ignore

from postfix_blocker.db.migrations import init_db
from postfix_blocker.db.schema import get_blocked_table
from tests.utils_wait import wait_for_db_url


def _db2_url() -> str:
    return os.environ.get(
        'TEST_DB2_URL',
        'ibm_db_sa://db2inst1:blockerpass@localhost:50000/BLOCKER',
    )


def _smoke_db(url: str) -> None:
    engine = create_engine(url)  # type: ignore[misc]
    try:
        init_db(engine)
        bt = get_blocked_table()

        # DB2 can throw SQL0911N on DML under concurrent load; retry a few times.
        last_exc: Exception | None = None
        for attempt in range(1, 8):
            try:
                with engine.connect() as conn:
                    # Clean slate
                    conn.execute(bt.delete())
                    # Insert two rows (avoid executemany to sidestep DB2 rowcount issues)
                    conn.execute(bt.insert().values(pattern='unit1@example.com', is_regex=False))
                    conn.execute(bt.insert().values(pattern='.*@unit.test', is_regex=True))
                    conn.commit()
                last_exc = None
                break
            except (
                OperationalError,
                ProgrammingError,
            ) as exc:  # pragma: no cover - timing dependent
                last_exc = exc
                msg = str(exc)
                if (
                    'SQL0911N' in msg or 'deadlock' in msg.lower() or 'timeout' in msg.lower()
                ) and attempt < 7:
                    time.sleep(1.0)
                    continue
                raise
        if last_exc:
            raise last_exc

        # Read back directly via SQLAlchemy (no legacy shim)
        from sqlalchemy import select  # type: ignore

        # DB2 can experience transient lock timeouts under concurrent writes. Retry a few times.
        last_exc: Exception | None = None
        for attempt in range(1, 8):
            try:
                with engine.connect() as conn:
                    rows = list(conn.execute(select(bt.c.pattern, bt.c.is_regex)))
                pats = sorted((r[0], r[1]) for r in rows)
                assert pats == [('.*@unit.test', True), ('unit1@example.com', False)]
                last_exc = None
                break
            except (
                OperationalError,
                ProgrammingError,
            ) as exc:  # pragma: no cover - timing dependent
                last_exc = exc
                msg = str(exc)
                if (
                    'SQL0911N' in msg or 'deadlock' in msg.lower() or 'timeout' in msg.lower()
                ) and attempt < 7:
                    time.sleep(1.0)
                    continue
                raise
        if last_exc:
            raise last_exc
    finally:
        try:
            engine.dispose()
        except Exception:
            pass


@pytest.mark.backend
@pytest.mark.slow
def test_db2_smoke():
    if create_engine is None:
        pytest.fail('SQLAlchemy not installed; backend tests require it.')
    url = _db2_url()
    # Ensure connectivity; fail if unavailable.
    if not wait_for_db_url(url):
        pytest.fail(
            f'DB2 backend not available at {url}. Backend tests require the database to be available.',
        )
    _smoke_db(url)
