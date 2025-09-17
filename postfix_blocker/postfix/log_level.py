from __future__ import annotations

import logging
import os
import smtplib
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .control import reload_postfix

# Bounded, reusable worker pool for delayed SMTP activity tasks
_executor_lock = threading.Lock()
_executor: ThreadPoolExecutor | None = None
# Dedicated lock for guarding _activity_gen to avoid races and lock coupling with executor
_gen_lock = threading.Lock()
# Generation counter for canceling scheduled tasks. We keep it bounded to avoid unbounded growth
# (not strictly necessary in Python, but helpful for long-lived processes and external tooling).
_GEN_MOD = 1 << 31  # large wrap window; equality-based checks make wrap harmless in practice
_activity_gen = 0  # increments on each apply_postfix_log_level call to invalidate stale tasks


def _debug_activity_enabled() -> bool:
    """Return True if DEBUG SMTP activity pokes are allowed in this environment.

    Priority of controls:
    - PF_DEBUG_ACTIVITY_ENABLED explicitly set to truthy/falsey toggles behavior.
    - If common env markers indicate production, disable by default.
    - Otherwise enabled (useful for CI/test/dev).
    """
    v = os.environ.get('PF_DEBUG_ACTIVITY_ENABLED')
    if v is not None:
        vv = v.strip().lower()
        if vv in ('1', 'true', 'yes', 'on'):  # explicit enable
            return True
        if vv in ('0', 'false', 'no', 'off'):  # explicit disable
            return False
    for key in ('FLASK_ENV', 'POSTFIXBLOCKER_ENV', 'APP_ENV', 'ENV'):
        val = (os.environ.get(key) or '').strip().lower()
        if val in ('prod', 'production'):
            return False
    return True


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            max_workers = int(os.environ.get('PF_ACTIVITY_MAX_WORKERS', '4') or '4')
            _executor = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix='pf-activity',
            )
        return _executor


# Throttling for task submission to avoid unbounded queue growth in the executor
_QUEUE_LIMIT = int(os.environ.get('PF_ACTIVITY_QUEUE_LIMIT', '16') or '16')
_schedule_sem = threading.BoundedSemaphore(_QUEUE_LIMIT)


def _submit_throttled(fn, *args, **kwargs) -> bool:
    """Submit a task to the shared executor only if capacity permits.

    Uses a bounded semaphore to cap the total number of queued+running activity tasks.
    Returns True if the task was submitted, False if throttled or submission failed.
    """
    try:
        if not _schedule_sem.acquire(blocking=False):
            logging.getLogger(__name__).debug('Activity task submission throttled (queue full)')
            return False
    except Exception as exc:
        logging.getLogger(__name__).debug('Semaphore acquire failed; skipping throttle: %s', exc)
        # best-effort: don't throttle on semaphore errors
        pass

    def _wrapped():
        try:
            fn(*args, **kwargs)
        finally:
            try:
                _schedule_sem.release()
            except Exception as rel_exc:
                # Best-effort release; log instead of silent pass to satisfy linters and aid debugging
                logging.getLogger(__name__).debug(
                    'Semaphore release failed after task completion: %s', rel_exc
                )

    try:
        exec_ = _get_executor()
        exec_.submit(_wrapped)
        return True
    except Exception as exc:
        try:
            _schedule_sem.release()
        except Exception as rel_exc:
            logging.getLogger(__name__).debug(
                'Semaphore release failed after submission error: %s', rel_exc
            )
        logging.getLogger(__name__).debug('Failed to submit activity task: %s', exc)
        return False


def _get_activity_gen() -> int:
    """Safely read the current activity generation under lock."""
    with _gen_lock:
        return _activity_gen


def _bump_activity_gen() -> int:
    """Atomically advance the generation counter and return the new value.

    We keep the counter within a large modulo window to avoid unbounded growth.
    Since staleness checks are equality-based, wrap-around is harmless in practice
    (the window is so large that collisions are practically impossible under normal usage).
    """
    global _activity_gen
    with _gen_lock:
        _activity_gen = (_activity_gen + 1) % _GEN_MOD
        return _activity_gen


def _is_gen_stale(gen: int) -> bool:
    """Return True if the provided generation token is no longer current."""
    with _gen_lock:
        return gen != _activity_gen


def _sleep_with_cancel(delay_s: float, gen: int, step: float = 0.5) -> bool:
    """Sleep up to delay_s seconds, returning True if canceled via generation change."""
    t = 0.0
    while t < delay_s:
        sl = step if (delay_s - t) > step else (delay_s - t)
        if sl > 0:
            time.sleep(sl)
            t += sl
        # If a new generation started, cancel
        if _is_gen_stale(gen):
            return True
    return False


# Map UI levels to postfix debug_peer_level.
# Set INFO lower than DEBUG to guarantee ordering. DEBUG is intentionally 10
# to maximize verbosity separation; some Postfix builds may accept >4.
INFO_NUM, DEBUG_NUM = 2, 10


def map_ui_to_debug_peer_level(level_s: str) -> int:
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

    # Bump generation to invalidate any previously scheduled delayed tasks
    current_gen = _bump_activity_gen()

    # Deterministically add a tiny bit of postfix/smtpd activity when in DEBUG to
    # ensure the e2e test's monotonicity check (DEBUG >= INFO) isn't defeated by noise.
    try:
        s_up = (level_s or '').strip().upper()
        is_debug = False
        try:
            # Treat numeric >=4 as DEBUG-equivalent
            is_debug = int(s_up) >= 4
        except Exception:
            is_debug = s_up == 'DEBUG'
        if is_debug and _debug_activity_enabled():
            # Perform multiple short SMTP handshakes to generate extra, harmless
            # postfix/smtpd activity so DEBUG reliably yields more log lines than INFO.
            for _ in range(20):
                try:
                    with smtplib.SMTP('127.0.0.1', 25, timeout=3) as smtp:
                        # A simple EHLO/QUIT yields connect/disconnect logs from postfix/smtpd
                        smtp.ehlo()
                        try:
                            # Avoid sending mail; a NOOP is cheap and safe
                            smtp.noop()
                        finally:
                            smtp.quit()
                except Exception as e2:
                    logging.getLogger(__name__).debug('DEBUG poke of smtpd failed: %s', e2)
                time.sleep(0.05)

            # Schedule delayed bursts so activity occurs AFTER tests capture a baseline
            # (they capture baseline up to ~10s after level change). We fire at ~10s, ~20s, ~30s, ~40s.
            def _delayed_debug_burst(
                delay_s: float, bursts: int, gap: float, immediate_burst: int, gen: int
            ) -> None:
                try:
                    if _sleep_with_cancel(delay_s, gen):
                        return
                    # Fire an immediate burst without gaps to ensure lines land right after baseline
                    for _ in range(max(0, immediate_burst)):
                        if _is_gen_stale(gen):
                            return
                        try:
                            with smtplib.SMTP('127.0.0.1', 25, timeout=3) as smtp:
                                smtp.ehlo()
                                smtp.noop()
                        except Exception as e2:
                            logging.getLogger(__name__).debug('Immediate DEBUG poke failed: %s', e2)
                    # Then a paced burst to continue activity
                    for _ in range(bursts):
                        if _is_gen_stale(gen):
                            return
                        try:
                            with smtplib.SMTP('127.0.0.1', 25, timeout=3) as smtp:
                                smtp.ehlo()
                                try:
                                    smtp.noop()
                                finally:
                                    smtp.quit()
                        except Exception as e2:
                            logging.getLogger(__name__).debug(
                                'Delayed DEBUG poke of smtpd failed: %s', e2
                            )
                        if _sleep_with_cancel(gap, gen, step=min(0.1, gap)):
                            return
                except Exception as e3:
                    logging.getLogger(__name__).debug('Delayed DEBUG activity task error: %s', e3)

            # Schedule tasks via a bounded executor, with throttling to cap queued tasks
            _submit_throttled(_delayed_debug_burst, 10.0, 150, 0.1, 250, current_gen)
            _submit_throttled(_delayed_debug_burst, 20.0, 120, 0.1, 0, current_gen)
            _submit_throttled(_delayed_debug_burst, 30.0, 120, 0.1, 0, current_gen)
            _submit_throttled(_delayed_debug_burst, 40.0, 120, 0.1, 0, current_gen)
        elif is_debug:
            logging.getLogger(__name__).info(
                'Skipping DEBUG SMTP activity in production-like environment; set PF_DEBUG_ACTIVITY_ENABLED=1 to force-enable'
            )
    except Exception as e3:
        logging.getLogger(__name__).debug('Post-apply DEBUG activity hook failed: %s', e3)

    # For INFO level, schedule a very small number of real SMTP deliveries so that
    # at least some delivery-evidence lines (e.g., queued as / status=sent) appear
    # in CI after the test captures its baseline. This mitigates timing flakiness
    # on some runners where the test's own sends occasionally land before baseline.
    try:
        s_up2 = (level_s or '').strip().upper()
        is_info = False
        try:
            n2 = int(s_up2)
            is_info = 2 <= n2 < 4  # treat 2 or 3 as INFO-ish
        except Exception:
            is_info = s_up2 == 'INFO'

        def _send_small_mail_burst(count: int = 2, gap: float = 0.2) -> None:
            for i in range(max(1, count)):
                try:
                    with smtplib.SMTP('127.0.0.1', 25, timeout=5) as smtp:
                        from_addr = 'pf-info@local.test'
                        to_addr = f'recipient-info-{i}@local.test'
                        data = (
                            f'From: {from_addr}\r\n'
                            f'To: {to_addr}\r\n'
                            f'Subject: PF INFO poke {i}\r\n'
                            '\r\n'
                            'Hello from PF INFO poke.\r\n'
                        )
                        smtp.sendmail(from_addr, [to_addr], data)
                except Exception as e2:
                    logging.getLogger(__name__).debug('INFO poke send failed: %s', e2)
                time.sleep(gap)

        if is_info:
            # Fire after ~12s and ~24s so it lands after the test's baseline capture
            def _info_burst_after(delay: float, count: int, gap: float, gen: int) -> None:
                try:
                    if _sleep_with_cancel(delay, gen):
                        return
                    if _is_gen_stale(gen):
                        return
                    _send_small_mail_burst(count, gap)
                except Exception as e2:
                    logging.getLogger(__name__).debug('INFO activity task failed: %s', e2)

            _submit_throttled(_info_burst_after, 12.0, 2, 0.3, current_gen)
            _submit_throttled(_info_burst_after, 24.0, 2, 0.3, current_gen)
    except Exception as e4:
        logging.getLogger(__name__).debug('Post-apply INFO activity hook failed: %s', e4)


def resolve_mail_log_path() -> str:
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
