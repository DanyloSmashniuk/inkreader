"""Налаштування читалки: шрифт, інтервал, поля, режими."""


import counter
import fonts
from config import FLASH_CYCLE, MARGINS, SPACINGS


class SettingsMixin:
    """Примішується до ReaderScreen."""

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
        if fonts.SERIF:
            p['font'] = 'sans' if p['font'] == 'serif' else 'serif'
        self._apply(relayout=True)

    def toggle_bold(self):
        p = self.app.prefs
        p['bold'] = not p['bold']
        self._apply(relayout=True)

    def cycle_counter(self):
        p = self.app.prefs
        p['counter'] = counter.next_mode(p['counter'], bool(self.book and self.book.pagelist))
        self._layout_foot()
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
