from __future__ import annotations

import pytest

from postfix_blocker.models.entries import BlockEntry, entry_to_dict, row_to_entry


class Obj:
    def __init__(self, pattern: str, is_regex: bool, test_mode: bool = True, id: int | None = None):
        self.pattern = pattern
        self.is_regex = is_regex
        self.test_mode = test_mode
        if id is not None:
            self.id = id


@pytest.mark.unit
def test_row_to_entry_from_attrs_and_tuple():
    o = Obj('x@example.com', False, True)
    e1 = row_to_entry(o)
    assert isinstance(e1, BlockEntry)
    assert e1.pattern == 'x@example.com' and e1.is_regex is False and e1.test_mode is True

    t = ('y@example.com', 1, 0)
    e2 = row_to_entry(t)
    assert e2.pattern == 'y@example.com' and e2.is_regex is True and e2.test_mode is False


@pytest.mark.unit
def test_entry_to_dict_includes_optional_id():
    o = Obj('z@example.com', True, False, id=123)
    d = entry_to_dict(o)
    assert d['pattern'] == 'z@example.com' and d['is_regex'] is True and d['test_mode'] is False
    assert d['id'] == 123

    # Fallback without id
    e = BlockEntry('a@b', False, True)
    d2 = entry_to_dict(e)
    assert 'id' not in d2
