import pytest

from textfix import clean_text, normalize, polish, remap_chapters


@pytest.mark.parametrize("raw, expected", [
    ("a b c", "a b c"),                      # нерозривний пробіл
    ("a b", "a b"),                       # em space
    ("a\x00b\x07c", "abc"),                    # керівні символи
    ("Так.....", "Так…"),
    ("Привіт -- світе", "Привіт — світе"),
    ("Привіт - світе", "Привіт — світе"),
    ("-Привіт", "— Привіт"),
    ("  багато   пробілів  ", "багато пробілів"),
])
def test_clean_text(raw, expected):
    assert clean_text(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("слово , слово", "слово, слово"),
    ("( дужка )", "(дужка)"),
    ("слово,слово", "слово, слово"),
    ("число 3,5 лишається", "число 3,5 лишається"),
])
def test_polish(raw, expected):
    assert polish(raw) == expected


def test_duplicate_headings_and_images_are_dropped():
    blocks, _ = normalize([("h", "Розділ"), ("h", "Розділ"), ("p", "Текст."),
                           ("i", "a.png"), ("i", "a.png")])
    assert [k for k, _t in blocks] == ["h", "p", "i"]


def test_separators_at_edges_and_next_to_headings_are_removed():
    blocks, _ = normalize([("s", ""), ("p", "Один."), ("s", ""), ("s", ""), ("h", "Назва"),
                           ("p", "Два."), ("s", "")])
    kinds = [k for k, _t in blocks]
    assert kinds[0] != "s" and kinds[-1] != "s"
    assert "ss" not in "".join(kinds)


def test_line_without_letters_becomes_separator():
    blocks, _ = normalize([("p", "Перше."), ("p", "* * *"), ("p", "Друге.")])
    assert [k for k, _t in blocks] == ["p", "s", "p"]


def test_hard_wrapped_file_is_joined_into_paragraphs():
    lines = [("p", "рядок номер %d без крапки" % i) for i in range(40)]
    blocks, firsts = normalize(lines)
    assert len(blocks) == 1
    assert firsts == [0]


def test_hard_wrapped_hyphenated_word_is_glued():
    lines = [("p", "звичайний рядок %d" % i) for i in range(35)]
    lines[10:12] = [("p", "це пере-"), ("p", "нос слова")]
    text = normalize(lines)[0][0][1]
    assert "переніс" not in text and "перенос слова" in text


def test_normal_book_is_not_glued():
    paras = [("p", "Це окреме речення номер %d." % i) for i in range(40)]
    assert len(normalize(paras)[0]) == 40


def test_very_long_paragraph_is_split_on_sentences_without_losing_text():
    sentences = ["Це речення номер %d." % i for i in range(300)]
    blocks, _ = normalize([("p", " ".join(sentences))])
    assert len(blocks) > 1
    assert all(len(t) < 2500 for _k, t in blocks)
    assert " ".join(t for _k, t in blocks) == " ".join(sentences)


def test_short_uppercase_line_becomes_heading():
    body = [("p", "Звичайний абзац із текстом номер %d." % i) for i in range(10)]
    blocks, _ = normalize([("p", "ВЕЛИКА НАЗВА")] + body)
    assert blocks[0] == ("h", "ВЕЛИКА НАЗВА")


def test_empty_blocks_are_dropped():
    assert normalize([("p", "   "), ("p", "​")])[0] == []


def test_remap_chapters_follows_new_indexes_and_merges_duplicates():
    chapters = [("a", 0), ("b", 1), ("c", 5)]
    firsts = [0, 3, 5]
    assert remap_chapters(chapters, firsts, 3) == [("a", 0), ("b", 1), ("c", 2)]
    assert remap_chapters([("a", 1), ("b", 2)], [0, 3], 2) == [("a", 1)]
