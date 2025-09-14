"""Optional backend smoke tests for Postgres and DB2.

These tests are skipped unless the corresponding environment variables are set
and SQLAlchemy + the appropriate driver are installed.

Set one or both of the following to enable:
- TEST_PG_URL  (e.g. postgresql://blocker:blocker@localhost:5433/blocker)
- TEST_DB2_URL (e.g. ibm_db_sa://db2inst1:password@localhost:50000/BLOCKER or db2+ibm_db://db2inst1:password@localhost:50000/BLOCKER)
"""
import os
import pytest

try:  # pragma: no cover - optional integration
    from sqlalchemy import create_engine
    from sqlalchemy.exc import OperationalError
except Exception:  # pragma: no cover - SQLAlchemy not installed
    create_engine = None  # type: ignore
    OperationalError = Exception  # type: ignore

from app import blocker
from tests.utils_wait import wait_for_db_url


def _default_urls():
    return {
        "pg": os.environ.get(
            "TEST_PG_URL", "postgresql://blocker:blocker@localhost:5433/blocker"
        ),
        "db2": os.environ.get(
            "TEST_DB2_URL", "ibm_db_sa://db2inst1:blockerpass@localhost:50000/BLOCKER"
        ),
    }


def _smoke_db(url: str) -> None:
    engine = create_engine(url)  # type: ignore[misc]
    blocker.init_db(engine)
    bt = blocker.get_blocked_table()
    with engine.connect() as conn:
        # Clean slate
        conn.execute(bt.delete())
        # Insert two rows
        conn.execute(bt.insert(), [
            {"pattern": "unit1@example.com", "is_regex": False},
            {"pattern": ".*@unit.test", "is_regex": True},
        ])
        conn.commit()

    # Read back via API function
    entries = blocker.fetch_entries(engine)
    pats = sorted((e.pattern, e.is_regex) for e in entries)
    assert pats == [(".*@unit.test", True), ("unit1@example.com", False)]


@pytest.mark.backend
@pytest.mark.skipif(create_engine is None, reason="SQLAlchemy not installed")
@pytest.mark.parametrize("backend", ["pg", "db2"])
def test_backends_smoke(backend: str):
    urls = _default_urls()
    url = urls[backend]
    # Try quick connectivity; skip if unavailable to avoid hard failures when
    # docker services are not running in the environment.
    if not wait_for_db_url(url):
        pytest.skip(f"{backend} backend not available at {url}")
    _smoke_db(url)
