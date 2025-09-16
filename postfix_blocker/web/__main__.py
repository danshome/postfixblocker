from __future__ import annotations

import os

from .app_factory import create_app


def main() -> None:  # pragma: no cover - dev helper
    app = create_app()
    host = os.environ.get('API_HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '5000'))
    app.run(host=host, port=port)


if __name__ == '__main__':  # pragma: no cover - dev helper
    main()
