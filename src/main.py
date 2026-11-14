"""InkReader: читалка EPUB/FB2 з режимом «електронні чорнила» (Kivy).

Верстку сторінок робить typeset.py, чистку «кривих» файлів — textfix.py,
переноси слів — hyph.py. Тут: інтерфейс, малювання сторінки, налаштування.
"""
import json
import logging
import os
import shutil
import sys
import time

os.environ.setdefault('SDL_VIDEO_X11_WMCLASS', 'InkReader')   # збігається з StartupWMClass ярлика

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import NoTransition, ScreenManager
from kivy.utils import platform

import fonts
from book_loader import SUPPORTED_EXTS, guess_ext, load_book
from config import DATA_VERSION, DEFAULT_PREFS, VIEWS, palette
from file_browser import browse_books
from library import LibraryScreen
from reader import ReaderScreen
from widgets import (
    ICON_PATH,
)

log = logging.getLogger('inkreader')

# ------------------------------------------------------------------- застосунок

class InkReaderApp(App):
    title = 'InkReader'
    icon = ICON_PATH

    @property
    def colors(self):
        return palette(self.prefs)

    def build(self):
        self.books_dir = os.path.join(self.user_data_dir, 'books')
        os.makedirs(self.books_dir, exist_ok=True)
        self.state_path = os.path.join(self.user_data_dir, 'state.json')
        self.prefs = dict(DEFAULT_PREFS)
        self.library = []
        self._load_state()
        self.desktop = platform in ('linux', 'win', 'macosx')
        self.prefs.pop('win', None)     # старі версії зберігали розмір вікна — це могло виводити його за екран
        fonts.setup_fonts(self.user_data_dir)

        self.sm = ScreenManager(transition=NoTransition())   # жодної анімації
        self.library_screen = LibraryScreen(self, name='library')
        self.reader = ReaderScreen(self, name='reader')
        self.sm.add_widget(self.library_screen)
        self.sm.add_widget(self.reader)
        Window.bind(on_keyboard=self._on_key)
        self.show_library()
        # Android 15+/target API 35+: вікно малюється під рядком стану і панеллю навігації,
        # тому екрани самі відступають від них (див. set_insets)
        if platform == 'android':
            Window.bind(size=lambda *a: Clock.schedule_once(self._apply_insets, 0.1))
            Clock.schedule_interval(self._apply_insets, 1.0)   # панелі можуть з'явитись/змінитись пізніше
        return self.sm

    def _system_insets(self):
        """(left, top, right, bottom) у пікселях: рядок стану, навігація, виріз екрана."""
        from jnius import autoclass
        act = autoclass('org.kivy.android.PythonActivity').mActivity
        ins = act.getWindow().getDecorView().getRootWindowInsets()
        if ins is None:
            return None
        Build = autoclass('android.os.Build$VERSION')
        if Build.SDK_INT >= 30:
            Type = autoclass('android.view.WindowInsets$Type')
            i = ins.getInsets(Type.systemBars() | Type.displayCutout())
            return i.left, i.top, i.right, i.bottom
        return (ins.getSystemWindowInsetLeft(), ins.getSystemWindowInsetTop(),
                ins.getSystemWindowInsetRight(), ins.getSystemWindowInsetBottom())

    def _apply_insets(self, *_):
        try:
            v = self._system_insets()
        except Exception as e:  # noqa: BLE001 — jnius кидає різні Java-винятки
            log.debug('відступи системних панелей недоступні: %s', e)
            return
        if v is None:
            return
        l, t, r, b = v
        if b:
            b += dp(10)                         # невеликий запас: підвал не торкається панелі навігації
        ins = (l, t, r, b)
        if ins != getattr(self, '_insets', None):
            self._insets = ins
            for scr in (self.library_screen, self.reader):
                scr.set_insets(*ins)

    def on_start(self):
        files = [a for a in sys.argv[1:] if a.lower().endswith(SUPPORTED_EXTS) and os.path.isfile(a)]
        if files:                                  # «Відкрити за допомогою» з файлового менеджера
            Clock.schedule_once(lambda dt: self.open_path(files[0]), 0.3)
        if platform == 'android':
            try:
                from android.permissions import Permission, request_permissions
                request_permissions([Permission.READ_EXTERNAL_STORAGE])
            except (ImportError, AttributeError) as e:
                log.warning('запит дозволу на читання не виконано: %s', e)
            try:                                   # книга, відкрита з файлового менеджера
                from android import activity
                activity.bind(on_new_intent=lambda it: Clock.schedule_once(
                    lambda dt: self._handle_intent(it), 0))
                Clock.schedule_once(lambda dt: self._handle_intent(), 0.5)
            except ImportError as e:
                log.warning('відкриття з файлового менеджера недоступне: %s', e)
            try:                                   # екран не гасне під час читання
                from android.runnable import run_on_ui_thread
                from jnius import autoclass

                @run_on_ui_thread
                def keep_on():
                    act = autoclass('org.kivy.android.PythonActivity').mActivity
                    act.getWindow().addFlags(128)
                keep_on()
            except Exception as e:  # noqa: BLE001 — jnius кидає різні Java-винятки
                log.warning('не вдалося залишити екран увімкненим: %s', e)

    def on_pause(self):
        self.save_state()
        return True

    # ---------- «Відкрити за допомогою» на Android
    def _handle_intent(self, intent=None):
        try:
            from jnius import autoclass
            act = autoclass('org.kivy.android.PythonActivity').mActivity
            intent = intent or act.getIntent()
            if intent is None or intent.getAction() != 'android.intent.action.VIEW':
                return
            uri = intent.getData()
            if uri is None:
                return
            if uri.getScheme() == 'file':
                path = uri.getPath()
                if path and os.path.isfile(path):
                    try:
                        open(path, 'rb').close()
                        self.open_path(path)
                        return
                    except OSError:
                        pass                       # немає прямого доступу — читаємо через систему
            self._import_uri(uri, act)
        except Exception as e:  # noqa: BLE001 — межа інтерфейсу: показуємо помилку, а не падаємо
            log.exception('не вдалося обробити intent')
            self.message('Не вдалося відкрити файл', repr(e))

    def _import_uri(self, uri, act):
        """content://… → копія в теці застосунку → відкрити (з тим самим прогресом, якщо книга вже є)."""
        cr = act.getContentResolver()
        name, size = None, -1
        try:
            cur = cr.query(uri, None, None, None, None)
            if cur is not None:
                try:
                    if cur.moveToFirst():
                        i = cur.getColumnIndex('_display_name')
                        if i >= 0:
                            name = cur.getString(i)
                        j = cur.getColumnIndex('_size')
                        if j >= 0 and not cur.isNull(j):
                            size = cur.getLong(j)
                finally:
                    cur.close()
        except Exception as e:  # noqa: BLE001 — ім'я й розмір необов'язкові, jnius кидає різні винятки
            log.debug("не вдалося прочитати ім'я та розмір файлу: %s", e)
        name = os.path.basename(name or uri.getLastPathSegment() or 'book').replace(os.sep, '_')
        key = 'uri:%s:%s' % (name, size)
        for e in self.library:
            if e.get('src') == key and os.path.exists(e['path']):
                self.open_entry(e)
                return
        dst = os.path.join(self.books_dir, '%d_%s' % (int(time.time() * 1000), name))
        pfd = cr.openFileDescriptor(uri, 'r')
        with os.fdopen(pfd.detachFd(), 'rb') as f, open(dst, 'wb') as out:
            shutil.copyfileobj(f, out, 1 << 20)
        if not dst.lower().endswith(SUPPORTED_EXTS):
            ext = guess_ext(dst)
            if not ext:
                os.remove(dst)
                self.message('Не вдалося відкрити книгу', 'Підтримуються лише EPUB та FB2')
                return
            os.rename(dst, dst + ext)
            dst += ext
        self.add_book(dst, copied=True, key=key)

    def on_stop(self):
        self.save_state()

    # ---------- стан
    def _load_state(self):
        try:
            with open(self.state_path, encoding='utf-8') as f:
                data = json.load(f)
            self.prefs.update(data.get('prefs', {}))
            self.library = [e for e in data.get('library', []) if os.path.exists(e['path'])]
        except FileNotFoundError:
            pass                                       # перший запуск
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            log.warning('стан не прочитано, починаємо з нуля: %s', e)
        if self.prefs.get('theme') in ('paper', 'eink', 'night'):    # старі версії
            self.prefs['theme'] = 'dark' if self.prefs['theme'] == 'night' else 'light'
            self.prefs['eink'] = True
        for k, v in DEFAULT_PREFS.items():
            self.prefs.setdefault(k, v)

    def save_state(self):
        self.library.sort(key=lambda e: e.get('t', 0), reverse=True)
        try:
            with open(self.state_path, 'w', encoding='utf-8') as f:
                json.dump({'prefs': self.prefs, 'library': self.library}, f, ensure_ascii=False)
        except (OSError, TypeError, ValueError) as e:
            log.warning('стан не збережено: %s', e)

    # ---------- вигляд
    def restyle(self):
        Window.clearcolor = self.colors[0]
        self.library_screen.refresh()
        self.reader.apply_theme()

    def cycle_view(self):
        p = self.prefs
        cur = (p['eink'], p['theme'])
        i = VIEWS.index(cur) if cur in VIEWS else 0
        p['eink'], p['theme'] = VIEWS[(i + 1) % len(VIEWS)]
        self.save_state()
        self.restyle()

    def make_popup(self, title, content, size_hint=(0.88, 0.4)):
        bg, fg = self.colors
        return Popup(title=title, content=content, size_hint=size_hint, background='',
                     background_color=bg, title_color=fg, separator_color=fg,
                     overlay_color=(0, 0, 0, 0.35), auto_dismiss=True)

    def message(self, title, text):
        lbl = Label(text=text, halign='center', color=self.colors[1])
        lbl.bind(size=lambda w, s: setattr(w, 'text_size', (s[0] - 20, None)))
        self.make_popup(title, lbl).open()

    # ---------- екрани
    def show_library(self):
        self.library_screen.refresh()
        self.sm.current = 'library'
        Window.clearcolor = self.colors[0]

    # ---------- книги
    def cache_dir(self, path):
        return os.path.join(self.user_data_dir, 'cache', os.path.basename(path))

    def pick_file(self):
        if platform == 'android':
            try:
                self._android_pick()
                return
            except Exception as e:  # noqa: BLE001 — jnius кидає різні Java-винятки; є запасний вибір
                log.warning('системний вибір файлу недоступний: %s', e)
        browse_books(self)

    PICK_CODE = 7311

    def _android_pick(self):
        """Системний вибір файлу (Google Files, Xiaomi…): відповідь — content://, її читаємо через систему."""
        from android import activity
        from jnius import autoclass
        Intent = autoclass('android.content.Intent')
        act = autoclass('org.kivy.android.PythonActivity').mActivity
        if not getattr(self, '_pick_bound', False):
            activity.bind(on_activity_result=self._on_activity_result)
            self._pick_bound = True
        it = Intent(Intent.ACTION_OPEN_DOCUMENT)
        it.addCategory(Intent.CATEGORY_OPENABLE)
        it.setType('*/*')
        act.startActivityForResult(it, self.PICK_CODE)

    def _on_activity_result(self, request, result, intent):
        if request != self.PICK_CODE or result != -1 or intent is None:
            return
        uri = intent.getData()
        if uri is not None:
            Clock.schedule_once(lambda dt: self._open_uri(uri), 0)

    def _open_uri(self, uri):
        try:
            from jnius import autoclass
            self._import_uri(uri, autoclass('org.kivy.android.PythonActivity').mActivity)
        except Exception as e:  # noqa: BLE001 — межа інтерфейсу: показуємо помилку, а не падаємо
            log.exception('не вдалося відкрити вибраний файл')
            self.message('Не вдалося відкрити файл', repr(e))

    def _picked(self, selection):
        if selection and selection[0]:
            self.add_book(selection[0])

    def open_path(self, src):
        src = os.path.abspath(src)
        for e in self.library:
            if e.get('src') == src and os.path.exists(e['path']):
                self.open_entry(e)
                return
        self.add_book(src)

    def add_book(self, src, copied=False, key=None):
        """copied=True: src уже лежить у теці застосунку (імпорт з content://), key — ідентифікатор для «src»."""
        if copied:
            dst = src
        else:
            dst = os.path.join(self.books_dir, '%d_%s' % (int(time.time() * 1000),
                                                          os.path.basename(src)))
            try:
                shutil.copy2(src, dst)
            except OSError as e:
                log.warning('не вдалося скопіювати книгу, читаємо на місці: %s', e)
                dst = src
        try:
            book = load_book(dst, self.cache_dir(dst))
        except Exception as e:  # noqa: BLE001 — межа інтерфейсу: формат файлу довільний, показуємо причину
            log.warning('не вдалося відкрити книгу %s: %s', dst, e)
            if copied or dst != src:
                try:
                    os.remove(dst)
                except OSError:
                    pass
            self.message('Не вдалося відкрити книгу', str(e))
            return
        entry = {'path': dst, 'title': book.title, 'author': book.author,
                 'cover': book.cover, 'block': 0, 'off': 0, 'pct': 0,
                 't': time.time(), 'v': DATA_VERSION, 'src': key or os.path.abspath(src)}
        self.library.insert(0, entry)
        self.save_state()
        self.open_entry(entry, book)

    def open_entry(self, entry, book=None):
        try:
            book = book or load_book(entry['path'], self.cache_dir(entry['path']))
        except Exception as e:  # noqa: BLE001 — межа інтерфейсу: формат файлу довільний, показуємо причину
            log.warning('не вдалося відкрити книгу %s: %s', entry['path'], e)
            self.message('Не вдалося відкрити книгу', str(e))
            return
        if entry.get('v') != DATA_VERSION:      # нормалізація змінила нумерацію блоків
            entry['block'], entry['off'], entry['pct'], entry['v'] = 0, 0, 0, DATA_VERSION
        if book.cover:
            entry['cover'] = book.cover
        entry['t'] = time.time()
        self.reader.open(entry, book)
        self.sm.current = 'reader'
        Window.clearcolor = self.colors[0]

    def remove_entry(self, entry):
        if entry in self.library:
            self.library.remove(entry)
            if entry['path'].startswith(self.books_dir):
                try:
                    os.remove(entry['path'])
                except OSError:
                    pass
                shutil.rmtree(self.cache_dir(entry['path']), ignore_errors=True)
            self.save_state()
            self.library_screen.refresh()

    # ---------- клавіші (кнопка «Назад», апаратні кнопки гортання, клавіатура)
    def _on_key(self, _window, key, *_args):
        return self.sm.current == 'reader' and self.reader.handle_key(key)


if __name__ == '__main__':
    InkReaderApp().run()
