# ruff: noqa: E402
from __future__ import annotations

"""Properties access and keys (refactor implementation)."""
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from .schema import get_props_table

# Keys as used by the API/UI
LOG_KEYS = {
    'api': 'log.level.api',
    'blocker': 'log.level.blocker',
    'postfix': 'log.level.postfix',
}
REFRESH_KEYS = {
    'api': 'log.refresh.api',
    'blocker': 'log.refresh.blocker',
    'postfix': 'log.refresh.postfix',
}
LINES_KEYS = {
    'api': 'log.lines.api',
    'blocker': 'log.lines.blocker',
    'postfix': 'log.lines.postfix',
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


__all__ = ['LOG_KEYS', 'REFRESH_KEYS', 'LINES_KEYS', 'get_prop', 'set_prop']
