# === AI Student Planner – Streamlit Web App (full file) ===
# Safe to paste over your existing app.py

from pathlib import Path
import os, json, subprocess
import streamlit as st

# --- AI (OpenAI) ---
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()  # reads .env with OPENAI_API_KEY=...
client = OpenAI()  # will use env var; no hardcoded key

# ---- Page config / Theme ----
st.set_page_config(page_title="AI Student Planner", page_icon="🧠", layout="wide")
st.markdown("""
<style>
/* Modern dark dashboard polish */
section[data-testid="stSidebar"] {min-width: 280px;}
.block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
div.stButton>button {border-radius: 10px; padding: 0.6rem 1rem; font-weight: 600;}
</style>
""", unsafe_allow_html=True)

st.title("🧠 AI Student Planner")
st.caption("Smart task planner that generates your daily, weekly and monthly schedules automatically.")

# ---------- Helpers ----------
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "planner_data.json"

def run_cli(args:list[str])->str:
    """Run your existing CLI (main.py) and return stdout text."""
    out = subprocess.run(["python", "main.py", *args], capture_output=True, text=True)
    return (out.stdout or "") + (out.stderr or "")

def read_textfile(path:Path)->str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""

def list_plan_files():
    return sorted([p for p in ROOT.glob("plan*.txt")], key=lambda p: p.name)

# ---------- Sidebar ----------
with st.sidebar:
    st.header("⚙ Controls")
    st.write("Quick actions")
    if st.button("Generate Daily Plan"):
        run_cli(["plan", "--period", "day"])
        st.success("Daily plan generated ✅")
    if st.button("Generate Weekly Plan"):
        run_cli(["plan", "--period", "week"])
        st.success("Weekly plan generated ✅")
    if st.button("Generate Monthly Plan"):
        run_cli(["plan", "--period", "month"])
        st.success("Monthly plan generated ✅")

    st.divider()
    st.subheader("📁 Upload (notes / syllabus)")
    up = st.file_uploader("Optional: attach a file to reference", type=["txt","pdf","md","docx"], accept_multiple_files=True)
    uploaded_notes = []
    if up:
        for f in up:
            # we only keep content for AI context if it's text-like
            try:
                txt = f.read().decode("utf-8", errors="ignore")
                uploaded_notes.append((f.name, txt[:8000]))  # cap to keep prompt small
            except Exception:
                pass
        st.success(f"Attached {len(uploaded_notes)} file(s) for AI context")

# ---------- Main: Add task ----------
st.subheader("📝 Add a new task")
task_input = st.text_area(
    "Type your task in natural language",
    placeholder="e.g. Study for physics exam 2h tomorrow urgent",
    height=80
)

cols = st.columns([1,1,1])
if cols[0].button("Add Task"):
    if task_input.strip():
        out = run_cli(["add", task_input.strip()])
        st.success("Task added ✅")
        st.code(out or "Added.", language="text")
    else:
        st.warning("Please enter a task first.")

if cols[1].button("List Tasks"):
    st.code(run_cli(["list"]), language="text")

if cols[2].button("Clear All Tasks"):
    st.warning("This removes every task!")
    st.code(run_cli(["clear"]), language="text")

st.divider()

# ---------- AI Assistant ----------
st.subheader("🤖 AI Assistant (suggest plan)")

ai_cols = st.columns([1,1,1,1])
period_choice = ai_cols[0].selectbox("Plan period", ["day", "week", "month"], index=1)
hours_avail = ai_cols[1].number_input("Max study hrs/day", min_value=1, max_value=16, value=6)
start_hour = ai_cols[2].number_input("Start hour", min_value=5, max_value=12, value=9)
end_hour   = ai_cols[3].number_input("End hour", min_value=13, max_value=23, value=21)

if st.button("🧠 Generate Smart Plan"):
    # Build context: current tasks + (optional) uploaded notes
    current_tasks = run_cli(["list"])
    notes_text = ""
    if 'uploaded_notes' in locals() and uploaded_notes:
        joined = "\n\n".join([f"# {name}\n{txt}" for name, txt in uploaded_notes])
        notes_text = f"\n\nAdditional notes for context:\n{joined}"

    user_prompt = f"""
You are an assistant that creates efficient study schedules for students.
Create a {period_choice} plan considering work hours {int(start_hour)}:00–{int(end_hour)}:00,
max {int(hours_avail)} study hours per day, short 10m breaks between blocks.
Use the student tasks list below. If no durations are given, infer reasonable times.

Tasks (from system):
{current_tasks}

Primary new request (if any):
{task_input.strip()}

Format the output as time blocks, one per line:
HH:MM–HH:MM | [priority] title (duration) [notes]

End with a short checklist of key outcomes.
{notes_text}
""".strip()

    try:
        chat = client.chat.completions.create(
            model="gpt-4o-mini",  # lightweight & fast
            messages=[{"role":"user","content": user_prompt}],
            temperature=0.4,
        )
        plan_text = chat.choices[0].message.content.strip()
        st.success("AI plan generated ✅")
        st.code(plan_text, language="text")
        st.download_button("⬇ Download AI plan", plan_text, file_name=f"ai_plan_{period_choice}.txt")

    except Exception as e:
        st.error(f"AI error: {e}")

st.divider()

# ---------- Preview generated text plans ----------
st.subheader("🗂 Generated Plan Files")
plans = list_plan_files()
if not plans:
    st.info("No generated plans yet. Use the sidebar to create day/week/month plans.")
else:
    for p in plans:
        with st.expander(p.name):
            st.code(read_textfile(p), language="text")

# ---------- Show current tasks ----------
st.subheader("📋 Current Tasks (from CLI)")
st.code(run_cli(["list"]), language="text")
