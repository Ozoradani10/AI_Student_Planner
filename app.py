# app.py — Pairent Autonomous Student Planner (Fully Working Version)

from _future_ import annotations
import os, json, time, threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import streamlit as st

from scheduler import run_auto_sync, load_events, save_events

# --- Settings ---
TIMEZONE = ZoneInfo("Europe/Istanbul")
TITLE = "Pairent — AI Student Planner"
SUB = "Automatically collects updates from your email & portal, understands them with AI, and builds your schedule — no typing."

st.set_page_config(page_title=TITLE, layout="wide")

# --- Header ---
st.markdown(f"""
<div style='text-align:center;'>
    <h1 style='margin-bottom:0;'>{TITLE}</h1>
    <p style='opacity:0.85;'>{SUB}</p>
</div>
""", unsafe_allow_html=True)

# --- Two columns: Schedule + Controls ---
col1, col2 = st.columns([2,1])

# LEFT COLUMN: Schedule
with col1:
    st.subheader("📅 Your Schedule")
    events = load_events()
    if not events:
        st.info("No events detected yet. Click *Sync now* or *Generate with AI*.")
    else:
        def parse_iso(s):
            try:
                return datetime.fromisoformat(s)
            except:
                return None
        events = sorted(events, key=lambda e: parse_iso(e.get("when") or ""))
        today = datetime.now(TIMEZONE).date()

        for e in events:
            dt = parse_iso(e.get("when"))
            if not dt:
                continue
            label = dt.astimezone(TIMEZONE).strftime("%a %d %b • %H:%M")
            st.markdown(f"""
            <div style='padding:8px;margin:4px 0;border-radius:8px;background:#1e1e1e3a;'>
                <b>{e.get("title","(no title)")}</b><br>
                <span style='opacity:0.8;'>{label}</span><br>
                <span style='font-size:12px;opacity:0.6;'>📍 {e.get("location","")}</span>
            </div>
            """, unsafe_allow_html=True)

# RIGHT COLUMN: Controls
with col2:
    st.subheader("⚙ Controls")
    st.caption("IMAP + OpenAI come from Streamlit Secrets. Timezone: Europe/Istanbul")

    # --- Sync Now ---
    if st.button("🔄 Sync now (read email + portal + AI)"):
        st.info("Syncing... please wait ⏳")
        results = run_auto_sync()
        if results:
            st.success(f"✅ {len(results)} new events found and synced!")
        else:
            st.warning("⚠ No new events found. Try again later or send a schedule email.")

    # --- AI Demo Schedule Button ---
    if st.button("🧠 Generate with AI (demo)"):
        st.info("Generating your sample AI-based schedule...")
        demo_events = [
            {"type": "class", "title": "AI Fundamentals", "when": "2025-10-21T09:00:00", "location": "Room 203", "notes": "Bring your laptop"},
            {"type": "exam", "title": "Math Midterm", "when": "2025-10-23T13:00:00", "location": "Hall B", "notes": "Chapters 1–4"},
            {"type": "meeting", "title": "Project Group Discussion", "when": "2025-10-25T15:00:00", "location": "Library", "notes": "Discuss AI Planner"},
        ]
        save_events(demo_events)
        st.success("✅ AI-generated sample schedule created successfully!")

# --- Footer ---
st.markdown("<hr>", unsafe_allow_html=True)
st.caption("© 2025 Pairent Autonomous Student Planner — built for Turkish universities 🇹🇷")
