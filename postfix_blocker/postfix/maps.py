# ruff: noqa: E402
from __future__ import annotations

"""Postfix map writing helpers (refactor implementation)."""

import logging
import os
from collections.abc import Iterable
from pathlib import Path

from ..models.entries import BlockEntry


def write_map_files(entries: Iterable[BlockEntry], postfix_dir: str | None = None) -> None:
    """Write enforced and test maps for literal and regex blocks.

    Paths (under postfix_dir):
      - blocked_recipients
      - blocked_recipients.pcre
      - blocked_recipients_test
      - blocked_recipients_test.pcre
    """
    pdir = postfix_dir or os.environ.get('POSTFIX_DIR', '/etc/postfix')
    base = Path(pdir)

    literal_lines: list[str] = []
    regex_lines: list[str] = []
    test_literal_lines: list[str] = []
    test_regex_lines: list[str] = []

    for entry in entries:
        line_lit = f'{entry.pattern}\tREJECT'
        line_re = f'/{entry.pattern}/ REJECT'
        if entry.test_mode:
            if entry.is_regex:
                test_regex_lines.append(line_re)
            else:
                test_literal_lines.append(line_lit)
        else:
            if entry.is_regex:
                regex_lines.append(line_re)
            else:
                literal_lines.append(line_lit)

    logging.info(
        'Preparing Postfix maps: enforce(lit=%d, re=%d) test(lit=%d, re=%d)',
        len(literal_lines),
        len(regex_lines),
        len(test_literal_lines),
        len(test_regex_lines),
    )

    paths = {
        'literal': base / 'blocked_recipients',
        'regex': base / 'blocked_recipients.pcre',
        'test_literal': base / 'blocked_recipients_test',
        'test_regex': base / 'blocked_recipients_test.pcre',
    }

    with paths['literal'].open('w', encoding='utf-8') as f:
        f.write('\n'.join(literal_lines) + ('\n' if literal_lines else ''))
    with paths['regex'].open('w', encoding='utf-8') as f:
        f.write('\n'.join(regex_lines) + ('\n' if regex_lines else ''))
    with paths['test_literal'].open('w', encoding='utf-8') as f:
        f.write('\n'.join(test_literal_lines) + ('\n' if test_literal_lines else ''))
    with paths['test_regex'].open('w', encoding='utf-8') as f:
        f.write('\n'.join(test_regex_lines) + ('\n' if test_regex_lines else ''))

    logging.info(
        'Wrote maps: %s (bytes=%d), %s (bytes=%d), %s (bytes=%d), %s (bytes=%d)',
        str(paths['literal']),
        paths['literal'].stat().st_size,
        str(paths['regex']),
        paths['regex'].stat().st_size,
        str(paths['test_literal']),
        paths['test_literal'].stat().st_size,
        str(paths['test_regex']),
        paths['test_regex'].stat().st_size,
    )


__all__ = ['BlockEntry', 'write_map_files']
