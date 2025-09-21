from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    kwargs.setdefault('check', True)
    return subprocess.run(cmd, **kwargs)


def _docker_available() -> bool:
    return shutil.which('docker') is not None


@pytest.mark.skipif(not _docker_available(), reason='docker CLI not available')
def test_install_script_on_rocky(tmp_path: Path) -> None:
    if importlib.util.find_spec('build') is None:
        pytest.skip('python -m build is not installed')
    repo_root = Path(__file__).resolve().parents[1]

    dist_dir = repo_root / 'dist'
    if dist_dir.exists():
        for entry in dist_dir.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()

    build_env = os.environ.copy()
    build_env.setdefault('SETUPTOOLS_SCM_PRETEND_VERSION', '0.0.0')
    _run(
        [sys.executable, '-m', 'build', '--sdist', '--wheel'],
        cwd=repo_root,
        env=build_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    wheels = sorted(dist_dir.glob('postfix_blocker-*-py3-none-any.whl'))
    assert wheels, 'wheel not built'
    wheel_path = wheels[-1]
    version = wheel_path.name.split('-')[1]
    tarball_path = dist_dir / f'postfix_blocker-{version}.tar.gz'
    assert tarball_path.exists(), 'sdist not built'

    container_name = f'postfixblocker-install-{uuid.uuid4().hex[:8]}'
    env_file = repo_root / 'docker' / 'install-test.env'
    assert env_file.exists(), 'docker/install-test.env missing'
    run_args = [
        'docker',
        'run',
        '-d',
        '--name',
        container_name,
        '--env-file',
        str(env_file),
    ]
    if platform.machine().lower() in {'arm64', 'aarch64'}:
        run_args.extend(['--platform', 'linux/amd64'])
    run_args.extend(['rockylinux:9', 'sleep', '1800'])
    _run(run_args)

    _run(['docker', 'cp', str(wheel_path), f'{container_name}:/tmp/{wheel_path.name}'])
    _run(['docker', 'cp', str(tarball_path), f'{container_name}:/tmp/{tarball_path.name}'])
    _run(
        [
            'docker',
            'exec',
            container_name,
            'bash',
            '-lc',
            f'set -euo pipefail; rm -rf /tmp/postfix_blocker-{version}; '
            f'tar -xzf /tmp/{tarball_path.name} -C /tmp; '
            f'cp /tmp/postfix_blocker-{version}/scripts/install.sh /tmp/install.sh'
            ' && chmod +x /tmp/install.sh',
        ]
    )

    install_cmd = [
        '/bin/bash',
        '-lc',
        'set -euo pipefail; '
        'DB_URL="ibm_db_sa://${POSTFIXBLOCKER_DB_USER}:${POSTFIXBLOCKER_DB_PASSWORD}@'
        '${POSTFIXBLOCKER_DB_HOST}:${POSTFIXBLOCKER_DB_PORT}/${POSTFIXBLOCKER_DB_NAME}?currentSchema='
        '${POSTFIXBLOCKER_DB_SCHEMA}"; '
        f'/tmp/install.sh --non-interactive --version {version} '
        f'--tarball-path /tmp/{tarball_path.name} '
        f'--wheel-path /tmp/{wheel_path.name} '
        '--systemd-mode write-only --postfix-mode skip '
        '--skip-db2-driver-check --force '
        '--db-url "$DB_URL"',
    ]
    _run(['docker', 'exec', container_name] + install_cmd)

    # Validate installation artifacts exist
    _run(['docker', 'exec', container_name, 'test', '-d', '/opt/postfixblocker/venv'])
    _run(['docker', 'exec', container_name, 'test', '-f', '/opt/postfixblocker/.env'])
    _run(
        [
            'docker',
            'exec',
            container_name,
            'bash',
            '-lc',
            'set -euo pipefail; '
            'DB_URL="ibm_db_sa://${POSTFIXBLOCKER_DB_USER}:${POSTFIXBLOCKER_DB_PASSWORD}@'
            '${POSTFIXBLOCKER_DB_HOST}:${POSTFIXBLOCKER_DB_PORT}/${POSTFIXBLOCKER_DB_NAME}?currentSchema='
            '${POSTFIXBLOCKER_DB_SCHEMA}"; '
            'grep -F "BLOCKER_DB_URL=$DB_URL" /opt/postfixblocker/.env',
        ]
    )
    _run(
        [
            'docker',
            'exec',
            container_name,
            'bash',
            '-lc',
            'source /opt/postfixblocker/venv/bin/activate && python -c "import postfix_blocker"',
        ]
    )

    # Ensure services files were written
    _run(
        [
            'docker',
            'exec',
            container_name,
            'test',
            '-f',
            '/etc/systemd/system/postfixblocker-blocker.service',
        ]
    )
    _run(
        [
            'docker',
            'exec',
            container_name,
            'test',
            '-f',
            '/etc/systemd/system/postfixblocker-api.service',
        ]
    )

    # Second run should succeed (idempotency)
    _run(['docker', 'exec', container_name] + install_cmd)

    print(f'[install-test] container available: {container_name}', flush=True)
