from __future__ import annotations

import pytest

try:
    from sqlalchemy import create_engine, text
except Exception:  # pragma: no cover - SQLAlchemy may be missing in minimal envs
    create_engine = None  # type: ignore
    text = None  # type: ignore

from postfix_blocker.db.migrations import init_db
from postfix_blocker.web.app_factory import create_app


@pytest.mark.unit
@pytest.mark.skipif(create_engine is None, reason='SQLAlchemy not installed')
def test_addresses_crud_and_paging(monkeypatch):
    # Prepare in-memory DB and app
    engine = create_engine('sqlite:///:memory:')  # type: ignore[misc]
    init_db(engine)

    app = create_app()
    app.testing = True
    # Inject our engine and bypass ensure_db_ready
    app.config['db_engine'] = engine
    app.config['ensure_db_ready'] = lambda: True

    with app.test_client() as c:
        # Unpaged list returns [] initially
        r0 = c.get('/addresses')
        assert r0.status_code == 200
        data0 = r0.get_json()
        assert isinstance(data0, list)
        assert data0 == []

        # Add several entries
        for patt, is_rx, tm in [('a@example.com', False, True), ('b@example.com', False, False)]:
            ra = c.post('/addresses', json={'pattern': patt, 'is_regex': is_rx, 'test_mode': tm})
            assert ra.status_code == 201
            assert (ra.get_json() or {}).get('status') == 'ok'

        # Paged list reports shape with items/total
        r1 = c.get(
            '/addresses',
            query_string={'page': '1', 'page_size': '10', 'sort': 'id', 'dir': 'asc'},
        )
        assert r1.status_code == 200
        js1 = r1.get_json() or {}
        assert isinstance(js1.get('items'), list)
        assert int(js1.get('total') or 0) >= 2
        ids = [it['id'] for it in js1['items']]

        # Update first entry pattern and toggle test_mode
        first_id = int(ids[0])
        ru = c.put(f'/addresses/{first_id}', json={'pattern': 'alpha@example.com'})
        assert ru.status_code == 200
        # Toggle test_mode (True->False or False->True depending on original)
        ru2 = c.put(f'/addresses/{first_id}', json={'test_mode': False})
        assert ru2.status_code == 200

        # Update with no fields -> 400
        r_bad = c.put(f'/addresses/{first_id}', json={})
        assert r_bad.status_code == 400

        # Update non-existent id -> 404
        r404 = c.put('/addresses/99999', json={'pattern': 'x'})
        assert r404.status_code == 404

        # Delete first entry
        rd = c.delete(f'/addresses/{first_id}')
        assert rd.status_code == 200
        assert (rd.get_json() or {}).get('status') == 'deleted'

        # Final list should still be reachable
        r2 = c.get('/addresses')
        assert r2.status_code == 200
        data2 = r2.get_json()
        assert isinstance(data2, list)
        # At least one remaining entry
        assert len(data2) >= 1
