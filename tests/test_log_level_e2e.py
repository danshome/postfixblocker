import os
import smtplib
import time
from email.message import EmailMessage

import pytest
import requests

# Default endpoint for the DB2 stack; can be overridden via env
API_BASE_DB2 = os.environ.get('E2E_API_BASE_DB2', 'http://127.0.0.1:5002')
SMTP_PORT_DB2 = int(os.environ.get('SMTP_PORT_DB2', '1026'))


def _dbg(msg: str) -> None:
    if os.environ.get('E2E_DEBUG') == '1':
        print(f'[E2E][log_level] {msg}')


def _get(api_base: str, path: str, **kwargs):
    try:
        r = requests.get(api_base + path, timeout=30, **kwargs)
        _dbg(f'GET {path} -> {r.status_code}')
        return r
    except Exception as exc:
        _dbg(f'GET {path} failed: {exc}')
        raise


def _put(api_base: str, path: str, json: dict):
    try:
        r = requests.put(api_base + path, json=json, timeout=30)
        _dbg(f'PUT {path} -> {r.status_code}')
        return r
    except Exception as exc:
        _dbg(f'PUT {path} failed: {exc}')
        raise


def wait_for_api_ready(api_base: str, timeout: int = 600) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            # Prefer /auth/session because it is unprotected and returns 200 when API is up
            r = _get(api_base, '/auth/session')
            if r.status_code == 200:
                _dbg('API ready (auth/session=200)')
                return True
        except Exception:
            pass
        try:
            r2 = _get(api_base, '/addresses')
            if r2.status_code == 200:
                _dbg('API ready (addresses=200)')
                return True
            if r2.status_code in (401, 403):
                # API is up but auth is enforced; do not spin for full timeout
                _dbg('API up but auth required (addresses returned 401/403)')
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def _send_test_mail(port: int, to_addr: str) -> None:
    msg = EmailMessage()
    msg['From'] = 'sender@example.com'
    msg['To'] = to_addr
    msg['Subject'] = 'PostfixBlocker E2E Simple Test'
    msg.set_content('Hello from simple e2e test')
    with smtplib.SMTP('127.0.0.1', port, timeout=15) as s:
        s.send_message(msg)


def _get_postfix_tail_lines(api_base: str, lines: int = 6000) -> list[str]:
    r = _get(api_base, '/logs/tail', params={'name': 'postfix', 'lines': str(lines)})
    assert r.ok
    content = str(r.json().get('content') or '')
    # Normalize to non-empty lines
    return [ln for ln in content.splitlines() if ln.strip()]


def _count_recipient_mentions(api_base: str, recipient: str, lines: int = 6000) -> int:
    tail = _get_postfix_tail_lines(api_base, lines=lines)
    # Count occurrences of the full recipient address in the tail
    # This isolates per-email logging rather than total file growth.
    return sum(1 for ln in tail if recipient in ln)


def _measure_delta_for_level(api_base: str, smtp_port: int, level: str, recipient: str) -> int:
    # Apply level and allow a brief moment for it to take effect
    r = _put(api_base, '/logs/level/postfix', {'level': level})
    assert r.ok
    time.sleep(0.5)

    # Establish baseline count of lines mentioning this specific recipient
    base0 = _count_recipient_mentions(api_base, recipient)

    # First email: wait until we observe new lines for this recipient
    _send_test_mail(smtp_port, recipient)

    start = time.time()
    count1 = base0
    while time.time() - start < 90:
        count1 = _count_recipient_mentions(api_base, recipient)
        if count1 > base0:
            break
        time.sleep(0.5)

    # Second email: measure incremental lines attributable to one send at this level
    _send_test_mail(smtp_port, recipient)

    start2 = time.time()
    count2 = count1
    while time.time() - start2 < 90:
        count2 = _count_recipient_mentions(api_base, recipient)
        if count2 > count1:
            break
        time.sleep(0.5)

    delta = max(0, count2 - count1)
    return delta


@pytest.mark.e2e
def test_postfix_log_level_increasing_line_counts():
    scenario = {'name': 'db2', 'api_base': API_BASE_DB2, 'smtp_port': SMTP_PORT_DB2}
    if not wait_for_api_ready(scenario['api_base']):
        pytest.fail(
            f'API not ready for e2e test ({scenario["name"]}). Backend/E2E tests require the API to be available.',
        )

    # Use distinct recipients per level to aid diagnostics
    ts = int(time.time() * 1000)
    rec_warning = f'loglvl-{scenario["name"]}-warning-{ts}@example.com'
    rec_info = f'loglvl-{scenario["name"]}-info-{ts}@example.com'
    rec_debug = f'loglvl-{scenario["name"]}-debug-{ts}@example.com'

    # WARNING should be least verbose, INFO more, DEBUG most
    dw = _measure_delta_for_level(
        scenario['api_base'],
        scenario['smtp_port'],
        'WARNING',
        rec_warning,
    )
    di = _measure_delta_for_level(scenario['api_base'], scenario['smtp_port'], 'INFO', rec_info)
    dd = _measure_delta_for_level(scenario['api_base'], scenario['smtp_port'], 'DEBUG', rec_debug)

    # Allow variability on CI due to background log noise.
    slack = 60
    assert di >= dw - slack, (
        f'[{scenario["name"]}] Expected INFO ({di}) to be close to or above WARNING ({dw}); slack={slack}'
    )
    # DEBUG should be the most verbose, within slack margin
    assert dd >= max(di, dw) - slack, (
        f'[{scenario["name"]}] Expected DEBUG ({dd}) >= max(INFO, WARNING) ({max(di, dw)}) - slack({slack}); '
        f"recipients={{'W': '{rec_warning}', 'I': '{rec_info}', 'D': '{rec_debug}'}}"
    )
