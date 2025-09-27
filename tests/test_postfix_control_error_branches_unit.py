from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from postfix_blocker.postfix.control import has_postfix_pcre, reload_postfix


@dataclass
class _RC:
    returncode: int


@pytest.mark.unit
def test_reload_postfix_handles_env_not_ready(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    # Create empty map files to force size==0 branch
    (tmp_path / 'blocked_recipients').write_text('', encoding='utf-8')
    (tmp_path / 'blocked_recipients_test').write_text('', encoding='utf-8')

    # Fail postmap and status to exercise the "environment not ready" warning path
    def _fake_run(cmd: list[str], **kwargs: Any) -> _RC:  # type: ignore[no-untyped-def]
        # return non-zero for all commands to simulate transient failures
        return _RC(returncode=1)

    monkeypatch.setenv('POSTFIX_DIR', str(tmp_path))
    monkeypatch.setattr('postfix_blocker.postfix.control._run_fixed', _fake_run)

    # Should not raise
    reload_postfix()


@pytest.mark.unit
def test_has_postfix_pcre_file_not_found(monkeypatch) -> None:
    def _raise_not_found(cmd: list[str], **kwargs: Any):  # type: ignore[no-untyped-def]
        raise FileNotFoundError('postconf')

    monkeypatch.setattr('postfix_blocker.postfix.control._run_fixed', _raise_not_found)
    assert has_postfix_pcre() is False
