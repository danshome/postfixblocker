import os
import time
import logging
import subprocess
from typing import List, Optional
from dataclasses import dataclass

# NOTE: Make SQLAlchemy an optional dependency at import time so unit tests that
# only exercise file-writing logic don't require the package to be installed.
try:  # Lazy/optional SQLAlchemy imports
    from sqlalchemy import (
        Column,
        Integer,
        String,
        Boolean,
        DateTime,
        MetaData,
        Table,
        Index,
        create_engine,
        select,
        func,
        inspect,
    )
    from sqlalchemy.engine import Engine
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.sql import text
    _SA_AVAILABLE = True
except Exception:  # pragma: no cover - exercised when SQLAlchemy is missing
    Column = Integer = String = Boolean = DateTime = None  # type: ignore
    MetaData = Table = Index = create_engine = select = func = inspect = None  # type: ignore
    Engine = object  # type: ignore
    OperationalError = Exception  # Fallback for broad except
    text = None  # type: ignore
    _SA_AVAILABLE = False

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

DB_URL = os.environ.get("BLOCKER_DB_URL", "postgresql://blocker:blocker@db:5432/blocker")
CHECK_INTERVAL = float(os.environ.get("BLOCKER_INTERVAL", "5"))
POSTFIX_DIR = os.environ.get("POSTFIX_DIR", "/etc/postfix")

"""Database schema and helpers for Postfix Blocker.

The module is careful to work with both PostgreSQL and IBM DB2 11.5 via
SQLAlchemy. We avoid backend-specific DDL (e.g., "CREATE INDEX IF NOT EXISTS")
and instead declare indexes/constraints via SQLAlchemy so the dialect can
generate the right SQL for each backend.
"""

# Lazily construct metadata/table only if SQLAlchemy is present to avoid
# import-time failures when tests don't need DB access.
_metadata = None  # type: Optional[MetaData]
_blocked_table = None  # type: Optional[Table]

# Public references (assigned once constructed) for convenient imports
blocked_table: Optional[Table] = None
metadata: Optional[MetaData] = None

def _ensure_sa_schema_loaded() -> None:
    global _metadata, _blocked_table
    if not _SA_AVAILABLE:
        raise RuntimeError("SQLAlchemy is not installed; DB features are unavailable.")
    if _metadata is None or _blocked_table is None:
        _metadata = MetaData()
        # Use CURRENT_TIMESTAMP via SQLAlchemy to stay portable across backends
        _blocked_table = Table(
            "blocked_addresses",
            _metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("pattern", String(255), nullable=False),
            Column("is_regex", Boolean, nullable=False, default=False),
            Column(
                "updated_at",
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


def get_engine() -> Engine:  # type: ignore[override]
    if not _SA_AVAILABLE:
        raise RuntimeError("SQLAlchemy is not installed; cannot create engine.")
    return create_engine(DB_URL)  # type: ignore[misc]


def init_db(engine: Engine) -> None:  # type: ignore[override]
    """Create table and indexes if they do not exist.

    Uses explicit transaction (engine.begin) for SQLAlchemy 2.x compatibility
    instead of autocommit execution options which are deprecated/removed.
    """
    _ensure_sa_schema_loaded()
    assert _metadata is not None
    # Avoid DB2 duplicate index warnings by skipping create_all when the table
    # already exists. SQLAlchemy's index existence checks can be unreliable for
    # some DB2 versions.
    try:
        from sqlalchemy import inspect as _inspect  # type: ignore
    except Exception:  # pragma: no cover
        _inspect = inspect  # type: ignore
    try:
        if _inspect is not None and _inspect(engine).has_table("blocked_addresses"):
            return
    except Exception:
        # Fall back to attempting create_all if inspection fails
        pass
    _metadata.create_all(engine)


def fetch_entries(engine: Engine) -> List[BlockEntry]:  # type: ignore[override]
    _ensure_sa_schema_loaded()
    assert _blocked_table is not None
    with engine.connect() as conn:  # type: ignore[attr-defined]
        rows = conn.execute(
            select(_blocked_table.c.pattern, _blocked_table.c.is_regex)
        ).fetchall()
        return [BlockEntry(pattern=row[0], is_regex=row[1]) for row in rows]


def write_map_files(entries: List[BlockEntry]) -> None:
    """Write Postfix access files for literal and regex blocks."""
    literal_lines = []
    regex_lines = []
    for entry in entries:
        if entry.is_regex:
            regex_lines.append(f"/{entry.pattern}/ REJECT")
        else:
            literal_lines.append(f"{entry.pattern}\tREJECT")

    literal_path = os.path.join(POSTFIX_DIR, "blocked_recipients")
    regex_path = os.path.join(POSTFIX_DIR, "blocked_recipients.pcre")

    # Ensure deterministic trailing newline only when there is content.
    with open(literal_path, "w", encoding="utf-8") as f:
        f.write("\n".join(literal_lines) + ("\n" if literal_lines else ""))
    with open(regex_path, "w", encoding="utf-8") as f:
        f.write("\n".join(regex_lines) + ("\n" if regex_lines else ""))

    logging.info("Wrote %s and %s", literal_path, regex_path)


def reload_postfix() -> None:
    """Run postmap and reload Postfix to pick up changes."""
    literal_path = os.path.join(POSTFIX_DIR, "blocked_recipients")
    try:
        logging.info("Running postmap")
        rc1 = os.system(f"postmap {literal_path}")
        logging.info("Reloading postfix")
        rc2 = os.system("postfix reload")
        if rc1 != 0 or rc2 != 0:
            logging.error("Postfix commands failed: postmap=%s reload=%s", rc1, rc2)
    except Exception as exc:
        logging.error("Failed to reload postfix: %s", exc)


# One-time capability check flags
_PCRE_CHECKED = False
_PCRE_AVAILABLE = False
_PCRE_REGEX_WARNED = False


def _has_postfix_pcre() -> bool:
    """Return True if Postfix supports PCRE maps ("pcre" listed in postconf -m)."""
    try:
        res = subprocess.run(["postconf", "-m"], capture_output=True, text=True, check=True)
        return "pcre" in res.stdout.lower()
    except FileNotFoundError:
        logging.error("'postconf' not found; cannot verify Postfix PCRE support.")
        return False
    except Exception as exc:  # pragma: no cover - environment dependent
        logging.warning("Could not verify Postfix PCRE support via 'postconf -m': %s", exc)
        return False


def monitor_loop() -> None:
    engine = get_engine()
    # Be resilient to slow DB startup (e.g., DB2 taking minutes). Keep the
    # process alive and retry schema initialization instead of exiting so
    # supervisord doesn't thrash the process with rapid restarts.
    while True:
        try:
            init_db(engine)
            logging.info("Database schema ready.")
            break
        except OperationalError as exc:
            logging.warning("DB init not ready: %s; retrying in %ss", exc, CHECK_INTERVAL)
        except Exception as exc:  # pragma: no cover - depends on external DB readiness
            logging.warning("DB init failed: %s; retrying in %ss", exc, CHECK_INTERVAL)
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
                "if main.cf references a PCRE map. Ensure Postfix PCRE support is enabled."
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
                        "%d regex entries present but Postfix PCRE support is missing; "
                        "regex rules will NOT be enforced.",
                        regex_count,
                    )
                    _PCRE_REGEX_WARNED = True
            current_hash = hash(tuple((e.pattern, e.is_regex) for e in entries))
            if current_hash != last_hash:
                write_map_files(entries)
                reload_postfix()
                last_hash = current_hash
        except OperationalError as exc:
            logging.error("Database error: %s", exc)
        except Exception as exc:  # pragma: no cover - transient external failures
            logging.error("Unexpected error: %s", exc)
        time.sleep(CHECK_INTERVAL)


def get_blocked_table() -> Table:
    """Return the SQLAlchemy Table for blocked addresses.

    Useful for tests and callers that need to construct SQLAlchemy statements
    without relying on module import-time side effects.
    """
    _ensure_sa_schema_loaded()
    assert _blocked_table is not None
    return _blocked_table


if __name__ == "__main__":
    monitor_loop()
