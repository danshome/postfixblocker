# ruff: noqa: E402
from __future__ import annotations

"""Properties access and keys (refactor implementation)."""
import logging
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from .schema import get_props_table

# Keys as used by the API/UI
_PREFIX = 'postfix-blocker.'
LOG_KEYS = {
    'api': f'{_PREFIX}log.level.api',
    'blocker': f'{_PREFIX}log.level.blocker',
    'postfix': f'{_PREFIX}log.level.postfix',
}
REFRESH_KEYS = {
    'api': f'{_PREFIX}log.refresh.api',
    'blocker': f'{_PREFIX}log.refresh.blocker',
    'postfix': f'{_PREFIX}log.refresh.postfix',
}
LINES_KEYS = {
    'api': f'{_PREFIX}log.lines.api',
    'blocker': f'{_PREFIX}log.lines.blocker',
    'postfix': f'{_PREFIX}log.lines.postfix',
}

_LOGGER = logging.getLogger(__name__)


DEFAULT_PROP_VALUES: dict[str, str | None] = {
    LOG_KEYS['api']: 'INFO',
    LOG_KEYS['blocker']: 'INFO',
    LOG_KEYS['postfix']: 'INFO',
    REFRESH_KEYS['api']: '5000',
    REFRESH_KEYS['blocker']: '5000',
    REFRESH_KEYS['postfix']: '5000',
    LINES_KEYS['api']: '100',
    LINES_KEYS['blocker']: '100',
    LINES_KEYS['postfix']: '100',
}


def get_prop(engine: Engine, key: str, default: str | None = None) -> str | None:
    pt = get_props_table()
    try:
        with engine.connect() as conn:
            res = conn.execute(select(pt.c.value).where(pt.c.key == key)).scalar()
            return res if res is not None else default
    except Exception:
        return default


def set_prop(engine: Engine, key: str, value: str | None) -> None:
    pt = get_props_table()
    with engine.begin() as conn:
        # Always bump UPDATE_TS explicitly to support schemas without DB defaults/triggers
        rc = (
            conn.execute(
                pt.update()
                .where(pt.c.key == key)
                .values(value=value, update_ts=func.current_timestamp())
            ).rowcount
            or 0
        )
        if rc == 0:
            try:
                conn.execute(
                    pt.insert().values(key=key, value=value, update_ts=func.current_timestamp())
                )
            except Exception:
                conn.execute(
                    pt.update()
                    .where(pt.c.key == key)
                    .values(value=value, update_ts=func.current_timestamp())
                )


def _is_duplicate_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(token in msg for token in ('duplicate', 'unique', 'sql0803', 'constraint'))


def _run_insert_attempts(conn, runners: list[tuple[str, Callable[[], Any]]], key: str) -> bool:
    for label, action in runners:
        try:
            action()
            return True
        except Exception as exc:  # pragma: no cover - driver/dialect variety
            if _is_duplicate_error(exc):
                return True
            _LOGGER.debug('Seed insert %s failed for %s: %s', label, key, exc)
    return False


def seed_default_props(engine: Engine) -> None:
    """Seed CRIS props rows when missing to ensure stable defaults."""
    if not DEFAULT_PROP_VALUES:
        return
    pt = get_props_table()
    with engine.begin() as conn:
        for key, default in DEFAULT_PROP_VALUES.items():
            exists = None
            try:
                exists = conn.execute(select(pt.c.key).where(pt.c.key == key)).first()
            except AttributeError:
                try:
                    exists = conn.exec_driver_sql(  # type: ignore[attr-defined]
                        'SELECT 1 FROM cris_props WHERE key = ?',
                        (key,),
                    ).first()
                except Exception as exc:  # pragma: no cover - diagnostic fallback
                    _LOGGER.debug('Seed probe fallback failed for %s: %s', key, exc)
            except Exception as exc:  # pragma: no cover - driver/dialect variety
                _LOGGER.debug('Seed probe failed for %s: %s', key, exc)

            if exists is not None:
                continue

            def _make_sqlalchemy_insert(key_val: str, default_val: str | None) -> Callable[[], Any]:
                def _inner() -> Any:
                    return conn.execute(
                        pt.insert().values(
                            key=key_val,
                            value=default_val,
                            update_ts=func.current_timestamp(),
                        )
                    )

                return _inner

            def _make_driver_ts_insert(key_val: str, default_val: str | None) -> Callable[[], Any]:
                def _inner() -> Any:
                    return conn.exec_driver_sql(  # type: ignore[attr-defined]
                        'INSERT INTO cris_props (key, value, update_ts) '
                        'VALUES (?, ?, CURRENT_TIMESTAMP)',
                        (key_val, default_val),
                    )

                return _inner

            def _make_driver_insert(key_val: str, default_val: str | None) -> Callable[[], Any]:
                def _inner() -> Any:
                    return conn.exec_driver_sql(  # type: ignore[attr-defined]
                        'INSERT INTO cris_props (key, value) VALUES (?, ?)',
                        (key_val, default_val),
                    )

                return _inner

            insert_attempts = [
                ('sqlalchemy', _make_sqlalchemy_insert(key, default)),
                ('driver ts', _make_driver_ts_insert(key, default)),
                ('driver', _make_driver_insert(key, default)),
            ]

            if not _run_insert_attempts(
                conn, insert_attempts, key
            ):  # pragma: no cover - diagnostic only
                _LOGGER.debug('Seed insert attempts exhausted for %s', key)


__all__ = ['LOG_KEYS', 'REFRESH_KEYS', 'LINES_KEYS', 'get_prop', 'set_prop', 'seed_default_props']
