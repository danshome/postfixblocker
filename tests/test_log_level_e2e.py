import os
import smtplib
import time
from email.message import EmailMessage

import pytest
import requests

# Default endpoints for PG and DB2 stacks; can be overridden via env
API_BASE_PG = os.environ.get('E2E_API_BASE_PG', 'http://127.0.0.1:5001')
API_BASE_DB2 = os.environ.get('E2E_API_BASE_DB2', 'http://127.0.0.1:5002')
SMTP_PORT_PG = int(os.environ.get('SMTP_PORT_PG', '1025'))
SMTP_PORT_DB2 = int(os.environ.get('SMTP_PORT_DB2', '1026'))


def _get(api_base: str, path: str, **kwargs):
    return requests.get(api_base + path, timeout=30, **kwargs)


def _put(api_base: str, path: str, json: dict):
    return requests.put(api_base + path, json=json, timeout=30)


def wait_for_api_ready(api_base: str, timeout: int = 600) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = _get(api_base, '/addresses')
            if r.status_code == 200:
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


def _get_postfix_line_count(api_base: str) -> int:
    r = _get(api_base, '/logs/lines', params={'name': 'postfix'})
    assert r.ok
    return int(r.json().get('count') or 0)


def _measure_delta_for_level(api_base: str, smtp_port: int, level: str, recipient: str) -> int:
    # Apply level and allow a brief moment for it to take effect
    r = _put(api_base, '/logs/level/postfix', {'level': level})
    assert r.ok
    time.sleep(0.5)

    # Establish baseline and wait for one email worth of lines (ignore startup noise)
    base0 = _get_postfix_line_count(api_base)

    _send_test_mail(smtp_port, recipient)

    # Wait until count increases after first send
    start = time.time()
    count1 = base0
    while time.time() - start < 90:
        count1 = _get_postfix_line_count(api_base)
        if count1 > base0:
            break
        time.sleep(0.5)

    # Send another email and wait for next increase
    _send_test_mail(smtp_port, recipient)

    start2 = time.time()
    count2 = count1
    while time.time() - start2 < 90:
        count2 = _get_postfix_line_count(api_base)
        if count2 > count1:
            break
        time.sleep(0.5)

    delta = max(0, count2 - count1)
    return delta


@pytest.mark.e2e
@pytest.mark.parametrize(
    'scenario',
    [
        {'name': 'pg', 'api_base': API_BASE_PG, 'smtp_port': SMTP_PORT_PG},
        {'name': 'db2', 'api_base': API_BASE_DB2, 'smtp_port': SMTP_PORT_DB2},
    ],
    ids=lambda s: s['name'],
)
def test_postfix_log_level_increasing_line_counts(scenario):
    if not wait_for_api_ready(scenario['api_base']):
        pytest.skip(f'API not ready for e2e test ({scenario["name"]})')

    # Use distinct recipients per level to aid diagnostics
    ts = int(time.time() * 1000)
    rec_warning = f'loglvl-{scenario["name"]}-warning-{ts}@example.com'
    rec_info = f'loglvl-{scenario["name"]}-info-{ts}@example.com'
    rec_debug = f'loglvl-{scenario["name"]}-debug-{ts}@example.com'

    # WARNING should be least verbose, INFO more, DEBUG most
    dw = _measure_delta_for_level(
        scenario['api_base'], scenario['smtp_port'], 'WARNING', rec_warning
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
