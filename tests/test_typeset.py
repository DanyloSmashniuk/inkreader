"""Верстка: картинки з підписами не залишають порожніх сторінок."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from typeset import Geometry, typeset  # noqa: E402

LOREM = ('Це довгий абзац тексту для перевірки верстки, у якому достатньо слів, '
         'щоб зайняти кілька рядків на сторінці. ') * 6


def width(word, heading=False):
    return 8.0 * len(word)


def layout(blocks, sizes, rows=30):
    geo = Geometry(col_w=600.0, n_cols=1, rows=rows, lh=20.0, indent=20.0,
                   space_body=6.0, space_head=7.0, hyph=False)
    return typeset(blocks, set(), sizes, geo, width)


def page_blocks(page):
    return [it[1] for _c, _r, it in page]


def test_caption_stays_with_picture():
    blocks = []
    sizes = {}
    for n in range(8):
        blocks.append(('p', LOREM))
        blocks.append(('i', 'img%d.png' % n))
        blocks.append(('p', 'Рис. %d. Підпис до картинки номер %d' % (n, n)))
        sizes['img%d.png' % n] = (900, 500 + 40 * n)
    pages, pos = layout(blocks, sizes)
    for n in range(8):
        img_bi = 3 * n + 1
        pg = [i for i, p in enumerate(pages) if img_bi in page_blocks(p)]
        cap = [i for i, p in enumerate(pages) if (img_bi + 1) in page_blocks(p)]
        assert pg and cap and pg[0] == cap[0], 'підпис відірвано від картинки %d' % n


def test_pictures_are_not_full_page_and_no_empty_halves():
    blocks = []
    sizes = {}
    for n in range(10):
        blocks.append(('p', LOREM))
        blocks.append(('i', 'a%d.png' % n))
        blocks.append(('p', 'Рис. %d. Підпис' % n))
        sizes['a%d.png' % n] = (1200, 1600)                  # висока картинка
    pages, _pos = layout(blocks, sizes)
    for p in pages[:-1]:
        used = max(r + (it[5] if it[0] == 'i' else 1) for _c, r, it in p)
        assert used >= 0.6 * 30, 'на сторінці лишилась порожня половина'
    for p in pages:
        for _c, _r, it in p:
            if it[0] == 'i':
                assert it[5] <= 0.55 * 30 + 2


def test_text_is_not_lost_and_positions_do_not_decrease():
    blocks = [('p', LOREM), ('i', 'x.png'), ('p', 'Рис. 1. Підпис'), ('p', LOREM),
              ('i', 'y.png'), ('p', LOREM)]
    sizes = {'x.png': (800, 600), 'y.png': (400, 900)}
    pages, pos = layout(blocks, sizes)
    seen = {bi for p in pages for bi in page_blocks(p)}
    assert seen == set(range(len(blocks)))
    assert pos == sorted(pos)
