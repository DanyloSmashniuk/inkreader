import notes

BLOCKS = [('h', 'Розділ'), ('p', 'Перше речення. Друге   речення\nтретє.'), ('p', 'Інший абзац.')]


def mk(b, o):
    return lambda: {'b': b, 'o': o, 't': 1, 'txt': 'x', 'ch': '', 'pct': 0}


def test_toggle_bookmark_adds_and_removes():
    e = {}
    assert notes.toggle_bookmark(e, (1, 0), (2, 0), mk(1, 0)) is True
    assert notes.page_bookmarks(e, (1, 0), (2, 0))
    assert not notes.page_bookmarks(e, (2, 0), None)
    assert notes.toggle_bookmark(e, (1, 0), (2, 0), mk(1, 0)) is False
    assert e['bm'] == []


def test_bookmark_survives_relayout():
    """Після зміни верстки закладка потрапляє на ту сторінку, що містить її позицію."""
    e = {}
    notes.toggle_bookmark(e, (1, 40), (1, 90), mk(1, 40))
    assert notes.page_bookmarks(e, (1, 0), (1, 100))          # нова верстка: сторінка ширша
    assert not notes.page_bookmarks(e, (1, 90), None)


def test_bookmarks_sorted_and_last_page():
    e = {}
    notes.toggle_bookmark(e, (2, 0), None, mk(2, 5))
    notes.toggle_bookmark(e, (0, 0), (1, 0), mk(0, 0))
    assert [(b['b'], b['o']) for b in e['bm']] == [(0, 0), (2, 5)]
    assert notes.page_bookmarks(e, (2, 0), None)
    notes.remove_bookmark(e, e['bm'][0])
    assert len(e['bm']) == 1


def test_preview_is_one_line_and_cut():
    assert notes.preview(BLOCKS[1][1], 0, 200) == 'Перше речення. Друге речення третє.'
    s = notes.preview('слово ' * 100, 0, 20)
    assert len(s) <= 21 and s.endswith('…')
    assert notes.preview('abc', 1) == 'bc'


def test_segments_merge_by_block():
    words = [(1, 0, 6), (1, 7, 15), (2, 0, 5)]
    assert notes.segments(words) == [[1, 0, 15], [2, 0, 5]]
    assert notes.selection_text(BLOCKS, [[1, 0, 15], [2, 0, 5]]) == 'Перше речення.\nІнший'


def test_highlight_add_dedup_overlap_remove():
    e = {}
    assert notes.add_highlight(e, [[1, 0, 14]], 'Перше речення.', now=5)
    assert not notes.add_highlight(e, [[1, 0, 14]], 'Перше речення.', now=6)    # дублікат
    assert not notes.add_highlight(e, [], '')
    notes.add_highlight(e, [[2, 0, 5]], 'Інший')
    idx = notes.hl_index(e)
    assert notes.overlaps(idx, 1, 3, 8) and notes.overlaps(idx, 1, 13, 20)
    assert not notes.overlaps(idx, 1, 14, 20) and not notes.overlaps(idx, 0, 0, 5)
    assert notes.hl_start(e['hl'][0]) == (1, 0)
    assert notes.remove_highlights(e, [[1, 5, 9]]) == 1            # частковий перетин знімає виділення
    assert len(e['hl']) == 1
    notes.remove_highlight(e, e['hl'][0])
    assert e['hl'] == []
