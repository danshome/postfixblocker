"""Simple script to demonstrate end-to-end blocking behaviour.

The script assumes the docker-compose environment is running.  If any of the
services are unavailable the operations below will timeout quickly rather than
hang indefinitely.
"""
import json
import os
import sys
import time
import smtplib
from urllib.request import urlopen
from urllib.error import URLError

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

# Ensure repository root is on the import path so `app` can be imported when
# running the script directly.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from app import blocker

DB_URL = os.environ.get(
    "BLOCKER_DB_URL", "postgresql://blocker:blocker@localhost:5433/blocker")

TIMEOUT = 5


def send_mail(recipient: str, msg: str = "hello") -> None:
    """Send a message through the local Postfix instance."""
    with smtplib.SMTP("localhost", 1025, timeout=TIMEOUT) as smtp:
        smtp.sendmail(
            "tester@example.com", [recipient], f"Subject: test\n\n{msg}"
        )


def mailhog_messages():
    """Return list of recipients captured by MailHog."""
    try:
        with urlopen(
            "http://localhost:8025/api/v2/messages", timeout=TIMEOUT
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


def main():
    try:
        engine = create_engine(DB_URL)
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


if __name__ == "__main__":
    main()
