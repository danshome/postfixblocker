#!/usr/bin/env python3
from __future__ import annotations

"""Compare table contents between Postgres and DB2 via API test endpoints.

Requires API containers to be running with TEST_RESET_ENABLE=1 (docker-compose sets it).
This script fetches /test/dump from both API instances and compares the
normalized contents of blocked_addresses and cris_props, ignoring volatile
columns like id and updated_at.

Exit codes:
  0 = match
  2 = unable to fetch from one or both APIs
  3 = mismatch (differences printed)
"""

import json
import sys
from typing import Any, Dict, List, Tuple

import urllib.request
import urllib.error

PG = 'http://127.0.0.1:5001'
DB2 = 'http://127.0.0.1:5002'


def _get_json(url: str, timeout: float = 5.0) -> Tuple[int, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return resp.getcode() or 200, data
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode('utf-8')
        except Exception:
            body = ''
        print(f"[compare] HTTP error {e.code} for {url}: {body}")
        return e.code, None
    except Exception as e:
        print(f"[compare] Request failed for {url}: {e}")
        return 0, None


def _as_set(items: List[Dict[str, Any]], keys: Tuple[str, ...]) -> set:
    def _norm(v: Any) -> Any:
        if isinstance(v, bool):
            return bool(v)
        if isinstance(v, (int, float)):
            return v
        return str(v) if v is not None else None

    out = set()
    for it in items or []:
        tup = tuple(_norm(it.get(k)) for k in keys)
        out.add(tup)
    return out


def main() -> int:
    pg_code, pg_dump = _get_json(f"{PG}/test/dump")
    db2_code, db2_dump = _get_json(f"{DB2}/test/dump")

    if pg_code != 200 or db2_code != 200 or pg_dump is None or db2_dump is None:
        print("[AI_SIGNAL][DB_SYNC] status=unavailable detail=one_or_both_unreachable")
        print("[compare][ERROR] Could not fetch /test/dump from one or both APIs.")
        return 2

    pg_blocked = _as_set(list(pg_dump.get('blocked', [])), ('pattern', 'is_regex', 'test_mode'))
    db2_blocked = _as_set(list(db2_dump.get('blocked', [])), ('pattern', 'is_regex', 'test_mode'))

    pg_props = _as_set(list(pg_dump.get('props', [])), ('key', 'value'))
    db2_props = _as_set(list(db2_dump.get('props', [])), ('key', 'value'))

    blocked_equal = pg_blocked == db2_blocked
    props_equal = pg_props == db2_props

    if blocked_equal and props_equal:
        print("[AI_SIGNAL][DB_SYNC] status=ok tables=blocked_addresses,cris_props match=1")
        return 0

    print("[AI_SIGNAL][DB_SYNC] status=mismatch tables=blocked_addresses,cris_props match=0")
    def _fmt(diff: set) -> List[str]:
        return [" | ".join(str(x) for x in row) for row in sorted(diff)]

    blocked_only_pg = pg_blocked - db2_blocked
    blocked_only_db2 = db2_blocked - pg_blocked
    props_only_pg = pg_props - db2_props
    props_only_db2 = db2_props - pg_props

    print("---- Differences: blocked_addresses ----")
    if blocked_only_pg:
        print("Only in Postgres:")
        print("  pattern | is_regex | test_mode")
        for line in _fmt(blocked_only_pg):
            print(f"  {line}")
    if blocked_only_db2:
        print("Only in DB2:")
        print("  pattern | is_regex | test_mode")
        for line in _fmt(blocked_only_db2):
            print(f"  {line}")

    print("---- Differences: cris_props ----")
    if props_only_pg:
        print("Only in Postgres:")
        print("  key | value")
        for line in _fmt(props_only_pg):
            print(f"  {line}")
    if props_only_db2:
        print("Only in DB2:")
        print("  key | value")
        for line in _fmt(props_only_db2):
            print(f"  {line}")

    print("\n[HINT] The DB states differ between PG and DB2. This suggests tests are not running the same operations against both backends or cleanup is incomplete. Review tests to ensure both databases are exercised identically and use the new /test/reset mechanism at suite start.")
    return 3


if __name__ == '__main__':
    sys.exit(main())
