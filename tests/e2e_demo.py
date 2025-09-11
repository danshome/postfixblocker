"""Simple script to demonstrate end-to-end blocking behaviour.

It assumes the docker-compose environment is running.
"""
import os
import time
import smtplib
import requests
from sqlalchemy import create_engine

from app import blocker

DB_URL = os.environ.get(
    "BLOCKER_DB_URL", "postgresql://blocker:blocker@localhost:5433/blocker")


def send_mail(recipient: str, msg: str = "hello") -> None:
    with smtplib.SMTP("localhost", 1025) as smtp:
        smtp.sendmail("tester@example.com", [recipient], f"Subject: test\n\n{msg}")


def mailhog_messages():
    resp = requests.get("http://localhost:8025/api/v2/messages")
    data = resp.json()
    recipients = []
    for item in data.get("items", []):
        to = item.get("To", [])
        if to:
            recipients.append(f"{to[0]['Mailbox']}@{to[0]['Domain']}")
    return recipients


def main():
    engine = create_engine(DB_URL)
    blocker.init_db(engine)
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
