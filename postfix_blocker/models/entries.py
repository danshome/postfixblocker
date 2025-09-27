from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BlockEntry:
    pattern: str
    is_regex: bool
    test_mode: bool = False


def row_to_entry(row: Any) -> BlockEntry:
    # Row may be a tuple-like or have attributes
    try:
        # SQLAlchemy row with attributes
        pattern = row.pattern if hasattr(row, 'pattern') else row[0]
        is_regex = row.is_regex if hasattr(row, 'is_regex') else row[1]
        tm = (
            getattr(row, 'test_mode', True)
            if hasattr(row, 'test_mode')
            else (row[2] if len(row) > 2 else True)
        )
    except Exception:
        # Fallback defaults
        pattern, is_regex, tm = '', False, True
    return BlockEntry(pattern=str(pattern), is_regex=bool(is_regex), test_mode=bool(tm))


def entry_to_dict(obj: Any) -> dict[str, Any]:
    # Accept either a BlockEntry or an ORM row-like with attributes
    pattern = getattr(obj, 'pattern', None)
    is_regex = getattr(obj, 'is_regex', None)
    test_mode = getattr(obj, 'test_mode', True)
    id_ = getattr(obj, 'id', None)
    d = {
        'pattern': pattern,
        'is_regex': bool(is_regex),
        'test_mode': bool(test_mode),
    }
    if id_ is not None:
        d['id'] = id_
    return d


__all__ = ['BlockEntry', 'entry_to_dict', 'row_to_entry']
