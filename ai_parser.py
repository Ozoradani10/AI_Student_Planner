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

def parse_updates_to_events(text):
    # Prevent empty or invalid input
    if not text or str(text).strip() == "":
        return "No new updates found."

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": f"Extract exams, deadlines, and class events from this text:\n{text}"
                }
            ],
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        return f"AI parsing failed: {str(e)}"
