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


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup('compose')
    group.addoption(
        '--compose-rebuild',
        action='store_true',
        default=False,
        help="Run 'docker compose down' then 'docker compose up --build -d' before tests",
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
        # Docker not available; do nothing.
        return

    always = os.environ.get('PYTEST_COMPOSE_ALWAYS', '0') == '1'
    force = pytestconfig.getoption('--compose-rebuild') or always
    needs = getattr(pytestconfig, '_compose_needs_stack', False)

    # Rebuild when forced or when backend/e2e tests are part of this run
    if not (force or needs):
        return

    def run(cmd: list[str]) -> None:
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as exc:
            print(f'[compose] Command failed ({exc.returncode}): {" ".join(cmd)}', file=sys.stderr)
            # Do not fail the whole test run; tests will skip if services are unavailable

    print('[compose] Bringing stack down...', flush=True)
    run([*compose, 'down', '-v', '--remove-orphans'])
    print('[compose] Building and starting stack...', flush=True)
    run([*compose, 'up', '-d', '--build'])  # build latest app code
