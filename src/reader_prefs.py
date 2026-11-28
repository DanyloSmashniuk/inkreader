"""Панель «Налаштування»: нижній аркуш, під яким текст книги видно й змінюється одразу."""
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget

import counter
import fonts
from config import MARGIN_NAMES
from widgets import BgBox, Rule, Tile, flat_button, make_scroll

TILE_H = dp(62)


class PrefsMixin:
    """Примішується до ReaderScreen."""

    sheet = None
    _sheet_scroll = None

    def pref_rows(self):
        """[(група, ключ, назва, значення, дія)] у порядку показу."""
        p = self.app.prefs
        book_pages = bool(self.book and self.book.pagelist)
        mode = counter.effective(p['counter'], book_pages)
        return [
            ('Текст', 'font', 'Шрифт', 'із засічками' if p['font'] == 'serif' and fonts.SERIF
             else 'без засічок', self.toggle_font),
            ('Текст', 'spacing', 'Інтервал', '%.2f' % p['spacing'], self.cycle_spacing),
            ('Текст', 'margin', 'Поля', MARGIN_NAMES[p['margin']], self.cycle_margin),
            ('Текст', 'justify', 'Вирівнювання', 'по ширині' if p['justify'] else 'по лівому',
             self.toggle_justify),
            ('Текст', 'hyph', 'Переноси', 'так' if p['hyph'] else 'ні', self.toggle_hyph),
            ('Текст', 'bold', 'Накреслення', 'жирне' if p['bold'] else 'звичайне', self.toggle_bold),
            ('Екран', 'eink', 'Режим', 'E-ink' if p['eink'] else 'Колір', self.toggle_eink),
            ('Екран', 'theme', 'Тема', 'темна' if p['theme'] == 'dark' else 'світла', self.toggle_theme),
            ('Екран', 'flash', 'Оновлення екрана',
             'вимк.' if not p['flash_every'] else 'щоразу' if p['flash_every'] == 1
             else 'кожні %d' % p['flash_every'], self.cycle_flash),
            ('Екран', 'counter', 'Підпис прогресу', counter.NAMES[mode], self.cycle_counter),
        ]

    def show_settings(self):
        """Відкриває (або закриває, якщо вже відкрита) нижню панель налаштувань."""
        if not self.book:
            return
        if self.sheet is not None:
            self.close_settings()
            return
        self.show_menu(False)
        self._open_sheet(1.0)

    def _place_sheet(self):
        """Панель лежить у безпечній зоні: нижня системна панель не перекриває плитки."""
        if self.sheet is None:
            return
        l, _t, r, b = self.inset
        w = max(1, self.width)
        self.sheet.size_hint_x = max(0.1, (w - l - r) / w)
        self.sheet.pos_hint = {'x': l / w, 'y': 0}
        self._sheet_pad.height = b
        self.sheet.height = max(dp(300), self.height * 0.46) + b

    def close_settings(self):
        if self.sheet is not None:
            self.root_f.remove_widget(self.sheet)
            self.sheet = self._sheet_scroll = None

    def _open_sheet(self, scroll_y):
        """Будує панель наново (потрібно лише після зміни палітри)."""
        if self.sheet is not None:
            self.root_f.remove_widget(self.sheet)
        bg, fg = self.app.colors
        dim = (fg[0], fg[1], fg[2], 0.4)
        sheet = BgBox(color=bg, orientation='vertical', size_hint=(1, None), pos_hint={'x': 0, 'y': 0})
        self._sheet_pad = Widget(size_hint_y=None, height=0)     # місце під системну панель навігації
        head = BoxLayout(size_hint_y=None, height=dp(58), padding=(dp(14), 0, dp(4), 0))
        title = Label(text='[b]Налаштування[/b]\n[size=%d]торкнись тексту вгорі, щоб закрити[/size]'
                      % int(sp(11)), markup=True, color=fg, font_size=sp(17), halign='left', valign='middle')
        title.bind(size=lambda w, s: setattr(w, 'text_size', s))
        done = flat_button('Готово', self.close_settings, fg, font_size=sp(16), bold=True,
                           size_hint_x=None, width=dp(104))
        head.add_widget(title)
        head.add_widget(done)
        scroll = make_scroll(fg)
        scroll.do_scroll_x = False
        body = BoxLayout(orientation='vertical', size_hint_y=None, padding=(dp(12), dp(4), dp(12), dp(10)),
                         spacing=dp(6))
        body.bind(minimum_height=body.setter('height'))
        scroll.add_widget(body)

        tiles = {}
        size_val = Label(color=fg, font_size=sp(18), bold=True, size_hint_x=None, width=dp(56))

        def refresh():
            size_val.text = '%d' % self.app.prefs['font_size']
            for _g, key, name, value, _a in self.pref_rows():
                tiles[key].set_texts(name, value)

        def tap(key, action):
            action()
            if key in ('eink', 'theme'):              # змінюють палітру: панель будуємо знову
                self._open_sheet(scroll.scroll_y)
            else:
                refresh()

        def step(delta):
            self.change_font(delta)
            refresh()

        def header(text):
            lbl = Label(text=text.upper(), color=(fg[0], fg[1], fg[2], 0.65), font_size=sp(12),
                        halign='left', valign='bottom', size_hint_y=None, height=dp(26))
            lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
            return lbl

        size_row = BoxLayout(size_hint_y=None, height=TILE_H, spacing=dp(8))
        cap = Label(text='Розмір', color=fg, font_size=sp(16), halign='left', valign='middle',
                    size_hint_x=None, width=dp(88))
        cap.bind(size=lambda w, s: setattr(w, 'text_size', s))
        minus = Tile(fg, text='[b]A−[/b]', font_size=sp(20), halign='center', on_release=lambda *_: step(-2))
        plus = Tile(fg, text='[b]A+[/b]', font_size=sp(20), halign='center', on_release=lambda *_: step(2))
        for w in (cap, minus, size_val, plus):
            size_row.add_widget(w)

        group, grid = None, None
        for g, key, _n, _v, action in self.pref_rows():
            if g != group:
                group = g
                body.add_widget(header(g))
                if g == 'Текст':
                    body.add_widget(size_row)
                grid = GridLayout(cols=2, size_hint_y=None, spacing=dp(8), row_default_height=TILE_H,
                                  row_force_default=True)
                grid.bind(minimum_height=grid.setter('height'))
                body.add_widget(grid)
            t = Tile(fg, on_release=lambda _w, k=key, a=action: tap(k, a))
            tiles[key] = t
            grid.add_widget(t)
        refresh()
        for w in (head, Rule(color=dim, thick=1), scroll, self._sheet_pad):
            sheet.add_widget(w)
        self.sheet, self._sheet_scroll = sheet, scroll
        self._place_sheet()
        self.root_f.add_widget(sheet)
        scroll.scroll_y = scroll_y
