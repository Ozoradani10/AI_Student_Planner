# app.py — Pairent Autonomous Student Planner
import streamlit as st
import os, json
from datetime import datetime
from zoneinfo import ZoneInfo

from scheduler import run_auto_sync
from email_reader import fetch_recent_emails
from portal_scraper import fetch_portal_texts

# --- CONFIG ---
TIMEZONE = ZoneInfo("Europe/Istanbul")

st.set_page_config(page_title="Pairent – AI Student Planner", layout="wide")

st.title("📘 Pairent — AI Student Planner")
st.caption("Automatically collects updates from your email & portal, understands them with AI, builds your schedule — no typing.")

# --- LOGIN ---
st.sidebar.header("🔒 Student Login")
email = st.sidebar.text_input("University Email")
password = st.sidebar.text_input("App Password (Gmail App-specific password)", type="password")

if not email or not password:
    st.warning("Please sign in with your Gmail app password.")
    st.stop()

# --- MAIN ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🗓 Your schedule")

    events_path = "events.json"
    if os.path.exists(events_path):
        with open(events_path, "r", encoding="utf-8") as f:
            events = json.load(f)
    else:
        events = []

    if not events:
        st.info("No events yet. Click *Sync now* to ingest your email/portal.")
    else:
        events.sort(key=lambda e: e.get("when", ""))
        for e in events:
            title = e.get("title", "Untitled")
            when = e.get("when", "")
            loc = e.get("location", "")
            st.markdown(f"{title}**  \n🕓 {when}  \n📍 {loc}")

with col2:
    st.subheader("⚙ Controls")
    st.caption("IMAP + OpenAI come from Streamlit Secrets. Portal auto-detects. (Timezone: Europe/Istanbul)")

    # --- SYNC BUTTON ---
    if st.button("🔄 Sync now (read email + portal + AI)"):
        st.info("Syncing... please wait ⏳")
        subjects, bodies = fetch_recent_emails(email=email, app_password=password, limit=25)
        results = run_auto_sync(bodies, subjects)
        if results:
            st.success(f"{len(results)} new events found and synced successfully!")
        else:
            st.warning("No new events found. Try again after receiving a new schedule email.")

    # --- GENERATE WITH AI (Demo) ---
    if st.button("🧠 Generate with AI (demo)"):
        st.info("Generating your AI-based sample schedule...")
        demo_events = [
            {"type": "class", "title": "AI Fundamentals", "when": "2025-10-21T09:00:00", "location": "Room 201"},
            {"type": "meeting", "title": "Math Midterm", "when": "2025-10-23T16:00:00", "location": "Main Hall"},
            {"type": "notice", "title": "Project Discussion", "when": "2025-10-25T18:00:00", "location": "Library"},
        ]
        with open(events_path, "w", encoding="utf-8") as f:
            json.dump(demo_events, f, ensure_ascii=False, indent=2)
        st.success("Demo schedule generated successfully!")

# --- FOOTER ---
st.markdown("---")
st.caption("© 2025 Pairent Autonomous Student Planner – built for Turkish universities 🇹🇷")
