# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

All commands use the venv Python, run from the repo root:

```bash
.venv/bin/python3 todo_manager.py todos          # all-in-one dashboard
.venv/bin/python3 todo_manager.py add "..."      # add tasks from natural language
.venv/bin/python3 todo_manager.py list           # view todos + AI priority recommendation
.venv/bin/python3 todo_manager.py reminder "..." # add a deadline-based reminder
.venv/bin/python3 todo_manager.py reminders      # view all reminders
.venv/bin/python3 todo_manager.py complete 1,3   # mark todos done by ID
.venv/bin/python3 todo_manager.py done-reminder 2
.venv/bin/python3 todo_manager.py log            # view completion history
.venv/bin/python3 todo_manager.py remind         # login reminder summary (non-interactive)
.venv/bin/python3 todo_manager.py checkin        # evening check-in (interactive)
```

## Setup

```bash
bash setup.sh   # creates .venv, installs deps, initializes data files, registers macOS LaunchAgent
```

The LaunchAgent (`~/Library/LaunchAgents/com.<user>.todo-manager.plist`) calls `todo_remind.sh` at login, which opens a Terminal window showing the daily summary — but only once per day (guarded by `.last_run`).

## Architecture

**Single-file CLI** — everything lives in `todo_manager.py`:

- **Data layer**: `todos.json`, `reminders.json`, `completed_log.json` — plain JSON files stored next to the script. `load_*/save_*` helpers read/write them directly with no ORM.
- **AI layer**: `ask_claude()` calls `claude_agent_sdk.query()` (uses Claude Code subscription, no API key). Three AI functions: `summarize_input` (NL → task list), `parse_reminder` (NL → `{text, due_date}`), `get_priority_recommendation` (tasks + reminders → 2–4 sentence advice). All return structured output parsed from Claude's response via `re.search`.
- **Commands**: async commands (`todos`, `add`, `reminder`, `list`, `remind`, `checkin`) use `anyio.run(main)`. Sync commands (`reminders`, `complete`, `done-reminder`, `log`) run directly. Async and sync command tables are separate dicts in `main()`.
- **Shell scripts**: `todo_remind.sh` (login, non-interactive) and `todo_checkin.sh` (evening, interactive) use AppleScript to open a Terminal window and run the appropriate command inside it.

**No tests, no linter config** — the project has no test suite or formatting toolchain.

## Key constraints

- `todo_remind.sh` and `todo_checkin.sh` have the repo path hard-coded. Re-run `bash setup.sh` after moving the folder to regenerate the LaunchAgent plist with the new path. The shell scripts themselves still need their `DIR` variable updated manually.
- The `claude-agent-sdk` requires the Claude Code CLI to be installed and logged in (`claude login`). No Anthropic API key is used.
- macOS only — depends on `osascript`/AppleScript and `launchctl`.
