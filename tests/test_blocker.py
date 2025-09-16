import os
import tempfile

import pytest

from postfix_blocker.models.entries import BlockEntry
from postfix_blocker.postfix.maps import write_map_files


@pytest.mark.unit
def test_write_map_files():
    entries = [
        BlockEntry(pattern='a@example.com', is_regex=False),
        BlockEntry(pattern='.*@blocked.com', is_regex=True),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        # Write maps directly to the temporary directory (no legacy shim)
        write_map_files(entries, postfix_dir=tmp)
        with open(os.path.join(tmp, 'blocked_recipients'), encoding='utf-8') as f:
            content = f.read()
            assert 'a@example.com' in content
        with open(os.path.join(tmp, 'blocked_recipients.pcre'), encoding='utf-8') as f:
            content = f.read()
            assert '/.*@blocked.com/' in content
