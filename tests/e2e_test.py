"""Simple script to demonstrate end-to-end blocking behaviour.

The script assumes the docker-compose environment is running. If any of the
services are unavailable the operations below will timeout quickly rather than
hang indefinitely.

It can be run from the host or from within a container by configuring hosts
and ports with the environment variables:

- ``SMTP_HOST`` (default ``localhost``)
- ``SMTP_PORT`` (default ``1025``)
- ``MAILHOG_HOST`` (default ``localhost``)
- ``MAILHOG_PORT`` (default ``8025``)
- ``BLOCKER_DB_URL`` (default
  ``postgresql://blocker:blocker@localhost:5433/blocker``)
"""
import argparse
import json
import os
import random
import sys
import time
import smtplib
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

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

# Import blocker with flexible fallbacks.
# 1) Try package import (when running from repo root)
# 2) Try local module import (when running inside /opt/app in the container)
# 3) As a last resort, prepend repo root to sys.path and retry package import
try:  # pragma: no cover - import shim
    from app import blocker  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    try:
        import blocker  # type: ignore
    except ModuleNotFoundError:
        ROOT = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(ROOT))
        from app import blocker  # type: ignore

DB_URL = os.environ.get(
    "BLOCKER_DB_URL", "postgresql://blocker:blocker@localhost:5433/blocker"
)

SMTP_HOST = os.environ.get("SMTP_HOST", "localhost")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "1025"))
MAILHOG_HOST = os.environ.get("MAILHOG_HOST", "localhost")
MAILHOG_PORT = int(os.environ.get("MAILHOG_PORT", "8025"))

TIMEOUT = 5


def send_mail(recipient: str, msg: str = "hello") -> None:
    """Send a message through the Postfix instance."""
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=TIMEOUT) as smtp:
        smtp.sendmail(
            "tester@example.com", [recipient], f"Subject: test\n\n{msg}"
        )


def mailhog_messages():
    """Return list of recipients captured by MailHog."""
    try:
        with urlopen(
            f"http://{MAILHOG_HOST}:{MAILHOG_PORT}/api/v2/messages?limit=10000",
            timeout=TIMEOUT,
        ) as resp:
            data = json.load(resp)
    except URLError as exc:
        print("Could not fetch MailHog messages:", exc)
        return []

    recipients = []
    for item in data.get("items", []):
        to = item.get("To", [])
        if to:
            recipients.append(f"{to[0]['Mailbox']}@{to[0]['Domain']}")
    return recipients


def mailhog_clear():
    url = f"http://{MAILHOG_HOST}:{MAILHOG_PORT}/api/v1/messages"
    if requests:
        try:
            requests.delete(url, timeout=TIMEOUT)
            return
        except Exception as exc:
            print("Could not clear MailHog messages via requests:", exc)
    # Fallback to urllib with explicit DELETE method
    try:
        from urllib.request import Request
        req = Request(url, method="DELETE")
        with urlopen(req, timeout=TIMEOUT):
            pass
    except Exception as exc:
        print("Could not clear MailHog messages via urllib:", exc)


def _dbg(msg: str):
    if os.environ.get("E2E_DEBUG") == "1":
        print(msg)


def run_e2e_scenario(db_url: str, smtp_host: str, smtp_port: int, mh_host: str, mh_port: int):
    """Run a minimal e2e scenario and return delivered recipients.

    Assumes a Postfix + blocker service is running and configured to use the
    same backend as db_url.
    """
    global DB_URL, SMTP_HOST, SMTP_PORT, MAILHOG_HOST, MAILHOG_PORT
    DB_URL = db_url
    SMTP_HOST = smtp_host
    SMTP_PORT = smtp_port
    MAILHOG_HOST = mh_host
    MAILHOG_PORT = mh_port

    if create_engine is None:
        return []
    try:
        engine = create_engine(DB_URL)
        _dbg("engine created")
    except Exception as exc:
        _dbg(f"engine creation failed: {exc}")
        return []
    try:
        blocker.init_db(engine)
        _dbg("init_db ok")
    except Exception as exc:
        _dbg(f"init_db failed: {exc}")
        return []

    # Reset DB and MailHog
    try:
        with engine.connect() as conn:
            conn.execute(blocker.get_blocked_table().delete())
            conn.execute(blocker.get_blocked_table().insert(), [
                {"pattern": "blocked1@example.com", "is_regex": False},
                {"pattern": ".*@blocked.com", "is_regex": True},
            ])
            conn.commit()
            _dbg("db reset and seed ok")
    except Exception as exc:
        _dbg(f"db reset failed: {exc}")
        return []

    # Allow blocker to detect and reload
    time.sleep(6)
    mailhog_clear()

    for rcpt in ["blocked1@example.com", "allowed@example.com", "user@blocked.com"]:
        try:
            send_mail(rcpt)
        except Exception:
            pass

    time.sleep(2)
    return mailhog_messages()


def mailhog_counts():
    if not requests:
        print("'requests' not installed; cannot fetch MailHog counts.")
        return {}
    url = f"http://{MAILHOG_HOST}:{MAILHOG_PORT}/api/v2/messages?limit=10000"
    try:
        resp = requests.get(url, timeout=TIMEOUT)
        data = resp.json()
    except Exception as exc:
        print("Could not fetch MailHog counts:", exc)
        return {}
    counts = {}
    for item in data.get("items", []):
        to = item.get("To", [])
        if to:
            r = f"{to[0]['Mailbox']}@{to[0]['Domain']}"
            counts[r] = counts.get(r, 0) + 1
    return counts


def main():
    if create_engine is None:
        print("SQLAlchemy not installed; skipping e2e demo.")
        return
    try:
        engine = create_engine(DB_URL)
    except Exception as exc:
        print("Could not create engine:", exc)
        return
    try:
        blocker.init_db(engine)
    except OperationalError as exc:
        print("Could not connect to database:", exc)
        return

    with engine.connect() as conn:
        conn.execute(blocker.blocked_table.delete())
        conn.execute(blocker.blocked_table.insert(), [
            {"pattern": "blocked1@example.com", "is_regex": False},
            {"pattern": ".*@blocked.com", "is_regex": True},
        ])
        conn.commit()
    # wait for service to pick up changes
    time.sleep(5)
    recipients = [
        "blocked1@example.com",
        "allowed@example.com",
        "user@blocked.com",
    ]
    for r in recipients:
        try:
            send_mail(r)
        except Exception as exc:
            print("send failed", r, exc)
    time.sleep(3)
    print("Delivered:", mailhog_messages())


def random_localpart(n=8):
    letters = "abcdefghijklmnopqrstuvwxyz"
    return "".join(random.choice(letters) for _ in range(n))


def generate_addresses(total: int):
    allowed = []
    blocked = []
    # Blocked individuals/domains/regex will be inserted into DB
    # Generate a mix of recipients across several domains
    allowed_domains = ["example.com", "test.com", "ok.org"]
    blocked_domains = ["blocked.com", "deny.org"]

    # Some known individuals to test literal blocks
    individuals = [
        "blocked1@example.com",
        "alice@deny.org",
        "bob@blocked.com",
    ]

    # Populate pools
    for _ in range(total):
        if random.random() < 0.15:
            # generate address that will match regex like spam\d+
            lp = f"spam{random.randint(1, 9999)}"
            dom = random.choice(allowed_domains + blocked_domains)
            addr = f"{lp}@{dom}"
        else:
            dom = random.choice(allowed_domains + blocked_domains)
            lp = random_localpart()
            addr = f"{lp}@{dom}"

        # Bias: mix in some known individuals periodically
        if random.random() < 0.05:
            addr = random.choice(individuals)

        if dom in blocked_domains or addr in individuals or addr.startswith("spam"):
            blocked.append(addr)
        else:
            allowed.append(addr)

    # Ensure we have a special long-running allowed recipient we will block mid-run
    victim = "victim@example.com"
    allowed.extend([victim] * max(20, total // 4))

    # Shuffle to interleave recipients
    random.shuffle(allowed)
    random.shuffle(blocked)
    all_addrs = allowed + blocked
    random.shuffle(all_addrs)
    return all_addrs, victim


def mass_demo(total: int = 200):
    if create_engine is None:
        print("SQLAlchemy not installed; skipping e2e mass demo.")
        return
    print(f"Starting mass demo with {total} messages...")
    try:
        engine = create_engine(DB_URL, connect_args={"connect_timeout": TIMEOUT})
        blocker.init_db(engine)
    except OperationalError as exc:
        print("Could not connect to database:", exc)
        return

    # Clear DB and MailHog for a clean slate
    with engine.connect() as conn:
        conn.execute(blocker.blocked_table.delete())
        conn.commit()
    mailhog_clear()

    # Insert initial blocks: one individual, one domain (regex), one regex class
    with engine.connect() as conn:
        conn.execute(blocker.blocked_table.insert(), [
            {"pattern": "blocked1@example.com", "is_regex": False},
            {"pattern": ".*@blocked.com", "is_regex": True},
            {"pattern": ".*@deny\\.org", "is_regex": True},
            {"pattern": "^spam[0-9]+@.*", "is_regex": True},
        ])
        conn.commit()

    # Allow blocker to propagate to postfix maps
    time.sleep(6)

    recipients, victim = generate_addresses(total)
    sent = 0
    mid_block_applied = False
    for i, rcpt in enumerate(recipients, start=1):
        try:
            send_mail(rcpt, msg=f"msg #{i}")
            sent += 1
        except Exception as exc:
            # Expected for blocked recipients
            pass

        # After ~40% of sends, block the victim address while still sending
        if not mid_block_applied and i >= max(10, total // 2):
            with engine.connect() as conn:
                conn.execute(blocker.blocked_table.insert(), [
                    {"pattern": victim, "is_regex": False},
                ])
                conn.commit()
            mid_block_applied = True
            # Wait a bit for blocker to detect & reload postfix
            time.sleep(6)

    # Give MailHog a moment to ingest
    time.sleep(2)
    counts = mailhog_counts()
    victim_count = counts.get(victim, 0)
    print(f"Victim delivered count: {victim_count} (should be < attempted pre-block)")
    print("Top deliveries (sample):")
    for k, v in list(sorted(counts.items(), key=lambda x: -x[1]))[:10]:
        print(f"  {k}: {v}")

    # Quick sanity: explicitly verify blocked patterns did not deliver
    blocked_samples = [
        "blocked1@example.com",
        "bob@blocked.com",
        "alice@deny.org",
        "spam123@ok.org",
        "user@blocked.com",
    ]
    actually_delivered_blocked = [b for b in blocked_samples if counts.get(b)]
    if actually_delivered_blocked:
        print("Unexpected deliveries for blocked: ", actually_delivered_blocked)
    else:
        print("Blocked samples correctly rejected.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Postfix Blocker e2e demo")
    parser.add_argument("--mass", action="store_true", help="run mass traffic demo")
    parser.add_argument("--total", type=int, default=200, help="total messages to attempt in mass demo")
    args = parser.parse_args()
    if args.mass:
        mass_demo(total=args.total)
    else:
        main()
