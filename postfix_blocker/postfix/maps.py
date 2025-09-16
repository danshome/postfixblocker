# ruff: noqa: E402
from __future__ import annotations

"""Postfix map writing helpers (refactor implementation)."""

import logging
import os
from collections.abc import Iterable

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
        'literal': os.path.join(pdir, 'blocked_recipients'),
        'regex': os.path.join(pdir, 'blocked_recipients.pcre'),
        'test_literal': os.path.join(pdir, 'blocked_recipients_test'),
        'test_regex': os.path.join(pdir, 'blocked_recipients_test.pcre'),
    }

    with open(paths['literal'], 'w', encoding='utf-8') as f:
        f.write('\n'.join(literal_lines) + ('\n' if literal_lines else ''))
    with open(paths['regex'], 'w', encoding='utf-8') as f:
        f.write('\n'.join(regex_lines) + ('\n' if regex_lines else ''))
    with open(paths['test_literal'], 'w', encoding='utf-8') as f:
        f.write('\n'.join(test_literal_lines) + ('\n' if test_literal_lines else ''))
    with open(paths['test_regex'], 'w', encoding='utf-8') as f:
        f.write('\n'.join(test_regex_lines) + ('\n' if test_regex_lines else ''))

    logging.info(
        'Wrote maps: %s (bytes=%d), %s (bytes=%d), %s (bytes=%d), %s (bytes=%d)',
        paths['literal'],
        os.path.getsize(paths['literal']),
        paths['regex'],
        os.path.getsize(paths['regex']),
        paths['test_literal'],
        os.path.getsize(paths['test_literal']),
        paths['test_regex'],
        os.path.getsize(paths['test_regex']),
    )


__all__ = ['write_map_files', 'BlockEntry']
