"""Переноси слів.

Кирилиця (українська/російська): правила поділу на склади, без залежностей.
Латиниця: через pyphen, якщо його встановлено (інакше без переносів).

hyph_points(word) -> список позицій, у яких слово можна розірвати (word[:pos] + '-').
"""
import re

_VOWELS = set('аеєиіїоуюяыэёАЕЄИІЇОУЮЯЫЭЁ')
_SOFT = set("ьъ'’ʼ`ЬЪ")            # не відриваємо від попередньої літери
_PUNCT = '«»"“”„‘’\'()[]{}<>.,;:!?…—–-*•'
_CYR = re.compile(r"^[А-Яа-яІіЇїЄєҐґЁёЫыЭэЪъ'’ʼ`]+$")
_LAT = re.compile(r"^[A-Za-z]+$")
MIN_LEFT = 2
MIN_RIGHT = 3

try:                                   # необов'язково
    import pyphen
    _PYPHEN = pyphen.Pyphen(lang='en_US')
except (ImportError, KeyError):
    _PYPHEN = None

_cache: dict[str, list[int]] = {}


def _cyr_points(w):
    n = len(w)
    vowels = [i for i, ch in enumerate(w) if ch in _VOWELS]
    pts = []
    for a, b in zip(vowels, vowels[1:]):
        cons = b - a - 1
        if cons == 0:
            k = a + 1                              # по-ет
        elif cons == 1:
            k = a + 1 if w[a + 1] not in 'йЙ' else a + 2   # ма-ти, ай-да
        else:
            k = a + 2                              # вест-ник, пас-порт
        while k < n and w[k] in _SOFT:             # ь, ъ, апостроф лишаємо зліва
            k += 1
        if MIN_LEFT <= k <= n - MIN_RIGHT and w[k - 1] not in _SOFT:
            pts.append(k)
    return sorted(set(pts))


def _core_points(core):
    if _CYR.match(core):
        return _cyr_points(core)
    if _PYPHEN is not None and _LAT.match(core):
        n = len(core)
        return [p for p in _PYPHEN.positions(core) if MIN_LEFT <= p <= n - MIN_RIGHT]
    return []


def hyph_points(word):
    """Позиції можливих переносів у слові (з урахуванням лапок/розділових знаків по краях)."""
    r = _cache.get(word)
    if r is not None:
        return r
    lead = len(word) - len(word.lstrip(_PUNCT))
    core = word.strip(_PUNCT)
    if len(core) < 5 or not core.isalpha() and not _CYR.match(core):
        r = []
    elif core.isupper():
        r = []
    else:
        r = [lead + p for p in _core_points(core)]
    if len(_cache) > 50000:
        _cache.clear()
    _cache[word] = r
    return r
