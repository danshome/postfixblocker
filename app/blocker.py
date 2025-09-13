import os
import time
import logging
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
        create_engine,
        select,
        func,
    )
    from sqlalchemy.engine import Engine
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.sql import text
    _SA_AVAILABLE = True
except Exception:  # pragma: no cover - exercised when SQLAlchemy is missing
    Column = Integer = String = Boolean = DateTime = None  # type: ignore
    MetaData = Table = create_engine = select = func = None  # type: ignore
    Engine = object  # type: ignore
    OperationalError = Exception  # Fallback for broad except
    text = None  # type: ignore
    _SA_AVAILABLE = False

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

DB_URL = os.environ.get("BLOCKER_DB_URL", "postgresql://blocker:blocker@db:5432/blocker")
CHECK_INTERVAL = float(os.environ.get("BLOCKER_INTERVAL", "5"))
POSTFIX_DIR = os.environ.get("POSTFIX_DIR", "/etc/postfix")

# Lazily construct metadata/table only if SQLAlchemy is present to avoid
# import-time failures when tests don't need DB access.
_metadata = None  # type: Optional[MetaData]
_blocked_table = None  # type: Optional[Table]

def _ensure_sa_schema_loaded() -> None:
    global _metadata, _blocked_table
    if not _SA_AVAILABLE:
        raise RuntimeError("SQLAlchemy is not installed; DB features are unavailable.")
    if _metadata is None or _blocked_table is None:
        _metadata = MetaData()
        _blocked_table = Table(
            "blocked_addresses",
            _metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("pattern", String(255), nullable=False, unique=True),
            Column("is_regex", Boolean, nullable=False, default=False),
            Column(
                "updated_at",
                DateTime,
                server_default=func.now(),
                onupdate=func.now(),
            ),
        )

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
    # Create tables
    assert _metadata is not None
    _metadata.create_all(engine)
    # Create index in a transaction-safe way
    with engine.begin() as conn:  # type: ignore[attr-defined]
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_blocked_pattern ON blocked_addresses(pattern)"
            )
        )


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


def monitor_loop() -> None:
    engine = get_engine()
    init_db(engine)
    last_hash = None
    while True:
        try:
            entries = fetch_entries(engine)
            current_hash = hash(tuple((e.pattern, e.is_regex) for e in entries))
            if current_hash != last_hash:
                write_map_files(entries)
                reload_postfix()
                last_hash = current_hash
        except OperationalError as exc:
            logging.error("Database error: %s", exc)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    monitor_loop()
