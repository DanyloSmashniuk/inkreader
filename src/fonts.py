"""Вбудований шрифт із засічками: розпаковується в теку користувача й реєструється в Kivy."""
import logging
import os

from kivy.core.text import LabelBase

log = logging.getLogger(__name__)

SERIF = None                           # ім'я вбудованого шрифту з засічками


def setup_fonts(user_dir):
    global SERIF
    try:
        import fontdata
        paths = fontdata.install(os.path.join(user_dir, 'fonts'))
        if paths:
            LabelBase.register(name='Serif', fn_regular=paths[0], fn_bold=paths[1])
            SERIF = 'Serif'
    except (ImportError, OSError, ValueError, IndexError) as e:
        log.warning('вбудований шрифт недоступний: %s', e)
        SERIF = None
