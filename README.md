# Todo Manager

An AI-powered local task manager for macOS. Describe what you need to do in plain English — Claude turns it into clean, numbered tasks. A Terminal window opens automatically every time you log in.

> **No API key needed.** This runs through your Claude Pro or Claude Code subscription.

> **v1.2 is out.** `--complete-todo`, improved todo summarization, inference recommendation removed — see the [changelog](https://github.com/mehtadome/todo-manager/pull/6).

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

> **Side effect — Script Editor opening at login:** If the LaunchAgent plist points to a `.sh` file that no longer exists (e.g. after moving the folder without re-running setup), macOS may open Script Editor at login instead of Terminal. This happens because Launch Services falls back to opening the missing file by its `.sh` association. Fix it by re-running `bash setup.sh`, or remove the plist manually: `rm ~/Library/LaunchAgents/com.<user>.todo-manager.plist`.

### 3. Grant macOS permissions

The launcher uses AppleScript to open a Terminal window. On first run, macOS will prompt you to allow this. Click **Allow** when asked.

If the Terminal window doesn't appear on login, go to:

**System Settings → Privacy & Security → Automation**

Make sure **Terminal** is allowed to be controlled by scripts.

---

## How it works

Every time you log in, a Terminal window opens automatically running `todos --remindme`. You can also trigger it manually at any time:

```bash
.venv/bin/python3 todo_manager.py todos
```

The session shows:
- All pending todos with color-dot age indicators
- Any active reminders with due-date urgency (display only)
- A prompt to mark todos and reminders done by number
- A free-text prompt to rant — Claude distills it into clean action items

Numbers displayed next to todos reset to `[1]` each session — always use what you see on screen.

Todo age dots:
- `⚪` — added today or yesterday
- `🟢` — 3–6 days old
- `🟡` — 7–13 days old
- `🔴` — 14+ days (very stale)

### Non-interactive flags

All flags exit after their action and print the current list — useful for shell aliases or scripting.

| Flag | Behavior |
|---|---|
| `--remindme` | Display-only summary, no prompts (used by login LaunchAgent) |
| `--add-todo "text"` | Add a todo; Claude always restates it concisely before saving |
| `--add-reminder "text"` | Parse natural-language reminder with due date |
| `--complete-todo "text"` | Complete by case-insensitive text match |
| `--complete-todo #N` or `N` | Complete by list position |
| `--complete-todo` | Show list, then multiline number entry (Enter×2 to submit) |

---

## Files

| File | Purpose |
|------|---------|
| `setup.sh` | One-time setup: venv, dependencies, data files, LaunchAgent |
| `todo_manager.py` | Main CLI script |
| `scripts/todo_remind.sh` | Opens a Terminal window at login |
| `scripts/todo_checkin.sh` | Opens a Terminal window for an evening check-in |
| `.venv/` | Python virtual environment (created by setup) |
| `assets/todos.json` | Live task list (created by setup) |
| `assets/reminders.json` | Active reminders (created by setup) |
| `assets/completed_log.json` | Completion history (created by setup) |
| `assets/todo_cron.log` | Cron output log |
| `assets/.last_reminded` | Tracks the last date the login reminder fired (created by setup) |
