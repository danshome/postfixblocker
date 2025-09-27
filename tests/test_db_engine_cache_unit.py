from __future__ import annotations

from pathlib import Path

import pytest

from postfix_blocker.db.engine import get_user_engine


@pytest.mark.unit
def test_get_user_engine_uses_absolute_um_db_path_and_caches(monkeypatch, tmp_path: Path) -> None:
    # Ensure no pytest per-test key so module-level cache is used
    monkeypatch.delenv('PYTEST_CURRENT_TEST', raising=False)

    # Point UM_DB_PATH at an absolute file path to exercise the branch that
    # converts raw paths into sqlite URLs (coverage for lines 68–71 in engine.py)
    abs_db = tmp_path / 'um_abs.db'
    monkeypatch.setenv('UM_DB_PATH', str(abs_db))

    # First call should create an engine and initialize the UM_USER table.
    eng1 = get_user_engine()
    assert eng1 is not None

    # Second call should hit the early return from the module-level cache
    # (coverage for line 59 in engine.py)
    eng2 = get_user_engine()
    assert eng2 is eng1

    # Sanity: clear env var for other tests
    monkeypatch.delenv('UM_DB_PATH', raising=False)
