import os
from flask import Flask, jsonify, request, abort
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from blocker import blocked_table, get_engine, init_db

app = Flask(__name__)
engine = get_engine()
init_db(engine)


def row_to_dict(row):
    return {"id": row.id, "pattern": row.pattern, "is_regex": row.is_regex}


@app.route("/addresses", methods=["GET"])
def list_addresses():
    with engine.connect() as conn:
        rows = conn.execute(select(blocked_table)).fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/addresses", methods=["POST"])
def add_address():
    data = request.get_json(force=True)
    pattern = data.get("pattern")
    is_regex = bool(data.get("is_regex", False))
    if not pattern:
        abort(400, "pattern is required")
    with engine.connect() as conn:
        try:
            conn.execute(blocked_table.insert().values(pattern=pattern, is_regex=is_regex))
            conn.commit()
        except IntegrityError:
            abort(409, "pattern already exists")
    return {"status": "ok"}, 201


@app.route("/addresses/<int:entry_id>", methods=["DELETE"])
def delete_address(entry_id):
    with engine.connect() as conn:
        conn.execute(blocked_table.delete().where(blocked_table.c.id == entry_id))
        conn.commit()
    return {"status": "deleted"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
