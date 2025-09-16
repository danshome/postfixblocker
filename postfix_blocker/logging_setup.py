from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


def configure_logging(
    service: str, level_env: str, file_env: str | None = None, default: str | int = 'INFO'
) -> None:
    raw = (os.environ.get(level_env) or str(default)).strip()
    try:
        level = int(raw)
    except Exception:
        level = getattr(logging, raw.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        try:
            h.setLevel(level)
        except Exception:
            logging.debug('Could not set handler level', exc_info=True)
    path = os.environ.get(file_env) if file_env else None
    if path:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fh = RotatingFileHandler(path, maxBytes=10 * 1024 * 1024, backupCount=5)
            fh.setLevel(level)
            fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s %(message)s'))
            if not any(
                isinstance(h, RotatingFileHandler)
                and getattr(h, 'baseFilename', '') == fh.baseFilename
                for h in root.handlers
            ):
                root.addHandler(fh)
        except Exception:
            logging.warning('Could not set up file logging at %s', path, exc_info=True)
    logging.info(
        '%s logging initialized (level=%s file=%s)',
        service,
        logging.getLevelName(level),
        path or 'none',
    )


def set_logger_level(level_s: str | int) -> None:
    try:
        level = int(level_s)  # type: ignore[arg-type]
    except Exception:
        level = getattr(logging, str(level_s).upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        try:
            h.setLevel(level)
        except Exception:
            logging.debug('Failed to set handler level', exc_info=True)
    root.info('Log level changed via props to %s', level_s)


__all__ = ['configure_logging', 'set_logger_level']
