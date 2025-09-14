import os
from flask import Flask, jsonify, request, abort
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from blocker import get_blocked_table, get_engine, init_db

# Common string constants to avoid duplicated literals in code
ROUTE_ADDRESSES = "/addresses"

KEY_ERROR = "error"
KEY_STATUS = "status"
KEY_PATTERN = "pattern"
KEY_IS_REGEX = "is_regex"

ERR_DB_NOT_READY = "database not ready"

STATUS_OK = "ok"
STATUS_DELETED = "deleted"

app = Flask(__name__)
engine = get_engine()

# Lazily initialize DB to avoid crashing API when backend is not yet ready
_db_ready = False


def ensure_db_ready() -> bool:
    """Ensure database schema is initialized; return True on success.

    Avoids process exit loops when the database is temporarily unavailable
    (e.g., DB2 taking minutes to initialize). Routes can respond gracefully
    while retrying on subsequent requests.
    """
    global _db_ready
    if _db_ready:
        return True
    try:
        init_db(engine)
        _db_ready = True
        return True
    except Exception as exc:  # pragma: no cover - depends on external DB readiness
        # Keep API alive; callers can retry later
        app.logger.warning("DB init not ready: %s", exc)
        return False


def row_to_dict(row):
    return {"id": row.id, KEY_PATTERN: row.pattern, KEY_IS_REGEX: row.is_regex}


@app.route(ROUTE_ADDRESSES, methods=["GET"])
def list_addresses():
    if not ensure_db_ready():
        return jsonify({KEY_ERROR: ERR_DB_NOT_READY}), 503
    # Optional server-side pagination, sorting, and search
    args = request.args
    paged = any(k in args for k in ("page", "page_size", "q", "sort", "dir"))
    bt = get_blocked_table()
    if not paged:
        with engine.connect() as conn:
            rows = conn.execute(select(bt)).fetchall()
        return jsonify([row_to_dict(r) for r in rows])

    # Defaults
    try:
        page = max(int(args.get("page", 1)), 1)
    except Exception:
        page = 1
    try:
        page_size = min(max(int(args.get("page_size", 25)), 1), 500)
    except Exception:
        page_size = 25
    q = (args.get("q") or "").strip()
    f_pattern = (args.get("f_pattern") or "").strip()
    f_id = (args.get("f_id") or "").strip()
    f_is_regex = (args.get("f_is_regex") or "").strip().lower()
    sort = (args.get("sort") or "pattern").strip()
    direction = (args.get("dir") or "asc").lower()
    if direction not in ("asc", "desc"):
        direction = "asc"

    # Build filters and ordering (portable across PG/DB2)
    filters = []
    if q:
        q_like = f"%{q.upper()}%"
        filters.append(func.upper(bt.c.pattern).like(q_like))
    if f_pattern:
        fp_like = f"%{f_pattern.upper()}%"
        filters.append(func.upper(bt.c.pattern).like(fp_like))
    if f_id:
        try:
            fid = int(f_id)
            filters.append(bt.c.id == fid)
        except Exception:
            pass
    if f_is_regex in ("1", "true", "t", "yes", "y"):
        filters.append(bt.c.is_regex.is_(True))
    elif f_is_regex in ("0", "false", "f", "no", "n"):
        filters.append(bt.c.is_regex.is_(False))

    sort_columns = {
        "id": bt.c.id,
        "pattern": bt.c.pattern,
        "is_regex": bt.c.is_regex,
        "updated_at": bt.c.updated_at,
    }
    order_col = sort_columns.get(sort, bt.c.pattern)
    order_by = order_col.asc() if direction == "asc" else order_col.desc()

    offset = (page - 1) * page_size
    with engine.connect() as conn:
        total = conn.execute(select(func.count()).select_from(bt).where(*filters)).scalar() or 0
        stmt = select(bt).where(*filters).order_by(order_by).offset(offset).limit(page_size)
        rows = conn.execute(stmt).fetchall()
    return jsonify(
        {
            "items": [row_to_dict(r) for r in rows],
            "total": int(total),
            "page": page,
            "page_size": page_size,
            "sort": sort,
            "dir": direction,
            "q": q,
        }
    )


@app.route(ROUTE_ADDRESSES, methods=["POST"])
def add_address():
    if not ensure_db_ready():
        return jsonify({KEY_ERROR: ERR_DB_NOT_READY}), 503
    data = request.get_json(force=True)
    pattern = data.get(KEY_PATTERN)
    is_regex = bool(data.get(KEY_IS_REGEX, False))
    if not pattern:
        abort(400, "pattern is required")
    with engine.connect() as conn:
        try:
            conn.execute(get_blocked_table().insert().values(pattern=pattern, is_regex=is_regex))
            conn.commit()
        except IntegrityError:
            abort(409, "pattern already exists")
    return {KEY_STATUS: STATUS_OK}, 201


@app.route("/addresses/<int:entry_id>", methods=["DELETE"])
def delete_address(entry_id):
    if not ensure_db_ready():
        return jsonify({KEY_ERROR: ERR_DB_NOT_READY}), 503
    with engine.connect() as conn:
        bt = get_blocked_table()
        conn.execute(bt.delete().where(bt.c.id == entry_id))
        conn.commit()
    return {KEY_STATUS: STATUS_DELETED}


@app.route("/addresses/<int:entry_id>", methods=["PUT", "PATCH"])
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
    if KEY_PATTERN in data and (data[KEY_PATTERN] or "").strip():
        updates[KEY_PATTERN] = data[KEY_PATTERN].strip()
    if KEY_IS_REGEX in data:
        updates[KEY_IS_REGEX] = bool(data[KEY_IS_REGEX])
    if not updates:
        abort(400, "no updatable fields provided")

    bt = get_blocked_table()
    from sqlalchemy.exc import IntegrityError as _IntegrityError  # local import for optional SA at import time
    with engine.connect() as conn:
        try:
            res = conn.execute(bt.update().where(bt.c.id == entry_id).values(**updates))
            if res.rowcount == 0:
                abort(404)
            conn.commit()
        except _IntegrityError:
            abort(409, "pattern already exists")
    return {KEY_STATUS: STATUS_OK}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
