"""Екран бібліотеки: список книг з обкладинками, вибір вигляду, додавання."""
import os

from kivy.effects.scroll import ScrollEffect
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.utils import escape_markup

from swipe import SwipeRow
from widgets import BgBox, Pic, Rule, flat_button


class LibraryScreen(Screen):
    def set_insets(self, l, t, r, b):
        """Відступи під системні панелі Android: padding всередині екрана (сам екран не зсуваємо:
        у зсунутому RelativeLayout Kivy віддає кнопкам «відпускання» у координатах вікна.)"""
        self.root_box.padding = (l, t, r, b)       # BoxLayout.padding: left, TOP, right, BOTTOM

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.root_box = BgBox(orientation='vertical')
        self.add_widget(self.root_box)

        self.bar = BoxLayout(size_hint_y=None, height=dp(60), padding=(dp(16), 0, 0, 0))
        self.title_lbl = Label(text='[b]Бібліотека[/b]', markup=True, halign='left',
                               valign='middle', font_size=sp(20))
        self.title_lbl.bind(size=lambda w, s: setattr(w, 'text_size', s))
        self.view_btn = flat_button('', self.app.cycle_view, size_hint_x=None,
                                    width=dp(120), font_size=sp(12))
        self.add_btn = flat_button('+ Книга', self.app.pick_file, size_hint_x=None,
                                   width=dp(100))
        for w in (self.title_lbl, self.view_btn, self.add_btn):
            self.bar.add_widget(w)
        self.rule = Rule()
        self.root_box.add_widget(self.bar)
        self.root_box.add_widget(self.rule)

        self.open_rows = []          # рядки зі свайпом, що зараз відкриті
        self.scroll = ScrollView(effect_cls=ScrollEffect, bar_width=dp(10), do_scroll_x=False,
                                 scroll_type=['bars', 'content'], scroll_wheel_distance=dp(90))
        self.listbox = BoxLayout(orientation='vertical', size_hint_y=None)
        self.listbox.bind(minimum_height=self.listbox.setter('height'))
        self.scroll.add_widget(self.listbox)
        self.root_box.add_widget(self.scroll)

    def refresh(self):
        bg, fg = self.app.colors
        self.root_box.set_bg(bg)
        self.rule.set_color(fg)
        self.scroll.bar_color = fg
        self.scroll.bar_inactive_color = (fg[0], fg[1], fg[2], 0.4)
        for w in (self.title_lbl, self.view_btn, self.add_btn):
            w.color = fg
        p = self.app.prefs
        self.view_btn.text = 'Вигляд\n%s · %s' % ('E-ink' if p['eink'] else 'Колір',
                                                    'темна' if p['theme'] == 'dark' else 'світла')
        self.open_rows.clear()
        self.listbox.clear_widgets()
        if not self.app.library:
            hint = Label(text='Порожньо.\nНатисни «+ Книга» і обери EPUB або FB2.\n'
                              'Книгу видаляє свайп ліворуч.',
                         color=fg, halign='center', size_hint_y=None, height=dp(200))
            hint.bind(size=lambda w, s: setattr(w, 'text_size', (s[0], None)))
            self.listbox.add_widget(hint)
            return
        for entry in self.app.library:
            self.listbox.add_widget(self._row(entry, bg, fg))
            self.listbox.add_widget(Rule(color=(fg[0], fg[1], fg[2], 0.5), thick=1))

    def _row(self, entry, bg, fg):
        """Рядок книги: обкладинка, назва, автор і відсоток; свайп ліворуч — «Видалити»."""
        eink = self.app.prefs['eink']
        content = BgBox(color=bg, padding=(dp(12), dp(8), dp(8), dp(8)), spacing=dp(12))
        cover = entry.get('cover')
        if cover and os.path.exists(cover):
            thumb = Pic(cover, gray=eink, size_hint_x=None, width=dp(62))
        else:
            thumb = BgBox(color=(fg[0], fg[1], fg[2], 0.15), size_hint_x=None, width=dp(62))
            thumb.add_widget(Label(
                text='[b]%s[/b]' % escape_markup((entry['title'] or '?')[:1].upper()),
                markup=True, color=fg, font_size=sp(26)))
        sub = escape_markup(entry.get('author') or '—')
        lbl = Label(text='[b]%s[/b]\n[size=%d]%s  ·  %d%%[/size]' % (
            escape_markup(entry['title']), int(sp(13)), sub, entry.get('pct', 0)),
            markup=True, halign='left', valign='middle', color=fg)
        lbl.bind(size=lambda w, s: setattr(w, 'text_size', (s[0], s[1])))
        content.add_widget(thumb)
        content.add_widget(lbl)
        return SwipeRow(content, on_tap=lambda: self.app.open_entry(entry),
                        on_delete=lambda: self.app.remove_entry(entry), colors=(bg, fg),
                        group=self.open_rows, height=dp(108))
