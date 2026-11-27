"""Підпис прогресу: режими й форматування (без Kivy)."""
import counter

D = {'pct': 12, 'idx': 7, 'n': 376, 'real': 40, 'real_total': 300, 'label': '33', 'label_total': 410,
     'ch_page': 3, 'ch_total': 12, 'left': 9000, 'multi': True}


def test_footer_modes():
    assert counter.footer('conv', D) == '40 з 300  ·  12%'
    assert counter.footer('book', D) == '33 з 410  ·  12%'
    assert counter.footer('screen', D) == '7 з 376  ·  12%'
    assert counter.footer('chapter', D) == 'у розділі 3 з 12  ·  12%'
    assert counter.footer('pct', D) == '12%'
    assert counter.footer('time', D) == '≈ 8 хв до кінця розділу'
    assert counter.footer('time', dict(D, multi=False)) == '≈ 8 хв до кінця книги'
    assert counter.footer('time', dict(D, left=0)) == 'кінець розділу'
    assert counter.footer('book', dict(D, label=None)) == '40 з 300  ·  12%'     # без друкованих сторінок


def test_minutes_text():
    assert counter.minutes_text(10) == '1 хв'
    assert counter.minutes_text(1200 * 59) == '59 хв'
    assert counter.minutes_text(1200 * 60) == '1 год'
    assert counter.minutes_text(1200 * 125) == '2 год 5 хв'


def test_mode_cycle_skips_book_pages_when_absent():
    seen, mode = [], 'conv'
    for _ in range(6):
        mode = counter.next_mode(mode, False)
        seen.append(mode)
    assert seen == ['screen', 'chapter', 'time', 'pct', 'conv', 'screen']
    assert counter.next_mode('conv', True) == 'book'
    assert counter.effective('book', False) == 'conv' and counter.effective('чужий', True) == 'conv'
