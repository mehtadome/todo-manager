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
PRIORITY_CACHE_FILE = SCRIPT_DIR / "priority_cache.json"

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
    return {"reminders": []}

def load_log():
    if COMPLETED_LOG_FILE.exists():
        with open(COMPLETED_LOG_FILE) as f:
            return json.load(f)
    return {"completed": []}

def load_priority_cache() -> dict | None:
    if PRIORITY_CACHE_FILE.exists():
        with open(PRIORITY_CACHE_FILE) as f:
            return json.load(f)
    return None

def save_priority_cache(recommendation: str, todo_ids: list[int]):
    with open(PRIORITY_CACHE_FILE, "w") as f:
        json.dump({
            "recommendation": recommendation,
            "cached_at": datetime.now().isoformat(),
            "todo_ids": todo_ids,
        }, f, indent=2)

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
        return f", 🔴 OVERDUE by {abs(days_left)}d"
    if days_left == 0:
        return ", 🚨 DUE TODAY"
    if days_left == 1:
        return ", 🚨 due tomorrow"
    if days_left <= 3:
        return f", ⚠️ due in {days_left}d"
    if days_left <= 7:
        return f", 📌 due in {days_left}d"
    return f", due in {days_left}d"

# ─── Input helper ─────────────────────────────────────────────────────────────

def multiline_input(prompt: str) -> str:
    """Read free-form text until the user hits Enter twice consecutively."""
    print(prompt)
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        except KeyboardInterrupt:
            raise
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

async def get_priority_recommendation(tasks: list[dict]) -> str:
    lines = ["TODOS:"]
    for i, t in enumerate(tasks, 1):
        lines.append(f"  [{i}] {t['text']} — pending {days_pending(t['created_at'])} day(s)")

    system = """You are a productivity coach.
Return ONLY a JSON object with two keys:
  "num": the [#] number of the single highest-priority todo
  "reason": one sentence explaining why, with no markdown formatting.
Factor in how long todos have been pending."""

    raw = await ask_claude("\n".join(lines) + "\n\nWhat should I tackle first and why?", system)
    match = re.search(r'\{.*?\}', raw, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            num = int(parsed["num"])
            reason = parsed["reason"].replace("**", "")
            return f"[{num}] {tasks[num - 1]['text']}: {reason}"
        except (KeyError, IndexError, ValueError, json.JSONDecodeError):
            pass
    return raw.replace("**", "")

# ─── Command ──────────────────────────────────────────────────────────────────

async def cmd_todos(morning: bool = False, force_refresh: bool = False):
    tasks = load_todos()["tasks"]
    reminders = load_reminders()["reminders"]

    # ── Todos ─────────────────────────────────────────────────────────────────
    if tasks:
        print(f"\n━━━  📋  TODOS  ({len(tasks)} pending)  ━━━\n")
        for i, task in enumerate(tasks, 1):
            age = days_pending(task["created_at"])
            age_str = "today" if age == 0 else f"{age}d"
            flag = "  ⚠️  overdue!" if age >= 7 else ("  📌" if age >= 3 else "")
            print(f"  [{i}]  {task['text']}")
            print(f"         pending {age_str}{flag}")
    else:
        print("\n━━━  📋  TODOS  ━━━\n")
        print("  No pending todos.")
        if morning:
            print("  (No todos to prioritize — skipping inference.)")

    # ── Reminders (display only) ───────────────────────────────────────────────
    if reminders:
        print(f"\n━━━  🔔  REMINDERS  ({len(reminders)} active)  ━━━\n")
        for i, r in enumerate(sorted(reminders, key=lambda r: r["due_date"]), 1):
            left = days_until(r["due_date"])
            print(f"  [{i}]  {r['text']}")
            print(f"         {r['due_date']}{urgency_label(left)}")

    # ── Priority recommendation ────────────────────────────────────────────────
    if tasks:
        current_ids = [t["id"] for t in tasks]
        cache = load_priority_cache()
        cached_ids = cache.get("todo_ids", []) if cache else []
        has_new_todos = any(tid not in cached_ids for tid in current_ids)

        needs_inference = morning or force_refresh or cache is None or has_new_todos

        print("\n🎯  Priority Recommendation\n")
        if needs_inference:
            rec = await get_priority_recommendation(tasks)
            save_priority_cache(rec, current_ids)
        else:
            rec = cache["recommendation"]
        print(f"   {rec}")

    # ── Complete todos ─────────────────────────────────────────────────────────
    if tasks:
        print("\nMark any todos as done? Enter numbers (space-separated), or press Enter to skip:")
        try:
            done_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); return

        if done_input:
            try:
                ids = {int(x) for x in done_input.split()}
            except ValueError:
                print("Invalid input — enter space-separated numbers.")
                return

            data = load_todos()
            log = load_log()
            now = datetime.now().isoformat()
            done, remaining = [], []
            for i, task in enumerate(data["tasks"], 1):
                if i in ids:
                    days = days_pending(task["created_at"])
                    log["completed"].append({
                        "id": task["id"], "text": task["text"],
                        "created_at": task["created_at"], "completed_at": now,
                        "days_to_complete": days, "type": "todo"
                    })
                    done.append((task, days))
                else:
                    remaining.append(task)
            data["tasks"] = remaining
            save_todos(data)
            save_log(log)
            if done:
                print(f"\n✅  Completed {len(done)} task(s):")
                for task, days in done:
                    duration = "same day" if days == 0 else f"{days} day{'s' if days != 1 else ''}"
                    print(f"   ✓  {task['text']}  ({duration})")

    # ── Add new todos ──────────────────────────────────────────────────────────
    print("\n─── New todos? (reminders will be asked next) ───")
    try:
        new_todos = multiline_input("Rant freely — press Enter twice when done, or just Enter twice to skip:\n")
    except KeyboardInterrupt:
        print(); return
    if new_todos:
        print("\nProcessing...", flush=True)
        new_tasks = await summarize_input(new_todos)
        if new_tasks:
            data = load_todos()
            now = datetime.now().isoformat()
            print("\nAdded tasks:")
            for i, task_text in enumerate(new_tasks, 1):
                task = {"id": data["next_id"], "text": task_text, "created_at": now}
                data["tasks"].append(task)
                data["next_id"] += 1
                print(f"  {i}. {task_text}")
            save_todos(data)
            print(f"\n✓ {len(new_tasks)} task(s) added.")

    # ── Add new reminders ──────────────────────────────────────────────────────
    print("\n─── New reminders? ───")
    try:
        new_reminder = multiline_input("Describe what and by when — press Enter twice when done, or just Enter twice to skip:\n")
    except KeyboardInterrupt:
        print(); return
    if new_reminder:
        print("\nProcessing...", flush=True)
        parsed = await parse_reminder(new_reminder)
        if parsed:
            data = load_reminders()
            if "next_id" not in data:
                data["next_id"] = len(data["reminders"]) + 1
            reminder = {
                "id": data["next_id"],
                "text": parsed["text"],
                "due_date": parsed["due_date"],
                "created_at": datetime.now().isoformat()
            }
            data["reminders"].append(reminder)
            data["next_id"] += 1
            with open(REMINDERS_FILE, "w") as f:
                json.dump(data, f, indent=2)
            left = days_until(parsed["due_date"])
            print(f"\n  🔔  {parsed['text']}")
            print(f"       {parsed['due_date']}{urgency_label(left)}")
            print("\n✓ Reminder saved.")
        else:
            print("Couldn't extract a task and date — try: \"submit report by April 10th\"")

    print()

# ─── Entry point ──────────────────────────────────────────────────────────────

async def main():
    args = sys.argv[1:]
    morning = "--morning" in args
    force_refresh = "--messages" in args
    positional = [a for a in args if not a.startswith("--")]

    if positional and positional[0].lower() != "todos":
        print(f"Unknown command: '{positional[0]}'. Only 'todos' is supported.")
        sys.exit(1)

    await cmd_todos(morning=morning, force_refresh=force_refresh)

if __name__ == "__main__":
    try:
        anyio.run(main)
    except KeyboardInterrupt:
        print()
        sys.exit(0)
