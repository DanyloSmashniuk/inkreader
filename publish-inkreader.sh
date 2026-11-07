#!/usr/bin/env bash
# Публікація InkReader на GitHub: код, релізні файли та GitHub Pages.
set -Eeuo pipefail

OWNER="DanyloSmashniuk"
REPO_NAME="inkreader"
REPO="$OWNER/$REPO_NAME"
BRANCH="main"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(sed -n 's/^version *= *//p' "$ROOT/buildozer.spec" | head -n1 | tr -d '[:space:]')"
[[ -n "$VERSION" ]] || { echo "ПОМИЛКА: не знайшов version у buildozer.spec" >&2; exit 1; }
TAG="v$VERSION"
RELEASE_DIR="$HOME/release-inkreader"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\nПОМИЛКА: %s\n' "$*" >&2; exit 1; }

# Використання:
#   ./publish-inkreader.sh --check            лише перевірка, нічого не публікує
#   ./publish-inkreader.sh [app.apk linux.tar.xz]   публікація (шляхи необовʼязкові)
CHECK_ONLY=0
if [[ "${1:-}" == "--check" ]]; then CHECK_ONLY=1; shift; fi
APK_INPUT="${1:-}"
TAR_INPUT="${2:-}"

command -v git >/dev/null || die "Git не встановлений: sudo pacman -S git"
command -v gh  >/dev/null || die "GitHub CLI не встановлений: sudo pacman -S github-cli"
command -v curl >/dev/null || die "curl не встановлений: sudo pacman -S curl"

# Перевіряємо потрібні файли саме у структурі цього репозиторію.
[[ -f "$ROOT/README.md" && -f "$ROOT/LICENSE" && -f "$ROOT/docs/index.html" && -f "$ROOT/buildozer.spec" ]] \
  || die "Не схоже на корінь InkReader. Запусти скрипт із теки репозиторію."

say "Перевірка релізних збірок"
if [[ -z "$APK_INPUT" ]]; then
  for f in "$ROOT"/bin/*.apk "$HOME"/inkreader-apk/bin/*.apk; do
    [[ -f "$f" ]] && { APK_INPUT="$f"; break; }
  done
fi
if [[ -z "$TAR_INPUT" ]]; then
  for f in "$ROOT/dist/InkReader-linux.tar.xz" "$HOME/Завантажене/InkReader-linux.tar.xz" "$HOME/Downloads/InkReader-linux.tar.xz"; do
    [[ -f "$f" ]] && { TAR_INPUT="$f"; break; }
  done
fi
[[ -n "$APK_INPUT" && -f "$APK_INPUT" ]] || die "APK не знайдено. Спочатку збудуй Android: buildozer android debug (очікується bin/*.apk), або передай шлях першим аргументом."
[[ -n "$TAR_INPUT" && -f "$TAR_INPUT" ]] || die "Linux-архів не знайдено. Виконай ./scripts/build_linux.sh та ./scripts/package_linux.sh або передай шлях другим аргументом."

# Захист від застарілих збірок: файли в релізі мають бути новішими за код.
newest_src="$(find "$ROOT/src" -type f \( -name '*.py' -o -name '*.png' \) -printf '%T@\n' | sort -n | tail -n1)"
newest_src="${newest_src%.*}"
stale() { [[ "$(stat -c %Y "$1")" -lt "$newest_src" ]]; }
PROBLEMS=0
if stale "$APK_INPUT"; then
  printf '\033[1;31m✗\033[0m APK старіша за код у src/. Перезбери: buildozer android debug\n'; PROBLEMS=1
else
  printf '\033[1;32m✓\033[0m APK новіша за код: %s\n' "$APK_INPUT"
fi
if stale "$TAR_INPUT"; then
  printf '\033[1;31m✗\033[0m Linux-архів старіший за код у src/. Перезбери: ./scripts/build_linux.sh && ./scripts/package_linux.sh\n'; PROBLEMS=1
else
  printf '\033[1;32m✓\033[0m Linux-архів новіший за код: %s\n' "$TAR_INPUT"
fi
for pat in 'elif x < 0.3' 'def scroll_by'; do
  if grep -q "$pat" "$ROOT/src/main.py"; then printf '\033[1;32m✓\033[0m main.py містить «%s»\n' "$pat"
  else printf '\033[1;31m✗\033[0m main.py без «%s» (стара версія?)\n' "$pat"; PROBLEMS=1; fi
done
if grep -q 'org.example' "$ROOT/buildozer.spec"; then
  printf '\033[1;33m!\033[0m package.domain = org.example (заглушка). Після публікації змінити буде не можна без втрати оновлень.\n'
fi
printf '\033[1;32m✓\033[0m Версія %s, тег %s\n' "$VERSION" "$TAG"
if (( PROBLEMS )) && [[ "${FORCE:-0}" != "1" ]]; then
  die "Є проблеми вище. Виправ їх або запусти з FORCE=1, якщо це свідомо."
fi
if (( CHECK_ONLY )); then say "Перевірку завершено, нічого не опубліковано"; exit 0; fi

mkdir -p "$RELEASE_DIR"
install -m 0644 "$APK_INPUT" "$RELEASE_DIR/InkReader.apk"
install -m 0644 "$TAR_INPUT" "$RELEASE_DIR/InkReader-linux.tar.xz"

# Оновлюємо тільки конкретні поля, які справді є у файлах цього проєкту.
say "Налаштування посилань у README та сайті"
sed -i \
  -e "s#https://USERNAME.github.io/inkreader/#https://${OWNER}.github.io/${REPO_NAME}/#g" \
  -e "s#../../releases/latest#https://github.com/${REPO}/releases/latest#g" \
  "$ROOT/README.md"
sed -i \
  -e "s#var REPO = \"USERNAME/inkreader\";#var REPO = \"${REPO}\";#" \
  "$ROOT/docs/index.html"

grep -Fq "var REPO = \"$REPO\";" "$ROOT/docs/index.html" \
  || die "Не вдалося оновити REPO у docs/index.html. Перевір рядок REPO вручну."

say "Авторизація GitHub"
gh auth status >/dev/null 2>&1 || gh auth login -h github.com -p https -w
gh auth setup-git

cd "$ROOT"
if [[ ! -d .git ]]; then
  git init -b "$BRANCH"
fi
CURRENT_BRANCH="$(git branch --show-current)"
if [[ "$CURRENT_BRANCH" != "$BRANCH" ]]; then
  git branch -M "$BRANCH"
fi

# Не перезаписуємо випадково чужий origin.
if git remote get-url origin >/dev/null 2>&1; then
  ORIGIN="$(git remote get-url origin)"
  case "$ORIGIN" in
    *"github.com:${REPO}.git"|*"github.com/${REPO}.git") ;;
    *) die "У origin вже інший репозиторій: $ORIGIN. Перевір його перед публікацією." ;;
  esac
else
  git remote add origin "https://github.com/${REPO}.git"
fi

say "Створення GitHub-репозиторію, якщо його ще немає"
if ! gh repo view "$REPO" >/dev/null 2>&1; then
  gh repo create "$REPO" --public
fi
gh repo edit "$REPO" \
  --description "Читалка EPUB і FB2 з режимом «електронні чорнила». Linux і Android." \
  --homepage "https://${OWNER}.github.io/${REPO_NAME}/" \
  --add-topic epub --add-topic fb2 --add-topic ebook-reader --add-topic kivy --add-topic e-ink >/dev/null 2>&1 || true

git add README.md docs .github src assets scripts tests requirements.txt requirements-dev.txt pyproject.toml buildozer.spec .gitignore LICENSE publish-inkreader.sh
if ! git diff --cached --quiet; then
  git commit -m "InkReader $VERSION"
else
  say "Змін у Git немає — новий commit не потрібен"
fi

git push -u origin "$BRANCH"

say "Публікація релізу $TAG"
NOTES_FILE="$(mktemp)"
cat > "$NOTES_FILE" <<NOTES
Перша публічна версія InkReader: читалка EPUB і FB2 з режимом «електронні чорнила».

**Android** (7.0+, arm64): завантажте \`InkReader.apk\`, відкрийте файл і дозвольте встановлення з цього джерела.
**Linux** (x86_64): розпакуйте \`InkReader-linux.tar.xz\` і запустіть \`./install.sh\`.
NOTES
if gh release view "$TAG" -R "$REPO" >/dev/null 2>&1; then
  gh release upload "$TAG" "$RELEASE_DIR/InkReader.apk" "$RELEASE_DIR/InkReader-linux.tar.xz" -R "$REPO" --clobber
else
  gh release create "$TAG" "$RELEASE_DIR/InkReader.apk" "$RELEASE_DIR/InkReader-linux.tar.xz" \
    -R "$REPO" --title "InkReader $VERSION" --notes-file "$NOTES_FILE"
fi

say "Увімкнення GitHub Pages із гілки main та папки /docs"
if gh api "repos/$REPO/pages" >/dev/null 2>&1; then
  echo "GitHub Pages уже налаштовано. Перевір налаштування в репозиторії."
else
  gh api -X POST "repos/$REPO/pages" \
    -f "source[branch]=$BRANCH" -f "source[path]=/docs" >/dev/null \
    || echo "Pages не вдалося ввімкнути автоматично. У Settings → Pages вибери Deploy from a branch → main → /docs."
fi

printf '\nГотово!\n'
printf 'Репозиторій: https://github.com/%s\n' "$REPO"
printf 'Сайт:        https://%s.github.io/%s/\n' "$OWNER" "$REPO_NAME"
printf 'APK:         https://github.com/%s/releases/latest/download/InkReader.apk\n' "$REPO"
printf 'Linux:       https://github.com/%s/releases/latest/download/InkReader-linux.tar.xz\n' "$REPO"
printf '\nРелізні файли взято з:\n  APK:  %s\n  TAR:  %s\n' "$APK_INPUT" "$TAR_INPUT"
