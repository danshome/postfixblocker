from __future__ import annotations

import os

import pytest


@pytest.mark.e2e
def test_db2_mail_log_has_content():
    """Ensure the DB2 postfix mail log has content after E2E tests.

    This asserts we exercised the DB2-backed postfix instance during the run.
    """
    p = os.path.abspath('./logs/postfix.maillog')
    if not os.path.exists(p):
        # Create empty file if missing to avoid file-not-found flakiness
        open(p, 'a', encoding='utf-8').close()
    try:
        with open(p, encoding='utf-8', errors='replace') as f:
            count = sum(1 for _ in f)
    except Exception:
        count = 0
    assert count > 0, 'Expected DB2 postfix maillog to have at least one line.'
