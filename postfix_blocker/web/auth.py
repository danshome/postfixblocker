from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable

from flask import jsonify, session

SESSION_USER_KEY = 'admin_user'


def _is_auth_required() -> bool:
    """Return True if API auth should be enforced.

    Default: disabled (False). Enable by setting environment variable
    API_AUTH_REQUIRED=1 for the API process. This keeps legacy behavior and
    allows test/e2e suites that expect public endpoints to run unchanged.
    """
    return os.environ.get('API_AUTH_REQUIRED', '0') == '1'


def login_required(fn: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(fn)
    def _wrapped(*args: Any, **kwargs: Any):
        # If auth is not required, allow the request through.
        if not _is_auth_required():
            return fn(*args, **kwargs)
        user = session.get(SESSION_USER_KEY)
        if not user:
            return jsonify({'error': 'unauthorized'}), 401
        return fn(*args, **kwargs)

    return _wrapped


def set_logged_in(username: str) -> None:
    session[SESSION_USER_KEY] = username


def clear_login() -> None:
    session.pop(SESSION_USER_KEY, None)


def is_logged_in() -> bool:
    if not _is_auth_required():
        return True
    return bool(session.get(SESSION_USER_KEY))
