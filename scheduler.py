# scheduler.py — background auto-sync + reminders (Europe/Istanbul)

from __future__ import annotations
import os, json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from email_reader import fetch_recent_emails
from ai_parser import parse_updates_to_events

# --- Settings ---
TIMEZONE = ZoneInfo("Europe/Istanbul")  # Turkey time
DATA_DIR = "data"
EVENTS_JSON = os.path.join(DATA_DIR, "events.json")

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

def load_events() -> list[dict]:
    """Load events from local storage (JSON file)."""
    if not os.path.exists(EVENTS_JSON):
        return []
    try:
        with open(EVENTS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_events(events: list[dict]):
    """Save events to local storage (JSON file)."""
    with open(EVENTS_JSON, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

def run_auto_sync():
    """Fetch emails, parse with AI, and save new events."""
    try:
        subjects, bodies = fetch_recent_emails(limit=25)
        texts = (subjects or []) + (bodies or [])
        if not texts:
            return []
        api_key = os.getenv("OPENAI_API_KEY")
        events = parse_updates_to_events(api_key, texts) or []
        save_events(events)
        return events
    except Exception as e:
        print("Auto-sync failed:", e)
        return []
