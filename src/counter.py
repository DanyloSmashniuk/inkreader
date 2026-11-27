"""Підпис прогресу внизу сторінки: режими й форматування. Чиста логіка без Kivy."""

# (код режиму, назва в налаштуваннях)
COUNTERS = [('conv', 'умовні'), ('book', 'за книгою'), ('screen', 'екранні'),
            ('chapter', 'у розділі'), ('time', 'час до кінця розділу'), ('pct', 'відсотки')]
NAMES = dict(COUNTERS)
CHARS_PER_MIN = 1200          # орієнтовна швидкість читання: ~200 слів на хвилину


def effective(mode, has_book_pages):
    """Режим «за книгою» без друкованих сторінок у файлі показує умовні."""
    if mode not in NAMES:
        mode = 'conv'
    return 'conv' if mode == 'book' and not has_book_pages else mode


def next_mode(mode, has_book_pages):
    modes = [m for m, _ in COUNTERS if m != 'book' or has_book_pages]
    cur = effective(mode, has_book_pages)
    return modes[(modes.index(cur) + 1) % len(modes)]


def minutes_text(chars):
    """Скільки читати за `chars` знаків: «8 хв», «1 год 5 хв»."""
    m = max(1, -(-chars // CHARS_PER_MIN))
    if m < 60:
        return '%d хв' % m
    h, m = divmod(m, 60)
    return '%d год %d хв' % (h, m) if m else '%d год' % h


def footer(mode, d):
    """Текст у правому нижньому куті. d: pct, idx, n, real, real_total, label, label_total,
    ch_page, ch_total, left (знаків до кінця розділу), multi (в книзі кілька розділів)."""
    pct = d['pct']
    if mode == 'book' and d.get('label') is not None:
        return '%s з %d  ·  %d%%' % (d['label'], d['label_total'], pct)
    if mode == 'screen':
        return '%d з %d  ·  %d%%' % (d['idx'], d['n'], pct)
    if mode == 'chapter':
        return 'у розділі %d з %d  ·  %d%%' % (d['ch_page'], d['ch_total'], pct)
    if mode == 'time':
        target = 'розділу' if d['multi'] else 'книги'
        if d['left'] <= 0:
            return 'кінець %s' % target
        return '≈ %s до кінця %s' % (minutes_text(d['left']), target)
    if mode == 'pct':
        return '%d%%' % pct
    return '%d з %d  ·  %d%%' % (d['real'], d['real_total'], pct)
