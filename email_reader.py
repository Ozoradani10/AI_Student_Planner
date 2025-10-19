# email_reader.py — fetch recent emails (AI-driven auto-detector for exam/class updates)
import imaplib, email, os
from email.header import decode_header
from datetime import datetime, timedelta

def fetch_recent_emails(limit: int = 25) -> tuple[list[str], list[str]]:
    """
    Connect to Gmail IMAP using credentials from Streamlit Secrets or sidebar inputs.
    Returns subjects[] and bodies[] for analysis.
    """
    IMAP_HOST = "imap.gmail.com"
    IMAP_USER = os.getenv("IMAP_USER", "")
    IMAP_PASS = os.getenv("IMAP_PASS", "")

    subjects, bodies = [], []

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(IMAP_USER, IMAP_PASS)
        mail.select("inbox")

        # Get last 25 messages
        result, data = mail.search(None, "ALL")
        ids = data[0].split()[-limit:]
        for i in reversed(ids):
            res, msg_data = mail.fetch(i, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subj, enc = decode_header(msg["Subject"])[0]
                    subj = subj.decode(enc) if isinstance(subj, bytes) else subj
                    subjects.append(subj)

                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body += part.get_payload(decode=True).decode(errors="ignore")
                    else:
                        body = msg.get_payload(decode=True).decode(errors="ignore")
                    bodies.append(body)

        mail.logout()
    except Exception as e:
        print("Email fetch error:", e)

    return subjects, bodies
