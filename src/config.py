"""Константи й налаштування за замовчуванням, палітра. Без Kivy — легко перевіряти тестами."""

DATA_VERSION = 3                      # змінюється, коли міняється верстка/нормалізація

# ----------------------------------------------------------------- налаштування

DEFAULT_PREFS = {'font_size': 20, 'theme': 'light', 'eink': True, 'font': 'serif',
                 'flash_every': 6, 'spacing': 1.3, 'margin': 1,
                 'justify': True, 'hyph': True, 'bold': False, 'counter': 'book'}
SPACINGS = [1.15, 1.3, 1.45, 1.6]
MARGINS = [0.03, 0.055, 0.085]
MARGIN_NAMES = ['вузькі', 'середні', 'широкі']
FLASH_CYCLE = [0, 1, 3, 6, 10, 20]
VIEWS = [(True, 'light'), (True, 'dark'), (False, 'light'), (False, 'dark')]


def palette(prefs):
    dark = prefs['theme'] == 'dark'
    if prefs['eink']:      # чисто чорне на «папері» e-ink (або навпаки)
        return ((0, 0, 0, 1), (0.93, 0.93, 0.93, 1)) if dark else \
               ((0.90, 0.90, 0.88, 1), (0, 0, 0, 1))
    return ((0.07, 0.07, 0.08, 1), (0.82, 0.82, 0.80, 1)) if dark else \
           ((0.965, 0.95, 0.915, 1), (0.13, 0.12, 0.11, 1))
