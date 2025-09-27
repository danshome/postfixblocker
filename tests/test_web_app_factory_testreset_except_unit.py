from __future__ import annotations

import sys
import types

import pytest

from postfix_blocker.web.app_factory import create_app


@pytest.mark.unit
def test_create_app_handles_missing_test_reset_blueprint(monkeypatch):
    # Enable the optional test reset blueprint
    monkeypatch.setenv('TEST_RESET_ENABLE', '1')

    # Inject a dummy module without `bp` so `from .routes_test_reset import bp` fails
    fake_mod = types.ModuleType('postfix_blocker.web.routes_test_reset')
    monkeypatch.setitem(sys.modules, 'postfix_blocker.web.routes_test_reset', fake_mod)

    app = create_app()
    # App should still be constructed successfully even if importing the test
    # reset blueprint fails; no exception should bubble up.
    assert app is not None
