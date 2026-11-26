"""Закладки й виділення: чиста логіка без Kivy (легко перевіряється тестами).

Дані лежать у записі книги в бібліотеці:
    entry['bm'] — закладки: {'b': блок, 'o': зсув, 't': час, 'txt': початок сторінки, 'ch': розділ, 'pct': %}
    entry['hl'] — виділення: {'seg': [[блок, від, до], ...], 'txt': текст, 't': час}
Позиція — це (блок, зсув у тексті), а не номер сторінки, тому закладки й виділення
переживають зміну шрифту, полів та розміру екрана.
"""
import time

INF = (float('inf'), 0)


# --------------------------------------------------------------------- закладки

def bookmarks(entry):
    return entry.setdefault('bm', [])


def highlights(entry):
    return entry.setdefault('hl', [])


def page_bookmarks(entry, lo, hi=None):
    """Закладки, що лежать на сторінці [lo, hi): hi=None — остання сторінка."""
    top = hi if hi is not None else INF
    return [b for b in entry.get('bm', ()) if lo <= (b['b'], b['o']) < top]


def toggle_bookmark(entry, lo, hi, make):
    """Є закладка на сторінці — прибирає її, немає — додає (make() повертає новий запис).
    Повертає True, якщо закладку додано."""
    here = page_bookmarks(entry, lo, hi)
    bm = bookmarks(entry)
    if here:
        for b in here:
            bm.remove(b)
        return False
    bm.append(make())
    bm.sort(key=lambda b: (b['b'], b['o']))
    return True


def remove_bookmark(entry, bm):
    if bm in entry.get('bm', ()):
        entry['bm'].remove(bm)


def preview(text, off=0, limit=90):
    """Початок фрагмента одним рядком — підпис до закладки."""
    s = ' '.join(text[off:off + limit * 3].split())
    return s if len(s) <= limit else s[:limit].rstrip() + '…'


# -------------------------------------------------------------------- виділення

def segments(words):
    """words — [(блок, від, до)] у порядку читання → [[блок, від, до]] по одному на блок."""
    out = []
    for b, s, e in words:
        if out and out[-1][0] == b:
            out[-1][1] = min(out[-1][1], s)
            out[-1][2] = max(out[-1][2], e)
        else:
            out.append([b, s, e])
    return out


def selection_text(blocks, segs):
    """Текст виділення: один абзац — один рядок, пробіли нормалізовані."""
    parts = (' '.join(blocks[b][1][s:e].split()) for b, s, e in segs)
    return '\n'.join(p for p in parts if p)


def hl_index(entry):
    """{блок: [(від, до)]} — для швидкої перевірки слів під час малювання сторінки."""
    idx = {}
    for h in entry.get('hl', ()):
        for b, s, e in h['seg']:
            idx.setdefault(b, []).append((s, e))
    return idx


def overlaps(index, b, s, e):
    return any(s < he and e > hs for hs, he in index.get(b, ()))


def _hit(h, segs):
    return any(b == hb and s < he and e > hs
               for b, s, e in segs for hb, hs, he in h['seg'])


def add_highlight(entry, segs, text, now=None):
    """Додає виділення. Точний дублікат ігнорується. Повертає True, якщо додано."""
    segs = [list(s) for s in segs]
    hl = highlights(entry)
    if not segs or any(h['seg'] == segs for h in hl):
        return False
    hl.append({'seg': segs, 'txt': text, 't': now if now is not None else time.time()})
    hl.sort(key=lambda h: (h['seg'][0][0], h['seg'][0][1]))
    return True


def remove_highlights(entry, segs):
    """Знімає всі виділення, що перетинаються з segs. Повертає, скільки знято."""
    hl = entry.get('hl', [])
    gone = [h for h in hl if _hit(h, segs)]
    for h in gone:
        hl.remove(h)
    return len(gone)


def remove_highlight(entry, h):
    if h in entry.get('hl', ()):
        entry['hl'].remove(h)


def hl_start(h):
    b, s, _e = h['seg'][0]
    return (b, s)
