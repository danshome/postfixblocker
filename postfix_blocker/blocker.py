"""Legacy blocker entrypoint and back-compat shims.

This module remains import-compatible for tests and external callers while the
actual implementation lives in focused modules under `postfix_blocker/`.

Exports:
- POSTFIX_DIR: default Postfix directory path (overridable in tests)
- BlockEntry: dataclass for entries
- write_map_files: Postfix map writer
- reload_postfix: Postfix control helper
- get_blocked_table, init_db: DB helpers
- fetch_entries(engine): convenience wrapper used by tests

Running as a script starts the blocker service loop.
"""

from __future__ import annotations

import os
import warnings
from typing import Any

from .config import load_config
from .db.migrations import init_db
from .db.schema import get_blocked_table, get_props_table
from .logging_setup import configure_logging
from .models.entries import BlockEntry
from .postfix import reload_postfix  # re-export
from .postfix.maps import write_map_files as _write_map_files
from .services.blocker_service import run_forever as _run_forever

# Deprecation notice for direct imports
warnings.warn(
    'postfix_blocker.blocker is a legacy shim; use services.blocker_service and other\n'
    'refactored modules under postfix_blocker/. This shim will be removed in a\n'
    'future release.',
    category=DeprecationWarning,
    stacklevel=2,
)

# Back-compat variable used by tests
POSTFIX_DIR = os.environ.get('POSTFIX_DIR', '/etc/postfix')


def fetch_entries(engine: Any) -> list[BlockEntry]:
    """Return BlockEntry list from the blocked_addresses table.

    Thin wrapper to keep the historical import surface for tests.
    """
    # Use the internal helper from the service to avoid duplication
    try:
        from .services.blocker_service import _fetch_entries as _impl
    except Exception:  # pragma: no cover - import safety
        # Local minimal fallback to avoid hard failure if import graph changes
        from sqlalchemy import select  # type: ignore

        bt = get_blocked_table()
        with engine.connect() as conn:  # type: ignore[attr-defined]
            rows = list(conn.execute(select(bt.c.pattern, bt.c.is_regex, bt.c.test_mode)))
        return [BlockEntry(pattern=r[0], is_regex=r[1], test_mode=bool(r[2])) for r in rows]
    return _impl(engine)  # type: ignore[misc]


def write_map_files(entries):
    """Back-compat wrapper that honors blocker.POSTFIX_DIR override in tests."""
    return _write_map_files(entries, POSTFIX_DIR)


# Re-export selected helpers for back-compat
__all__ = [
    'POSTFIX_DIR',
    'BlockEntry',
    'write_map_files',
    'reload_postfix',
    'get_blocked_table',
    'get_props_table',
    'init_db',
    'fetch_entries',
]


def main() -> None:  # pragma: no cover - service runner
    # Ensure blocker logs are written to file and honor dynamic level
    configure_logging(
        service='blocker',
        level_env='BLOCKER_LOG_LEVEL',
        file_env='BLOCKER_LOG_FILE',
        default='INFO',
    )
    cfg = load_config()
    _run_forever(cfg)


if __name__ == '__main__':  # pragma: no cover - service runner
    main()
