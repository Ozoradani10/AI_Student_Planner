# ai_parser.py
from openai import OpenAI

SYSTEM = """You extract actionable student events from raw emails/announcements.
Return JSON with key 'events' = list of objects:
{ "type": "exam|deadline|class|meeting|notice",
  "title": "string",
  "when": "ISO or human time (accept natural if ambiguous)",
  "location": "string or ''",
  "notes": "short notes" }
If an item has only a deadline, still use 'when' for its due time.
Be conservative: only output events you are confident about."""

def parse_updates_to_events(api_key, texts):
    """
    texts: list[str] (email bodies/subjects/portal texts)
    Returns: list[dict] as events (see SYSTEM).
    """
    client = OpenAI(api_key=api_key)
    joined = "\n\n---\n\n".join(texts)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role":"system", "content": SYSTEM},
            {"role":"user", "content": f"Extract events from these updates:\n{joined}"}
        ],
        response_format={"type": "json_object"}
    )
    import json
    try:
        data = json.loads(resp.choices[0].message.content)
        return data.get("events", [])
    except Exception:
        return []
