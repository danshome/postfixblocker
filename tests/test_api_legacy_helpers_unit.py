from __future__ import annotations

import logging
from typing import Any

import pytest

from postfix_blocker import api as api_mod
from postfix_blocker.logging_setup import set_logger_level


@pytest.mark.unit
def test__coerce_level_numeric_and_names() -> None:
    # Numeric strings are returned as integers
    assert api_mod._coerce_level('15') == 15
    # Known names map via logging module
    assert api_mod._coerce_level('DEBUG') == logging.DEBUG
    assert api_mod._coerce_level('info') == logging.INFO
    # Unknown names default to INFO
    assert api_mod._coerce_level('not-a-level') == logging.INFO


@pytest.mark.unit
def test__tail_file_returns_last_lines(tmp_path) -> None:  # type: ignore[no-untyped-def]
    p = tmp_path / 'sample.log'
    lines = [f'line-{i}' for i in range(7)]
    p.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    out = api_mod._tail_file(str(p), 3)
    assert out.splitlines() == lines[-3:]


@pytest.mark.unit
def test_package_dunder_getattr_error() -> None:
    import postfix_blocker as pkg

    with pytest.raises(AttributeError):
        # Accessing an unknown attribute should raise AttributeError(name)
        pkg.does_not_exist


class _FakeCompleted:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout


@pytest.mark.unit
def test_has_postfix_pcre_true(monkeypatch) -> None:
    # Patch the control module's _run_fixed to simulate `postconf -m` output
    from postfix_blocker.postfix import control as ctl

    def _fake_run(cmd: list[str], **kwargs: Any) -> _FakeCompleted:  # type: ignore[no-untyped-def]
        assert cmd[:2] == ['/usr/sbin/postconf', '-m']
        return _FakeCompleted('pcre\nhash\n')

    monkeypatch.setattr(ctl, '_run_fixed', _fake_run)
    assert ctl.has_postfix_pcre() is True


@pytest.mark.unit
def test_set_logger_level_changes_root_level() -> None:
    # Ensure we can set the root logger level dynamically
    set_logger_level('WARNING')
    assert logging.getLogger().getEffectiveLevel() == logging.WARNING
