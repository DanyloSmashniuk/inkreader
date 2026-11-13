import pytest
from conftest import CHAPTERS

from book_loader import load_book


def test_fb2_metadata_and_chapters(fb2_path):
    book = load_book(fb2_path)
    assert book.title == "Нічна пошта"
    assert "Верес" in book.author
    assert [title for title, _ in book.chapters] == CHAPTERS


def test_epub_chapter_names_come_from_toc(epub_path):
    book = load_book(epub_path)
    assert book.title == "Нічна пошта"
    assert [title for title, _ in book.chapters] == CHAPTERS


def test_chapter_indexes_point_at_blocks(epub_path):
    book = load_book(epub_path)
    for _title, idx in book.chapters:
        assert 0 <= idx < len(book.blocks)


def test_unknown_format_is_rejected(tmp_path):
    path = tmp_path / "book.txt"
    path.write_text("текст", encoding="utf-8")
    with pytest.raises(ValueError):
        load_book(str(path))
