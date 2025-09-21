from __future__ import annotations

import os
import tempfile

import pytest

from postfix_blocker.models.entries import BlockEntry
from postfix_blocker.postfix.maps import write_map_files


@pytest.mark.unit
def test_write_map_files_test_mode_variants():
    entries = [
        BlockEntry(pattern='b@example.com', is_regex=False, test_mode=True),
        BlockEntry(pattern='^test@.*', is_regex=True, test_mode=True),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        write_map_files(entries, postfix_dir=tmp)
        with open(os.path.join(tmp, 'blocked_recipients_test'), encoding='utf-8') as f:
            lit = f.read()
            assert 'b@example.com' in lit
        with open(os.path.join(tmp, 'blocked_recipients_test.pcre'), encoding='utf-8') as f:
            rex = f.read()
            assert '/^test@.*/' in rex
