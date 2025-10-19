# portal_scraper.py — auto-detect & parse university portals (OBS, LMS, Moodle, ABS, Teams)
import os, re, requests
from bs4 import BeautifulSoup
from datetime import datetime

# --- Detect known university systems automatically ---
KNOWN_PORTALS = [
    "obs.", "lms.", "moodle.", "teams.", "edu.tr", "abs.", "sis.", "campus."
]

def detect_portal_links(email_bodies: list[str]) -> list[str]:
    """Find possible portal URLs inside emails."""
    urls = []
    for body in email_bodies:
        found = re.findall(r"https?://[^\s>]+", body)
        for url in found:
            if any(tag in url.lower() for tag in KNOWN_PORTALS):
                if url not in urls:
                    urls.append(url)
    return urls

def fetch_portal_texts(email_bodies: list[str]) -> list[str]:
    """
    Automatically fetch portal pages or calendar .ics files mentioned in emails.
    Returns: list of extracted text contents from those portals.
    """
    texts = []
    portal_links = detect_portal_links(email_bodies)

    for url in portal_links:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")

                # Try to find academic words (exam, schedule, class, deadline)
                text = soup.get_text(separator=" ", strip=True)
                if any(word in text.lower() for word in ["exam", "schedule", "class", "deadline", "ders", "sınav", "hafta"]):
                    texts.append(text[:3000])  # limit for safety
        except Exception as e:
            print("Portal scrape failed:", e)

    # fallback: if no portals detected
    if not texts:
        texts.append("No university portal found or accessible.")
    return texts

# --- Demo / test ---
if __name__ == "__main__":
    test_email = [
        "Your LMS link is https://lms.ankara.edu.tr/login and OBS at https://obs.metu.edu.tr"
    ]
    data = fetch_portal_texts(test_email)
    print(f"Fetched {len(data)} portal contents")
    for t in data:
        print(t[:300], "\n---")
