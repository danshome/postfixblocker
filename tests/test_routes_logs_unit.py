from __future__ import annotations

import os
import tempfile

import pytest

try:
    from sqlalchemy import create_engine
except Exception:  # pragma: no cover - SQLAlchemy may be missing in minimal envs
    create_engine = None  # type: ignore

from postfix_blocker.db.migrations import init_db
from postfix_blocker.web.app_factory import create_app


@pytest.mark.unit
@pytest.mark.skipif(create_engine is None, reason='SQLAlchemy not installed')
def test_logs_level_refresh_tail_and_lines(monkeypatch):
    engine = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(engine)

    app = create_app()
    app.testing = True
    app.config['db_engine'] = engine
    app.config['ensure_db_ready'] = lambda: True

    with tempfile.TemporaryDirectory() as td:
        api_log = os.path.join(td, 'api.log')
        # Create a small log file
        with open(api_log, 'w', encoding='utf-8') as f:
            f.write('line1\nline2\nline3\n')
        # Point API_LOG_FILE env to our temp file
        monkeypatch.setenv('API_LOG_FILE', api_log)

        with app.test_client() as c:
            # GET current level for api (seeded to INFO)
            r1 = c.get('/logs/level/api')
            assert r1.status_code == 200
            assert (r1.get_json() or {}).get('level') in (None, 'INFO')

            # PUT level -> DEBUG (also updates in-process logger)
            r2 = c.put('/logs/level/api', json={'level': 'DEBUG'})
            assert r2.status_code == 200
            assert (r2.get_json() or {}).get('status') == 'ok'

            # GET refresh defaults (seeded by props)
            r3 = c.get('/logs/refresh/api')
            assert r3.status_code == 200
            js = r3.get_json() or {}
            assert int(js.get('interval_ms') or 0) > 0
            assert int(js.get('lines') or 0) > 0

            # PUT refresh updates
            r4 = c.put('/logs/refresh/api', json={'interval_ms': 7500, 'lines': 250})
            assert r4.status_code == 200
            r5 = c.get('/logs/refresh/api')
            js5 = r5.get_json() or {}
            assert js5.get('interval_ms') == 7500
            assert js5.get('lines') == 250

            # Tail last 2 lines
            rt = c.get('/logs/tail', query_string={'name': 'api', 'lines': '2'})
            assert rt.status_code == 200
            content = (rt.get_json() or {}).get('content') or ''
            assert 'line3' in content

            # Count lines
            rl = c.get('/logs/lines', query_string={'name': 'api'})
            assert rl.status_code == 200
            assert (rl.get_json() or {}).get('missing') is False
            assert (rl.get_json() or {}).get('count') == 3
