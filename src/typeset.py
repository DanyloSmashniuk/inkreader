"""Верстка сторінок: єдина сітка рядків, вирівнювання по ширині, переноси, колонки.

Модуль не залежить від Kivy: вимірювання слів приходить ззовні (функція width).

    geo = Geometry(col_w, n_cols, rows, lh, indent, space_body, space_head, hyph)
    pages, pos = typeset(blocks, chapter_blocks, img_sizes, geo, width)

pages[i] — список (колонка, рядок, елемент) у порядку читання. Елемент:
    ('t', блок, початок, кінець, стиль, прапорці)   рядок тексту
        стиль: 'h' заголовок, 's' роздільник сцен, 'p0' перший рядок абзацу, 'p' інші
        прапорці: 1 — наприкінці рядка перенос, 2 — не вирівнювати по ширині
    ('i', блок, шлях, ширина, висота, рядків)       картинка
pos[i] — позиція (блок, зсув) початку сторінки (для збереження місця читання).

Правила, що роблять сторінки охайними незалежно від документа:
  * усі сторінки на однаковій сітці рядків;
  * немає «висячих» рядків: на початку/в кінці сторінки не лишається один рядок абзацу;
  * заголовок не лишається один унизу сторінки;
  * слово переноситься лише тоді, коли без переносу пробіли розтягнулися б надто сильно,
    і не більше двох переносів підряд;
  * картинка не вища за ~55% сторінки, тож поруч із нею завжди є місце для тексту;
  * підпис («Рис. 12 …») завжди стоїть разом із картинкою;
  * якщо картинка з підписом не влазить унизу, вона переходить на початок наступної
    сторінки, а текст далі заповнює залишок (без порожніх половин сторінки).
"""
import math
import re

from hyph import hyph_points

_TOK = re.compile(r'\S+')
_CAPTION = re.compile(r'^\s*(рис(унок|\.)?|фото(графія)?|іл(юстрація|\.)|ил(люстрация|\.)|схема|діаграма|'
                      r'табл(иця|\.)?|fig(ure|\.)?|photo|image|table|chart)\b', re.I)
IMG_MAX_ROWS = 0.55    # найбільша висота картинки, частка сторінки


class Geometry:
    def __init__(self, col_w, n_cols, rows, lh, indent, space_body, space_head, hyph=True):
        self.col_w = col_w
        self.n_cols = n_cols
        self.rows = rows
        self.lh = lh
        self.indent = indent
        self.space = {False: space_body, True: space_head}
        self.hyph = hyph


def justify_positions(words, widths, avail, space):
    """Зсуви слів у рядку, розтягнутому на ширину avail (надмірні пропуски не розтягуємо)."""
    n = len(words)
    gap = space
    if n > 1:
        g = (avail - sum(widths)) / (n - 1)
        if space * 0.5 <= g <= space * 3.5:
            gap = g
    xs, x = [], 0.0
    for w in widths:
        xs.append(x)
        x += w + gap
    return xs


def typeset(blocks, chapters, img_sizes, geo, width):
    rows, ncols, col_w, lh = geo.rows, geo.n_cols, geo.col_w, geo.lh
    pages, poss = [], []
    cur, col, row, pos0 = [], 0, 0, None
    pending = None          # картинка з підписом, що чекає початку наступної сторінки
    breaks_cache = {}

    # ---------------------------------------------------------------- переноси
    def breaks(tok, hyph):
        key = (tok, hyph)
        r = breaks_cache.get(key)
        if r is None:
            r = []
            n = len(tok)
            for i, c in enumerate(tok):
                if c == '-' and 0 < i < n - 1 and tok[i - 1].isalpha() and tok[i + 1].isalpha():
                    r.append((i + 1, False))                 # після наявного дефіса
            if hyph:
                r += [(p, True) for p in hyph_points(tok) if 0 < p < n]
            r.sort()
            breaks_cache[key] = r
        return r

    def best_break(text, a, b, heading, room, hyph):
        """Найдовший фрагмент слова text[a:b], що влазить у room (разом із дефісом)."""
        if room <= 0:
            return None
        best = None
        for idx, hy in breaks(text[a:b], hyph):
            if width(text[a:a + idx] + ('-' if hy else ''), heading) <= room + 0.01:
                best = (a + idx, hy)
            else:
                break
        return best

    def force_split(text, ls, end, heading, avail, hyph):
        br = best_break(text, ls, end, heading, avail, hyph)
        if br:
            return br
        lo, hi, k = ls + 1, end - 1, ls + 1                  # довге «слово» (URL тощо)
        while lo <= hi:
            mid = (lo + hi) // 2
            if width(text[ls:mid], heading) <= avail:
                k, lo = mid, mid + 1
            else:
                hi = mid - 1
        return k, False

    # ------------------------------------------------------------ розбиття на рядки
    def wrap(text, heading, indent, hyph):
        """[(початок, кінець, перенос)] — рядки абзацу."""
        sp = geo.space[heading]
        out, ls, end, cur_w, nsp, hyrun = [], None, 0, 0.0, 0, 0
        avail = col_w - indent

        def push(k, hy):
            nonlocal avail, hyrun
            out.append((ls, k, hy))
            hyrun = hyrun + 1 if hy else 0
            avail = col_w

        for m in _TOK.finditer(text):
            a, b = m.span()
            wd = width(text[a:b], heading)
            if ls is None:
                ls, end, cur_w, nsp = a, b, wd, 0
            elif cur_w + sp + wd <= avail + 0.01:
                end, cur_w, nsp = b, cur_w + sp + wd, nsp + 1
            else:
                # у скільки разів розтягнуться пробіли, якщо не переносити слово
                stretch = (avail - cur_w) / nsp / sp if nsp else 9.0
                limit = 0.85 if hyrun < 2 else 2.0
                br = (best_break(text, a, b, heading, avail - cur_w - sp, hyph)
                      if stretch > limit else None)
                if br:
                    k, hy = br
                    push(k, hy)
                    ls, end, cur_w, nsp = k, b, width(text[k:b], heading), 0
                else:
                    push(end, False)
                    ls, end, cur_w, nsp = a, b, wd, 0
            while cur_w > avail + 0.01 and end - ls > 1:
                k, hy = force_split(text, ls, end, heading, avail, hyph)
                push(k, hy)
                ls, cur_w, nsp = k, width(text[k:end], heading), 0
        if ls is not None:
            out.append((ls, end, False))
        return out

    # ----------------------------------------------------------------- сторінки
    def flush():
        nonlocal cur, col, row, pos0
        if cur:
            if pos0 is None:
                pos0 = (cur[0][2][1], 0)
            pages.append(cur)
            poss.append(pos0)
        cur, col, row, pos0 = [], 0, 0, None

    def new_col():
        nonlocal col, row
        if col + 1 < ncols:
            col, row = col + 1, 0
        else:
            flush()
        place_pending()

    def put(item, n, pos):
        nonlocal row, pos0
        cur.append((col, row, item))
        row += n
        if pos0 is None and pos is not None:
            pos0 = pos

    def gap(n=1):
        nonlocal row
        if row > 0:
            row = min(rows, row + n)

    def place_par(bi, lines, first_style, justify):
        n, i = len(lines), 0
        while i < n:
            free, remaining = rows - row, n - i
            if remaining <= free:
                take = remaining
            else:
                take = free
                if remaining - take == 1:                    # не лишати один рядок на новій сторінці
                    if take > 2:
                        take -= 1
                    elif row > 0:
                        new_col()
                        continue
                if take < (2 if i == 0 else 1) and row > 0:  # не лишати один рядок унизу
                    new_col()
                    continue
                take = max(1, take)
            for j in range(i, i + take):
                s, e, hy = lines[j]
                style = first_style if j == 0 else 'p'
                flag = (1 if hy else 0) | (2 if (j == n - 1 or not justify) else 0)
                put(('t', bi, s, e, style, flag), 1, (bi, s))
            i += take
            if i < n:
                new_col()

    def place_group(g):
        """Картинка та її підпис (якщо є) — одним шматком."""
        bi, path, w, h, k, cap_bi, cap_lines = g
        put(('i', bi, path, w, h, k), k, None)
        if cap_bi is not None:
            place_par(cap_bi, cap_lines, 'p0', True)

    def place_pending():
        nonlocal pending
        if pending is not None:
            g, pending = pending, None
            place_group(g)

    skip = set()
    for bi, (kind, text) in enumerate(blocks):
        if bi in skip:
            continue
        if kind == 'i':
            size = img_sizes.get(text)
            if not size:
                continue
            sw, sh = size
            scale = min(col_w / sw, IMG_MAX_ROWS * rows * lh / sh, 3.0)
            w, h = sw * scale, sh * scale
            k = min(rows, max(1, int(math.ceil((h + 0.5 * lh) / lh))))
            cap_bi, cap_lines = None, []
            nxt = blocks[bi + 1] if bi + 1 < len(blocks) else None
            if nxt and nxt[0] == 'p' and len(nxt[1]) <= 400 and _CAPTION.match(nxt[1]):
                cap_bi = bi + 1
                cap_lines = wrap(nxt[1], False, geo.indent, geo.hyph)
                skip.add(cap_bi)
            need = k + len(cap_lines)
            if pending is not None:
                new_col()                                    # попередня картинка йде першою
            if row == 0 or rows - row >= need:
                place_group((bi, text, w, h, k, cap_bi, cap_lines))
            else:
                pending = (bi, text, w, h, k, cap_bi, cap_lines)
        elif kind == 's':
            if rows - row < 3:
                new_col()
            gap()
            put(('t', bi, 0, 0, 's', 2), 1, (bi, 0))
            gap()
        elif kind == 'h':
            lines = wrap(text, True, 0, False)
            if bi in chapters:
                if cur:
                    flush()
                if pending is not None:                      # картинка не переходить у наступний розділ
                    place_pending()
                    flush()
                row = 1                                      # повітря над заголовком розділу
            else:
                if row > 0 and rows - row < len(lines) + 4:  # заголовок + ≥2 рядки тексту
                    new_col()
                gap()
            for s, e, _hy in lines:
                put(('t', bi, s, e, 'h', 2), 1, (bi, s))
            gap()
        elif kind == 'v':                                    # рядок вірша: без відступу й вирівнювання
            place_par(bi, wrap(text, False, 0, False), 'p', False)
        else:
            place_par(bi, wrap(text, False, geo.indent, geo.hyph), 'p0', True)
    if pending is not None:
        new_col() if cur else place_pending()
    flush()
    if not pages:
        pages, poss = [[]], [(0, 0)]
    return pages, poss
