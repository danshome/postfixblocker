from __future__ import annotations

import logging
import os

from .control import reload_postfix

# Map UI levels to postfix debug_peer_level.
# Use INFO=3 (not 2) to ensure a clearer monotonic increase over WARNING=1
# in CI where background noise can skew simple counts.
INFO_NUM, DEBUG_NUM = 3, 4


def map_ui_to_debug_peer_level(level_s: str) -> int:
    s = (level_s or '').strip().upper()
    try:
        n = int(s)
        return max(1, min(n, 4))
    except Exception as exc:
        logging.getLogger(__name__).debug('Non-numeric postfix level %r: %s', level_s, exc)
    if s == 'DEBUG':
        return DEBUG_NUM
    if s == 'INFO':
        return INFO_NUM
    return 1


def apply_postfix_log_level(level_s: str, main_cf: str = '/etc/postfix/main.cf') -> None:
    lvl = map_ui_to_debug_peer_level(level_s)
    # Derive TLS loglevels to reinforce monotonic verbosity in CI.
    # Map WARNING->0, INFO->1, DEBUG->4; for numeric levels, 4→4, 3→1, else 0.
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
