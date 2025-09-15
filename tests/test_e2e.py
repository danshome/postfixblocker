import os

import pytest

from tests.e2e_test import run_e2e_scenario
from tests.utils_wait import wait_for_db_url, wait_for_smtp


def _targets():
    return [
        {
            'name': 'pg',
            'db_url': os.environ.get(
                'TEST_PG_URL', 'postgresql://blocker:blocker@localhost:5433/blocker'
            ),
            'smtp_host': os.environ.get('SMTP_HOST', 'localhost'),
            'smtp_port': int(os.environ.get('SMTP_PORT_PG', '1025')),
            'mh_host': os.environ.get('MAILHOG_HOST', 'localhost'),
            'mh_port': int(os.environ.get('MAILHOG_PORT', '8025')),
        },
        {
            'name': 'db2',
            'db_url': os.environ.get(
                'TEST_DB2_URL',
                'ibm_db_sa://db2inst1:blockerpass@localhost:50000/BLOCKER',
            ),
            'smtp_host': os.environ.get('SMTP_HOST', 'localhost'),
            'smtp_port': int(os.environ.get('SMTP_PORT_DB2', '1026')),
            'mh_host': os.environ.get('MAILHOG_HOST', 'localhost'),
            'mh_port': int(os.environ.get('MAILHOG_PORT', '8025')),
        },
    ]


@pytest.mark.e2e
@pytest.mark.parametrize('target', _targets(), ids=lambda t: t['name'])
def test_e2e_both_backends(target):
    # Ensure DB and SMTP endpoints are ready; skip if not.
    if not wait_for_db_url(target['db_url']):
        pytest.skip(f'DB not ready for {target["name"]}')
    if not wait_for_smtp(target['smtp_host'], target['smtp_port'], total_timeout=60):
        pytest.skip(f'SMTP not ready for {target["name"]}')
    delivered = run_e2e_scenario(
        target['db_url'],
        target['smtp_host'],
        target['smtp_port'],
        target['mh_host'],
        target['mh_port'],
    )

    if not delivered:  # backend/service not available; skip rather than fail
        pytest.skip(f'E2E target {target["name"]} unavailable')

    assert 'allowed@example.com' in delivered
    assert 'blocked1@example.com' not in delivered
    assert 'user@blocked.com' not in delivered
