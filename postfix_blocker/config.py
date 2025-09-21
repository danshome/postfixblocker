from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # Core
    db_url: str
    check_interval: float
    postfix_dir: str
    pid_file: str

    # Logging
    api_log_file: str | None
    api_log_level: str
    blocker_log_file: str | None
    blocker_log_level: str


def load_config(env: Mapping[str, str] | None = None) -> Config:
    e = os.environ if env is None else env
    return Config(
        # DB2 is the only supported backend.
        db_url=e.get('BLOCKER_DB_URL', 'ibm_db_sa://db2inst1:blockerpass@db2:50000/BLOCKER'),
        check_interval=float(e.get('BLOCKER_INTERVAL', '5')),
        postfix_dir=e.get('POSTFIX_DIR', '/etc/postfix'),
        pid_file=e.get('BLOCKER_PID_FILE', '/var/run/postfix-blocker/blocker.pid'),
        api_log_file=e.get('API_LOG_FILE'),
        api_log_level=e.get('API_LOG_LEVEL', 'INFO'),
        blocker_log_file=e.get('BLOCKER_LOG_FILE'),
        blocker_log_level=e.get('BLOCKER_LOG_LEVEL', 'INFO'),
    )
