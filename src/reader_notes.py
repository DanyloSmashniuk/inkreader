"""Закладки і список нотаток (закладки та виділення) в читалці."""
import time
from bisect import bisect_right

from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.utils import escape_markup

import notes
from swipe import SwipeRow
from widgets import BgBox, Rule, flat_button, make_scroll, scroll_by

ROW_H = dp(80)


class NotesMixin:
    """Примішується до ReaderScreen."""

    def page_range(self):
        """[початок, початок наступної) поточної сторінки; для останньої hi=None."""
        lo = self.page_pos[self.idx]
        hi = self.page_pos[self.idx + 1] if self.idx + 1 < len(self.page_pos) else None
        return lo, hi

    def has_bookmark(self):
        return bool(self.pages) and bool(notes.page_bookmarks(self.entry, *self.page_range()))

    def chapter_at(self, block):
        ci = bisect_right(self.chap_blocks, block) - 1
        return self.book.chapters[ci][0] if ci >= 0 else ''

    def _rebuild_hl(self):
        self._hl_idx = notes.hl_index(self.entry)

    def go_to_pos(self, pos):
        self._go(max(0, bisect_right(self.page_pos, tuple(pos)) - 1), flash=False)

    # ---------- закладка поточної сторінки
    def toggle_bookmark(self):
        if not self.pages:
            return
        lo, hi = self.page_range()
        notes.toggle_bookmark(self.entry, lo, hi, lambda: self._new_bookmark(lo))
        self._queue_save()
        self.render()
        self._refresh_menu_labels()

    def _new_bookmark(self, pos):
        b, o = pos
        kind, text = self.book.blocks[b][0], self.book.blocks[b][1]
        snippet = notes.preview(text, o) if kind in 'hpv' else ''
        return {'b': b, 'o': o, 't': time.time(), 'txt': snippet or 'Ілюстрація',
                'ch': self.chapter_at(b), 'pct': int(round(100 * (self.idx + 1) / len(self.pages)))}

    # ---------- список нотаток
    def show_notes(self, tab='bm'):
        if not self.book:
            return
        bg, fg = self.app.colors
        scroll = make_scroll(fg)
        scroll.do_scroll_x = False                      # горизонтальний рух віддаємо свайпу рядків
        lst = BoxLayout(orientation='vertical', size_hint_y=None)
        lst.bind(minimum_height=lst.setter('height'))
        scroll.add_widget(lst)
        tabs = BoxLayout(size_hint_y=None, height=dp(46))
        nav = BoxLayout(size_hint_y=None, height=dp(48))
        nav.add_widget(flat_button('Вгору', lambda: scroll_by(scroll, scroll.height * 0.9), fg))
        nav.add_widget(flat_button('Вниз', lambda: scroll_by(scroll, -scroll.height * 0.9), fg))
        nav.add_widget(flat_button('Закрити', lambda: self._modal_popup.dismiss(), fg, bold=True))
        box = BoxLayout(orientation='vertical')
        for w in (tabs, Rule(color=(fg[0], fg[1], fg[2], 0.4), thick=1), scroll,
                  Rule(color=(fg[0], fg[1], fg[2], 0.4), thick=1), nav):
            box.add_widget(w)
        popup = self.app.make_popup('Нотатки', box, (0.94, 0.88), closer=False)
        state = {'tab': tab}
        group = []                                       # відкриті рядки зі свайпом

        def jump(pos):
            popup.dismiss()
            self.go_to_pos(pos)
            self.show_menu(False)

        def drop(item, is_bm):
            if is_bm:
                notes.remove_bookmark(self.entry, item)
            else:
                notes.remove_highlight(self.entry, item)
                self._rebuild_hl()
            self._queue_save()
            self.render()
            self._refresh_menu_labels()
            fill()

        def row(item, is_bm):
            if is_bm:
                head = '[b]%s[/b]  ·  %d%%' % (escape_markup(item.get('ch') or 'Початок'),
                                               item.get('pct', 0))
                body, pos = item['txt'], (item['b'], item['o'])
            else:
                head = '[b]%s[/b]' % escape_markup(self.chapter_at(item['seg'][0][0]) or 'Початок')
                body = item['txt'] if len(item['txt']) <= 140 else item['txt'][:140].rstrip() + '…'
                pos = notes.hl_start(item)
            content = BgBox(color=bg, padding=(dp(14), dp(6)))
            lbl = Label(text='%s\n[size=%d]%s[/size]' % (head, int(sp(14)), escape_markup(body)),
                        markup=True, halign='left', valign='middle', color=fg, font_size=sp(13))
            lbl.bind(size=lambda w, s: setattr(w, 'text_size', (s[0], s[1])))
            content.add_widget(lbl)
            return SwipeRow(content, on_tap=lambda: jump(pos), on_delete=lambda: drop(item, is_bm),
                            colors=(bg, fg), group=group, height=ROW_H)

        def fill():
            lst.clear_widgets()
            group.clear()
            tabs.clear_widgets()
            bms, hls = self.entry.get('bm', []), self.entry.get('hl', [])
            for key, name, n in (('bm', 'Закладки', len(bms)), ('hl', 'Виділення', len(hls))):
                mark = '[b]%s (%d)[/b]' if key == state['tab'] else '%s (%d)'
                tabs.add_widget(flat_button(mark % (name, n), lambda k=key: switch(k), fg,
                                            markup=True, font_size=sp(15)))
            items = bms if state['tab'] == 'bm' else hls
            if not items:
                empty = ('Закладок ще немає.\nНатисни «Закладка» в меню (або клавішу B).'
                         if state['tab'] == 'bm' else
                         'Виділень ще немає.\nЗатисни слово на сторінці й потягни, потім «Виділити».')
                hint = Label(text=empty, color=fg, halign='center', size_hint_y=None, height=dp(160))
                hint.bind(size=lambda w, s: setattr(w, 'text_size', (s[0] - dp(20), None)))
                lst.add_widget(hint)
            else:
                lst.add_widget(Label(text='Свайп ліворуч — видалити', color=(fg[0], fg[1], fg[2], 0.6),
                                     font_size=sp(12), size_hint_y=None, height=dp(26)))
            for item in items:
                lst.add_widget(row(item, state['tab'] == 'bm'))
                lst.add_widget(Rule(color=(fg[0], fg[1], fg[2], 0.4), thick=1))
            scroll.scroll_y = 1.0

        def switch(key):
            state['tab'] = key
            fill()

        fill()
        self._modal_popup, self._modal_scroll = popup, scroll
        popup.bind(on_dismiss=lambda *_: setattr(self, '_modal_scroll', None))
        popup.open()
