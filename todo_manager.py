#!/usr/bin/env python3
"""
AI-Powered Local Todo Task Manager
Uses Claude Code (via claude-agent-sdk) — no API key required.
"""

import anyio
import json
import re
import sys
import subprocess
from datetime import datetime, date
from pathlib import Path

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

SCRIPT_DIR = Path(__file__).parent
TODOS_FILE = SCRIPT_DIR / "todos.json"
REMINDERS_FILE = SCRIPT_DIR / "reminders.json"
COMPLETED_LOG_FILE = SCRIPT_DIR / "completed_log.json"

# ─── Data helpers ────────────────────────────────────────────────────────────

def load_todos():
    if TODOS_FILE.exists():
        with open(TODOS_FILE) as f:
            return json.load(f)
    return {"tasks": [], "next_id": 1}

def save_todos(data):
    with open(TODOS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_reminders():
    if REMINDERS_FILE.exists():
        with open(REMINDERS_FILE) as f:
            return json.load(f)
    return {"reminders": [], "next_id": 1}

def save_reminders(data):
    with open(REMINDERS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_log():
    if COMPLETED_LOG_FILE.exists():
        with open(COMPLETED_LOG_FILE) as f:
            return json.load(f)
    return {"completed": []}

def save_log(data):
    with open(COMPLETED_LOG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def days_pending(created_at_str: str) -> int:
    created = datetime.fromisoformat(created_at_str)
    return (datetime.now() - created).days

def days_until(due_date_str: str) -> int:
    due = date.fromisoformat(due_date_str)
    return (due - date.today()).days

def urgency_label(days_left: int) -> str:
    if days_left < 0:
        return f"  🔴  OVERDUE by {abs(days_left)}d"
    if days_left == 0:
        return "  🚨  DUE TODAY"
    if days_left == 1:
        return "  🚨  due tomorrow"
    if days_left <= 3:
        return f"  ⚠️   due in {days_left}d"
    if days_left <= 7:
        return f"  📌  due in {days_left}d"
    return f"  due in {days_left}d"

# ─── Input helper ─────────────────────────────────────────────────────────────

def multiline_input(prompt: str) -> str:
    """Read free-form text until the user hits Enter twice consecutively."""
    print(prompt)
    lines = []
    while True:
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            break
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines).strip()

# ─── macOS notification ───────────────────────────────────────────────────────

def notify(title: str, message: str):
    try:
        safe_msg = message.replace('"', '\\"')
        safe_title = title.replace('"', '\\"')
        subprocess.run(
            ["osascript", "-e",
             f'display notification "{safe_msg}" with title "{safe_title}" sound name "default"'],
            capture_output=True, timeout=5
        )
    except Exception:
        pass

# ─── Claude helpers (via Claude Code subscription) ────────────────────────────

async def ask_claude(prompt: str, system: str) -> str:
    """Send a single prompt to Claude and return the result. Runs inside the shared event loop."""
    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(system_prompt=system, max_turns=1)
    ):
        if isinstance(message, ResultMessage):
            return message.result or ""
    return ""

async def summarize_input(raw_text: str) -> list[str]:
    system = """You are a personal task manager assistant. The user will give you a stream-of-consciousness description of things they need to do.

Extract each distinct task, rewrite it as a clear and concise action item, and return ONLY a valid JSON array of strings — no preamble, no explanation, no markdown.

Example input:
"ugh I need to call my dentist about that appointment I've been putting off, finish the quarterly report for Sarah, and fix that login bug that keeps crashing"

Example output:
["Call dentist to schedule/confirm appointment", "Complete and submit quarterly report to Sarah", "Fix login page crash bug"]"""

    text = await ask_claude(raw_text, system)
    match = re.search(r'\[.*?\]', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return [
        re.sub(r'^[\d\.\-\)\s]+', '', line).strip()
        for line in text.splitlines()
        if line.strip() and line.strip() not in ('[', ']')
    ]

async def parse_reminder(raw_text: str) -> dict | None:
    today = date.today().isoformat()
    system = f"""You are a reminder parser. Today's date is {today}.

The user will describe something they need to do by a certain date. Extract:
1. A clear, concise task description
2. The due date in YYYY-MM-DD format

Return ONLY a JSON object with keys "text" and "due_date". No preamble, no markdown.

Examples:
Input: "need to submit my tax return by april 15th"
Output: {{"text": "Submit tax return", "due_date": "2026-04-15"}}

Input: "remind me to renew my car registration, it expires end of this month"
Output: {{"text": "Renew car registration", "due_date": "2026-04-30"}}"""

    text = await ask_claude(raw_text, system)
    match = re.search(r'\{.*?\}', text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            if "text" in parsed and "due_date" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass
    return None

async def get_priority_recommendation(tasks: list[dict], reminders: list[dict]) -> str:
    lines = []
    if tasks:
        lines.append("TODOS (no fixed deadline):")
        for i, t in enumerate(tasks):
            lines.append(f"  {i+1}. [ID {t['id']}] {t['text']} — pending {days_pending(t['created_at'])} day(s)")
    if reminders:
        lines.append("\nREMINDERS (deadline-based):")
        for i, r in enumerate(reminders):
            left = days_until(r["due_date"])
            status = f"OVERDUE by {abs(left)}d" if left < 0 else (f"due in {left}d" if left > 0 else "DUE TODAY")
            lines.append(f"  {i+1}. [ID {r['id']}] {r['text']} — {status} (due {r['due_date']})")

    system = """You are a productivity coach. The user has both open-ended todos and deadline-based reminders.
Give a direct, actionable priority recommendation in 2–4 sentences.
Treat overdue and imminent reminders (≤3 days) as highest urgency — call them out explicitly.
Factor in how long todos have been pending too."""

    return await ask_claude("\n".join(lines) + "\n\nWhat should I tackle first and why?", system)

# ─── Commands ─────────────────────────────────────────────────────────────────

async def cmd_add(args: list[str]):
    if args:
        raw_text = " ".join(args)
    else:
        raw_text = multiline_input("What do you need to get done? Just rant — I'll sort it out.\n(Press Enter twice when done)\n")
        if not raw_text:
            print("Nothing entered.")
            return

    print("\nProcessing...", flush=True)
    tasks = await summarize_input(raw_text)
    if not tasks:
        print("Couldn't extract any tasks from that input.")
        return

    data = load_todos()
    now = datetime.now().isoformat()

    print("\nAdded tasks:")
    for i, task_text in enumerate(tasks, 1):
        task = {"id": data["next_id"], "text": task_text, "created_at": now}
        data["tasks"].append(task)
        data["next_id"] += 1
        print(f"  {i}. {task_text}")

    save_todos(data)
    print(f"\n✓ {len(tasks)} task(s) added.")

async def cmd_add_reminder(raw_text: str = ""):
    if not raw_text:
        raw_text = multiline_input("Describe what you need to do and by when.\n(Press Enter twice when done)\n")
        if not raw_text:
            print("Nothing entered.")
            return

    print("\nProcessing...", flush=True)
    parsed = await parse_reminder(raw_text)
    if not parsed:
        print("Couldn't extract a task and date from that. Try: \"submit report by April 10th\"")
        return

    data = load_reminders()
    reminder = {
        "id": data["next_id"],
        "text": parsed["text"],
        "due_date": parsed["due_date"],
        "created_at": datetime.now().isoformat()
    }
    data["reminders"].append(reminder)
    data["next_id"] += 1
    save_reminders(data)

    left = days_until(parsed["due_date"])
    print(f"\n  🔔  {parsed['text']}")
    print(f"      Due {parsed['due_date']}{urgency_label(left)}")
    print("\n✓ Reminder saved.")

def cmd_complete_reminder(args: list[str]):
    if not args:
        print("Usage: done-reminder <id1,id2,...>")
        return
    try:
        ids = {int(x.strip()) for x in args[0].split(",")}
    except ValueError:
        print("Error: IDs must be comma-separated integers.")
        return

    data = load_reminders()
    log = load_log()
    now = datetime.now().isoformat()

    done, remaining = [], []
    for r in data["reminders"]:
        if r["id"] in ids:
            left = days_until(r["due_date"])
            log["completed"].append({
                "id": r["id"], "text": r["text"], "due_date": r["due_date"],
                "created_at": r["created_at"], "completed_at": now,
                "days_to_complete": days_pending(r["created_at"]),
                "days_before_due": left, "type": "reminder"
            })
            done.append(r)
        else:
            remaining.append(r)

    if not done:
        print("No matching reminder IDs found.")
        return

    data["reminders"] = remaining
    save_reminders(data)
    save_log(log)

    print(f"\n✅  Dismissed {len(done)} reminder(s):")
    for r in done:
        left = days_until(r["due_date"])
        timing = "on time" if left >= 0 else f"{abs(left)}d late"
        print(f"   ✓  {r['text']}  ({timing})")

def _print_reminders(reminders: list[dict]):
    for r in sorted(reminders, key=lambda r: r["due_date"]):
        left = days_until(r["due_date"])
        print(f"  [{r['id']:>2}]  {r['text']}")
        print(f"         due {r['due_date']}{urgency_label(left)}")

def cmd_list_reminders():
    data = load_reminders()
    reminders = data["reminders"]
    if not reminders:
        print("\nNo reminders set.")
        return
    print(f"\n🔔  Reminders  ({len(reminders)} total)\n")
    _print_reminders(reminders)
    print()

def cmd_complete(args: list[str]):
    if not args:
        print("Usage: complete <id1,id2,...>  (e.g. complete 1,3)")
        return
    try:
        ids = {int(x.strip()) for x in args[0].split(",")}
    except ValueError:
        print("Error: IDs must be comma-separated integers.")
        return

    data = load_todos()
    log = load_log()
    now = datetime.now().isoformat()

    done, remaining = [], []
    for task in data["tasks"]:
        if task["id"] in ids:
            days = days_pending(task["created_at"])
            log["completed"].append({
                "id": task["id"], "text": task["text"],
                "created_at": task["created_at"], "completed_at": now,
                "days_to_complete": days, "type": "todo"
            })
            done.append((task, days))
        else:
            remaining.append(task)

    if not done:
        print("No matching task IDs found. Use `list` to see IDs.")
        return

    data["tasks"] = remaining
    save_todos(data)
    save_log(log)

    print(f"\n✅  Completed {len(done)} task(s):")
    for task, days in done:
        duration = "same day" if days == 0 else f"{days} day{'s' if days != 1 else ''}"
        print(f"   ✓  {task['text']}  ({duration})")

async def cmd_todos():
    tasks = load_todos()["tasks"]
    reminders = load_reminders()["reminders"]
    has_anything = tasks or reminders

    # ── Section 1: Todos ──────────────────────────────────────────────────────
    if tasks:
        print(f"\n━━━  📋  TODOS  ({len(tasks)} pending)  ━━━\n")
        for task in tasks:
            age = days_pending(task["created_at"])
            age_str = "today" if age == 0 else f"{age}d"
            flag = "  ⚠️  overdue!" if age >= 7 else ("  📌" if age >= 3 else "")
            print(f"  [{task['id']:>2}]  {task['text']}")
            print(f"         pending {age_str}{flag}")
    else:
        print("\n━━━  📋  TODOS  ━━━\n")
        print("  No pending todos.")

    # ── Section 2: Reminders ──────────────────────────────────────────────────
    if reminders:
        print(f"\n━━━  🔔  REMINDERS  ({len(reminders)} active)  ━━━\n")
        _print_reminders(reminders)
    else:
        print(f"\n━━━  🔔  REMINDERS  ━━━\n")
        print("  No reminders set.")

    # ── Priority recommendation ───────────────────────────────────────────────
    if has_anything:
        print("\n🎯  Priority Recommendation\n")
        rec = await get_priority_recommendation(tasks, reminders)
        for line in rec.splitlines():
            print(f"   {line}")

    # ── Step 1: Mark todos done ───────────────────────────────────────────────
    if tasks:
        print("\nMark any todos as done? Enter IDs (comma-separated), or press Enter to skip:")
        try:
            done_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); return
        if done_input:
            cmd_complete([done_input])

    # ── Step 2: Dismiss reminders ─────────────────────────────────────────────
    if reminders:
        print("\nDismiss any reminders? Enter IDs (comma-separated), or press Enter to skip:")
        try:
            dismiss_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); return
        if dismiss_input:
            cmd_complete_reminder([dismiss_input])

    # ── Step 3: New todos ─────────────────────────────────────────────────────
    print("\n─── New todos? ───")
    new_todos = multiline_input("Rant freely — press Enter twice when done, or just Enter twice to skip:\n")
    if new_todos:
        await cmd_add([new_todos])

    # ── Step 4: New reminders ─────────────────────────────────────────────────
    print("\n─── New reminders? ───")
    new_reminder = multiline_input("Describe what you need to do and by when — press Enter twice when done, or just Enter twice to skip:\n")
    if new_reminder:
        await cmd_add_reminder(new_reminder)

    print()

async def cmd_list(silent=False) -> list[dict]:
    data = load_todos()
    tasks = data["tasks"]

    if not tasks:
        if not silent:
            print("\nNo pending tasks! You're all caught up 🎉")
        return []

    if not silent:
        print(f"\n📋  Pending Tasks  ({len(tasks)} total)\n")
        for task in tasks:
            age = days_pending(task["created_at"])
            age_str = "today" if age == 0 else f"{age}d"
            flag = "  ⚠️  overdue!" if age >= 7 else ("  📌" if age >= 3 else "")
            print(f"  [{task['id']:>2}]  {task['text']}")
            print(f"         pending {age_str}{flag}")

        reminders = load_reminders()["reminders"]
        print("\n🎯  Priority Recommendation\n")
        rec = await get_priority_recommendation(tasks, reminders)
        for line in rec.splitlines():
            print(f"   {line}")
        print()

    return tasks

async def cmd_remind():
    tasks = load_todos()["tasks"]
    reminders = load_reminders()["reminders"]
    urgent_reminders = [r for r in reminders if days_until(r["due_date"]) <= 3]

    if not tasks and not reminders:
        notify("📋 Daily Reminder", "Nothing pending — you're all caught up!")
        print("\n☀️  Good afternoon! Nothing pending — you're all caught up 🎉")
        return

    notif_parts = []
    if tasks:
        notif_parts.append(f"{len(tasks)} todo(s)")
    if urgent_reminders:
        notif_parts.append(f"{len(urgent_reminders)} urgent reminder(s)")
    elif reminders:
        notif_parts.append(f"{len(reminders)} reminder(s)")
    notify("📋 Daily Reminder", ", ".join(notif_parts) + " pending.")

    if tasks:
        print(f"\n☀️  Daily Reminder — {len(tasks)} todo(s)\n")
        for task in tasks:
            age = days_pending(task["created_at"])
            age_str = "today" if age == 0 else f"{age}d"
            flag = "  ⚠️" if age >= 7 else ("  📌" if age >= 3 else "")
            print(f"  [{task['id']:>2}]  {task['text']}  ({age_str}){flag}")

    if reminders:
        print(f"\n🔔  Reminders\n")
        _print_reminders(reminders)

    print("\n🎯  Today's Priority:\n")
    rec = await get_priority_recommendation(tasks, reminders)
    for line in rec.splitlines():
        print(f"   {line}")
    print()

async def cmd_checkin():
    tasks = load_todos()["tasks"]
    reminders = load_reminders()["reminders"]
    notify("📋 Evening Check-in",
           f"{len(tasks)} todo(s), {len(reminders)} reminder(s) pending. Time to check in!")
    await cmd_todos()

def cmd_log():
    log = load_log()
    completed = log["completed"]

    if not completed:
        print("\nNothing completed yet.")
        return

    print(f"\n📊  Completed Log  ({len(completed)} total)\n")
    for entry in sorted(completed, key=lambda x: x["completed_at"], reverse=True):
        done_date = datetime.fromisoformat(entry["completed_at"]).strftime("%Y-%m-%d")
        days = entry["days_to_complete"]
        duration = "same day" if days == 0 else f"{days} day{'s' if days != 1 else ''}"
        tag = "🔔" if entry.get("type") == "reminder" else "✓"
        extra = ""
        if entry.get("type") == "reminder" and "days_before_due" in entry:
            left = entry["days_before_due"]
            extra = f"  |  {'on time' if left >= 0 else f'{abs(left)}d late'}"
        print(f"  {tag}  {entry['text']}")
        print(f"     Completed {done_date}  |  Took {duration}{extra}")

    if len(completed) > 1:
        avg = sum(e["days_to_complete"] for e in completed) / len(completed)
        print(f"\n  Average completion time: {avg:.1f} days")
    print()

# ─── Entry point ──────────────────────────────────────────────────────────────

USAGE = """
AI-Powered Todo Task Manager

Commands:
  todos              Show everything, mark done, add new (all-in-one)
  add [text...]      Add todos (rant freely)
  reminder           Add a deadline-based reminder
  list               Show pending todos + priority recommendation
  reminders          Show all reminders
  complete <ids>     Mark todos done by ID
  done-reminder <ids>  Dismiss reminders by ID
  remind             1pm summary (runs automatically via cron)
  checkin            6pm check-in (runs automatically via cron)
  log                View completed history
"""

async def main():
    if len(sys.argv) < 2:
        print(USAGE)
        return

    cmd = sys.argv[1].lower()
    args = sys.argv[2:]

    async_commands = {
        "todos": cmd_todos,
        "add": lambda: cmd_add(args),
        "reminder": cmd_add_reminder,
        "list": cmd_list,
        "remind": cmd_remind,
        "checkin": cmd_checkin,
    }
    sync_commands = {
        "reminders": cmd_list_reminders,
        "complete": lambda: cmd_complete(args),
        "done-reminder": lambda: cmd_complete_reminder(args),
        "log": cmd_log,
    }

    if cmd in async_commands:
        await async_commands[cmd]()
    elif cmd in sync_commands:
        sync_commands[cmd]()
    else:
        print(f"Unknown command: '{cmd}'\n{USAGE}")
        sys.exit(1)

if __name__ == "__main__":
    anyio.run(main)
