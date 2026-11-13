import pytest

from hyph import hyph_points


@pytest.mark.parametrize("word, expected", [
    ("інформація", [2, 5, 7]),      # ін-фор-ма-ція
    ("привіт", [3]),                # при-віт
])
def test_known_cyrillic_words(word, expected):
    assert hyph_points(word) == expected


@pytest.mark.parametrize("word", ["інформація", "програма", "комп'ютер", "привіт", "підручник"])
def test_points_leave_at_least_two_letters_left_and_three_right(word):
    points = hyph_points(word)
    assert points
    assert all(2 <= p <= len(word) - 3 for p in points)
    assert points == sorted(set(points))


def test_never_leaves_soft_sign_or_apostrophe_at_start_of_next_line():
    for word in ["сільський", "різдвяний", "комп'ютер", "міністерство", "об'єднання"]:
        for p in hyph_points(word):
            assert word[p] not in "ьъ'’ʼ`", (word, p)


def test_punctuation_around_word_shifts_positions():
    assert hyph_points("«інформація»") == [p + 1 for p in hyph_points("інформація")]


def test_short_words_uppercase_and_numbers_are_not_hyphenated():
    assert hyph_points("їж") == []
    assert hyph_points("ІНФОРМАЦІЯ") == []
    assert hyph_points("12345678") == []
    assert hyph_points("") == []


def test_result_is_stable_with_cache():
    assert hyph_points("інформація") == hyph_points("інформація")


def test_latin_words_use_pyphen_when_available():
    pytest.importorskip("pyphen")
    points = hyph_points("information")
    assert points
    assert all(2 <= p <= len("information") - 3 for p in points)


def test_mixed_alphabet_word_is_left_alone():
    assert hyph_points("словоword") == []
