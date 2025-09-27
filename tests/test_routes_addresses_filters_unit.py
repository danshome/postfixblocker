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
def test_addresses_filters_sorting_and_direction(monkeypatch):
    eng = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(eng)

    app = create_app()
    app.testing = True
    app.config['db_engine'] = eng
    app.config['ensure_db_ready'] = lambda: True

    with app.test_client() as c:
        # Seed entries
        c.post(
            '/addresses',
            json={'pattern': 'alpha@example.com', 'is_regex': False, 'test_mode': True},
        )
        c.post(
            '/addresses',
            json={'pattern': 'beta@example.com', 'is_regex': False, 'test_mode': False},
        )
        c.post('/addresses', json={'pattern': '.*@corp.com', 'is_regex': True})

        # Quick search q=beta
        r_q = c.get('/addresses', query_string={'q': 'beta', 'page': '1', 'page_size': '10'})
        js_q = r_q.get_json() or {}
        assert any('beta' in it['pattern'] for it in js_q.get('items', []))

        # f_pattern filter
        r_fp = c.get(
            '/addresses',
            query_string={'f_pattern': 'corp', 'page': '1', 'page_size': '10'},
        )
        js_fp = r_fp.get_json() or {}
        assert all('corp' in it['pattern'] for it in js_fp.get('items', []))

        # f_id exact match (use an id from previous response if available, else 1)
        some_id = (js_q.get('items') or [{}])[0].get('id', 1)
        r_fid = c.get(
            '/addresses',
            query_string={'f_id': str(some_id), 'page': '1', 'page_size': '10'},
        )
        js_fid = r_fid.get_json() or {}
        assert all(it['id'] == some_id for it in js_fid.get('items', []))

        # Sort by id desc
        r_sort = c.get(
            '/addresses',
            query_string={'sort': 'id', 'dir': 'desc', 'page': '1', 'page_size': '10'},
        )
        assert r_sort.status_code == 200
        js_sort = r_sort.get_json() or {}
        items = js_sort.get('items', [])
        assert items == sorted(items, key=lambda e: e['id'], reverse=True)
