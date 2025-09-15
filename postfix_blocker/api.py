import logging  # moved to postfix_blocker.api
import os
import signal
import time
from typing import TYPE_CHECKING, Any, cast

from flask import Flask, abort, g, jsonify, request
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError

# Support running both as part of the 'app' package and as a standalone script in the container
try:
    from .blocker import get_blocked_table, get_engine, init_db  # type: ignore
except Exception:  # pragma: no cover - fallback when executed as a script
    from blocker import get_blocked_table, get_engine, init_db  # type: ignore

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
            engine = get_engine()
        init_db(engine)
        _db_ready = True
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
            rows = conn.execute(select(bt)).fetchall()
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
        rows = conn.execute(stmt).fetchall()
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
        conn.execute(bt.delete().where(bt.c.id == entry_id))
        conn.commit()
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
    from sqlalchemy.exc import IntegrityError as _IntegrityError  # local import

    eng = cast(Any, engine)
    with eng.connect() as conn:
        try:
            res = conn.execute(bt.update().where(bt.c.id == entry_id).values(**updates))
            if res.rowcount == 0:
                abort(404)
            conn.commit()
        except _IntegrityError:
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


if __name__ == '__main__':
    # Bind to localhost by default for safety; container sets API_HOST=0.0.0.0
    host = os.environ.get('API_HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    app.run(host=host, port=port)
