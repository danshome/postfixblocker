from __future__ import annotations

"""Log tail helpers.

Provide a simple, deterministic tail implementation suitable for API responses.
"""


def tail_file(path: str, lines: int) -> str:
    """Return the last N lines of a text file as a single string.

    Reads using UTF-8 with error replacement; if decoding fails, falls back to
    reading bytes and decoding with replacement to ensure robust behavior with
    partially binary logs.

    Args:
        path: Absolute or relative path to the log file.
        lines: Number of trailing lines to include (values <= len(file) only).

    Returns:
        A single string comprised of the last N lines joined by newlines. If the
        file has fewer than N lines, all lines are returned.
    """
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
