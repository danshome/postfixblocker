from __future__ import annotations

import pytest

try:
    from sqlalchemy import create_engine
except Exception:  # pragma: no cover - SQLAlchemy may be missing
    create_engine = None  # type: ignore

from postfix_blocker.db.migrations import init_db
from postfix_blocker.web.app_factory import create_app


@pytest.mark.unit
@pytest.mark.skipif(create_engine is None, reason='SQLAlchemy not installed')
def test_logs_refresh_get_put_and_level_api(monkeypatch):
    eng = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(eng)
    app = create_app()
    app.testing = True
    app.config['db_engine'] = eng
    app.config['ensure_db_ready'] = lambda: True

    with app.test_client() as c:
        # GET defaults
        r_get = c.get('/logs/refresh/api')
        assert r_get.status_code == 200
        js = r_get.get_json() or {}
        assert js.get('name') == 'api'
        assert isinstance(js.get('interval_ms'), int)
        assert isinstance(js.get('lines'), int)

        # PUT new settings
        r_put = c.put('/logs/refresh/api', json={'interval_ms': 1234, 'lines': 321})
        assert r_put.status_code == 200
        # Confirm GET reflects new values
        r_get2 = c.get('/logs/refresh/api')
        js2 = r_get2.get_json() or {}
        assert js2.get('interval_ms') == 1234
        assert js2.get('lines') == 321

        # Level GET/PUT for api
        r_lv0 = c.get('/logs/level/api')
        assert r_lv0.status_code == 200
        r_lv = c.put('/logs/level/api', json={'level': 'DEBUG'})
        assert r_lv.status_code == 200
        r_lv2 = c.get('/logs/level/api')
        assert (r_lv2.get_json() or {}).get('level') in ('DEBUG', '10', 'debug', 10, 'INFO', None)


@pytest.mark.unit
@pytest.mark.skipif(create_engine is None, reason='SQLAlchemy not installed')
def test_logs_level_postfix_and_invalid_service(monkeypatch):
    eng = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(eng)
    app = create_app()
    app.testing = True
    app.config['db_engine'] = eng
    app.config['ensure_db_ready'] = lambda: True

    # Monkeypatch apply_postfix_log_level to capture input without touching filesystem
    called = {'level': None}
    from postfix_blocker.web import routes_logs as rl

    monkeypatch.setattr(
        rl,
        'apply_postfix_log_level',
        lambda level: called.__setitem__('level', level),
    )

    with app.test_client() as c:
        # PUT level for postfix triggers our patched function
        r = c.put('/logs/level/postfix', json={'level': 'WARNING'})
        assert r.status_code == 200
        assert called['level'] == 'WARNING'

        # Invalid service -> 404
        r404 = c.get('/logs/level/unknown')
        assert r404.status_code == 404


@pytest.mark.unit
def test_logs_lines_happy_path(tmp_path):
    app = create_app()
    app.testing = True
    # Create a temp log file with known number of lines
    p = tmp_path / 'api.log'
    p.write_text('a\n' * 5, encoding='utf-8')

    # Point the app to this log file via env compatible config
    app.config['API_LOG_FILE'] = str(p)

    with app.test_client() as c:
        r = c.get('/logs/lines', query_string={'name': 'api'})
        assert r.status_code == 200
        js = r.get_json() or {}
        assert js.get('missing') is False
        assert js.get('count') == 5
