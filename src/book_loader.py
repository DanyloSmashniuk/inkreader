"""Завантаження книг EPUB та FB2 (також .fb2.zip) без зовнішніх залежностей.

load_book(path, img_dir=None) -> Book:
    title, author
    blocks   : список (kind, text): 'h' заголовок, 'p' абзац, 'i' картинка (text = шлях до файлу)
    chapters : список (title, індекс_блоку) для змісту
    cover    : шлях до файлу обкладинки або ''
    img_sizes: {шлях_до_картинки: (ширина, висота)}
Картинки зберігаються у img_dir (якщо його не задано, картинки ігноруються).
"""
import base64
import hashlib
import os
import posixpath
import re
import struct
import zipfile
from html.parser import HTMLParser
from urllib.parse import unquote
from xml.etree import ElementTree as ET

from textfix import normalize, remap_chapters

SUPPORTED_EXTS = ('.epub', '.fb2', '.zip')


class Book:
    def __init__(self, title='', author=''):
        self.title = title
        self.author = author
        self.blocks = []
        self.chapters = []
        self.cover = ''
        self.img_sizes = {}
        self.pagelist = []     # [(підпис сторінки, блок)] із самого документа
        self.page_total = 0


def _local(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def _norm(text):
    return ' '.join(text.split())


# ------------------------------------------------------------ картинки

def _image_info(data):
    """Повертає (розширення, ширина, висота) для PNG/JPEG/GIF/WEBP або None."""
    try:
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            w, h = struct.unpack('>II', data[16:24])
            ext = '.png'
        elif data[:6] in (b'GIF87a', b'GIF89a'):
            w, h = struct.unpack('<HH', data[6:10])
            ext = '.gif'
        elif data[:2] == b'\xff\xd8':
            ext, w, h = '.jpg', 0, 0
            i, n = 2, len(data)
            while i + 9 < n:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker == 0xFF:
                    i += 1
                    continue
                if marker in (0x01, 0xD8) or 0xD0 <= marker <= 0xD7:
                    i += 2
                    continue
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    h, w = struct.unpack('>HH', data[i + 5:i + 9])
                    break
                i += 2 + struct.unpack('>H', data[i + 2:i + 4])[0]
        elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
            ext, kind = '.webp', data[12:16]
            if kind == b'VP8 ':
                w = struct.unpack('<H', data[26:28])[0] & 0x3FFF
                h = struct.unpack('<H', data[28:30])[0] & 0x3FFF
            elif kind == b'VP8L':
                b = struct.unpack('<I', data[21:25])[0]
                w, h = (b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1
            elif kind == b'VP8X':
                w = 1 + int.from_bytes(data[24:27], 'little')
                h = 1 + int.from_bytes(data[27:30], 'little')
            else:
                return None
        else:
            return None
    except Exception:
        return None
    if w <= 0 or h <= 0:
        return None
    return ext, w, h


def _store_image(book, img_dir, key, data, min_side=40):
    """Зберігає картинку у img_dir, повертає шлях або ''. Дрібні іконки пропускає."""
    if not img_dir or not data:
        return ''
    info = _image_info(data)
    if not info:
        return ''
    ext, w, h = info
    if max(w, h) < min_side:
        return ''
    path = os.path.join(img_dir, hashlib.sha1(key.encode('utf-8')).hexdigest()[:16] + ext)
    if not os.path.exists(path):
        os.makedirs(img_dir, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data)
    book.img_sizes[path] = (w, h)
    return path


# ---------------------------------------------------------------- EPUB

_SKIP = {'script', 'style', 'head', 'svg'}
_HEADINGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
_BREAKS = {'p', 'div', 'li', 'blockquote', 'pre', 'tr', 'br', 'section',
           'article', 'ul', 'ol', 'table', 'hr', 'dd', 'dt'}
_IMAGES = {'img', 'image'}


class _HtmlText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self._buf = []
        self._skip = 0
        self._h = 0
        self.anchors = {}
        self.pagebreaks = []

    def _anchor(self, attrs):
        d = dict(attrs)
        typ = (d.get('epub:type') or '') + ' ' + (d.get('role') or '')
        if 'pagebreak' in typ:
            lab = (d.get('title') or d.get('aria-label') or '').strip()
            self.pagebreaks.append((lab, len(self.blocks) + (1 if ''.join(self._buf).strip() else 0)))
        for k, v in attrs:
            if k in ('id', 'name') and v and v not in self.anchors:
                self.anchors[v] = len(self.blocks) + (1 if ''.join(self._buf).strip() else 0)

    def _flush(self):
        text = _norm(''.join(self._buf))
        self._buf = []
        text = re.sub(r'(\s*\|\s*)+$', '', text)        # зайві роздільники комірок таблиці
        if text:
            self.blocks.append(('h' if self._h else 'p', text))

    def _img(self, attrs):
        d = dict(attrs)
        src = d.get('src') or d.get('xlink:href') or d.get('href')
        if src:
            self._flush()
            self.blocks.append(('i', src))

    def _hr(self):
        self._flush()
        if not self._skip:
            self.blocks.append(('s', ''))

    def handle_starttag(self, tag, attrs):
        self._anchor(attrs)
        if tag in _IMAGES:
            self._img(attrs)
        elif tag in _SKIP:
            self._skip += 1
        elif tag in _HEADINGS:
            self._flush()
            self._h += 1
        elif tag == 'hr':
            self._hr()
        elif tag == 'li':
            self._flush()
            self._buf.append('• ')
        elif tag in _BREAKS:
            self._flush()

    def handle_startendtag(self, tag, attrs):
        self._anchor(attrs)
        if tag in _IMAGES:
            self._img(attrs)
        elif tag == 'hr':
            self._hr()
        elif tag in _BREAKS:
            self._flush()

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self._skip = max(0, self._skip - 1)
        elif tag in _HEADINGS:
            self._flush()
            self._h = max(0, self._h - 1)
        elif tag in ('td', 'th'):
            self._buf.append(' | ')
        elif tag in _BREAKS:
            self._flush()

    def handle_data(self, data):
        if not self._skip:
            self._buf.append(data)

    def close(self):
        super().close()
        self._flush()


def _zip_read(z, names, base, href):
    href = unquote(href.split('#')[0].split('?')[0])
    full = posixpath.normpath(posixpath.join(base, href))
    if full in names:
        try:
            return full, z.read(full)
        except Exception:
            pass
    return full, None


def _epub_toc(z, names, base, opf, manifest, file_start, anchors):
    """Зміст із самого документа: EPUB3 nav.xhtml або EPUB2 toc.ncx (назви як в оригіналі)."""
    entries = []          # (назва, шлях файлу, якір)
    nav = next((v for v in manifest.values() if 'nav' in v[2].split()), None)
    ncx = next((v for v in manifest.values() if 'ncx' in v[1]), None)

    def target(tbase, href):
        full, _ = _zip_read(z, names, tbase, href)
        frag = unquote(href.split('#', 1)[1]) if '#' in href else ''
        return full, frag

    if nav:
        full, raw = _zip_read(z, names, base, nav[0])
        if raw:
            try:
                root = ET.fromstring(raw)
            except Exception:
                root = None
            if root is not None:
                for n in root.iter():
                    if _local(n.tag) == 'nav' and any(v == 'toc' for k, v in n.attrib.items()
                                                      if _local(k) == 'type'):
                        for a in n.iter():
                            if _local(a.tag) == 'a' and a.get('href'):
                                t = _norm(''.join(a.itertext()))
                                if t:
                                    entries.append((t,) + target(posixpath.dirname(full), a.get('href')))
                        break
    if not entries and ncx:
        full, raw = _zip_read(z, names, base, ncx[0])
        if raw:
            try:
                root = ET.fromstring(raw)
            except Exception:
                root = None
            if root is not None:
                for p in root.iter():
                    if _local(p.tag) == 'navPoint':
                        lab = src = None
                        for ch in p:
                            if _local(ch.tag) == 'navLabel' and lab is None:
                                lab = _norm(''.join(ch.itertext()))
                            elif _local(ch.tag) == 'content' and src is None:
                                src = ch.get('src')
                        if lab and src:
                            entries.append((lab,) + target(posixpath.dirname(full), src))
    out, seen = [], set()
    for title, f, frag in entries:
        b = anchors.get((f, frag)) if frag else None
        if b is None:
            b = file_start.get(f)
        if b is None or b in seen:
            continue
        seen.add(b)
        out.append((title, b))
    out.sort(key=lambda c: c[1])
    return out


def _epub_pagelist(z, names, base, manifest, file_start, anchors):
    """Номери сторінок друкованого видання: nav page-list (EPUB3) або pageList у NCX (EPUB2)."""
    raw_list = []
    nav = next((v for v in manifest.values() if 'nav' in v[2].split()), None)
    ncx = next((v for v in manifest.values() if 'ncx' in v[1]), None)

    def parse(item):
        full, raw = _zip_read(z, names, base, item[0])
        if not raw:
            return None, ''
        try:
            return ET.fromstring(raw), posixpath.dirname(full)
        except Exception:
            return None, ''

    if nav:
        root, d = parse(nav)
        if root is not None:
            for n in root.iter():
                if _local(n.tag) == 'nav' and any('page-list' in v for k, v in n.attrib.items()
                                                  if _local(k) == 'type'):
                    for a in n.iter():
                        if _local(a.tag) == 'a' and a.get('href'):
                            raw_list.append((_norm(''.join(a.itertext())), d, a.get('href')))
    if not raw_list and ncx:
        root, d = parse(ncx)
        if root is not None:
            for t in root.iter():
                if _local(t.tag) == 'pageTarget':
                    lab = _norm(t.get('value') or '')
                    src = None
                    for ch in t.iter():
                        if _local(ch.tag) == 'text' and not lab:
                            lab = _norm(ch.text or '')
                        elif _local(ch.tag) == 'content':
                            src = ch.get('src')
                    if lab and src:
                        raw_list.append((lab, d, src))
    out = []
    for lab, d, href in raw_list:
        full, _ = _zip_read(z, names, d, href)
        frag = unquote(href.split('#', 1)[1]) if '#' in href else ''
        b = anchors.get((full, frag)) if frag else None
        if b is None:
            b = file_start.get(full)
        if lab and b is not None:
            out.append((lab, b))
    out.sort(key=lambda c: c[1])
    return out


def _parse_epub(path, img_dir=None):
    z = zipfile.ZipFile(path)
    container = ET.fromstring(z.read('META-INF/container.xml'))
    opf_path = None
    for el in container.iter():
        if _local(el.tag) == 'rootfile' and el.get('full-path'):
            opf_path = el.get('full-path')
            break
    if not opf_path:
        raise ValueError('Некоректний EPUB: немає OPF')
    opf = ET.fromstring(z.read(opf_path))

    book = Book()
    manifest = {}
    spine = []
    cover_id = None
    for el in opf.iter():
        name = _local(el.tag)
        if name == 'title' and not book.title and el.text:
            book.title = _norm(el.text)
        elif name == 'creator' and not book.author and el.text:
            book.author = _norm(el.text)
        elif name == 'item':
            manifest[el.get('id') or ''] = (el.get('href', ''),
                                            el.get('media-type', ''),
                                            el.get('properties', ''))
        elif name == 'itemref':
            spine.append(el.get('idref'))
        elif name == 'meta' and el.get('name') == 'cover':
            cover_id = el.get('content')

    base = posixpath.dirname(opf_path)
    names = set(z.namelist())
    part = 0
    file_start, anchors, pb_raw = {}, {}, []
    for idref in spine:
        item = manifest.get(idref)
        if not item or not item[0]:
            continue
        href, mtype, _props = item
        if mtype and 'html' not in mtype and 'xml' not in mtype:
            continue
        full, raw = _zip_read(z, names, base, href)
        if raw is None:
            continue
        parser = _HtmlText()
        try:
            parser.feed(raw.decode('utf-8', errors='replace'))
            parser.close()
        except Exception:
            pass
        hbase = posixpath.dirname(full)
        blocks = []
        idxmap = []
        for kind, text in parser.blocks:
            idxmap.append(len(blocks))
            if kind == 'i':
                f2, d2 = _zip_read(z, names, hbase, text)
                p = _store_image(book, img_dir, f2, d2)
                if p:
                    blocks.append(('i', p))
            else:
                blocks.append((kind, text))
        idxmap.append(len(blocks))
        if not blocks:
            continue
        part += 1
        start = len(book.blocks)
        file_start[full] = start
        for lab, ai in parser.pagebreaks:
            pb_raw.append((lab, start + idxmap[min(ai, len(idxmap) - 1)]))
        for aid, ai in parser.anchors.items():
            anchors[(full, aid)] = start + idxmap[min(ai, len(idxmap) - 1)]
        book.blocks.extend(blocks)
        if blocks[0][0] == 'h':
            book.chapters.append((blocks[0][1], start))
        elif sum(len(t) for k, t in blocks if k == 'p') > 300:
            book.chapters.append(('Розділ %d' % part, start))

    pl = _epub_pagelist(z, names, base, manifest, file_start, anchors)
    if len(pl) < 10 and len(pb_raw) >= 10:
        pl = [(lab or str(i + 1), b) for i, (lab, b) in enumerate(pb_raw)]
    if len(pl) >= 10:
        book.pagelist = pl
    toc = _epub_toc(z, names, base, opf, manifest, file_start, anchors)
    if len(toc) >= 2:
        book.chapters = toc

    # обкладинка: meta cover -> properties=cover-image -> файл з "cover" у назві
    cands = []
    if cover_id in manifest:
        cands.append(manifest[cover_id][0])
    cands += [h for h, _m, p in manifest.values() if 'cover-image' in p]
    cands += [h for i, (h, m, _p) in manifest.items()
              if m.startswith('image/') and 'cover' in (i + h).lower()]
    for cand in cands:
        f, d = _zip_read(z, names, base, cand)
        book.cover = _store_image(book, img_dir, f, d, min_side=0)
        if book.cover:
            break
    if not book.cover:
        book.cover = next((t for k, t in book.blocks if k == 'i'), '')
    return book


# ----------------------------------------------------------------- FB2

def _parse_fb2_bytes(data, img_dir=None):
    root = ET.fromstring(data)
    book = Book()

    binaries = {}
    for el in root:
        if _local(el.tag) == 'binary' and el.get('id'):
            binaries[el.get('id')] = el

    def image_for(el, min_side=40):
        href = ''
        for k, v in el.attrib.items():
            if k.endswith('href'):
                href = v.lstrip('#')
        b = binaries.get(href)
        if b is None or not b.text:
            return ''
        try:
            raw = base64.b64decode(b.text)
        except Exception:
            return ''
        return _store_image(book, img_dir, 'fb2:' + href, raw, min_side)

    for el in root.iter():
        name = _local(el.tag)
        if name == 'book-title' and not book.title:
            book.title = _norm(''.join(el.itertext()))
        elif name == 'author' and not book.author:
            first = last = ''
            for sub in el:
                n = _local(sub.tag)
                if n == 'first-name':
                    first = _norm(''.join(sub.itertext()))
                elif n == 'last-name':
                    last = _norm(''.join(sub.itertext()))
            book.author = (first + ' ' + last).strip()
        elif name == 'coverpage' and not book.cover:
            for sub in el.iter():
                if _local(sub.tag) == 'image':
                    book.cover = image_for(sub, 0)
                    break

    def add(kind, text):
        text = _norm(text)
        if text:
            book.blocks.append((kind, text))

    def walk(parent, depth):
        for child in parent:
            name = _local(child.tag)
            if name == 'section':
                walk(child, depth + 1)
            elif name == 'title':
                text = _norm(' '.join(''.join(p.itertext())
                                      for p in child if _local(p.tag) == 'p')
                             or ''.join(child.itertext()))
                if text:
                    if depth <= 2:
                        book.chapters.append((text, len(book.blocks)))
                    add('h', text)
            elif name == 'subtitle':
                add('h', ''.join(child.itertext()))
            elif name == 'v':
                add('v', ''.join(child.itertext()))
            elif name in ('p', 'text-author'):
                add('p', ''.join(child.itertext()))
            elif name == 'image':
                p = image_for(child)
                if p:
                    book.blocks.append(('i', p))
            elif name in ('epigraph', 'cite', 'poem', 'stanza', 'annotation'):
                walk(child, depth)

    if book.cover:
        book.blocks.append(('i', book.cover))   # обкладинка першою сторінкою
    for body in root:
        if _local(body.tag) != 'body':
            continue
        if (body.get('name') or '').lower() in ('notes', 'comments'):
            continue
        walk(body, 0)
    return book


def _parse_fb2(path, img_dir=None):
    with open(path, 'rb') as f:
        return _parse_fb2_bytes(f.read(), img_dir)


def _parse_fb2_zip(path, img_dir=None):
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.lower().endswith('.fb2'):
                return _parse_fb2_bytes(z.read(name), img_dir)
    raise ValueError('В архіві немає .fb2 файлу')


# ----------------------------------------------------------------- API

def load_book(path, img_dir=None):
    low = path.lower()
    if low.endswith('.epub'):
        book = _parse_epub(path, img_dir)
    elif low.endswith('.fb2'):
        book = _parse_fb2(path, img_dir)
    elif low.endswith('.zip'):
        book = _parse_fb2_zip(path, img_dir)
    else:
        raise ValueError('Підтримуються лише EPUB та FB2')
    if not book.blocks:
        raise ValueError('Не вдалося знайти текст у книзі')
    # однакова чистка для будь-якого файлу: символи, склеювання рядків, розділювачі
    blocks, firsts = normalize(book.blocks)
    if not blocks:
        raise ValueError('Не вдалося знайти текст у книзі')
    book.chapters = remap_chapters(book.chapters, firsts, len(blocks))
    if book.pagelist:
        nums = [int(l) for l, _b in book.pagelist if l.isdigit()]
        book.page_total = max(nums) if nums else len(book.pagelist)
        book.pagelist = remap_chapters(book.pagelist, firsts, len(blocks))
    book.blocks = blocks
    if not book.title:
        book.title = os.path.splitext(os.path.basename(path))[0]
    return book
