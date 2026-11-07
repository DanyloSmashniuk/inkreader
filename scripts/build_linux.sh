#!/usr/bin/env bash
# Збирає InkReader для Linux у dist/InkReader (PyInstaller). Потрібен лише python3 з venv.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv-build
. .venv-build/bin/activate
pip install --upgrade pip
pip install kivy plyer pyphen pyinstaller
pyinstaller --noconfirm --clean --name InkReader --windowed \
    --paths src --collect-submodules plyer \
    --add-data src/icon.png:. --exclude-module tkinter \
    src/main.py
echo
echo "Готово: $(pwd)/dist/InkReader/InkReader"
