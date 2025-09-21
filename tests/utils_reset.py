"""Shared test utilities for resetting the DB2-backed API.

These helpers are intended for use by both unit/integration tests and by
frontend e2e (via analogous TS helpers).
"""

from __future__ import annotations

from collections.abc import Iterable

try:  # pragma: no cover - requests not required for unit-only runs
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore


DEFAULT_BASES: tuple[str, ...] = (
    'http://127.0.0.1:5002',  # DB2
)


def _post_json(url: str, payload: dict) -> int:
    if not requests:  # pragma: no cover - absent in minimal env
        return 0
    try:
        r = requests.post(url, json=payload, timeout=5)
        return r.status_code
    except Exception:
        return 0


def reset_via_api(base_url: str, seeds: Iterable[dict] | None = None) -> bool:
    """Reset a single API instance via /test/reset.

    Returns True if the reset endpoint responded with 200.
    """
    code = _post_json(base_url.rstrip('/') + '/test/reset', {'seeds': list(seeds or [])})
    return code == 200


def reset_both(bases: Iterable[str] | None = None) -> dict[str, bool]:
    """Reset available API instances (DB2-only now).

    Returns a mapping of base_url -> success flag.
    """
    bases = tuple(bases or DEFAULT_BASES)
    return {b: reset_via_api(b) for b in bases}
