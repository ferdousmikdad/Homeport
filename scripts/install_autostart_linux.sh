#!/usr/bin/env bash
# Start Homeport when you log in to Linux (systemd user service,
# or an XDG autostart entry on desktops without systemd --user).
set -euo pipefail
DIR="$(cd "$(dirname "$0")/.." && pwd)"
PY="$DIR/.venv/bin/python"
[ -x "$PY" ] || { echo "Run ./run.sh once first so .venv is created."; exit 1; }

if command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
    UNIT_DIR="$HOME/.config/systemd/user"
    mkdir -p "$UNIT_DIR"
    cat > "$UNIT_DIR/localhost-manager.service" <<UNIT
[Unit]
Description=Homeport
After=network-online.target

[Service]
WorkingDirectory=$DIR
ExecStart="$PY" "$DIR/launch.py" --no-browser
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
UNIT
    systemctl --user daemon-reload
    systemctl --user enable --now localhost-manager.service
    echo "✅ Installed systemd user service 'localhost-manager' (running now, starts at login)."
else
    mkdir -p "$HOME/.config/autostart"
    cat > "$HOME/.config/autostart/localhost-manager.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Homeport
Exec="$PY" "$DIR/launch.py" --no-browser
Path=$DIR
X-GNOME-Autostart-enabled=true
DESK
    echo "✅ Added ~/.config/autostart/localhost-manager.desktop (starts at your next login)."
fi
