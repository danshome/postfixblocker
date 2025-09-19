from __future__ import annotations

import logging
import os
import tempfile
from logging.handlers import RotatingFileHandler

import pytest

from postfix_blocker.logging_setup import configure_logging, set_logger_level


@pytest.mark.unit
def test_configure_logging_sets_level_and_file_handler(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        log_path = os.path.join(td, 'app.log')
        monkeypatch.setenv('X_LEVEL', 'DEBUG')
        monkeypatch.setenv('X_FILE', log_path)

        # Remove any pre-existing RotatingFileHandler on root
        root = logging.getLogger()
        for h in list(root.handlers):
            if isinstance(h, RotatingFileHandler):
                root.removeHandler(h)

        configure_logging(service='api', level_env='X_LEVEL', file_env='X_FILE', default='INFO')

        assert root.level == logging.DEBUG
        # A RotatingFileHandler pointing at our file should be present and properly configured
        file_handlers = [h for h in root.handlers if isinstance(h, RotatingFileHandler)]
        assert any(getattr(h, 'baseFilename', None) == log_path for h in file_handlers)
        # Strengthen assertions: verify rotation config
        target = next(h for h in file_handlers if getattr(h, 'baseFilename', None) == log_path)
        assert getattr(target, 'maxBytes', None) == 10 * 1024 * 1024
        assert getattr(target, 'backupCount', None) == 5


@pytest.mark.unit
def test_set_logger_level_updates_root_level():
    root = logging.getLogger()
    set_logger_level('WARNING')
    assert root.level == logging.WARNING
    set_logger_level(10)
    assert root.level == 10
