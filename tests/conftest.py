"""Невеликі книги для тестів: створюються на льоту, без зовнішніх файлів."""
import zipfile

import pytest

PARAS = [
    "Станція називалася Вишневе, хоча жодного вишневого дерева Марта там не побачила.",
    "Поштова контора містилася в приміщенні колишньої водокачки.",
    "Всередині пахло сургучем, мокрою вовною й чаєм із чебрецем.",
]
CHAPTERS = ["Нічний потяг", "Станція Вишневе", "Хата край дороги"]


@pytest.fixture
def fb2_path(tmp_path):
    body = "".join(
        "<section><title><p>%s</p></title>%s</section>"
        % (name, "".join("<p>%s</p>" % p for p in PARAS))
        for name in CHAPTERS
    )
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0">'
        "<description><title-info><author><first-name>Олена</first-name>"
        "<last-name>Верес</last-name></author><book-title>Нічна пошта</book-title>"
        "<lang>uk</lang></title-info></description><body>%s</body></FictionBook>" % body
    )
    path = tmp_path / "book.fb2"
    path.write_text(xml, encoding="utf-8")
    return str(path)


@pytest.fixture
def epub_path(tmp_path):
    path = tmp_path / "book.epub"
    chapters = "".join(
        '<li><a href="c%d.xhtml">%s</a></li>' % (i, name) for i, name in enumerate(CHAPTERS)
    )
    nav = (
        '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
        '<body><nav epub:type="toc"><ol>%s</ol></nav></body></html>' % chapters
    )
    manifest = '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
    spine = ""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr(
            "META-INF/container.xml",
            '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        for i, name in enumerate(CHAPTERS):
            html = (
                '<html xmlns="http://www.w3.org/1999/xhtml"><body><h1>%s</h1>%s</body></html>'
                % (name, "".join("<p>%s</p>" % p for p in PARAS))
            )
            z.writestr("OEBPS/c%d.xhtml" % i, html)
            manifest += '<item id="c%d" href="c%d.xhtml" media-type="application/xhtml+xml"/>' % (i, i)
            spine += '<itemref idref="c%d"/>' % i
        z.writestr("OEBPS/nav.xhtml", nav)
        z.writestr(
            "OEBPS/content.opf",
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Нічна пошта</dc:title>'
            "<dc:creator>Олена Верес</dc:creator></metadata>"
            "<manifest>%s</manifest><spine>%s</spine></package>" % (manifest, spine),
        )
    return str(path)
