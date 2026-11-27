"""Вікно «Налаштування»: усі рідкісні параметри читалки списком (назва зліва, значення справа)."""
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label

import counter
import fonts
from config import MARGIN_NAMES
from widgets import RowButton, Rule, flat_button, make_scroll, scroll_by

ROW_H = dp(56)


class PrefsMixin:
    """Примішується до ReaderScreen."""

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
        if not self.book:
            return
        bg, fg = self.app.colors
        dim = (fg[0], fg[1], fg[2], 0.4)
        scroll = make_scroll(fg)
        scroll.do_scroll_x = False
        lst = BoxLayout(orientation='vertical', size_hint_y=None)
        lst.bind(minimum_height=lst.setter('height'))
        scroll.add_widget(lst)
        nav = BoxLayout(size_hint_y=None, height=dp(48))
        nav.add_widget(flat_button('Вгору', lambda: scroll_by(scroll, scroll.height * 0.9), fg))
        nav.add_widget(flat_button('Вниз', lambda: scroll_by(scroll, -scroll.height * 0.9), fg))
        box = BoxLayout(orientation='vertical')
        for w in (scroll, Rule(color=dim, thick=1), nav):
            box.add_widget(w)
        popup = self.app.make_popup('Налаштування', box, (0.94, 0.88))
        recolor = {'eink', 'theme'}               # змінюють палітру: вікно відкриваємо знову

        def tap(key, action):
            action()
            if key in recolor:
                y = scroll.scroll_y
                popup.dismiss()
                self.show_settings()
                self._modal_scroll.scroll_y = y
            else:
                fill()

        def fill():
            y = scroll.scroll_y
            lst.clear_widgets()
            group = None
            for g, key, name, value, action in self.pref_rows():
                if g != group:
                    group = g
                    head = Label(text=g.upper(), color=(fg[0], fg[1], fg[2], 0.65), font_size=sp(12),
                                 halign='left', valign='bottom', size_hint_y=None, height=dp(34))
                    head.bind(size=lambda w, s: setattr(w, 'text_size', (s[0] - dp(24), s[1] - dp(4))))
                    lst.add_widget(head)
                lst.add_widget(Rule(color=dim, thick=1))
                row = FloatLayout(size_hint_y=None, height=ROW_H)
                row.add_widget(RowButton(text='', color=fg, size_hint=(1, 1),
                                         on_release=lambda _w, k=key, a=action: tap(k, a)))
                left = Label(text=name, color=fg, font_size=sp(16), halign='left', valign='middle',
                             size_hint=(0.55, 1), pos_hint={'x': 0, 'y': 0})
                right = Label(text=value, color=(fg[0], fg[1], fg[2], 0.8), font_size=sp(16),
                              halign='right', valign='middle', size_hint=(0.45, 1),
                              pos_hint={'right': 1, 'y': 0})
                for lbl in (left, right):
                    lbl.bind(size=lambda w, s: setattr(w, 'text_size', (s[0] - dp(24), s[1])))
                    row.add_widget(lbl)
                lst.add_widget(row)
            lst.add_widget(Rule(color=dim, thick=1))
            scroll.scroll_y = y
        fill()
        self._modal_popup, self._modal_scroll = popup, scroll
        popup.bind(on_dismiss=lambda *_: setattr(self, '_modal_scroll', None))
        popup.open()
