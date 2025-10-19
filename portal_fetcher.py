# portal_fetcher.py
from __future__ import annotations
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Dict
from ics import Calendar

def fetch_ics_events(ics_url: str, tz: ZoneInfo) -> List[Dict]:
    """Download an ICS and normalize to Païrent's event dicts."""
    try:
        r = requests.get(ics_url, timeout=20)
        r.raise_for_status()
        cal = Calendar(r.text)
    except Exception:
        return []

    events: List[Dict] = []
    for e in cal.events:
        # Start/end handling (can be date or datetime)
        start = e.begin.datetime if hasattr(e.begin, "datetime") else e.begin
        end   = e.end.datetime   if hasattr(e.end, "datetime")   else e.end
        if isinstance(start, datetime) and start.tzinfo is None:
            start = start.replace(tzinfo=tz)
        if isinstance(end, datetime) and end.tzinfo is None:
            end = end.replace(tzinfo=tz)

        events.append({
            "type": "class" if "class" in (e.name or "").lower() else "event",
            "title": (e.name or "Calendar item").strip(),
            "when": start.isoformat() if isinstance(start, datetime) else str(start),
            "location": (e.location or "").strip(),
            "notes": (e.description or "").strip(),
            "source": "portal-ics"
        })
    return events
