from __future__ import annotations

import os
import tempfile

import pytest

from postfix_blocker.postfix import log_level as ll


@pytest.mark.unit
def test_apply_postfix_log_level_updates_file_and_handles_reload_error(monkeypatch):
    # Prepare a temporary main.cf with some existing keys
    with tempfile.TemporaryDirectory() as td:
        main_cf = os.path.join(td, 'main.cf')
        with open(main_cf, 'w', encoding='utf-8') as f:
            f.write(
                '\n'.join(
                    [
                        'myhostname = example',
                        'debug_peer_level = 1',
                        'smtp_tls_loglevel = 0',
                    ],
                )
                + '\n',
            )

        # Make reload_postfix raise to hit warning path
        monkeypatch.setattr(
            ll,
            'reload_postfix',
            lambda: (_ for _ in ()).throw(RuntimeError('no svc')),
        )

        # DEBUG -> lvl=10, tls=4; should update existing keys and add missing ones
        ll.apply_postfix_log_level('DEBUG', main_cf=main_cf)

        content = open(main_cf, encoding='utf-8').read()
        assert 'debug_peer_level = 10' in content
        assert 'debug_peer_list = 0.0.0.0/0' in content  # added if missing
        assert 'smtp_tls_loglevel = 4' in content
        assert 'smtpd_tls_loglevel = 4' in content

        # Numeric 3 -> tls=1; ensure values updated again without duplication
        ll.apply_postfix_log_level('3', main_cf=main_cf)
        content2 = open(main_cf, encoding='utf-8').read()
        assert 'smtp_tls_loglevel = 1' in content2
        assert 'smtpd_tls_loglevel = 1' in content2


@pytest.mark.unit
def test_resolve_mail_log_path_env_and_fallback(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        preferred = os.path.join(td, 'maillog')
        # Neither exists -> should return preferred default even if not present
        monkeypatch.setenv('MAIL_LOG_FILE', '')
        monkeypatch.setattr(ll.os.path, 'exists', lambda p: False)
        # Bypass getsize calls since exists() is False
        p = ll.resolve_mail_log_path()
        assert p.endswith('/var/log/maillog')

        # Env override when file exists; also force other paths to appear missing
        with open(preferred, 'w', encoding='utf-8') as f:
            f.write('x')
        monkeypatch.setenv('MAIL_LOG_FILE', preferred)

        def exists_only_preferred(path: str) -> bool:  # type: ignore[override]
            return path == preferred

        monkeypatch.setattr(ll.os.path, 'exists', exists_only_preferred)
        # getsize not used for env branch, but keep consistent
        monkeypatch.setattr(ll.os.path, 'getsize', os.path.getsize)
        assert ll.resolve_mail_log_path() == preferred
