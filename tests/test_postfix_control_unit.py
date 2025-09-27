from __future__ import annotations

import types

import pytest

from postfix_blocker.postfix.control import has_postfix_pcre, reload_postfix


class _RC:
    def __init__(self, rc: int):
        self.returncode = rc


@pytest.mark.unit
def test_reload_postfix_success_and_reload(monkeypatch):
    calls: list[tuple[tuple[str, ...], dict]] = []

    def fake_run(argv, check=False, capture_output=False, text=False):
        calls.append((tuple(argv), {}))
        # Map command to return code
        if argv[:2] == ['/usr/sbin/postfix', 'status']:
            return _RC(0)
        return _RC(0)

    # Sizes > 0 so we do not take the size==0 warning branch
    monkeypatch.setenv('POSTFIX_DIR', '/tmp/postfix')
    monkeypatch.setattr('os.path.getsize', lambda _p: 1024)
    monkeypatch.setattr('subprocess.run', fake_run)

    # Should not raise
    reload_postfix()

    # Expect postmap on two files and postfix status+reload
    joined = '\n'.join(' '.join(a) for a, _ in calls)
    assert '/usr/sbin/postmap' in joined
    assert '/usr/sbin/postfix status' in joined
    assert '/usr/sbin/postfix reload' in joined


@pytest.mark.unit
def test_reload_postfix_warning_branches(monkeypatch):
    # Force sizes==0 and postfix status != 0 to hit the special warning path
    monkeypatch.setattr('os.path.getsize', lambda _p: 0)

    seq = {
        'postmap1': 0,
        'postmap2': 1,  # fail one of the postmap commands
        'status': 1,  # postfix not running
        'reload': 1,
    }

    def fake_run(argv, check=False, capture_output=False, text=False):
        if argv[:2] == ['/usr/sbin/postfix', 'status']:
            return _RC(seq['status'])
        if argv[:2] == ['/usr/sbin/postfix', 'reload']:
            return _RC(seq['reload'])
        # two postmap calls come first
        if argv[0] == '/usr/sbin/postmap':
            # toggle between first and second
            if seq['postmap1'] is not None:
                rc = seq['postmap1']
                seq['postmap1'] = None  # type: ignore[assignment]
                return _RC(rc)
            return _RC(seq['postmap2'])
        return _RC(0)

    monkeypatch.setattr('subprocess.run', fake_run)

    # Should not raise despite failures; logs a warning internally
    reload_postfix()


@pytest.mark.unit
def test_reload_postfix_exception_is_caught(monkeypatch):
    def boom(argv, **kwargs):
        raise RuntimeError('no binaries')

    monkeypatch.setattr('subprocess.run', boom)

    # Should swallow exception and only log a warning
    reload_postfix()


@pytest.mark.unit
def test_has_postfix_pcre_true(monkeypatch):
    def ok(argv, capture_output=False, text=False, check=True):
        return types.SimpleNamespace(stdout='xxx\nPCRE\nzzz')

    monkeypatch.setattr('subprocess.run', ok)
    assert has_postfix_pcre() is True


@pytest.mark.unit
def test_has_postfix_pcre_file_not_found(monkeypatch):
    def not_found(argv, **kwargs):
        raise FileNotFoundError('postconf missing')

    monkeypatch.setattr('subprocess.run', not_found)
    assert has_postfix_pcre() is False


@pytest.mark.unit
def test_has_postfix_pcre_generic_exception(monkeypatch):
    def err(argv, **kwargs):
        raise RuntimeError('bad')

    monkeypatch.setattr('subprocess.run', err)
    assert has_postfix_pcre() is False
