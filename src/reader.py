"""Екран читання: верстка, малювання сторінки, гортання."""
import re
import time
from bisect import bisect_left, bisect_right

from kivy.clock import Clock
from kivy.graphics import Color, PopMatrix, PushMatrix, Rectangle, Translate, Triangle
from kivy.metrics import dp, sp
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen
from kivy.uix.widget import Widget

import counter
import fonts
import notes
from config import MARGINS
from gestures import GestureMixin
from reader_menu import MenuMixin
from reader_notes import NotesMixin
from reader_prefs import PrefsMixin
from reader_settings import SettingsMixin
from selection import SelectionMixin
from typeset import Geometry, justify_positions, typeset
from widgets import PAGE_CH, BgFloat, Faces, Pic

_TOKEN = re.compile(r'\S+')
MARK_ALPHA = {1: 0.2, 2: 0.4}      # збережене виділення / поточне виділення


class ReaderScreen(GestureMixin, SelectionMixin, NotesMixin, PrefsMixin, MenuMixin, SettingsMixin, Screen):
    """Екран читання: верстка, малювання сторінки, гортання. Меню, нотатки, виділення й жести — у міксинах."""
    FOOTER_H = dp(34)
    inset = (0, 0, 0, 0)          # l, t, r, b — системні панелі Android

    def set_insets(self, l, t, r, b):
        self.inset = (l, t, r, b)
        self._place_bars()
        self._on_resize()

    def _place_bars(self, *_):
        """Верхня і нижня панелі меню лежать у межах безпечної зони."""
        l, t, r, b = self.inset
        w, h = max(1, self.width), max(1, self.height)
        for bar, hint in ((self.top_bar, {'x': l / w, 'top': 1 - t / h}),
                          (self.bottom_bar, {'x': l / w, 'y': b / h})):
            bar.size_hint_x = max(0.1, (w - l - r) / w)
            bar.pos_hint = hint

    def __init__(self, app, **kw):
        super().__init__(**kw)
        self.app = app
        self.book = None
        self.entry = None
        self.pages, self.page_pos = [], []
        self.chap_blocks = []
        self.idx = 0
        self.turns = 0
        self.menu_visible = False
        self.faces = None
        self.geo = None
        self.col_x = [0]
        self.page_top = 0
        self._pag_ev = self._save_ev = None
        self._pagination_key = None
        self._words = []              # слова поточної сторінки: (x0, y0, x1, y1, блок, від, до)
        self.sel = None               # виділення: діапазон індексів у _words
        self._hl_idx = {}
        self._anchor = 0

        self.root_f = BgFloat()
        self.add_widget(self.root_f)
        self.page = Widget()
        self.root_f.add_widget(self.page)
        self.foot_l = Label(font_size=sp(12), halign='left', valign='middle',
                            size_hint=(None, None))
        self.foot_r = Label(font_size=sp(12), halign='right', valign='middle',
                            size_hint=(None, None))
        self.root_f.add_widget(self.foot_l)
        self.root_f.add_widget(self.foot_r)

        self._flash = Widget()
        with self._flash.canvas:
            self._flash_c = Color(0, 0, 0, 1)
            self._flash_rect = Rectangle(pos=self._flash.pos, size=self._flash.size)
        self._flash.bind(pos=lambda w, v: setattr(self._flash_rect, 'pos', v),
                         size=lambda w, v: setattr(self._flash_rect, 'size', v))

        self._build_menu()
        self._build_sel_bar()
        self.bind(size=self._on_resize)
        self.bind(size=self._place_bars)
        self._place_bars()

    def apply_theme(self):
        bg, fg = self.app.colors
        self.root_f.set_bg(bg)
        for bar in (self.top_bar, self.bottom_bar):
            bar.set_bg(bg)
        self.top_rule.set_color(fg)
        self.bottom_rule.set_color(fg)
        self.restyle_sel_bar(bg, fg)
        self.seek.set_color(fg)
        for w in [self.back_btn, self.title_lbl, self.toc_btn] + list(self.btns.values()):
            w.color = fg
        self.foot_l.color = self.foot_r.color = (fg[0], fg[1], fg[2], 0.8)
        self._flash_c.rgba = (0, 0, 0, 1)
        self._refresh_menu_labels()
        if self.pages:
            self.render()

    # ---------- відкриття
    def open(self, entry, book):
        self.entry = entry
        self.book = book
        self.pages, self.page_pos = [], []
        self.chap_blocks = [b for _, b in book.chapters]
        # «справжні» сторінки: стала довжина (знаків), не залежить від шрифту й екрана
        self.cum, tot = [], 0
        for k, t in book.blocks:
            self.cum.append(tot)
            tot += len(t) if k in 'hpv' else 0
        self.total_chars = tot
        self.real_total = max(1, -(-tot // PAGE_CH))
        self.pl_blocks = [b for _, b in book.pagelist]
        self.turns = 0
        self._pagination_key = None
        self.show_menu(False)
        self.clear_selection(render=False)
        self._rebuild_hl()
        self.apply_theme()
        self._schedule_paginate(0.05, (entry.get('block', 0), entry.get('off', 0)))

    # ---------- верстка
    def _on_resize(self, *_):
        if self.book:
            self._schedule_paginate(0.25, self.cur_pos())

    def _schedule_paginate(self, delay, pos):
        if self._pag_ev:
            self._pag_ev.cancel()
        self._pag_ev = Clock.schedule_once(lambda dt: self.paginate(pos), delay)

    def cur_pos(self):
        if self.page_pos:
            return self.page_pos[self.idx]
        return (self.entry.get('block', 0), self.entry.get('off', 0)) if self.entry else (0, 0)

    def relayout(self):
        self.paginate(self.cur_pos())

    def paginate(self, target=None):
        if not self.book or self.width < 60 or self.height < 60:
            return
        p = self.app.prefs
        il, it, ir, ib = self.inset
        W, H = self.width - il - ir, self.height - it - ib      # безпечна зона
        fam = fonts.SERIF if (p['font'] == 'serif' and fonts.SERIF) else 'Roboto'
        key = (fam, p['font_size'], p['bold'])
        if self.faces is None or self._pagination_key != key:
            self.faces = Faces(fam, sp(p['font_size']), p['bold'])
            self._pagination_key = key
        faces = self.faces

        # адаптивна геометрія: поля у % від ширини, обмежена довжина рядка, 2 колонки на широких екранах
        mx = max(dp(10), W * MARGINS[p['margin']])
        self._margin = mx                     # ширина поля: у ньому малюється стрічка закладки
        avail_w = W - 2 * mx
        max_col = faces.fs * 34
        gutter = max(dp(24), mx)
        if W > H * 1.2 and avail_w >= faces.fs * 44:
            n_cols = 2
            col_w = min(max_col, (avail_w - gutter) / 2)
        else:
            n_cols = 1
            col_w = min(max_col, avail_w)
        total = n_cols * col_w + (n_cols - 1) * gutter
        x0 = (W - total) / 2
        self.col_x = [x0 + i * (col_w + gutter) for i in range(n_cols)]

        base_lh = faces.line_height() * p['spacing']
        top_pad = max(dp(14), H * 0.02)
        avail_h = H - top_pad - self.FOOTER_H
        rows = max(3, int(avail_h // base_lh))
        lh = min(avail_h / rows, base_lh * 1.18)       # однакова сітка рядків на кожній сторінці
        self.page_top = H - top_pad - (avail_h - rows * lh) / 2

        self.geo = Geometry(col_w, n_cols, rows, lh, faces.fs * 1.4,
                            faces.space[False], faces.space[True], p['hyph'])
        self._foot_geo = (il + x0, ib + dp(3), total)
        self._layout_foot()
        self.page.pos, self.page.size = (il, ib), (W, H)

        pages, pos = typeset(self.book.blocks, set(self.chap_blocks),
                             self.book.img_sizes, self.geo, faces.width)
        self.pages, self.page_pos = pages, pos
        target = tuple(target or (0, 0))
        self.idx = max(0, bisect_right(self.page_pos, target) - 1)
        self.apply_theme()
        self.render()

    # ---------- малювання сторінки
    def render(self):
        if not self.pages or not self.geo:
            return
        g, faces = self.geo, self.faces
        bg, fg = self.app.colors
        gray = self.app.prefs['eink']
        justify = self.app.prefs['justify']
        blocks = self.book.blocks
        pv = self.page
        pv.canvas.clear()
        pv.clear_widgets()
        items = self.pages[self.idx]
        only_img = len(items) == 1 and items[0][2][0] == 'i'
        lh = g.lh
        pics = []
        hit = self._words = []
        il, it_, ir, ib = self.inset
        with pv.canvas:
            PushMatrix()
            Translate(il, ib)           # сторінка малюється в безпечній зоні
            Color(*fg)
            for col, row, it in items:
                x_col = self.col_x[col]
                y_top = self.page_top - row * lh
                if it[0] == 'i':
                    _, _bi, path, w, h, _r = it
                    if only_img:
                        y_top = self.page_top - (g.rows * lh - h) / 2
                    pics.append((path, x_col + (g.col_w - w) / 2, y_top - h, w, h))
                    continue
                _, bi, s, e, style, flag = it
                heading = style == 'h'
                spans = None
                if style == 's':
                    words = ['* * *']
                else:
                    text = blocks[bi][1]
                    spans = [(m.start() + s, m.end() + s) for m in _TOKEN.finditer(text[s:e])]
                    words = [text[a:b] for a, b in spans]
                    if flag & 1 and words:
                        words[-1] += '-'
                if not words:
                    continue
                widths = [faces.width(wd, heading) for wd in words]
                space = faces.space[heading]
                if heading or style == 's':
                    line_w = sum(widths) + space * (len(words) - 1)
                    xs = [(g.col_w - line_w) / 2 + sum(widths[:i]) + space * i
                          for i in range(len(words))]
                    x_start = x_col
                else:
                    indent = g.indent if style == 'p0' else 0
                    x_start = x_col + indent
                    if justify and style in ('p0', 'p') and not flag & 2:
                        xs = justify_positions(words, widths, g.col_w - indent, space)
                    else:
                        xs = [sum(widths[:i]) + space * i for i in range(len(words))]
                marks = [self._mark(bi, a, b, len(hit) + i) for i, (a, b) in enumerate(spans)] if spans else []
                for k, (wd, x) in enumerate(zip(words, xs)):
                    tex = faces.texture(wd, heading)
                    y = y_top - lh / 2 - tex.height / 2
                    wx = round(x_start + x)
                    if spans:
                        hit.append((wx + il, y_top - lh + ib, wx + widths[k] + il, y_top + ib,
                                    bi, spans[k][0], spans[k][1]))
                        if marks[k]:                       # підкладка: виділення зливається між сусідніми словами
                            wide = widths[k] + (space if k + 1 < len(marks) and marks[k + 1] == marks[k] else 0)
                            Color(fg[0], fg[1], fg[2], MARK_ALPHA[marks[k]])
                            Rectangle(pos=(wx, round(y_top - lh)), size=(wide, lh))
                            if marks[k] == 1:
                                Rectangle(pos=(wx, round(y_top - lh)), size=(wide, max(1, int(dp(1)))))
                            Color(*fg)
                    Rectangle(texture=tex, pos=(wx, round(y)), size=tex.size)
            # прогрес читання: тонка лінія над підвалом
            n = len(self.pages)
            frac = (self.idx + 1) / n
            x0, tw = self.col_x[0], self.col_x[-1] + g.col_w - self.col_x[0]
            yb = self.FOOTER_H - dp(3)
            th = max(2, int(dp(2)))
            Color(fg[0], fg[1], fg[2], 0.3)
            Rectangle(pos=(x0, yb), size=(tw, 1))
            Color(*fg)
            Rectangle(pos=(x0, yb - th / 2), size=(tw * frac, th))
            if self.has_bookmark():               # стрічка закладки в правому верхньому куті
                mx = getattr(self, '_margin', dp(16))
                rw, rh = max(dp(8), min(dp(16), mx - dp(2))), dp(40)     # стрічка лежить у полі, текст не затуляє
                xr, ytop = self.width - il - ir - rw, self.height - it_ - ib     # безпечна зона, не весь віджет
                Color(*fg)
                Rectangle(pos=(xr, ytop - rh), size=(rw, rh))
                Color(*bg)
                Triangle(points=[xr, ytop - rh, xr + rw / 2, ytop - rh + dp(10), xr + rw, ytop - rh])
            PopMatrix()
        for path, x, y, w, h in pics:
            pv.add_widget(Pic(path, gray=gray, pos=(round(x + il), round(y + ib)), size=(w, h),
                              size_hint=(None, None)))

        n = len(self.pages)
        pct = int(round(100 * (self.idx + 1) / n))
        self.foot_l.text = self.chapter_at(self.page_pos[self.idx][0])
        self.foot_l.shorten = True
        self.foot_l.shorten_from = 'right'
        mode = counter.effective(self.app.prefs['counter'], bool(self.book.pagelist))
        self.foot_r.text = counter.footer(mode, self._counter_data(pct))
        self.entry['pct'] = pct

    def _layout_foot(self):
        """Підписи внизу: назва розділу ліворуч, прогрес праворуч (довгий підпис — ширше місце)."""
        geo = getattr(self, '_foot_geo', None)
        if not geo:
            return
        x, y, total = geo
        wide = self.app.prefs['counter'] in ('time', 'chapter')
        share = 0.56 if wide else 0.34
        self.foot_l.size = (total * (1 - share), dp(24))
        self.foot_l.text_size = self.foot_l.size
        self.foot_l.pos = (x, y)
        self.foot_r.size = (total * share, dp(24))
        self.foot_r.text_size = self.foot_r.size
        self.foot_r.pos = (x + total - self.foot_r.width, y)

    def _counter_data(self, pct):
        """Числа для підпису прогресу (див. counter.footer)."""
        n, idx = len(self.pages), self.idx
        b0, off0 = self.page_pos[idx]
        pos = (self.cum[b0] + off0) if self.cum else 0
        d = {'pct': pct, 'idx': idx + 1, 'n': n, 'real_total': self.real_total,
             'real': min(self.real_total, pos // PAGE_CH + 1), 'label': None, 'label_total': 0}
        if self.book.pagelist:
            j = bisect_right(self.pl_blocks, b0) - 1
            d['label'] = self.book.pagelist[j if j >= 0 else 0][0]
            d['label_total'] = self.book.page_total
        cb = self.chap_blocks
        ci = bisect_right(cb, b0) - 1
        start = bisect_left(self.page_pos, (cb[ci], 0)) if ci >= 0 else 0
        if ci + 1 < len(cb):
            end = bisect_left(self.page_pos, (cb[ci + 1], 0))
            end_chars = self.cum[min(cb[ci + 1], len(self.cum) - 1)] if self.cum else 0
        else:
            end, end_chars = n, self.total_chars
        d.update(ch_page=max(1, idx - start + 1), ch_total=max(1, end - start, idx - start + 1),
                 left=max(0, end_chars - pos), multi=len(cb) > 1)
        return d

    def _mark(self, bi, a, b, n):
        """0 — звичайне слово, 1 — збережене виділення, 2 — поточне виділення."""
        if self.sel and self.sel[0] <= n <= self.sel[1]:
            return 2
        return 1 if notes.overlaps(self._hl_idx, bi, a, b) else 0

    # ---------- гортання
    def _go(self, idx, flash=True):
        idx = max(0, min(len(self.pages) - 1, idx))
        if idx == self.idx:
            return
        self.clear_selection(render=False)
        self.idx = idx
        self.turns += 1
        p = self.app.prefs
        self.render()
        if flash and p['eink'] and p['flash_every'] and self.turns % p['flash_every'] == 0:
            self._do_flash()
        self.seek.set(idx, len(self.pages) - 1)
        self._queue_save()

    def _do_flash(self):
        """Повне оновлення, як в e-ink: чорний, потім білий спалах проти «привидів»."""
        bg = self.app.colors[0]
        self._flash_c.rgba = (0, 0, 0, 1) if bg[0] > 0.3 else (1, 1, 1, 1)
        self.root_f.add_widget(self._flash)
        Clock.schedule_once(lambda dt: setattr(self._flash_c, 'rgba', bg), 0.09)
        Clock.schedule_once(lambda dt: self.root_f.remove_widget(self._flash), 0.16)

    def next_page(self):
        self._go(self.idx + 1)

    def prev_page(self):
        self._go(self.idx - 1)

    def _seek_preview(self, v):
        n = len(self.pages)
        self.foot_r.text = '%d / %d  ·  %d%%' % (v + 1, n, int(round(100 * (v + 1) / n)))

    def _seek_done(self, v):
        self._go(int(v), flash=False)

    def go_to_block(self, block):
        self._go(max(0, bisect_right(self.page_pos, (block, 0)) - 1), flash=False)

    def _queue_save(self):
        if self.page_pos:
            self.entry['block'], self.entry['off'] = self.page_pos[self.idx]
            self.entry['t'] = time.time()
        if self._save_ev:
            self._save_ev.cancel()
        self._save_ev = Clock.schedule_once(lambda dt: self.app.save_state(), 0.8)
