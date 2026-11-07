#!/usr/bin/env bash
# Пакує зібрану програму в dist/InkReader-linux.tar.xz разом із install.sh та іконками.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -x dist/InkReader/InkReader ] || { echo "Спочатку виконайте scripts/build_linux.sh"; exit 1; }
OUT=dist/InkReader-linux
rm -rf "$OUT"; mkdir -p "$OUT"
cp -r dist/InkReader "$OUT/InkReader"
cp scripts/install.sh assets/icon.png assets/icon-256.png "$OUT/"
# менший розмір: прибираємо зайві символи з бібліотек
find "$OUT/InkReader" -name '*.so*' -exec strip --strip-unneeded {} + 2>/dev/null || true
tar -C dist -cf - InkReader-linux | xz -9e -T0 > dist/InkReader-linux.tar.xz
ls -lh dist/InkReader-linux.tar.xz
