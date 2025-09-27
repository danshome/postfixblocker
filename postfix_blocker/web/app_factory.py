from __future__ import annotations

import logging
import time
from contextlib import suppress
from typing import Any, Final

from flask import Flask, g, request

from ..db.engine import get_engine as _get_engine
from ..db.migrations import init_db as _init_db
from ..logging_setup import configure_logging

# Types for app.config keys
_CFG_ENGINE: Final[str] = 'db_engine'
_CFG_READY: Final[str] = 'db_ready'
_CFG_ENSURE: Final[str] = 'ensure_db_ready'


def _configure_session(app: Flask) -> None:
    try:
        import os as _os

        app.secret_key = _os.environ.get('SESSION_SECRET', 'dev-secret-change-me')
        app.config.update(
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE='Lax',
            SESSION_COOKIE_SECURE=True,
        )
    except Exception as exc:
        logging.getLogger('api').warning('Session configuration failed: %s', exc)


def _install_request_logging_hooks(app: Flask) -> None:
    # Install request logging hooks similar to legacy api.py
    @app.before_request
    def _log_request_start() -> None:  # pragma: no cover - integration behavior
        g.request_start_time = time.time()
        try:
            qs = request.query_string.decode('utf-8') if request.query_string else ''
        except Exception:
            qs = ''
        logging.getLogger('api').info(
            'API %s %s%s from=%s',
            request.method,
            request.path,
            f'?{qs}' if qs else '',
            request.remote_addr,
        )

    @app.after_request
    def _log_request_end(response):  # pragma: no cover - integration behavior
        try:
            start = getattr(g, 'request_start_time', None)
            dur_ms = (time.time() - start) * 1000.0 if start else 0.0
        except Exception:
            dur_ms = 0.0
        logging.getLogger('api').info(
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
            logging.getLogger('api').exception(
                'API error on %s %s: %s',
                request.method,
                request.path,
                exc,
            )


def _setup_db_lazy(app: Flask) -> None:
    app.config[_CFG_ENGINE] = None
    app.config[_CFG_READY] = False

    def ensure_db_ready() -> bool:
        if app.config.get(_CFG_READY):
            return True
        try:
            if app.config.get(_CFG_ENGINE) is None:
                logging.getLogger('api').debug(
                    'Creating SQLAlchemy engine (app_factory.ensure_db_ready)',
                )
                app.config[_CFG_ENGINE] = _get_engine()
            logging.getLogger('api').debug('Initializing database schema via migrations.init_db')
            _init_db(app.config[_CFG_ENGINE])  # type: ignore[arg-type]
        except Exception as exc:  # pragma: no cover - external dependency
            logging.getLogger('api').warning('DB init not ready: %s', exc)
            return False
        else:  # TRY300
            app.config[_CFG_READY] = True
            logging.getLogger('api').debug('Database schema ready (app_factory.ensure_db_ready)')
            return True

    app.config[_CFG_ENSURE] = ensure_db_ready


def _register_blueprints(app: Flask) -> None:
    from .routes_addresses import bp as addresses_bp
    from .routes_auth import bp as auth_bp
    from .routes_logs import bp as logs_bp

    app.register_blueprint(addresses_bp)
    app.register_blueprint(logs_bp)
    app.register_blueprint(auth_bp)


def _maybe_install_test_reset(app: Flask) -> None:
    try:
        import os as _os

        if _os.environ.get('TEST_RESET_ENABLE', '0') == '1':
            from .routes_test_reset import bp as test_reset_bp

            app.register_blueprint(test_reset_bp)
    except Exception as exc:
        logging.getLogger('api').debug('Test reset blueprint not installed: %s', exc)


def create_app(config: Any | None = None) -> Flask:
    """Create and configure the Flask API application.

    Features:
      - Initializes per-service logging for the API process using
        logging_setup.configure_logging (level/file via env).
      - Lazily initializes the database engine and schema on first access via
        ensure_db_ready() stored in app.config.
      - Registers the address and logs blueprints providing REST endpoints.
      - Installs simple request/response logging hooks for observability.

    Args:
        config: Optional object/dict with overrides for Flask app.config.

    Returns:
        A configured Flask application instance.
    """
    app = Flask(__name__)

    # Apply optional config overrides so the argument is used (ARG001)
    if isinstance(config, dict):
        # Ignore invalid config objects, keep app default config
        with suppress(Exception):
            app.config.update(config)

    # Session/secret configuration
    _configure_session(app)

    # Initialize logging for API (file/level via env)
    configure_logging(
        service='api',
        level_env='API_LOG_LEVEL',
        file_env='API_LOG_FILE',
        default='INFO',
    )

    _install_request_logging_hooks(app)

    # Lazy DB init; store in app.config
    _setup_db_lazy(app)

    # Register blueprints
    _register_blueprints(app)

    # Test-only reset blueprint (guarded by env flag)
    _maybe_install_test_reset(app)

    return app
