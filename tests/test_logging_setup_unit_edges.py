from __future__ import annotations

import logging

import pytest

from postfix_blocker.logging_setup import configure_logging, set_logger_level


class _BadHandler(logging.Handler):
    def setLevel(self, level):  # type: ignore[override]
        raise RuntimeError('cannot set level')

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - not used
        pass


@pytest.mark.unit
def test_configure_logging_handler_setlevel_failure_is_caught(monkeypatch):
    # Ensure no file logging attempt to keep it isolated
    monkeypatch.delenv('X_FILE', raising=False)
    monkeypatch.setenv('X_LEVEL', 'INFO')

    root = logging.getLogger()
    # Insert a bad handler that raises when setLevel is called
    bad = _BadHandler()
    root.addHandler(bad)
    try:
        configure_logging(service='api', level_env='X_LEVEL', file_env='X_FILE', default='INFO')
        # Reaching here without exception means except path executed and swallowed
        assert True
    finally:
        try:
            root.removeHandler(bad)
        except Exception:
            pass


@pytest.mark.unit
def test_set_logger_level_handler_setlevel_failure_is_caught():
    root = logging.getLogger()
    bad = _BadHandler()
    root.addHandler(bad)
    try:
        set_logger_level('DEBUG')
        assert root.level == logging.DEBUG
    finally:
        try:
            root.removeHandler(bad)
        except Exception:
            pass
