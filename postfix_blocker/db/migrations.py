# ruff: noqa: E402
from __future__ import annotations

"""Database initialization and lightweight migrations (refactor implementation)."""
import logging as _logging

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from .schema import _ensure_loaded, get_blocked_table, get_props_table  # type: ignore


def init_db(engine: Engine) -> None:
    """Create tables if needed and perform lightweight migrations.

    - Ensure both blocked_addresses and cris_props exist.
    - Ensure test_mode column exists with NOT NULL default.

    Notes:
    - Some dialects (e.g., DB2) can misreport table existence via Inspector.
      To avoid spurious CREATE TABLE errors (SQL0601N), we attempt creation
      unconditionally and ignore "already exists" errors in a portable way.
    """
    _ensure_loaded()
    insp = inspect(engine)
    dname = (engine.dialect.name or '').lower()

    # Legacy alternative backend support has been removed.

    # Db2: mirror sql/db2_init.sql so we don't depend on a DBA
    if dname in ('ibm_db_sa', 'db2'):
        with engine.begin() as conn:
            # Query helpers
            def _fetchone(sql: str):
                try:
                    return conn.exec_driver_sql(sql).first()
                except Exception:
                    return None

            # Safety: never drop a tablespace if it contains any user table with rows
            def _tablespace_has_tables_with_rows(ts_name: str) -> bool:
                """
                Returns True if the tablespace contains any non-system table that has at least one row.
                On any error (catalog differences, permissions, etc.), errs on the safe side and returns True.
                """
                try:
                    rows = conn.exec_driver_sql(
                        'SELECT t.TABSCHEMA, t.TABNAME '
                        'FROM SYSCAT.TABLES t '
                        'JOIN SYSCAT.TABLESPACES s ON t.TBSPACEID = s.TBSPACEID '
                        "WHERE s.TBSPACE = ? AND t.TYPE = 'T'",
                        (ts_name,),
                    ).fetchall()
                except Exception:
                    # If we cannot enumerate reliably, assume there is data to avoid any risk
                    return True
                for sch, tab in rows or []:
                    sch = (sch or '').strip()
                    tab = (tab or '').strip()
                    # Skip system schemas defensively
                    if sch.upper().startswith('SYS'):
                        continue
                    try:
                        # Use catalog cardinality; if >0, consider it populated
                        card_row = conn.exec_driver_sql(
                            'SELECT COALESCE(CARD, 0) FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = ?',
                            (sch, tab),
                        ).first()
                        if card_row and int(card_row[0] or 0) > 0:
                            return True
                    except Exception:
                        # If probing fails for any table, err on the safe side
                        return True
                return False

            # 1) Ensure TS/BP (handle TS first to allow dropping BP if needed)
            ts = _fetchone(
                "SELECT COUNT(*), COALESCE(MAX(PAGESIZE),0) FROM SYSCAT.TABLESPACES WHERE TBSPACE='TS32K'"
            )
            ts_count = int(ts[0]) if ts else 0
            ts_pg = int(ts[1]) if ts else 0
            bp = _fetchone(
                "SELECT COUNT(*), COALESCE(MAX(PAGESIZE),0) FROM SYSCAT.BUFFERPOOLS WHERE BPNAME='BP32K'"
            )
            bp_count = int(bp[0]) if bp else 0
            bp_pg = int(bp[1]) if bp else 0

            # Drop TS if wrong pagesize (only if it contains no user tables with rows)
            if ts_count > 0 and ts_pg != 32768:
                unsafe = True
                try:
                    unsafe = _tablespace_has_tables_with_rows('TS32K')
                except Exception:
                    unsafe = True
                if not unsafe:
                    try:
                        conn.exec_driver_sql('DROP TABLESPACE TS32K')
                    except Exception as exc:
                        _logging.getLogger(__name__).debug(
                            'DROP TABLESPACE TS32K failed; continuing: %s', exc
                        )
                    ts_count = 0
                else:
                    # Skip dropping to avoid any chance of data loss
                    pass

            # Drop BP if wrong pagesize (after TS is gone)
            if bp_count > 0 and bp_pg != 32768 and ts_count == 0:
                try:
                    conn.exec_driver_sql('DROP BUFFERPOOL BP32K')
                except Exception as exc:
                    _logging.getLogger(__name__).debug(
                        'DROP BUFFERPOOL BP32K failed; continuing: %s', exc
                    )
                bp_count = 0

            # Create BP if missing
            if bp_count == 0:
                try:
                    conn.exec_driver_sql('CREATE BUFFERPOOL BP32K SIZE 1000 PAGESIZE 32K')
                except Exception as exc:
                    _logging.getLogger(__name__).debug(
                        'CREATE BUFFERPOOL BP32K failed; continuing: %s', exc
                    )

            # Create TS if missing
            ts = _fetchone("SELECT COUNT(*) FROM SYSCAT.TABLESPACES WHERE TBSPACE='TS32K'")
            ts_count = int(ts[0]) if ts else 0
            if ts_count == 0:
                try:
                    conn.exec_driver_sql(
                        'CREATE TABLESPACE TS32K PAGESIZE 32K MANAGED BY AUTOMATIC STORAGE EXTENTSIZE 32 BUFFERPOOL BP32K'
                    )
                except Exception as exc:
                    _logging.getLogger(__name__).debug(
                        'CREATE TABLESPACE TS32K failed; continuing: %s', exc
                    )
            else:
                # Try to point at BP32K
                try:
                    conn.exec_driver_sql('ALTER TABLESPACE TS32K BUFFERPOOL BP32K')
                except Exception as exc:
                    _logging.getLogger(__name__).debug(
                        'ALTER TABLESPACE TS32K BUFFERPOOL BP32K failed; continuing: %s', exc
                    )

            # 2) Schema CRISOP
            try:
                conn.exec_driver_sql('CREATE SCHEMA CRISOP')
            except Exception as exc:
                _logging.getLogger(__name__).debug(
                    'CREATE SCHEMA CRISOP failed or exists; continuing: %s', exc
                )

            # 3) Tables in CRISOP (create if missing)
            # BLOCKED_ADDRESSES
            try:
                conn.exec_driver_sql(
                    'CREATE TABLE CRISOP.BLOCKED_ADDRESSES ('
                    '  ID INTEGER GENERATED ALWAYS AS IDENTITY (START WITH 1, INCREMENT BY 1) PRIMARY KEY, '
                    '  PATTERN VARCHAR(255) NOT NULL, '
                    '  IS_REGEX SMALLINT NOT NULL DEFAULT 0, '
                    '  TEST_MODE SMALLINT NOT NULL DEFAULT 1, '
                    '  UPDATED_AT TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP '
                    ') IN TS32K INDEX IN TS32K'
                )
            except Exception as exc:
                _logging.getLogger(__name__).debug(
                    'CREATE TABLE CRISOP.BLOCKED_ADDRESSES skipped/failed; continuing: %s', exc
                )

            # CRIS_PROPS
            try:
                conn.exec_driver_sql(
                    'CREATE TABLE CRISOP.CRIS_PROPS ('
                    '  KEY       VARCHAR(1024 OCTETS) NOT NULL, '
                    '  VALUE     VARCHAR(1024 OCTETS), '
                    '  UPDATE_TS TIMESTAMP(6), '
                    '  CONSTRAINT XPKCRISPROPS PRIMARY KEY (KEY)'
                    ') IN TS32K INDEX IN TS32K'
                )
            except Exception as exc:
                _logging.getLogger(__name__).debug(
                    'CREATE TABLE CRISOP.CRIS_PROPS skipped/failed; continuing: %s', exc
                )

            # 4) Trigger to keep UPDATED_AT fresh
            try:
                conn.exec_driver_sql(
                    'CREATE OR REPLACE TRIGGER CRISOP.TRG_BLOCKED_ADDRESSES_SET_UPDATED\n'
                    'NO CASCADE BEFORE UPDATE ON CRISOP.BLOCKED_ADDRESSES\n'
                    'REFERENCING NEW AS N\n'
                    'FOR EACH ROW\n'
                    'SET N.UPDATED_AT = CURRENT TIMESTAMP'
                )
            except Exception as exc:
                _logging.getLogger(__name__).debug(
                    'CREATE OR REPLACE TRIGGER skipped/failed; continuing: %s', exc
                )

            # 5) Aliases in CURRENT SCHEMA for unqualified access
            try:
                conn.exec_driver_sql('DROP ALIAS BLOCKED_ADDRESSES')
            except Exception as exc:
                _logging.getLogger(__name__).debug(
                    'DROP ALIAS BLOCKED_ADDRESSES failed; continuing: %s', exc
                )
            try:
                conn.exec_driver_sql('CREATE ALIAS BLOCKED_ADDRESSES FOR CRISOP.BLOCKED_ADDRESSES')
            except Exception as exc:
                _logging.getLogger(__name__).debug(
                    'CREATE ALIAS BLOCKED_ADDRESSES failed; continuing: %s', exc
                )
            try:
                conn.exec_driver_sql('DROP ALIAS CRIS_PROPS')
            except Exception as exc:
                _logging.getLogger(__name__).debug(
                    'DROP ALIAS CRIS_PROPS failed; continuing: %s', exc
                )
            try:
                conn.exec_driver_sql('CREATE ALIAS CRIS_PROPS FOR CRISOP.CRIS_PROPS')
            except Exception as exc:
                _logging.getLogger(__name__).debug(
                    'CREATE ALIAS CRIS_PROPS failed; continuing: %s', exc
                )
        return

    # Generic (non-Db2) fallback: Create or verify tables with a robust, idempotent approach
    bt = get_blocked_table()
    pt = get_props_table()

    def _safe_create(table) -> None:
        try:
            # Force create without pre-checks; swallow "already exists" errors
            table.create(engine, checkfirst=False)
        except Exception as exc:  # pragma: no cover - dialect/driver specific
            msg = str(exc).lower()
            # Common patterns across backends for existing table
            if (
                ('already exists' in msg)
                or ('sql0601n' in msg)
                or ('object to be created is identical to the existing name' in msg)
            ):
                return
            # As a fallback, try create with checkfirst (may succeed on some dialects)
            try:
                table.create(engine, checkfirst=True)
                return
            except Exception:
                raise

    # Create tables via SQLAlchemy for other dialects
    _safe_create(bt)
    _safe_create(pt)

    # Migration: ensure test_mode exists (generic fallback path only)
    try:
        cols = insp.get_columns('blocked_addresses') or []
        existing = {c.get('name', '').lower() for c in cols}
    except Exception:
        existing = set()
    if 'test_mode' not in existing:
        with engine.begin() as conn:
            try:
                conn.exec_driver_sql(
                    'ALTER TABLE blocked_addresses ADD COLUMN test_mode BOOLEAN NOT NULL DEFAULT TRUE'
                )
            except Exception:
                conn.exec_driver_sql(
                    'ALTER TABLE blocked_addresses ADD COLUMN test_mode SMALLINT NOT NULL DEFAULT 1'
                )
            # Normalize legacy NULLs
            try:
                conn.exec_driver_sql(
                    'UPDATE blocked_addresses SET test_mode = 1 WHERE test_mode IS NULL'
                )
            except Exception:
                try:
                    conn.exec_driver_sql(
                        'UPDATE blocked_addresses SET test_mode = TRUE WHERE test_mode IS NULL'
                    )
                except Exception as exc:
                    import logging as _lg

                    _lg.getLogger(__name__).debug(
                        'Could not normalize legacy NULL test_mode values; continuing: %s', exc
                    )

    # No extra trigger work for generic dialects


__all__ = ['init_db']
