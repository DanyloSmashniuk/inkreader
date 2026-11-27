"""Димовий тест інтерфейсу: програма запускається, відкриває книги й проходить основні дії.

Потрібні Kivy і графічний вивід (у CI це xvfb). Без Kivy тест пропускається.
Запуск вручну: xvfb-run -a pytest tests/test_ui_smoke.py
"""
import os
import time

import pytest

pytest.importorskip('kivy')
os.environ.setdefault('KIVY_NO_ARGS', '1')


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('KIVY_HOME', str(tmp_path / 'kivy'))
    from kivy.core.window import Window

    import main
    a = main.InkReaderApp()
    data = tmp_path / 'data'
    data.mkdir()
    monkeypatch.setattr(type(a), 'user_data_dir', property(lambda s: str(data)))
    a.build()
    Window.size = (800, 1200)
    return a


def tick(n=2):
    from kivy.clock import Clock
    for _ in range(n):
        Clock.tick()


def test_read_and_navigate(app, fb2_path, epub_path):
    r = app.reader
    app.add_book(fb2_path)
    app.add_book(epub_path)
    tick()
    assert len(app.library) == 2 and app.sm.current == 'reader'
    r.paginate(r.cur_pos())
    assert r.pages
    n = len(r.pages)
    r.next_page()
    r.prev_page()
    r._go(n - 1, flash=False)
    r._go(0, flash=False)
    r.show_menu(True)
    r.show_menu(False)
    r.show_menu(True)
    r.change_font(2)
    for name in ('cycle_spacing cycle_margin toggle_font toggle_bold cycle_counter toggle_justify '
                 'toggle_hyph toggle_eink toggle_theme toggle_eink toggle_theme cycle_flash').split():
        getattr(r, name)()
        tick()
    r.relayout()
    r._do_flash()
    r.show_toc()
    tick()
    assert app._on_key(None, 27) is True            # Esc закриває зміст
    for key in (275, 276, 278, 279, 109, 109, 116, 27):
        app._on_key(None, key)
        tick()
    r.back()
    r.leave()
    tick()
    assert app.sm.current == 'library'


def test_library_and_state(app, fb2_path, tmp_path):
    from file_browser import browse_books
    lib = app.library_screen
    app.add_book(fb2_path)
    tick()
    app.show_library()
    lib.set_insets(0, 20, 0, 30)
    app.reader.set_insets(0, 20, 0, 30)
    lib.refresh()
    app.cycle_view()
    app.restyle()
    browse_books(app)
    tick()
    bad = tmp_path / 'bad.epub'
    bad.write_bytes(b'not a book')
    count = len(app.library)
    app.add_book(str(bad))                           # зіпсований файл: повідомлення, не збій
    tick()
    assert len(app.library) == count
    app.open_entry(app.library[0])
    tick()
    app.save_state()
    app._load_state()
    assert len(app.library) == count
    app.remove_entry(app.library[0])
    assert len(app.library) == count - 1


def test_import_from_android_uri(app, fb2_path):
    """Імпорт content:// через підставні Java-об'єкти: без дубліката, тип за вмістом."""
    class Cur:
        def moveToFirst(self): return True
        def getColumnIndex(self, c): return {'_display_name': 0, '_size': 1}[c]
        def getString(self, i): return 'Нічна пошта'         # без розширення
        def isNull(self, j): return False
        def getLong(self, j): return os.path.getsize(fb2_path)
        def close(self): pass

    class Pfd:
        def detachFd(self): return os.open(fb2_path, os.O_RDONLY)

    class Resolver:
        def query(self, *a): return Cur()
        def openFileDescriptor(self, uri, mode): return Pfd()

    class Activity:
        def getContentResolver(self): return Resolver()

    class Uri:
        def getLastPathSegment(self): return 'x'

    app._import_uri(Uri(), Activity())
    tick()
    assert len(app.library) == 1
    entry = app.library[0]
    assert entry['path'].endswith('.fb2') and entry['src'].startswith('uri:')
    app.sm.current = 'library'
    app._import_uri(Uri(), Activity())                    # повторно: той самий запис
    tick()
    assert len(app.library) == 1 and app.sm.current == 'reader'


# ------------------------------------------------------------------ дотики (синтетичні)

def drag(x0, y0, x1, y1, steps=8, hold=0):
    """Палець: торкнутися (x0, y0), провести до (x1, y1), відпустити. Координати вікна."""
    from kivy.clock import Clock
    from kivy.tests.common import UnitTestTouch
    t = UnitTestTouch(x0, y0)
    t.touch_down()
    for _ in range(12):                     # ScrollView передає дотик дітям після короткої паузи
        time.sleep(0.02)
        Clock.tick()
    for i in range(1, steps + 1):
        t.touch_move(x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)
        Clock.tick()
    for _ in range(hold):
        Clock.tick()
    t.touch_up()
    Clock.tick()


@pytest.fixture
def shown(app):
    from kivy.core.window import Window
    Window.add_widget(app.sm)
    Window.size = (800, 1200)
    tick(3)
    yield app
    Window.remove_widget(app.sm)


def row_center(app, i=0):
    rows = [w for w in app.library_screen.listbox.children if hasattr(w, 'action')][::-1]
    r = rows[i]
    cx, cy = r.to_window(r.center_x, r.center_y)             # координати вікна (враховують прокрутку)
    return r, cx, cy


def test_swipe_row_reveals_delete_and_removes(shown, fb2_path, epub_path):
    app = shown
    app.add_book(fb2_path)
    app.add_book(epub_path)
    tick()
    app.show_library()
    tick(3)
    assert len(app.library) == 2
    row, cx, cy = row_center(app, 0)
    drag(cx + 200, cy, cx - 100, cy)                    # свайп ліворуч
    assert row.is_open and len(app.library) == 2
    drag(cx + 200, cy, cx - 50, cy)                     # інший рядок/той самий: свайп уже відкритого
    row, cx, cy = row_center(app, 0)
    assert row.is_open
    bx, by = row.to_window(row.right - 40, row.center_y)
    drag(bx, by, bx, by, steps=1)                    # дотик по кнопці «Видалити»
    tick(2)
    assert len(app.library) == 1


def test_swipe_row_tap_opens_and_short_drag_closes(shown, fb2_path, epub_path):
    app = shown
    app.add_book(fb2_path)
    app.add_book(epub_path)
    app.show_library()
    tick(3)
    row, cx, cy = row_center(app, 0)
    drag(cx + 100, cy, cx + 100, cy, steps=1)           # короткий дотик відкриває книгу
    tick(2)
    assert app.sm.current == 'reader'
    app.show_library()
    tick(3)
    row, cx, cy = row_center(app, 0)
    drag(cx + 200, cy, cx + 150, cy)                    # малий свайп: рядок лишається закритим
    assert not row.is_open and app.sm.current == 'library'
    drag(cx + 200, cy, cx - 100, cy)
    assert row.is_open
    _row2, x2, y2 = row_center(app, 1)
    drag(x2, y2, x2, y2, steps=1)                       # дотик по іншому рядку закриває перший
    assert not row.is_open and app.sm.current == 'library'     # і книгу не відкриває
