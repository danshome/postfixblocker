# ruff: noqa: E402
from __future__ import annotations

"""Properties access and keys (refactor implementation)."""
import logging
from typing import Any

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


def seed_default_props(engine: Engine) -> None:
    """Seed CRIS props rows when missing to ensure stable defaults."""
    if not DEFAULT_PROP_VALUES:
        return
    pt = get_props_table()
    with engine.begin() as conn:
        for key, default in DEFAULT_PROP_VALUES.items():
            probe_ok = True
            try:
                exists: Any = conn.execute(select(pt.c.key).where(pt.c.key == key)).first()
            except AttributeError:
                try:
                    exists = conn.exec_driver_sql(  # type: ignore[attr-defined]
                        'SELECT 1 FROM cris_props WHERE key = ?',
                        (key,),
                    ).first()
                except Exception as exc:  # pragma: no cover - diagnostic fallback
                    logging.getLogger(__name__).debug('Seed probe failed for %s: %s', key, exc)
                    probe_ok = False
            if not probe_ok:
                continue
            if exists is None:
                try:
                    conn.execute(
                        pt.insert().values(
                            key=key, value=default, update_ts=func.current_timestamp()
                        )
                    )
                except AttributeError:
                    try:
                        conn.exec_driver_sql(  # type: ignore[attr-defined]
                            'INSERT INTO cris_props (key, value, update_ts) VALUES (?, ?, CURRENT_TIMESTAMP)',
                            (key, default),
                        )
                    except Exception:
                        conn.exec_driver_sql(  # type: ignore[attr-defined]
                            'INSERT INTO cris_props (key, value) VALUES (?, ?)',
                            (key, default),
                        )


__all__ = ['LOG_KEYS', 'REFRESH_KEYS', 'LINES_KEYS', 'get_prop', 'set_prop', 'seed_default_props']
