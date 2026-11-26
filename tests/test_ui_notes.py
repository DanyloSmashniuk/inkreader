# ruff: noqa: F811  (фікстури app/shown імпортовано з test_ui_smoke і використано як аргументи)
"""Закладки, виділення тексту й список нотаток: логіка на справжньому екрані читання (xvfb) та
синтетичні дотики. Без Kivy тести пропускаються."""
import time

import pytest

pytest.importorskip('kivy')
from test_ui_smoke import app, shown, tick  # noqa: E402,F401  (фікстури)

import notes  # noqa: E402


@pytest.fixture
def long_paras(monkeypatch):
    """Робить тестову книгу довшою: кілька десятків сторінок."""
    import conftest
    monkeypatch.setattr(conftest, 'PARAS', conftest.PARAS * 40)


@pytest.fixture
def reading(long_paras, shown, epub_path):
    app = shown
    app.add_book(epub_path)
    tick(3)
    r = app.reader
    r.paginate(r.cur_pos())
    tick(2)
    assert len(r.pages) > 8 and r._words
    return app, r


def press(x, y, to=None, hold=1.0):
    """Довге натискання на (x, y), за потреби — протягнути до `to`. Повертає дотик до відпускання."""
    from kivy.clock import Clock
    from kivy.tests.common import UnitTestTouch
    t = UnitTestTouch(x, y)
    t.touch_down()
    end = time.time() + hold
    while time.time() < end:
        time.sleep(0.03)
        Clock.tick()
    if to:
        for i in range(1, 6):
            t.touch_move(x + (to[0] - x) * i / 5, y + (to[1] - y) * i / 5)
            Clock.tick()
    return t


def center(w):
    return (w[0] + w[2]) / 2, (w[1] + w[3]) / 2


def middle_words(r, count=3):
    """Індекси підряд `count` слів з одного рядка поблизу середини сторінки."""
    mid = r.height / 2
    cands = sorted(range(len(r._words) - count), key=lambda i: abs(center(r._words[i])[1] - mid))
    for i in cands:
        ys = {round(center(r._words[i + k])[1]) for k in range(count)}
        xs = [center(r._words[i + k])[0] for k in range(count)]
        if len(ys) == 1 and xs == sorted(xs) and 0.35 * r.width < xs[0] < 0.55 * r.width:
            return i
    raise AssertionError('немає підходящого рядка')


def test_bookmark_toggle_persist_and_relayout(reading):
    app, r = reading
    r._go(3, flash=False)
    assert not r.has_bookmark()
    r.toggle_bookmark()
    assert r.has_bookmark() and len(r.entry['bm']) == 1
    bm = r.entry['bm'][0]
    assert bm['txt'] and bm['pct'] > 0
    r._go(0, flash=False)
    assert not r.has_bookmark()
    r.go_to_pos((bm['b'], bm['o']))
    assert r.idx == 3 and r.has_bookmark()
    app.save_state()
    app._load_state()
    assert app.library[0]['bm'] == [bm]
    r.change_font(4)                                  # нова верстка: закладка лишається на своїй сторінці
    r.relayout()
    tick(2)
    assert r.has_bookmark()
    assert app._on_key(None, 98) is True              # B знімає закладку
    assert not r.has_bookmark() and r.entry['bm'] == []
    r.show_menu(True)
    assert r.btns['bookmark'].text.startswith('Закладка')


def test_long_press_select_highlight_tap_unhighlight(reading):
    app, r = reading
    i = middle_words(r)
    (x0, y0), (x2, y2) = center(r._words[i]), center(r._words[i + 2])
    t = press(x0, y0, to=(x2, y2))
    assert r.sel == (i, i + 2)                        # виділено три слова
    t.touch_up()
    tick(2)
    assert r.sel_bar.parent is not None and r.sel_btns['hl'].text == 'Виділити'
    want = ' '.join(r.book.blocks[w[4]][1][w[5]:w[6]] for w in r._words[i:i + 3])
    r.toggle_highlight()                              # кнопка «Виділити»
    tick(2)
    assert r.sel is None and r.sel_bar.parent is None
    assert [h['txt'] for h in r.entry['hl']] == [want]
    assert all(r._mark(w[4], w[5], w[6], n) == 1 for n, w in enumerate(r._words[i:i + 3], i))
    # дотик по збереженому виділенню (центр екрана) відкриває дії над ним
    from test_ui_smoke import drag
    drag(x0, y0, x0, y0, steps=1)
    tick(2)
    assert r.sel == (i, i + 2) and r.sel_btns['hl'].text == 'Зняти виділення'
    assert r.menu_visible is False
    r.toggle_highlight()
    assert r.entry['hl'] == [] and r.sel is None


def test_short_tap_without_highlight_still_opens_menu_and_clears_selection(reading):
    app, r = reading
    from test_ui_smoke import drag
    i = middle_words(r)
    x, y = center(r._words[i])
    t = press(x, y)
    t.touch_up()
    tick(2)
    assert r.sel == (i, i)
    drag(r.width * 0.5, r.height * 0.9, r.width * 0.5, r.height * 0.9, steps=1)   # дотик деінде знімає виділення
    tick(2)
    assert r.sel is None and r.menu_visible is False
    drag(r.width * 0.5, r.height * 0.9, r.width * 0.5, r.height * 0.9, steps=1)   # звичайний дотик по центру
    tick(2)
    assert r.menu_visible is True


def test_copy_selection_and_keys(reading, monkeypatch):
    app, r = reading
    import selection
    copied = []

    class Clip:
        @staticmethod
        def copy(text):
            copied.append(text)
    monkeypatch.setattr(selection, 'Clipboard', Clip)
    i = middle_words(r)
    (x0, y0), (x2, y2) = center(r._words[i]), center(r._words[i + 2])
    press(x0, y0, to=(x2, y2)).touch_up()
    tick(2)
    assert app._on_key(None, 99) is True              # C копіює виділене
    assert len(copied) == 1 and len(copied[0].split()) == 3 and r.sel is None
    press(x0, y0).touch_up()
    tick(2)
    assert r.sel is not None
    assert app._on_key(None, 27) is True and r.sel is None      # Esc знімає виділення


def test_page_turn_clears_selection(reading):
    app, r = reading
    i = middle_words(r)
    press(*center(r._words[i])).touch_up()
    tick(2)
    assert r.sel is not None
    r.next_page()
    assert r.sel is None and r.sel_bar.parent is None


def test_notes_popup_lists_jumps_and_deletes(reading):
    app, r = reading
    r._go(2, flash=False)
    r.toggle_bookmark()
    i = middle_words(r)
    notes.add_highlight(r.entry, [[r._words[i][4], r._words[i][5], r._words[i + 2][6]]], 'три слова')
    r._rebuild_hl()
    r._go(0, flash=False)
    r.show_notes()
    tick(2)
    assert r._modal_scroll is not None
    rows = [w for w in r._modal_scroll.walk() if hasattr(w, 'action')]
    assert len(rows) == 1                              # вкладка «Закладки»
    rows[0].on_tap()                                   # перехід до закладки
    tick(2)
    assert r.idx == 2 and r._modal_scroll is None
    r.show_notes('hl')
    tick(2)
    rows = [w for w in r._modal_scroll.walk() if hasattr(w, 'action')]
    assert len(rows) == 1
    rows[0].on_delete()                                # видалення виділення зі списку
    tick(2)
    assert r.entry['hl'] == [] and not r._hl_idx
    assert app._on_key(None, 27) is True and r._modal_scroll is None


def test_bookmarks_marked_on_seek_bar(reading):
    app, r = reading
    for page in (2, 5):
        r._go(page, flash=False)
        r.toggle_bookmark()
    r.show_menu(True)
    assert r.seek.marks == [2, 5]
    r.toggle_bookmark()                               # знімає закладку поточної (5-ї) сторінки
    assert r.seek.marks == [2]
    r.relayout()
    tick(2)
    r.show_menu(False)
    r.show_menu(True)
    assert len(r.seek.marks) == 1
