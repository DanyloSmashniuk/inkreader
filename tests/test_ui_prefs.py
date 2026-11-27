# ruff: noqa: F811  (фікстури app/shown імпортовано з test_ui_smoke і використано як аргументи)
"""Нижнє меню з одним рядком, вікно «Налаштування» і режими підпису прогресу (xvfb)."""
import json

import pytest

pytest.importorskip('kivy')
from test_ui_notes import long_paras, reading  # noqa: E402,F401  (фікстури)
from test_ui_smoke import app, shown, tick  # noqa: E402,F401


def buttons(widget):
    from kivy.uix.button import Button
    return [w for w in widget.walk() if isinstance(w, Button)]


def test_bottom_bar_is_one_row(reading):
    app, r = reading
    r.show_menu(True)
    assert set(r.btns) == {'minus', 'plus', 'bookmark', 'notes', 'settings'}
    assert r.bottom_bar.height < 130 and r.btns['settings'].text == 'Налаштування'
    assert r.btns['plus'].text.startswith('A+') and r.btns['notes'].text.startswith('Нотатки')


def test_settings_popup_taps_and_keys(reading):
    app, r = reading
    start = app.prefs['margin']
    assert app._on_key(None, 115) is True                 # S відкриває вікно
    assert r._modal_scroll is not None
    rows = r.pref_rows()
    assert [x[0] for x in rows].count('Текст') == 6 and [x[0] for x in rows].count('Екран') == 4
    btns = [b for b in buttons(r._modal_popup.content) if b.text == '']   # рядки, крім «Вгору/Вниз»
    assert len(btns) == len(rows)
    btns[2].dispatch('on_release')                        # «Поля»: наступне значення, вікно лишається
    assert app.prefs['margin'] != start and r._modal_scroll is not None
    theme = app.prefs['theme']
    old = r._modal_popup
    btns[7].dispatch('on_release')                        # «Тема»: палітра змінилась, вікно відкрито знову
    tick(2)
    assert app.prefs['theme'] != theme and r._modal_scroll is not None and r._modal_popup is not old
    assert app._on_key(None, 27) is True                  # Esc закриває
    tick(2)
    assert r._modal_scroll is None


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
