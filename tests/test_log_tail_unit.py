from __future__ import annotations

import os
import tempfile

import pytest

from postfix_blocker.services.log_tail import tail_file


@pytest.mark.unit
def test_tail_file_text_and_binary_fallback():
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'log.txt')
        with open(p, 'w', encoding='utf-8') as f:
            for i in range(1, 11):
                f.write(f'line-{i}\n')
        # Text mode
        out = tail_file(p, 3)
        assert out.splitlines() == ['line-8', 'line-9', 'line-10']

        # Overwrite with some binary garbage that is not strict UTF-8
        with open(p, 'wb') as f:
            f.write(b'\xff\xfe\xfdline-1\nline-2\n')
        out2 = tail_file(p, 1)
        assert out2.strip() == 'line-2'
