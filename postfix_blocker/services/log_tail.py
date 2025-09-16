from __future__ import annotations

"""Log tail helpers.

Provide a simple, deterministic tail implementation suitable for API responses.
"""


def tail_file(path: str, lines: int) -> str:
    # Deterministic and simple: read text and slice last N lines.
    # Adequate for typical log sizes in this app and robust across platforms.
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            all_lines = f.read().splitlines()
    except UnicodeDecodeError:
        with open(path, 'rb') as f:
            all_lines = f.read().decode('utf-8', errors='replace').splitlines()
    return '\n'.join(all_lines[-lines:])


__all__ = ['tail_file']
