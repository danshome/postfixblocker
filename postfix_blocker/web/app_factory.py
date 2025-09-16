from __future__ import annotations

import logging
import time
from typing import Any, Final

from flask import Flask, g, request

from ..db.engine import get_engine as _get_engine
from ..db.migrations import init_db as _init_db
from ..logging_setup import configure_logging

# Types for app.config keys
_CFG_ENGINE: Final[str] = 'db_engine'
_CFG_READY: Final[str] = 'db_ready'
_CFG_ENSURE: Final[str] = 'ensure_db_ready'


def create_app(config: Any | None = None) -> Flask:
    app = Flask(__name__)

    # Initialize logging for API (file/level via env)
    configure_logging(
        service='api', level_env='API_LOG_LEVEL', file_env='API_LOG_FILE', default='INFO'
    )

    # Install request logging hooks similar to legacy api.py
    @app.before_request
    def _log_request_start() -> None:  # pragma: no cover - integration behavior
        g._start_time = time.time()
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
            start = getattr(g, '_start_time', None)
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
                'API error on %s %s: %s', request.method, request.path, exc
            )

    # Lazy DB init; store in app.config
    app.config[_CFG_ENGINE] = None
    app.config[_CFG_READY] = False

    def ensure_db_ready() -> bool:
        if app.config.get(_CFG_READY):
            return True
        try:
            if app.config.get(_CFG_ENGINE) is None:
                logging.getLogger('api').debug(
                    'Creating SQLAlchemy engine (app_factory.ensure_db_ready)'
                )
                app.config[_CFG_ENGINE] = _get_engine()
            logging.getLogger('api').debug('Initializing database schema via migrations.init_db')
            _init_db(app.config[_CFG_ENGINE])  # type: ignore[arg-type]
            app.config[_CFG_READY] = True
            logging.getLogger('api').debug('Database schema ready (app_factory.ensure_db_ready)')
            return True
        except Exception as exc:  # pragma: no cover - external dependency
            logging.getLogger('api').warning('DB init not ready: %s', exc)
            return False

    app.config[_CFG_ENSURE] = ensure_db_ready

    # Register blueprints
    from .routes_addresses import bp as addresses_bp
    from .routes_logs import bp as logs_bp

    app.register_blueprint(addresses_bp)
    app.register_blueprint(logs_bp)

    return app
