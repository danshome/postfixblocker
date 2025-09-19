"""Utilities for applying Postfix log-level changes.

Purpose
-------
Provide a small, focused API to:
- Map UI/API log-level inputs (e.g., "WARNING", "INFO", "DEBUG" or numeric strings)
  to Postfix-compatible values via map_ui_to_debug_peer_level.
- Persist those values to /etc/postfix/main.cf (debug_peer_level, debug_peer_list,
  smtp_tls_loglevel, smtpd_tls_loglevel) and reload Postfix via apply_postfix_log_level.
- Resolve the current mail log path across distros via resolve_mail_log_path.

Note
----
This module contains no test-specific behavior and does not schedule background
SMTP activity. Tests should verify observability on their own without requiring
side effects from this module.

Public API
----------
- map_ui_to_debug_peer_level(level_s: str) -> int
- apply_postfix_log_level(level_s: str, main_cf: str = '/etc/postfix/main.cf') -> None
- resolve_mail_log_path() -> str
"""

from __future__ import annotations

import logging
import os

from .control import reload_postfix

# Map UI levels to postfix debug_peer_level.
# Set INFO lower than DEBUG to guarantee ordering. DEBUG is intentionally 10
# to maximize verbosity separation; some Postfix builds may accept >4.
INFO_NUM, DEBUG_NUM = 2, 10


def map_ui_to_debug_peer_level(level_s: str) -> int:
    """Map a UI/API level string to a Postfix debug_peer_level integer.

    Behavior:
    - Symbolic names:
      - "WARNING" (or anything unknown) → 1
      - "INFO" → 2
      - "DEBUG" → 10 (for higher verbosity on builds that support >4)
    - Numeric strings are respected but capped to 4 and floored to 1.

    Args:
        level_s: Level name or numeric string.

    Returns:
        An integer suitable for Postfix main.cf debug_peer_level.
    """
    s = (level_s or '').strip().upper()
    try:
        n = int(s)
        # Numeric input: respect caller but cap to Postfix's typical max (4)
        # to avoid accidental invalid settings via API.
        return max(1, min(int(n), 4))
    except Exception as exc:
        logging.getLogger(__name__).debug('Non-numeric postfix level %r: %s', level_s, exc)
        if s == 'DEBUG':
            # For DEBUG specifically, return 10 to try higher verbosity in Postfix
            # environments that support it.
            return DEBUG_NUM
        if s == 'INFO':
            return INFO_NUM
        return 1


def apply_postfix_log_level(level_s: str, main_cf: str = '/etc/postfix/main.cf') -> None:
    """Persist the requested log verbosity to Postfix and reload it.

    This updates these main.cf settings (creating them if absent):
      - debug_peer_level = <mapped value>
      - debug_peer_list = 0.0.0.0/0  (enable for all peers)
      - smtp_tls_loglevel = <derived from level>
      - smtpd_tls_loglevel = <derived from level>

    TLS loglevel derivation:
      - WARNING → 0, INFO → 1, DEBUG → 4
      - numeric strings: >=4→4, >=3→1, else 0

    Args:
        level_s: User-provided level (symbolic or numeric string).
        main_cf: Path to Postfix main.cf to modify.

    Note:
        A best-effort reload is attempted via postfix.control.reload_postfix();
        failures are logged as warnings and do not raise.
    """
    lvl = map_ui_to_debug_peer_level(level_s)
    # Derive TLS loglevels. Map WARNING->0, INFO->1, DEBUG->4; for numeric levels,
    # 4→4, 3→1, else 0.
    s = (level_s or '').strip().upper()
    if s == 'DEBUG':
        tls_lvl = 4
    elif s == 'INFO':
        tls_lvl = 1
    else:
        try:
            n = int(s)
            if n >= 4:
                tls_lvl = 4
            elif n >= 3:
                tls_lvl = 1
            else:
                tls_lvl = 0
        except Exception:
            tls_lvl = 0

    lines: list[str] = []
    if os.path.exists(main_cf):
        with open(main_cf, encoding='utf-8') as f:
            lines = f.read().splitlines()
    out: list[str] = []
    found_lvl = False
    found_list = False
    found_smtp_tls = False
    found_smtpd_tls = False
    for line in lines:
        sline = line.strip()
        if sline.startswith('debug_peer_level'):
            out.append(f'debug_peer_level = {lvl}')
            found_lvl = True
        elif sline.startswith('debug_peer_list'):
            out.append('debug_peer_list = 0.0.0.0/0')
            found_list = True
        elif sline.startswith('smtp_tls_loglevel'):
            out.append(f'smtp_tls_loglevel = {tls_lvl}')
            found_smtp_tls = True
        elif sline.startswith('smtpd_tls_loglevel'):
            out.append(f'smtpd_tls_loglevel = {tls_lvl}')
            found_smtpd_tls = True
        else:
            out.append(line)
    if not found_lvl:
        out.append(f'debug_peer_level = {lvl}')
    if not found_list:
        out.append('debug_peer_list = 0.0.0.0/0')
    if not found_smtp_tls:
        out.append(f'smtp_tls_loglevel = {tls_lvl}')
    if not found_smtpd_tls:
        out.append(f'smtpd_tls_loglevel = {tls_lvl}')

    with open(main_cf, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')
    logging.getLogger(__name__).debug(
        'Updated main.cf debug_peer_level=%s tls_loglevel=%s from %s', lvl, tls_lvl, level_s
    )
    try:
        reload_postfix()
    except Exception as exc:
        logging.getLogger(__name__).warning('Postfix reload failed after level change: %s', exc)


def resolve_mail_log_path() -> str:
    """Return the best-known mail log path for the running system.

    Order of resolution:
      1) MAIL_LOG_FILE env var if it exists on disk
      2) /var/log/maillog if present and non-empty
      3) /var/log/mail.log if present and non-empty
      4) Fallback to "/var/log/maillog" if checks fail

    Returns:
        Absolute path to a mail log file (may not yet exist in dev/CI).
    """
    # Allow override via environment for CI/container differences.
    env_override = os.environ.get('MAIL_LOG_FILE')
    if env_override:
        try:
            if os.path.exists(env_override):
                return env_override
        except Exception as exc:
            logging.getLogger(__name__).debug('MAIL_LOG_FILE check failed: %s', exc)
    preferred = '/var/log/maillog'
    fallback = '/var/log/mail.log'
    try:
        if os.path.exists(preferred) and os.path.getsize(preferred) > 0:
            return preferred
        if os.path.exists(fallback) and os.path.getsize(fallback) > 0:
            return fallback
    except Exception as exc:
        logging.getLogger(__name__).debug('resolve_mail_log_path stat failed: %s', exc)
        # Best-effort; return preferred by default
    return preferred


__all__ = ['map_ui_to_debug_peer_level', 'apply_postfix_log_level', 'resolve_mail_log_path']
