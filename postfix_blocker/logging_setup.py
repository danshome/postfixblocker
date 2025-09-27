from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


def _set_handler_level_safely(handler: logging.Handler, level: int) -> None:
    try:
        handler.setLevel(level)
    except Exception:
        logging.debug('Could not set handler level', exc_info=True)


def configure_logging(
    service: str,
    level_env: str,
    file_env: str | None = None,
    default: str | int = 'INFO',
) -> None:
    raw = (os.environ.get(level_env) or str(default)).strip()
    try:
        level = int(raw)
    except Exception:
        level = getattr(logging, raw.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        _set_handler_level_safely(h, level)
    path_s = os.environ.get(file_env) if file_env else None
    if path_s:
        try:
            from pathlib import Path

            p = Path(path_s)
            p.parent.mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(str(p), maxBytes=10 * 1024 * 1024, backupCount=5)
            fh.setLevel(level)
            fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s %(message)s'))
            if not any(
                isinstance(h, RotatingFileHandler)
                and getattr(h, 'baseFilename', '') == fh.baseFilename
                for h in root.handlers
            ):
                root.addHandler(fh)
        except Exception:
            logging.warning('Could not set up file logging at %s', path_s, exc_info=True)
    logging.info(
        '%s logging initialized (level=%s file=%s)',
        service,
        logging.getLevelName(level),
        path_s or 'none',
    )


def set_logger_level(level_s: str | int) -> None:
    try:
        level = int(level_s)  # type: ignore[arg-type]
    except Exception:
        level = getattr(logging, str(level_s).upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        _set_handler_level_safely(h, level)
    root.info('Log level changed via props to %s', level_s)


__all__ = ['configure_logging', 'set_logger_level']
