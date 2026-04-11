#!/bin/bash
# Sets up the todo manager from a fresh clone.
# Run once from inside the todo-manager/ folder.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "Setting up Todo Manager..."
echo ""

# ── Python environment ────────────────────────────────────────────────────────

echo "Creating virtual environment..."
python3 -m venv "$SCRIPT_DIR/.venv"

echo "Installing dependencies..."
"$SCRIPT_DIR/.venv/bin/pip" install --quiet claude-agent-sdk anyio

# ── Shell scripts ─────────────────────────────────────────────────────────────

chmod +x "$SCRIPT_DIR/todo_remind.sh"
chmod +x "$SCRIPT_DIR/todo_checkin.sh"

# ── Runtime files ─────────────────────────────────────────────────────────────

echo "Initializing data files..."

# .last_run left empty so the reminder fires on the very first login
touch "$SCRIPT_DIR/.last_run"

[ -f "$SCRIPT_DIR/todos.json" ] || \
    echo '{"tasks": [], "next_id": 1}' > "$SCRIPT_DIR/todos.json"

[ -f "$SCRIPT_DIR/reminders.json" ] || \
    echo '{"reminders": [], "next_id": 1}' > "$SCRIPT_DIR/reminders.json"

[ -f "$SCRIPT_DIR/completed_log.json" ] || \
    echo '{"completed": []}' > "$SCRIPT_DIR/completed_log.json"

# ── LaunchAgent ───────────────────────────────────────────────────────────────

PLIST_LABEL="com.$(whoami).todo-manager"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"

echo "Registering login launcher..."

cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$PLIST_LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$SCRIPT_DIR/todo_remind.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
EOF

# Unload first in case a stale entry exists (e.g. after moving the folder)
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "Done! Todo Manager is set up."
echo ""
echo "A Terminal window will open with your todos on your next login."
echo "You can also run it manually any time:"
echo ""
echo "  .venv/bin/python3 todo_manager.py todos"
echo ""
echo "If the login window doesn't appear, check:"
echo "  System Settings → Privacy & Security → Automation"
echo "  and make sure Terminal is allowed."
echo ""
