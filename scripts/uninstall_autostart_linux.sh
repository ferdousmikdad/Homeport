#!/usr/bin/env bash
# Remove the Homeport login service / autostart entry on Linux.
set -uo pipefail
if command -v systemctl >/dev/null 2>&1 && [ -f "$HOME/.config/systemd/user/localhost-manager.service" ]; then
    systemctl --user disable --now localhost-manager.service 2>/dev/null
    rm -f "$HOME/.config/systemd/user/localhost-manager.service"
    systemctl --user daemon-reload 2>/dev/null
    echo "✅ Removed systemd user service 'localhost-manager'."
fi
if [ -f "$HOME/.config/autostart/localhost-manager.desktop" ]; then
    rm -f "$HOME/.config/autostart/localhost-manager.desktop"
    echo "✅ Removed ~/.config/autostart/localhost-manager.desktop."
fi
