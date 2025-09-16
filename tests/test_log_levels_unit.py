from __future__ import annotations

import pytest


@pytest.mark.unit
def test_set_level_delegates(monkeypatch):
    calls: list[tuple[object, ...]] = []

    def fake_set(level):  # type: ignore[no-redef]
        calls.append((level,))

    # Patch the underlying logging_setup function
    import postfix_blocker.logging_setup as logging_setup

    monkeypatch.setattr(logging_setup, 'set_logger_level', fake_set, raising=True)

    from postfix_blocker.services.log_levels import set_level

    set_level('DEBUG')
    set_level(10)

    assert calls == [('DEBUG',), (10,)]
