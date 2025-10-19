# ai_parser.py — stronger rule-based + AI fallback
import os, re, json
from datetime import datetime
import dateparser
from typing import List, Dict
from openai import OpenAI

SYSTEM = """You extract actionable student events from raw emails/announcements.
Return JSON with key 'events' -> list of:
{ "type":"exam|deadline|class|meeting|notice",
  "title":"string",
  "when":"ISO 8601 UTC (e.g., 2025-10-22T14:00:00Z)",
  "location":"string or ''",
  "notes":"short notes"}
If only a due date appears, still fill 'when'. Only output events you are confident about."""

DP_SETTINGS = {
    "PREFER_DATES_FROM": "future",
    "TIMEZONE": "UTC",
    "RETURN_AS_TIMEZONE_AWARE": True
}

def _iso(dt) -> str:
    return dt.astimezone().strftime("%Y-%m-%dT%H:%M:%SZ")

def _rule_based(text: str) -> List[Dict]:
    text = re.sub(r'\s+', ' ', text)
    events: List[Dict] = []

    # Patterns that appear in casual mails:
    # 1) “midterm on Tue 10:00 in Room B” / “quiz at 12:40”
    patt1 = re.findall(r'(exam|midterm|quiz|class|lecture|meeting)\s*(?:on|at)?\s*([A-Za-z]{3,9}\s+\d{1,2}(?:,\s*\d{4})?|\d{4}-\d{2}-\d{2}|tomorrow|today)?\s*(?:at)?\s*(\d{1,2}[:.]\d{2})?\s*(?:in|at)?\s*([A-Za-z]\s?\w\s?(?:Room|Hall|Block)?\s?\w*)?', text, flags=re.IGNORECASE)
    for typ, day, time, loc in patt1:
        when_str = " ".join([x for x in [day, time] if x])
        dt = dateparser.parse(when_str, settings=DP_SETTINGS)
        if dt:
            events.append({
                "type": typ.lower() if typ else "notice",
                "title": typ.title() if typ else "Event",
                "when": _iso(dt),
                "location": (loc or "").strip(),
                "notes": when_str
            })

    # 2) “deadline due on Oct 28” / “Project due 2025-11-01 23:59”
    patt2 = re.findall(r'(deadline|due)\s*(?:on|:)?\s*([A-Za-z]{3,9}\s+\d{1,2}(?:,\s*\d{4})?|\d{4}-\d{2}-\d{2}(?:\s*\d{1,2}[:.]\d{2})?)', text, flags=re.IGNORECASE)
    for _, d in patt2:
        dt = dateparser.parse(d, settings=DP_SETTINGS)
        if dt:
            events.append({"type":"deadline","title":"Deadline","when":_iso(dt),"location":"","notes":f"Due: {d}"})

    return events

def extract_events_from_texts(texts: List[str]) -> List[Dict]:
    joined = "\n\n".join(texts)
    rb = _rule_based(joined)

    # AI fallback (enrich + catch tricky phrasing)
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            response_format={"type":"json_object"},
            messages=[
                {"role":"system","content":SYSTEM},
                {"role":"user","content":f"Extract events from the following text:\n{joined[:12000]}"}]
        )
        data = json.loads(resp.choices[0].message.content)
        ai = data.get("events", [])
    except Exception:
        ai = []

    # merge + dedupe
    all_events = rb + ai
    out: List[Dict] = []
    seen = set()
    for e in all_events:
        title = (e.get("title") or "Event").strip()
        when  = e.get("when") or ""
        try:
            dt = dateparser.parse(when, settings=DP_SETTINGS) if "T" not in when else datetime.fromisoformat(when.replace("Z","+00:00"))
        except Exception:
            continue
        when_iso = _iso(dt)
        key = (title, when_iso)
        if key in seen: 
            continue
        seen.add(key)
        e["title"] = title
        e["when"]  = when_iso
        e["location"] = e.get("location","")
        e["notes"] = e.get("notes","")
        out.append(e)
    return out

def generate_study_plan(goal: str, duration: str) -> str:
    prompt = f"Create a crisp, motivational {duration.lower()} study plan for: {goal}. Use headings and short bullet points."
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role":"system","content":"You write sharp, structured study plans."},
                {"role":"user","content":prompt}
            ]
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Could not generate plan: {e}"
