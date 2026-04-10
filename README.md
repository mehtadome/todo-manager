# Todo Manager

An AI-powered local task manager. Rant about what you need to do — Claude turns it into clean, numbered tasks, recommends what to tackle first based on how long things have been sitting, and nudges you twice a day to stay on top of it.

---

## Setup

> **No API key needed.** This app runs through your Claude Code subscription.
> Make sure you're logged in: `claude login`

### 1. Create the virtual environment and install dependencies

From inside the `todo-manager/` folder:

```bash
python3 -m venv .venv
.venv/bin/pip install claude-agent-sdk anyio
```

### 2. Enable the daily reminders (cron)

Run this once from inside the `todo-manager/` folder to register the two cron jobs:

```bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$SCRIPT_DIR/.venv/bin/python3"
(
  echo "# Todo Manager — 1pm daily reminder"
  echo "0 13 * * * source ~/.zshrc && \"$PYTHON\" \"$SCRIPT_DIR/todo_manager.py\" remind >> \"$SCRIPT_DIR/todo_cron.log\" 2>&1"
  echo "# Todo Manager — 6pm interactive check-in"
  echo "0 18 * * * source ~/.zshrc && \"$SCRIPT_DIR/todo_checkin.sh\" >> \"$SCRIPT_DIR/todo_cron.log\" 2>&1"
) | crontab -
```

> **Note:** If you move the folder, re-run the block above from the new location to update the cron paths.

---

## Usage

All commands are run from inside the `todo-manager/` folder using the venv Python.

### `add` — Add tasks from natural language

Just rant. Claude extracts and cleans up the individual tasks for you.

```bash
.venv/bin/python3 todo_manager.py add "need to email the client back, fix that login bug in prod, and pick up dry cleaning before Saturday"
```

You can also run it with no arguments for a multi-line prompt:

```bash
.venv/bin/python3 todo_manager.py add
```

Output:
```
Added tasks:
  1. Reply to client email regarding project timeline
  2. Fix production login bug
  3. Pick up dry cleaning before Saturday

✓ 3 task(s) added.
```

---

### `list` — View pending tasks with a priority recommendation

```bash
.venv/bin/python3 todo_manager.py list
```

Output:
```
📋  Pending Tasks  (3 total)

  [ 1]  Reply to client email regarding project timeline
         pending today
  [ 2]  Fix production login bug
         pending 4d  📌
  [ 3]  Pick up dry cleaning before Saturday
         pending 8d  ⚠️  overdue!

🎯  Priority Recommendation

   You've had the dry cleaning and the login bug sitting for several days —
   tackle those first. The client email can follow.
```

Age indicators:
- `📌` — pending 3+ days
- `⚠️ overdue!` — pending 7+ days

---

### `complete` — Mark tasks as done

Pass one or more task IDs as a comma-separated list.

```bash
.venv/bin/python3 todo_manager.py complete 1,3
```

Output:
```
✅  Completed 2 task(s):
   ✓  Reply to client email regarding project timeline  (same day)
   ✓  Pick up dry cleaning before Saturday  (8 days)
```

---

### `log` — View completed task history

See every task you've finished and how long it took.

```bash
.venv/bin/python3 todo_manager.py log
```

Output:
```
📊  Completed Tasks Log  (5 total)

  ✓  Reply to client email regarding project timeline
     Completed 2026-03-31  |  Took same day
  ✓  Pick up dry cleaning before Saturday
     Completed 2026-03-31  |  Took 8 days
  ...

  Average completion time: 3.4 days
```

---

### `remind` — Manual 1pm reminder

Prints your task list and a priority recommendation. Also fires a macOS notification.

```bash
.venv/bin/python3 todo_manager.py remind
```

This runs automatically every day at 1pm via cron.

---

### `checkin` — Manual 6pm check-in

Interactive session: mark completions and add new tasks.

```bash
.venv/bin/python3 todo_manager.py checkin
```

This runs automatically every day at 6pm via cron (opens a new Terminal window).

---

## How the daily automation works

| Time | What happens |
|------|-------------|
| **1pm** | macOS notification fires. Your task list and Claude's priority pick print to the terminal (and to `todo_cron.log`). |
| **6pm** | A new Terminal window opens with the interactive check-in. Mark what you finished, add anything new. |

Cron output is appended to `todo_cron.log` in this folder.

---

## Files

| File | Purpose |
|------|---------|
| `todo_manager.py` | Main CLI script |
| `todo_checkin.sh` | Shell wrapper that opens Terminal for the 6pm cron job |
| `.venv/` | Python virtual environment (run `python3 -m venv .venv` to create) |
| `todos.json` | Live task list (auto-created) |
| `completed_log.json` | Completion history (auto-created) |
| `todo_cron.log` | Cron job output log (auto-created) |

---

## Model

Uses your **Claude Code subscription** via `claude-agent-sdk` — no API key required. Runs whatever model your subscription provides.
