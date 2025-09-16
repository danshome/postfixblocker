from __future__ import annotations

"""Unified log level utilities for services.

This thin wrapper centralizes how we apply dynamic log-level changes at runtime
for both the API and the blocker. It delegates to logging_setup.set_logger_level
so any future adjustments (e.g., handler policies) are kept in one place.
"""

from ..logging_setup import set_logger_level as _set_logger_level  # noqa: E402


def set_level(level: str | int) -> None:
    """Set process-wide log level.

    Accepts either a logging level name (e.g., "DEBUG") or an int level.
    """
    _set_logger_level(level)


__all__ = ['set_level']
