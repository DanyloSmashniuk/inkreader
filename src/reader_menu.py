"""Меню читалки (верхня й нижня панелі) і зміст."""
from bisect import bisect_right

from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.utils import escape_markup

from widgets import BgBox, RowButton, Rule, SeekBar, flat_button, make_scroll, scroll_by


class MenuMixin:
    """Примішується до ReaderScreen."""

    def _build_menu(self):
        self.top_bar = BgBox(orientation='vertical', size_hint=(1, None), height=dp(54),
                             pos_hint={'top': 1})
        row = BoxLayout(padding=(dp(4), 0))
        self.back_btn = flat_button('‹ Бібліотека', self.leave, size_hint_x=None, width=dp(140))
        self.title_lbl = Label(halign='center', valign='middle', shorten=True,
                               shorten_from='right')
        self.title_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        self.toc_btn = flat_button('Зміст', self.show_toc, size_hint_x=None, width=dp(90))
        for w in (self.back_btn, self.title_lbl, self.toc_btn):
            row.add_widget(w)
        self.top_rule = Rule()
        self.top_bar.add_widget(row)
        self.top_bar.add_widget(self.top_rule)

        self.bottom_bar = BgBox(orientation='vertical', size_hint=(1, None),
                                height=dp(112), pos_hint={'x': 0, 'y': 0})
        self.bottom_rule = Rule()
        self.seek = SeekBar(self._seek_done, self._seek_preview, size_hint_y=None,
                            height=dp(44))
        row = BoxLayout(size_hint_y=None, height=dp(60))
        self.btns = {}
        spec = [('minus', 0.55, lambda: self.change_font(-2)),
                ('plus', 0.55, lambda: self.change_font(2)),
                ('bookmark', 1.1, self.toggle_bookmark),
                ('notes', 1.5, self.show_notes),
                ('settings', 1.4, self.show_settings)]
        for key, weight, cb in spec:
            b = flat_button('', cb, font_size=sp(12), size_hint_x=weight)
            self.btns[key] = b
            row.add_widget(b)
        self.btns['settings'].text = 'Налаштування'
        for w in (self.bottom_rule, self.seek, row):
            self.bottom_bar.add_widget(w)

    def show_menu(self, show):
        if show == self.menu_visible:
            return
        self.menu_visible = show
        if show:
            self.title_lbl.text = self.book.title if self.book else ''
            self._refresh_menu_labels()
            self.seek.set(self.idx, len(self.pages) - 1)
            self.root_f.add_widget(self.top_bar)
            self.root_f.add_widget(self.bottom_bar)
        else:
            self.root_f.remove_widget(self.top_bar)
            self.root_f.remove_widget(self.bottom_bar)

    def _seek_marks(self):
        """Штрихи закладок на повзунку: сторінка, на якій лежить кожна закладка."""
        if not self.page_pos:
            return
        e = self.entry or {}
        self.seek.set_marks(max(0, bisect_right(self.page_pos, (b['b'], b['o'])) - 1)
                            for b in e.get('bm', ()))

    def _refresh_menu_labels(self):
        p = self.app.prefs
        b = self.btns
        b['minus'].text = 'A−\n%d' % max(8, p['font_size'] - 2)
        b['plus'].text = 'A+\n%d' % (p['font_size'] + 2)
        b['bookmark'].text = 'Закладка\n%s' % ('зняти' if self.has_bookmark() else 'додати')
        self._seek_marks()
        e = self.entry or {}
        b['notes'].text = 'Нотатки\n%d закл. · %d вид.' % (len(e.get('bm', ())), len(e.get('hl', ())))

    def show_toc(self):
        if not self.book:
            return
        bg, fg = self.app.colors
        scroll = make_scroll(fg)
        lst = BoxLayout(orientation='vertical', size_hint_y=None)
        lst.bind(minimum_height=lst.setter('height'))
        box = BoxLayout(orientation='vertical')
        box.add_widget(scroll)
        nav = BoxLayout(size_hint_y=None, height=dp(48))
        nav.add_widget(flat_button('Вгору', lambda: scroll_by(scroll, scroll.height * 0.9), fg))
        nav.add_widget(flat_button('Вниз', lambda: scroll_by(scroll, -scroll.height * 0.9), fg))
        nav.add_widget(flat_button('Закрити', lambda: self._modal_popup.dismiss(), fg, bold=True))
        box.add_widget(Rule(color=(fg[0], fg[1], fg[2], 0.4), thick=1))
        box.add_widget(nav)
        popup = self.app.make_popup('Зміст', box, (0.94, 0.88), closer=False)
        chapters = self.book.chapters or [('Початок', 0)]
        ci = bisect_right(self.chap_blocks, self.page_pos[self.idx][0]) - 1 if self.pages else -1
        for i, (title, block) in enumerate(chapters):
            mark = '[b]%s[/b]' if i == ci else '%s'
            b = RowButton(text=mark % escape_markup(title), size_hint_y=None, height=dp(52),
                          color=fg)
            b.bind(on_release=lambda _w, bl=block: (popup.dismiss(), self.go_to_block(bl),
                                                    self.show_menu(False)))
            lst.add_widget(b)
            lst.add_widget(Rule(color=(fg[0], fg[1], fg[2], 0.4), thick=1))
        scroll.add_widget(lst)
        self._modal_popup, self._modal_scroll = popup, scroll
        popup.bind(on_dismiss=lambda *_: setattr(self, '_modal_scroll', None))

        def focus_current(_dt):
            """Відкриває зміст одразу на поточному розділі."""
            room = lst.height - scroll.height
            if room > 0 and ci > 0:
                y = ci * lst.height / len(chapters) - scroll.height / 2
                scroll.scroll_y = 1.0 - min(1.0, max(0.0, y / room))
        popup.open()
        Clock.schedule_once(focus_current, 0)
