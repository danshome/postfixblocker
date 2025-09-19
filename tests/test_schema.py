import pytest


@pytest.mark.unit
def test_blocked_table_schema():
    pytest.importorskip('sqlalchemy')
    from postfix_blocker.db.schema import get_blocked_table, get_props_table

    # Should not raise
    tbl = get_blocked_table()
    assert tbl.name == 'blocked_addresses'
    cols = set(c.name for c in tbl.columns)
    assert {'id', 'pattern', 'is_regex', 'updated_at'}.issubset(cols)

    # Properties table
    pt = get_props_table()
    assert pt.name.lower() == 'cris_props'
    pcols = set(c.name.lower() for c in pt.columns)
    assert {'key', 'value', 'update_ts'}.issubset(pcols)
