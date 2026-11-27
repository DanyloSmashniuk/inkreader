"""Жести й клавіші читалки: гортання, довге натискання (виділення), колесо миші, клавіатура."""
from kivy.core.window import Window
from kivy.metrics import dp

from widgets import scroll_by


class GestureMixin:
    """Примішується до ReaderScreen."""

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

    def on_touch_down(self, touch):
        if super().on_touch_down(touch):
            return True
        self._cancel_long_press()
        if (self.pages and not self.menu_visible and self.collide_point(*touch.pos)
                and getattr(touch, 'button', None) in (None, 'left')
                and not (self.sel and self.sel_bar.collide_point(*touch.pos))):
            self._arm_long_press(touch)
        return False

    def on_touch_move(self, touch):
        if touch.ud.get('selecting'):
            self._extend_selection(touch.pos)
            return True
        if self._lp_touch is touch and (abs(touch.x - touch.ox) > dp(10)
                                        or abs(touch.y - touch.oy) > dp(10)):
            self._cancel_long_press()
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.ud.get('selecting'):                 # палець відпущено після виділення
            touch.ud['selecting'] = False
            self._selection_done()
            return True
        if self._lp_touch is touch:
            self._cancel_long_press()
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
        if self.sel and self.sel_bar.collide_point(*touch.opos):
            return True
        dx = touch.pos[0] - touch.opos[0]
        dy = touch.pos[1] - touch.opos[1]
        if abs(dx) > dp(40) and abs(dx) > 1.5 * abs(dy):
            self.show_menu(False)
            self.next_page() if dx < 0 else self.prev_page()
            return True
        if abs(dx) < dp(20) and abs(dy) < dp(20):
            x = touch.opos[0] / max(1, self.width)
            if self.sel:                              # дотик поза панеллю знімає виділення
                self.clear_selection()
            elif self.menu_visible:
                self.show_menu(False)
            elif x < 0.3:
                self.prev_page()
            elif x > 0.7:
                self.next_page()
            elif not self.tap_highlight(touch.opos):   # дотик по збереженому виділенню — дії над ним
                self.show_menu(True)
            return True
        return False

    def handle_key(self, key):
        sv = getattr(self, '_modal_scroll', None)
        if sv is not None:                         # відкритий зміст чи нотатки: клавіші гортають їх
            page = sv.height * 0.9
            moves = {274: -dp(104), 273: dp(104), 281: -page, 280: page, 32: -page}
            if key == 27:
                self._modal_popup.dismiss()
            elif key in moves:
                scroll_by(sv, moves[key])
            elif key == 278:
                sv.scroll_y = 1.0
            elif key == 279:
                sv.scroll_y = 0.0
            return True
        if self.sel:                               # є виділення: Esc знімає, C копіює, H виділяє
            if key == 27:
                self.clear_selection()
            elif key == 99:
                self.copy_selection()
            elif key == 104:
                self.toggle_highlight()
            return True
        if key == 27:
            if Window.fullscreen and not self.menu_visible:   # Esc спершу виходить з повного екрана
                Window.fullscreen = False
                return True
            self.back()
            return True
        if key in (275, 274, 32, 281, 13, 271):
            self.next_page()
            return True
        if key in (276, 273, 280, 8):
            self.prev_page()
            return True
        if key == 278 and self.pages:                 # Home
            self._go(0, flash=False)
            return True
        if key == 279 and self.pages:                 # End
            self._go(len(self.pages) - 1, flash=False)
            return True
        if key == 292:                             # F11: повний екран
            Window.fullscreen = False if Window.fullscreen else 'auto'
            return True
        if key in (116, 99):                       # T / C: зміст
            self.show_toc()
            return True
        if key == 98:                              # B: закладка поточної сторінки
            self.toggle_bookmark()
            return True
        if key == 110:                             # N: нотатки
            self.show_notes()
            return True
        if key == 115:                             # S: налаштування
            self.show_settings()
            return True
        if key == 109:                             # M: меню
            self.show_menu(not self.menu_visible)
            return True
        return False
