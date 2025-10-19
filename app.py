# app.py — Pairent Autonomous Student Planner (Full AI Version + Notifications)
from __future__ import annotations
import os, json, threading, time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import streamlit as st

from scheduler import run_auto_sync, load_events, save_events
from email_reader import fetch_recent_emails
from portal_scraper import fetch_portal_texts
from notifier import send_email_reminder

# --- CONFIG ---
TIMEZONE = ZoneInfo("Europe/Istanbul")
TITLE = "Pairent — AI Student Planner"
SUB = "Autonomous AI agent that collects university updates, understands them, and reminds you — no typing."

st.set_page_config(page_title=TITLE, layout="wide")

# --- LOGIN PANEL ---
st.sidebar.title("🔐 Student Login")
email = st.sidebar.text_input("University Email")
password = st.sidebar.text_input("App Password (Gmail App-specific password)", type="password")

if not email or not password:
    st.warning("Please sign in with your student account to continue.")
    st.stop()

# Store credentials for all modules
os.environ["IMAP_USER"] = email
os.environ["IMAP_PASS"] = password
os.environ["SMTP_USER"] = email
os.environ["SMTP_PASS"] = password

# --- HEADER ---
st.markdown(f"""
<div style='text-align:center;'>
  <h1 style='margin-bottom:0;'>{TITLE}</h1>
  <p style='opacity:0.85;'>{SUB}</p>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns([2,1])

# --- LEFT: SCHEDULE ---
with col1:
    st.subheader("📅 Your Schedule")
    events = load_events()
    if not events:
        st.info("No events detected yet. Click *Sync now* or *Generate with AI*.")
    else:
        def parse_iso(s):
            try: return datetime.fromisoformat(s)
            except: return None

        events = sorted(events, key=lambda e: parse_iso(e.get("when") or ""))
        for e in events:
            dt = parse_iso(e.get("when"))
            if not dt: continue
            label = dt.astimezone(TIMEZONE).strftime("%a %d %b • %H:%M")
            st.markdown(f"""
            <div style='padding:8px;margin:4px 0;border-radius:8px;background:#1e1e1e3a;'>
              <b>{e.get("title","(no title)")}</b><br>
              <span style='opacity:0.8;'>{label}</span><br>
              <span style='font-size:12px;opacity:0.6;'>📍 {e.get("location","")}</span>
            </div>
            """, unsafe_allow_html=True)

# --- RIGHT: CONTROLS ---
with col2:
    st.subheader("⚙ Controls")

    if st.button("🔄 Sync now (read email + portal + AI)"):
        st.info("Syncing... please wait ⏳")
        subjects, bodies = fetch_recent_emails(limit=25)
        portal_texts = fetch_portal_texts(bodies)
        results = run_auto_sync(bodies + portal_texts)
        if results:
            st.success(f"✅ {len(results)} events synced successfully!")
        else:
            st.warning("⚠ No new events found.")

    if st.button("🧠 Generate with AI (demo)"):
        st.info("Generating AI-based demo schedule...")
        demo_events = [
            {"type":"class","title":"AI Fundamentals","when":"2025-10-21T09:00:00","location":"Room 203","notes":"Bring laptop"},
            {"type":"exam","title":"Math Midterm","when":"2025-10-23T13:00:00","location":"Hall B","notes":"Ch 1–4"},
            {"type":"meeting","title":"Project Discussion","when":"2025-10-25T15:00:00","location":"Library","notes":"Discuss AI Planner"},
        ]
        save_events(demo_events)
        st.success("✅ AI schedule generated!")

    if st.button("📧 Send Reminder Now"):
        st.info("Sending reminders to your inbox 📨...")
        send_email_reminder(email, password)
        st.success("✅ Reminder sent successfully!")

st.markdown("<hr>", unsafe_allow_html=True)
st.caption("© 2025 Pairent Autonomous Student Planner — built for Turkish universities 🇹🇷")
