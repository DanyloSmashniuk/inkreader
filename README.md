<div align="center">

<img src="assets/icon-256.png" width="96" alt="InkReader">

# InkReader

**Читалка EPUB і FB2 з режимом «електронні чорнила».**
Без реклами, акаунта та інтернету. Linux і Android.

[Завантажити](https://github.com/DanyloSmashniuk/inkreader/releases/latest) · [Сайт](https://DanyloSmashniuk.github.io/inkreader/)

<img src="assets/screenshots/e-ink.png" width="19%" alt="Режим e-ink"> <img src="assets/screenshots/dark.png" width="19%" alt="Темна тема"> <img src="assets/screenshots/contents.png" width="19%" alt="Зміст"> <img src="assets/screenshots/menu.png" width="19%" alt="Меню"> <img src="assets/screenshots/library.png" width="19%" alt="Бібліотека">

</div>

## Можливості

- **E-ink режим.** Чорний текст на кольорі паперу, без градієнтів і блиску. Підсилені сірі кольори, повне оновлення екрана кожні 1, 3, 6, 10 або 20 сторінок. Є й звичайний кольоровий режим, світла та темна теми.
- **Справжні сторінки.** Номери беруться зі сторінок паперового видання (page-list в EPUB). Якщо їх немає, рахуються умовні сторінки по 1800 знаків. Внизу завжди видно відсоток і повзунок прогресу.
- **Розділи з самого документа.** Зміст береться з навігації EPUB або з секцій FB2. Якщо його немає, читалка сама знаходить заголовки.
- **Охайний текст.** Вирівнювання по ширині, переноси слів (кирилиця за правилами складів, англійська через `pyphen`), без «вдів» і «сиріт». Вбудований шрифт Liberation Serif із жирним накресленням.
- **Чистка «кривих» файлів.** Зайві пробіли й невидимі символи, жорстко розбиті рядки, дублі заголовків, надто довгі абзаци.
- **Бібліотека** з обкладинками, позиція читання зберігається для кожної книги.
- **Керування.** Тап по краях гортає сторінки, тап по центру відкриває меню, свайп теж гортає. На комп'ютері також працюють клавіатура та колесо миші.

Формати: EPUB, FB2, FB2.ZIP.

## Встановлення

Готові збірки лежать у [Releases](https://github.com/DanyloSmashniuk/inkreader/releases/latest).

**Android** (7.0+, arm64): завантажте `InkReader.apk`, відкрийте файл і дозвольте встановлення з цього джерела.

**Linux** (x86_64):

```bash
tar -xf InkReader-linux.tar.xz
cd InkReader-linux && ./install.sh
```

Скрипт поставить програму в `~/.local/share/InkReader` і додасть ярлик у меню. Також можна просто запустити `InkReader/InkReader` без встановлення. Книги відкриваються й через «Відкрити за допомогою» у файловому менеджері.

## Клавіші (комп'ютер)

| Дія | Клавіші |
| --- | --- |
| Наступна сторінка | `Space`, `Enter`, `PgDn`, `→`, `↓` |
| Попередня сторінка | `Backspace`, `PgUp`, `←`, `↑` |
| Початок / кінець книги | `Home` / `End` |
| Зміст | `T` або `C` |
| Меню | `M` |
| Повний екран | `F11` |
| Назад до бібліотеки | `Esc` |

## Запуск із вихідного коду

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
./scripts/run.sh                 # або ./scripts/run.sh книга.epub
```

Дані (книги, обкладинки, стан) зберігаються в `~/.config/inkreader/`.

## Збірка

**Linux** (PyInstaller):

```bash
./scripts/build_linux.sh         # dist/InkReader/InkReader
./scripts/package_linux.sh       # dist/InkReader-linux.tar.xz
```

**Android** (buildozer, потрібні Linux та JDK 17):

```bash
pip install buildozer
buildozer android debug          # bin/*.apk
```

Збирайте з теки, шлях до якої містить лише латиницю: інакше Java може не знайти файли. Налаштування лежать у [`buildozer.spec`](buildozer.spec).

## Структура

```
src/
  main.py          інтерфейс (Kivy): бібліотека, читання, меню, клавіші
  book_loader.py   розбір EPUB і FB2: текст, розділи, сторінки, обкладинки
  textfix.py       чистка тексту й нормалізація блоків
  hyph.py          переноси слів
  typeset.py       верстка: рядки, вирівнювання, розбиття на сторінки
  fontdata.py      вбудований шрифт Liberation Serif (SIL OFL 1.1)
docs/              сайт (GitHub Pages)
scripts/           запуск, збірка й пакування
tests/             тести розбору книг і тексту
assets/            іконки та знімки екрана
```

Книга після розбору це список блоків `(тип, текст)`, де тип: `h` заголовок, `p` абзац, `v` вірш, `s` розділювач, `i` картинка. Верстка перетворює їх на сторінки, а `main.py` лише малює готові рядки.

## Тести

```bash
pip install -r requirements-dev.txt
pytest
```

## Сайт

Папка `docs/` публікується через GitHub Pages (Settings → Pages → Deploy from a branch → `main` → `/docs`). Кнопка «Завантажити» на сайті сама визначає систему й бере файл з останнього релізу, тож у релізі файли мають називатись `InkReader.apk` і `InkReader-linux.tar.xz`. Свій логін вказується в рядку `REPO` у `docs/index.html`.

## Ліцензія

Код поширюється за ліцензією [MIT](LICENSE). Вбудований шрифт Liberation Serif поширюється за ліцензією SIL OFL 1.1.
