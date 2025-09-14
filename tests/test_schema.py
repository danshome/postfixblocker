import pytest


@pytest.mark.unit
def test_blocked_table_schema():
    sa = pytest.importorskip("sqlalchemy")
    from app import blocker

    # Should not raise
    tbl = blocker.get_blocked_table()
    assert tbl.name == "blocked_addresses"
    cols = set(c.name for c in tbl.columns)
    assert {"id", "pattern", "is_regex", "updated_at"}.issubset(cols)

