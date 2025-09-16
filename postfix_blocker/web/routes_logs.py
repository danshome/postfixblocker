from __future__ import annotations

import logging
import os
from typing import Any, cast

from flask import Blueprint, abort, current_app, jsonify, request

from ..db.props import LINES_KEYS, LOG_KEYS, REFRESH_KEYS, get_prop, set_prop
from ..logging_setup import set_logger_level
from ..postfix.log_level import apply_postfix_log_level, resolve_mail_log_path
from ..services.log_tail import tail_file

bp = Blueprint('logs', __name__)

KEY_ERROR = 'error'
ERR_DB_NOT_READY = 'database not ready'
KEY_STATUS = 'status'
STATUS_OK = 'ok'


@bp.route('/logs/level/<service>', methods=['GET', 'PUT'])
def log_level(service: str):
    if service not in LOG_KEYS:
        abort(404)
    ensure_db_ready = current_app.config.get('ensure_db_ready')
    if callable(ensure_db_ready):
        if not ensure_db_ready():
            return jsonify({KEY_ERROR: ERR_DB_NOT_READY}), 503
    eng = cast(Any, current_app.config.get('db_engine'))
    key = LOG_KEYS[service]
    if request.method == 'GET':
        val = get_prop(eng, key, None)
        logging.getLogger('api').debug('Get log level service=%s level=%s', service, val)
        return jsonify({'service': service, 'level': val})
    data = request.get_json(force=True) or {}
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
def tail_log():
    name = (request.args.get('name') or '').strip().lower()
    try:
        lines = max(min(int(request.args.get('lines', '200')), 2000), 1)
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
    if not os.path.exists(path):
        return jsonify({'name': name, 'path': path, 'content': '', 'missing': True})
    try:
        content = tail_file(path, lines)
    except Exception as exc:
        logging.getLogger('api').debug('Tail read failed: %s', exc)
        content = ''
    return jsonify({'name': name, 'path': path, 'content': content, 'missing': False})


@bp.route('/logs/refresh/<name>', methods=['GET', 'PUT'])
def refresh_interval(name: str):
    name = name.lower()
    if name not in REFRESH_KEYS:
        abort(404)
    ensure_db_ready = current_app.config.get('ensure_db_ready')
    if callable(ensure_db_ready):
        if not ensure_db_ready():
            return jsonify({KEY_ERROR: ERR_DB_NOT_READY}), 503
    eng = cast(Any, current_app.config.get('db_engine'))
    if request.method == 'GET':
        ms = int(get_prop(eng, REFRESH_KEYS[name], '0') or '0')
        lines = int(get_prop(eng, LINES_KEYS[name], '200') or '200')
        logging.getLogger('api').debug(
            'Get refresh settings name=%s interval_ms=%s lines=%s', name, ms, lines
        )
        return jsonify({'name': name, 'interval_ms': ms, 'lines': lines})
    data = request.get_json(force=True) or {}
    ms_s = str(int(data.get('interval_ms', 0)))
    lines_s = str(int(data.get('lines', 200)))
    logging.getLogger('api').debug(
        'Set refresh settings name=%s interval_ms=%s lines=%s', name, ms_s, lines_s
    )
    set_prop(eng, REFRESH_KEYS[name], ms_s)
    set_prop(eng, LINES_KEYS[name], lines_s)
    return jsonify({KEY_STATUS: STATUS_OK})
