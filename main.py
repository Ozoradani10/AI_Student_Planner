#!/usr/bin/env python3
# AI Student Planner (CLI) — natural language tasks -> daily/weekly/monthly plan
# No web UI. Uses JSON storage + dateparser. Single-file, fast.

import json, re, sys, argparse, uuid
from pathlib import Path
from datetime import datetime, timedelta, time
import dateparser

DATA_FILE = Path(__file__).with_name("planner_data.json")
WORK_START = time(9, 0)     # start of planning day
WORK_END   = time(21, 0)    # end of planning day
DEFAULT_BLOCK_MIN = 60      # default study block minutes
DEFAULT_BREAK_MIN = 10      # short break between blocks

PRIORITY_MAP = {"urgent": 3, "high": 2, "medium": 1, "low": 0}
LEVEL_TO_TEXT = {3:"urgent",2:"high",1:"medium",0:"low"}

# ---------------------------- Storage ----------------------------
def _now():
    return datetime.now()

def load_data():
    if DATA_FILE.exists():
        with DATA_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {"tasks": [], "completed": []}

def save_data(data):
    with DATA_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ---------------------------- Parsing ----------------------------
DUR_RE = re.compile(r'(?P<val>\d+(\.\d+)?)\s*(?P<Unit>h|hr|hrs|hour|hours|m|min|mins|minute|minutes)\b', re.I)

def parse_duration_minutes(text, default=DEFAULT_BLOCK_MIN):
    m = DUR_RE.search(text)
    if not m:
        return default
    val = float(m.group("val"))
    unit = m.group("Unit").lower()
    return int(val*60) if unit.startswith('h') else int(val)

def parse_due(text):
    # Try to detect explicit due date/time; fallback None
    # Examples: "tomorrow 5pm", "by Friday", "due 20 Oct 14:00"
    candidates = []
    for chunk in re.findall(r'(by|due|on|at|before)?\s*[^,.;]*', text, re.I):
        dt = dateparser.parse(chunk, settings={"PREFER_DATES_FROM": "future"})
        if dt: candidates.append(dt)
    return min(candidates) if candidates else None

def infer_priority(text):
    for k, v in PRIORITY_MAP.items():
        if re.search(rf'\b{k}\b', text, re.I):
            return v
    if re.search(r'\b(exam|midterm|final|quiz|deadline)\b', text, re.I):
        return 2
    return 1  # default medium

def infer_course(text):
    # naive: words after "for" or "in" until punctuation
    m = re.search(r'\b(for|in)\s+([A-Za-z0-9\s\-&]{2,})', text)
    if m:
        return m.group(2).strip().split(",")[0][:40]
    return None

# ---------------------------- Commands ----------------------------
def cmd_add(args):
    data = load_data()
    text = args.text
    task = {
        "id": str(uuid.uuid4())[:8],
        "title": text.strip(),
        "course": infer_course(text),
        "duration_min": parse_duration_minutes(text),
        "priority": infer_priority(text),
        "due": parse_due(text).isoformat() if parse_due(text) else None,
        "created": _now().isoformat(),
        "notes": args.notes
    }
    data["tasks"].append(task)
    save_data(data)
    print(f"[ADDED] {task['id']} • {task['title']} • {LEVEL_TO_TEXT[task['priority']]} • {task['duration_min']}m" +
          (f" • due {task['due']}" if task['due'] else ""))

def cmd_list(_args):
    data = load_data()
    if not data["tasks"]:
        print("No open tasks.")
        return
    # sort by priority desc, then by due soonest, then created
    def sort_key(t):
        due = dateparser.parse(t["due"]) if t["due"] else datetime.max
        return (-t["priority"], due, t["created"])
    for t in sorted(data["tasks"], key=sort_key):
        due = dateparser.parse(t["due"]).strftime("%Y-%m-%d %H:%M") if t["due"] else "-"
        print(f"{t['id']} | {LEVEL_TO_TEXT[t['priority']]:6} | {t['duration_min']:>3}m | due: {due} | {t['title']}")

def cmd_delete(args):
    data = load_data()
    before = len(data["tasks"])
    data["tasks"] = [t for t in data["tasks"] if t["id"] != args.id]
    save_data(data)
    print("[DELETED]" if len(data["tasks"]) < before else "[NOT FOUND]")

def cmd_done(args):
    data = load_data()
    idx = next((i for i,t in enumerate(data["tasks"]) if t["id"]==args.id), None)
    if idx is None:
        print("[NOT FOUND]")
        return
    t = data["tasks"].pop(idx)
    t["completed_at"] = _now().isoformat()
    data["completed"].append(t)
    save_data(data)
    print(f"[DONE] {t['id']} • {t['title']}")

# ---------------------------- Planning Core ----------------------------
def daterange(start_date, end_date):
    d = start_date
    while d <= end_date:
        yield d
        d += timedelta(days=1)

def plan_window(period, start_str=None):
    if start_str:
        start = datetime.strptime(start_str, "%Y-%m-%d")
    else:
        today = _now().date()
        start = datetime.combine(today, time(0,0))
    if period == "day":
        end = start + timedelta(days=0)
    elif period == "week":
        end = start + timedelta(days=6)
    else:
        # month = 30-day window from start
        end = start + timedelta(days=29)
    return start, end

def day_slots(day):
    # generate work slots between WORK_START and WORK_END
    start_dt = datetime.combine(day.date(), WORK_START)
    end_dt = datetime.combine(day.date(), WORK_END)
    return [(start_dt, end_dt)]

def allocate(tasks, start, end):
    # Greedy fit: priority desc, due soonest, then longest
    def tkey(t):
        due = dateparser.parse(t["due"]) if t["due"] else datetime.max
        return (-t["priority"], due, -t["duration_min"])
    tasks = sorted(tasks, key=tkey)

    schedule = []  # list of blocks: {start,end,task_id,title}
    for day in daterange(start.date(), end.date()):
        free_windows = day_slots(datetime.combine(day, time()))
        # place tasks that must occur on/before this day
        for task in [x for x in tasks if x["duration_min"] > 0]:
            due_dt = dateparser.parse(task["due"]) if task["due"] else None
            if due_dt and due_dt.date() < day:
                # already missed; schedule today anyway
                pass

        i = 0
        while i < len(tasks):
            t = tasks[i]
            if t["duration_min"] <= 0:
                i += 1
                continue

            # If task has due date before this day ends, try to place today; else still place if room.
            can_place_today = True
            # Try to fit in first free window big enough
            placed = False
            dur = t["duration_min"]
            j = 0
            while j < len(free_windows):
                win_start, win_end = free_windows[j]
                available = int((win_end - win_start).total_seconds() // 60)
                if available >= dur:
                    block_start = win_start
                    block_end = win_start + timedelta(minutes=dur)
                    schedule.append({
                        "start": block_start.isoformat(),
                        "end": block_end.isoformat(),
                        "task_id": t["id"],
                        "title": t["title"],
                        "course": t["course"],
                        "priority": t["priority"]
                    })
                    # update window: consume + add a small break
                    new_start = block_end + timedelta(minutes=DEFAULT_BREAK_MIN)
                    if new_start < win_end:
                        free_windows[j] = (new_start, win_end)
                    else:
                        free_windows.pop(j)
                    # consume task
                    t["duration_min"] = 0
                    placed = True
                    break
                else:
                    j += 1
            if not placed:
                i += 1  # try next task
        # next day

    return schedule

def cmd_plan(args):
    data = load_data()
    start, end = plan_window(args.period, args.start)
    # Copy tasks snapshot
    tasks = [dict(t) for t in data["tasks"]]

    # Trim tasks to period window preference: prioritize tasks due within window
    filtered = []
    for t in tasks:
        due = dateparser.parse(t["due"]) if t["due"] else None
        if (due is None) or (start.date() <= due.date() <= end.date()):
            filtered.append(t)
    if not filtered:
        filtered = tasks  # if window has none, still plan from backlog

    schedule = allocate(filtered, start, end)

    if not schedule:
        print("No schedule generated (not enough tasks or zero durations).")
        return

    # Output pretty table and save file
    out_lines = []
    print(f"=== PLAN: {args.period.upper()} ({start.date()} -> {end.date()}) ===")
    cur_day = None
    for blk in sorted(schedule, key=lambda b: b["start"]):
        s = dateparser.parse(blk["start"])
        e = dateparser.parse(blk["end"])
        if cur_day != s.date():
            cur_day = s.date()
            print(f"\n{cur_day} -------------------------")
            out_lines.append(f"\n{cur_day} -------------------------")
        line = f"{s.strftime('%H:%M')} - {e.strftime('%H:%M')} | [{LEVEL_TO_TEXT[blk['priority']]}] {blk['title']}"
        if blk.get("course"):
            line += f"  ({blk['course']})"
        print(line)
        out_lines.append(line)

    out_path = Path(__file__).with_name(f"plan{args.period}{start.date()}{end.date()}.txt")
    out_path.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"\n[SAVED] {out_path.name}")

def cmd_clear(_args):
    save_data({"tasks": [], "completed": []})
    print("[CLEARED] All tasks removed.")

# ---------------------------- CLI ----------------------------
def build_parser():
    p = argparse.ArgumentParser(prog="planner", description="AI Student Planner (CLI)")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="Add a task in natural language")
    a.add_argument("text", help='e.g., "Finish math homework 2h by tomorrow 5pm urgent"')
    a.add_argument("--notes", default="", help="Optional notes")
    a.set_defaults(func=cmd_add)

    sub.add_parser("list", help="List tasks").set_defaults(func=cmd_list)

    d = sub.add_parser("delete", help="Delete task by ID")
    d.add_argument("id")
    d.set_defaults(func=cmd_delete)

    dn = sub.add_parser("done", help="Mark task done by ID")
    dn.add_argument("id")
    dn.set_defaults(func=cmd_done)

    pl = sub.add_parser("plan", help="Generate plan")
    pl.add_argument("--period", choices=["day","week","month"], default="day")
    pl.add_argument("--start", help="YYYY-MM-DD (default=today)")
    pl.set_defaults(func=cmd_plan)

    sub.add_parser("clear", help="Remove all tasks").set_defaults(func=cmd_clear)
    return p

def generate_all_periods():
    import subprocess
    print("\n[AI AGENT] Generating daily, weekly, and monthly plans...\n")
    subprocess.run(["python", "main.py", "plan", "--period", "day"])
    subprocess.run(["python", "main.py", "plan", "--period", "week"])
    subprocess.run(["python", "main.py", "plan", "--period", "month"])
    print("\n[AI AGENT] All plans generated successfully!\n")

def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)

# ---- handle "all" mode before running normal CLI ----
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "all":
        generate_all_periods()
        sys.exit()
    else:
        main()
