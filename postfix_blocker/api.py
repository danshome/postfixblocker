"""Thin API entrypoint and legacy helpers for tests.

- Exposes `app` created by the Flask app factory.
- Provides `_tail_file` and `_coerce_level` expected by existing unit tests.

Do not add routes here; routes live under `postfix_blocker/web/routes_*.py`.
"""

from __future__ import annotations

import logging
from typing import Any

from .services.log_tail import tail_file as _tail_file_impl
from .web.app_factory import create_app

# Flask application (used by gunicorn, unit tests, and e2e)
app = create_app()


# ---- Legacy test helpers ----------------------------------------------------


def _tail_file(path: str, lines: int) -> str:
    """Backward-compatible wrapper used by unit tests.

    Delegates to services.log_tail.tail_file.
    """
    return _tail_file_impl(path, lines)


def _coerce_level(level: Any) -> int:
    """Coerce a level string/int to a logging level int.

    Behaviour matches historical helper used by tests:
    - numeric strings return that integer
    - names like "DEBUG"/"info" map via logging module
    - unknown names default to logging.INFO (still an int)
    """
    try:
        return int(level)  # type: ignore[arg-type]
    except Exception as exc:
        logging.getLogger(__name__).debug('Non-integer log level %r: %s', level, exc)
    s = str(level).strip().upper()
    return getattr(logging, s, logging.INFO)


__all__ = ['app', '_tail_file', '_coerce_level']


if __name__ == '__main__':  # pragma: no cover - dev/supervisor entrypoint
    import os

    host = os.environ.get('API_HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '5000'))
    app.run(host=host, port=port)
