#!/usr/bin/env bash
# Збірка APK для Android (target API 36, NDK 28c, 16 KB-вирівнювання, як вимагає Google Play).
# Збирає у ОКРЕМІЙ робочій теці (WORK), репозиторій не чіпає. Кеш у WORK/.buildozer лишається,
# тож повторні збірки швидкі. Результат: WORK/bin/*.apk
#
#   ./scripts/build_android.sh                  # робоча тека ~/inkreader-apk
#   WORK=~/mydir VENV=~/build311 ./scripts/build_android.sh
set -eu -o pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="${WORK:-$HOME/inkreader-apk}"
VENV="${VENV:-$HOME/build311}"        # venv з Python 3.11 (див. README)

[ -f "$VENV/bin/activate" ] || { echo "Нема venv: $VENV (python3.11 -m venv $VENV)"; exit 1; }
source "$VENV/bin/activate"
pip install -q -U buildozer cython==0.29.37

mkdir -p "$WORK"; rm -rf "$WORK/src" "$WORK/assets"
cp -r "$ROOT/src" "$ROOT/assets" "$ROOT/buildozer.spec" "$WORK"/
cd "$WORK"

# Баг python-for-android 2026.05.09: прямі посилання на android-колеса (requests -> charset_normalizer
# ...android_24_arm64_v8a.whl) ставляться хостовим pip без --platform, і pip їх відкидає.
# Додаємо --platform до тієї команди (ідемпотентно). Після першого запуску p4a уже склонований.
patch_p4a() {
  local bp="$WORK/.buildozer/android/platform/python-for-android/pythonforandroid/build.py"
  [ -f "$bp" ] || return 1
  python3 - "$bp" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
old = "\"install -v --target '{0}' --no-deps -r requirements.txt\""
new = "\"install -v --target '{0}' --no-deps --only-binary=:all: --platform android_24_arm64_v8a -r requirements.txt\""
if new in s: print("p4a: патч уже застосовано")
elif old in s: open(p, "w").write(s.replace(old, new)); print("p4a: патч застосовано")
else: print("УВАГА: потрібний рядок у build.py не знайдено (p4a змінився?)"); sys.exit(2)
PY
}
# p4a не перестворює venv, а після невдалої збірки pip у ньому пошкоджений: чистимо перед кожним запуском.
B="$WORK/.buildozer/android/platform/build-arm64-v8a/build"
clean() { rm -rf "$B/venv" "$B/python-installs" "$B/requirements.txt"; }

patch_p4a || echo "p4a ще не склонований: перший запуск може впасти на pip; запусти скрипт ще раз."
clean
if ! buildozer android debug 2>&1 | tee build.log | tail -n 25; then :; fi
if ! ls bin/*.apk >/dev/null 2>&1 || [ "$(ls -t bin/*.apk | head -1)" -ot "$ROOT/src/main.py" ]; then
  echo "APK не зібралась (або застаріла). Якщо це перший запуск, патч p4a застосовується тільки після"
  echo "його клонування: запусти скрипт ще раз."; exit 1
fi
APK="$WORK/$(ls -t bin/*.apk | head -1)"

# --- перевірка вимог Google Play
echo; echo "== Перевірка APK =="
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
unzip -q "$APK" 'lib/*' -d "$T/lib"
check() {   # рахує .so з вирівнюванням 4 КБ у теці
  local n=0 bad=0 f a
  while IFS= read -r f; do
    head -c4 "$f" | grep -q ELF || continue
    n=$((n+1)); a=$(readelf -lW "$f" | awk '/LOAD/{print $NF}' | sort -u | tr '\n' ' ')
    case "$a" in *0x1000*|*0x2000*) echo "  ПОГАНО $a $(basename "$f")"; bad=$((bad+1));; esac
  done < <(find "$1" -name '*.so')
  echo "  $2: бібліотек $n, з вирівнюванням 4 КБ: $bad"; [ "$bad" = 0 ]
}
ok=1
check "$T/lib" "lib/" || ok=0
mkdir "$T/bundle"; tar -xzf "$T"/lib/*/libpybundle.so -C "$T/bundle" 2>/dev/null && chmod -R u+rwX "$T/bundle" \
  && { check "$T/bundle" "Python-модулі" || ok=0; } || echo "  (libpybundle.so не вдалося розпакувати для перевірки)"
AAPT=$(ls "$HOME"/.buildozer/android/platform/android-sdk/build-tools/*/aapt 2>/dev/null | tail -1 || true)
[ -n "$AAPT" ] && "$AAPT" dump badging "$APK" | grep -oE "(targetSdkVersion|sdkVersion):'[0-9]+'" | sed 's/^/  /'
[ "$ok" = 1 ] && echo "OK: вирівнювання 16 КБ" || echo "УВАГА: є бібліотеки з вирівнюванням 4 КБ"
echo; echo "Готово: $APK"
