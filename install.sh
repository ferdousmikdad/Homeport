#!/bin/sh
# Install Homeport on macOS or Linux:
#   curl -fsSL https://raw.githubusercontent.com/ferdousmikdad/Homeport/main/install.sh | sh
#
# - Apple Silicon Mac: installs Homeport.app into /Applications (or ~/Applications)
# - Linux x86_64:      installs the AppImage + a menu entry and a `homeport` command
# - anything else:     installs from source and starts it (needs nothing first)
# Files fetched with curl aren't quarantined, so no "unverified developer" prompt.
set -eu

REPO="ferdousmikdad/Homeport"
BASE="${HOMEPORT_DOWNLOAD_BASE:-https://github.com/$REPO/releases/latest/download}"
RAW="https://raw.githubusercontent.com/$REPO/main"
OS="$(uname -s)"
ARCH="$(uname -m)"

say() { printf '%s\n' "$*"; }
fetch() { curl -fsSL --retry 3 -o "$2" "$1"; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM

# ---- macOS (Apple Silicon): native app ----
if [ "$OS" = Darwin ] && [ "$ARCH" = arm64 ] && fetch "$BASE/Homeport-mac-arm64.zip" "$TMP/homeport.zip" 2>/dev/null; then
    DEST="${HOMEPORT_APPS_DIR:-/Applications}"
    [ -w "$DEST" ] || DEST="$HOME/Applications"
    mkdir -p "$DEST"
    rm -rf "$DEST/Homeport.app"
    ditto -x -k "$TMP/homeport.zip" "$DEST"
    xattr -dr com.apple.quarantine "$DEST/Homeport.app" 2>/dev/null || true
    say "✓ Homeport installed in $DEST — opening it now."
    [ -n "${HOMEPORT_NO_OPEN:-}" ] || open "$DEST/Homeport.app"
    exit 0
fi

# ---- Linux (x86_64): AppImage ----
if [ "$OS" = Linux ] && [ "$ARCH" = x86_64 ] && fetch "$BASE/Homeport-x86_64.AppImage" "$TMP/Homeport.AppImage" 2>/dev/null; then
    LIB="$HOME/.local/lib/homeport"
    BIN="$HOME/.local/bin"
    mkdir -p "$LIB" "$BIN" "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/512x512/apps"
    install -m 755 "$TMP/Homeport.AppImage" "$LIB/Homeport.AppImage"
    cat > "$BIN/homeport" <<EOF
#!/bin/sh
# Homeport launcher (works without FUSE too)
APP="$LIB/Homeport.AppImage"
if [ -e /dev/fuse ] && { ldconfig -p 2>/dev/null | grep -q 'libfuse.so.2'; }; then exec "\$APP" "\$@"; fi
exec "\$APP" --appimage-extract-and-run "\$@"
EOF
    chmod 755 "$BIN/homeport"
    fetch "$RAW/packaging/homeport.png" "$HOME/.local/share/icons/hicolor/512x512/apps/homeport.png" 2>/dev/null || true
    cat > "$HOME/.local/share/applications/homeport.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Homeport
Comment=Run, watch and share every local project
Exec=$BIN/homeport
Icon=homeport
Categories=Development;
Terminal=false
EOF
    say "✓ Homeport installed — find it in your apps menu, or run: homeport"
    nohup "$BIN/homeport" >/dev/null 2>&1 &
    exit 0
fi

# ---- Anything else: run from source (no install needed first) ----
DIR="${HOMEPORT_HOME:-$HOME/.homeport/app}"
say "Installing Homeport from source into $DIR …"
if command -v git >/dev/null 2>&1; then
    if [ -d "$DIR/.git" ]; then
        git -C "$DIR" pull --ff-only --quiet
    else
        rm -rf "$DIR"
        mkdir -p "$(dirname "$DIR")"
        git clone --depth 1 --quiet "https://github.com/$REPO" "$DIR"
    fi
else
    fetch "https://github.com/$REPO/archive/refs/heads/main.tar.gz" "$TMP/src.tar.gz"
    rm -rf "$DIR"
    mkdir -p "$DIR"
    tar -xzf "$TMP/src.tar.gz" -C "$DIR" --strip-components=1
fi
mkdir -p "$HOME/.local/bin"
printf '#!/bin/sh\nexec "%s/run.sh" "$@"\n' "$DIR" > "$HOME/.local/bin/homeport"
chmod 755 "$HOME/.local/bin/homeport"
say "✓ Installed. Start it any time with: homeport   (or $DIR/run.sh)"
exec "$DIR/run.sh"
