# Todo Manager

An AI-powered local task manager for macOS. Describe what you need to do in plain English — Claude turns it into clean, numbered tasks and recommends what to tackle first based on urgency and how long things have been sitting. A Terminal window opens automatically every time you log in.

> **No API key needed.** This runs through your Claude Pro or Claude Code subscription.

---

## Prerequisites

Before cloning, make sure you have the following installed and ready.

### Claude Code CLI

This app uses the `claude-agent-sdk`, which requires the Claude Code CLI to be installed and logged in.

1. Install Claude Code: https://claude.ai/code
2. Log in:
   ```bash
   claude login
   ```
   Follow the browser prompt to authenticate with your Anthropic account.

### Python 3

macOS ships with Python 3. Verify it's available:

```bash
python3 --version
```

If not found, install it from https://python.org or via Homebrew: `brew install python3`

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/mehtadome/todo-manager.git
cd todo-manager
```

### 2. Run setup

```bash
bash setup.sh
```

This handles everything in one shot:
- Creates the Python virtual environment and installs dependencies
- Makes the shell scripts executable
- Initializes the data files (`todos.json`, `reminders.json`, etc.)
- Registers the macOS LaunchAgent that opens a Terminal window at login

To verify the launcher is registered:

```bash
launchctl list | grep todo-manager
```

> **If you move the folder**, just re-run `bash setup.sh` from the new location. It will re-register the LaunchAgent with the updated path.

### 3. Grant macOS permissions

The launcher uses AppleScript to open a Terminal window. On first run, macOS will prompt you to allow this. Click **Allow** when asked.

If the Terminal window doesn't appear on login, go to:

**System Settings → Privacy & Security → Automation**

Make sure **Terminal** is allowed to be controlled by scripts.

---

## How it works

Every time you log in, a Terminal window opens automatically showing:

- All pending todos with age indicators
- All active reminders with due-date urgency
- Claude's priority recommendation for what to tackle first

You can also trigger it manually at any time:

```bash
.venv/bin/python3 todo_manager.py remind
```

---

## Usage

All commands are run from inside the `todo-manager/` folder.

### `todos` — All-in-one dashboard

View everything, mark completions, and add new tasks in one session.

```bash
.venv/bin/python3 todo_manager.py todos
```

---

### `add` — Add tasks from natural language

Just describe what you need to do. Claude extracts and cleans up the individual tasks.

```bash
.venv/bin/python3 todo_manager.py add "need to email the client back, fix that login bug in prod, and pick up dry cleaning before Saturday"
```

Or run with no arguments for a multi-line prompt:

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

### `reminder` — Add a deadline-based reminder

Describe the task and its due date in plain English.

```bash
.venv/bin/python3 todo_manager.py reminder "need to file my taxes by April 15th"
```

---

### `list` — View pending todos

Shows all todos with age indicators and Claude's priority recommendation.

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

### `reminders` — View all reminders

```bash
.venv/bin/python3 todo_manager.py reminders
```

---

### `complete` — Mark todos as done

Pass one or more IDs as a comma-separated list.

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

### `done-reminder` — Dismiss a reminder

```bash
.venv/bin/python3 todo_manager.py done-reminder 2
```

---

### `log` — View completion history

```bash
.venv/bin/python3 todo_manager.py log
```

Output:
```
📊  Completed Log  (5 total)

  ✓  Reply to client email regarding project timeline
     Completed 2026-03-31  |  Took same day
  ✓  Pick up dry cleaning before Saturday
     Completed 2026-03-31  |  Took 8 days

  Average completion time: 3.4 days
```

---

## Files

| File | Purpose |
|------|---------|
| `setup.sh` | One-time setup: venv, dependencies, data files, LaunchAgent |
| `todo_manager.py` | Main CLI script |
| `todo_remind.sh` | Opens a Terminal window at login with your todo summary |
| `todo_checkin.sh` | Opens a Terminal window for an interactive check-in session |
| `.venv/` | Python virtual environment (created by setup) |
| `todos.json` | Live task list (created by setup) |
| `reminders.json` | Active reminders (created by setup) |
| `completed_log.json` | Completion history (created by setup) |
| `.last_run` | Tracks the last date the login reminder fired (created by setup) |
