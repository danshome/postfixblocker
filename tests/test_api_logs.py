import os
import tempfile

import pytest


@pytest.mark.unit
def test_tail_file_reads_last_lines():
    try:
        from postfix_blocker.api import _tail_file
    except Exception:
        pytest.fail('Flask or API module not available; required for unit tests.')

    # Create a temp log file with 1000 lines
    with tempfile.NamedTemporaryFile('w+b', delete=False) as tf:
        path = tf.name
    try:
        with open(path, 'w', encoding='utf-8') as f:
            for i in range(1, 501):
                f.write(f'line-{i}\n')
        # Request last 10 lines
        out = _tail_file(path, 10)
        lines = out.strip().split('\n')
        assert len(lines) == 10
        assert lines[0] == 'line-491'
        assert lines[-1] == 'line-500'
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass


@pytest.mark.unit
def test_level_coercion():
    import logging

    try:
        from postfix_blocker.api import _coerce_level
    except Exception:
        pytest.fail('Flask or API module not available; required for unit tests.')

    assert _coerce_level('10') == 10
    assert _coerce_level('DEBUG') == logging.DEBUG
    assert _coerce_level('info') == logging.INFO
    # Unknown defaults to INFO mapping via getattr
    assert isinstance(_coerce_level('notalevel'), int)
