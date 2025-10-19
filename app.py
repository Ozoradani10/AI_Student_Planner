# app.py — Pairent instant-response (richer UI + schedule email)
import os, json
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st

from email_reader import fetch_recent_emails
from ai_parser import extract_events_from_texts, generate_study_plan
from notifier import send_email

APP_TITLE = "📘 Pairent — AI Student Planner"
SUB = "Automatically collects updates from your email, understands them with AI, and builds your schedule — no typing."
DEFAULT_TZ = "Europe/Istanbul"

# ---------- Styles ----------
HERO_CSS = """
<style>
:root { --pairent-accent:#00ADB5; }
.stApp { background:#0b0f14; }
h1,h2,h3,h4 { color:#f5f7fa !important; }
.small-note{opacity:.75;font-size:.95rem}
.hero{
  padding:18px;border-radius:16px;background:linear-gradient(135deg,#0f1a26 0%,#0c1a1f 100%);
  border:1px solid #1e2a38;margin-bottom:10px
}
.card{padding:12px 14px;border-radius:12px;background:#11161e;border:1px solid #1f2a37;margin:10px 0;}
.divider{height:1px;background:#1c2835;margin:12px 0}
.event{padding:10px;border-radius:10px;background:#0f1720;border:1px solid #1e2a38;margin:6px 0}
.event .title{font-weight:700;color:#e7f9ff}
.event .when{opacity:.9}
.event .where{opacity:.8;font-size:.95rem}
.btn-primary button{background:#00ADB5!important;border-color:#00ADB5!important;color:#041217!important;font-weight:700}
footer{visibility:hidden}
</style>
"""

st.set_page_config(page_title="Pairent — AI Planner", page_icon="📘", layout="wide")
st.markdown(HERO_CSS, unsafe_allow_html=True)

# ---------- Sidebar: login ----------
with st.sidebar:
    st.markdown("### 🔐 Student Login")
    email_addr = st.text_input("Email (Gmail recommended)", key="login_email", placeholder="you@gmail.com")
    app_pass   = st.text_input("App Password (16 chars, no spaces)", key="login_pass", type="password")
    tz_choice  = st.selectbox("Timezone", ["Europe/Istanbul","Europe/Berlin","Europe/London","Asia/Almaty","Asia/Dubai","UTC"], index=0)
    st.session_state["tz"] = ZoneInfo(tz_choice)
    st.caption("Use a Google *App Password* (Security → App passwords). Type without spaces.")

st.markdown(f"""
<div class="hero">
  <h1 style="margin:0;">{APP_TITLE}</h1>
  <div class="small-note">{SUB}</div>
</div>
""", unsafe_allow_html=True)

left, right = st.columns([2,1])

# ---------- LEFT: schedule ----------
with left:
    st.subheader("🗓 Your schedule")
    events = st.session_state.get("events", [])

    def _parse_iso(s):
        try:
            return datetime.fromisoformat(s.replace("Z","+00:00"))
        except Exception:
            return None

    if events:
        events = [e for e in events if _parse_iso(e.get("when",""))]
        events.sort(key=lambda e: _parse_iso(e["when"]))
        for e in events:
            dt_local = _parse_iso(e["when"]).astimezone(st.session_state["tz"])
            label = dt_local.strftime("%a %d %b, %H:%M")
            st.markdown(f"""
            <div class="event">
              <div class="title">{e.get('title','(no title)')}</div>
              <div class="when">🕒 {label}</div>
              <div class="where">📍 {e.get('location','')}</div>
              <div class="small-note">{e.get('notes','')}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No events detected yet. As soon as related emails arrive, Pairent will parse them and populate your schedule automatically.")

    # Email my schedule
    if events and st.button("📧 Email my schedule", use_container_width=True):
        if not email_addr or not app_pass:
            st.error("Fill email + app password in the sidebar.")
        else:
            rows = []
            for e in events:
                dt_local = _parse_iso(e["when"]).astimezone(st.session_state["tz"])
                rows.append(f"<tr><td>{dt_local.strftime('%a %d %b, %H:%M')}</td><td>{e.get('title','')}</td><td>{e.get('location','')}</td><td>{e.get('notes','')}</td></tr>")
            html = f"""
            <div style="font-family:Inter,Arial,sans-serif">
              <h2 style="color:#00ADB5;margin:0 0 8px">Your Upcoming Schedule</h2>
              <table cellpadding="8" cellspacing="0" style="border-collapse:collapse;border:1px solid #e6eef2">
                <thead><tr style="background:#f3fbfc"><th align="left">When</th><th align="left">Title</th><th align="left">Where</th><th align="left">Notes</th></tr></thead>
                <tbody>{''.join(rows)}</tbody>
              </table>
              <p style="opacity:.7">— Pairent</p>
            </div>
            """
            try:
                send_email(email_addr, app_pass, email_addr, "Your schedule — Pairent", html)
                st.success(f"Schedule emailed to {email_addr}")
            except Exception as e:
                st.error(f"Could not send: {e}")

# ---------- RIGHT: controls ----------
with right:
    st.subheader("⚙ Controls")
    st.caption("IMAP + OpenAI use your sidebar login and server secrets.")

    # SYNC NOW
    if st.button("📥 Sync now (read email + AI)", use_container_width=True):
        if not email_addr or not app_pass:
            st.error("Please fill your email and App Password in the sidebar.")
        else:
            with st.spinner("Reading Inbox and extracting events…"):
                subjects, bodies = fetch_recent_emails(email_addr, app_pass, limit=25)
                if not bodies:
                    st.warning("No emails read (Inbox empty or IMAP login failed).")
                else:
                    found = extract_events_from_texts(bodies + subjects)
                    current = st.session_state.get("events", [])
                    # merge & dedupe
                    seen = {(e.get("title",""), e.get("when","")) for e in current}
                    for e in found:
                        key = (e.get("title",""), e.get("when",""))
                        if key not in seen:
                            current.append(e); seen.add(key)
                    st.session_state["events"] = current
                    st.success(f"Parsed {len(found)} new event(s).")

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    # GENERATE AI PLAN
    st.markdown("### 🤖 Generate AI Plan")
    prompt = st.text_input("Goal (one prompt)", placeholder="prepare for math midterm")
    duration = st.selectbox("Plan type", ["Daily","Weekly","Monthly"], index=1)
    if st.button("✨ Generate AI Plan", use_container_width=True):
        if not prompt.strip():
            st.warning("Please enter a goal.")
        else:
            with st.spinner("Creating your personalized plan…"):
                plan_md = generate_study_plan(prompt, duration)
                st.session_state["latest_plan"] = plan_md
            st.success("Plan generated successfully!")

    if st.session_state.get("latest_plan"):
        st.markdown("#### 📋 Your Plan")
        st.markdown(st.session_state["latest_plan"])

        if st.button("📧 Email me this plan", use_container_width=True):
            if not email_addr or not app_pass:
                st.error("Fill email + app password in the sidebar.")
            else:
                try:
                    send_email(
                        smtp_user=email_addr,
                        smtp_pass=app_pass,
                        to=email_addr,
                        subject=f"Your {duration} AI Study Plan — Pairent",
                        html=f"""<div style="font-family:Inter,Arial,sans-serif;color:#111">
                        <h2 style="color:#00ADB5;margin:0 0 6px">Your {duration} AI Study Plan</h2>
                        <div style="background:#f7fbfc;border:1px solid #d8eef2;border-radius:10px;padding:14px">{st.session_state["latest_plan"].replace('\n','<br>')}</div>
                        <p style="opacity:.7">— Pairent</p></div>"""
                    )
                    st.info(f"Plan sent to {email_addr} ✅")
                except Exception as e:
                    st.error(f"Could not send email: {e}")

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

    # DEBUG (shows last subjects so you know IMAP worked)
    with st.expander("🔎 Debug: show last Inbox subjects"):
        if email_addr and app_pass:
            try:
                subs, _ = fetch_recent_emails(email_addr, app_pass, limit=10)
                for s in subs[:10]:
                    st.write("• ", s)
            except Exception as e:
                st.error(str(e))

    # Thanks
    if st.button("🙌 Thanks", use_container_width=True):
        st.success("We’re glad you’re here! Pairent will keep your schedule tidy.")

st.caption("© 2025 Pairent — Instant-response beta")
