# portal_scraper.py
import requests
from ics import Calendar

def fetch_portal_texts(ics_url=None):
    """
    If the university offers an .ics feed, use it.
    Returns list of human-readable strings for the AI to digest.
    """
    items = []
    if ics_url:
        try:
            r = requests.get(ics_url, timeout=20)
            r.raise_for_status()
            cal = Calendar(r.text)
            for e in cal.events:
                when = e.begin.to('UTC').format('YYYY-MM-DD HH:mm') if e.begin else ""
                line = f"{e.name or 'Event'} on {when} {('- ' + e.location) if e.location else ''}. {e.description or ''}"
                items.append(line.strip())
        except Exception:
            pass
    return items
