from __future__ import annotations

from pathlib import Path

import pytest

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine
except Exception:  # pragma: no cover - SQLAlchemy not installed in some envs
    create_engine = None  # type: ignore
    Engine = object  # type: ignore

from postfix_blocker.db.migrations import init_db


@pytest.mark.unit
def test_init_db_sqlite_creates_tables_and_migrates_test_mode(tmp_path: Path) -> None:
    if create_engine is None:
        pytest.fail('SQLAlchemy not installed; migrations unit tests require it.')
    db_path = tmp_path / 'test_migrations.sqlite'
    # Use an on-disk DB so ALTER TABLE changes persist across connections
    engine: Engine = create_engine(f'sqlite:///{db_path}')  # type: ignore[misc]

    # Start with a legacy blocked_addresses table missing test_mode to exercise migration path
    with engine.begin() as conn:
        # Drop if present from a previous run
        try:
            conn.execute(text('DROP TABLE IF EXISTS blocked_addresses'))
        except Exception:
            pass
        try:
            conn.execute(text('DROP TABLE IF EXISTS cris_props'))
        except Exception:
            pass
        # Legacy shape
        conn.execute(
            text(
                """
                CREATE TABLE blocked_addresses (
                    id INTEGER PRIMARY KEY,
                    pattern VARCHAR(255) NOT NULL,
                    is_regex BOOLEAN NOT NULL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    # Run migrations: should create cris_props and add test_mode to blocked_addresses
    init_db(engine)
    # Run again to exercise idempotent create/exists paths
    init_db(engine)

    # Verify tables/columns via PRAGMA
    with engine.connect() as conn:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info('blocked_addresses')"))}
        assert {'id', 'pattern', 'is_regex', 'test_mode', 'updated_at'}.issubset(cols)

        # Ensure default works for inserts that don't specify test_mode
        conn.execute(
            text('INSERT INTO blocked_addresses (pattern, is_regex) VALUES (:p, :r)'),
            {'p': 'x@example.com', 'r': 0},
        )
        conn.commit()
        # Read back
        row = conn.execute(text('SELECT pattern, is_regex, test_mode FROM blocked_addresses'))
        first = row.first()
        assert first is not None
        # sqlite can store booleans as 0/1
        assert first[0] == 'x@example.com'
        assert int(first[1]) in (0, 1)
        assert int(first[2]) in (0, 1)

    # Clean up
    try:
        engine.dispose()
    except Exception:
        pass
