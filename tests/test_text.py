from hyph import hyph_points
from textfix import clean_text, normalize
from typeset import justify_positions


def test_soft_hyphens_and_zero_width_chars_are_removed():
    assert clean_text("до­свідчення​") == "досвідчення"


def test_normalize_keeps_text_and_returns_first_indexes():
    blocks, firsts = normalize([("h", "Розділ"), ("p", "Перший абзац."), ("p", "Другий абзац.")])
    assert [b[1] for b in blocks] == ["Розділ", "Перший абзац.", "Другий абзац."]
    assert len(firsts) >= 3


def test_long_cyrillic_word_has_hyphenation_points():
    points = hyph_points("інформація")
    assert points
    assert all(0 < p < len("інформація") for p in points)


def test_short_word_is_not_hyphenated():
    assert not hyph_points("їж")


def test_justify_stretches_line_to_full_width():
    widths = [40, 40, 40]
    xs = justify_positions(["a", "b", "c"], widths, avail=140, space=5)
    assert xs[0] == 0
    assert round(xs[-1] + widths[-1]) == 140
