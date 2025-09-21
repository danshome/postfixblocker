"""Generate a Shields.io-compatible coverage badge JSON.

Expects coverage XML from coverage.py as input. Writes a JSON endpoint file
that shields.io can consume via its `endpoint` data source feature.
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def _color_for(percent: int) -> str:
    if percent >= 90:
        return 'brightgreen'
    if percent >= 80:
        return 'green'
    if percent >= 70:
        return 'yellowgreen'
    if percent >= 60:
        return 'yellow'
    if percent >= 50:
        return 'orange'
    return 'red'


def main() -> int:
    if len(sys.argv) != 3:
        print('usage: python gen_coverage_badge.py COVERAGE_XML OUTPUT_JSON', file=sys.stderr)
        return 1

    src = Path(sys.argv[1])
    dest = Path(sys.argv[2])

    if not src.is_file():
        print(f'coverage file not found: {src}', file=sys.stderr)
        return 1

    try:
        tree = ET.parse(src)
    except Exception as exc:  # pragma: no cover - catastrophic parsing failure
        print(f'failed to parse coverage XML: {exc}', file=sys.stderr)
        return 1

    root = tree.getroot()
    rate = root.attrib.get('line-rate') or root.attrib.get('line_rate')
    try:
        percent = int(round(float(rate) * 100)) if rate is not None else 0
    except Exception:  # pragma: no cover - malformed numeric value
        percent = 0

    badge = {
        'schemaVersion': 1,
        'label': 'coverage',
        'message': f'{percent}%',
        'color': _color_for(percent),
    }

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(badge, sort_keys=True), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
