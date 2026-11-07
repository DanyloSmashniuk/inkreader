#!/usr/bin/env bash
# Встановлює InkReader у ~/.local/share/InkReader і додає ярлик з іконкою в меню програм.
set -e
cd "$(dirname "$0")"
DEST="$HOME/.local/share/InkReader"
mkdir -p "$DEST" "$HOME/.local/share/applications" "$HOME/.local/share/icons/hicolor/256x256/apps"
rm -rf "$DEST"/*
cp -r InkReader/. "$DEST"/
chmod +x "$DEST/InkReader"
cp icon.png "$DEST/icon.png"
cp icon-256.png "$HOME/.local/share/icons/hicolor/256x256/apps/inkreader.png"
cat > "$HOME/.local/share/applications/inkreader.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=InkReader
Comment=Читалка EPUB та FB2
Exec=$DEST/InkReader %f
Icon=$DEST/icon.png
Terminal=false
Categories=Office;Viewer;
StartupWMClass=InkReader
MimeType=application/epub+zip;application/x-fictionbook+xml;application/x-fb2+xml;
DESK
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
(kbuildsycoca6 || kbuildsycoca5) >/dev/null 2>&1 || true
echo "Встановлено. Шукай «InkReader» у меню програм або запусти: $DEST/InkReader"
