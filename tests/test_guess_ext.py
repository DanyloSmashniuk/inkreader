from book_loader import guess_ext


def test_guess_by_content(fb2_path, epub_path, tmp_path):
    assert guess_ext(fb2_path) == '.fb2'
    assert guess_ext(epub_path) == '.epub'
    junk = tmp_path / 'x'
    junk.write_bytes(b'hello')
    assert guess_ext(str(junk)) == ''
    assert guess_ext(str(tmp_path / 'missing')) == ''
