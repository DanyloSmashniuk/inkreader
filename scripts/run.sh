#!/usr/bin/env bash
# Запуск із вихідного коду (для розробки): ./scripts/run.sh [книга.epub]
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 src/main.py "$@"
