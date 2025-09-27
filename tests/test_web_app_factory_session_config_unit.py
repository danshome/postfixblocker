from __future__ import annotations

import flask
import pytest

from postfix_blocker.web.app_factory import create_app


@pytest.mark.unit
def test_create_app_handles_session_config_error(monkeypatch, caplog):
    # Make Config.update raise the first time it's called to trigger the
    # try/except in create_app's session configuration block.
    original_update = flask.config.Config.update

    def broken_update(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError('boom')

    monkeypatch.setattr(flask.config.Config, 'update', broken_update)

    try:
        caplog.set_level('WARNING')
        app = create_app()
        # App should still be created successfully even if session config fails
        assert getattr(app, 'secret_key', None) is not None
    finally:
        # Restore original method to avoid leaking state
        monkeypatch.setattr(flask.config.Config, 'update', original_update)
