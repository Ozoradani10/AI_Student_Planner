# scheduler.py — background auto-sync + reminders (Europe/Istanbul)

from _future_ import annotations
import os, json, time, threading
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from email_reader import fetch_recent_emails
from portal_scraper import fetch_portal_texts
from ai_parser import parse_updates_to_events

# --- Settings ---
TIMEZONE = ZoneInfo("Europe/Istanbul")           # Turkey time
CHECK_EVERY_HOURS = int(os.getenv("SYNC_EVERY_HOURS", "3"))  # change via Secret if you want
DATA_DIR = "data"
EVENTS_JSON = os.path.join(DATA_DIR, "events.json")

SMTP_HOST = os.getenv("SMTP_HOST") or "smtp.gmail.com"
SMTP_PORT = int(os.getenv("SMTP_PORT") or "587")
SMTP_USER = os.getenv("SMTP_USER") or ""
SMTP_PASS = os.getenv("SMTP_PASS") or ""
SMTP_EMAIL = os.getenv("SMTP_EMAIL") or SMTP_USER
SMTP_NAME = os.getenv("SMTP_NAME") or "Pairent"
# -----------------

def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_events() -> list[dict]:
    if not os.path.exists(EVENTS_JSON):
        return []
    with open(EVENTS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def save_events(events: list[dict]) -> None:
    _ensure_dirs()
    with open(EVENTS_JSON, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

def _normalize_event(ev: dict) -> dict:
    """Ensure fields exist and convert 'when' to ISO if parseable."""
    out = {
        "type": ev.get("type") or "",
        "title": ev.get("title") or "",
        "when": ev.get("when") or "",
        "location": ev.get("location") or "",
        "notes": ev.get("notes") or "",
        "source": ev.get("source") or "",
        "created_at": ev.get("created_at") or datetime.now(TIMEZONE).isoformat()
    }
    return out

def _merge_events(old: list[dict], new: list[dict]) -> list[dict]:
    """
    Merge by (title, when, type). Very simple de-dup.
    """
    seen = {(e.get("title",""), e.get("when",""), e.get("type","")) for e in old}
    out = old[:]
    for n in new:
        key = (n.get("title",""), n.get("when",""), n.get("type",""))
        if key not in seen:
            out.append(n)
            seen.add(key)
    # sort by time (unknown times last)
    def _key(e):
        try:
            return datetime.fromisoformat(e["when"])
        except Exception:
            return datetime.max.replace(tzinfo=TIMEZONE)
    return sorted(out, key=_key)

def _send_email(to_addr: str, subject: str, html_body: str):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    if not (SMTP_USER and SMTP_PASS and to_addr):
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_NAME} <{SMTP_EMAIL}>"
    msg["To"] = to_addr
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_EMAIL, to_addr, msg.as_string())

def _format_event_line(e: dict) -> str:
    when = e.get("when","")
    title = e.get("title","")
    kind = e.get("type","")
    loc = e.get("location","")
    parts = [f"<b>{title}</b> ({kind})"]
    if when: parts.append(f"<br>🕒 {when}")
    if loc:  parts.append(f"<br>📍 {loc}")
    if e.get("notes"): parts.append(f"<br>📝 {e['notes']}")
    return "<div style='margin:8px 0;'>" + "".join(parts) + "</div>"

def _send_morning_summary(to_addr: str, events: list[dict]):
    today = datetime.now(TIMEZONE).date()
    tomorrow = today + timedelta(days=1)
    def parse_iso(s):
        try: return datetime.fromisoformat(s)
        except: return None
    todays = [e for e in events if (dt:=parse_iso(e.get("when",""))) and dt.date()==today]
    upcoming = [e for e in events if (dt:=parse_iso(e.get("when",""))) and today <= dt.date() < today+timedelta(days=7)]

    body = "<h2>📅 Today’s Schedule</h2>"
    body += ("".join(_format_event_line(e) for e in todays) or "<p>No events today.</p>")
    body += "<hr><h3>🔔 Coming up (7 days)</h3>"
    body += ("".join(_format_event_line(e) for e in upcoming) or "<p>No upcoming events.</p>")
    _send_email(to_addr, "Pairent — Morning Summary", f"<div style='font-family:Arial'>{body}</div>")

def _send_deadline_reminders(to_addr: str, events: list[dict]):
    now = datetime.now(TIMEZONE)
    soon = now + timedelta(hours=72)
    def parse_iso(s):
        try: return datetime.fromisoformat(s)
        except: return None
    window = [e for e in events if (dt:=parse_iso(e.get("when",""))) and now <= dt <= soon]
    if not window: return
    body = "<h2>⏰ Upcoming exams & deadlines (72h)</h2>" + "".join(_format_event_line(e) for e in window)
    _send_email(to_addr, "Pairent — Upcoming (72h)", f"<div style='font-family:Arial'>{body}</div>")

def _primary_user_email() -> str:
    """Use secrets SMTP_EMAIL as the owner’s address for summaries/reminders."""
    return SMTP_EMAIL or SMTP_USER

def run_sync_once(openai_api_key: str):
    """One full sync pass."""
    texts = []
    # 1) Ingest email
    try:
        texts.extend(fetch_recent_emails())
    except Exception as e:
        print("[email ingest] error:", e)

    # 2) Ingest portal (if configured)
    try:
        texts.extend(fetch_portal_texts())
    except Exception as e:
        print("[portal ingest] error:", e)

    # 3) AI → events
    try:
        ai_events = parse_updates_to_events(openai_api_key, texts) if texts else []
        ai_events = [_normalize_event(e) for e in ai_events]
    except Exception as e:
        print("[ai parse] error:", e)
        ai_events = []

    # 4) Merge & save
    current = load_events()
    merged = _merge_events(current, ai_events)
    save_events(merged)

    # 5) Notifications
    owner = _primary_user_email()
    if owner:
        _send_deadline_reminders(owner, merged)

def _loop(openai_api_key: str):
    while True:
        try:
            run_sync_once(openai_api_key)
        except Exception as e:
            print("[sync loop] error:", e)
        time.sleep(CHECK_EVERY_HOURS * 3600)

_worker_started = False
def start_background_worker(openai_api_key: str):
    global _worker_started
    if _worker_started:
        return
    _ensure_dirs()
    t = threading.Thread(target=_loop, args=(openai_api_key,), daemon=True)
    t.start()
    _worker_started = True
