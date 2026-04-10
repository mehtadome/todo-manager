#!/bin/bash
# Opens an interactive Terminal window for the 6pm todo check-in.
# Called by cron — cannot run interactively from cron directly.

DIR="/Users/ruchir/Desktop/VSCode/Claude Sandbox/todo-manager"
PYTHON="$DIR/.venv/bin/python3"
SCRIPT="$DIR/todo_manager.py"

osascript <<EOF
tell application "Terminal"
    activate
    do script "echo ''; echo '🌆  Evening Todo Check-in'; \"$PYTHON\" \"$SCRIPT\" checkin; echo ''; echo 'Press any key to close...'; read -n1"
end tell
EOF
