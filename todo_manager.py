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
    return {"reminders": []}

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

async def get_priority_recommendation(tasks: list[dict], reminders: list[dict]) -> str:
    lines = []
    if tasks:
        lines.append("TODOS (no fixed deadline):")
        for i, t in enumerate(tasks, 1):
            lines.append(f"  [{i}] {t['text']} — pending {days_pending(t['created_at'])} day(s)")
    if reminders:
        lines.append("\nREMINDERS (deadline-based):")
        for i, r in enumerate(reminders, 1):
            left = days_until(r["due_date"])
            status = f"OVERDUE by {abs(left)}d" if left < 0 else (f"due in {left}d" if left > 0 else "DUE TODAY")
            lines.append(f"  [{i}] {r['text']} — {status} (due {r['due_date']})")

    system = """You are a productivity coach. The user has both open-ended todos and deadline-based reminders.
Return ONLY a JSON object with three keys:
  "num": the [#] number of the single highest-priority item
  "type": "todo" or "reminder"
  "reason": one sentence explaining why, with no markdown formatting.
Treat overdue and imminent reminders (≤3 days) as highest urgency.
Factor in how long todos have been pending too."""

    raw = await ask_claude("\n".join(lines) + "\n\nWhat should I tackle first and why?", system)
    match = re.search(r'\{.*?\}', raw, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            num = int(parsed["num"])
            reason = parsed["reason"].replace("**", "")
            if parsed.get("type") == "reminder":
                item_text = sorted(reminders, key=lambda r: r["due_date"])[num - 1]["text"]
            else:
                item_text = tasks[num - 1]["text"]
            return f"[{num}] {item_text}: {reason}"
        except (KeyError, IndexError, ValueError, json.JSONDecodeError):
            pass
    return raw.replace("**", "")

# ─── Command ──────────────────────────────────────────────────────────────────

async def cmd_todos():
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

    # ── Reminders (display only) ───────────────────────────────────────────────
    if reminders:
        print(f"\n━━━  🔔  REMINDERS  ({len(reminders)} active)  ━━━\n")
        for i, r in enumerate(sorted(reminders, key=lambda r: r["due_date"]), 1):
            left = days_until(r["due_date"])
            print(f"  [{i}]  {r['text']}")
            print(f"         {r['due_date']}{urgency_label(left)}")

    # ── Priority recommendation ────────────────────────────────────────────────
    if tasks or reminders:
        print("\n🎯  Priority Recommendation\n")
        rec = await get_priority_recommendation(tasks, reminders)
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
    print("\n─── Anything else to add? ───")
    new_todos = multiline_input("Rant freely — press Enter twice when done, or just Enter twice to skip:\n")
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

    print()

# ─── Entry point ──────────────────────────────────────────────────────────────

async def main():
    if len(sys.argv) > 1 and sys.argv[1].lower() != "todos":
        print(f"Unknown command: '{sys.argv[1]}'. Only 'todos' is supported.")
        sys.exit(1)
    await cmd_todos()

if __name__ == "__main__":
    anyio.run(main)
