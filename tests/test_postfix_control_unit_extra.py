from __future__ import annotations

from types import SimpleNamespace

import pytest

from postfix_blocker.postfix.control import has_postfix_pcre, reload_postfix


class _DummyCompleted:
    def __init__(self, returncode: int = 0, stdout: str = ''):
        self.returncode = returncode
        self.stdout = stdout


@pytest.mark.unit
def test_reload_postfix_happy_path(tmp_path, monkeypatch):
    # Prepare fake postfix dir with map files
    pf = tmp_path / 'postfix'
    pf.mkdir()
    (pf / 'blocked_recipients').write_text('ok')
    (pf / 'blocked_recipients_test').write_text('ok')
    monkeypatch.setenv('POSTFIX_DIR', str(pf))

    calls = []

    def _fake_run(args, **kwargs):  # nosec - test stub
        calls.append(list(args))
        # Simulate 'postfix status' returning 0 to trigger reload
        if args[:2] == ['/usr/sbin/postfix', 'status']:
            return _DummyCompleted(0)
        return _DummyCompleted(0)

    monkeypatch.setattr('postfix_blocker.postfix.control.subprocess.run', _fake_run)

    # Should not raise
    reload_postfix()

    # Ensure we attempted postmap, status, and reload
    cmds = [' '.join(c) for c in calls]
    assert any('postmap' in c for c in cmds)
    assert any('postfix status' in c for c in cmds)
    assert any('postfix reload' in c for c in cmds)


@pytest.mark.unit
def test_has_postfix_pcre_true(monkeypatch):
    def _fake_run(args, **kwargs):  # nosec - test stub
        return SimpleNamespace(stdout='btree hash pcre ')

    monkeypatch.setattr('postfix_blocker.postfix.control.subprocess.run', _fake_run)
    assert has_postfix_pcre() is True


@pytest.mark.unit
def test_has_postfix_pcre_file_missing(monkeypatch):
    def _fake_run(args, **kwargs):  # nosec - test stub
        raise FileNotFoundError('postconf missing')

    monkeypatch.setattr('postfix_blocker.postfix.control.subprocess.run', _fake_run)
    assert has_postfix_pcre() is False
