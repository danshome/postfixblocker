"""Compatibility package for the Postfix Blocker application.

Allows importing the application modules via `postfix_blocker` while keeping
the on-disk package named `app` for runtime paths. This avoids breaking
existing container paths while presenting a clearer import name to callers.

Usage:
    from postfix_blocker import blocker, api
"""

import importlib as _importlib
from typing import Any as _Any

__all__ = ['blocker', 'api']


def __getattr__(name: str) -> _Any:  # PEP 562 lazy import of submodules
    if name in ('api', 'blocker'):
        return _importlib.import_module(f'.{name}', __name__)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
