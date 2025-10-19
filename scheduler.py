# scheduler.py
import json, os, pytz, dateparser, datetime
from pathlib import Path

DATA = Path("data"); DATA.mkdir(exist_ok=True)
DB   = DATA / "tasks.json"

def load_events():
    if DB.exists():
        with DB.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {"events": []}

def save_events(events):
    with DB.open("w", encoding="utf-8") as f:
        json.dump({"events": events}, f, ensure_ascii=False, indent=2)

def merge_events(existing, new_items):
    # Deduplicate by (title, when)
    key = set((e.get("title","").strip(), e.get("when","").strip()) for e in existing)
    for n in new_items:
        t = n.get("title","").strip(); w = n.get("when","").strip()
        if (t, w) not in key and t and w:
            existing.append(n); key.add((t, w))
    return existing

def upcoming(events, hours=72, tz="UTC"):
    now = datetime.datetime.now(pytz.timezone(tz))
    out=[]
    for e in events:
        w = e.get("when","")
        dt = dateparser.parse(w, settings={"TIMEZONE": tz, "RETURN_AS_TIMEZONE_AWARE": True})
        if not dt: 
            continue
        if now <= dt <= now + datetime.timedelta(hours=hours):
            out.append((dt, e))
    return [e for _,e in sorted(out, key=lambda x: x[0])]
