"""Виділення тексту на сторінці: довге натискання на слово, протягнути, дія над виділеним.

Слова сторінки зібрані під час малювання (ReaderScreen._words): прямокутник у координатах екрана
та позиція в тексті (блок, від, до). Виділення — діапазон індексів цього списку, тому воно живе,
поки відкрита та сама сторінка; збережене виділення (highlight) — діапазони тексту, див. notes.py.
"""
import math

from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout

import notes
from widgets import BgBox, Rule, flat_button

LONG_PRESS = 0.45        # с утримання до початку виділення
TAP_SLACK = dp(6)        # наскільки поруч зі словом має бути дотик, щоб вважатися дотиком по ньому
PRESS_SLACK = dp(30)     # те саме для довгого натискання (палець товстіший за слово)


class SelectionMixin:
    """Примішується до ReaderScreen."""
    _lp_ev = None
    _lp_touch = None

    # ---------- панель дій
    def _build_sel_bar(self):
        self.sel_bar = BgBox(orientation='vertical', size_hint=(1, None), height=dp(58),
                             pos_hint={'x': 0, 'y': 0})
        self.sel_rule = Rule()
        row = BoxLayout()
        self.sel_btns = {
            'copy': flat_button('Копіювати', self.copy_selection, font_size=sp(14)),
            'hl': flat_button('Виділити', self.toggle_highlight, font_size=sp(14)),
            'cancel': flat_button('Скасувати', self.clear_selection, font_size=sp(14)),
        }
        for b in self.sel_btns.values():
            row.add_widget(b)
        self.sel_bar.add_widget(self.sel_rule)
        self.sel_bar.add_widget(row)

    def restyle_sel_bar(self, bg, fg):
        self.sel_bar.set_bg(bg)
        self.sel_rule.set_color(fg)
        for b in self.sel_btns.values():
            b.color = fg

    # ---------- пошук слова
    def _nearest_word(self, x, y, slack=None):
        best, best_d = None, None
        for n, (x0, y0, x1, y1, *_rest) in enumerate(self._words):
            d = math.hypot(max(x0 - x, 0, x - x1), 2 * max(y0 - y, 0, y - y1))   # рядок важливіший за стовпчик
            if best_d is None or d < best_d:
                best, best_d = n, d
        if best is None or (slack is not None and best_d > slack):
            return None
        return best

    # ---------- довге натискання
    def _cancel_long_press(self):
        if self._lp_ev:
            self._lp_ev.cancel()
        self._lp_ev = self._lp_touch = None

    def _arm_long_press(self, touch):
        self._cancel_long_press()
        self._lp_touch = touch
        self._lp_ev = Clock.schedule_once(lambda dt: self._start_selection(touch), LONG_PRESS)

    def _start_selection(self, touch):
        self._lp_ev = None
        if self._lp_touch is not touch or not self.pages or self.menu_visible:
            return
        n = self._nearest_word(touch.x, touch.y, PRESS_SLACK)
        if n is None:
            return
        touch.ud['selecting'] = True
        self._anchor = n
        self._set_selection(n, n)

    def _extend_selection(self, pos):
        n = self._nearest_word(*pos)
        if n is not None:
            self._set_selection(min(self._anchor, n), max(self._anchor, n))

    def _set_selection(self, a, b):
        if self.sel == (a, b):
            return
        self.sel = (a, b)
        self.render()

    def _selection_done(self):
        self._lp_touch = None
        if self.sel:
            self._show_sel_bar()

    # ---------- панель
    def _sel_words(self):
        if not self.sel:
            return []
        a, b = self.sel
        return self._words[a:b + 1]

    def _sel_segments(self):
        return notes.segments([(w[4], w[5], w[6]) for w in self._sel_words()])

    def _show_sel_bar(self):
        words = self._sel_words()
        if not words:
            return
        l, t, r, b = self.inset
        w, h = max(1, self.width), max(1, self.height)
        # панель з того боку, де виділення її не затуляє
        low = sum((x[1] + x[3]) / 2 for x in words) / len(words) < h * 0.42
        self.sel_bar.size_hint_x = max(0.1, (w - l - r) / w)
        self.sel_bar.pos_hint = {'x': l / w, 'top': 1 - t / h} if low else {'x': l / w, 'y': b / h}
        have = any(notes.overlaps(self._hl_idx, bi, s, e) for bi, s, e in self._sel_segments())
        self.sel_btns['hl'].text = 'Зняти виділення' if have else 'Виділити'
        self.show_menu(False)
        if self.sel_bar.parent is None:
            self.root_f.add_widget(self.sel_bar)

    def clear_selection(self, render=True):
        had = self.sel is not None
        self.sel = None
        self._lp_touch = None
        if self.sel_bar.parent is not None:
            self.root_f.remove_widget(self.sel_bar)
        if had and render and self.pages:
            self.render()

    # ---------- дії
    def copy_selection(self):
        segs = self._sel_segments()
        text = notes.selection_text(self.book.blocks, segs)
        if text:
            try:
                Clipboard.copy(text)
            except Exception:  # noqa: BLE001 — буфер обміну залежить від платформи; не повод падати
                pass
        self.clear_selection()
        self.foot_l.text = 'Скопійовано'
        Clock.schedule_once(lambda dt: self.render(), 1.5)

    def toggle_highlight(self):
        segs = self._sel_segments()
        if not segs:
            return
        if any(notes.overlaps(self._hl_idx, bi, s, e) for bi, s, e in segs):
            notes.remove_highlights(self.entry, segs)
        else:
            notes.add_highlight(self.entry, segs, notes.selection_text(self.book.blocks, segs))
        self._rebuild_hl()
        self._queue_save()
        self.clear_selection(render=False)
        self.render()
        self._refresh_menu_labels()

    def tap_highlight(self, pos):
        """Дотик по збереженому виділенню: вибирає його цілком (щоб зняти або скопіювати)."""
        n = self._nearest_word(*pos, TAP_SLACK)
        if n is None:
            return False
        _x0, _y0, _x1, _y1, bi, a, b = self._words[n]
        hits = [h for h in self.entry.get('hl', ())
                if any(sb == bi and a < se and b > ss for sb, ss, se in h['seg'])]
        if not hits:
            return False
        idx = [i for i, w in enumerate(self._words)
               if any(w[4] == sb and w[5] < se and w[6] > ss for h in hits for sb, ss, se in h['seg'])]
        self.sel = (min(idx), max(idx))
        self.render()
        self._show_sel_bar()
        return True
