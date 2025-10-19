import os
os.environ["WATCHFILES_FORCE_POLLING"] = "true"
# app.py  —  AI Student Planner (Premium UI + HTML Email + ICS)
# Requires Streamlit Secrets:
#   OPENAI_API_KEY = "sk-..."
#   SMTP_EMAIL = "your@gmail.com"
#   SMTP_APP_PASSWORD = "16-char Google App Password"
#   SMTP_NAME = "Païrent Planner"        # optional display name
#
# Requirements (requirements.txt):
#   streamlit>=1.33
#   dateparser
#   pytz
#   openai>=1.0.0
#   python-dotenv

import os
import re
import ssl
import json
import smtplib
from pathlib import Path
from datetime import datetime, timedelta, date
from typing import Optional

import streamlit as st
import dateparser
from openai import OpenAI
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


# ---------- Config ----------
st.set_page_config(
    page_title="Païrent — AI Student Planner",
    page_icon="📘",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ---------- Premium CSS ----------
st.markdown("""
<style>
/* background */
.stApp {
  background: radial-gradient(1200px 600px at 20% 0%, rgba(64,132,255,0.12), transparent),
              radial-gradient(1200px 600px at 80% 0%, rgba(0,212,255,0.10), transparent),
              linear-gradient(180deg, #0b1220 0%, #0f1424 60%, #0b1220 100%);
  color: #e9eefb;
}

/* gradient page header */
.px-hero {
  background: linear-gradient(135deg, #3B82F6 0%, #22D3EE 100%);
  border-radius: 20px;
  padding: 22px 24px;
  color: white;
  box-shadow: 0 8px 30px rgba(59,130,246,.35);
  border: 1px solid rgba(255,255,255,.15);
}

/* glass panels */
.px-card {
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.12);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-radius: 18px;
  padding: 18px 18px;
  box-shadow: 0 10px 28px rgba(0,0,0,.25);
}

/* nicer inputs */
.stTextInput > div > div > input,
.stNumberInput input,
.stSelectbox div[data-baseweb="select"] input {
  border-radius: 12px !important;
}

/* success banner */
.px-ok {
  background: rgba(34,197,94,.15);
  border: 1px solid rgba(34,197,94,.35);
  color: #c8f7d1;
  border-radius: 12px;
  padding: 10px 12px;
}

/* markdown content */
.block-container h2, .block-container h3 {
  color: #eaf1ff;
}
.block-container code, .block-container pre {
  background: rgba(255,255,255,0.06) !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    "<div class='px-hero'><h2 style='margin:0'>📘 Païrent — AI Student Planner</h2>"
    "<p style='margin:6px 0 0 0;opacity:.95'>Generate sharp, structured daily/weekly/monthly study plans, "
    "and deliver them via beautiful HTML email with a calendar attachment.</p></div>",
    unsafe_allow_html=True,
)

# ---------- Keys / Clients ----------
def get_secret(name: str, default: Optional[str] = None) -> Optional[str]:
    # Works on Streamlit Cloud & locally
    try:
        return st.secrets[name] if name in st.secrets else os.getenv(name, default)
    except Exception:
        return os.getenv(name, default)

OPENAI_API_KEY = get_secret("OPENAI_API_KEY")
SMTP_EMAIL = get_secret("SMTP_EMAIL")
SMTP_APP_PASSWORD = get_secret("SMTP_APP_PASSWORD")
SMTP_NAME = get_secret("SMTP_NAME", "Païrent Planner")

if not OPENAI_API_KEY:
    st.error("OPENAI_API_KEY is missing in Secrets. Add it and reboot the app.")
    st.stop()

import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------- LLM ----------
SYS_PROMPT = (
    "You are Païrent, a senior academic planner. Create crisp, actionable schedules with time blocks, "
    "task names, and short reasons. Keep tone friendly, modern, and professional. Use Markdown headings and lists.\n"
    "If plan type = Weekly: structure by days (Mon–Sun). If Daily: use time ranges with breaks. If Monthly: "
    "group by weeks with highlights. Keep each block 45–120 minutes unless otherwise specified."
)

def generate_smart_plan(
    plan_type: str,
    study_hours_per_day: float,
    start_hour: int,
    end_hour: int,
    notes: str
) -> str:
    user_prompt = (
        f"Plan type: {plan_type}\n"
        f"Study hours per day: {study_hours_per_day}\n"
        f"Day range: {start_hour}:00–{end_hour}:00\n"
        f"Extra notes or tasks: {notes or '(none)'}\n\n"
        "Return a Markdown plan. Start with a short 1-line summary."
    )

    res = client.responses.create(
        model="gpt-4o-mini",
        input=[{"role": "system", "content": SYS_PROMPT},
               {"role": "user", "content": user_prompt}],
        temperature=0.4,
    )
    # OpenAI Responses API text:
    text = res.output_text or ""
    return text.strip()


# ---------- Email (HTML) ----------
EMAIL_TEMPLATE = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Your AI Study Plan</title>
  <style>
    body {{
      margin:0; padding:0; background:#0b1220; color:#e9eefb; font-family: Inter, Arial, sans-serif;
    }}
    .wrap {{
      max-width: 700px; margin: 24px auto; padding: 0 16px;
    }}
    .hero {{
      background: linear-gradient(135deg, #3B82F6 0%, #22D3EE 100%);
      border-radius: 16px; padding: 22px 24px; color: #fff;
      box-shadow: 0 8px 28px rgba(59,130,246,.35);
    }}
    .card {{
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 16px; padding: 18px 18px; margin-top: 16px;
    }}
    h1,h2,h3 {{ margin: 0 0 8px 0; }}
    p {{ line-height: 1.55; }}
    .btn {{
      display:inline-block; padding:10px 16px; border-radius:12px; color:#0b1220; font-weight:600;
      background:#a8ffec; text-decoration:none; margin-top:12px;
    }}
    pre {{
      white-space: pre-wrap; word-wrap: break-word; background: rgba(0,0,0,.25);
      padding:12px; border-radius:12px; color:#f6faff;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <h2>📘 Your Païrent Study Plan</h2>
      <p>Here’s your AI-generated plan. We’ve attached a calendar file (.ics) too.</p>
    </div>
    <div class="card">
      <h3>Plan</h3>
      <pre>{plan_markdown}</pre>
      <a class="btn" href="{app_url}" target="_blank">Open Païrent</a>
    </div>
    <p style="opacity:.7;margin-top:16px">Sent automatically by Païrent • {today}</p>
  </div>
</body>
</html>
"""

def build_ics(plan_title: str, plan_text: str, start: date, days: int = 7) -> bytes:
    """
    Minimal ICS: one multi-day all-day event with the plan in DESCRIPTION.
    This avoids extra dependencies and still imports into Calendar apps.
    """
    dtstamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dtstart = start.strftime("%Y%m%d")
    dtend = (start + timedelta(days=days)).strftime("%Y%m%d")  # exclusive
    # Clean description (escape commas/semicolons)
    desc = plan_text.replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")
    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Païrent Planner//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{dtstamp}-parent@planner
DTSTAMP:{dtstamp}
DTSTART;VALUE=DATE:{dtstart}
DTEND;VALUE=DATE:{dtend}
SUMMARY:{plan_title}
DESCRIPTION:{desc}
END:VEVENT
END:VCALENDAR
"""
    return ics.encode("utf-8")

def send_email_html(
    to_email: str,
    subject: str,
    html_body: str,
    ics_bytes: Optional[bytes] = None,
    ics_name: str = "study-plan.ics"
) -> None:
    if not (SMTP_EMAIL and SMTP_APP_PASSWORD):
        raise RuntimeError("SMTP settings missing. Add SMTP_EMAIL and SMTP_APP_PASSWORD in Secrets.")

    msg = MIMEMultipart("mixed")
    msg["From"] = f"{SMTP_NAME} <{SMTP_EMAIL}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText("Your device does not support HTML emails. See attached plan.", "plain"))
    alt.attach(MIMEText(html_body, "html"))
    msg.attach(alt)

    if ics_bytes:
        part = MIMEBase("text", "calendar", method="REQUEST", name=ics_name)
        part.set_payload(ics_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f'attachment; filename="{ics_name}"')
        msg.attach(part)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(SMTP_EMAIL, SMTP_APP_PASSWORD)
        server.sendmail(SMTP_EMAIL, [to_email], msg.as_string())


# ---------- UI ----------
st.markdown("<div class='px-card'>", unsafe_allow_html=True)

colA, colB = st.columns([1,1])
with colA:
    plan_type = st.selectbox("Plan type", ["Daily", "Weekly", "Monthly"], index=1)
    study_hours = st.number_input("Max study hours / day", 1.0, 12.0, 6.0, step=0.5)
    start_hour = st.number_input("Start hour", 5, 12, 9)
with colB:
    end_hour = st.number_input("End hour", 13, 24, 21)
    notes = st.text_input("Extra notes (subjects, deadlines, exams, preferences)", "")
    email_to = st.text_input("Send to email (optional)", placeholder="name@example.com")

col1, col2 = st.columns([1,1])
with col1:
    auto_email = st.checkbox("Email me the plan", value=bool(email_to))
with col2:
    start_date_str = st.text_input("Start date (YYYY-MM-DD, optional)", "")

st.markdown("</div>", unsafe_allow_html=True)

btn = st.button("✨ Generate Smart Plan", use_container_width=True)

if btn:
    with st.spinner("Thinking with Païrent…"):
        plan = generate_smart_plan(plan_type, study_hours, start_hour, end_hour, notes)

    st.markdown("<div class='px-card'>", unsafe_allow_html=True)
    st.success("Plan generated ✓")
    st.markdown("### 📘 Your Smart Study Plan")
    st.markdown(plan)
    st.markdown("</div>", unsafe_allow_html=True)

    # Prepare email if requested
    if auto_email and email_to:
        # Determine ICS window
        if plan_type.lower().startswith("day"):
            days_span = 1
        elif plan_type.lower().startswith("month"):
            days_span = 28
        else:
            days_span = 7

        # Start date
        if start_date_str:
            d = dateparser.parse(start_date_str)
            start_date = d.date() if d else date.today()
        else:
            start_date = date.today()

        # Build pretty HTML
        app_url = st.secrets.get("APP_URL", os.getenv("APP_URL", "https://share.streamlit.io"))
        html = EMAIL_TEMPLATE.format(
            plan_markdown=plan,
            app_url=app_url,
            today=datetime.now().strftime("%b %d, %Y"),
        )

        # .ics attachment
        title = f"Païrent {plan_type} Study Plan"
        ics = build_ics(title, plan, start=start_date, days=days_span)

        try:
            send_email_html(
                to_email=email_to.strip(),
                subject=title,
                html_body=html,
                ics_bytes=ics,
                ics_name=f"parent-{plan_type.lower()}-plan.ics"
            )
            st.markdown("<div class='px-ok'>📧 Sent to your inbox!</div>", unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Email failed: {e}")

# Footer
st.markdown("<br><div style='opacity:.6;text-align:center'>© Païrent — built for students</div>", unsafe_allow_html=True)
