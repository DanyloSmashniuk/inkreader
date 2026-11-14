"""Android: системні відступи, «Відкрити за допомогою», системний вибір файлу (SAF).

Код імпортує jnius/android лише всередині методів, тому модуль безпечно імпортується на ПК.
"""
import logging
import os
import shutil
import time

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp

from book_loader import SUPPORTED_EXTS, guess_ext

log = logging.getLogger('inkreader')


class AndroidMixin:
    """Примішується до InkReaderApp; методи викликає лише Android-гілка застосунку."""

    def _android_build(self):
        """Android 15+/target API 35+: вікно малюється під рядком стану і панеллю навігації,
        тому екрани самі відступають від них (див. set_insets)."""
        Window.bind(size=lambda *a: Clock.schedule_once(self._apply_insets, 0.1))
        Clock.schedule_interval(self._apply_insets, 1.0)   # панелі можуть з'явитись/змінитись пізніше

    def _android_start(self):
        """Запускається з on_start: дозволи, «Відкрити за допомогою», екран не гасне."""
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
