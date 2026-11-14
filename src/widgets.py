"""Загальні віджети Kivy: фон, лінії, кнопки, повзунок, картинки, кеш текстур слів."""
import logging
import os
import sys

from kivy.core.image import Image as CoreImage
from kivy.core.text import Label as CoreLabel
from kivy.effects.scroll import ScrollEffect
from kivy.graphics import Color, Rectangle, RenderContext
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

log = logging.getLogger(__name__)


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
            except Exception as e:  # noqa: BLE001 — помилки GL/шейдера в Kivy не мають спільного типу
                log.warning('шейдер відтінків сірого недоступний: %s', e)
                gray_ok = False
        super().__init__(**kw)
        try:
            self._tex = CoreImage(source).texture
        except Exception as e:  # noqa: BLE001 — декодери зображень Kivy кидають різні типи
            log.warning('не вдалося завантажити зображення %s: %s', source, e)
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
