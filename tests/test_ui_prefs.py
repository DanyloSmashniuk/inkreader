# ruff: noqa: F811  (фікстури app/shown імпортовано з test_ui_smoke і використано як аргументи)
"""Нижнє меню з одним рядком, вікно «Налаштування» і режими підпису прогресу (xvfb)."""
import json

import pytest

pytest.importorskip('kivy')
from test_ui_notes import long_paras, reading  # noqa: E402,F401  (фікстури)
from test_ui_smoke import app, shown, tick  # noqa: E402,F401

from config import MARGIN_NAMES  # noqa: E402


def buttons(widget):
    from kivy.uix.button import Button
    return [w for w in widget.walk() if isinstance(w, Button)]


def test_bottom_bar_is_one_row(reading):
    app, r = reading
    r.show_menu(True)
    assert set(r.btns) == {'minus', 'plus', 'bookmark', 'notes', 'settings'}
    assert r.bottom_bar.height < 130 and r.btns['settings'].text == 'Налаштування'
    assert r.btns['plus'].text.startswith('A+') and r.btns['notes'].text.startswith('Нотатки')


def sheet_tiles(r):
    return [w for w in r.sheet.walk() if type(w).__name__ == 'Tile' and '[b]A' not in w.text]


def test_settings_sheet_taps_and_keys(reading):
    app, r = reading
    start = app.prefs['margin']
    assert app._on_key(None, 115) is True                 # S відкриває панель
    assert r.sheet is not None
    rows = r.pref_rows()
    assert [x[0] for x in rows].count('Текст') == 6 and [x[0] for x in rows].count('Екран') == 4
    tiles = sheet_tiles(r)
    assert len(tiles) == len(rows)
    tiles[2].dispatch('on_release')                       # «Поля»: значення змінилось, панель лишилась
    assert app.prefs['margin'] != start and r.sheet is not None
    assert MARGIN_NAMES[app.prefs['margin']] in tiles[2].text   # плитка показує нове значення
    size = app.prefs['font_size']
    plus = [w for w in r.sheet.walk() if type(w).__name__ == 'Tile' and w.text == '[b]A+[/b]'][0]
    plus.dispatch('on_release')
    assert app.prefs['font_size'] == size + 2
    theme, old = app.prefs['theme'], r.sheet
    tiles[7].dispatch('on_release')                       # «Тема»: палітра змінилась, панель перебудована
    tick(2)
    assert app.prefs['theme'] != theme and r.sheet is not None and r.sheet is not old
    assert app._on_key(None, 27) is True                  # Esc закриває
    assert r.sheet is None


def test_settings_sheet_closes_by_tap_on_text_and_done(reading):
    from test_ui_smoke import drag
    app, r = reading
    r.show_settings()
    tick(2)
    assert r.sheet is not None and r.sheet.height < r.height * 0.6   # текст зверху лишається видимим
    r.show_settings()                                     # повторний виклик закриває
    assert r.sheet is None
    r.show_settings()
    x, y = r.width / 2, r.height * 0.9                    # дотик по тексту над панеллю
    drag(x, y, x, y, steps=1)
    tick(2)
    assert r.sheet is None
    r.show_settings()
    done = [w for w in r.sheet.walk() if getattr(w, 'text', '') == 'Готово'][0]
    done.dispatch('on_release')
    assert r.sheet is None
    r.show_settings()
    r.back()                                              # кнопка «Назад» на Android
    assert r.sheet is None


def test_counter_modes_in_footer(reading):
    app, r = reading
    seen = set()
    for _ in range(7):
        r.cycle_counter()
        tick(1)
        text = r.foot_r.text
        mode = app.prefs['counter']
        assert text
        if mode == 'screen':
            assert text.startswith('%d з %d' % (r.idx + 1, len(r.pages)))
        elif mode == 'chapter':
            assert text.startswith('у розділі ')
        elif mode == 'time':
            assert 'до кінця' in text or text.startswith('кінець')
            assert r.foot_r.width > r.width * 0.4            # довгому підпису дано більше місця
        elif mode == 'pct':
            assert text == '%d%%' % r.entry['pct']
        seen.add(mode)
    assert {'screen', 'chapter', 'time', 'pct', 'conv'} <= seen
    r._go(len(r.pages) - 1, flash=False)
    app.prefs['counter'] = 'time'
    r.render()
    assert r.foot_r.text.startswith('кінець') or 'хв' in r.foot_r.text


def test_old_page_pref_migrates(app, tmp_path):
    state = tmp_path / 'old.json'
    state.write_text(json.dumps({'prefs': {'book_pages': False}, 'library': []}), encoding='utf-8')
    app.state_path = str(state)
    app._load_state()
    assert app.prefs['counter'] == 'conv'
    state.write_text(json.dumps({'prefs': {'book_pages': True}, 'library': []}), encoding='utf-8')
    app._load_state()
    assert app.prefs['counter'] == 'book'
    state.write_text(json.dumps({'prefs': {'counter': 'pct'}, 'library': []}), encoding='utf-8')
    app._load_state()
    assert app.prefs['counter'] == 'pct'


def test_every_settings_row_reacts_to_real_touch(shown, fb2_path):
    """Справжній дотик по кожному рядку вікна «Налаштування» змінює саме його значення."""
    from test_ui_smoke import drag
    app = shown
    app.add_book(fb2_path)
    tick(3)
    r = app.reader
    r.paginate(r.cur_pos())
    tick(2)
    r.show_menu(True)
    tick(2)
    bx, by = r.btns['settings'].to_window(r.btns['settings'].center_x, r.btns['settings'].center_y)
    drag(bx, by, bx, by, steps=1)                         # кнопка «Налаштування» в нижній панелі
    tick(3)
    assert r.sheet is not None
    keys = [k for _g, k, *_ in r.pref_rows()]
    for i, key in enumerate(keys):
        if key in ('eink', 'theme', 'font'):              # палітра перебудовує панель; шрифт може бути єдиним
            continue
        tiles = sheet_tiles(r)
        assert len(tiles) == len(keys)
        before = {k: v for _g, k, _n, v, _a in r.pref_rows()}[key]
        scr, tile = r._sheet_scroll, tiles[i]
        for sy in (1.0, 0.75, 0.5, 0.25, 0.0):             # прокручуємо, доки плитка не стане видимою
            scr.scroll_y = sy
            tick(2)
            if scr.collide_point(*tile.to_window(tile.center_x, tile.center_y)):
                break
        x, y = tile.to_window(tile.center_x, tile.center_y)
        assert r.sheet.collide_point(x, y) and scr.collide_point(x, y), key
        drag(x, y, x, y, steps=1)
        tick(3)
        after = {k: v for _g, k, _n, v, _a in r.pref_rows()}[key]
        assert after != before, key


def test_settings_sheet_stays_above_system_bar(reading):
    app, r = reading
    r.set_insets(0, 40, 0, 120)                           # нижня панель навігації Android
    r.show_settings()
    tick(2)
    assert r.sheet.y == 0 and r._sheet_pad.height == 120
    tile = sheet_tiles(r)[0]
    scr = r._sheet_scroll
    assert scr.y >= 120 - 1                               # прокручуваний список починається над панеллю
    assert tile.width > 0
    r.set_insets(0, 40, 0, 0)
    assert r._sheet_pad.height == 0
