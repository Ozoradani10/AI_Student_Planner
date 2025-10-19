# app.py — Païrent (manual sync version)
from __future__ import annotations

import os, json
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st

# local modules
from email_reader import fetch_recent_emails   # returns (subjects, bodies)
from ai_parser import parse_updates_to_events  # OpenAI JSON parser
from scheduler import load_events, save_events # tiny JSON store on disk

# --- config ---
TIMEZONE = ZoneInfo("Europe/Istanbul")
st.set_page_config(page_title="Païrent — AI Student Planner", layout="wide")

# --- header ---
TITLE = "Païrent — AI Student Planner"
SUB   = ("Automatically collects university updates from your email, "
         "understands them with AI, and builds your schedule — no typing.")

st.markdown(
    f"""
    <div style='text-align:left;'>
      <h1 style='margin:0 0 6px 0;'>🧠 {TITLE}</h1>
      <div style='opacity:.85'>{SUB}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

def parse_iso(s: str):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

def sync_now() -> list[dict]:
    """Read recent emails, ask AI to extract events, save & return them."""
    # 1) get last ~25 emails (subjects + bodies)
    subjects, bodies = fetch_recent_emails(limit=25)
    texts = (subjects or []) + (bodies or [])
    if not texts:
        return []

    # 2) AI -> list of events
    api_key = os.getenv("OPENAI_API_KEY")
    events = parse_updates_to_events(api_key, texts) or []

    # 3) persist
    save_events(events)
    return events

col1, col2 = st.columns([2, 1])

# LEFT: schedule
with col1:
    st.subheader("📅 Your schedule")
    events = load_events()

    if not events:
        st.info("No events yet. Click *Sync now* to ingest your email.")
    else:
        # sort by time and show
        events_sorted = [e for e in events if parse_iso(e.get("when"))]
        events_sorted.sort(key=lambda e: parse_iso(e["when"]))

        for e in events_sorted:
            dt = parse_iso(e["when"]).astimezone(TIMEZONE)
            label = dt.strftime("%a %d %b, %H:%M")
            st.markdown(
                f"""
                <div style='padding:10px;margin:6px 0;border-radius:8px;
                            background:#1c1c1f;border:1px solid #2a2a2e;'>
                  <b>{e.get("title","(no title)")}</b><br>
                  <span style='opacity:.8'>{label}</span><br>
                  <span style='font-size:12px;opacity:.6'>📍 {e.get("location","")}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

# RIGHT: controls
with col2:
    st.subheader("⚙ Controls")
    st.caption("IMAP & OpenAI come from Streamlit Secrets. Timezone: Europe/Istanbul")

    if st.button("🔄 Sync now (read email + AI)"):
        with st.spinner("Syncing…"):
            new_events = sync_now()

        if new_events:
            st.success(f"✅ {len(new_events)} events synced.")
        else:
            st.warning("No new events were found in recent emails.")

st.markdown("<hr>", unsafe_allow_html=True)
st.caption("© 2025 Païrent — Autonomous Student Planner for Turkish universities 🇹🇷")
