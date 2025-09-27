from __future__ import annotations

import pytest

from postfix_blocker.postfix.log_level import resolve_mail_log_path


@pytest.mark.unit
def test_resolve_mail_log_path_env_override(monkeypatch, tmp_path):
    p = tmp_path / 'mail.log'
    p.write_text('x', encoding='utf-8')
    monkeypatch.setenv('MAIL_LOG_FILE', str(p))
    assert resolve_mail_log_path() == str(p)


@pytest.mark.unit
def test_resolve_mail_log_path_preferred_and_fallback(monkeypatch, tmp_path):
    # Simulate presence of system paths without touching the real filesystem
    monkeypatch.delenv('MAIL_LOG_FILE', raising=False)

    def fake_exists(path: str) -> bool:
        return path in ('/var/log/maillog', '/var/log/mail.log')

    def fake_size(path: str) -> int:
        if path == '/var/log/maillog':
            return 1
        if path == '/var/log/mail.log':
            return 2
        return 0

    monkeypatch.setattr('os.path.exists', fake_exists)
    monkeypatch.setattr('os.path.getsize', fake_size)

    # Should pick preferred when it has size > 0
    assert resolve_mail_log_path() == '/var/log/maillog'

    # Now zero out preferred to force fallback branch
    def fake_size2(path: str) -> int:
        if path == '/var/log/maillog':
            return 0
        if path == '/var/log/mail.log':
            return 2
        return 0

    monkeypatch.setattr('os.path.getsize', fake_size2)
    # Should pick fallback when preferred has size 0
    assert resolve_mail_log_path() == '/var/log/mail.log'


@pytest.mark.unit
def test_resolve_mail_log_path_exception_branch(monkeypatch):
    # Cause os.path.getsize to throw; function should return preferred '/var/log/maillog'
    monkeypatch.delenv('MAIL_LOG_FILE', raising=False)

    def bad_size(_):
        raise RuntimeError('boom')

    def fake_exists(_):
        return True

    monkeypatch.setattr('os.path.exists', fake_exists)
    monkeypatch.setattr('os.path.getsize', bad_size)

    path = resolve_mail_log_path()
    assert isinstance(path, str)
    assert path.endswith('maillog')
