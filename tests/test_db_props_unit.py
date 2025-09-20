from __future__ import annotations

import pytest

try:
    from sqlalchemy import create_engine
except Exception:  # pragma: no cover - SQLAlchemy not installed in some envs
    create_engine = None  # type: ignore

from postfix_blocker.db.migrations import init_db
from postfix_blocker.db.props import get_prop, set_prop


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
