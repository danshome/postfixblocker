import os
from flask import Flask, jsonify, request, abort
from sqlalchemy import select
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
    with engine.connect() as conn:
        rows = conn.execute(select(get_blocked_table())).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
