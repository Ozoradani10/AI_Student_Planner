# Pairent — Autonomous AI Student Planner (Final Master Version)
# Single-file app: login -> background IMAP fetch -> AI parse -> schedule -> reminders
# Works on desktop & mobile (Streamlit). No buttons required after sign-in.

import os, re, ssl, json, time, threading, imaplib, smtplib
from email import policy
from email.parser import BytesParser
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st
from openai import OpenAI

# ---------- CONFIG ----------
APP_NAME = "Pairent — AI Student Planner"
TZ_DEFAULT = "Europe/Istanbul"           # Turkey default
SYNC_EVERY_MINUTES = 15                  # background interval
MORNING_SUMMARY_HOUR = 8                 # local time
REMINDER_LEAD_MIN = 60                   # email & in-app reminder before event

DATA_FILE = "events.json"                # persisted per app instance (not per user)

MODEL = "gpt-4o-mini"

HERO_TITLE = "📘 Pairent — AI Student Planner"
HERO_SUB = ("Automatically collects updates from your email & portals, "
            "understands them with AI, builds your schedule, and reminds you — no typing.")

SYSTEM = """
You extract actionable student events from raw emails/announcements.
Return JSON with key "events": list of objects, each:
{ "type": "exam|deadline|class|meeting|notice",
  "title": "short title",
  "when": "ISO 8601 datetime or clear natural time (accept local human phrases)",
  "location": "string or ''",
  "notes": "short notes" }
Only output events you are confident about. If only a due date, still use "when" for its due time.
Combine subject + body if both are provided.
"""

# ---------- helpers: storage ----------
def load_events() -> list[dict]:
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_events(events: list[dict]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

def dedupe_events(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for e in items:
        key = (e.get("title","").strip().lower(), e.get("when","").strip())
        if key in seen: 
            continue
        seen.add(key)
        out.append(e)
    return out

# ---------- helpers: email servers autodetect ----------
def detect_servers(email_addr: str):
    dom = email_addr.split("@")[-1].lower()
    imap_host = smtp_host = None
    if dom in ("gmail.com","googlemail.com"):
        imap_host, smtp_host = "imap.gmail.com", "smtp.gmail.com"
    elif dom in ("outlook.com","hotmail.com","live.com","office365.com","outlook.office365.com","outlook.sa"):
        imap_host, smtp_host = "outlook.office365.com", "smtp.office365.com"
    elif dom in ("yahoo.com","yahoo.co.uk","ymail.com"):
        imap_host, smtp_host = "imap.mail.yahoo.com", "smtp.mail.yahoo.com"
    elif dom in ("icloud.com","me.com","mac.com"):
        imap_host, smtp_host = "imap.mail.me.com", "smtp.mail.me.com"
    elif dom in ("yandex.com","yandex.ru","ya.ru"):
        imap_host, smtp_host = "imap.yandex.com", "smtp.yandex.com"
    else:
        # best effort fallback
        imap_host, smtp_host = f"imap.{dom}", f"smtp.{dom}"
    return imap_host, smtp_host, 993, 587

# ---------- IMAP fetch ----------
def fetch_recent_emails(email_addr: str, app_password: str, limit: int = 30) -> tuple[list[str], list[str]]:
    imap_host, _, imap_port, _ = detect_servers(email_addr)
    subjects, bodies = [], []
    try:
        mail = imaplib.IMAP4_SSL(imap_host, imap_port)
        # Many providers require app passwords / OAuth. This will raise if invalid.
        mail.login(email_addr, app_password)
        mail.select("INBOX")
        # last ~500 ids (cheap)
        typ, data = mail.search(None, "ALL")
        if typ != "OK":
            return [], []
        ids = data[0].split()
        for msg_id in ids[-500:][::-1]:  # newest first
            if len(subjects) >= limit:
                break
            typ, raw = mail.fetch(msg_id, "(RFC822)")
            if typ != "OK":
                continue
            msg = BytesParser(policy=policy.default).parsebytes(raw[0][1])
            subj = str(msg["subject"] or "").strip()
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    if ctype == "text/plain":
                        body += part.get_content() or ""
            else:
                body = msg.get_content() or ""
            text = (subj + "\n\n" + body).strip()
            # Keep only likely academic updates (very lightweight filter)
            if re.search(r"\b(exam|midterm|final|quiz|deadline|class|lecture|schedule|timetable|assignment|homework|lab|course|meeting)\b", text, re.I):
                subjects.append(subj)
                bodies.append(body.strip())
        mail.logout()
    except imaplib.IMAP4.error:
        # auth/IMAP error
        raise
    except Exception:
        # ignore network glitches
        pass
    return subjects, bodies

# ---------- SMTP email ----------
def send_email(email_addr: str, app_password: str, to_addr: str, subject: str, html_body: str):
    _, smtp_host, _, smtp_port = detect_servers(email_addr)
    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = email_addr
    msg["To"] = to_addr
    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls(context=ssl.create_default_context())
        s.login(email_addr, app_password)
        s.sendmail(email_addr, [to_addr], msg.as_string())

# ---------- AI parsing ----------
def parse_updates_to_events(api_key: str, texts: list[str]) -> list[dict]:
    if not texts:
        return []
    client = OpenAI(api_key=api_key)
    joined = "\n\n---\n\n".join(texts)[:15000]  # keep prompt small
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0.2,
            messages=[
                {"role":"system","content":SYSTEM},
                {"role":"user","content":f"Extract events from these updates:\n{joined}"}
            ],
            response_format={"type":"json_object"}
        )
        import json as _json
        data = _json.loads(resp.choices[0].message.content)
        return data.get("events", [])
    except Exception:
        return []

# ---------- background worker ----------
def background_loop():
    tz = ZoneInfo(st.session_state.get("tz", TZ_DEFAULT))
    while st.session_state.get("auth_ok", False):
        try:
            # 1) Fetch emails
            subj, bodies = fetch_recent_emails(
                st.session_state["email"],
                st.session_state["password"],
                limit=40
            )
            texts = []
            # Keep very recent bodies first
            for s, b in list(zip(subj, bodies))[:40]:
                texts.append((s or "").strip())
                texts.append((b or "").strip())
            # 2) AI -> events
            new_events = parse_updates_to_events(st.secrets["OPENAI_API_KEY"], texts)
            # Normalize times -> ISO
            norm = []
            now = datetime.now(tz)
            for e in new_events:
                when = str(e.get("when","")).strip()
                if not when:
                    continue
                # accept already-ISO or natural phrases like "Tue 10:00"
                try:
                    dt = None
                    if re.match(r"\d{4}-\d{2}-\d{2}T", when):
                        from dateutil.parser import isoparse
                        dt = isoparse(when)
                    else:
                        # very light natural parse (today/tomorrow/HH:MM)
                        m = re.match(r"(today|tomorrow)?\s*(\d{1,2}:\d{2})?", when, re.I)
                        if m:
                            base = now if (m.group(1) or "").lower() == "today" else (now + timedelta(days=1))
                            hhmm = m.group(2) or "09:00"
                            h, M = map(int, hhmm.split(":"))
                            dt = base.replace(hour=h, minute=M, second=0, microsecond=0)
                    if not dt:
                        # last resort: ignore item
                        continue
                    e["when"] = dt.astimezone(tz).isoformat()
                    norm.append(e)
                except Exception:
                    continue
            # 3) Merge store
            all_events = dedupe_events(load_events() + norm)
            save_events(all_events)

            # 4) Reminders (in-app + email)
            upcoming_window = datetime.now(tz) + timedelta(minutes=REMINDER_LEAD_MIN + 1)
            reminders = []
            for e in all_events:
                try:
                    from dateutil.parser import isoparse
                    dt = isoparse(e["when"]).astimezone(tz)
                except Exception:
                    continue
                mins_left = int((dt - datetime.now(tz)).total_seconds() // 60)
                if 0 < mins_left <= REMINDER_LEAD_MIN:
                    label = f"⏰ {e.get('title','(no title)')} at {dt.strftime('%a %d %b %H:%M')}"
                    # Avoid duplicate reminder spam in same loop
                    key = dt.isoformat() + "|" + e.get("title","")
                    if key not in st.session_state.get("sent_keys", set()):
                        st.session_state.setdefault("sent_keys", set()).add(key)
                        reminders.append(label)
                        # Email reminder
                        try:
                            send_email(
                                st.session_state["email"],
                                st.session_state["password"],
                                st.session_state["email"],
                                f"Reminder · {e.get('title','')}",
                                f"<p>{label}</p><p>Location: {e.get('location','-')}</p>"
                            )
                        except Exception:
                            pass
            # queue toasts for FE
            if reminders:
                st.session_state.setdefault("toasts", []).extend(reminders)

            # 5) Morning summary at MORNING_SUMMARY_HOUR
            now_local = datetime.now(tz)
            if now_local.hour == MORNING_SUMMARY_HOUR and now_local.minute < 5:
                todays = []
                for e in all_events:
                    try:
                        from dateutil.parser import isoparse
                        dt = isoparse(e["when"]).astimezone(tz)
                        if dt.date() == now_local.date():
                            todays.append(f"• {e.get('title','(no title)')} — {dt.strftime('%H:%M')}")
                    except Exception:
                        continue
                if todays:
                    html = "<h3>Today</h3>" + "<br>".join(todays)
                    try:
                        send_email(
                            st.session_state["email"],
                            st.session_state["password"],
                            st.session_state["email"],
                            "Pairent · Today’s plan",
                            html
                        )
                    except Exception:
                        pass
        except imaplib.IMAP4.error:
            # auth error: pause; UI will show banner
            st.session_state["auth_ok"] = False
        except Exception:
            # swallow other transient errors
            pass
        # sleep until next cycle or until logout
        for _ in range(SYNC_EVERY_MINUTES * 6):
            if not st.session_state.get("auth_ok", False):
                return
            time.sleep(10)

# ---------- UI ----------
st.set_page_config(page_title=APP_NAME, page_icon="📘", layout="wide")
tz_name = st.session_state.get("tz", TZ_DEFAULT)
tz = ZoneInfo(tz_name)

# Sidebar login
with st.sidebar:
    st.markdown("## 🔐 Student Login")
    email_in = st.text_input("University / Personal Email", value=st.session_state.get("email",""))
    pwd_in = st.text_input("Email password (or Gmail app password)", type="password", value=st.session_state.get("password",""))
    tz_opts = ["Europe/Istanbul","Europe/Berlin","Europe/London","Asia/Almaty","Asia/Tashkent","UTC"]
    tz_name = st.selectbox("Timezone", tz_opts, index=tz_opts.index(tz_name) if tz_name in tz_opts else 0)
    st.session_state["tz"] = tz_name

    colA, colB = st.columns(2)
    with colA:
        if st.button("Sign in"):
            st.session_state["email"] = email_in.strip()
            st.session_state["password"] = pwd_in
            if st.session_state["email"] and st.session_state["password"]:
                st.session_state["auth_ok"] = True
                # start background thread (only once)
                if not st.session_state.get("bg_started"):
                    t = threading.Thread(target=background_loop, daemon=True)
                    t.start()
                    st.session_state["bg_started"] = True
            else:
                st.session_state["auth_ok"] = False
    with colB:
        if st.button("Sign out"):
            st.session_state["auth_ok"] = False
            st.session_state["email"] = ""
            st.session_state["password"] = ""

# Hero
st.markdown(f"### {HERO_TITLE}")
st.caption(HERO_SUB)

# In-app toasts queued by background worker
for _ in range(len(st.session_state.get("toasts", []))):
    msg = st.session_state["toasts"].pop(0)
    try:
        st.toast(msg)
    except Exception:
        st.info(msg)

# Auth status banner
if not st.session_state.get("auth_ok", False):
    st.warning("Please sign in with your email + password (Gmail users: app password recommended). "
               "Pairent will then begin syncing automatically.")
else:
    st.success("Signed in. Pairent is syncing in the background. You’ll receive reminders here and by email.")

# Schedule view
st.subheader("📅 Your schedule")
events = load_events()
if not events:
    st.info("No events detected yet. As soon as related emails arrive, Pairent will parse them and populate your schedule here automatically.")
else:
    # sort by date/time
    try:
        from dateutil.parser import isoparse
        events_sorted = sorted(events, key=lambda e: isoparse(e.get("when","2100-01-01T00:00:00")))
    except Exception:
        events_sorted = events

    # group by date
    by_date = {}
    for e in events_sorted:
        try:
            from dateutil.parser import isoparse
            d = isoparse(e["when"]).astimezone(ZoneInfo(tz_name)).date().isoformat()
        except Exception:
            d = "Unknown"
        by_date.setdefault(d, []).append(e)

    for d, items in by_date.items():
        st.markdown(f"#### {datetime.fromisoformat(d+'T00:00:00').strftime('%a %d %b %Y')}")
        for e in items:
            try:
                from dateutil.parser import isoparse
                dt = isoparse(e["when"]).astimezone(ZoneInfo(tz_name))
                label_time = dt.strftime("%H:%M")
            except Exception:
                label_time = "—"
            st.markdown(
                f"""
<div style="padding:10px;border:1px solid #2a2a2a;border-radius:10px;margin:6px 0;background:#111;">
  <b>{e.get('title','(no title)')}</b> <span style="opacity:.7">({e.get('type','event')})</span><br>
  🕒 {label_time} &nbsp;&nbsp; 📍 {e.get('location','—')}<br>
  <span style="opacity:.8">{e.get('notes','')}</span>
</div>
""",
                unsafe_allow_html=True
            )

st.caption("© 2025 Pairent – Autonomous Student Planner")
