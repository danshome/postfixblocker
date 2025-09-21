"""Produce a static Shields badge endpoint payload."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 5:
        print('usage: python write_badge.py LABEL MESSAGE COLOR OUTPUT_JSON', file=sys.stderr)
        return 1

    label, message, color, output = sys.argv[1:5]
    dest = Path(output)

    badge = {
        'schemaVersion': 1,
        'label': label,
        'message': message,
        'color': color,
    }

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(badge, sort_keys=True), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
