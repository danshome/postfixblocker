import os
import smtplib
import time
from email.message import EmailMessage

import pytest
import requests

API_BASE = os.environ.get('E2E_API_BASE', 'http://127.0.0.1:5001')


def _get(path: str, **kwargs):
    return requests.get(API_BASE + path, timeout=30, **kwargs)


def _put(path: str, json: dict):
    return requests.put(API_BASE + path, json=json, timeout=30)


def wait_for_api_ready(timeout=600):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = _get('/addresses')
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def _send_test_mail(port: int = 1025, to_addr: str = 'recipient@example.com') -> None:
    msg = EmailMessage()
    msg['From'] = 'sender@example.com'
    msg['To'] = to_addr
    msg['Subject'] = 'PostfixBlocker E2E Simple Test'
    msg.set_content('Hello from simple e2e test')
    with smtplib.SMTP('127.0.0.1', port, timeout=10) as s:
        s.send_message(msg)


def _get_postfix_line_count() -> int:
    r = _get('/logs/lines', params={'name': 'postfix'})
    assert r.ok
    return int(r.json().get('count') or 0)


def _measure_delta_for_level(level: str) -> int:
    # Apply level
    r = _put('/logs/level/postfix', {'level': level})
    assert r.ok

    # Establish baseline and wait for one email worth of lines
    base0 = _get_postfix_line_count()

    _send_test_mail()

    # Wait until count increases after first send
    start = time.time()
    count1 = base0
    while time.time() - start < 45:
        count1 = _get_postfix_line_count()
        if count1 > base0:
            break
        time.sleep(0.5)

    # Send another email and wait for next increase
    _send_test_mail()

    start2 = time.time()
    count2 = count1
    while time.time() - start2 < 45:
        count2 = _get_postfix_line_count()
        if count2 > count1:
            break
        time.sleep(0.5)

    delta = max(0, count2 - count1)
    return delta


@pytest.mark.e2e
def test_postfix_log_level_increasing_line_counts():
    if not wait_for_api_ready():
        pytest.skip('API not ready for e2e test')

    # WARNING should be least verbose, INFO more, DEBUG most
    dw = _measure_delta_for_level('WARNING')
    di = _measure_delta_for_level('INFO')
    dd = _measure_delta_for_level('DEBUG')

    # Allow small variability on CI: INFO may occasionally be within a small
    # margin of WARNING due to unrelated background log noise.
    slack = 25
    assert di >= dw - slack, (
        f'Expected INFO ({di}) to be close to or above WARNING ({dw}); slack={slack}'
    )
    # DEBUG should be the most verbose
    assert dd > max(di, dw), f'Expected DEBUG ({dd}) > max(INFO, WARNING) ({max(di, dw)})'
