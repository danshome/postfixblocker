from __future__ import annotations

import pytest

from postfix_blocker.config import Config, load_config


@pytest.mark.unit
def test_load_config_defaults(monkeypatch):
    # Clear env
    for k in [
        'BLOCKER_DB_URL',
        'BLOCKER_INTERVAL',
        'POSTFIX_DIR',
        'BLOCKER_PID_FILE',
        'API_LOG_FILE',
        'API_LOG_LEVEL',
        'BLOCKER_LOG_FILE',
        'BLOCKER_LOG_LEVEL',
    ]:
        monkeypatch.delenv(k, raising=False)

    cfg = load_config()
    assert isinstance(cfg, Config)
    assert cfg.db_url.endswith('@db:5432/blocker')
    assert cfg.check_interval == 5.0
    assert cfg.postfix_dir == '/etc/postfix'
    assert cfg.pid_file.endswith('blocker.pid')
    assert cfg.api_log_file is None
    assert cfg.blocker_log_file is None
    assert cfg.api_log_level == 'INFO'
    assert cfg.blocker_log_level == 'INFO'


@pytest.mark.unit
def test_load_config_overrides(monkeypatch):
    monkeypatch.setenv('BLOCKER_DB_URL', 'sqlite:///file.db')
    monkeypatch.setenv('BLOCKER_INTERVAL', '2.5')
    monkeypatch.setenv('POSTFIX_DIR', '/tmp/postfix')
    monkeypatch.setenv('BLOCKER_PID_FILE', '/tmp/pidfile.pid')
    monkeypatch.setenv('API_LOG_FILE', '/tmp/a.log')
    monkeypatch.setenv('BLOCKER_LOG_FILE', '/tmp/b.log')
    monkeypatch.setenv('API_LOG_LEVEL', 'DEBUG')
    monkeypatch.setenv('BLOCKER_LOG_LEVEL', '10')

    cfg = load_config()
    assert cfg.db_url == 'sqlite:///file.db'
    assert cfg.check_interval == 2.5
    assert cfg.postfix_dir == '/tmp/postfix'
    assert cfg.pid_file == '/tmp/pidfile.pid'
    assert cfg.api_log_file == '/tmp/a.log'
    assert cfg.blocker_log_file == '/tmp/b.log'
    assert cfg.api_log_level == 'DEBUG'
    assert cfg.blocker_log_level == '10'
