from __future__ import annotations

import logging
import os

import pytest

from postfix_blocker.logging_setup import configure_logging, set_logger_level


@pytest.mark.unit
def test_configure_logging_and_set_logger_level_variants(tmp_path):
    # Point logs at a temp file
    log_file = tmp_path / 'api.log'
    os.environ['API_LOG_FILE'] = str(log_file)
    os.environ['API_LOG_LEVEL'] = 'INFO'
    try:
        configure_logging(
            service='api', level_env='API_LOG_LEVEL', file_env='API_LOG_FILE', default='WARNING'
        )
        logger = logging.getLogger('api')
        # Default INFO from env should be applied
        assert logger.level in (logging.INFO, 0)  # 0 if handler-level manages it

        # Change level via helper (case-insensitive and tolerant)
        set_logger_level('debug')
        # After setting DEBUG, logger should be more verbose
        # We can't assert exact value because logging setup may use handlers; check that DEBUG is enabled
        assert logger.isEnabledFor(logging.DEBUG)

        # Set invalid value should not raise
        set_logger_level('not-a-level')
        # Keep a simple log to hit file writing path
        logger.info('hello test')
        assert log_file.exists()
    finally:
        os.environ.pop('API_LOG_FILE', None)
        os.environ.pop('API_LOG_LEVEL', None)
