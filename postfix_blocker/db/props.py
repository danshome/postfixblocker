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
                .values(value=value, update_ts=func.current_timestamp()),
            ).rowcount
            or 0
        )
        if rc == 0:
            try:
                conn.execute(
                    pt.insert().values(key=key, value=value, update_ts=func.current_timestamp()),
                )
            except Exception:
                conn.execute(
                    pt.update()
                    .where(pt.c.key == key)
                    .values(value=value, update_ts=func.current_timestamp()),
                )


def _is_duplicate_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(token in msg for token in ('duplicate', 'unique', 'sql0803', 'constraint'))


def _run_insert_attempts(runners: list[tuple[str, Callable[[], Any]]], key: str) -> bool:
    """Run candidate insert strategies until one succeeds.

    Avoids try/except inside the loop body for PERF203 by delegating the
    exception handling to a small helper.
    """

    def _try_one(label: str, action: Callable[[], Any]) -> bool:
        try:
            action()
        except Exception as exc:  # pragma: no cover - driver/dialect variety
            if _is_duplicate_error(exc):
                return True
            _LOGGER.debug('Seed insert %s failed for %s: %s', label, key, exc)
            return False
        else:
            return True

    return any(_try_one(label, action) for label, action in runners)


def _probe_exists(conn, pt, key: str, *, is_db2: bool) -> bool:
    """Check whether a key already exists, using multiple strategies."""
    try:
        return bool(
            conn.execute(select(func.count()).select_from(pt).where(pt.c.key == key)).scalar() or 0,
        )
    except AttributeError:
        try:
            return bool(
                conn.exec_driver_sql(  # type: ignore[attr-defined]
                    'SELECT 1 FROM cris_props WHERE key = ?',
                    (key,),
                ).first(),
            )
        except Exception as exc:  # pragma: no cover - diagnostic fallback
            _LOGGER.warning('Seed probe fallback failed for %s: %s', key, exc)
    except Exception as exc:  # pragma: no cover - driver/dialect variety
        _LOGGER.warning('Seed probe failed for %s: %s', key, exc)

    if is_db2:
        try:
            return bool(
                conn.exec_driver_sql(  # type: ignore[attr-defined]
                    'SELECT 1 FROM CRISOP.CRIS_PROPS WHERE KEY = ?',
                    (key,),
                ).first(),
            )
        except Exception as exc:  # pragma: no cover - db2 catalog differences
            _LOGGER.warning('Seed probe CRISOP fallback failed for %s: %s', key, exc)
    return False


def _build_insert_attempts(
    conn,
    pt,
    key: str,
    default: str | None,
    *,
    is_db2: bool,
) -> list[tuple[str, Callable[[], Any]]]:
    def _make_sqlalchemy_insert(key_val: str, default_val: str | None) -> Callable[[], Any]:
        def _inner() -> Any:
            return conn.execute(
                pt.insert().values(
                    key=key_val,
                    value=default_val,
                    update_ts=func.current_timestamp(),
                ),
            )

        return _inner

    def _make_driver_ts_insert(key_val: str, default_val: str | None) -> Callable[[], Any]:
        def _inner() -> Any:
            return conn.exec_driver_sql(  # type: ignore[attr-defined]
                'INSERT INTO cris_props (key, value, update_ts) VALUES (?, ?, CURRENT_TIMESTAMP)',
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

    def _make_db2_exec(sql: str, params: tuple[Any, ...]) -> Callable[[], Any]:
        def _inner() -> Any:
            return conn.exec_driver_sql(  # type: ignore[attr-defined]
                sql,
                params,
            )

        return _inner

    attempts: list[tuple[str, Callable[[], Any]]] = [
        ('sqlalchemy', _make_sqlalchemy_insert(key, default)),
        ('driver ts', _make_driver_ts_insert(key, default)),
        ('driver', _make_driver_insert(key, default)),
    ]
    if is_db2:
        attempts.extend(
            [
                (
                    'db2 crisop ts',
                    _make_db2_exec(
                        'INSERT INTO CRISOP.CRIS_PROPS (KEY, VALUE, UPDATE_TS) VALUES (?, ?, CURRENT_TIMESTAMP)',
                        (key, default),
                    ),
                ),
                (
                    'db2 crisop',
                    _make_db2_exec(
                        'INSERT INTO CRISOP.CRIS_PROPS (KEY, VALUE) VALUES (?, ?)',
                        (key, default),
                    ),
                ),
            ],
        )
    return attempts


def seed_default_props(engine: Engine) -> None:
    """Seed CRIS props rows when missing to ensure stable defaults."""
    if not DEFAULT_PROP_VALUES:
        return
    pt = get_props_table()
    dialect = (engine.dialect.name or '').lower()
    is_db2 = dialect in ('ibm_db_sa', 'db2')
    inserted: list[str] = []
    with engine.begin() as conn:
        for key, default in DEFAULT_PROP_VALUES.items():
            if _probe_exists(conn, pt, key, is_db2=is_db2):
                continue

            msg = f'Seeding default CRIS prop {key}'
            _LOGGER.info(msg)
            logging.getLogger().info(msg)

            insert_attempts = _build_insert_attempts(conn, pt, key, default, is_db2=is_db2)
            if not _run_insert_attempts(insert_attempts, key):  # pragma: no cover - diagnostic only
                _LOGGER.warning('Seed insert attempts exhausted for %s', key)
                logging.getLogger().warning('Seed insert attempts exhausted for %s', key)
            else:
                inserted.append(key)

    if inserted:
        message = f'Seeded {len(inserted)} CRIS props: {", ".join(sorted(inserted))}'
        _LOGGER.info(message)
        logging.getLogger().info(message)
    else:
        _LOGGER.info('CRIS props defaults already present; no seeding performed')


__all__ = ['LINES_KEYS', 'LOG_KEYS', 'REFRESH_KEYS', 'get_prop', 'seed_default_props', 'set_prop']
