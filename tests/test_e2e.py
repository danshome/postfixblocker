import json
import os
from urllib.request import urlopen

import pytest

from tests.e2e_test import run_e2e_scenario
from tests.utils_wait import wait_for_db_url, wait_for_smtp


def _target_db2():
    return {
        'name': 'db2',
        'db_url': os.environ.get(
            'TEST_DB2_URL', 'ibm_db_sa://db2inst1:blockerpass@localhost:50000/BLOCKER'
        ),
        'smtp_host': os.environ.get('SMTP_HOST', 'localhost'),
        'smtp_port': int(os.environ.get('SMTP_PORT_DB2', '1026')),
        'mh_host': os.environ.get('MAILHOG_HOST', 'localhost'),
        'mh_port': int(os.environ.get('MAILHOG_PORT', '8025')),
    }


@pytest.mark.e2e
def test_e2e_db2():
    target = _target_db2()
    # Ensure DB and SMTP endpoints are ready; fail if not.
    if not wait_for_db_url(target['db_url']):
        pytest.fail(
            f'DB not ready for {target["name"]} at {target["db_url"]}. Backend/E2E tests require the database to be available.'
        )
    if not wait_for_smtp(target['smtp_host'], target['smtp_port'], total_timeout=60):
        pytest.fail(
            f'SMTP not ready for {target["name"]} at {target["smtp_host"]}:{target["smtp_port"]}. Backend/E2E tests require SMTP to be available.'
        )
    delivered = run_e2e_scenario(
        target['db_url'],
        target['smtp_host'],
        target['smtp_port'],
        target['mh_host'],
        target['mh_port'],
    )

    if not delivered:  # backend/service not available; fail with diagnostics
        # Gather some quick diagnostics to aid triage
        diag = {
            'db_url': target['db_url'],
            'smtp': f'{target["smtp_host"]}:{target["smtp_port"]}',
            'mailhog': f'{target["mh_host"]}:{target["mh_port"]}',
            'mh_count': 'n/a',
        }
        try:
            with urlopen(
                f'http://{target["mh_host"]}:{target["mh_port"]}/api/v2/messages?limit=100',
                timeout=5,
            ) as resp:
                data = json.load(resp)
                diag['mh_count'] = len(data.get('items', []))
        except Exception:
            pass
        pytest.fail(f'E2E target {target["name"]} unavailable or failed; diag={diag}')

    assert 'allowed@example.com' in delivered
    assert 'blocked1@example.com' not in delivered
    assert 'user@blocked.com' not in delivered
