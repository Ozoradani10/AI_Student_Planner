# email_reader.py — Gmail IMAP auto fetcher for Païrent
import os, imaplib, email
from email.header import decode_header

IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.getenv("IMAP_USER")
IMAP_PASS = os.getenv("IMAP_PASS")

def fetch_recent_emails(limit: int = 20):
    """Fetch the most recent emails and return (subjects, bodies)."""
    subjects, bodies = [], []
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(IMAP_USER, IMAP_PASS)
        mail.select("inbox")

        _, data = mail.search(None, "ALL")
        mail_ids = data[0].split()[-limit:]
        for mid in reversed(mail_ids):
            _, msg_data = mail.fetch(mid, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1])

            # Decode subject
            subj, enc = decode_header(msg.get("Subject"))[0]
            if isinstance(subj, bytes):
                subj = subj.decode(enc or "utf-8", errors="ignore")
            subjects.append(subj or "")

            # Extract body
            body_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body_text += part.get_payload(decode=True).decode("utf-8", errors="ignore")
                        break
            else:
                body_text = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

            bodies.append(body_text)
        mail.logout()
    except Exception as e:
        print("Email fetch error:", e)
    return subjects, bodies
