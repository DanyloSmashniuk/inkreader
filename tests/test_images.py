import struct
import zipfile

import pytest

from book_loader import Book, _image_info, _store_image, load_book


def png(w, h):
    return b"\x89PNG\r\n\x1a\n" + b"\0\0\0\r" + b"IHDR" + struct.pack(">II", w, h) + b"\0" * 8


def gif(w, h):
    return b"GIF89a" + struct.pack("<HH", w, h) + b"\0" * 8


def jpeg(w, h):
    return b"\xff\xd8\xff\xc0" + struct.pack(">H", 17) + b"\x08" + struct.pack(">HH", h, w) + b"\0" * 12


def webp_vp8x(w, h):
    return (b"RIFF" + b"\0" * 4 + b"WEBP" + b"VP8X" + struct.pack("<I", 10) + b"\0" * 4
            + (w - 1).to_bytes(3, "little") + (h - 1).to_bytes(3, "little"))


@pytest.mark.parametrize("data, ext", [
    (png(300, 500), ".png"),
    (gif(300, 500), ".gif"),
    (jpeg(300, 500), ".jpg"),
    (webp_vp8x(300, 500), ".webp"),
])
def test_image_info_reads_format_and_size(data, ext):
    assert _image_info(data) == (ext, 300, 500)


@pytest.mark.parametrize("data", [b"", b"not an image", b"\x89PNG\r\n\x1a\n", b"\xff\xd8", b"RIFF"])
def test_image_info_rejects_unknown_or_truncated_data(data):
    assert _image_info(data) is None


def test_store_image_saves_big_pictures_and_skips_icons(tmp_path):
    book = Book()
    big = _store_image(book, str(tmp_path), "big", png(300, 500))
    icon = _store_image(book, str(tmp_path), "icon", png(16, 16))
    assert big and icon == ""
    assert book.img_sizes[big] == (300, 500)
    assert (tmp_path / big.split("/")[-1]).exists()


def test_store_image_without_directory_ignores_pictures():
    assert _store_image(Book(), None, "x", png(300, 500)) == ""


def test_fb2_inside_zip_is_loaded(fb2_path, tmp_path):
    zpath = tmp_path / "book.fb2.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.write(fb2_path, "book.fb2")
    assert load_book(str(zpath)).title == "Нічна пошта"


def test_zip_without_fb2_is_rejected(tmp_path):
    zpath = tmp_path / "empty.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.writestr("readme.txt", "hello")
    with pytest.raises(ValueError):
        load_book(str(zpath))


def test_unsupported_extension_is_rejected(tmp_path):
    path = tmp_path / "book.pdf"
    path.write_bytes(b"%PDF")
    with pytest.raises(ValueError):
        load_book(str(path))


def test_book_without_text_is_rejected(tmp_path):
    path = tmp_path / "empty.fb2"
    path.write_text('<?xml version="1.0"?><FictionBook><body></body></FictionBook>', encoding="utf-8")
    with pytest.raises(ValueError):
        load_book(str(path))
