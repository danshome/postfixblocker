"""Postfix Blocker Python package.

- Exposes runtime submodules via `postfix_blocker.*`.
- Provides `__version__` for packaging/diagnostics.

Usage examples:
    from postfix_blocker import __version__
    from postfix_blocker import blocker, api
"""

from __future__ import annotations

import importlib as _importlib
from typing import Any as _Any
from typing import Callable as _Callable

# Package version (pep 621 / importlib.metadata)
try:  # Python 3.8+ stdlib metadata
    from importlib.metadata import version as _real_ver

    _ver: _Callable[[str], str] = _real_ver
except Exception:  # pragma: no cover - very old Pythons only

    def _ver(_: str) -> str:
        return '0.0.0'


try:
    __version__ = _ver('postfix-blocker')
except Exception:  # fallback for editable/dev without installed metadata
    __version__ = '0.0.0'

__all__ = ['__version__', 'blocker', 'api']


def __getattr__(name: str) -> _Any:  # PEP 562 lazy import of submodules
    if name in ('api', 'blocker'):
        return _importlib.import_module(f'.{name}', __name__)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
