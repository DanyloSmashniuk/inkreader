"""Нормалізація тексту книги: робить «криві» файли однаково читабельними.

normalize(blocks) -> (нові_блоки, firsts)
    blocks: [(kind, text)], kind: 'h' заголовок, 'p' абзац, 'v' рядок вірша,
            's' розділювач, 'i' картинка (text = шлях)
    firsts: для кожного нового блоку індекс першого вихідного блоку (для переносу змісту)
remap_chapters(chapters, firsts, n) -> зміст з новими індексами
"""
import re
import unicodedata
from bisect import bisect_left
from statistics import median

_SPACES = str.maketrans({
    ' ': ' ', ' ': ' ', ' ': ' ', ' ': ' ', ' ': ' ',
    ' ': ' ', ' ': ' ', ' ': ' ', ' ': ' ', ' ': ' ',
    '　': ' ', '\t': ' ', '\r': ' ', '\n': ' ', '\x0b': ' ', '\x0c': ' ',
    ' ': ' ', ' ': ' ',
})
# м'який перенос, нульової ширини символи, керівні символи напрямку тексту
_DROP = dict.fromkeys(map(ord, '­​‌‍⁠﻿‎‏'
                               '‪‫‬‭‮'))
_TERM = re.compile(r'[.!?…:]["»”’)\]]*\s*$')
_SENT = re.compile(r'(?:(?<=[.!?…])|(?<=[.!?…][»”"’)]))\s+(?=["«“—(]?[A-ZА-ЯІЇЄҐ])')
_LEAD_DASH = re.compile(r'^[-–](?=\s|[^\W\d_])\s*')
_LIST_BULLET = ('—', '–', '-', '•', '*', '·')


def clean_text(s):
    s = s.translate(_SPACES).translate(_DROP)
    s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Cc')
    s = re.sub(r'\.{3,}|…{2,}', '…', s)
    s = re.sub(r'\s*--+\s*', ' — ', s)                 # -- → —
    s = re.sub(r'(?<=\s)[-–](?=\s)', '—', s)           # " - " → " — "
    s = ' '.join(s.split())
    s = _LEAD_DASH.sub('— ', s)                        # "-Привіт" → "— Привіт"
    return s.strip()


_SP_BEFORE = re.compile(r'\s+([,.;:!?…)\]»])')
_SP_AFTER_OPEN = re.compile(r'([(\[«])\s+')
_SP_MISSING = re.compile(r'(?<=[^\W\d_])([,;!?])(?=[^\W\d_])')
_DASH_MID = re.compile(r'(?<=\s)[-–](?=\s)')


def polish(t):
    """Дрібні вади, видимі лише після склеювання рядків: «слово , слово», « - » замість тире."""
    t = _SP_BEFORE.sub(r'\1', t)
    t = _SP_AFTER_OPEN.sub(r'\1', t)
    t = _SP_MISSING.sub(r'\1 ', t)
    t = _DASH_MID.sub('—', t)
    return t


def _has_alnum(t):
    return any(ch.isalnum() for ch in t)


def _split_long(t, target=1100, limit=2500):
    """Дуже довгий абзац (зламаний файл) ріжемо по реченнях."""
    if len(t) <= limit:
        return [t]
    out, cur = [], ''
    for sent in _SENT.split(t):
        cur = (cur + ' ' + sent).strip()
        if len(cur) >= target:
            out.append(cur)
            cur = ''
    if cur:
        if out and len(cur) < 200:
            out[-1] += ' ' + cur
        else:
            out.append(cur)
    return out


def normalize(blocks):
    # 1. чистка тексту, розділювачі, порожні блоки
    items = []                                         # [src, kind, text]
    for src, (kind, text) in enumerate(blocks):
        if kind == 'i':
            if items and items[-1][1] == 'i' and items[-1][2] == text:
                continue                                # дубль картинки
            items.append([src, 'i', text])
            continue
        t = clean_text(text)
        if kind == 's' or (t and not _has_alnum(t)):
            items.append([src, 's', ''])
        elif t:
            items.append([src, kind, t])

    # 2. чи файл «жорстко розбитий» на короткі рядки без розділових знаків?
    ps = [it[2] for it in items if it[1] == 'p']
    broken = False
    if len(ps) >= 30:
        term = sum(1 for t in ps if _TERM.search(t))
        broken = term / len(ps) < 0.4 and median(len(t) for t in ps) < 120

    # 3. склеювання рядків одного абзацу
    out = []
    for src, kind, t in items:
        if (broken and kind == 'p' and out and out[-1][1] == 'p'
                and not _TERM.search(out[-1][2]) and not t.startswith(_LIST_BULLET)):
            prev = out[-1][2]
            if prev.endswith('-') and len(prev) > 2 and prev[-2].isalpha() and t[:1].islower():
                out[-1][2] = prev[:-1] + t
            else:
                out[-1][2] = prev + ' ' + t
            continue
        out.append([src, kind, t])

    for it in out:
        if it[1] in ('p', 'h', 'v'):
            it[2] = polish(it[2])

    # 4. короткі рядки ВЕЛИКИМИ літерами — це заголовки
    caps = [it for it in out if it[1] == 'p' and len(it[2]) <= 70 and it[2].isupper()
            and not _TERM.search(it[2]) and not it[2].startswith(_LIST_BULLET)]
    if len(caps) < 0.3 * max(1, len(out)):
        for it in caps:
            it[1] = 'h'

    # 5. дублі заголовків, розділювачі біля заголовків/на краях, довгі абзаци
    fin = []
    for src, kind, t in out:
        if kind == 'h' and fin and fin[-1][1] == 'h' and fin[-1][2] == t:
            continue
        if kind == 's':
            if not fin or fin[-1][1] in ('s', 'h'):
                continue
        if kind == 'h' and fin and fin[-1][1] == 's':
            fin.pop()
        if kind == 'p':
            parts = _split_long(t)
            fin.append([src, 'p', parts[0]])
            for extra in parts[1:]:
                fin.append([src, 'p', extra])
            continue
        fin.append([src, kind, t])
    while fin and fin[-1][1] == 's':
        fin.pop()

    return [(k, t) for _s, k, t in fin], [s for s, _k, _t in fin]


def remap_chapters(chapters, firsts, n):
    out = []
    for title, idx in chapters:
        j = min(bisect_left(firsts, idx), max(0, n - 1))
        if out and out[-1][1] == j:
            continue
        out.append((title, j))
    return out
