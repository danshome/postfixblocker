from __future__ import annotations

import pytest

from postfix_blocker.postfix.log_level import map_ui_to_debug_peer_level


@pytest.mark.unit
@pytest.mark.parametrize(
    'inp,expected_min,expected_max',
    [
        ('DEBUG', 4, 4),
        ('INFO', 3, 3),
        ('warning', 1, 1),
        ('2', 2, 2),
        ('7', 4, 4),  # capped at 4
        ('0', 1, 1),  # min 1
        ('', 1, 1),
        ('not-a-level', 1, 1),
    ],
)
def test_map_ui_to_debug_peer_level(inp: str, expected_min: int, expected_max: int):
    n = map_ui_to_debug_peer_level(inp)
    assert expected_min <= n <= expected_max
