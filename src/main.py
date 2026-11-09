"""InkReader: читалка EPUB/FB2 з режимом «електронні чорнила» (Kivy).

Верстку сторінок робить typeset.py, чистку «кривих» файлів — textfix.py,
переноси слів — hyph.py. Тут: інтерфейс, малювання сторінки, налаштування.
"""
import json
import os
import shutil
import sys
import time
from bisect import bisect_right

os.environ.setdefault('SDL_VIDEO_X11_WMCLASS', 'InkReader')   # збігається з StartupWMClass ярлика

from kivy.app import App
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.core.text import Label as CoreLabel, LabelBase
from kivy.core.window import Window
from kivy.effects.scroll import ScrollEffect
from kivy.graphics import Color, Rectangle, RenderContext
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import NoTransition, Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.utils import escape_markup, platform

from book_loader import SUPPORTED_EXTS, load_book
from typeset import Geometry, justify_positions, typeset

DATA_VERSION = 3                      # змінюється, коли міняється верстка/нормалізація

# ----------------------------------------------------------------- налаштування

DEFAULT_PREFS = {'font_size': 20, 'theme': 'light', 'eink': True, 'font': 'serif',
                 'flash_every': 6, 'spacing': 1.3, 'margin': 1,
                 'justify': True, 'hyph': True, 'bold': False, 'book_pages': True}
SPACINGS = [1.15, 1.3, 1.45, 1.6]
MARGINS = [0.03, 0.055, 0.085]
MARGIN_NAMES = ['вузькі', 'середні', 'широкі']
FLASH_CYCLE = [0, 1, 3, 6, 10, 20]
VIEWS = [(True, 'light'), (True, 'dark'), (False, 'light'), (False, 'dark')]

SERIF = None                           # ім'я вбудованого шрифту з засічками


def setup_fonts(user_dir):
    global SERIF
    try:
        import fontdata
        paths = fontdata.install(os.path.join(user_dir, 'fonts'))
        if paths:
            LabelBase.register(name='Serif', fn_regular=paths[0], fn_bold=paths[1])
            SERIF = 'Serif'
    except Exception:
        SERIF = None


def palette(prefs):
    dark = prefs['theme'] == 'dark'
    if prefs['eink']:      # чисто чорне на «папері» e-ink (або навпаки)
        return ((0, 0, 0, 1), (0.93, 0.93, 0.93, 1)) if dark else \
               ((0.90, 0.90, 0.88, 1), (0, 0, 0, 1))
    return ((0.07, 0.07, 0.08, 1), (0.82, 0.82, 0.80, 1)) if dark else \
           ((0.965, 0.95, 0.915, 1), (0.13, 0.12, 0.11, 1))


# --------------------------------------------------------------------- віджети

class Bg:
    def init_bg(self, color):
        with self.canvas.before:
            self._bgc = Color(*color)
            self._bgr = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd_bg, size=self._upd_bg)

    def _upd_bg(self, *_):
        self._bgr.pos = self.pos
        self._bgr.size = self.size

    def set_bg(self, color):
        self._bgc.rgba = color


class BgBox(Bg, BoxLayout):
    def __init__(self, color=(0, 0, 0, 1), **kw):
        BoxLayout.__init__(self, **kw)
        self.init_bg(color)


class BgFloat(Bg, FloatLayout):
    def __init__(self, color=(0, 0, 0, 1), **kw):
        FloatLayout.__init__(self, **kw)
        self.init_bg(color)


class Rule(Widget):
    """Тонка лінія-розділювач (замість заливки великих областей)."""

    def __init__(self, color=(0, 0, 0, 1), thick=2, **kw):
        kw.setdefault('size_hint_y', None)
        kw['height'] = max(1, int(dp(thick)))
        super().__init__(**kw)
        with self.canvas:
            self._c = Color(*color)
            self._r = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._upd, size=self._upd)

    def _upd(self, *_):
        self._r.pos, self._r.size = self.pos, self.size

    def set_color(self, color):
        self._c.rgba = color


def flat_button(text, cb, color=(0, 0, 0, 1), **kw):
    """Плоска кнопка: без фону, анімацій і підсвічування натискання."""
    b = Button(text=text, background_normal='', background_down='',
               background_color=(0, 0, 0, 0), color=color, halign='center',
               on_release=lambda *_: cb(), **kw)
    return b


def make_scroll(fg):
    """Список, який гортається колесом, пальцем і перетягуванням смуги справа (важливо для DeX)."""
    return ScrollView(effect_cls=ScrollEffect, bar_width=dp(10), bar_color=fg,
                      bar_inactive_color=(fg[0], fg[1], fg[2], 0.45),
                      scroll_type=['bars', 'content'], scroll_wheel_distance=dp(90))


def scroll_by(sv, px):
    """Зсуває список на px пікселів: додатне значення вгору, від'ємне вниз."""
    child = sv.children[0] if sv.children else None
    room = (child.height - sv.height) if child else 0
    if room > 0:
        sv.scroll_y = min(1.0, max(0.0, sv.scroll_y + px / room))


class RowButton(Button):
    def __init__(self, **kw):
        super().__init__(markup=True, halign='left', valign='middle',
                         background_normal='', background_down='',
                         background_color=(0, 0, 0, 0), **kw)
        self.bind(size=lambda w, s: setattr(w, 'text_size', (s[0] - dp(12), s[1])))


def _icon_path():
    base = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'icon.png')


ICON_PATH = _icon_path()
PAGE_CH = 1800   # знаків на одну «сторінку» документа


class SeekBar(Widget):
    """Однотонний повзунок для e-ink: тонка лінія, заповнена частина, квадратний «язичок»."""

    def __init__(self, on_change, on_preview=None, **kw):
        super().__init__(**kw)
        self.on_change, self.on_preview = on_change, on_preview
        self.vmax, self.value = 1, 0
        self.fg = (0, 0, 0, 1)
        self._drag = False
        self.bind(pos=self._draw, size=self._draw)

    def set(self, value, vmax):
        if not self._drag:
            self.value, self.vmax = value, max(1, vmax)
            self._draw()

    def set_color(self, fg):
        self.fg = fg
        self._draw()

    def _draw(self, *_):
        self.canvas.clear()
        pad = dp(14)
        w = max(1, self.width - 2 * pad)
        cx = self.x + pad + w * (self.value / self.vmax)
        cy = self.center_y
        th = max(2, int(dp(2)))
        k = dp(16)
        with self.canvas:
            Color(self.fg[0], self.fg[1], self.fg[2], 0.35)
            Rectangle(pos=(self.x + pad, cy - th / 2), size=(w, th))
            Color(*self.fg)
            Rectangle(pos=(self.x + pad, cy - th), size=(cx - self.x - pad, th * 2))
            Rectangle(pos=(cx - k / 2, cy - k / 2), size=(k, k))

    def _from_x(self, x):
        pad = dp(14)
        frac = min(1.0, max(0.0, (x - self.x - pad) / max(1, self.width - 2 * pad)))
        return int(round(frac * self.vmax))

    def on_touch_down(self, t):
        if self.collide_point(*t.pos):
            t.grab(self)
            self._drag = True
            self.value = self._from_x(t.x)
            self._draw()
            if self.on_preview:
                self.on_preview(self.value)
            return True
        return False

    def on_touch_move(self, t):
        if t.grab_current is self:
            self.value = self._from_x(t.x)
            self._draw()
            if self.on_preview:
                self.on_preview(self.value)
            return True
        return False

    def on_touch_up(self, t):
        if t.grab_current is self:
            t.ungrab(self)
            self._drag = False
            self.value = self._from_x(t.x)
            self._draw()
            self.on_change(self.value)
            return True
        return False


_GRAY_FS = '''
$HEADER$
uniform float contrast;
void main(void) {
    vec4 c = frag_color * texture2D(texture0, tex_coord0);
    float g = dot(c.rgb, vec3(0.299, 0.587, 0.114));
    g = clamp((g - 0.5) * contrast + 0.5, 0.0, 1.0);
    gl_FragColor = vec4(g, g, g, c.a);
}
'''


class Pic(Widget):
    """Картинка зі збереженням пропорцій. gray=True: чорно-біла з підвищеним контрастом (e-ink)."""

    def __init__(self, source, gray=False, **kw):
        gray_ok = False
        if gray:
            try:
                ctx = RenderContext(use_parent_projection=True,
                                    use_parent_modelview=True,
                                    use_parent_frag_modelview=True)
                ctx.shader.fs = _GRAY_FS
                if ctx.shader.success:
                    self.canvas = ctx
                    gray_ok = True
            except Exception:
                gray_ok = False
        super().__init__(**kw)
        try:
            self._tex = CoreImage(source).texture
        except Exception:
            self._tex = None
        with self.canvas:
            Color(1, 1, 1, 1)
            self._r = Rectangle(texture=self._tex, pos=self.pos, size=self.size)
        if gray_ok:
            self.canvas['contrast'] = 1.3
        self.bind(pos=self._upd, size=self._upd)
        self._upd()

    def _upd(self, *_):
        if not self._tex:
            return
        tw, th = self._tex.size
        k = min(self.width / tw, self.height / th)
        w, h = tw * k, th * k
        self._r.size = (w, h)
        self._r.pos = (self.x + (self.width - w) / 2, self.y + (self.height - h) / 2)


class Faces:
    """Шрифти: вимірювання слів і кеш текстур (слова малюємо по одному — це дає
    рівне вирівнювання по ширині й піксель-в-піксель чіткі позиції)."""

    def __init__(self, family, size, bold=False):
        self.family = family
        self.bold = bold
        self.fs = max(8, int(round(size)))
        self.hfs = int(round(self.fs * 1.14))
        self._w, self._t = {}, {}
        self._m = {False: CoreLabel(font_name=family, font_size=self.fs, bold=bold),
                   True: CoreLabel(font_name=family, font_size=self.hfs, bold=True)}
        self.space = {h: max(2.0, self.width('a a', h) - self.width('aa', h))
                      for h in (False, True)}

    def width(self, word, heading=False):
        k = (word, heading)
        v = self._w.get(k)
        if v is None:
            v = self._m[heading].get_extents(word)[0]
            self._w[k] = v
        return v

    def line_height(self):
        return self._m[False].get_extents('Ay')[1]

    def texture(self, word, heading=False):
        k = (word, heading)
        t = self._t.get(k)
        if t is None:
            lbl = CoreLabel(text=word, font_name=self.family,
                            font_size=self.hfs if heading else self.fs,
                            bold=heading or self.bold, color=(1, 1, 1, 1))
            lbl.refresh()
            t = lbl.texture
            if len(self._t) > 8000:
                self._t.clear()
            self._t[k] = t
        return t


# ------------------------------------------------------------------ бібліотека

class LibraryScreen(Screen):
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

        self.scroll = ScrollView(effect_cls=ScrollEffect, bar_width=dp(10),
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
        self.listbox.clear_widgets()
        if not self.app.library:
            hint = Label(text='Порожньо.\nНатисни «+ Книга» і обери EPUB або FB2.',
                         color=fg, halign='center', size_hint_y=None, height=dp(200))
            hint.bind(size=lambda w, s: setattr(w, 'text_size', (s[0], None)))
            self.listbox.add_widget(hint)
            return
        for entry in self.app.library:
            row = BoxLayout(size_hint_y=None, height=dp(108),
                            padding=(dp(12), dp(8), 0, dp(8)), spacing=dp(8))
            cover = entry.get('cover')
            if cover and os.path.exists(cover):
                thumb = Pic(cover, gray=p['eink'], size_hint_x=None, width=dp(62))
            else:
                thumb = BgBox(color=(fg[0], fg[1], fg[2], 0.15), size_hint_x=None, width=dp(62))
                thumb.add_widget(Label(
                    text='[b]%s[/b]' % escape_markup((entry['title'] or '?')[:1].upper()),
                    markup=True, color=fg, font_size=sp(26)))
            row.add_widget(thumb)
            sub = escape_markup(entry.get('author') or '—')
            btn = RowButton(text='[b]%s[/b]\n[size=%d]%s  ·  %d%%[/size]' % (
                escape_markup(entry['title']), int(sp(13)), sub, entry.get('pct', 0)),
                color=fg)
            btn.bind(on_release=lambda _w, e=entry: self.app.open_entry(e))
            rm = flat_button('×', lambda e=entry: self.app.remove_entry(e), fg,
                             size_hint_x=None, width=dp(52), font_size=sp(22))
            row.add_widget(btn)
            row.add_widget(rm)
            self.listbox.add_widget(row)
            self.listbox.add_widget(Rule(color=(fg[0], fg[1], fg[2], 0.5), thick=1))


# ---------------------------------------------------------------------- читання

class ReaderScreen(Screen):
    FOOTER_H = dp(34)

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
        self.bind(size=self._on_resize)

    # ---------- меню
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
                                height=dp(228), pos_hint={'x': 0, 'y': 0})
        self.bottom_rule = Rule()
        self.seek = SeekBar(self._seek_done, self._seek_preview, size_hint_y=None,
                            height=dp(44))
        r1 = BoxLayout(size_hint_y=None, height=dp(56))
        r2 = BoxLayout(size_hint_y=None, height=dp(56))
        r3 = BoxLayout(size_hint_y=None, height=dp(56))
        self.btns = {}
        spec = [(r1, 'minus', lambda: self.change_font(-2)),
                (r1, 'plus', lambda: self.change_font(2)),
                (r1, 'spacing', self.cycle_spacing),
                (r1, 'margin', self.cycle_margin),
                (r1, 'font', self.toggle_font),
                (r2, 'eink', self.toggle_eink),
                (r2, 'theme', self.toggle_theme),
                (r2, 'justify', self.toggle_justify),
                (r2, 'hyph', self.toggle_hyph),
                (r2, 'flash', self.cycle_flash),
                (r3, 'bold', self.toggle_bold),
                (r3, 'pages', self.toggle_pages)]
        for parent, key, cb in spec:
            b = flat_button('', cb, font_size=sp(12))
            self.btns[key] = b
            parent.add_widget(b)
        for w in (self.bottom_rule, self.seek, r1, r2, r3):
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

    def _refresh_menu_labels(self):
        p = self.app.prefs
        b = self.btns
        b['minus'].text = 'A−\n%d' % max(8, p['font_size'] - 2)
        b['plus'].text = 'A+\n%d' % (p['font_size'] + 2)
        b['spacing'].text = 'Інтервал\n%.2f' % p['spacing']
        b['margin'].text = 'Поля\n%s' % MARGIN_NAMES[p['margin']]
        b['font'].text = 'Шрифт\n%s' % ('із засічками' if p['font'] == 'serif' and SERIF
                                        else 'без засічок')
        b['eink'].text = 'Режим\n%s' % ('E-ink' if p['eink'] else 'Колір')
        b['theme'].text = 'Тема\n%s' % ('темна' if p['theme'] == 'dark' else 'світла')
        b['justify'].text = 'Вирівнювання\n%s' % ('по ширині' if p['justify'] else 'по лівому')
        b['hyph'].text = 'Переноси\n%s' % ('так' if p['hyph'] else 'ні')
        b['bold'].text = 'Накреслення\n%s' % ('жирне' if p['bold'] else 'звичайне')
        b['pages'].text = 'Сторінки\n%s' % ('за книгою' if p['book_pages'] and self.book
                                            and self.book.pagelist else 'умовні')
        b['flash'].text = 'Оновлення\n%s' % ('вимк.' if not p['flash_every'] else
                                              'щоразу' if p['flash_every'] == 1 else
                                              'кожні %d' % p['flash_every'])

    def apply_theme(self):
        bg, fg = self.app.colors
        self.root_f.set_bg(bg)
        for bar in (self.top_bar, self.bottom_bar):
            bar.set_bg(bg)
        self.top_rule.set_color(fg)
        self.bottom_rule.set_color(fg)
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
        self.real_total = max(1, -(-tot // PAGE_CH))
        self.pl_blocks = [b for _, b in book.pagelist]
        self.turns = 0
        self._pagination_key = None
        self.show_menu(False)
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
        W, H = self.width, self.height
        fam = SERIF if (p['font'] == 'serif' and SERIF) else 'Roboto'
        key = (fam, p['font_size'], p['bold'])
        if self.faces is None or self._pagination_key != key:
            self.faces = Faces(fam, sp(p['font_size']), p['bold'])
            self._pagination_key = key
        faces = self.faces

        # адаптивна геометрія: поля у % від ширини, обмежена довжина рядка, 2 колонки на широких екранах
        mx = max(dp(10), W * MARGINS[p['margin']])
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
        self.foot_l.size = (total * 0.66, dp(24))
        self.foot_l.text_size = self.foot_l.size
        self.foot_l.pos = (x0, dp(3))
        self.foot_r.size = (total * 0.34, dp(24))
        self.foot_r.text_size = self.foot_r.size
        self.foot_r.pos = (x0 + total - self.foot_r.width, dp(3))
        self.page.pos, self.page.size = (0, 0), (W, H)

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
        fg = self.app.colors[1]
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
        with pv.canvas:
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
                if style == 's':
                    words = ['* * *']
                else:
                    words = blocks[bi][1][s:e].split()
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
                for wd, x in zip(words, xs):
                    tex = faces.texture(wd, heading)
                    y = y_top - lh / 2 - tex.height / 2
                    Rectangle(texture=tex, pos=(round(x_start + x), round(y)), size=tex.size)
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
        for path, x, y, w, h in pics:
            pv.add_widget(Pic(path, gray=gray, pos=(round(x), round(y)), size=(w, h),
                              size_hint=(None, None)))

        n = len(self.pages)
        pct = int(round(100 * (self.idx + 1) / n))
        ci = bisect_right(self.chap_blocks, self.page_pos[self.idx][0]) - 1
        chap = self.book.chapters[ci][0] if ci >= 0 else ''
        self.foot_l.text = chap
        self.foot_l.shorten = True
        self.foot_l.shorten_from = 'right'
        b0, off0 = self.page_pos[self.idx]
        if self.book.pagelist and self.app.prefs['book_pages']:
            j = bisect_right(self.pl_blocks, b0) - 1
            lab = self.book.pagelist[j][0] if j >= 0 else self.book.pagelist[0][0]
            self.foot_r.text = '%s з %d  ·  %d%%' % (lab, self.book.page_total, pct)
        else:
            real = min(self.real_total, (self.cum[b0] + off0) // PAGE_CH + 1) if self.cum else 1
            self.foot_r.text = '%d з %d  ·  %d%%' % (real, self.real_total, pct)
        self.entry['pct'] = pct

    # ---------- гортання
    def _go(self, idx, flash=True):
        idx = max(0, min(len(self.pages) - 1, idx))
        if idx == self.idx:
            return
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

    # ---------- налаштування
    def _apply(self, relayout=False, rerender=False):
        self.app.save_state()
        self._refresh_menu_labels()
        if relayout:
            self.relayout()
        elif rerender:
            self.render()

    def change_font(self, delta):
        p = self.app.prefs
        p['font_size'] = max(10, min(48, p['font_size'] + delta))
        self._apply(relayout=True)

    def cycle_spacing(self):
        p = self.app.prefs
        i = min(range(len(SPACINGS)), key=lambda k: abs(SPACINGS[k] - p['spacing']))
        p['spacing'] = SPACINGS[(i + 1) % len(SPACINGS)]
        self._apply(relayout=True)

    def cycle_margin(self):
        p = self.app.prefs
        p['margin'] = (p['margin'] + 1) % len(MARGINS)
        self._apply(relayout=True)

    def toggle_font(self):
        p = self.app.prefs
        if SERIF:
            p['font'] = 'sans' if p['font'] == 'serif' else 'serif'
        self._apply(relayout=True)

    def toggle_bold(self):
        p = self.app.prefs
        p['bold'] = not p['bold']
        self._apply(relayout=True)

    def toggle_pages(self):
        p = self.app.prefs
        p['book_pages'] = not p['book_pages']
        self._apply(rerender=True)

    def toggle_justify(self):
        p = self.app.prefs
        p['justify'] = not p['justify']
        self._apply(rerender=True)

    def toggle_hyph(self):
        p = self.app.prefs
        p['hyph'] = not p['hyph']
        self._apply(relayout=True)

    def toggle_eink(self):
        p = self.app.prefs
        p['eink'] = not p['eink']
        self.app.restyle()
        self.app.save_state()

    def toggle_theme(self):
        p = self.app.prefs
        p['theme'] = 'light' if p['theme'] == 'dark' else 'dark'
        self.app.restyle()
        self.app.save_state()

    def cycle_flash(self):
        p = self.app.prefs
        i = FLASH_CYCLE.index(p['flash_every']) if p['flash_every'] in FLASH_CYCLE else 0
        p['flash_every'] = FLASH_CYCLE[(i + 1) % len(FLASH_CYCLE)]
        self._apply()

    # ---------- зміст
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
        box.add_widget(Rule(color=(fg[0], fg[1], fg[2], 0.4), thick=1))
        box.add_widget(nav)
        popup = self.app.make_popup('Зміст', box, (0.94, 0.88))
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
        self._toc_popup, self._toc_scroll = popup, scroll
        popup.bind(on_dismiss=lambda *_: setattr(self, '_toc_scroll', None))

        def focus_current(_dt):
            """Відкриває зміст одразу на поточному розділі."""
            room = lst.height - scroll.height
            if room > 0 and ci > 0:
                y = ci * lst.height / len(chapters) - scroll.height / 2
                scroll.scroll_y = 1.0 - min(1.0, max(0.0, y / room))
        popup.open()
        Clock.schedule_once(focus_current, 0)

    # ---------- навігація / дотики
    def leave(self):
        """Кнопка «Бібліотека»: одразу до бібліотеки (меню закривається само)."""
        self.show_menu(False)
        self.app.save_state()
        self.app.show_library()

    def back(self):
        if self.menu_visible:
            self.show_menu(False)
            return
        self.app.save_state()
        self.app.show_library()

    def on_touch_up(self, touch):
        if super().on_touch_up(touch):
            return True
        if getattr(touch, 'button', '') in ('scrollup', 'scrolldown'):   # колесо миші (DeX, ПК)
            if self.collide_point(*touch.pos):
                self.show_menu(False)
                self.next_page() if touch.button == 'scrollup' else self.prev_page()
                return True
            return False
        if not self.collide_point(*touch.opos):
            return False
        if self.menu_visible and (self.top_bar.collide_point(*touch.opos)
                                  or self.bottom_bar.collide_point(*touch.opos)):
            return True
        dx = touch.pos[0] - touch.opos[0]
        dy = touch.pos[1] - touch.opos[1]
        if abs(dx) > dp(40) and abs(dx) > 1.5 * abs(dy):
            self.show_menu(False)
            self.next_page() if dx < 0 else self.prev_page()
            return True
        if abs(dx) < dp(20) and abs(dy) < dp(20):
            x = touch.opos[0] / max(1, self.width)
            if self.menu_visible:
                self.show_menu(False)
            elif x < 0.3:
                self.prev_page()
            elif x > 0.7:
                self.next_page()
            else:
                self.show_menu(True)
            return True
        return False


# ------------------------------------------------------------------- застосунок

class InkReaderApp(App):
    title = 'InkReader'
    icon = ICON_PATH

    @property
    def colors(self):
        return palette(self.prefs)

    def build(self):
        self.books_dir = os.path.join(self.user_data_dir, 'books')
        os.makedirs(self.books_dir, exist_ok=True)
        self.state_path = os.path.join(self.user_data_dir, 'state.json')
        self.prefs = dict(DEFAULT_PREFS)
        self.library = []
        self._load_state()
        self.desktop = platform in ('linux', 'win', 'macosx')
        self.prefs.pop('win', None)     # старі версії зберігали розмір вікна — це могло виводити його за екран
        setup_fonts(self.user_data_dir)

        self.sm = ScreenManager(transition=NoTransition())   # жодної анімації
        self.library_screen = LibraryScreen(self, name='library')
        self.reader = ReaderScreen(self, name='reader')
        self.sm.add_widget(self.library_screen)
        self.sm.add_widget(self.reader)
        Window.bind(on_keyboard=self._on_key)
        self.show_library()
        return self.sm

    def on_start(self):
        files = [a for a in sys.argv[1:] if a.lower().endswith(SUPPORTED_EXTS) and os.path.isfile(a)]
        if files:                                  # «Відкрити за допомогою» з файлового менеджера
            Clock.schedule_once(lambda dt: self.open_path(files[0]), 0.3)
        if platform == 'android':
            try:
                from android.permissions import Permission, request_permissions
                request_permissions([Permission.READ_EXTERNAL_STORAGE])
            except Exception:
                pass
            try:                                   # екран не гасне під час читання
                from android.runnable import run_on_ui_thread
                from jnius import autoclass

                @run_on_ui_thread
                def keep_on():
                    act = autoclass('org.kivy.android.PythonActivity').mActivity
                    act.getWindow().addFlags(128)
                keep_on()
            except Exception:
                pass

    def on_pause(self):
        self.save_state()
        return True

    def on_stop(self):
        self.save_state()

    # ---------- стан
    def _load_state(self):
        try:
            with open(self.state_path, encoding='utf-8') as f:
                data = json.load(f)
            self.prefs.update(data.get('prefs', {}))
            self.library = [e for e in data.get('library', []) if os.path.exists(e['path'])]
        except Exception:
            pass
        if self.prefs.get('theme') in ('paper', 'eink', 'night'):    # старі версії
            self.prefs['theme'] = 'dark' if self.prefs['theme'] == 'night' else 'light'
            self.prefs['eink'] = True
        for k, v in DEFAULT_PREFS.items():
            self.prefs.setdefault(k, v)

    def save_state(self):
        self.library.sort(key=lambda e: e.get('t', 0), reverse=True)
        try:
            with open(self.state_path, 'w', encoding='utf-8') as f:
                json.dump({'prefs': self.prefs, 'library': self.library}, f, ensure_ascii=False)
        except Exception:
            pass

    # ---------- вигляд
    def restyle(self):
        Window.clearcolor = self.colors[0]
        self.library_screen.refresh()
        self.reader.apply_theme()

    def cycle_view(self):
        p = self.prefs
        cur = (p['eink'], p['theme'])
        i = VIEWS.index(cur) if cur in VIEWS else 0
        p['eink'], p['theme'] = VIEWS[(i + 1) % len(VIEWS)]
        self.save_state()
        self.restyle()

    def make_popup(self, title, content, size_hint=(0.88, 0.4)):
        bg, fg = self.colors
        return Popup(title=title, content=content, size_hint=size_hint, background='',
                     background_color=bg, title_color=fg, separator_color=fg,
                     overlay_color=(0, 0, 0, 0.35), auto_dismiss=True)

    def message(self, title, text):
        lbl = Label(text=text, halign='center', color=self.colors[1])
        lbl.bind(size=lambda w, s: setattr(w, 'text_size', (s[0] - 20, None)))
        self.make_popup(title, lbl).open()

    # ---------- екрани
    def show_library(self):
        self.library_screen.refresh()
        self.sm.current = 'library'
        Window.clearcolor = self.colors[0]

    # ---------- книги
    def cache_dir(self, path):
        return os.path.join(self.user_data_dir, 'cache', os.path.basename(path))

    def pick_file(self):
        if platform == 'android':
            try:
                from plyer import filechooser
                filechooser.open_file(
                    on_selection=lambda sel: Clock.schedule_once(lambda dt: self._picked(sel), 0),
                    filters=[['Книги', '*.epub', '*.fb2', '*.zip']], multiple=False)
                return
            except Exception:
                pass
        self.browse_books()

    def browse_books(self):
        """Власний вибір книги: кроки по теках, швидкі місця, тап по книзі відкриває її."""
        bg, fg = self.colors
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
        popup = self.make_popup('Обери книгу', outer, (0.95, 0.92))
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
                row.bind(on_release=lambda w, full=full: (popup.dismiss(), self._picked([full])))
                lst.add_widget(row)
                lst.add_widget(Rule(fg_soft, 1))
            if not dirs and not files:
                note('Тут немає книг і тек')
            sv.scroll_y = 1

        fg_soft = (fg[0], fg[1], fg[2], 0.25)
        go(state['path'])
        popup.open()

    def _picked(self, selection):
        if selection:
            self.add_book(selection[0])

    def open_path(self, src):
        src = os.path.abspath(src)
        for e in self.library:
            if e.get('src') == src and os.path.exists(e['path']):
                self.open_entry(e)
                return
        self.add_book(src)

    def add_book(self, src):
        dst = os.path.join(self.books_dir, '%d_%s' % (int(time.time() * 1000),
                                                      os.path.basename(src)))
        try:
            shutil.copy2(src, dst)
        except Exception:
            dst = src
        try:
            book = load_book(dst, self.cache_dir(dst))
        except Exception as e:
            if dst != src:
                try:
                    os.remove(dst)
                except OSError:
                    pass
            self.message('Не вдалося відкрити книгу', str(e))
            return
        entry = {'path': dst, 'title': book.title, 'author': book.author,
                 'cover': book.cover, 'block': 0, 'off': 0, 'pct': 0,
                 't': time.time(), 'v': DATA_VERSION, 'src': os.path.abspath(src)}
        self.library.insert(0, entry)
        self.save_state()
        self.open_entry(entry, book)

    def open_entry(self, entry, book=None):
        try:
            book = book or load_book(entry['path'], self.cache_dir(entry['path']))
        except Exception as e:
            self.message('Не вдалося відкрити книгу', str(e))
            return
        if entry.get('v') != DATA_VERSION:      # нормалізація змінила нумерацію блоків
            entry['block'], entry['off'], entry['pct'], entry['v'] = 0, 0, 0, DATA_VERSION
        if book.cover:
            entry['cover'] = book.cover
        entry['t'] = time.time()
        self.reader.open(entry, book)
        self.sm.current = 'reader'
        Window.clearcolor = self.colors[0]

    def remove_entry(self, entry):
        if entry in self.library:
            self.library.remove(entry)
            if entry['path'].startswith(self.books_dir):
                try:
                    os.remove(entry['path'])
                except OSError:
                    pass
                shutil.rmtree(self.cache_dir(entry['path']), ignore_errors=True)
            self.save_state()
            self.library_screen.refresh()

    # ---------- клавіші (кнопка «Назад», апаратні кнопки гортання, клавіатура)
    def _on_key(self, _window, key, *_args):
        if self.sm.current != 'reader':
            return False
        sv = getattr(self.reader, '_toc_scroll', None)
        if sv is not None:                         # відкритий зміст: клавіші гортають його
            page = sv.height * 0.9
            moves = {274: -dp(104), 273: dp(104), 281: -page, 280: page, 32: -page}
            if key == 27:
                self.reader._toc_popup.dismiss()
            elif key in moves:
                scroll_by(sv, moves[key])
            elif key == 278:
                sv.scroll_y = 1.0
            elif key == 279:
                sv.scroll_y = 0.0
            return True
        if key == 27:
            if Window.fullscreen and not self.reader.menu_visible:   # Esc спершу виходить з повного екрана
                Window.fullscreen = False
                return True
            self.reader.back()
            return True
        r = self.reader
        if key in (275, 274, 32, 281, 13, 271):
            r.next_page()
            return True
        if key in (276, 273, 280, 8):
            r.prev_page()
            return True
        if key == 278 and r.pages:                 # Home
            r._go(0, flash=False)
            return True
        if key == 279 and r.pages:                 # End
            r._go(len(r.pages) - 1, flash=False)
            return True
        if key == 292:                             # F11: повний екран
            Window.fullscreen = False if Window.fullscreen else 'auto'
            return True
        if key in (116, 99):                       # T / C: зміст
            r.show_toc()
            return True
        if key == 109:                             # M: меню
            r.show_menu(not r.menu_visible)
            return True
        return False


if __name__ == '__main__':
    InkReaderApp().run()
