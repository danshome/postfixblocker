from __future__ import annotations

"""Unified log level utilities for services.

This thin wrapper centralizes how we apply dynamic log-level changes at runtime
for both the API and the blocker. It delegates to logging_setup.set_logger_level
so any future adjustments (e.g., handler policies) are kept in one place.
"""

# NOTE: Avoid binding set_logger_level at import time so tests can monkeypatch
# postfix_blocker.logging_setup.set_logger_level reliably, even if this module
# was imported earlier in the test session (e.g., under mutmut "clean tests").
# We import the module at call time and dereference the attribute then.


def set_level(level: str | int) -> None:
    """Set process-wide log level.

    Accepts either a logging level name (e.g., "DEBUG") or an int level.
    """
    from .. import logging_setup as _logging_setup  # local import for late binding

    _logging_setup.set_logger_level(level)


__all__ = ['set_level']
