#!/bin/bash
# Install a LaunchAgent that starts Homeport at login and restarts
# it if it stops. Works from wherever this project folder lives.
set -e

DIR="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.localhostmanager.server"
TEMPLATE="$DIR/scripts/localhostmanager.plist.template"
PLIST_DST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ ! -x "$DIR/.venv/bin/python" ]; then
    echo "❌ $DIR/.venv is missing. Create it first:"
    echo "   cd \"$DIR\" && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents" "$DIR/data/logs"

# Unload a previous copy (current or legacy name) if it is loaded
launchctl unload "$PLIST_DST" 2>/dev/null || true
launchctl unload "$HOME/Library/LaunchAgents/com.stably.localhostmanager.plist" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/com.stably.localhostmanager.plist"

# Fill in this project's folder (escape characters special to sed)
ESCAPED_DIR=$(printf '%s' "$DIR" | sed -e 's/[\/&|]/\\&/g')
sed "s|__DIR__|$ESCAPED_DIR|g" "$TEMPLATE" > "$PLIST_DST"
chmod 644 "$PLIST_DST"
plutil -lint "$PLIST_DST" >/dev/null

launchctl load -w "$PLIST_DST"

echo "✅ Homeport LaunchAgent installed for: $DIR"
echo "It will start automatically at login and restart if it stops."
