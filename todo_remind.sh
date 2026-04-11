#!/bin/bash
# Opens an interactive Terminal window for the daily todo reminder.
# Called by cron/launchd — cannot run interactively from there directly.

DIR="/Users/ruchir/Desktop/VSCode/Claude Sandbox/todo-manager"
PYTHON="$DIR/.venv/bin/python3"
SCRIPT="$DIR/todo_manager.py"

osascript <<EOF
tell application "Terminal"
    activate
    do script "echo ''; echo '☀️  Daily Todo Reminder'; \"$PYTHON\" \"$SCRIPT\" remind; echo ''; echo 'Press any key to close...'; read -n1"
end tell
EOF
