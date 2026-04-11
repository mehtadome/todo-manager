#!/bin/bash
# Opens an interactive Terminal window for the daily todo reminder.
# Called by launchd at login — skips if already run today.

DIR="/Users/ruchir/Desktop/VSCode/Claude Sandbox/todo-manager"
PYTHON="$DIR/.venv/bin/python3"
SCRIPT="$DIR/todo_manager.py"
LAST_RUN_FILE="$DIR/.last_run"

TODAY="$(date +%Y-%m-%d)"
if [ -f "$LAST_RUN_FILE" ] && [ "$(cat "$LAST_RUN_FILE")" = "$TODAY" ]; then
    exit 0
fi
echo "$TODAY" > "$LAST_RUN_FILE"

osascript <<EOF
tell application "Terminal"
    activate
    do script "echo ''; echo '☀️  Daily Todo Reminder'; \"$PYTHON\" \"$SCRIPT\" remind; echo ''; echo 'Press any key to close...'; read -n1"
end tell
EOF
