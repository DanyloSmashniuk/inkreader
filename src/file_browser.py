"""Власний вибір книги (ПК і запасний варіант на Android): кроки по теках, швидкі місця."""
import os

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.utils import escape_markup, platform

from book_loader import SUPPORTED_EXTS
from widgets import RowButton, Rule, flat_button, make_scroll


def browse_books(app):
    """Власний вибір книги: кроки по теках, швидкі місця, тап по книзі відкриває її."""
    bg, fg = app.colors
    dim = '%02x%02x%02x' % tuple(int(255 * (0.55 * c + 0.45 * b)) for c, b in zip(fg[:3], bg[:3]))
    home = os.path.expanduser('~')
    android = os.path.isdir('/storage/emulated/0')
    root = '/storage/emulated/0' if android else home
    state = {'path': root}

    outer = BoxLayout(orientation='vertical', spacing=dp(6), padding=(dp(6), 0, dp(6), dp(6)))
    top = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(4))
    up = flat_button('‹', lambda: go(os.path.dirname(state['path'])), fg,
                     size_hint_x=None, width=dp(48), font_size='30sp')
    where = Label(color=fg, halign='left', valign='middle', shorten=True,
                  shorten_from='left', font_size='15sp')
    where.bind(size=lambda w, sz: setattr(w, 'text_size', sz))
    top.add_widget(up)
    top.add_widget(where)
    outer.add_widget(top)

    places = [('Дім', home)]
    for name, label in (('Books', 'Books'), ('Книги', 'Книги'), ('Download', 'Завантаження'),
                        ('Downloads', 'Завантаження'), ('Завантаження', 'Завантаження'),
                        ('Documents', 'Документи'), ('Документи', 'Документи')):
        d = os.path.join(root, name)
        if os.path.isdir(d) and all(d != x[1] for x in places) \
                and all(label != x[0] for x in places):
            places.append((label, d))
    if android:
        places[0] = ('Пам\'ять', root)
    if platform == 'win':
        for letter in 'CDEFGHIJKLMNOPQRSTUVWXYZ':
            if os.path.isdir(letter + ':\\'):
                places.append((letter + ':', letter + ':\\'))
    chips = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(6))
    for label, d in places[:8]:
        chips.add_widget(flat_button(label, lambda d=d: go(d), fg, font_size='15sp'))
    outer.add_widget(chips)
    outer.add_widget(Rule(fg, 1))

    sv = make_scroll(fg)
    lst = BoxLayout(orientation='vertical', size_hint_y=None)
    lst.bind(minimum_height=lst.setter('height'))
    sv.add_widget(lst)
    outer.add_widget(sv)
    popup = app.make_popup('Обери книгу', outer, (0.95, 0.92))
    outer.add_widget(Rule(fg, 1))
    outer.add_widget(flat_button('Скасувати', popup.dismiss, fg,
                                 size_hint_y=None, height=dp(48)))

    def size_text(n):
        for u in ('Б', 'КБ', 'МБ', 'ГБ'):
            if n < 1024 or u == 'ГБ':
                return '%d %s' % (n, u) if u == 'Б' else '%.1f %s' % (n, u)
            n /= 1024.0

    def note(text):
        lbl = Label(text=text, color=fg, size_hint_y=None, height=dp(120))
        lst.add_widget(lbl)

    def go(path):
        path = os.path.abspath(path)
        try:
            names = sorted(os.listdir(path), key=str.lower)
        except OSError:
            note('Немає доступу до цієї теки')
            return
        state['path'] = path
        shown = ('~' + path[len(home):]) if path == home or path.startswith(home + os.sep) else path
        where.text = shown
        up.disabled = path == os.path.dirname(path)
        lst.clear_widgets()
        dirs, files = [], []
        for n in names:
            if n.startswith('.'):
                continue
            full = os.path.join(path, n)
            if os.path.isdir(full):
                dirs.append((n, full))
            elif n.lower().endswith(SUPPORTED_EXTS):
                files.append((n, full))
        for n, full in dirs:
            row = RowButton(text='[b]%s[/b]   [color=%s]›[/color]' % (escape_markup(n), dim),
                            color=fg, size_hint_y=None, height=dp(54), font_size='17sp')
            row.bind(on_release=lambda w, full=full: go(full))
            lst.add_widget(row)
            lst.add_widget(Rule(fg_soft, 1))
        for n, full in files:
            try:
                sz = size_text(os.path.getsize(full))
            except OSError:
                sz = ''
            ext = os.path.splitext(n)[1].lstrip('.').upper()
            row = RowButton(text='%s\n[size=13sp][color=%s]%s · %s[/color][/size]'
                            % (escape_markup(n), dim, ext, sz),
                            color=fg, size_hint_y=None, height=dp(62), font_size='17sp')
            row.bind(on_release=lambda w, full=full: (popup.dismiss(), app._picked([full])))
            lst.add_widget(row)
            lst.add_widget(Rule(fg_soft, 1))
        if not dirs and not files:
            note('Тут немає книг і тек')
        sv.scroll_y = 1

    fg_soft = (fg[0], fg[1], fg[2], 0.25)
    go(state['path'])
    popup.open()
