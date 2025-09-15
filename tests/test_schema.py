import pytest


@pytest.mark.unit
def test_blocked_table_schema():
    pytest.importorskip('sqlalchemy')
    from postfix_blocker import blocker

    # Should not raise
    tbl = blocker.get_blocked_table()
    assert tbl.name == 'blocked_addresses'
    cols = set(c.name for c in tbl.columns)
    assert {'id', 'pattern', 'is_regex', 'updated_at'}.issubset(cols)
