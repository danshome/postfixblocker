import logging
import os
import subprocess  # nosec B404
import time
from dataclasses import dataclass
from typing import Optional

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

DB_URL = os.environ.get('BLOCKER_DB_URL', 'postgresql://blocker:blocker@db:5432/blocker')
CHECK_INTERVAL = float(os.environ.get('BLOCKER_INTERVAL', '5'))
POSTFIX_DIR = os.environ.get('POSTFIX_DIR', '/etc/postfix')

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

# Public references (assigned once constructed) for convenient imports
blocked_table: Optional[Table] = None
metadata: Optional[MetaData] = None


def _ensure_sa_schema_loaded() -> None:
    global _metadata, _blocked_table
    if not _SA_AVAILABLE:
        raise RuntimeError('SQLAlchemy is not installed; DB features are unavailable.')
    if _metadata is None or _blocked_table is None:
        _metadata = MetaData()
        # Use CURRENT_TIMESTAMP via SQLAlchemy to stay portable across backends
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
        # Rely on the unique constraint on pattern for indexing across backends.
        # Some DB2 environments raise a warning-as-error when attempting to
        # create a duplicate non-unique index over an existing unique index.

        # Publish public references
        global blocked_table, metadata
        blocked_table = _blocked_table
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
    return create_engine(DB_URL)  # type: ignore[misc]


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
    # Lightweight migration: ensure 'test_mode' column exists and is NOT NULL DEFAULT 1
    try:
        insp = _inspect(engine) if _inspect is not None else None  # type: ignore
        existing_cols = {
            c['name'].lower() for c in (insp.get_columns('blocked_addresses') if insp else [])
        }
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
        rows = conn.execute(
            select(_blocked_table.c.pattern, _blocked_table.c.is_regex, _blocked_table.c.test_mode)
        ).fetchall()
        return [BlockEntry(pattern=row[0], is_regex=row[1], test_mode=bool(row[2])) for row in rows]


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
        'Wrote maps: %s, %s, %s, %s',
        paths['literal'],
        paths['regex'],
        paths['test_literal'],
        paths['test_regex'],
    )


def reload_postfix() -> None:
    """Run postmap and reload Postfix to pick up changes."""
    literal_path = os.path.join(POSTFIX_DIR, 'blocked_recipients')
    test_literal_path = os.path.join(POSTFIX_DIR, 'blocked_recipients_test')
    try:
        logging.info('Running postmap')
        rc1 = subprocess.run(['/usr/sbin/postmap', literal_path], check=False).returncode  # nosec B603
        rc1b = subprocess.run(['/usr/sbin/postmap', test_literal_path], check=False).returncode  # nosec B603
        logging.info('Reloading postfix')
        rc2 = subprocess.run(['/usr/sbin/postfix', 'reload'], check=False).returncode  # nosec B603
        if rc1 != 0 or rc1b != 0 or rc2 != 0:
            logging.error(
                'Postfix commands failed: postmap=%s postmap_test=%s reload=%s', rc1, rc1b, rc2
            )
    except Exception as exc:
        logging.error('Failed to reload postfix: %s', exc)


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


def monitor_loop() -> None:
    engine: Optional[SAEngine] = None
    # Be resilient to slow DB startup (e.g., DB2 taking minutes) or missing
    # drivers initially. Keep the process alive and retry instead of exiting.
    while True:
        try:
            if engine is None:
                engine = get_engine()
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
    last_hash = None
    while True:
        try:
            entries = fetch_entries(engine)
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
            current_hash = hash(tuple((e.pattern, e.is_regex) for e in entries))
            if current_hash != last_hash:
                write_map_files(entries)
                reload_postfix()
                last_hash = current_hash
        except SAOperationalError as exc:
            logging.error('Database error: %s', exc)
        except Exception as exc:  # pragma: no cover - transient external failures
            logging.error('Unexpected error: %s', exc)
        time.sleep(CHECK_INTERVAL)


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
    monitor_loop()
