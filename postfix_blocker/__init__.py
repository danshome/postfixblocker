"""Compatibility package for the Postfix Blocker application.

Allows importing the application modules via `postfix_blocker` while keeping
the on-disk package named `app` for runtime paths. This avoids breaking
existing container paths while presenting a clearer import name to callers.

Usage:
    from postfix_blocker import blocker, api
"""

from . import blocker  # noqa: F401
from . import api  # noqa: F401

__all__ = ["blocker", "api"]
