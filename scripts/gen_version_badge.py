"""Compute the latest SemVer git tag and emit a Shields badge endpoint."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


SEMVER_RE = re.compile(r"^v?(\d+\.\d+\.\d+)$")


def _latest_tag() -> str:
    try:
        completed = subprocess.run(
            ['git', 'tag', '--list'],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return 'unreleased'

    tags = []
    for raw in completed.stdout.splitlines():
        raw = raw.strip()
        match = SEMVER_RE.match(raw)
        if match:
            tags.append(match.group(1))

    if not tags:
        return 'unreleased'

    tags.sort(key=lambda s: tuple(int(part) for part in s.split('.')))
    return tags[-1]


def main() -> int:
    if len(sys.argv) != 2:
        print('usage: python gen_version_badge.py OUTPUT_JSON', file=sys.stderr)
        return 1

    dest = Path(sys.argv[1])
    version = _latest_tag()

    color = 'blue' if version != 'unreleased' else 'lightgrey'

    badge = {
        'schemaVersion': 1,
        'label': 'release',
        'message': version,
        'color': color,
    }

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(badge, sort_keys=True), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
