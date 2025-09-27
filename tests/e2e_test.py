"""Simple script to demonstrate end-to-end blocking behaviour.

The script assumes the docker-compose environment is running. If any of the
services are unavailable the operations below will timeout quickly rather than
hang indefinitely.

It can be run from the host or from within a container by configuring hosts
and ports with the environment variables:

- ``SMTP_HOST`` (default ``localhost``)
- ``SMTP_PORT`` (default ``1026``)
- ``MAILHOG_HOST`` (default ``localhost``)
- ``MAILHOG_PORT`` (default ``8025``)
- ``BLOCKER_DB_URL`` (default
  ``ibm_db_sa://db2inst1:blockerpass@localhost:50000/BLOCKER``)
"""

import argparse
import json
import os
import random
import smtplib
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

try:  # pragma: no cover - optional for local runs
    from sqlalchemy import create_engine
    from sqlalchemy.exc import OperationalError
except Exception:  # pragma: no cover - keep import-safe for pytest collection
    create_engine = None  # type: ignore
    OperationalError = Exception  # type: ignore
try:  # pragma: no cover - optional dependency for demo helpers
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore

# Import refactored DB helpers for test execution (avoid deprecated shim)
try:  # pragma: no cover - keep import-safe for pytest collection
    from postfix_blocker.db.migrations import init_db as _init_db
    from postfix_blocker.db.schema import get_blocked_table as _get_blocked_table
except Exception:  # pragma: no cover
    _init_db = None  # type: ignore
    _get_blocked_table = None  # type: ignore

# Import blocker shim only when running as a standalone script, not during pytest
# collection. This keeps tests free of DeprecationWarning while preserving the
# demo script behaviour.
if __name__ == '__main__':  # pragma: no cover - import shim only for script execution
    try:
        from postfix_blocker import blocker  # type: ignore
    except ModuleNotFoundError:
        try:
            import blocker  # type: ignore
        except ModuleNotFoundError:
            ROOT = Path(__file__).resolve().parent.parent
            # Parent of the package directory must be on sys.path
            sys.path.insert(0, str(ROOT))
            from postfix_blocker import blocker  # type: ignore

DB_URL = os.environ.get(
    'BLOCKER_DB_URL',
    'ibm_db_sa://db2inst1:blockerpass@localhost:50000/BLOCKER',
)

SMTP_HOST = os.environ.get('SMTP_HOST', 'localhost')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '1026'))
MAILHOG_HOST = os.environ.get('MAILHOG_HOST', 'localhost')
MAILHOG_PORT = int(os.environ.get('MAILHOG_PORT', '8025'))

TIMEOUT = 5


def send_mail(recipient: str, msg: str = 'hello') -> None:
    """Send a message through the Postfix instance."""
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=TIMEOUT) as smtp:
        smtp.sendmail('tester@example.com', [recipient], f'Subject: test\n\n{msg}')


def mailhog_messages():
    """Return list of recipients captured by MailHog."""
    try:
        with urlopen(
            f'http://{MAILHOG_HOST}:{MAILHOG_PORT}/api/v2/messages?limit=10000',
            timeout=TIMEOUT,
        ) as resp:
            data = json.load(resp)
    except URLError as exc:
        print('Could not fetch MailHog messages:', exc)
        return []

    recipients = []
    for item in data.get('items', []):
        to = item.get('To', [])
        if to:
            recipients.append(f'{to[0]["Mailbox"]}@{to[0]["Domain"]}')
    return recipients


def mailhog_clear():
    url = f'http://{MAILHOG_HOST}:{MAILHOG_PORT}/api/v1/messages'
    if requests:
        try:
            requests.delete(url, timeout=TIMEOUT)
            return
        except Exception as exc:
            print('Could not clear MailHog messages via requests:', exc)
    # Fallback to urllib with explicit DELETE method
    try:
        from urllib.request import Request

        req = Request(url, method='DELETE')
        with urlopen(req, timeout=TIMEOUT):
            pass
    except Exception as exc:
        print('Could not clear MailHog messages via urllib:', exc)


def _dbg(msg: str):
    if os.environ.get('E2E_DEBUG') == '1':
        print(msg)


def _wait_until(predicate, timeout: float = 30.0, interval: float = 0.5) -> bool:
    """Poll predicate() until it returns truthy or timeout expires.
    Returns True on success, False on timeout. Exceptions in predicate are ignored.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if predicate():
                return True
        except Exception:
            pass
        time.sleep(interval)
    return False


def run_e2e_scenario(db_url: str, smtp_host: str, smtp_port: int, mh_host: str, mh_port: int):
    """Run a minimal e2e scenario and return delivered recipients.

    Assumes a Postfix + blocker service is running and configured to use the
    same backend as db_url.
    """
    if create_engine is None:
        return []
    try:
        engine = create_engine(db_url)
        _dbg('engine created')
    except Exception as exc:
        _dbg(f'engine creation failed: {exc}')
        return []
    if _init_db is None or _get_blocked_table is None:
        _dbg('refactored DB helpers not available')
        try:
            engine.dispose()
        except Exception:
            pass
        return []
    try:
        _init_db(engine)
        _dbg('init_db ok')
    except Exception as exc:
        _dbg(f'init_db failed: {exc}')
        try:
            engine.dispose()
        except Exception:
            pass
        return []

    # Local helpers to avoid mutating module globals
    def _send_mail_local(recipient: str, msg: str = 'hello') -> None:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=TIMEOUT) as smtp:
            smtp.sendmail('tester@example.com', [recipient], f'Subject: test\n\n{msg}')

    def _mh_messages_local():
        try:
            with urlopen(
                f'http://{mh_host}:{mh_port}/api/v2/messages?limit=10000',
                timeout=TIMEOUT,
            ) as resp:
                data = json.load(resp)
        except Exception as exc:
            _dbg(f'Could not fetch MailHog messages: {exc}')
            return None
        recipients = []
        for item in data.get('items', []):
            to = item.get('To', [])
            if to:
                recipients.append(f'{to[0]["Mailbox"]}@{to[0]["Domain"]}')
        return recipients

    def _mh_clear_local() -> bool:
        url = f'http://{mh_host}:{mh_port}/api/v1/messages'
        if requests:
            try:
                requests.delete(url, timeout=TIMEOUT)
                return True
            except Exception as exc:
                _dbg(f'Could not clear MailHog messages via requests: {exc}')
        try:
            from urllib.request import Request

            req = Request(url, method='DELETE')
            with urlopen(req, timeout=TIMEOUT):
                return True
        except Exception as exc:
            _dbg(f'Could not clear MailHog messages via urllib: {exc}')
            return False

    # Reset DB and seed patterns
    try:
        with engine.connect() as conn:
            bt = _get_blocked_table()
            conn.execute(bt.delete())
            conn.execute(
                bt.insert(),
                [
                    {'pattern': 'blocked1@example.com', 'is_regex': False, 'test_mode': False},
                    {'pattern': '.*@blocked.com', 'is_regex': True, 'test_mode': False},
                ],
            )
            conn.commit()
            _dbg('db reset and seed ok')
    except Exception as exc:
        _dbg(f'db reset failed: {exc}')
        try:
            engine.dispose()
        except Exception:
            pass
        return []

    # Poll for blocker to apply new rules by attempting a blocked send until it is rejected
    def _blocked_applied() -> bool:
        try:
            _send_mail_local('blocked1@example.com', msg='probe')
            # If accepted, rules not yet applied
            return False
        except smtplib.SMTPRecipientsRefused as exc:
            codes = []
            for info in exc.recipients.values():
                try:
                    codes.append(int(info[0]))
                except Exception:
                    continue
            _dbg(f'blocked probe response codes={codes}')
            # Treat permanent failures (5xx) as success; 4xx means maps not yet ready
            return any(code >= 500 for code in codes)
        except Exception as exc:
            _dbg(f'blocked probe unexpected failure: {exc}')
            return False

    if not _wait_until(_blocked_applied, timeout=60, interval=1.0):
        _dbg('blocker did not apply rules within timeout; skipping')
        try:
            engine.dispose()
        except Exception:
            pass
        return []

    if not _mh_clear_local():
        _dbg('could not clear MailHog; skipping')
        try:
            engine.dispose()
        except Exception:
            pass
        return []

    # Send a trio of messages (one allowed, two blocked)
    for rcpt in ['blocked1@example.com', 'allowed@example.com', 'user@blocked.com']:
        try:
            _send_mail_local(rcpt)
        except Exception:
            pass

    def _allowed_delivered() -> bool:
        msgs = _mh_messages_local()
        return bool(msgs and ('allowed@example.com' in msgs))

    _wait_until(_allowed_delivered, timeout=15, interval=1.0)

    try:
        final = _mh_messages_local() or []
    finally:
        try:
            engine.dispose()
        except Exception:
            pass
    return final


def mailhog_counts():
    if not requests:
        print("'requests' not installed; cannot fetch MailHog counts.")
        return {}
    url = f'http://{MAILHOG_HOST}:{MAILHOG_PORT}/api/v2/messages?limit=10000'
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        data = resp.json()
    except Exception as exc:
        print('Could not fetch MailHog counts:', exc)
        return {}
    counts = {}
    for item in data.get('items', []):
        to = item.get('To', [])
        if to:
            r = f'{to[0]["Mailbox"]}@{to[0]["Domain"]}'
            counts[r] = counts.get(r, 0) + 1
    return counts


def main():
    if create_engine is None:
        print('SQLAlchemy not installed; skipping e2e demo.')
        return
    try:
        engine = create_engine(DB_URL)
    except Exception as exc:
        print('Could not create engine:', exc)
        return
    try:
        blocker.init_db(engine)
    except OperationalError as exc:
        print('Could not connect to database:', exc)
        return

    with engine.connect() as conn:
        conn.execute(blocker.blocked_table.delete())
        conn.execute(
            blocker.blocked_table.insert(),
            [
                {'pattern': 'blocked1@example.com', 'is_regex': False, 'test_mode': False},
                {'pattern': '.*@blocked.com', 'is_regex': True, 'test_mode': False},
            ],
        )
        conn.commit()
    # wait for service to pick up changes
    time.sleep(5)
    recipients = [
        'blocked1@example.com',
        'allowed@example.com',
        'user@blocked.com',
    ]
    for r in recipients:
        try:
            send_mail(r)
        except Exception as exc:
            print('send failed', r, exc)
    time.sleep(3)
    print('Delivered:', mailhog_messages())


def random_localpart(n=8):
    letters = 'abcdefghijklmnopqrstuvwxyz'
    return ''.join(random.choice(letters) for _ in range(n))


def generate_addresses(total: int):
    allowed = []
    blocked = []
    # Blocked individuals/domains/regex will be inserted into DB
    # Generate a mix of recipients across several domains
    allowed_domains = ['example.com', 'test.com', 'ok.org']
    blocked_domains = ['blocked.com', 'deny.org']

    # Some known individuals to test literal blocks
    individuals = [
        'blocked1@example.com',
        'alice@deny.org',
        'bob@blocked.com',
    ]

    # Populate pools
    for _ in range(total):
        if random.random() < 0.15:
            # generate address that will match regex like spam\d+
            lp = f'spam{random.randint(1, 9999)}'
            dom = random.choice(allowed_domains + blocked_domains)
            addr = f'{lp}@{dom}'
        else:
            dom = random.choice(allowed_domains + blocked_domains)
            lp = random_localpart()
            addr = f'{lp}@{dom}'

        # Bias: mix in some known individuals periodically
        if random.random() < 0.05:
            addr = random.choice(individuals)

        if dom in blocked_domains or addr in individuals or addr.startswith('spam'):
            blocked.append(addr)
        else:
            allowed.append(addr)

    # Ensure we have a special long-running allowed recipient we will block mid-run
    victim = 'victim@example.com'
    allowed.extend([victim] * max(20, total // 4))

    # Shuffle to interleave recipients
    random.shuffle(allowed)
    random.shuffle(blocked)
    all_addrs = allowed + blocked
    random.shuffle(all_addrs)
    return all_addrs, victim


def mass_demo(total: int = 200):
    if create_engine is None:
        print('SQLAlchemy not installed; skipping e2e mass demo.')
        return
    print(f'Starting mass demo with {total} messages...')
    try:
        engine = create_engine(DB_URL, connect_args={'connect_timeout': TIMEOUT})
        blocker.init_db(engine)
    except OperationalError as exc:
        print('Could not connect to database:', exc)
        return

    # Clear DB and MailHog for a clean slate
    with engine.connect() as conn:
        conn.execute(blocker.blocked_table.delete())
        conn.commit()
    mailhog_clear()

    # Insert initial blocks: one individual, one domain (regex), one regex class
    with engine.connect() as conn:
        conn.execute(
            blocker.blocked_table.insert(),
            [
                {'pattern': 'blocked1@example.com', 'is_regex': False},
                {'pattern': '.*@blocked.com', 'is_regex': True},
                {'pattern': '.*@deny\\.org', 'is_regex': True},
                {'pattern': '^spam[0-9]+@.*', 'is_regex': True},
            ],
        )
        conn.commit()

    # Allow blocker to propagate to postfix maps
    time.sleep(6)

    recipients, victim = generate_addresses(total)
    sent = 0
    mid_block_applied = False
    for i, rcpt in enumerate(recipients, start=1):
        try:
            send_mail(rcpt, msg=f'msg #{i}')
            sent += 1
        except Exception:
            # Expected for blocked recipients
            pass

        # After ~40% of sends, block the victim address while still sending
        if not mid_block_applied and i >= max(10, total // 2):
            with engine.connect() as conn:
                conn.execute(
                    blocker.blocked_table.insert(),
                    [
                        {'pattern': victim, 'is_regex': False, 'test_mode': False},
                    ],
                )
                conn.commit()
            mid_block_applied = True
            # Wait a bit for blocker to detect & reload postfix
            time.sleep(6)

    # Give MailHog a moment to ingest
    time.sleep(2)
    counts = mailhog_counts()
    victim_count = counts.get(victim, 0)
    print(f'Victim delivered count: {victim_count} (should be < attempted pre-block)')
    print('Top deliveries (sample):')
    for k, v in list(sorted(counts.items(), key=lambda x: -x[1]))[:10]:
        print(f'  {k}: {v}')

    # Quick sanity: explicitly verify blocked patterns did not deliver
    blocked_samples = [
        'blocked1@example.com',
        'bob@blocked.com',
        'alice@deny.org',
        'spam123@ok.org',
        'user@blocked.com',
    ]
    actually_delivered_blocked = [b for b in blocked_samples if counts.get(b)]
    if actually_delivered_blocked:
        print('Unexpected deliveries for blocked: ', actually_delivered_blocked)
    else:
        print('Blocked samples correctly rejected.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Postfix Blocker e2e demo')
    parser.add_argument('--mass', action='store_true', help='run mass traffic demo')
    parser.add_argument(
        '--total',
        type=int,
        default=200,
        help='total messages to attempt in mass demo',
    )
    args = parser.parse_args()
    if args.mass:
        mass_demo(total=args.total)
    else:
        main()
