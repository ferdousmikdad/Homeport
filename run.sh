#!/usr/bin/env bash
# Start Homeport on Linux or macOS — nothing needs to be installed first.
#
#   1. Already set up?               -> start right away.
#   2. Python 3.9+ on this computer? -> use it to set up .venv.
#   3. No Python?                    -> download a private copy (via uv) into
#                                       .runtime/ inside this folder. Nothing is
#                                       installed system-wide; no admin needed.
# Requirements are (re)installed only when requirements.txt changes.
set -euo pipefail
cd "$(dirname "$0")"

VENV_PY=".venv/bin/python"
RUNTIME="$PWD/.runtime"
UV="$RUNTIME/uv"
# Keep everything uv downloads inside this folder.
export UV_PYTHON_INSTALL_DIR="$RUNTIME/python" UV_CACHE_DIR="$RUNTIME/cache"

find_python() {
    local cand path
    for cand in python3 python3.13 python3.12 python3.11 python3.10 python3.9 python; do
        path="$(command -v "$cand" 2>/dev/null)" || continue
        # macOS: without the Command Line Tools, /usr/bin/python3 is only a
        # stub that pops up an install dialog — skip it.
        if [ "$(uname -s)" = Darwin ] && [ "$path" = /usr/bin/python3 ] && ! xcode-select -p >/dev/null 2>&1; then
            continue
        fi
        # needs venv + ensurepip (Debian/Ubuntu split them out as python3-venv)
        if "$path" -c 'import sys, venv, ensurepip; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1; then
            echo "$path"
            return 0
        fi
    done
    return 1
}

get_uv() {
    [ -x "$UV" ] && return 0
    local target
    case "$(uname -s)-$(uname -m)" in
        Darwin-arm64) target=aarch64-apple-darwin ;;
        Darwin-x86_64) target=x86_64-apple-darwin ;;
        Linux-x86_64) target=x86_64-unknown-linux-gnu ;;
        Linux-aarch64 | Linux-arm64) target=aarch64-unknown-linux-gnu ;;
        *)
            echo "❌ Automatic setup isn't available for $(uname -s) $(uname -m)."
            echo "   Install Python 3.9 or newer, then run this again."
            exit 1 ;;
    esac
    command -v curl >/dev/null 2>&1 || { echo "❌ curl is needed to download Python. Install curl or Python 3.9+."; exit 1; }
    echo "Python wasn't found — downloading a private copy into .runtime/ (one time, about 40 MB)…"
    mkdir -p "$RUNTIME"
    curl -fsSL "https://github.com/astral-sh/uv/releases/latest/download/uv-$target.tar.gz" \
        | tar -xz -C "$RUNTIME" --strip-components=1
}

# 1–3: make sure .venv exists and works
if [ ! -x "$VENV_PY" ] || ! "$VENV_PY" -c 'import sys' >/dev/null 2>&1; then
    rm -rf .venv
    if [ -z "${HOMEPORT_FORCE_DOWNLOAD:-}" ] && PY="$(find_python)"; then
        echo "Setting up with $("$PY" --version 2>&1)…"
        "$PY" -m venv .venv
    else
        get_uv
        UV_PYTHON_PREFERENCE=only-managed "$UV" venv --quiet --python 3.12 .venv
    fi
fi

# requirements (only when requirements.txt changed)
if ! cmp -s requirements.txt .venv/requirements.installed 2>/dev/null; then
    echo "Installing requirements…"
    if "$VENV_PY" -m pip --version >/dev/null 2>&1; then
        "$VENV_PY" -m pip install --quiet --upgrade pip
        "$VENV_PY" -m pip install --quiet -r requirements.txt
    else
        get_uv  # a .venv made by uv has no pip
        "$UV" pip install --quiet --python "$VENV_PY" -r requirements.txt
        rm -rf "$RUNTIME/cache"  # downloaded wheels aren't needed once installed
    fi
    cp requirements.txt .venv/requirements.installed
fi

exec "$VENV_PY" launch.py "$@"
