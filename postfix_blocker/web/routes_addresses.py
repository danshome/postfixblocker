from __future__ import annotations

import logging
import os
from typing import Any, cast

from flask import Blueprint, abort, current_app, jsonify, request
from sqlalchemy import func, inspect, select

from ..db.schema import get_blocked_table

bp = Blueprint('addresses', __name__)

# Constants
ROUTE_ADDRESSES = '/addresses'
KEY_ERROR = 'error'
ERR_DB_NOT_READY = 'database not ready'
KEY_STATUS = 'status'
STATUS_OK = 'ok'
STATUS_DELETED = 'deleted'
KEY_PATTERN = 'pattern'
KEY_IS_REGEX = 'is_regex'
KEY_TEST_MODE = 'test_mode'


@bp.route(ROUTE_ADDRESSES, methods=['GET'])
def list_addresses():
    ensure_db_ready = current_app.config.get('ensure_db_ready')
    if callable(ensure_db_ready):
        if not ensure_db_ready():
            return jsonify({KEY_ERROR: ERR_DB_NOT_READY}), 503
    args = request.args
    paged = any(k in args for k in ('page', 'page_size', 'q', 'sort', 'dir'))
    bt = get_blocked_table()
    eng = cast(Any, current_app.config.get('db_engine'))
    if not paged:
        with eng.connect() as conn:
            try:
                rows = list(conn.execute(select(bt)))
            except Exception as exc:
                logging.getLogger('api').debug('Unpaged list query failed: %s', exc)
                rows = []
        return jsonify(
            [
                {
                    'id': r.id,
                    KEY_PATTERN: r.pattern,
                    KEY_IS_REGEX: r.is_regex,
                    KEY_TEST_MODE: bool(getattr(r, 'test_mode', True)),
                }
                for r in rows
            ]
        )

    # Defaults
    try:
        page = max(int(args.get('page', 1)), 1)
    except Exception:
        page = 1
    try:
        page_size = min(max(int(args.get('page_size', 25)), 1), 500)
    except Exception:
        page_size = 25
    q = (args.get('q') or '').strip()
    f_pattern = (args.get('f_pattern') or '').strip()
    f_id = (args.get('f_id') or '').strip()
    f_is_regex = (args.get('f_is_regex') or '').strip().lower()
    sort = (args.get('sort') or 'pattern').strip()
    direction = (args.get('dir') or 'asc').lower()
    if direction not in ('asc', 'desc'):
        direction = 'asc'

    filters = []
    if q:
        q_like = f'%{q.upper()}%'
        filters.append(func.upper(bt.c.pattern).like(q_like))
    if f_pattern:
        fp_like = f'%{f_pattern.upper()}%'
        filters.append(func.upper(bt.c.pattern).like(fp_like))
    if f_id:
        try:
            fid = int(f_id)
        except ValueError:
            fid = None
        if fid is not None:
            filters.append(bt.c.id == fid)
    if f_is_regex in ('1', 'true', 't', 'yes', 'y'):
        filters.append(bt.c.is_regex.is_(True))
    elif f_is_regex in ('0', 'false', 'f', 'no', 'n'):
        filters.append(bt.c.is_regex.is_(False))

    sort_columns = {
        'id': bt.c.id,
        'pattern': bt.c.pattern,
        'is_regex': bt.c.is_regex,
        'updated_at': bt.c.updated_at,
        'test_mode': getattr(bt.c, 'test_mode', bt.c.is_regex),
    }
    order_col = sort_columns.get(sort, bt.c.pattern)
    order_by = order_col.asc() if direction == 'asc' else order_col.desc()

    offset = (page - 1) * page_size
    with eng.connect() as conn:
        total = conn.execute(select(func.count()).select_from(bt).where(*filters)).scalar() or 0
        stmt = select(bt).where(*filters).order_by(order_by).offset(offset).limit(page_size)
        try:
            rows = list(conn.execute(stmt))
        except Exception:
            rows = []
    return jsonify(
        {
            'items': [
                {
                    'id': r.id,
                    KEY_PATTERN: r.pattern,
                    KEY_IS_REGEX: r.is_regex,
                    KEY_TEST_MODE: bool(getattr(r, 'test_mode', True)),
                }
                for r in rows
            ],
            'total': int(total),
            'page': page,
            'page_size': page_size,
            'sort': sort,
            'dir': direction,
            'q': q,
        }
    )


@bp.route(ROUTE_ADDRESSES, methods=['POST'])
def add_address():
    ensure_db_ready = current_app.config.get('ensure_db_ready')
    if callable(ensure_db_ready):
        if not ensure_db_ready():
            return jsonify({KEY_ERROR: ERR_DB_NOT_READY}), 503
    data = request.get_json(force=True)
    pattern = data.get(KEY_PATTERN)
    is_regex = bool(data.get(KEY_IS_REGEX, False))
    test_mode = bool(data.get(KEY_TEST_MODE, True))
    if not pattern:
        abort(400, 'pattern is required')
    eng = cast(Any, current_app.config.get('db_engine'))
    with eng.connect() as conn:
        try:
            values = {KEY_PATTERN: pattern, KEY_IS_REGEX: is_regex}
            bt = get_blocked_table()
            try:
                insp = inspect(eng)
                cols = {c.get('name', '').lower() for c in insp.get_columns(bt.name)}
                if KEY_TEST_MODE in cols:
                    values[KEY_TEST_MODE] = test_mode
            except Exception as exc:
                logging.getLogger('api').debug(
                    'Column inspection failed; proceeding without test_mode: %s', exc
                )
            conn.execute(bt.insert().values(**values))
            conn.commit()
        except Exception as e:
            # Unique constraint handling is backend-specific; fall back to 409 based on message
            msg = str(e).lower()
            if 'duplicate' in msg or 'unique' in msg:
                abort(409, 'pattern already exists')
            raise
    _notify_blocker_refresh()
    return {KEY_STATUS: STATUS_OK}, 201


@bp.route('/addresses/<int:entry_id>', methods=['DELETE'])
def delete_address(entry_id: int):
    ensure_db_ready = current_app.config.get('ensure_db_ready')
    if callable(ensure_db_ready):
        if not ensure_db_ready():
            return jsonify({KEY_ERROR: ERR_DB_NOT_READY}), 503
    eng = cast(Any, current_app.config.get('db_engine'))
    bt = get_blocked_table()
    with eng.connect() as conn:
        conn.execute(bt.delete().where(bt.c.id == entry_id))
        conn.commit()
    _notify_blocker_refresh()
    return {KEY_STATUS: STATUS_DELETED}


@bp.route('/addresses/<int:entry_id>', methods=['PUT', 'PATCH'])
def update_address(entry_id: int):
    ensure_db_ready = current_app.config.get('ensure_db_ready')
    if callable(ensure_db_ready):
        if not ensure_db_ready():
            return jsonify({KEY_ERROR: ERR_DB_NOT_READY}), 503
    data = request.get_json(force=True) or {}
    updates = {}
    if KEY_PATTERN in data and (data[KEY_PATTERN] or '').strip():
        updates[KEY_PATTERN] = data[KEY_PATTERN].strip()
    if KEY_IS_REGEX in data:
        updates[KEY_IS_REGEX] = bool(data[KEY_IS_REGEX])
    if KEY_TEST_MODE in data:
        updates[KEY_TEST_MODE] = bool(data[KEY_TEST_MODE])
    if not updates:
        abort(400, 'no updatable fields provided')

    bt = get_blocked_table()
    eng = cast(Any, current_app.config.get('db_engine'))
    with eng.connect() as conn:
        try:
            res = conn.execute(bt.update().where(bt.c.id == entry_id).values(**updates))
            if res.rowcount == 0:
                abort(404)
            conn.commit()
        except Exception as e:
            msg = str(e).lower()
            if 'duplicate' in msg or 'unique' in msg:
                abort(409, 'pattern already exists')
            raise
    _notify_blocker_refresh()
    return {KEY_STATUS: STATUS_OK}


# --- Optional Blocker refresh notification (signal-based IPC) ---
def _notify_blocker_refresh() -> None:
    pid_file = os.environ.get('BLOCKER_PID_FILE', '/var/run/postfix-blocker/blocker.pid')
    try:
        with open(pid_file, encoding='utf-8') as f:
            pid_s = (f.read() or '').strip()
        if not pid_s:
            return
        pid = int(pid_s)
        import os as _os
        import signal

        _os.kill(pid, signal.SIGUSR1)
    except Exception as exc:  # pragma: no cover - optional/ephemeral
        logging.getLogger('api').debug('Blocker signal notify failed: %s', exc)
