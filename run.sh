#!/usr/bin/env bash
# Start Homeport on Linux or macOS.
# First run creates .venv and installs requirements; later runs reinstall only
# when requirements.txt changes. Then starts the server and opens the browser.
set -euo pipefail
cd "$(dirname "$0")"

VENV_PY=".venv/bin/python"

find_python() {
    for cand in python3 python3.13 python3.12 python3.11 python3.10 python3.9 python; do
        if command -v "$cand" >/dev/null 2>&1 &&
           "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
            echo "$cand"; return 0
        fi
    done
    return 1
}

if [ ! -x "$VENV_PY" ] || ! "$VENV_PY" -c 'import sys' 2>/dev/null; then
    PY="$(find_python)" || {
        echo "❌ Python 3.9 or newer is required."
        echo "   macOS: https://www.python.org/downloads/   Ubuntu/Debian: sudo apt install python3 python3-venv"
        exit 1
    }
    echo "Creating .venv with $("$PY" --version 2>&1)…"
    rm -rf .venv
    if ! "$PY" -m venv .venv; then
        echo "❌ Could not create a virtual environment."
        echo "   Ubuntu/Debian: sudo apt install python3-venv"
        exit 1
    fi
fi

if ! cmp -s requirements.txt .venv/requirements.installed 2>/dev/null; then
    echo "Installing requirements…"
    "$VENV_PY" -m pip install --upgrade pip >/dev/null
    "$VENV_PY" -m pip install -r requirements.txt
    cp requirements.txt .venv/requirements.installed
fi

exec "$VENV_PY" launch.py "$@"
