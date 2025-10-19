# email_reader.py — read latest university emails via IMAP
import imaplib
import email
from email.header import decode_header
from typing import List, Tuple, Optional
import os
import re

def _decode(s, enc):
    try:
        return s.decode(enc or "utf-8", errors="ignore") if isinstance(s, bytes) else str(s)
    except Exception:
        return s if isinstance(s, str) else str(s or "")

def _extract_text(msg: email.message.Message) -> str:
    # Prefer text/plain; fall back to text/html -> strip tags crudely
    text_parts = []
    for part in msg.walk():
        ctype = part.get_content_type()
        disp = str(part.get("Content-Disposition") or "").lower()
        if part.is_multipart():
            continue
        if "attachment" in disp:
            continue
        try:
            payload = part.get_payload(decode=True) or b""
        except Exception:
            payload = b""
        txt = _decode(payload, part.get_content_charset())
        if ctype == "text/html":
            # very light HTML strip so the parser gets clean text
            txt = re.sub(r"<(script|style)[\s\S]*?</\1>", "", txt, flags=re.I)
            txt = re.sub(r"<br\s*/?>", "\n", txt, flags=re.I)
            txt = re.sub(r"<[^>]+>", " ", txt)
        text_parts.append(txt)
    return "\n".join(text_parts).strip()

def _decode_subject(raw_subj) -> str:
    if not raw_subj:
        return ""
    try:
        parts = decode_header(raw_subj)
        out = []
        for val, enc in parts:
            out.append(_decode(val, enc))
        return "".join(out).strip()
    except Exception:
        return str(raw_subj)

def fetch_recent_emails(
    email: Optional[str] = None,
    app_password: Optional[str] = None,
    imap_host: Optional[str] = None,
    limit: int = 25,
) -> Tuple[List[str], List[str]]:
    """
    Returns (subjects[], bodies[]) of the most recent messages.
    If email/app_password not provided, falls back to Streamlit secrets / env:
      IMAP_USER, IMAP_PASS, IMAP_HOST
    """
    user = email or os.getenv("IMAP_USER")
    pwd = app_password or os.getenv("IMAP_PASS")
    host = (imap_host or os.getenv("IMAP_HOST") or "imap.gmail.com").strip()

    if not user or not pwd:
        # Nothing to read
        return [], []

    try:
        M = imaplib.IMAP4_SSL(host)
        M.login(user, pwd)
        M.select("INBOX")
        # Recent first
        typ, data = M.search(None, "ALL")
        if typ != "OK" or not data or not data[0]:
            M.logout()
            return [], []

        ids = data[0].split()
        ids = ids[-limit:]  # take last N
        subjects, bodies = [], []

        for i in reversed(ids):  # newest to oldest
            typ, msg_data = M.fetch(i, "(RFC822)")
            if typ != "OK" or not msg_data:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            subj = _decode_subject(msg.get("Subject"))
            body = _extract_text(msg)

            # Keep only potentially relevant updates (still pass everything to AI later)
            # Light filter so we don’t flood:
            if subj or body:
                subjects.append(subj)
                bodies.append(body)

        M.logout()
        return subjects, bodies

    except imaplib.IMAP4.error:
        # authentication or mailbox error
        return [], []
    except Exception:
        # Any other network/parse error -> return empty so UI shows a gentle warning
        return [], [] 
