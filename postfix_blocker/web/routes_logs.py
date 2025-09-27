from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable, cast

from flask import Blueprint, abort, current_app, jsonify, request
from flask.typing import ResponseReturnValue
from sqlalchemy.engine import Engine

from ..db.props import LINES_KEYS, LOG_KEYS, REFRESH_KEYS, get_prop, set_prop
from ..logging_setup import set_logger_level
from ..postfix.log_level import apply_postfix_log_level, resolve_mail_log_path
from ..services.log_tail import tail_file
from .auth import login_required

bp = Blueprint('logs', __name__)

KEY_ERROR = 'error'
ERR_DB_NOT_READY = 'database not ready'
KEY_STATUS = 'status'
STATUS_OK = 'ok'


@bp.route('/logs/level/<service>', methods=['GET', 'PUT'])
@login_required
def log_level(service: str) -> ResponseReturnValue:
    """Get or set the log level for a service (api|blocker|postfix).

    Methods:
      - GET:  Returns current level: {"service": <name>, "level": <str|None>}
      - PUT:  Body JSON {"level": "WARNING|INFO|DEBUG|<number>"} persists the level.
              For service=api the in-process logger is updated.
              For service=postfix, Postfix main.cf is updated and Postfix reloaded.

    Errors:
      - 404 if service is not one of LOG_KEYS (api, blocker, postfix)
      - 503 if the database is not ready
      - 400 if level is missing on PUT
    """
    if service not in LOG_KEYS:
        abort(404)
    _raw = current_app.config.get('ensure_db_ready')
    ensure_db_ready: Callable[[], bool] | None = (
        cast(Callable[[], bool], _raw) if callable(_raw) else None
    )
    if ensure_db_ready is not None and not ensure_db_ready():
        return jsonify({KEY_ERROR: ERR_DB_NOT_READY}), 503
    eng: Engine = cast(Engine, current_app.config.get('db_engine'))
    key = LOG_KEYS[service]
    if request.method == 'GET':
        val = get_prop(eng, key, None)
        logging.getLogger('api').debug('Get log level service=%s level=%s', service, val)
        return jsonify({'service': service, 'level': val})
    data: dict[str, Any] = cast(dict[str, Any], request.get_json(force=True) or {})
    level_s = str(data.get('level') or '').strip()
    if not level_s:
        abort(400, 'level is required')
    logging.getLogger('api').debug('Set log level service=%s level=%s', service, level_s)
    set_prop(eng, key, level_s)
    if service == 'api':
        set_logger_level(level_s)
    elif service == 'postfix':
        apply_postfix_log_level(level_s)
    return jsonify({KEY_STATUS: STATUS_OK})


@bp.route('/logs/tail', methods=['GET'])
@login_required
def tail_log() -> ResponseReturnValue:
    """Return the last N lines of a known log file.

    Query params:
      - name: one of api, blocker, postfix
      - lines: integer (default 200), capped at 8000

    Response JSON: { name, path, content, missing }
    """
    name: str = (request.args.get('name') or '').strip().lower()
    try:
        # Allow larger tails for heavy postfix logs; cap at 8000
        lines: int = max(min(int(request.args.get('lines', '200')), 8000), 1)
    except Exception:
        lines = 200
    if name not in ('api', 'blocker', 'postfix'):
        abort(400, 'unknown log name')
    if name == 'api':
        path = (
            current_app.config.get('API_LOG_FILE')
            or os.environ.get('API_LOG_FILE')
            or './logs/api.log'
        )
    elif name == 'blocker':
        path = (
            current_app.config.get('BLOCKER_LOG_FILE')
            or os.environ.get('BLOCKER_LOG_FILE')
            or './logs/blocker.log'
        )
    else:
        path = resolve_mail_log_path()
    logging.getLogger('api').debug('Tail request name=%s lines=%s path=%s', name, lines, path)
    if not Path(path).exists():
        return jsonify({'name': name, 'path': path, 'content': '', 'missing': True})
    try:
        content: str = tail_file(path, lines)
    except Exception as exc:
        logging.getLogger('api').debug('Tail read failed: %s', exc)
        content = ''
    return jsonify({'name': name, 'path': path, 'content': content, 'missing': False})


@bp.route('/logs/lines', methods=['GET'])
@login_required
def lines_count() -> ResponseReturnValue:
    """Return the line count for a known log name (api|blocker|postfix).

    Query params:
      - name: one of api, blocker, postfix

    Response JSON: { name, path, count, missing }
    """
    name: str = (request.args.get('name') or '').strip().lower()
    if name not in ('api', 'blocker', 'postfix'):
        abort(400, 'unknown log name')
    if name == 'api':
        path = (
            current_app.config.get('API_LOG_FILE')
            or os.environ.get('API_LOG_FILE')
            or './logs/api.log'
        )
    elif name == 'blocker':
        path = (
            current_app.config.get('BLOCKER_LOG_FILE')
            or os.environ.get('BLOCKER_LOG_FILE')
            or './logs/blocker.log'
        )
    else:
        path = resolve_mail_log_path()
    logging.getLogger('api').debug('Lines count request name=%s path=%s', name, path)
    if not Path(path).exists():
        return jsonify({'name': name, 'path': path, 'count': 0, 'missing': True})
    count: int = 0
    try:
        with Path(path).open(encoding='utf-8', errors='replace') as f:
            for _ in f:
                count += 1
    except Exception as exc:
        logging.getLogger('api').debug('Lines count read failed: %s', exc)
        count = 0
    return jsonify({'name': name, 'path': path, 'count': count, 'missing': False})


@bp.route('/logs/refresh/<name>', methods=['GET', 'PUT'])
@login_required
def refresh_interval(name: str) -> ResponseReturnValue:
    """Get or set UI refresh settings for a log view.

    Path param:
      - name: one of api, blocker, postfix

    Methods:
      - GET: returns { name, interval_ms, lines }
      - PUT: body JSON { interval_ms: number, lines: number } persists values

    Returns 404 if name is invalid; 503 if DB is not ready.
    """
    name = name.lower()
    if name not in REFRESH_KEYS:
        abort(404)
    _raw = current_app.config.get('ensure_db_ready')
    ensure_db_ready: Callable[[], bool] | None = (
        cast(Callable[[], bool], _raw) if callable(_raw) else None
    )
    if ensure_db_ready is not None and not ensure_db_ready():
        return jsonify({KEY_ERROR: ERR_DB_NOT_READY}), 503
    eng: Engine = cast(Engine, current_app.config.get('db_engine'))
    if request.method == 'GET':
        ms = int(get_prop(eng, REFRESH_KEYS[name], '5000') or '5000')
        lines = int(get_prop(eng, LINES_KEYS[name], '100') or '100')
        logging.getLogger('api').debug(
            'Get refresh settings name=%s interval_ms=%s lines=%s',
            name,
            ms,
            lines,
        )
        return jsonify({'name': name, 'interval_ms': ms, 'lines': lines})
    data: dict[str, Any] = cast(dict[str, Any], request.get_json(force=True) or {})
    ms_s: str = str(int(data.get('interval_ms', 0)))
    lines_s: str = str(int(data.get('lines', 200)))
    logging.getLogger('api').debug(
        'Set refresh settings name=%s interval_ms=%s lines=%s',
        name,
        ms_s,
        lines_s,
    )
    set_prop(eng, REFRESH_KEYS[name], ms_s)
    set_prop(eng, LINES_KEYS[name], lines_s)
    return jsonify({KEY_STATUS: STATUS_OK})
