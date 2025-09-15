import os
import tempfile

import pytest

from postfix_blocker import blocker


@pytest.mark.unit
def test_write_map_files():
    entries = [
        blocker.BlockEntry(pattern='a@example.com', is_regex=False),
        blocker.BlockEntry(pattern='.*@blocked.com', is_regex=True),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        orig_dir = blocker.POSTFIX_DIR
        blocker.POSTFIX_DIR = tmp
        blocker.write_map_files(entries)
        with open(os.path.join(tmp, 'blocked_recipients'), encoding='utf-8') as f:
            content = f.read()
            assert 'a@example.com' in content
        with open(os.path.join(tmp, 'blocked_recipients.pcre'), encoding='utf-8') as f:
            content = f.read()
            assert '/.*@blocked.com/' in content
        blocker.POSTFIX_DIR = orig_dir
