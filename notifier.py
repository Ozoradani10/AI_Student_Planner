# notifier.py — Automatic reminder sender for Pairent
import os, smtplib, json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("Europe/Istanbul")
DATA_FILE = "data/events.json"

def load_events():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def send_email_reminder(to_email: str, password: str):
    """Send upcoming events (next 24 h) as email reminder automatically."""
    events = load_events()
    if not events: return

    now = datetime.now(TIMEZONE)
    upcoming = [e for e in events if "when" in e and
                datetime.fromisoformat(e["when"]) < now + timedelta(hours=24)]

    if not upcoming: return

    msg_body = "📅 Upcoming Events (Next 24 Hours)\n\n"
    for e in upcoming:
        msg_body += f"- {e.get('title')} at {e.get('when')} ({e.get('location','')})\n"

    msg = MIMEText(msg_body, "plain", "utf-8")
    msg["Subject"] = "Pairent AI – Your Upcoming Schedule"
    msg["From"] = to_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login(to_email, password)
            s.send_message(msg)
            print("Reminder sent.")
    except Exception as e:
        print("Send error:", e)
