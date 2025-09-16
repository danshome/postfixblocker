from __future__ import annotations

import logging
import os

from .control import reload_postfix

INFO_NUM, DEBUG_NUM = 2, 4


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
    lines: list[str] = []
    if os.path.exists(main_cf):
        with open(main_cf, encoding='utf-8') as f:
            lines = f.read().splitlines()
    out: list[str] = []
    found_lvl = False
    found_list = False
    for line in lines:
        s = line.strip()
        if s.startswith('debug_peer_level'):
            out.append(f'debug_peer_level = {lvl}')
            found_lvl = True
        elif s.startswith('debug_peer_list'):
            out.append('debug_peer_list = 0.0.0.0/0')
            found_list = True
        else:
            out.append(line)
    if not found_lvl:
        out.append(f'debug_peer_level = {lvl}')
    if not found_list:
        out.append('debug_peer_list = 0.0.0.0/0')
    with open(main_cf, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')
    logging.getLogger(__name__).debug('Updated main.cf debug_peer_level=%s from %s', lvl, level_s)
    try:
        reload_postfix()
    except Exception as exc:
        logging.getLogger(__name__).warning('Postfix reload failed after level change: %s', exc)


def resolve_mail_log_path() -> str:
    preferred = '/var/log/maillog'
    fallback = '/var/log/mail.log'
    try:
        pref_exists = os.path.exists(preferred)
        fall_exists = os.path.exists(fallback)
        if pref_exists and not fall_exists:
            return preferred
        if fall_exists and not pref_exists:
            return fallback
        if pref_exists and fall_exists:
            # If both exist, choose the non-empty one; if both non-empty, choose newer mtime
            pref_size = os.path.getsize(preferred)
            fall_size = os.path.getsize(fallback)
            if pref_size == 0 and fall_size > 0:
                return fallback
            if fall_size == 0 and pref_size > 0:
                return preferred
            if pref_size > 0 and fall_size > 0:
                pref_mtime = os.path.getmtime(preferred)
                fall_mtime = os.path.getmtime(fallback)
                return preferred if pref_mtime >= fall_mtime else fallback
        # If we got here, either neither exists or both are empty; fall back to preferred
    except Exception as exc:
        logging.getLogger(__name__).debug('resolve_mail_log_path stat failed: %s', exc)
        # Best-effort; return preferred by default
    return preferred


__all__ = ['map_ui_to_debug_peer_level', 'apply_postfix_log_level', 'resolve_mail_log_path']
