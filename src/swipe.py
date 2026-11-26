"""Рядок списку зі свайпом: потягнув ліворуч — з-під рядка виходить кнопка «Видалити» (як у Telegram).

Дотик без руху відкриває елемент (on_tap). Відкритий рядок закривається дотиком по ньому,
свайпом праворуч або коли відкривається інший рядок того самого списку. Анімації немає
(екрани e-ink): рядок стрибає у фінальне положення.
"""
from kivy.metrics import dp, sp
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout

DRAG_START = dp(10)       # менший рух вважається дотиком
OPEN_FRACTION = 0.85      # скільки кнопки треба відкрити, щоб рядок лишився відкритим; менше — повертається


class SwipeRow(FloatLayout):
    def __init__(self, content, on_tap, on_delete, colors, group=None, label='Видалити',
                 action_w=None, **kw):
        kw.setdefault('size_hint_y', None)
        super().__init__(**kw)
        bg, fg = colors
        self.content, self.on_tap, self.on_delete = content, on_tap, on_delete
        self.action_w = action_w or dp(108)
        self.offset = 0.0
        self.group = group if group is not None else []     # відкриті рядки списку (щонайбільше один)
        self.action = Button(text=label, size_hint=(None, None), background_normal='',
                             background_down='', background_color=fg, color=bg, bold=True,
                             font_size=sp(15), on_release=lambda *_: self._delete())
        content.size_hint = (None, None)
        self.add_widget(self.action)
        self.add_widget(content)
        self.bind(pos=self._layout, size=self._layout)
        self._layout()

    # ---------- розкладка
    def _layout(self, *_):
        self.action.size = (self.action_w, self.height)
        self.action.pos = (self.right - self.action_w, self.y)
        self.content.size = self.size
        self.content.pos = (self.x + self.offset, self.y)
        self.action.opacity = 1 if self.offset < 0 else 0     # у закритому стані кнопки не видно

    def set_offset(self, value):
        self.offset = min(0.0, max(-self.action_w, value))
        self._layout()

    @property
    def is_open(self):
        return self.offset <= -self.action_w + 1

    def open(self):
        for other in list(self.group):
            if other is not self:
                other.close()
        self.set_offset(-self.action_w)
        if self not in self.group:
            self.group.append(self)

    def close(self):
        self.set_offset(0)
        if self in self.group:
            self.group.remove(self)

    def _delete(self):
        self.close()
        self.on_delete()

    # ---------- дотики
    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos) or getattr(touch, 'button', None) not in (None, 'left'):
            return False
        if self.offset < 0 and self.action.collide_point(*touch.pos):
            return self.action.on_touch_down(touch)
        others = [r for r in self.group if r is not self]
        for other in others:                                  # дотик по іншому рядку лише закриває відкритий
            other.close()
        touch.grab(self)
        touch.ud[id(self)] = {'x0': touch.x, 'off0': self.offset, 'drag': False, 'closed': bool(others)}
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return False
        st = touch.ud.get(id(self))
        if st is None:
            return False
        dx = touch.x - st['x0']
        if not st['drag'] and abs(dx) > DRAG_START:
            st['drag'] = True
        if st['drag']:
            self.set_offset(st['off0'] + dx)
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            if self.offset < 0 and self.action.collide_point(*touch.pos):
                return self.action.on_touch_up(touch)
            return False
        touch.ungrab(self)
        st = touch.ud.pop(id(self), None)
        if st is None:
            return True
        if st['drag']:
            self.open() if self.offset < -self.action_w * OPEN_FRACTION else self.close()
        elif st['off0'] < 0:
            self.close()                                      # дотик по відкритому рядку закриває його
        elif st['closed']:
            pass                                              # цей дотик закрив інший рядок — книгу не відкриваємо
        else:
            self.on_tap()
        return True
