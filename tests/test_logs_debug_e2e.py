import os
import re
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


def _send_test_mail(port: int = 1025) -> None:
    msg = EmailMessage()
    msg['From'] = 'sender@example.com'
    msg['To'] = 'recipient@example.com'
    msg['Subject'] = 'PostfixBlocker E2E Test'
    msg.set_content('Hello from e2e test')
    with smtplib.SMTP('127.0.0.1', port, timeout=10) as s:
        s.send_message(msg)


@pytest.mark.e2e
def test_debug_levels_reflected_in_logs():
    if not wait_for_api_ready():
        pytest.skip('API not ready for e2e test')

    # 1) API log: set to DEBUG, then make a paged request to trigger DEBUG logs and verify tail
    r = _put('/logs/level/api', {'level': 'DEBUG'})
    assert r.ok

    # Trigger a paged list to hit app.logger.debug path
    r = _get('/addresses', params={'page': '1', 'page_size': '1'})
    assert r.status_code in (200, 503)  # tolerate DB not ready briefly

    # Poll API log tail for evidence of DEBUG
    api_debug_ok = False
    start = time.time()
    while time.time() - start < 30:
        tr = _get('/logs/tail', params={'name': 'api', 'lines': '500'})
        assert tr.ok
        content = tr.json().get('content') or ''
        if ('API log level changed via props to DEBUG' in content) or ('[DEBUG]' in content):
            api_debug_ok = True
            break
        time.sleep(1.0)
    assert api_debug_ok, 'API log did not show DEBUG entries after level change'

    # 2) Blocker log: set to DEBUG and verify a DEBUG heartbeat or level-change note appears
    r = _put('/logs/level/blocker', {'level': 'DEBUG'})
    assert r.ok

    blocker_debug_ok = False
    start = time.time()
    while time.time() - start < 60:
        tr = _get('/logs/tail', params={'name': 'blocker', 'lines': '500'})
        if not tr.ok:
            time.sleep(1.0)
            continue
        content = tr.json().get('content') or ''
        if (
            'Blocker log level changed via props to' in content
            or 'Blocker loop heartbeat' in content
            or '[DEBUG]' in content
        ):
            blocker_debug_ok = True
            break
        time.sleep(1.0)
    assert blocker_debug_ok, 'Blocker log did not show DEBUG entries after level change'

    # 3) Postfix log: iterate through WARNING, INFO, DEBUG and verify verbosity differences

    def _tail_postfix(lines: int = 2000) -> str:
        tr_ = _get('/logs/tail', params={'name': 'postfix', 'lines': str(lines)})
        assert tr_.ok
        return tr_.json().get('content') or ''

    def _has_fatal_cfg(text: str) -> bool:
        t = text.lower()
        return ('fatal: bad numerical configuration' in t) or ('invalid debug_peer_level' in t)

    def _send_tagged_mails(tag: str, count: int = 2, port: int = 1025) -> None:
        for i in range(count):
            msg = EmailMessage()
            msg['From'] = 'sender@example.com'
            msg['To'] = f'recipient+{tag}-{i}@example.com'
            msg['Subject'] = f'PF E2E {tag}-{i}'
            msg.set_content('Hello from e2e test')
            with smtplib.SMTP('127.0.0.1', port, timeout=10) as s:
                s.send_message(msg)

    def _delta_postfix_lines(since_last_line: str, max_wait: float = 30.0) -> list[str]:
        # Poll until we see the marker line in the tail, then return the delta lines after it
        start_ = time.time()
        lines_param = 3000
        while time.time() - start_ < max_wait:
            content_ = _tail_postfix(lines=lines_param)
            lines_ = content_.splitlines()
            if not lines_:
                time.sleep(0.5)
                continue
            try:
                idx = len(lines_) - 1 - lines_[::-1].index(since_last_line)
                return lines_[idx + 1 :]
            except ValueError:
                # If marker fell out of window, expand
                lines_param = min(8000, lines_param + 1000)
                time.sleep(0.5)
        return []

    def _count_postfix_activity(delta_lines: list[str]) -> int:
        patt = re.compile(
            r'postfix/(smtpd|smtp|cleanup|qmgr|pickup|bounce|local|trivial-rewrite)', re.IGNORECASE
        )
        return sum(1 for ln in delta_lines if patt.search(ln))

    levels = ['WARNING', 'INFO', 'DEBUG']
    counts: dict[str, int] = {}

    for lv in levels:
        # Set level
        r = _put('/logs/level/postfix', {'level': lv})
        assert r.ok
        # Quick fatal check
        bad = False
        start2 = time.time()
        while time.time() - start2 < 10:
            cont = _tail_postfix(400)
            if _has_fatal_cfg(cont):
                bad = True
                break
            time.sleep(0.5)
        assert not bad, f'Postfix reported configuration error after setting {lv}'

        # Marker
        baseline = _tail_postfix(2000)
        marker = baseline.splitlines()[-1] if baseline.splitlines() else ''

        # Send a couple of emails
        try:
            _send_tagged_mails(lv.lower(), count=2, port=1025)
        except Exception:
            time.sleep(2)
            _send_tagged_mails(lv.lower(), count=2, port=1025)

        # Collect delta and activity count
        delta = _delta_postfix_lines(marker, max_wait=45.0)
        activity = _count_postfix_activity(delta)

        # Also ensure we saw at least some evidence of the sends
        def _delivery_evidence(ln: str) -> bool:
            return (
                ('to=<' in ln)
                or ('relay=mailhog' in ln)
                or ('status=sent' in ln)
                or ('queued as ' in ln)
            )

        assert any(_delivery_evidence(ln) for ln in delta), (
            f'No postfix delivery evidence at level {lv}'
        )
        counts[lv] = activity

    # Assert verbosity ordering: WARNING <= INFO <= DEBUG and at least one strict increase
    assert counts['INFO'] >= counts['WARNING'], f'Expected INFO >= WARNING but got {counts}'
    assert counts['DEBUG'] >= counts['INFO'], f'Expected DEBUG >= INFO but got {counts}'
    assert (counts['DEBUG'] >= counts['INFO'] + 2) or (counts['INFO'] >= counts['WARNING'] + 2), (
        f'Expected a noticeable verbosity increase across levels, got {counts}'
    )
