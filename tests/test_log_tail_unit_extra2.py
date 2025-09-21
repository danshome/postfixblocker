from __future__ import annotations

import builtins

import pytest

from postfix_blocker.services.log_tail import tail_file


@pytest.mark.unit
def test_tail_file_unicode_fallback(monkeypatch, tmp_path):
    p = tmp_path / 'log.bin'
    p.write_bytes(b'line-1\nline-2\n')

    # Force the first open (text mode) to raise UnicodeDecodeError to exercise fallback
    real_open = builtins.open

    def fake_open(path, *args, **kwargs):  # type: ignore[no-untyped-def]
        # When opened with text encoding (utf-8) we simulate a decode error
        if kwargs.get('encoding') == 'utf-8':
            raise UnicodeDecodeError('utf-8', b'\xff', 0, 1, 'fake')
        # When opened in binary, return bytes from the actual file
        if 'b' in args[0] if args else 'b' in kwargs.get('mode', ''):
            return real_open(path, 'rb')
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(builtins, 'open', fake_open)

    out = tail_file(str(p), 1)
    assert out.strip() == 'line-2'
