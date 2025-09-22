from __future__ import annotations

import pytest

try:
    from sqlalchemy import create_engine, text
except Exception:  # pragma: no cover - SQLAlchemy not installed in some envs
    create_engine = None  # type: ignore
    text = None  # type: ignore

from postfix_blocker.db.migrations import init_db
from postfix_blocker.db.props import LINES_KEYS, LOG_KEYS, REFRESH_KEYS, get_prop, set_prop


@pytest.mark.unit
def test_props_insert_update_and_get_default():
    if create_engine is None:
        pytest.fail('SQLAlchemy not installed; unit DB props tests require it.')
    engine = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(engine)

    # Default when not present
    assert get_prop(engine, 'missing', default='x') == 'x'

    # Insert via set_prop
    set_prop(engine, 'k1', 'v1')
    assert get_prop(engine, 'k1') == 'v1'

    # Update existing
    set_prop(engine, 'k1', 'v2')
    assert get_prop(engine, 'k1') == 'v2'


@pytest.mark.unit
def test_init_db_seeds_default_props():
    if create_engine is None or text is None:
        pytest.fail('SQLAlchemy not installed; unit DB props tests require it.')
    engine = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(engine)

    expected_keys = set(LOG_KEYS.values()) | set(REFRESH_KEYS.values()) | set(LINES_KEYS.values())
    with engine.connect() as conn:
        rows = conn.execute(text('SELECT key, value FROM cris_props')).fetchall()

    assert len(rows) == len(expected_keys)
    values = {row[0]: row[1] for row in rows}
    assert set(values) == expected_keys

    assert values[LOG_KEYS['api']] == 'INFO'
    assert values[LOG_KEYS['blocker']] == 'INFO'
    assert values[LOG_KEYS['postfix']] == 'INFO'
    assert values[REFRESH_KEYS['api']] == '5000'
    assert values[REFRESH_KEYS['blocker']] == '5000'
    assert values[REFRESH_KEYS['postfix']] == '5000'
    assert values[LINES_KEYS['api']] == '100'
    assert values[LINES_KEYS['blocker']] == '100'
    assert values[LINES_KEYS['postfix']] == '100'

    # Second init_db run should not duplicate rows
    init_db(engine)
    with engine.connect() as conn:
        rows_after = conn.execute(text('SELECT key, value FROM cris_props')).fetchall()
    assert len(rows_after) == len(expected_keys)
