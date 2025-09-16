from __future__ import annotations

import pytest


@pytest.mark.unit
def test_app_factory_blueprints_and_tail_endpoint():
    from postfix_blocker.web.app_factory import create_app

    app = create_app()

    # Blueprints registered
    assert 'logs' in app.blueprints
    assert 'addresses' in app.blueprints

    # /logs/tail should not require DB readiness
    client = app.test_client()
    resp = client.get('/logs/tail?name=api&lines=1')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    assert data.get('name') == 'api'

    # ensure_db_ready is present and returns a boolean
    ensure_db_ready = app.config.get('ensure_db_ready')
    assert callable(ensure_db_ready)
    assert isinstance(ensure_db_ready(), bool)
