# ruff: noqa: E402
from __future__ import annotations

"""Postfix control helpers (refactor implementation)."""
import logging
import os
import subprocess  # nosec B404


def reload_postfix() -> None:
    """Run postmap for literal maps and reload Postfix, tolerating startup timing.

    Uses environment POSTFIX_DIR for map paths; defaults to /etc/postfix.
    """
    postfix_dir = os.environ.get('POSTFIX_DIR', '/etc/postfix')
    literal_path = os.path.join(postfix_dir, 'blocked_recipients')
    test_literal_path = os.path.join(postfix_dir, 'blocked_recipients_test')
    try:
        logging.info('Running postmap on %s and %s', literal_path, test_literal_path)
        rc1 = subprocess.run(['/usr/sbin/postmap', literal_path], check=False).returncode  # nosec B603
        rc1b = subprocess.run(['/usr/sbin/postmap', test_literal_path], check=False).returncode  # nosec B603
        try:
            size1 = os.path.getsize(literal_path)
            size2 = os.path.getsize(test_literal_path)
        except Exception:
            size1 = size2 = -1
        try:
            status_rc = subprocess.run(['/usr/sbin/postfix', 'status'], check=False).returncode  # nosec B603
        except Exception:
            status_rc = 1
        if status_rc == 0:
            logging.info('Reloading postfix')
            rc2 = subprocess.run(['/usr/sbin/postfix', 'reload'], check=False).returncode  # nosec B603
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
        res = subprocess.run(
            ['/usr/sbin/postconf', '-m'], capture_output=True, text=True, check=True
        )  # nosec B603
        return 'pcre' in (res.stdout or '').lower()
    except FileNotFoundError:
        logging.error("'postconf' not found; cannot verify Postfix PCRE support.")
        return False
    except Exception as exc:
        logging.warning("Could not verify Postfix PCRE support via 'postconf -m': %s", exc)
        return False


__all__ = ['reload_postfix', 'has_postfix_pcre']
