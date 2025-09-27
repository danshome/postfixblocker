from __future__ import annotations

import pytest

from postfix_blocker.web.app_factory import create_app


@pytest.mark.unit
def test_list_addresses_not_ready_returns_503(monkeypatch):
    app = create_app()
    # Force ensure_db_ready to be present and return False to exercise 503 path
    app.config['ensure_db_ready'] = lambda: False

    with app.test_client() as client:
        resp = client.get('/addresses')
        assert resp.status_code == 503
        assert resp.get_json().get('error')


class _BadConn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    def execute(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError('boom')


class _BadEngine:
    def connect(self):  # type: ignore[no-untyped-def]
        return _BadConn()


@pytest.mark.unit
def test_list_addresses_unpaged_handles_query_error(monkeypatch):
    app = create_app()
    # Pretend DB is ready and install an engine whose select fails in unpaged path
    app.config['ensure_db_ready'] = lambda: True
    app.config['db_engine'] = _BadEngine()

    with app.test_client() as client:
        resp = client.get('/addresses')
        assert resp.status_code == 200
        assert resp.get_json() == []


class _Result0:
    def scalar(self) -> int:
        return 0


class _PagedConn:
    def __init__(self) -> None:
        self._calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):  # type: ignore[no-untyped-def]
        return False

    def execute(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
        # First execute is for SELECT COUNT ... -> return a result with scalar()
        if self._calls == 0:
            self._calls += 1
            return _Result0()
        # Second execute (the actual statement) should raise to hit except path
        raise RuntimeError('boom')


class _PagedEngine:
    def connect(self):  # type: ignore[no-untyped-def]
        return _PagedConn()


@pytest.mark.unit
def test_list_addresses_paged_parsing_defaults_and_exec_error(monkeypatch):
    app = create_app()
    app.config['ensure_db_ready'] = lambda: True
    app.config['db_engine'] = _PagedEngine()

    with app.test_client() as client:
        # Supply bad page_size and f_id values to exercise defaults and parsing guards
        resp = client.get('/addresses', query_string={'page': 2, 'page_size': 'xx', 'f_id': 'bad'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['page'] == 2
        assert data['page_size'] == 25  # default when parsing fails
        assert isinstance(data['items'], list)
        assert data['total'] == 0
