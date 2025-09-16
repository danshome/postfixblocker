import logging
import os
import signal
import subprocess  # nosec B404
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

# NOTE: Make SQLAlchemy an optional dependency at import time so unit tests that
# only exercise file-writing logic don't require the package to be installed.
try:  # Lazy/optional SQLAlchemy imports
    from sqlalchemy import (
        Boolean,
        Column,
        DateTime,
        Index,
        Integer,
        MetaData,
        String,
        Table,
        create_engine,
        func,
        inspect,
        select,
    )
    from sqlalchemy.engine import Engine as SAEngine
    from sqlalchemy.exc import OperationalError as SAOperationalError

    _SA_AVAILABLE = True
except Exception:  # pragma: no cover - exercised when SQLAlchemy is missing
    Column = Integer = String = Boolean = DateTime = None  # type: ignore
    MetaData = Table = Index = create_engine = select = func = inspect = None  # type: ignore
    SAEngine = object  # type: ignore
    SAOperationalError = Exception  # type: ignore
    _SA_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


def _setup_blocker_logging() -> None:
    # Default to DEBUG for detailed diagnostics; override via BLOCKER_LOG_LEVEL
    raw = (os.environ.get('BLOCKER_LOG_LEVEL') or 'INFO').strip()
    level_name = raw.upper()
    try:
        level = int(raw)
    except Exception:
        level = getattr(logging, level_name, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    # Ensure existing handlers honor the configured level (basicConfig/other libs)
    for h in list(root.handlers):
        try:
            h.setLevel(level)
        except Exception as exc:
            logging.debug('Could not set handler level: %s', exc)
    # Optional file handler
    log_path = os.environ.get('BLOCKER_LOG_FILE') or '/var/log/postfix-blocker/blocker.log'
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        from logging.handlers import RotatingFileHandler

        fh = RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=5)
        fh.setLevel(level)
        fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s %(message)s')
        fh.setFormatter(fmt)
        root = logging.getLogger()
        # Avoid duplicate handlers
        if not any(
            isinstance(h, RotatingFileHandler) and getattr(h, 'baseFilename', '') == fh.baseFilename
            for h in root.handlers
        ):
            root.addHandler(fh)
    except Exception as exc:  # pragma: no cover - filesystem/permissions
        logging.warning('Could not set up blocker file logging: %s', exc)
    # Emit a clear initialization line with requested/effective level and file
    logging.info(
        'Blocker logging initialized (requested_level=%s effective_level=%s file=%s)',
        level_name,
        logging.getLevelName(root.level),
        log_path,
    )


DB_URL = os.environ.get('BLOCKER_DB_URL', 'postgresql://blocker:blocker@db:5432/blocker')
CHECK_INTERVAL = float(os.environ.get('BLOCKER_INTERVAL', '5'))
POSTFIX_DIR = os.environ.get('POSTFIX_DIR', '/etc/postfix')
PID_FILE = os.environ.get('BLOCKER_PID_FILE', '/var/run/postfix-blocker/blocker.pid')

"""Database schema and helpers for Postfix Blocker.

The module is careful to work with both PostgreSQL and IBM DB2 11.5 via
SQLAlchemy. We avoid backend-specific DDL (e.g., "CREATE INDEX IF NOT EXISTS")
and instead declare indexes/constraints via SQLAlchemy so the dialect can
generate the right SQL for each backend.
"""

# Lazily construct metadata/table only if SQLAlchemy is present to avoid
# import-time failures when tests don't need DB access.

_metadata: Optional[MetaData] = None
_blocked_table: Optional[Table] = None
_props_table: Optional[Table] = None

# Public references (assigned once constructed) for convenient imports
blocked_table: Optional[Table] = None
metadata: Optional[MetaData] = None
props_table: Optional[Table] = None


def _ensure_sa_schema_loaded() -> None:
    global _metadata, _blocked_table, _props_table
    if not _SA_AVAILABLE:
        raise RuntimeError('SQLAlchemy is not installed; DB features are unavailable.')
    if _metadata is None or _blocked_table is None or _props_table is None:
        _metadata = MetaData()
        # Blocked addresses table
        _blocked_table = Table(
            'blocked_addresses',
            _metadata,
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('pattern', String(255), nullable=False),
            Column('is_regex', Boolean, nullable=False, default=False),
            Column('test_mode', Boolean, nullable=False, server_default='1'),
            Column(
                'updated_at',
                DateTime,
                server_default=func.current_timestamp(),  # type: ignore[attr-defined]
                onupdate=func.current_timestamp(),  # type: ignore[attr-defined]
            ),
        )
        # Properties table (CRIS_PROPS)
        _props_table = Table(
            'cris_props',
            _metadata,
            # DB2 has strict limits on indexed key length; 255 is safe across backends
            Column('key', String(255), primary_key=True),
            Column('value', String(1024), nullable=True),
            Column(
                'update_ts',
                DateTime,
                server_default=func.current_timestamp(),
                onupdate=func.current_timestamp(),
            ),
        )
        # Publish public references
        global blocked_table, metadata, props_table
        blocked_table = _blocked_table
        props_table = _props_table
        metadata = _metadata


@dataclass
class BlockEntry:
    pattern: str
    is_regex: bool
    # Default to enforce mode for compatibility with existing unit tests
    test_mode: bool = False


def get_engine() -> SAEngine:  # type: ignore[override]
    if not _SA_AVAILABLE:
        raise RuntimeError('SQLAlchemy is not installed; cannot create engine.')
    # Enable resilient pooling across both Postgres and DB2 drivers
    # - pool_pre_ping: validate connections before use to avoid stale sockets
    # - pool_use_lifo: reuse most-recently-returned connections to improve locality
    return create_engine(  # type: ignore[misc]
        DB_URL,
        pool_pre_ping=True,
        pool_use_lifo=True,
        pool_size=20,
        max_overflow=0,
        pool_recycle=3600,
    )


def init_db(engine: SAEngine) -> None:  # type: ignore[override]
    """Create table and indexes if they do not exist.

    Uses explicit transaction (engine.begin) for SQLAlchemy 2.x compatibility
    instead of autocommit execution options which are deprecated/removed.
    """
    _ensure_sa_schema_loaded()
    if _metadata is None:  # pragma: no cover - defensive
        raise RuntimeError('metadata not initialized')
    # Avoid DB2 duplicate index warnings by skipping create_all when the table
    # already exists. SQLAlchemy's index existence checks can be unreliable for
    # some DB2 versions.
    try:
        from sqlalchemy import inspect as _inspect  # type: ignore
    except Exception:  # pragma: no cover
        _inspect = inspect  # type: ignore
    table_exists = False
    try:
        table_exists = bool(
            _inspect is not None and _inspect(engine).has_table('blocked_addresses')
        )
    except Exception:
        table_exists = False
    if not table_exists:
        _metadata.create_all(engine)
    else:
        # Ensure auxiliary tables (e.g., cris_props) exist even if blocked_addresses already exists
        try:
            if _props_table is not None:
                _props_table.create(engine, checkfirst=True)  # type: ignore[attr-defined]
        except Exception as exc:
            # Best-effort; missing props table will be handled gracefully by getters
            logging.debug('Could not ensure props table exists: %s', exc)
    # Lightweight migration: ensure 'test_mode' column exists and is NOT NULL DEFAULT 1
    try:
        insp = _inspect(engine) if _inspect is not None else None  # type: ignore
        cols: list[Any] = []
        if insp is not None:
            try:
                cols = insp.get_columns('blocked_addresses') or []
            except Exception:
                cols = []
        existing_cols = {(c.get('name') or '').lower() for c in cols}
    except Exception:
        existing_cols = set()
    if 'test_mode' not in existing_cols:
        with engine.begin() as conn:
            # Try BOOLEAN first with a portable TRUE default; if it fails
            # (e.g., some DB2 variants), fall back to SMALLINT(1)
            try:
                conn.exec_driver_sql(
                    'ALTER TABLE blocked_addresses ADD COLUMN test_mode BOOLEAN NOT NULL DEFAULT TRUE'
                )
            except Exception:
                conn.exec_driver_sql(
                    'ALTER TABLE blocked_addresses ADD COLUMN test_mode SMALLINT NOT NULL DEFAULT 1'
                )
            # Ensure existing rows are set to test mode
            try:
                conn.exec_driver_sql(
                    'UPDATE blocked_addresses SET test_mode = 1 WHERE test_mode IS NULL'
                )
            except Exception:
                # For BOOLEAN types, set TRUE explicitly
                try:
                    conn.exec_driver_sql(
                        'UPDATE blocked_addresses SET test_mode = TRUE WHERE test_mode IS NULL'
                    )
                except Exception:
                    logging.debug('Could not normalize legacy NULL test_mode values; continuing')


def fetch_entries(engine: SAEngine) -> list[BlockEntry]:  # type: ignore[override]
    _ensure_sa_schema_loaded()
    if _blocked_table is None:  # pragma: no cover - defensive
        raise RuntimeError('blocked table not initialized')
    with engine.connect() as conn:  # type: ignore[attr-defined]
        res = conn.execute(
            select(_blocked_table.c.pattern, _blocked_table.c.is_regex, _blocked_table.c.test_mode)
        )
        try:
            rows = res.fetchall() or []
        except TypeError:
            rows = []
        return [BlockEntry(pattern=row[0], is_regex=row[1], test_mode=bool(row[2])) for row in rows]


def get_props_table() -> Table:
    _ensure_sa_schema_loaded()
    if props_table is None:
        raise RuntimeError('props table not initialized')
    return props_table


def get_prop(engine: SAEngine, key: str, default: Optional[str] = None) -> Optional[str]:
    _ensure_sa_schema_loaded()
    pt = get_props_table()
    try:
        with engine.connect() as conn:
            res = conn.execute(select(pt.c.value).where(pt.c.key == key)).scalar()
            return res if res is not None else default
    except Exception:
        return default


def set_prop(engine: SAEngine, key: str, value: Optional[str]) -> None:
    _ensure_sa_schema_loaded()
    pt = get_props_table()
    with engine.begin() as conn:
        # Upsert portable: try update, if rowcount==0 then insert
        rc = conn.execute(pt.update().where(pt.c.key == key).values(value=value)).rowcount or 0
        if rc == 0:
            try:
                conn.execute(pt.insert().values(key=key, value=value))
            except Exception:
                # Race-safe second update
                conn.execute(pt.update().where(pt.c.key == key).values(value=value))


def get_change_marker(engine: SAEngine) -> Optional[tuple[str, int]]:
    """Return a lightweight marker indicating table changes or None if unsupported.

    Uses (max(updated_at), count(*)) so any insert/update/delete changes the marker
    without fetching full rows. Falls back to None if the column is missing or
    the backend/dialect cannot compute the aggregate.
    """
    _ensure_sa_schema_loaded()
    if _blocked_table is None:  # pragma: no cover - defensive
        return None
    try:
        with engine.connect() as conn:  # type: ignore[attr-defined]
            row = conn.execute(select(func.max(_blocked_table.c.updated_at), func.count())).one()
            max_ts, cnt = row[0], int(row[1] or 0)
            marker = (str(max_ts) if max_ts is not None else '', cnt)
            return marker
    except Exception:
        return None


def write_map_files(entries: list[BlockEntry]) -> None:
    """Write Postfix access files for literal and regex blocks.

    Two sets of maps are maintained:
    - Enforced maps: blocked_recipients, blocked_recipients.pcre (REJECT)
    - Test maps: blocked_recipients_test, blocked_recipients_test.pcre (REJECT, but referenced via warn_if_reject)
    """
    literal_lines: list[str] = []
    regex_lines: list[str] = []
    test_literal_lines: list[str] = []
    test_regex_lines: list[str] = []
    for entry in entries:
        line_lit = f'{entry.pattern}\tREJECT'
        line_re = f'/{entry.pattern}/ REJECT'
        if entry.test_mode:
            if entry.is_regex:
                test_regex_lines.append(line_re)
            else:
                test_literal_lines.append(line_lit)
        else:
            if entry.is_regex:
                regex_lines.append(line_re)
            else:
                literal_lines.append(line_lit)

    logging.info(
        'Preparing Postfix maps: enforce(lit=%d, re=%d) test(lit=%d, re=%d)',
        len(literal_lines),
        len(regex_lines),
        len(test_literal_lines),
        len(test_regex_lines),
    )

    paths = {
        'literal': os.path.join(POSTFIX_DIR, 'blocked_recipients'),
        'regex': os.path.join(POSTFIX_DIR, 'blocked_recipients.pcre'),
        'test_literal': os.path.join(POSTFIX_DIR, 'blocked_recipients_test'),
        'test_regex': os.path.join(POSTFIX_DIR, 'blocked_recipients_test.pcre'),
    }

    # Ensure deterministic trailing newline only when there is content.
    with open(paths['literal'], 'w', encoding='utf-8') as f:
        f.write('\n'.join(literal_lines) + ('\n' if literal_lines else ''))
    with open(paths['regex'], 'w', encoding='utf-8') as f:
        f.write('\n'.join(regex_lines) + ('\n' if regex_lines else ''))
    with open(paths['test_literal'], 'w', encoding='utf-8') as f:
        f.write('\n'.join(test_literal_lines) + ('\n' if test_literal_lines else ''))
    with open(paths['test_regex'], 'w', encoding='utf-8') as f:
        f.write('\n'.join(test_regex_lines) + ('\n' if test_regex_lines else ''))

    logging.info(
        'Wrote maps: %s (bytes=%d), %s (bytes=%d), %s (bytes=%d), %s (bytes=%d)',
        paths['literal'],
        os.path.getsize(paths['literal']),
        paths['regex'],
        os.path.getsize(paths['regex']),
        paths['test_literal'],
        os.path.getsize(paths['test_literal']),
        paths['test_regex'],
        os.path.getsize(paths['test_regex']),
    )


def reload_postfix() -> None:
    """Run postmap and reload Postfix to pick up changes.

    Be tolerant of early container startup states where Postfix may not yet be
    ready. Downgrade noisy errors to warnings and retry on next loop.
    """
    literal_path = os.path.join(POSTFIX_DIR, 'blocked_recipients')
    test_literal_path = os.path.join(POSTFIX_DIR, 'blocked_recipients_test')
    try:
        logging.info('Running postmap on %s and %s', literal_path, test_literal_path)
        rc1 = subprocess.run(['/usr/sbin/postmap', literal_path], check=False).returncode  # nosec B603
        rc1b = subprocess.run(['/usr/sbin/postmap', test_literal_path], check=False).returncode  # nosec B603
        # Consider empty files benign: postmap may return non-zero in some builds
        try:
            size1 = os.path.getsize(literal_path)
            size2 = os.path.getsize(test_literal_path)
        except Exception:
            size1 = size2 = -1
        # Only attempt reload if postfix master appears to be running
        try:
            status_rc = subprocess.run(['/usr/sbin/postfix', 'status'], check=False).returncode  # nosec B603
        except Exception:
            status_rc = 1
        if status_rc == 0:
            logging.info('Reloading postfix')
            rc2 = subprocess.run(['/usr/sbin/postfix', 'reload'], check=False).returncode  # nosec B603
        else:
            rc2 = None
            logging.debug('Postfix master not running yet; skipping reload')
        # Log at WARNING instead of ERROR for transient/non-critical states
        failed = [
            str(x)
            for x in (rc1, rc1b, rc2 if rc2 is not None else 0)
            if isinstance(x, int) and x != 0
        ]
        if failed:
            if (size1 == 0 or size2 == 0) and status_rc != 0:
                logging.warning(
                    'Postfix commands had non-zero return codes (postmap/literals or reload) but environment not ready yet: '
                    'postmap=%s postmap_test=%s reload=%s',
                    rc1,
                    rc1b,
                    rc2,
                )
            else:
                logging.warning(
                    'Postfix commands had non-zero return codes: postmap=%s postmap_test=%s reload=%s',
                    rc1,
                    rc1b,
                    rc2,
                )
    except Exception as exc:
        logging.warning('Failed to reload postfix (transient): %s', exc)


# One-time capability check flags
_PCRE_CHECKED = False
_PCRE_AVAILABLE = False
_PCRE_REGEX_WARNED = False


def _has_postfix_pcre() -> bool:
    """Return True if Postfix supports PCRE maps ("pcre" listed in postconf -m)."""
    try:
        # Fixed command and arguments; no user-controlled input involved.
        res = subprocess.run(  # nosec B603
            ['/usr/sbin/postconf', '-m'], capture_output=True, text=True, check=True
        )
        return 'pcre' in res.stdout.lower()
    except FileNotFoundError:
        logging.error("'postconf' not found; cannot verify Postfix PCRE support.")
        return False
    except Exception as exc:  # pragma: no cover - environment dependent
        logging.warning("Could not verify Postfix PCRE support via 'postconf -m': %s", exc)
        return False


_refresh_event = threading.Event()


def _sigusr1(_signum, _frame) -> None:  # pragma: no cover - signal handler
    _refresh_event.set()


def _setup_signal_ipc() -> None:
    try:
        signal.signal(signal.SIGUSR1, _sigusr1)
        logging.info('Blocker listening for SIGUSR1 to trigger refresh')
    except Exception as exc:  # pragma: no cover - platform dependent
        logging.warning('Could not set SIGUSR1 handler: %s', exc)


def _write_pid_file() -> None:
    try:
        d = os.path.dirname(PID_FILE)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(PID_FILE, 'w', encoding='utf-8') as f:
            f.write(str(os.getpid()))
        logging.info('Blocker PID file written: %s', PID_FILE)
    except Exception as exc:  # pragma: no cover - filesystem/permissions
        logging.warning('Could not write PID file %s: %s', PID_FILE, exc)


def monitor_loop() -> None:
    engine: Optional[SAEngine] = None
    # Be resilient to slow DB startup (e.g., DB2 taking minutes) or missing
    # drivers initially. Keep the process alive and retry instead of exiting.
    while True:
        try:
            if engine is None:
                logging.debug('Creating SQLAlchemy engine in blocker.monitor_loop')
                engine = get_engine()
            logging.debug('Initializing DB schema in blocker.monitor_loop')
            init_db(engine)
            logging.info('Database schema ready.')
            break
        except SAOperationalError as exc:
            logging.warning('DB init not ready: %s; retrying in %ss', exc, CHECK_INTERVAL)
        except Exception as exc:  # pragma: no cover - depends on external DB readiness
            logging.warning('DB init failed: %s; retrying in %ss', exc, CHECK_INTERVAL)
        time.sleep(CHECK_INTERVAL)

    # One-time PCRE capability check (log explicit error once on startup)
    global _PCRE_CHECKED, _PCRE_AVAILABLE
    if not _PCRE_CHECKED:
        _PCRE_AVAILABLE = _has_postfix_pcre()
        _PCRE_CHECKED = True
        if not _PCRE_AVAILABLE:
            logging.error(
                "Postfix PCRE support not detected (no 'pcre' in 'postconf -m'). "
                "Regex rules will not be enforced and 'postfix reload' may fail "
                'if main.cf references a PCRE map. Ensure Postfix PCRE support is enabled.'
            )
    last_marker: Optional[tuple[str, int]] = None
    last_hash = None
    last_blocker_level: Optional[str] = None
    while True:
        try:
            logging.debug('Blocker loop heartbeat start (last_marker=%s)', last_marker)
            # Apply dynamic blocker log level from props
            try:
                level_str = get_prop(engine, 'log.level.blocker', None)
                if level_str is not None and level_str != last_blocker_level:
                    lvl = None
                    try:
                        lvl = int(level_str)
                    except Exception:
                        lvl = getattr(logging, str(level_str).upper(), None)
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

            marker = get_change_marker(engine)
            logging.debug('Change marker current=%s last=%s', marker, last_marker)
            if marker is not None and marker == last_marker:
                # No change detected; sleep and continue
                _refresh_event.wait(CHECK_INTERVAL)
                # Clear the flag if it was set; loop will process next
                if _refresh_event.is_set():
                    logging.debug('Woke up via SIGUSR1 or timeout with no marker change')
                    _refresh_event.clear()
                continue
            # Fetch full entries only when change is detected or marker unavailable
            entries = fetch_entries(engine)
            logging.debug('Fetched %d entries from DB', len(entries))
            # Warn once if regex entries exist but PCRE is unavailable
            global _PCRE_REGEX_WARNED
            if (not _PCRE_AVAILABLE) and (not _PCRE_REGEX_WARNED):
                regex_count = sum(1 for e in entries if e.is_regex)
                if regex_count:
                    logging.warning(
                        '%d regex entries present but Postfix PCRE support is missing; '
                        'regex rules will NOT be enforced.',
                        regex_count,
                    )
                    _PCRE_REGEX_WARNED = True
            # Include test_mode and sort for deterministic change detection.
            # Previously, test_mode changes did not trigger a reload; include it here
            # so switching between Test/Enforce updates the Postfix maps.
            sig = tuple(sorted((e.pattern, bool(e.is_regex), bool(e.test_mode)) for e in entries))
            current_hash = hash(sig)
            logging.debug('Computed content hash=%s (last_hash=%s)', current_hash, last_hash)
            # Update when either marker changed or content hash changed (fallback)
            if (marker is not None and marker != last_marker) or (
                marker is None and current_hash != last_hash
            ):
                write_map_files(entries)
                reload_postfix()
                last_hash = current_hash
                last_marker = marker
        except SAOperationalError:
            logging.exception('Database error')
        except Exception:  # pragma: no cover - transient external failures
            logging.exception('Unexpected error')
        _refresh_event.wait(CHECK_INTERVAL)
        if _refresh_event.is_set():
            logging.debug('SIGUSR1 received or timer elapsed; continuing loop')
            _refresh_event.clear()


def get_blocked_table() -> Table:
    """Return the SQLAlchemy Table for blocked addresses.

    Useful for tests and callers that need to construct SQLAlchemy statements
    without relying on module import-time side effects.
    """
    _ensure_sa_schema_loaded()
    if _blocked_table is None:  # pragma: no cover - defensive
        raise RuntimeError('blocked table not initialized')
    return _blocked_table


if __name__ == '__main__':
    _setup_blocker_logging()
    _setup_signal_ipc()
    _write_pid_file()
    monitor_loop()
