# email_reader.py
import imaplib, email
from typing import List, Tuple

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993

def _body_from_message(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get('Content-Disposition'))
            if ctype == 'text/plain' and 'attachment' not in disp:
                try:
                    return part.get_payload(decode=True).decode(errors="ignore")
                except Exception:
                    continue
    try:
        return msg.get_payload(decode=True).decode(errors="ignore")
    except Exception:
        return ""

def fetch_recent_emails(email_addr: str, app_password: str, limit: int = 25) -> Tuple[List[str], List[str]]:
    subjects, bodies = [], []
    M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    M.login(email_addr, app_password)   # 16-char Google App Password (no spaces)
    M.select("INBOX")
    typ, data = M.search(None, 'ALL')
    if typ != "OK": 
        return subjects, bodies
    ids = data[0].split()[-limit:]
    for i in ids[::-1]:
        typ, msg_data = M.fetch(i, '(RFC822)')
        if typ != "OK": continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)
        subjects.append(msg.get("Subject", ""))
        bodies.append(_body_from_message(msg))
    M.close(); M.logout()
    return subjects, bodies
