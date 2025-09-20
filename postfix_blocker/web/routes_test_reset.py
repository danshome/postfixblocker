"""Test-only reset endpoints.

from __future__ import annotations

WARNING: This blueprint is intended strictly for automated tests. It provides a
single POST /test/reset endpoint that clears the application tables to a
baseline state for the ACTIVE database used by this API instance.

Enable by setting environment variable TEST_RESET_ENABLE=1 for the API process.
In production images, this should remain disabled.
"""

import os
from typing import Any, cast

from flask import Blueprint, abort, current_app, jsonify, request
from sqlalchemy import delete

from ..db.schema import get_blocked_table, get_props_table

bp = Blueprint('test_reset', __name__)


@bp.route('/test/dump', methods=['GET'])
def dump_state():
    """Dump normalized state for comparisons (test-only).

    Returns JSON with two arrays:
      - blocked: [{pattern, is_regex, test_mode}]
      - props: [{key, value}]
    """
    if os.environ.get('TEST_RESET_ENABLE', '0') != '1':
        abort(403)
    ensure_db_ready = current_app.config.get('ensure_db_ready')
    if callable(ensure_db_ready):
        if not ensure_db_ready():
            return jsonify({'error': 'database not ready'}), 503
    eng = cast(Any, current_app.config.get('db_engine'))
    bt = get_blocked_table()
    pt = get_props_table()
    blocked: list[dict[str, Any]] = []
    props: list[dict[str, Any]] = []
    with eng.connect() as conn:
        for row in conn.execute(
            bt.select().with_only_columns(bt.c.pattern, bt.c.is_regex, bt.c.test_mode)
        ):
            blocked.append({'pattern': row[0], 'is_regex': bool(row[1]), 'test_mode': bool(row[2])})
        for row in conn.execute(pt.select().with_only_columns(pt.c.key, pt.c.value)):
            props.append({'key': row[0], 'value': row[1]})
    blocked.sort(key=lambda x: (x['pattern'], x['is_regex'], x['test_mode']))
    props.sort(key=lambda x: (x['key'] or ''))
    return jsonify({'blocked': blocked, 'props': props})


@bp.route('/test/reset', methods=['POST'])
def reset_state():
    """Reset DB state to a deterministic baseline for tests.

    Operations:
      - DELETE FROM blocked_addresses
      - DELETE FROM cris_props

    Notes:
      - We do not attempt to reset IDENTITY/SEQUENCE counters because the
        cross-DB comparison utility ignores volatile columns like `id` and
        `updated_at`.
    """
    # Basic guard: refuse when env flag not enabled
    if os.environ.get('TEST_RESET_ENABLE', '0') != '1':
        abort(403)

    ensure_db_ready = current_app.config.get('ensure_db_ready')
    if callable(ensure_db_ready):
        if not ensure_db_ready():
            return jsonify({'error': 'database not ready'}), 503
    eng = cast(Any, current_app.config.get('db_engine'))

    bt = get_blocked_table()
    pt = get_props_table()

    # Optional seeds can be provided by tests
    payload = request.get_json(silent=True) or {}
    seeds = payload.get('seeds') or []

    deleted_blocked = 0
    deleted_props = 0

    with eng.begin() as conn:
        deleted_blocked = conn.execute(delete(bt)).rowcount or 0
        deleted_props = conn.execute(delete(pt)).rowcount or 0
        # Seed initial entries if provided
        for seed in seeds:
            patt = str(seed.get('pattern') or '').strip()
            if not patt:
                continue
            is_regex = bool(seed.get('is_regex', False))
            test_mode = bool(seed.get('test_mode', True))
            conn.execute(bt.insert().values(pattern=patt, is_regex=is_regex, test_mode=test_mode))

    return jsonify(
        {
            'status': 'ok',
            'deleted': {
                'blocked_addresses': deleted_blocked,
                'cris_props': deleted_props,
            },
            'seeded': len(seeds),
        }
    )
