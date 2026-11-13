#!/bin/bash
# Remove the Homeport login LaunchAgent (current and legacy names).
set -e

found=0
for NAME in com.localhostmanager.server com.stably.localhostmanager; do
    PLIST_DST="$HOME/Library/LaunchAgents/$NAME.plist"
    if [ -f "$PLIST_DST" ]; then
        launchctl unload "$PLIST_DST" 2>/dev/null || true
        rm -f "$PLIST_DST"
        echo "✅ Removed LaunchAgent $NAME."
        found=1
    fi
done

[ "$found" = 1 ] || echo "No Homeport LaunchAgent is installed."
