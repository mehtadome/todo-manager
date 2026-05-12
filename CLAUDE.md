# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Versioning

Each merged PR increments the minor version. Current version: **v1.2** (PR #6).

| Version | PR |
|---|---|
| v1.0 | [#4 — reminders overhaul, quick-add flags, side effect docs](https://github.com/mehtadome/todo-manager/pull/4) |
| v1.1 | [#5 — color-dot priority system](https://github.com/mehtadome/todo-manager/pull/5) |
| v1.2 | [#6 — remove inference recommendation, always restate todos via Claude, add --complete-todo](https://github.com/mehtadome/todo-manager/pull/6) |

When creating a new PR, add a row to this table with the next version (v1.1, v1.2, …). When the version reaches **v1.9**, flag it to the user before proceeding — that's the signal to discuss whether to cut a v2.0.

## Running the app

All commands use the venv Python, run from the repo root:

```bash
.venv/bin/python3 todo_manager.py todos                        # all-in-one interactive dashboard
.venv/bin/python3 todo_manager.py todos --remindme             # non-interactive reminder summary (used at login)
.venv/bin/python3 todo_manager.py todos --add-todo "text"      # add a single todo via Claude restatement
.venv/bin/python3 todo_manager.py todos --complete-todo "text" # complete by text match, #N, or omit for interactive
```

## Setup

```bash
bash setup.sh   # creates .venv, installs deps, initializes data files, registers macOS LaunchAgent
```

The LaunchAgent (`~/Library/LaunchAgents/com.<user>.todo-manager.plist`) calls `scripts/todo_remind.sh` at login, which opens a Terminal window showing the daily summary — but only once per day (guarded by `assets/.last_reminded`).

## Architecture

**Single-file CLI** — everything lives in `todo_manager.py`:

- **Data layer**: `assets/todos.json`, `assets/reminders.json`, `assets/completed_log.json` — plain JSON files stored in the `assets/` subdirectory. `load_*/save_*` helpers read/write them directly with no ORM.
- **AI layer**: `ask_claude()` calls `claude_agent_sdk.query()` (uses Claude Code subscription, no API key). Two AI functions: `summarize_input` (NL → task list, always called for any todo input), `parse_reminders` (NL → list of `{text, due_date}`). Both return structured output parsed from Claude's response via `re.search`.
- **Commands**: single entry point — `todos` — which runs an interactive session: displays current todos and reminders, offers to mark items done, then prompts for new todos and reminders. Optional flags: `--remindme` (non-interactive, used by the login LaunchAgent), `--add-todo` (non-interactive add), `--add-reminder` (non-interactive add), `--complete-todo` (non-interactive completion by text, number, or interactive list).
- **Shell scripts**: `scripts/todo_remind.sh` (login, non-interactive) and `scripts/todo_checkin.sh` (evening, interactive) use AppleScript to open a Terminal window and run the appropriate command inside it.

**No tests, no linter config** — the project has no test suite or formatting toolchain.

## Known side effects

- **Script Editor opens at login**: If the LaunchAgent plist points to a `.sh` file that no longer exists (e.g. after moving the repo without re-running `setup.sh`), macOS Launch Services may open Script Editor at login via `.sh` file association. Fix by re-running `bash setup.sh`, or remove the plist with `launchctl unload` + `rm`.
- **"You have mail" at terminal open**: macOS delivers stderr from failed LaunchAgent runs to the local mailbox. A broken plist path causes this to accumulate. Removing or fixing the plist stops new mail; existing mail can be cleared with the `mail` command.

## Key constraints

- `scripts/todo_remind.sh` and `scripts/todo_checkin.sh` have the repo path hard-coded. Re-run `bash setup.sh` after moving the folder to regenerate the LaunchAgent plist with the new path. The shell scripts themselves still need their `DIR` variable updated manually.
- The `claude-agent-sdk` requires the Claude Code CLI to be installed and logged in (`claude login`). No Anthropic API key is used.
- macOS only — depends on `osascript`/AppleScript and `launchctl`.
