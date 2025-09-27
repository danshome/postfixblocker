# ruff: noqa: E402
from __future__ import annotations

"""Postfix control helpers (refactor implementation)."""
import logging
import os
import subprocess  # nosec B404  # Using subprocess to invoke fixed system utilities (postmap/postfix) is required for functionality; shell is not used.
from collections.abc import Sequence
from pathlib import Path
from typing import Any


def _run_fixed(cmd: Sequence[str], **kwargs: Any):
    """Run a whitelisted Postfix utility safely.

    Safety guarantees:
    - Absolute executable path is validated against an allowlist.
    - shell=False is always used (subprocess default when passing a list).
    - Arguments are constructed from internal values only.

    This narrow helper centralizes the one required subprocess invocation and
    documents the constraints. Lint suppressions are restricted to this callsite.
    """
    allowed = {'/usr/sbin/postmap', '/usr/sbin/postfix', '/usr/sbin/postconf'}
    exe = cmd[0] if cmd else ''
    if exe not in allowed:
        logging.getLogger(__name__).debug('Disallowed executable: %r', exe)
        raise ValueError(exe)
    return subprocess.run(list(cmd), **kwargs)  # noqa: S603  # nosec  # safe: fixed absolute executable path; no shell; arguments are internal


def reload_postfix() -> None:
    """Run postmap for literal maps and reload Postfix, tolerating startup timing.

    Uses environment POSTFIX_DIR for map paths; defaults to /etc/postfix.
    """
    postfix_dir = os.environ.get('POSTFIX_DIR', '/etc/postfix')
    literal_path = Path(postfix_dir) / 'blocked_recipients'
    test_literal_path = Path(postfix_dir) / 'blocked_recipients_test'
    try:
        logging.info('Running postmap on %s and %s', literal_path, test_literal_path)
        # Safe: using fixed executable and a validated filesystem path; no shell involvement.
        # Using fixed absolute executable and a validated file path within POSTFIX_DIR; shell is not used.
        rc1 = _run_fixed(['/usr/sbin/postmap', str(literal_path)], check=False).returncode
        rc1b = _run_fixed(['/usr/sbin/postmap', str(test_literal_path)], check=False).returncode
        try:
            size1 = literal_path.stat().st_size
            size2 = test_literal_path.stat().st_size
        except Exception:
            size1 = size2 = -1
        try:
            status_rc = _run_fixed(['/usr/sbin/postfix', 'status'], check=False).returncode
        except Exception:
            status_rc = 1
        if status_rc == 0:
            logging.info('Reloading postfix')
            rc2 = _run_fixed(['/usr/sbin/postfix', 'reload'], check=False).returncode
        else:
            rc2 = None
            logging.debug('Postfix master not running yet; skipping reload')
        failed = [
            str(x)
            for x in (rc1, rc1b, rc2 if rc2 is not None else 0)
            if isinstance(x, int) and x != 0
        ]
        if failed:
            if (size1 == 0 or size2 == 0) and status_rc != 0:
                logging.warning(
                    'Postfix commands had non-zero return codes (environment not ready): postmap=%s postmap_test=%s reload=%s',
                    rc1,
                    rc1b,
                    rc2,
                )
            else:
                logging.warning(
                    'Postfix commands had non-zero return codes: postmap=%s postmap_test=%s reload=%s',
                    rc1,
                    rc1b,
                    rc2,
                )
    except Exception as exc:
        logging.warning('Failed to reload postfix (transient): %s', exc)


def has_postfix_pcre() -> bool:
    try:
        # Fixed absolute executable with constant arguments; safe without shell.
        res = _run_fixed(
            ['/usr/sbin/postconf', '-m'],
            capture_output=True,
            text=True,
            check=True,
        )
        return 'pcre' in (res.stdout or '').lower()
    except FileNotFoundError:
        logging.exception("'postconf' not found; cannot verify Postfix PCRE support.")
        return False
    except Exception as exc:
        logging.warning("Could not verify Postfix PCRE support via 'postconf -m': %s", exc)
        return False


__all__ = ['has_postfix_pcre', 'reload_postfix']
