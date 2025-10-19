# portal_detector.py
from __future__ import annotations
import re
from typing import Iterable, List

# Common Turkish/intl campus systems that expose ICS
KNOWN_HOST_HINTS = [
    r"moodle\.", r"lms\.", r"obs\.", r"oibs\.", r"sis\.", r"kampus\.", r"kampus\w*\.",
    r"university", r"edu\.tr", r"student\.", r"myschedule", r"calendar", r"ical", r"ics"
]

# Microsoft/Google/Teams calendar export patterns
ICS_PATTERNS = [
    r"https?://[^\s\"'>]+\.ics",
    # Outlook/Office 365 share
    r"https?://outlook\.office\.com/calendar/[^\s\"'>]+",
    r"https?://outlook\.office\.com/owa/calendar/[^\s\"'>]+",
    # Google Calendar public/private links (end with .ics)
    r"https?://calendar\.google\.com/calendar/ical/[^\s\"'>]+\.ics",
    # Teams often surfaces via Outlook ICS link
]

def discover_ics_links_from_emails(email_texts: Iterable[str]) -> List[str]:
    """Scan recent email bodies/subjects for ICS links; return unique list."""
    found = set()
    blob = "\n\n".join(t for t in email_texts if t)

    # 1) direct .ics links
    for pat in ICS_PATTERNS:
        for m in re.finditer(pat, blob, flags=re.IGNORECASE):
            url = m.group(0).strip(").,;\"'")
            found.add(url)

    # 2) generic links that likely point to calendar export pages
    generic_links = re.findall(r"https?://[^\s\"'>]+", blob, flags=re.IGNORECASE)
    for url in generic_links:
        if any(re.search(h, url, re.IGNORECASE) for h in KNOWN_HOST_HINTS):
            # Heuristic: pages that end with ics are already in found;
            # here we keep candidates – portal export pages – students might click.
            if url.lower().endswith(".ics"):
                found.add(url)
            # If it’s not .ics, we skip auto-fetching (no login flows here).
            # It still helps us later to show “detected portal candidates” if you want.

    return sorted(found)
