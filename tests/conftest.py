"""Pytest configuration to optionally manage docker-compose lifecycle.

By default, we only rebuild/bring up the stack when backend/e2e tests are
collected, to keep unit test runs fast. To force compose management for all
runs, set env `PYTEST_COMPOSE_ALWAYS=1` or pass `--compose-rebuild`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore

# Ensure tests touching logging don't leak global state across the suite
import logging
from logging import Logger


@pytest.fixture(autouse=True)
def _restore_root_logger() -> None:
    root: Logger = logging.getLogger()
    old_level = root.level
    old_handlers = list(root.handlers)
    try:
        yield
    finally:
        try:
            root.setLevel(old_level)
        except Exception:
            pass
        # Remove any handlers added during the test and restore originals
        for h in list(root.handlers):
            if h not in old_handlers:
                try:
                    root.removeHandler(h)
                except Exception:
                    pass
        for h in old_handlers:
            if h not in root.handlers:
                try:
                    root.addHandler(h)
                except Exception:
                    pass


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup('compose')
    group.addoption(
        '--compose-rebuild',
        action='store_true',
        default=False,
        help="Run 'docker compose stop' then 'docker compose up --build -d' before tests",
    )
    group.addoption(
        '--no-compose',
        action='store_true',
        default=False,
        help='Disable docker-compose management even if enabled by env',
    )


def _docker_compose_cmd() -> list[str] | None:
    # Prefer modern 'docker compose', fallback to legacy 'docker-compose'
    if shutil.which('docker'):
        return ['docker', 'compose']
    if shutil.which('docker-compose'):
        return ['docker-compose']
    return None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    # Determine if any selected tests require the docker stack
    needs = any(('backend' in item.keywords) or ('e2e' in item.keywords) for item in items)
    # Store flag directly; used by the session-scoped compose fixture
    config._compose_needs_stack = needs  # type: ignore[attr-defined]


@pytest.fixture(scope='session', autouse=True)
def compose_stack(pytestconfig: pytest.Config) -> None:
    if pytestconfig.getoption('--no-compose'):
        return

    compose = _docker_compose_cmd()
    if not compose:
        import pytest

        # If backend/e2e tests are selected or forced, fail fast when docker is missing
        always = os.environ.get('PYTEST_COMPOSE_ALWAYS', '0') == '1'
        force = pytestconfig.getoption('--compose-rebuild') or always
        needs = getattr(pytestconfig, '_compose_needs_stack', False)
        if force or needs:
            pytest.fail(
                'Docker (compose) is required to run backend/e2e tests but was not found in PATH.'
            )
        return

    always = os.environ.get('PYTEST_COMPOSE_ALWAYS', '0') == '1'
    force = pytestconfig.getoption('--compose-rebuild') or always
    needs = getattr(pytestconfig, '_compose_needs_stack', False)

    # Helper: determine if the stack is already up (skip rebuilds in that case)
    def stack_running() -> bool:
        if not compose:
            return False
        try:
            out = subprocess.run(
                [*compose, 'ps', '--services', '--filter', 'status=running'],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            services = {line.strip() for line in out.splitlines() if line.strip()}
            return bool({'postfix', 'postfix_db2'} & services)
        except Exception:
            return False

    # Only manage the stack when backend/e2e tests are selected or forced
    if not (force or needs):
        return

    def run(cmd: list[str]) -> None:
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as exc:
            import pytest

            print(f'[compose] Command failed ({exc.returncode}): {" ".join(cmd)}', file=sys.stderr)
            pytest.fail(
                f'Docker compose command failed (exit {exc.returncode}). Backend/E2E tests require the stack to be available. Command={" ".join(cmd)}'
            )

    if force:
        print('[compose] Forced rebuild requested...', flush=True)
        print('[compose] Stopping stack...', flush=True)
        run([*compose, 'stop'])
        print('[compose] Building and starting stack...', flush=True)
        run([*compose, 'up', '-d', '--build'])
    else:
        if stack_running():
            print('[compose] Stack already running; skipping rebuild', flush=True)
        else:
            print('[compose] Starting stack (no rebuild)...', flush=True)
            run([*compose, 'up', '-d', '--build'])

    # After attempting to start, verify that at least one postfix service is running
    if not stack_running():
        import pytest

        pytest.fail('Docker stack did not start successfully; required services are not running.')


@pytest.fixture(scope='session', autouse=True)
def _cleanup_api_state() -> None:
    """Reset API state before and after the test session using /test/reset.

    Requires TEST_RESET_ENABLE=1 in the API containers (enabled in docker-compose).
    Falls back to best-effort deletion via /addresses if the reset endpoint is
    unavailable (e.g., during unit-only runs without the stack).
    """
    if not requests:
        return

    from .utils_reset import reset_both  # lazy import

    def wipe_legacy(port: int) -> None:
        base = f'http://127.0.0.1:{port}'
        try:
            r = requests.get(f'{base}/addresses', timeout=3)
            if r.status_code != 200:
                return
            for it in r.json() if isinstance(r.json(), list) else r.json().get('items', []):
                try:
                    requests.delete(f'{base}/addresses/{it["id"]}', timeout=3)
                except Exception:
                    pass
        except Exception:
            pass

    # Pre-session cleanup
    outcomes = reset_both()
    if not any(outcomes.values()):  # fallback if reset route unavailable
        wipe_legacy(5001)
        wipe_legacy(5002)

    # Post-session cleanup
    yield
    outcomes = reset_both()
    if not any(outcomes.values()):
        wipe_legacy(5001)
        wipe_legacy(5002)
