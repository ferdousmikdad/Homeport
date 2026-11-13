#!/usr/bin/env bash
# Build Homeport.app and a drag-to-install .dmg (unsigned; ad-hoc signed by PyInstaller).
#   packaging/build_macos.sh [version]      -> dist/Homeport-mac-<arch>.dmg
set -euo pipefail
cd "$(dirname "$0")/.."
VERSION="${1:-${HOMEPORT_VERSION:-0.0.0}}"
ARCH="$(uname -m)"   # arm64 or x86_64

HOMEPORT_VERSION="$VERSION" pyinstaller packaging/homeport.spec --noconfirm --clean

STAGE="$(mktemp -d)"
cp -R dist/Homeport.app "$STAGE/"
ln -s /Applications "$STAGE/Applications"
DMG="dist/Homeport-mac-$ARCH.dmg"
rm -f "$DMG"
hdiutil create -volname "Homeport" -srcfolder "$STAGE" -ov -format UDZO "$DMG" >/dev/null
rm -rf "$STAGE"
echo "built $DMG"
