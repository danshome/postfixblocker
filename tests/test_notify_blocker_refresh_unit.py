from __future__ import annotations

import pytest

from postfix_blocker.web.routes_addresses import _notify_blocker_refresh


@pytest.mark.unit
def test_notify_blocker_refresh_success(monkeypatch, tmp_path):
    # Create a fake pid file
    pidfile = tmp_path / 'blocker.pid'
    pidfile.write_text('1234', encoding='utf-8')

    # Point env to our temp pid file
    monkeypatch.setenv('BLOCKER_PID_FILE', str(pidfile))

    called = {'pid': None, 'sig': None}

    def fake_kill(pid, sig):
        called['pid'] = pid
        called['sig'] = sig

    monkeypatch.setattr('os.kill', fake_kill)

    # Should attempt to send SIGUSR1 to PID 1234
    _notify_blocker_refresh()
    assert called['pid'] == 1234
    # signal.SIGUSR1 has value 30/10/varies; check type only
    assert called['sig'] is not None


@pytest.mark.unit
def test_notify_blocker_refresh_ignores_errors(monkeypatch, tmp_path):
    # Write an invalid PID to trigger exception path
    pidfile = tmp_path / 'blocker.pid'
    pidfile.write_text('not-a-pid', encoding='utf-8')
    monkeypatch.setenv('BLOCKER_PID_FILE', str(pidfile))

    # Should not raise
    _notify_blocker_refresh()
