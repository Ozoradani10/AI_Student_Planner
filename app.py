# app.py — Pairent autonomous dashboard (Europe/Istanbul)

from _future_ import annotations
import os, json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

from scheduler import start_background_worker, load_events

# --- Settings ---
TIMEZONE = ZoneInfo("Europe/Istanbul")  # Turkey time
TITLE = "Paϊrent — AI Student Planner"
SUB = "Automatically collects updates from your email & portal, understands them, builds your schedule, and emails reminders — no typing."
DATA_NOTE = "Events update automatically every few hours."
# ---------------

# Secrets / env
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")

# Kick off background worker once per process
if not OPENAI_API_KEY:
    st.error("❌ Missing OpenAI API key in Streamlit Secrets.")
    st.stop()
start_background_worker(OPENAI_API_KEY)

st.set_page_config(page_title=TITLE, page_icon="🫧", layout="wide")
st.markdown(
    """
    <style>
      .pairent-hero{
        background: linear-gradient(135deg,#0ea5e9 0%, #60a5fa 100%);
        padding:22px 28px;border-radius:16px;color:white;margin-bottom:18px;
      }
      .pill {display:inline-block;background:#0ea5e933;color:#93c5fd;border:1px solid #60a5fa55;padding:4px 9px;border-radius:999px;font-size:12px;margin-left:6px;}
      .card{background:rgba(255,255,255,0.03);border:1px solid #ffffff18;border-radius:14px;padding:14px 16px;margin:8px 0;}
      .muted{color:#a3a3a3;font-size:13px}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(f"""
<div class="pairent-hero">
  <h2 style="margin:0;">{TITLE}</h2>
  <div style="opacity:.95">{SUB}</div>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.columns([2,1])

with col1:
    st.subheader("Your schedule")
    events = load_events()
    if not events:
        st.info("No events detected yet. Pairent will ingest your email/portal automatically soon.")
    else:
        # group by date
        def parse_iso(s):
            try: 
                return datetime.fromisoformat(s)
            except: 
                return None
        upcoming = [e for e in events if (dt:=parse_iso(e.get("when","")))]
        upcoming.sort(key=lambda e: parse_iso(e["when"]))
        today = datetime.now(TIMEZONE).date()
        for e in upcoming:
            dt = parse_iso(e["when"])
            if not dt: 
                continue
            label = dt.astimezone(TIMEZONE).strftime("%a %d %b, %H:%M")
            st.markdown(
                f"""
                <div class="card">
                    <div><b>{e.get('title','')}</b> <span class="pill">{e.get('type','')}</span></div>
                    <div class="muted">🕒 {label}  {' | 📍 '+e['location'] if e.get('location') else ''}</div>
                    <div>{e.get('notes','')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.caption(DATA_NOTE)

with col2:
    st.subheader("Status")
    st.markdown(
        f"""
        <div class="card">
          <div>⏱ Timezone: <b>Europe/Istanbul</b></div>
          <div>🔁 Background sync: <b>ON</b> (every {os.getenv('SYNC_EVERY_HOURS','3')}h)</div>
          <div>📧 Reminders: <b>ON</b> (72h window)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption("Change frequency by adding SYNC_EVERY_HOURS = \"1|3|6\" to Streamlit Secrets (optional).")
