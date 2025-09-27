from __future__ import annotations

import pytest

try:
    from sqlalchemy import create_engine
except Exception:  # pragma: no cover - SQLAlchemy may be missing in minimal envs
    create_engine = None  # type: ignore

from postfix_blocker.db.migrations import init_db
from postfix_blocker.web.app_factory import create_app


@pytest.mark.unit
@pytest.mark.skipif(create_engine is None, reason='SQLAlchemy not installed')
def test_routes_logs_and_addresses_error_branches(monkeypatch):
    eng = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(eng)

    app = create_app()
    app.testing = True
    app.config['db_engine'] = eng
    app.config['ensure_db_ready'] = lambda: True

    with app.test_client() as c:
        # routes_logs: invalid service -> 404
        r404 = c.get('/logs/level/notaservice')
        assert r404.status_code == 404

        # routes_logs: tail with invalid name -> 400
        r400 = c.get('/logs/tail', query_string={'name': 'bogus'})
        assert r400.status_code == 400

        # routes_logs: lines with invalid name -> 400
        r400b = c.get('/logs/lines', query_string={'name': ''})
        assert r400b.status_code == 400

        # routes_addresses: invalid page/size/dir/sort params should not crash and use defaults
        r = c.get(
            '/addresses',
            query_string={
                'page': 'notint',
                'page_size': '-5',
                'sort': 'unknown',
                'dir': 'sideways',
            },
        )
        assert r.status_code == 200
        js = r.get_json() or {}
        assert 'items' in js and 'total' in js

        # routes_addresses: filter flags parsing for f_is_regex values
        # Add two entries (regex and non-regex)
        c.post('/addresses', json={'pattern': 'a', 'is_regex': False})
        c.post('/addresses', json={'pattern': '.*@x', 'is_regex': True})
        r_true = c.get(
            '/addresses',
            query_string={'f_is_regex': 'true', 'page': '1', 'page_size': '10'},
        )
        assert r_true.status_code == 200
        js_true = r_true.get_json()
        items_true = js_true if isinstance(js_true, list) else (js_true or {}).get('items', [])
        assert any(it['is_regex'] for it in items_true)
        r_false = c.get(
            '/addresses',
            query_string={'f_is_regex': 'no', 'page': '1', 'page_size': '10'},
        )
        assert r_false.status_code == 200
        js_false = r_false.get_json()
        items_false = js_false if isinstance(js_false, list) else (js_false or {}).get('items', [])
        assert all(not it['is_regex'] for it in items_false)
