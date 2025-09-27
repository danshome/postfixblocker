from __future__ import annotations

import pytest

from postfix_blocker.db.admins import seed_default_admin


class _DummyResult:
    @property
    def rowcount(self):  # pragma: no cover - not used
        return 1


class _FakeConn:
    def __init__(self):
        self.calls = 0

    def execute(self, *args, **kwargs):
        self.calls += 1
        # First call is the SELECT COUNT() probe -> raise to trigger fallback branch
        if self.calls == 1:
            raise AttributeError('no execute for select')
        return _DummyResult()

    def exec_driver_sql(self, sql: str, params):
        # Simulate failure of the driver fallback probe as well to hit nested except
        raise RuntimeError('driver sql failed')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def begin(self):
        return _FakeConn()


@pytest.mark.unit
def test_seed_default_admin_handles_exists_probe_fallbacks():
    eng = _FakeEngine()
    # Should not raise despite both probe paths failing; should proceed to insert
    seed_default_admin(eng, 'admin', 'postfixblocker')  # type: ignore[arg-type]
