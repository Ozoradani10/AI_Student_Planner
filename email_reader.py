# email_reader.py
import imaplib, email, datetime
from email.header import decode_header, make_header

def _decode_hdr(x):
    try:
        return str(make_header(decode_header(x or "")))
    except Exception:
        return x or ""

def fetch_recent_emails(host, user, pwd, since_hours=48, from_filters=None, max_items=50):
    """Return a list of dicts: {subject, body, date} from IMAP (Gmail works with App Password)."""
    msgs = []
    since_date = (datetime.datetime.utcnow() - datetime.timedelta(hours=since_hours)).strftime("%d-%b-%Y")
    M = imaplib.IMAP4_SSL(host)
    M.login(user, pwd)
    M.select("INBOX")
    typ, data = M.search(None, '(SINCE "{}")'.format(since_date))
    if typ != "OK":
        M.logout()
        return msgs

    ids = data[0].split()
    ids = ids[-max_items:]  # last N
    for i in reversed(ids):
        typ, msg_data = M.fetch(i, "(RFC822)")
        if typ != "OK": 
            continue
        msg = email.message_from_bytes(msg_data[0][1])

        subj = _decode_hdr(msg.get("Subject"))
        frm  = _decode_hdr(msg.get("From"))
        date = msg.get("Date")

        if from_filters:
            f = (frm or "").lower()
            if not any(src.lower() in f for src in from_filters):
                # allow professor domains like .edu or the university domain
                pass

        # extract plain text body
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disp  = part.get("Content-Disposition", "")
                if ctype == "text/plain" and "attachment" not in (disp or "").lower():
                    try:
                        body += part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                    except Exception:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", errors="ignore")
            except Exception:
                pass

        msgs.append({"subject": subj, "from": frm, "date": date, "body": body})
    M.close()
    M.logout()
    return msgs
