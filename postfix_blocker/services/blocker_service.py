from __future__ import annotations

import logging
import os
import signal
import threading
import time

from sqlalchemy import select  # type: ignore
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError as SAOperationalError  # type: ignore

from ..config import Config, load_config
from ..db.engine import get_engine
from ..db.migrations import init_db
from ..db.props import LOG_KEYS, get_prop
from ..db.schema import get_blocked_table
from ..models.entries import BlockEntry
from ..postfix.control import has_postfix_pcre, reload_postfix
from ..postfix.maps import write_map_files

_refresh_event = threading.Event()


def setup_signal_ipc() -> None:
    try:
        signal.signal(signal.SIGUSR1, lambda *_: _refresh_event.set())
        logging.info('Blocker listening for SIGUSR1 to trigger refresh')
    except Exception as exc:  # pragma: no cover - platform dependent
        logging.warning('Could not set SIGUSR1 handler: %s', exc)


def write_pid_file(pid_path: str) -> None:
    try:
        d = os.path.dirname(pid_path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(pid_path, 'w', encoding='utf-8') as f:
            f.write(str(os.getpid()))
        logging.info('Blocker PID file written: %s', pid_path)
    except Exception as exc:  # pragma: no cover - filesystem/permissions
        logging.warning('Could not write PID file %s: %s', pid_path, exc)


def _fetch_entries(engine: Engine) -> list[BlockEntry]:
    bt = get_blocked_table()
    with engine.connect() as conn:
        res = conn.execute(select(bt.c.pattern, bt.c.is_regex, bt.c.test_mode))
        try:
            rows = res.fetchall() or []
        except TypeError:
            rows = []
    return [BlockEntry(pattern=row[0], is_regex=row[1], test_mode=bool(row[2])) for row in rows]


def _get_change_marker(engine: Engine) -> tuple[str, int] | None:
    bt = get_blocked_table()
    from sqlalchemy import func  # lazy import

    try:
        with engine.connect() as conn:
            row = conn.execute(select(func.max(bt.c.updated_at), func.count())).one()
            max_ts, cnt = row[0], int(row[1] or 0)
            return (str(max_ts) if max_ts is not None else '', cnt)
    except Exception:
        return None


def run_forever(config: Config | None = None) -> None:
    cfg = config or load_config()

    # Write PID file and set up signal-based IPC so API can trigger immediate refresh
    try:
        write_pid_file(cfg.pid_file)
    except Exception as exc:  # pragma: no cover - filesystem/permissions
        logging.debug('Unable to write PID file at startup: %s', exc)
    try:
        setup_signal_ipc()
    except Exception as exc:  # pragma: no cover - platform dependent
        logging.debug('Unable to set up signal IPC at startup: %s', exc)

    # One-time PCRE capability check
    pcre_available = has_postfix_pcre()
    if not pcre_available:
        logging.error(
            "Postfix PCRE support not detected (no 'pcre' in 'postconf -m'). Regex rules may not be enforced."
        )

    engine: Engine | None = None
    while True:
        try:
            if engine is None:
                logging.debug('Creating SQLAlchemy engine in blocker_service.run_forever')
                engine = get_engine()
            logging.debug('Initializing DB schema in blocker_service.run_forever')
            init_db(engine)
            logging.info('Database schema ready.')
            break
        except SAOperationalError as exc:
            logging.warning('DB init not ready: %s; retrying in %ss', exc, cfg.check_interval)
        except Exception as exc:  # pragma: no cover - depends on external DB readiness
            logging.warning('DB init failed: %s; retrying in %ss', exc, cfg.check_interval)
        time.sleep(cfg.check_interval)

    last_marker: tuple[str, int] | None = None
    last_hash = None
    last_blocker_level: str | None = None

    # Ensure refresh wait starts clean
    _refresh_event.clear()

    while True:
        try:
            logging.debug('Blocker loop heartbeat start (last_marker=%s)', last_marker)
            # Dynamic blocker log level from props
            try:
                level_str = get_prop(engine, LOG_KEYS['blocker'], None)  # type: ignore[arg-type]
                if level_str is not None and level_str != last_blocker_level:
                    try:
                        lvl = int(level_str)
                    except Exception:
                        lvl = getattr(logging, str(level_str).upper(), logging.INFO)
                    if isinstance(lvl, int):
                        logging.getLogger().setLevel(lvl)
                        for h in list(logging.getLogger().handlers):
                            try:
                                h.setLevel(lvl)
                            except Exception as exc:
                                logging.debug('Failed to set handler level: %s', exc)
                        logging.info('Blocker log level changed via props to %s', level_str)
                        last_blocker_level = level_str
            except Exception as exc:
                logging.debug('Failed to apply dynamic blocker log level: %s', exc)

            marker = _get_change_marker(engine)
            logging.debug('Change marker current=%s last=%s', marker, last_marker)
            entries = _fetch_entries(engine)
            logging.debug('Fetched %d entries from DB', len(entries))

            # Content signature includes test_mode to ensure map changes on mode toggle
            sig = tuple(sorted((e.pattern, bool(e.is_regex), bool(e.test_mode)) for e in entries))
            current_hash = hash(sig)
            logging.debug('Computed content hash=%s (last_hash=%s)', current_hash, last_hash)

            if (marker is not None and marker != last_marker) or (current_hash != last_hash):
                write_map_files(entries, cfg.postfix_dir)
                reload_postfix()
                # Emit a deterministic single-line apply marker for E2E tests and operators
                try:
                    total = len(entries)
                except Exception:
                    total = -1
                logging.info(
                    'BLOCKER_APPLY maps_updated total_entries=%s marker=%s hash=%s',
                    total,
                    marker,
                    current_hash,
                )
                last_hash = current_hash
                last_marker = marker
        except SAOperationalError:
            logging.exception('Database error')
        except Exception:  # pragma: no cover - transient external failures
            logging.exception('Unexpected error')
        _refresh_event.wait(cfg.check_interval)
        if _refresh_event.is_set():
            logging.debug('SIGUSR1 received or timer elapsed; continuing loop')
            _refresh_event.clear()
