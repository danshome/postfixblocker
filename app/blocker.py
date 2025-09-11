import os
import time
import logging
from typing import List
from dataclasses import dataclass

from sqlalchemy import (Column, Integer, String, Boolean, DateTime,
                        MetaData, Table, create_engine, select, func)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.sql import text

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

DB_URL = os.environ.get("BLOCKER_DB_URL", "postgresql://blocker:blocker@db:5432/blocker")
CHECK_INTERVAL = float(os.environ.get("BLOCKER_INTERVAL", "5"))
POSTFIX_DIR = os.environ.get("POSTFIX_DIR", "/etc/postfix")

metadata = MetaData()

blocked_table = Table(
    "blocked_addresses",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("pattern", String(255), nullable=False, unique=True),
    Column("is_regex", Boolean, nullable=False, default=False),
    Column("updated_at", DateTime, server_default=func.now(), onupdate=func.now()),
)

@dataclass
class BlockEntry:
    pattern: str
    is_regex: bool


def get_engine() -> Engine:
    return create_engine(DB_URL)


def init_db(engine: Engine) -> None:
    """Create table and indexes if they do not exist."""
    metadata.create_all(engine)
    # Simple index on pattern for faster lookups
    with engine.connect() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_blocked_pattern ON blocked_addresses(pattern)").execution_options(autocommit=True))


def fetch_entries(engine: Engine) -> List[BlockEntry]:
    with engine.connect() as conn:
        rows = conn.execute(select(blocked_table.c.pattern, blocked_table.c.is_regex)).fetchall()
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

    with open(literal_path, "w", encoding="utf-8") as f:
        f.write("\n".join(literal_lines) + "\n")
    with open(regex_path, "w", encoding="utf-8") as f:
        f.write("\n".join(regex_lines) + "\n")

    logging.info("Wrote %s and %s", literal_path, regex_path)


def reload_postfix() -> None:
    """Run postmap and reload Postfix to pick up changes."""
    literal_path = os.path.join(POSTFIX_DIR, "blocked_recipients")
    try:
        logging.info("Running postmap")
        os.system(f"postmap {literal_path}")
        logging.info("Reloading postfix")
        os.system("postfix reload")
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
