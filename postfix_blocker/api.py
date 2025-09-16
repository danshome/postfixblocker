import logging
import os
import signal
import time
from typing import TYPE_CHECKING, Any, cast

from flask import Flask, abort, g, jsonify, request
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

# Support running both as part of the 'app' package and as a standalone script in the container
# Import as a module once to avoid mypy redefinition errors when falling back
try:
    from . import blocker as _blocker  # type: ignore
except Exception:  # pragma: no cover - fallback when executed as a script
    import importlib

    _blocker = importlib.import_module('blocker')  # type: ignore

# Re-export the required callables (runtime attributes; not for static typing)
get_blocked_table = _blocker.get_blocked_table  # type: ignore[attr-defined]
get_engine = _blocker.get_engine  # type: ignore[attr-defined]
init_db = _blocker.init_db  # type: ignore[attr-defined]
get_props_table = _blocker.get_props_table  # type: ignore[attr-defined]
get_prop = _blocker.get_prop  # type: ignore[attr-defined]
set_prop = _blocker.set_prop  # type: ignore[attr-defined]

if TYPE_CHECKING:
    pass

# Common string constants to avoid duplicated literals in code
ROUTE_ADDRESSES = '/addresses'

KEY_ERROR = 'error'
KEY_STATUS = 'status'
KEY_PATTERN = 'pattern'
KEY_IS_REGEX = 'is_regex'
KEY_TEST_MODE = 'test_mode'

ERR_DB_NOT_READY = 'database not ready'

STATUS_OK = 'ok'
STATUS_DELETED = 'deleted'

app = Flask(__name__)
# Lazily create engine to avoid import-time failures when DB drivers are missing
engine: Any = None

# Lazily initialize DB to avoid crashing API when backend is not yet ready
_db_ready = False


# ----- Logging setup & request logging -----
def _init_logging() -> None:
    # Resolve desired level from env; accept names (DEBUG) or ints (10)
    raw = (os.environ.get('API_LOG_LEVEL') or 'INFO').strip()
    level_name = raw.upper()
    try:
        level = int(raw)
    except Exception:
        level = getattr(logging, level_name, logging.INFO)

    app.logger.setLevel(level)
    root = logging.getLogger()
    root.setLevel(level)

    # Ensure existing handlers honor the configured level (Flask/werkzeug add their own)
    for h in list(app.logger.handlers) + list(root.handlers):
        try:
            h.setLevel(level)
        except Exception as exc:
            # Not all handlers allow setting level (or may be misconfigured)
            # Log at debug instead of silently ignoring to satisfy linters.
            app.logger.debug('Could not set handler level: %s', exc)
    # Optional file handler
    log_path = os.environ.get('API_LOG_FILE')
    if log_path:
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            from logging.handlers import RotatingFileHandler

            fh = RotatingFileHandler(log_path, maxBytes=10 * 1024 * 1024, backupCount=5)
            fh.setLevel(level)
            fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s %(message)s')
            fh.setFormatter(fmt)
            # Attach to both the Flask app logger and the root logger so any
            # library logs (e.g., werkzeug) are captured as well.
            app.logger.addHandler(fh)
            if not any(
                isinstance(h, RotatingFileHandler)
                and getattr(h, 'baseFilename', '') == fh.baseFilename
                for h in root.handlers
            ):
                root.addHandler(fh)
        except Exception as exc:  # pragma: no cover - filesystem/permissions
            app.logger.warning('Could not set up API file logging: %s', exc)
    # Log both requested and effective levels for easier troubleshooting
    app.logger.info(
        'API logging initialized (requested_level=%s effective_level=%s file=%s)',
        level_name,
        logging.getLevelName(app.logger.level),
        log_path or 'none',
    )
    app.logger.debug(
        'API logger handlers=%s root_handlers=%s',
        [type(h).__name__ for h in app.logger.handlers],
        [type(h).__name__ for h in root.handlers],
    )


@app.before_request
def _log_request_start() -> None:  # pragma: no cover - integration behavior
    g._start_time = time.time()
    try:
        qs = request.query_string.decode('utf-8') if request.query_string else ''
    except Exception:
        qs = ''
    app.logger.info(
        'API %s %s%s from=%s',
        request.method,
        request.path,
        f'?{qs}' if qs else '',
        request.remote_addr,
    )


@app.after_request
def _log_request_end(response):  # pragma: no cover - integration behavior
    try:
        start = getattr(g, '_start_time', None)
        dur_ms = (time.time() - start) * 1000.0 if start else 0.0
    except Exception:
        dur_ms = 0.0
    app.logger.info(
        'API done %s %s status=%s duration=%.1fms',
        request.method,
        request.path,
        response.status_code,
        dur_ms,
    )
    return response


@app.teardown_request
def _log_request_teardown(exc):  # pragma: no cover - integration behavior
    if exc is not None:
        app.logger.exception('API error on %s %s: %s', request.method, request.path, exc)


# Initialize logging once
_init_logging()


def ensure_db_ready() -> bool:
    """Ensure database schema is initialized; return True on success.

    Avoids process exit loops when the database is temporarily unavailable
    (e.g., DB2 taking minutes to initialize). Routes can respond gracefully
    while retrying on subsequent requests.
    """
    global _db_ready, engine
    if _db_ready:
        return True
    try:
        if engine is None:
            app.logger.debug('Creating SQLAlchemy engine for DB URL from blocker.get_engine()')
            engine = get_engine()
        app.logger.debug('Initializing database schema via init_db')
        init_db(engine)
        _db_ready = True
        app.logger.debug('Database schema ready (ensure_db_ready)')
        return True
    except Exception as exc:  # pragma: no cover - depends on external DB readiness
        # Keep API alive; callers can retry later
        app.logger.warning('DB init not ready: %s', exc)
        return False


def row_to_dict(row):
    # Support rows missing test_mode (older DBs) by defaulting to True
    test_mode = getattr(row, 'test_mode', True)
    return {
        'id': row.id,
        KEY_PATTERN: row.pattern,
        KEY_IS_REGEX: row.is_regex,
        KEY_TEST_MODE: bool(test_mode),
    }


@app.route(ROUTE_ADDRESSES, methods=['GET'])
def list_addresses():
    if not ensure_db_ready():
        return jsonify({KEY_ERROR: ERR_DB_NOT_READY}), 503
    # Optional server-side pagination, sorting, and search
    args = request.args
    paged = any(k in args for k in ('page', 'page_size', 'q', 'sort', 'dir'))
    bt = get_blocked_table()
    if not paged:
        eng = cast(Any, engine)
        with eng.connect() as conn:
            try:
                # Some DB2 drivers may return None from fetchall() on empty results;
                # iterating the Result is robust across backends.
                rows = list(conn.execute(select(bt)))
            except Exception as exc:
                app.logger.debug('Unpaged list query failed: %s', exc)
                rows = []
        app.logger.debug('List (unpaged) returned %d rows', len(rows))
        return jsonify([row_to_dict(r) for r in rows])

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

    # Build filters and ordering (portable across PG/DB2)
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
    eng = cast(Any, engine)
    with eng.connect() as conn:
        total = conn.execute(select(func.count()).select_from(bt).where(*filters)).scalar() or 0
        stmt = select(bt).where(*filters).order_by(order_by).offset(offset).limit(page_size)
        try:
            rows = list(conn.execute(stmt))
        except Exception:
            rows = []
    app.logger.debug(
        'List (paged) args=%s returned %d/%d rows (page=%d size=%d sort=%s dir=%s)',
        dict(args),
        len(rows),
        total,
        page,
        page_size,
        sort,
        direction,
    )
    return jsonify(
        {
            'items': [row_to_dict(r) for r in rows],
            'total': int(total),
            'page': page,
            'page_size': page_size,
            'sort': sort,
            'dir': direction,
            'q': q,
        }
    )


@app.route(ROUTE_ADDRESSES, methods=['POST'])
def add_address():
    if not ensure_db_ready():
        return jsonify({KEY_ERROR: ERR_DB_NOT_READY}), 503
    data = request.get_json(force=True)
    pattern = data.get(KEY_PATTERN)
    is_regex = bool(data.get(KEY_IS_REGEX, False))
    test_mode = bool(data.get(KEY_TEST_MODE, True))
    if not pattern:
        abort(400, 'pattern is required')
    app.logger.debug(
        'Add address request: pattern=%s is_regex=%s test_mode=%s', pattern, is_regex, test_mode
    )
    eng = cast(Any, engine)
    with eng.connect() as conn:
        try:
            values = {KEY_PATTERN: pattern, KEY_IS_REGEX: is_regex}
            bt = get_blocked_table()
            # Include test_mode only if the physical column exists; otherwise
            # rely on DB defaults or legacy schema without the column.
            try:
                insp = inspect(eng)
                cols = {c.get('name', '').lower() for c in insp.get_columns(bt.name)}
                if KEY_TEST_MODE in cols:
                    values[KEY_TEST_MODE] = test_mode
            except Exception as exc:
                app.logger.debug('Column inspection failed; proceeding without test_mode: %s', exc)
            conn.execute(bt.insert().values(**values))
            conn.commit()
            app.logger.debug('Inserted address row: %s', values)
        except IntegrityError:
            abort(409, 'pattern already exists')
    try:
        _notify_blocker_refresh()
    finally:
        pass
    return {KEY_STATUS: STATUS_OK}, 201


@app.route('/addresses/<int:entry_id>', methods=['DELETE'])
def delete_address(entry_id):
    if not ensure_db_ready():
        return jsonify({KEY_ERROR: ERR_DB_NOT_READY}), 503
    eng = cast(Any, engine)
    with eng.connect() as conn:
        bt = get_blocked_table()
        rc = conn.execute(bt.delete().where(bt.c.id == entry_id)).rowcount
        conn.commit()
        app.logger.debug('Delete address id=%s rowcount=%s', entry_id, rc)
    try:
        _notify_blocker_refresh()
    finally:
        pass
    return {KEY_STATUS: STATUS_DELETED}


@app.route('/addresses/<int:entry_id>', methods=['PUT', 'PATCH'])
def update_address(entry_id: int):
    """Update an address entry. Accepts JSON with optional fields:
    - pattern: string
    - is_regex: bool
    Returns 404 if the entry does not exist, 409 on unique conflict.
    """
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

    eng = cast(Any, engine)
    with eng.connect() as conn:
        try:
            res = conn.execute(bt.update().where(bt.c.id == entry_id).values(**updates))
            if res.rowcount == 0:
                abort(404)
            conn.commit()
            app.logger.debug('Update address id=%s updates=%s', entry_id, updates)
        except IntegrityError:
            abort(409, 'pattern already exists')
    try:
        _notify_blocker_refresh()
    finally:
        pass
    return {KEY_STATUS: STATUS_OK}


# --- Optional Blocker refresh notification (signal-based IPC) ---
def _notify_blocker_refresh() -> None:
    """Best-effort notify the blocker to refresh immediately via SIGUSR1.

    Reads the PID from BLOCKER_PID_FILE and sends SIGUSR1. Any errors are
    logged at debug level and ignored to avoid impacting API latency.
    """
    pid_file = os.environ.get('BLOCKER_PID_FILE', '/var/run/postfix-blocker/blocker.pid')
    try:
        with open(pid_file, encoding='utf-8') as f:
            pid_s = (f.read() or '').strip()
        if not pid_s:
            return
        pid = int(pid_s)
        os.kill(pid, signal.SIGUSR1)
    except Exception as exc:  # pragma: no cover - optional/ephemeral
        app.logger.debug('Blocker signal notify failed: %s', exc)


# ----- Logs/Props helpers -----
LOG_KEYS = {
    'api': 'log.level.api',
    'blocker': 'log.level.blocker',
    'postfix': 'log.level.postfix',
}
REFRESH_KEYS = {
    'api': 'log.refresh.api',
    'blocker': 'log.refresh.blocker',
    'postfix': 'log.refresh.postfix',
}
LINES_KEYS = {
    'api': 'log.lines.api',
    'blocker': 'log.lines.blocker',
    'postfix': 'log.lines.postfix',
}


def _coerce_level(val: str) -> int:
    try:
        return int(val)
    except Exception:
        return int(getattr(logging, val.upper(), logging.INFO))


def _set_api_log_level(level_s: str) -> None:
    lvl = _coerce_level(level_s)
    app.logger.setLevel(lvl)
    root = logging.getLogger()
    root.setLevel(lvl)
    for h in list(app.logger.handlers) + list(root.handlers):
        try:
            h.setLevel(lvl)
        except Exception as exc:
            app.logger.debug('Failed to set handler level: %s', exc)
    app.logger.info('API log level changed via props to %s', level_s)


def _postfix_mail_log_path() -> str:
    """Return the system mail log path for Postfix.

    Prefer /var/log/maillog, but fall back to /var/log/mail.log on
    distributions that use that filename (e.g., RHEL/Rocky). We only
    READ logs; we never write to these files.
    """
    preferred = '/var/log/maillog'
    fallback = '/var/log/mail.log'
    try:
        if os.path.exists(preferred) and os.path.getsize(preferred) > 0:
            return preferred
        if os.path.exists(fallback) and os.path.getsize(fallback) > 0:
            return fallback
    except Exception as exc:
        app.logger.debug('Unable to stat mail log paths: %s', exc)
    return preferred


def _update_postfix_log_level(level_s: str) -> None:
    """Apply a UI log level to Postfix config safely.

    Postfix expects a numeric value for debug_peer_level. Map common UI levels
    to numeric values per requirement: INFO=2, DEBUG=4, anything else=1. Numeric
    strings are accepted and clamped to [1, 4]. We also ensure debug_peer_list
    is set so verbosity applies to all peers in this environment.
    """

    # Map UI level to a numeric value for Postfix debug_peer_level
    def _map_level(s: str) -> int:
        s_up = (s or '').strip().upper()
        # Numeric strings: clamp to [1, 4]
        try:
            n = int(s_up)
            return max(1, min(n, 4))
        except Exception as exc:
            try:
                app.logger.debug('Invalid numeric postfix level: %s (%s)', s_up, exc)
            except Exception:
                # logging may not be initialized in some import-time contexts
                ...
        if s_up == 'DEBUG':
            return 4
        if s_up == 'INFO':
            return 2
        # Anything else (WARNING, ERROR, CRITICAL, etc.)
        return 1

    lvl_num = _map_level(level_s)

    main_cf = os.environ.get('POSTFIX_MAIN_CF', '/etc/postfix/main.cf')
    try:
        lines = []
        if os.path.exists(main_cf):
            with open(main_cf, encoding='utf-8') as f:
                lines = f.read().splitlines()
        new_lines = []
        found_level = False
        found_list = False
        for line in lines:
            s = line.strip()
            if s.startswith('debug_peer_level'):
                new_lines.append(f'debug_peer_level = {lvl_num}')
                found_level = True
            elif s.startswith('debug_peer_list'):
                # Route debug verbosity to all peers so tests can observe differences
                new_lines.append('debug_peer_list = 0.0.0.0/0')
                found_list = True
            else:
                new_lines.append(line)
        if not found_level:
            new_lines.append(f'debug_peer_level = {lvl_num}')
        if not found_list:
            new_lines.append('debug_peer_list = 0.0.0.0/0')
        with open(main_cf, 'w', encoding='utf-8') as f:
            f.write('\n'.join(new_lines) + '\n')
        app.logger.debug(
            'Updated postfix main.cf debug_peer_level=%s (from %s); debug_peer_list=0.0.0.0/0',
            lvl_num,
            level_s,
        )
        # Reload postfix
        try:
            import subprocess  # nosec B404

            subprocess.run(['/usr/sbin/postfix', 'reload'], check=False)  # nosec B603
        except Exception as exc:
            app.logger.warning('Postfix reload failed: %s', exc)
    except Exception as exc:
        app.logger.warning('Failed to update postfix main.cf: %s', exc)


@app.route('/logs/level/<service>', methods=['GET', 'PUT'])
def log_level(service: str):
    if service not in LOG_KEYS:
        abort(404)
    if not ensure_db_ready():
        return jsonify({KEY_ERROR: ERR_DB_NOT_READY}), 503
    eng = cast(Any, engine)
    key = LOG_KEYS[service]
    if request.method == 'GET':
        val = get_prop(eng, key, None)
        app.logger.debug('Get log level service=%s level=%s', service, val)
        return jsonify({'service': service, 'level': val})
    data = request.get_json(force=True) or {}
    level_s = str(data.get('level') or '').strip()
    if not level_s:
        abort(400, 'level is required')
    app.logger.debug('Set log level service=%s level=%s', service, level_s)
    set_prop(eng, key, level_s)
    if service == 'api':
        _set_api_log_level(level_s)
    elif service == 'postfix':
        _update_postfix_log_level(level_s)
    return jsonify({KEY_STATUS: STATUS_OK})


@app.route('/logs/tail', methods=['GET'])
def tail_log():
    name = (request.args.get('name') or '').strip().lower()
    try:
        lines = max(min(int(request.args.get('lines', '200')), 2000), 1)
    except Exception:
        lines = 200
    if name not in ('api', 'blocker', 'postfix'):
        abort(400, 'unknown log name')
    # Resolve path
    if name == 'api':
        path = os.environ.get('API_LOG_FILE') or './logs/api.log'
    elif name == 'blocker':
        path = os.environ.get('BLOCKER_LOG_FILE') or './logs/blocker.log'
    else:
        path = _postfix_mail_log_path()
    app.logger.debug('Tail request name=%s lines=%s path=%s', name, lines, path)
    if not os.path.exists(path):
        return jsonify({'name': name, 'path': path, 'content': '', 'missing': True})
    try:
        content = _tail_file(path, lines)
    except Exception as exc:
        app.logger.debug('Tail read failed: %s', exc)
        content = ''
    return jsonify({'name': name, 'path': path, 'content': content, 'missing': False})


def _tail_file(path: str, lines: int) -> str:
    # Deterministic and simple: read text and slice last N lines.
    # Adequate for typical log sizes in this app and robust across platforms.
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            all_lines = f.read().splitlines()
    except UnicodeDecodeError:
        # Fallback to binary decode
        with open(path, 'rb') as f:
            all_lines = f.read().decode('utf-8', errors='replace').splitlines()
    return '\n'.join(all_lines[-lines:])


@app.route('/logs/refresh/<name>', methods=['GET', 'PUT'])
def refresh_interval(name: str):
    name = name.lower()
    if name not in REFRESH_KEYS:
        abort(404)
    if not ensure_db_ready():
        return jsonify({KEY_ERROR: ERR_DB_NOT_READY}), 503
    eng = cast(Any, engine)
    if request.method == 'GET':
        ms = int(get_prop(eng, REFRESH_KEYS[name], '0') or '0')
        lines = int(get_prop(eng, LINES_KEYS[name], '200') or '200')
        app.logger.debug('Get refresh settings name=%s interval_ms=%s lines=%s', name, ms, lines)
        return jsonify({'name': name, 'interval_ms': ms, 'lines': lines})
    data = request.get_json(force=True) or {}
    ms_s = str(int(data.get('interval_ms', 0)))
    lines_s = str(int(data.get('lines', 200)))
    app.logger.debug('Set refresh settings name=%s interval_ms=%s lines=%s', name, ms_s, lines_s)
    set_prop(eng, REFRESH_KEYS[name], ms_s)
    set_prop(eng, LINES_KEYS[name], lines_s)
    return jsonify({KEY_STATUS: STATUS_OK})


if __name__ == '__main__':
    # Bind to localhost by default for safety; container sets API_HOST=0.0.0.0
    host = os.environ.get('API_HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    app.run(host=host, port=port)
