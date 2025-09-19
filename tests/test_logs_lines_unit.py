from __future__ import annotations

import pytest


@pytest.mark.unit
def test_logs_lines_endpoint_basic():
    from postfix_blocker.web.app_factory import create_app

    app = create_app()
    client = app.test_client()

    # Known name should succeed with JSON shape
    resp = client.get('/logs/lines?name=api')
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    assert data.get('name') == 'api'
    assert 'path' in data
    assert 'count' in data
    assert 'missing' in data

    # Unknown name should be a 400
    resp2 = client.get('/logs/lines?name=unknown')
    assert resp2.status_code == 400
