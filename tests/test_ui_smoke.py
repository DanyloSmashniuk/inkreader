"""Димовий тест інтерфейсу: програма запускається, відкриває книги й проходить основні дії.

Потрібні Kivy і графічний вивід (у CI це xvfb). Без Kivy тест пропускається.
Запуск вручну: xvfb-run -a pytest tests/test_ui_smoke.py
"""
import os

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
    for name in ('cycle_spacing cycle_margin toggle_font toggle_bold toggle_pages toggle_justify '
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
