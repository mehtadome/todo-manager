# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

All commands use the venv Python, run from the repo root:

```bash
.venv/bin/python3 todo_manager.py todos           # all-in-one interactive dashboard
.venv/bin/python3 todo_manager.py todos --morning # morning mode: shows AI priority recommendation
.venv/bin/python3 todo_manager.py todos --remindme # non-interactive reminder summary (used at login)
```

## Setup

```bash
bash setup.sh   # creates .venv, installs deps, initializes data files, registers macOS LaunchAgent
```

The LaunchAgent (`~/Library/LaunchAgents/com.<user>.todo-manager.plist`) calls `scripts/todo_remind.sh` at login, which opens a Terminal window showing the daily summary — but only once per day (guarded by `assets/.last_reminded`).

## Architecture

**Single-file CLI** — everything lives in `todo_manager.py`:

- **Data layer**: `assets/todos.json`, `assets/reminders.json`, `assets/completed_log.json`, `assets/priority_cache.json` — plain JSON files stored in the `assets/` subdirectory. `load_*/save_*` helpers read/write them directly with no ORM.
- **AI layer**: `ask_claude()` calls `claude_agent_sdk.query()` (uses Claude Code subscription, no API key). Three AI functions: `summarize_input` (NL → task list), `parse_reminders` (NL → list of `{text, due_date}`), `get_priority_recommendation` (todos → one-sentence priority pick). All return structured output parsed from Claude's response via `re.search`.
- **Commands**: single entry point — `todos` — which runs an interactive session: displays current todos and reminders, offers to mark items done, then prompts for new todos and reminders. Optional flags: `--morning` (show AI priority recommendation), `--remindme` (non-interactive, used by the login LaunchAgent).
- **Shell scripts**: `scripts/todo_remind.sh` (login, non-interactive) and `scripts/todo_checkin.sh` (evening, interactive) use AppleScript to open a Terminal window and run the appropriate command inside it.

**No tests, no linter config** — the project has no test suite or formatting toolchain.

## Key constraints

- `scripts/todo_remind.sh` and `scripts/todo_checkin.sh` have the repo path hard-coded. Re-run `bash setup.sh` after moving the folder to regenerate the LaunchAgent plist with the new path. The shell scripts themselves still need their `DIR` variable updated manually.
- The `claude-agent-sdk` requires the Claude Code CLI to be installed and logged in (`claude login`). No Anthropic API key is used.
- macOS only — depends on `osascript`/AppleScript and `launchctl`.
