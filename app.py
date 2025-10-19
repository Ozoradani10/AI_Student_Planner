# app.py  — Païrent 2.0 (autonomous assistant)
import os, json, datetime, pytz, dateparser, smtplib
import streamlit as st
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from email_reader import fetch_recent_emails
from portal_scraper import fetch_portal_texts
from ai_parser import parse_updates_to_events
from scheduler import load_events, save_events, merge_events, upcoming

# --- Hardening for Streamlit Cloud file watch limits ---
os.environ["WATCHFILES_FORCE_POLLING"] = "true"

st.set_page_config(page_title="Païrent — AI Student Planner", page_icon="🧠", layout="wide")

# --- Secrets / ENV ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", "")
SMTP_HOST = os.getenv("SMTP_HOST") or st.secrets.get("SMTP_HOST","smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT") or st.secrets.get("SMTP_PORT","587"))
SMTP_USER = os.getenv("SMTP_USER") or st.secrets.get("SMTP_USER","")
SMTP_PASS = os.getenv("SMTP_PASS") or st.secrets.get("SMTP_PASS","")
SMTP_EMAIL= os.getenv("SMTP_EMAIL") or st.secrets.get("SMTP_EMAIL", SMTP_USER)
SMTP_NAME = os.getenv("SMTP_NAME") or st.secrets.get("SMTP_NAME","Païrent")

IMAP_HOST = os.getenv("IMAP_HOST") or st.secrets.get("IMAP_HOST","imap.gmail.com")
IMAP_USER = os.getenv("IMAP_USER") or st.secrets.get("IMAP_USER","")
IMAP_PASS = os.getenv("IMAP_PASS") or st.secrets.get("IMAP_PASS","")

PORTAL_ICS_URL = os.getenv("PORTAL_ICS_URL") or st.secrets.get("PORTAL_ICS_URL","")

# --- Header UI ---
st.markdown("""
<div style="padding:18px;border-radius:16px;background:linear-gradient(135deg,#2b6cb0,#38b2ac);color:#fff;">
  <h1 style="margin:0;">🧠 Païrent — AI Student Planner</h1>
  <p style="margin-top:6px;">Automatically collects updates from your email & portal, understands them, builds your schedule, and emails reminders — no typing.</p>
</div>
""", unsafe_allow_html=True)

with st.expander("Connections", expanded=True):
    st.markdown("*Gmail (IMAP)* and *SMTP* should already be set from Streamlit Secrets (your Gmail + App Password).")
    st.text_input("Optional: University portal calendar .ICS URL", key="portal_ics", value=PORTAL_ICS_URL)

colA, colB, colC = st.columns([1,1,1])
with colA:
    freq = st.selectbox("Auto-check while tab is open", ["Off", "Every 5 min", "Every 15 min", "Every 30 min"])
with colB:
    tz = st.selectbox("Your timezone", ["UTC","Europe/London","Europe/Berlin","America/New_York","Asia/Tashkent","Asia/Almaty","Asia/Dubai"], index=0)
with colC:
    lookahead = st.selectbox("Reminders window", ["Next 24h","Next 48h","Next 72h"], index=2)

# auto refresh
if freq != "Off":
    mins = int(freq.split()[1])
    st.experimental_rerun  # for lint
    st.autorefresh(interval=mins*60*1000, key="auto_tick")

# --- Actions ---
left, right = st.columns([1,1])
with left:
    if st.button("🔄 Sync now (read email + portal + AI)", use_container_width=True):
        if not OPENAI_API_KEY:
            st.error("Missing OPENAI_API_KEY in secrets.")
        elif not IMAP_USER or not IMAP_PASS:
            st.error("IMAP credentials are missing in secrets (IMAP_USER/IMAP_PASS).")
        else:
            with st.spinner("Reading email & portal…"):
                # 1) Gather raw updates
                emails = fetch_recent_emails(IMAP_HOST, IMAP_USER, IMAP_PASS, since_hours=48)
                email_texts = [f"{m['subject']}\n{m['body']}" for m in emails]
                portal_texts = fetch_portal_texts(st.session_state.get("portal_ics","").strip() or None)
                raw = email_texts + portal_texts

                # 2) AI parse -> events
                events = parse_updates_to_events(OPENAI_API_KEY, raw) if raw else []

                # 3) Merge + save
                db = load_events()
                merged = merge_events(db["events"], events)
                save_events(merged)

            st.success(f"Synced. Parsed {len(events)} new item(s).")

with right:
    if st.button("📧 Send morning summary now", use_container_width=True):
        try:
            send_morning_summary(tz)
            st.success("Sent!")
        except Exception as e:
            st.error(f"Email error: {e}")

# --- Helper: email sending ---
def send_html_email(to_email, subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{SMTP_NAME} <{SMTP_EMAIL}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.sendmail(SMTP_EMAIL, to_email, msg.as_string())

def send_morning_summary(tz):
    db = load_events()
    today = datetime.date.today()
    # today’s items
    lines = []
    for e in db["events"]:
        dt = dateparser.parse(e.get("when",""), settings={"TIMEZONE": tz, "RETURN_AS_TIMEZONE_AWARE": True})
        if dt and dt.date() == today:
            lines.append(f"<li><b>{e.get('title','')}</b> — {dt.strftime('%H:%M')} ({e.get('type','')}) {e.get('location','')}</li>")
    if not lines:
        lines.append("<li>No events today 🎉</li>")

    html = f"""
    <div style="font-family:Inter,Arial,sans-serif;background:#0f172a;padding:24px;color:#e2e8f0;">
      <div style="background:linear-gradient(135deg,#2563eb,#06b6d4);padding:18px;border-radius:14px;margin-bottom:16px;">
        <h2 style="margin:0;color:#fff;">Païrent — Your day</h2>
        <p style="margin:6px 0 0;color:#e6f3ff;">Auto summary for {today.isoformat()}</p>
      </div>
      <div style="background:#111827;padding:16px;border-radius:12px;border:1px solid #374151;">
        <ul style="margin:0 0 8px 18px;">{''.join(lines)}</ul>
      </div>
      <p style="font-size:12px;color:#94a3b8;margin-top:12px;">You’re receiving this because Païrent is connected to your student sources.</p>
    </div>
    """
    send_html_email(SMTP_EMAIL, "Païrent – your day", html)

# --- Display schedule ---
st.markdown("### 📅 Your schedule")
db = load_events()
if not db["events"]:
    st.info("No events yet. Click *Sync now* to ingest your email/portal.")
else:
    # Show upcoming list
    window = {"Next 24h":24,"Next 48h":48,"Next 72h":72}[lookahead]
    ups = upcoming(db["events"], hours=window, tz=tz)
    if ups:
        st.success(f"Upcoming in {lookahead}: {len(ups)} item(s)")
        for e in ups:
            dt = dateparser.parse(e.get("when",""), settings={"TIMEZONE": tz, "RETURN_AS_TIMEZONE_AWARE": True})
            st.markdown(
                f"- *{e.get('title','')}*  \n"
                f"  {dt.strftime('%Y-%m-%d %H:%M') if dt else e.get('when','')} — {e.get('type','')}  "
                f"{' @ ' + e.get('location','') if e.get('location') else ''}  \n"
                f"  {e.get('notes','')}"
            )
    else:
        st.info("Nothing urgent in the selected window.")

st.caption("Païrent runs while this tab is open (auto-check). For always-on background checks, deploy the same code on a worker (Render/Railway) or a small VM and run a cron.")
