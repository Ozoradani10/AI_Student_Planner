import os
import json
import io
import ssl
import smtplib
import threading
import time
from email.message import EmailMessage
from datetime import datetime, date, timedelta, time as dtime

import streamlit as st
from openai import OpenAI
from ics import Calendar, Event

# ---------------- CONFIG ----------------
st.set_page_config(page_title="AI Student Planner — Smart Notify", page_icon="🎓", layout="wide")

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USERNAME or "")


# ---------------- HELPERS ----------------
def send_email(to_email, subject, body):
    """Send plain-text email."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context) as s:
        s.login(SMTP_USERNAME, SMTP_PASSWORD)
        s.send_message(msg)


def schedule_email_notification(plan, email):
    """Background scheduler that waits and sends notifications."""
    def run():
        for day in plan.get("days", []):
            for block in day.get("blocks", []):
                try:
                    today = datetime.now().date()
                    now = datetime.now()
                    # assume plan for current week
                    sh, sm = map(int, block["start"].split(":"))
                    start_dt = datetime.combine(today, dtime(sh, sm))
                    notify_time = start_dt - timedelta(minutes=15)
                    wait_seconds = (notify_time - now).total_seconds()
                    if wait_seconds > 0:
                        time.sleep(wait_seconds)
                    subject = f"⏰ Reminder: {block['title']} starts soon!"
                    body = (
                        f"Hi there!\n\nYour session '{block['title']}' "
                        f"starts at {block['start']}.\n\nPriority: {block.get('priority','N/A')}\nNotes: {block.get('notes','')}"
                    )
                    send_email(email, subject, body)
                except Exception:
                    continue

    threading.Thread(target=run, daemon=True).start()


def next_monday(d: date) -> date:
    return d + timedelta(days=(0 - d.weekday()) % 7)


def coerce_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    return json.loads(text[start:end+1])


def plan_to_ics(plan):
    base = next_monday(date.today())
    cal = Calendar()
    for i, day in enumerate(plan.get("days", [])):
        ddate = base + timedelta(days=i)
        for b in day.get("blocks", []):
            sh, sm = map(int, b["start"].split(":"))
            eh, em = map(int, b["end"].split(":"))
            ev = Event()
            ev.name = b["title"]
            ev.begin = datetime.combine(ddate, dtime(sh, sm))
            ev.end = datetime.combine(ddate, dtime(eh, em))
            ev.description = f"{b.get('priority','')} — {b.get('notes','')}"
            cal.events.add(ev)
    buf = io.StringIO(str(cal))
    return buf.getvalue().encode()


def generate_plan(period, maxh, starth, endh):
    sys_prompt = (
        "You are a professional academic scheduler. Output JSON only, structured by days and study blocks, "
        "each with start, end, title, priority, and notes."
    )
    user_prompt = (
        f"Generate a {period.lower()} study plan, {maxh}h/day between {starth}:00–{endh}:00. "
        "Include realistic titles, priorities, and notes."
    )
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_prompt}],
    )
    return coerce_json(r.choices[0].message.content)


def render_plan(plan):
    st.markdown("### 📘 AI-Generated Study Plan")
    for d in plan["days"]:
        st.markdown(f"{d['name']}")
        for b in d["blocks"]:
            st.markdown(f"- ⏰ {b['start']}–{b['end']} — *{b['title']}* ({b.get('priority','')})  \n_{b.get('notes','')}_")
        st.markdown("---")


# ---------------- UI ----------------
st.title("🎯 AI Student Planner — Smart Notify")

period = st.sidebar.selectbox("Plan Period", ["Day", "Week"], index=1)
maxh = st.sidebar.slider("Study Hours / Day", 1, 12, 6)
starth = st.sidebar.slider("Start Hour", 6, 12, 9)
endh = st.sidebar.slider("End Hour", 18, 23, 21)
email = st.sidebar.text_input("📧 Email for notifications")

if st.button("✨ Generate Smart Plan"):
    try:
        plan = generate_plan(period, maxh, starth, endh)
        st.session_state["plan"] = plan
        st.success("✅ Plan created successfully!")
    except Exception as e:
        st.error(f"Error: {e}")

plan = st.session_state.get("plan")
if plan:
    render_plan(plan)

    ics_bytes = plan_to_ics(plan)
    st.download_button("📆 Download .ics Calendar", data=ics_bytes, file_name="study_plan.ics")

    if email:
        schedule_email_notification(plan, email)
        st.info("📨 Email reminders scheduled! You’ll receive notifications before each session.")
