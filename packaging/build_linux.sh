#!/usr/bin/env bash
# Build Homeport for Linux: an AppImage and a .deb (x86_64).
#   packaging/build_linux.sh [version]
#   -> dist/Homeport-x86_64.AppImage, dist/homeport_<version>_amd64.deb
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${1:-${HOMEPORT_VERSION:-0.0.0}}"

HOMEPORT_VERSION="$VERSION" pyinstaller packaging/homeport.spec --noconfirm --clean

DESKTOP_ENTRY='[Desktop Entry]
Type=Application
Name=Homeport
Comment=Run, watch and share every local project
Exec=homeport
Icon=homeport
Categories=Development;
Terminal=false'

# ---- AppImage ----
APPDIR="$(mktemp -d)/Homeport.AppDir"
mkdir -p "$APPDIR/usr/lib/homeport"
cp -R dist/Homeport/. "$APPDIR/usr/lib/homeport/"
cp packaging/homeport.png "$APPDIR/homeport.png"
printf '%s\n' "$DESKTOP_ENTRY" > "$APPDIR/homeport.desktop"
cat > "$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/homeport/Homeport" "$@"
EOF
chmod +x "$APPDIR/AppRun"
TOOL="$(mktemp -d)/appimagetool"
curl -fsSL -o "$TOOL" https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x "$TOOL"
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 "$TOOL" "$APPDIR" dist/Homeport-x86_64.AppImage

# ---- .deb ----
PKG="$(mktemp -d)/homeport"
mkdir -p "$PKG/DEBIAN" "$PKG/opt/homeport" "$PKG/usr/bin" "$PKG/usr/share/applications" \
         "$PKG/usr/share/icons/hicolor/512x512/apps"
cp -R dist/Homeport/. "$PKG/opt/homeport/"
ln -s /opt/homeport/Homeport "$PKG/usr/bin/homeport"
printf '%s\n' "$DESKTOP_ENTRY" > "$PKG/usr/share/applications/homeport.desktop"
cp packaging/homeport.png "$PKG/usr/share/icons/hicolor/512x512/apps/homeport.png"
cat > "$PKG/DEBIAN/control" <<EOF
Package: homeport
Version: $VERSION
Section: devel
Priority: optional
Architecture: amd64
Maintainer: The Homeport contributors <noreply@github.com>
Recommends: libwebkit2gtk-4.1-0 | libwebkit2gtk-4.0-37, gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0
Homepage: https://github.com/ferdousmikdad/Homeport
Description: Run, watch and share every local project
 Free, open-source dashboard for local dev servers: any stack, named URLs,
 phone preview, safe share links, crash fixer, databases and WordPress mode.
EOF
dpkg-deb --build --root-owner-group "$PKG" "dist/homeport_${VERSION}_amd64.deb"
echo "built dist/Homeport-x86_64.AppImage and dist/homeport_${VERSION}_amd64.deb"
