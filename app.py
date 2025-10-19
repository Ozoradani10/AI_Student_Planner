# app.py — Païrent Autonomous Student Planner
from _future_ import annotations
import os, json, time, threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import streamlit as st

# Internal imports
from ai_parser import parse_updates_to_events
from scheduler import load_events, save_events
from portal_detector import discover_ics_links_from_emails
from portal_fetcher import fetch_ics_events
from email_reader import fetch_recent_emails

# --- Settings ---
TIMEZONE = ZoneInfo("Europe/Istanbul")
st.set_page_config(page_title="Païrent — AI Student Planner", layout="wide")

# --- UI HEADER ---
st.markdown("""
<div style='text-align:center;'>
    <h1 style='margin-bottom:0;'>🧠 Païrent — AI Student Planner</h1>
    <p style='opacity:0.8;'>Automatically reads your email, understands university updates, and builds your schedule — no typing.</p>
</div>
""", unsafe_allow_html=True)

# --- Helper: ISO parsing ---
def parse_iso(s: str):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

# --- Core Sync Logic ---
def run_auto_sync(email_bodies: list[str], email_subjects: list[str]):
    """Reads Gmail messages + auto-detects university portal calendars + AI event extraction."""
    TZ = ZoneInfo("Europe/Istanbul")
    all_events = []

    texts = (email_subjects or []) + (email_bodies or [])
    if not texts:
        return []

    # Discover ICS URLs
    ics_urls = set()
    if os.getenv("PORTAL_ICS_URL"):
        ics_urls.add(os.getenv("PORTAL_ICS_URL").strip())
    for url in discover_ics_links_from_emails(texts):
        ics_urls.add(url)

    # Fetch ICS events
    ics_events = []
    for url in ics_urls:
        ics_events.extend(fetch_ics_events(url, TZ))

    # Extract events via AI
    try:
        ai_events = parse_updates_to_events(os.getenv("OPENAI_API_KEY"), texts)
    except Exception as e:
        ai_events = []
        print("AI parsing failed:", e)

    # Merge and return everything
    all_events = (ai_events or []) + (ics_events or [])
    save_events(all_events)
    return all_events

# --- LEFT COLUMN: schedule ---
col1, col2 = st.columns([2,1])
with col1:
    st.subheader("📅 Your schedule")
    events = load_events()

    if not events:
        st.info("No events detected yet. Païrent will ingest your email/portal automatically soon.")
    else:
        upcoming = [e for e in events if (dt := parse_iso(e.get("when"))) is not None]
        upcoming.sort(key=lambda e: parse_iso(e["when"]))
        today = datetime.now(TIMEZONE).date()

        for e in upcoming:
            dt = parse_iso(e["when"])
            if not dt:
                continue
            label = dt.astimezone(TIMEZONE).strftime("%a %d %b, %H:%M")
            st.markdown(f"""
            <div style='padding:8px;margin:4px 0;border-radius:8px;background:#1e1e1e33;'>
                <b>{e.get("title","(no title)")}</b><br>
                <span style='opacity:0.8;'>{label}</span><br>
                <span style='font-size:12px;opacity:0.6;'>📍 {e.get("location","")}</span>
            </div>
            """, unsafe_allow_html=True)

# --- RIGHT COLUMN: controls ---
try:
    LAST_BG_SYNC = st.session_state.get("LAST_BG_SYNC")
except Exception:
    LAST_BG_SYNC = None

with col2:
    st.subheader("⚙ Connections & Controls")
    st.caption("IMAP + SMTP are read from your Streamlit Secrets. Portal ICS auto-detected.")
    st.caption("Timezone: Europe/Istanbul")
    st.caption(
        "Background auto-sync: ON · Last run: "
        + (LAST_BG_SYNC.astimezone(TIMEZONE).strftime("%Y-%m-%d %H:%M") if LAST_BG_SYNC else "—")
    )

    if st.button("🔄 Sync now (read email + portal + AI)"):
        st.info("Syncing… please wait ⏳")
        subjects, bodies = fetch_recent_emails(limit=25)
        results = run_auto_sync(bodies, subjects)
        if results:
            st.success(f"✅ {len(results)} events found and synced successfully!")
        else:
            st.warning("⚠ No new events found. Try again after receiving an email with schedule info.")

# -------------------- BACKGROUND AUTO SYNC (hourly) --------------------
def background_sync_loop():
    """Read Gmail + portal automatically every hour and merge events."""
    global LAST_BG_SYNC
    while True:
        try:
            subjects, bodies = fetch_recent_emails(limit=25)
            run_auto_sync(bodies, subjects)
            LAST_BG_SYNC = datetime.now(TIMEZONE)
            st.session_state["LAST_BG_SYNC"] = LAST_BG_SYNC
            print("[Païrent] Background sync OK at", LAST_BG_SYNC)
        except Exception as e:
            print("[Païrent] Background sync error:", e)
        time.sleep(3600)  # run again in 1 hour

if not st.session_state.get("BG_THREAD_STARTED"):
    threading.Thread(target=background_sync_loop, daemon=True).start()
    st.session_state["BG_THREAD_STARTED"] = True
# ----------------------------------------------------------------------

st.markdown("<hr>", unsafe_allow_html=True)
st.caption("© 2025 Païrent Autonomous Student Planner — built for Turkish universities 🇹🇷")
