from __future__ import annotations

import os
import time


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except Exception:
        return default


def _is_db2_url(url: str) -> bool:
    u = url.lower()
    return 'ibm_db' in u or u.startswith('db2+') or u.startswith('ibm_db_sa://')


def wait_for_db_url(url: str, total_timeout: int | None = None) -> bool:
    """Wait for a database URL to accept connections.

    Returns True if ready, False if timeout or SQLAlchemy missing.
    """
    try:
        from sqlalchemy import create_engine, text  # type: ignore
    except Exception:
        return False

    is_db2 = _is_db2_url(url)
    if total_timeout is None:
        total_timeout = _env_int(
            'BACKEND_WAIT_TIMEOUT_DB2' if is_db2 else 'BACKEND_WAIT_TIMEOUT_PG',
            240 if is_db2 else 60,
        )

    probe_sql = 'SELECT 1 FROM SYSIBM.SYSDUMMY1' if is_db2 else 'SELECT 1'
    deadline = time.time() + total_timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            engine = create_engine(url)
            with engine.connect() as conn:
                conn.execute(text(probe_sql))  # type: ignore
            return True
        except Exception:  # pragma: no cover - timing dependent
            time.sleep(min(5, 0.5 * attempt))
    # Timed out
    return False


def wait_for_smtp(host: str, port: int, total_timeout: int = 60) -> bool:
    import socket

    deadline = time.time() + total_timeout
    while time.time() < deadline:
        s = socket.socket()
        s.settimeout(2)
        try:
            s.connect((host, port))
            s.close()
            return True
        except Exception:  # pragma: no cover - timing dependent
            time.sleep(1)
        finally:
            try:
                s.close()
            except Exception:
                pass
    return False
