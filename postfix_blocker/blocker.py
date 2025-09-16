"""Thin blocker service runner.

This module is retained only as an executable entrypoint
(`python -m postfix_blocker.blocker`). All legacy re-exports have been removed.
"""

from __future__ import annotations

import warnings

from .config import load_config
from .logging_setup import configure_logging
from .services.blocker_service import run_forever as _run_forever

# Notify callers that direct imports are deprecated and now unsupported
warnings.warn(
    'postfix_blocker.blocker is a thin runner only; import refactored modules '
    'from postfix_blocker.* (db.*, postfix.*, services.*). Legacy re-exports '
    'have been removed.',
    category=DeprecationWarning,
    stacklevel=2,
)


def main() -> None:  # pragma: no cover - service runner
    configure_logging(
        service='blocker',
        level_env='BLOCKER_LOG_LEVEL',
        file_env='BLOCKER_LOG_FILE',
        default='INFO',
    )
    cfg = load_config()
    _run_forever(cfg)


if __name__ == '__main__':  # pragma: no cover
    main()
