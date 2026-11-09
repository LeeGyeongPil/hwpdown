"""Write a synthetic HWP 5.0 file (record encoder + FileHeader/DocInfo/BodyText) from a SampleDoc."""
from __future__ import annotations

import hashlib
import struct
import zlib

from .cfb import build_cfb
from .spec import C, NUM0, NUM1, P, SampleDoc, T, TB

TAG_BEGIN = 0x10
DOC_PROPERTIES, CHAR_SHAPE, NUMBERING, PARA_SHAPE = TAG_BEGIN, TAG_BEGIN + 5, TAG_BEGIN + 7, TAG_BEGIN + 9
PARA_HEADER, PARA_TEXT, PARA_CHAR_SHAPE = TAG_BEGIN + 50, TAG_BEGIN + 51, TAG_BEGIN + 52
CTRL_HEADER, LIST_HEADER, PAGE_DEF, SHAPE_COMPONENT, TABLE = (
    TAG_BEGIN + 55, TAG_BEGIN + 56, TAG_BEGIN + 57, TAG_BEGIN + 60, TAG_BEGIN + 61)


def ctrl_id(code: str) -> bytes:
    """Control ids are the little-endian UINT32 of the 4-char ASCII code (e.g. 'tbl ')."""
    return struct.pack("<I", int.from_bytes(code.encode("ascii"), "big"))


def rec(tag: int, level: int, payload: bytes = b"") -> bytes:
    """Encode one record: 10-bit tag, 10-bit level, 12-bit size (0xFFF escapes to a 4-byte size)."""
    size = len(payload)
    if size >= 0xFFF:
        return struct.pack("<II", tag | (level << 10) | (0xFFF << 20), size) + payload
    return struct.pack("<I", tag | (level << 10) | (size << 20)) + payload


def deflate_raw(data: bytes) -> bytes:
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return c.compress(data) + c.flush()


def file_header(compressed: bool, distribution: bool = False, encrypted: bool = False) -> bytes:
    props = (1 if compressed else 0) | (2 if encrypted else 0) | (4 if distribution else 0)
    head = b"HWP Document File".ljust(32, b"\0") + struct.pack("<II", 0x05000300, props)
    return head.ljust(256, b"\0")


class _Body:
    """Encodes blocks into BodyText records; collects the character sizes it needs."""

    def __init__(self, size_ids: dict[float, int]) -> None:
        self.size_ids = size_ids

    def para(self, level: int, text: str, size: float, shape: int, ctrls: list[tuple[int, list[bytes]]]) -> bytes:
        """One paragraph. ``ctrls`` is a list of (control char code, [child records already encoded])."""
        utf = text.encode("utf-16-le")
        body = bytearray(utf)
        mask = 0
        child_records = b""
        for code, children in ctrls:
            cid = children[0][4:8]  # the control id sits at the start of the CTRL_HEADER payload
            body += struct.pack("<H", code) + cid + b"\0" * 8 + struct.pack("<H", code)
            mask |= 1 << code
            child_records += b"".join(children)
        body += struct.pack("<H", 13)
        nchars = len(body) // 2
        header = struct.pack("<IIHBBHHHI", nchars, mask, shape, 0, 0, 1, 0, 0, 0)
        out = rec(PARA_HEADER, level, header)
        out += rec(PARA_TEXT, level + 1, bytes(body))
        out += rec(PARA_CHAR_SHAPE, level + 1, struct.pack("<II", 0, self.size_ids[size]))
        return out + child_records

    def paragraph(self, level: int, p: P) -> bytes:
        ctrls = []
        for note in p.notes:
            inner = b"".join(self.paragraph(level + 2, q) for q in note.paras)
            children = [
                rec(CTRL_HEADER, level + 1, ctrl_id("fn  ") + b"\0" * 8),
                rec(LIST_HEADER, level + 2, struct.pack("<hIH", len(note.paras), 0, 0)),
                inner,
            ]
            ctrls.append((0x11, children))
        return self.para(level, p.text, p.size, p.shape, ctrls)

    def table(self, level: int, t: T) -> bytes:
        parts = [rec(CTRL_HEADER, level + 1, ctrl_id("tbl ") + b"\0" * 40),
                 rec(TABLE, level + 2, struct.pack("<IHHHHHHH", 0, t.rows, t.cols, 0, 0, 0, 0, 0)
                     + b"".join(struct.pack("<H", sum(1 for c in t.cells if c.row == r)) for r in range(t.rows))
                     + b"\0\0")]  # per-row cell counts, then the border fill id
        for c in t.cells:
            payload = struct.pack("<hIH", len(c.paras), 0, 0) + struct.pack(
                "<HHHHIIHHHHH", c.col, c.row, c.cs, c.rs, 1000 * c.cs, 500 * c.rs, 0, 0, 0, 0, 0)
            parts.append(rec(LIST_HEADER, level + 2, payload))
            parts.extend(self.paragraph(level + 2, q) for q in c.paras)
        return self.para(level, "", 10.0, 0, [(11, parts)])

    def textbox(self, level: int, tb: TB) -> bytes:
        parts = [rec(CTRL_HEADER, level + 1, ctrl_id("gso ") + b"\0" * 40),
                 rec(SHAPE_COMPONENT, level + 2, b"\0" * 20),
                 rec(LIST_HEADER, level + 3, struct.pack("<hIH", len(tb.paras), 0, 0))]
        parts.extend(self.paragraph(level + 3, q) for q in tb.paras)
        return self.para(level, "", 10.0, 0, [(11, parts)])

    def section(self, blocks: list) -> bytes:
        secd = [rec(CTRL_HEADER, 1, ctrl_id("secd") + b"\0" * 28), rec(PAGE_DEF, 2, b"\0" * 40)]
        out = self.para(0, "", 10.0, 0, [(2, secd)])
        for b in blocks:
            if isinstance(b, T):
                out += self.table(0, b)
            elif isinstance(b, TB):
                out += self.textbox(0, b)
            else:
                out += self.paragraph(0, b)
        return out


def _sizes(blocks: list) -> list[float]:
    seen: list[float] = [10.0]

    def add(p: P) -> None:
        if p.size not in seen:
            seen.append(p.size)
        for n in p.notes:
            for q in n.paras:
                add(q)

    for b in blocks:
        if isinstance(b, P):
            add(b)
        elif isinstance(b, T):
            for c in b.cells:
                for q in c.paras:
                    add(q)
        elif isinstance(b, TB):
            for q in b.paras:
                add(q)
    return seen


def _docinfo(sizes: list[float]) -> bytes:
    out = rec(DOC_PROPERTIES, 0, struct.pack("<H", 1) + b"\0" * 24)
    for s in sizes:
        out += rec(CHAR_SHAPE, 0, b"\0" * 42 + struct.pack("<iI", int(round(s * 100)), 0) + b"\0" * 22)
    levels = b""
    shapes = [0, 8, 0, 0, 0, 0, 0]  # level 2 uses 가,나,다 ; others 1,2,3
    for i in range(7):
        fmt = f"^{i + 1}.".encode("utf-16-le")
        levels += struct.pack("<IHHI", shapes[i] << 5, 0, 0, 0) + struct.pack("<H", len(fmt) // 2) + fmt
    out += rec(NUMBERING, 0, levels + struct.pack("<H", 1))
    for head, lvl, num in ((0, 0, 0), (2, 0, 1), (2, 1, 1)):  # PLAIN, NUM0, NUM1
        attr = (head << 23) | (lvl << 25)
        out += rec(PARA_SHAPE, 0, struct.pack("<I", attr) + b"\0" * 22 + struct.pack("<H", num) + b"\0" * 24)
    return out


def write_hwp5(doc: SampleDoc, compress: bool = True) -> bytes:
    """Return the bytes of a synthetic .hwp document."""
    sizes = _sizes(doc.blocks)
    size_ids = {s: i for i, s in enumerate(sizes)}
    docinfo = _docinfo(sizes)
    section = _Body(size_ids).section(doc.blocks)
    enc = deflate_raw if compress else (lambda b: b)
    return build_cfb({
        ("FileHeader",): file_header(compress),
        ("DocInfo",): enc(docinfo),
        ("BodyText", "Section0"): enc(section),
    })


def write_distribution_hwp5() -> bytes:
    """A document whose FileHeader marks it as a distribution (copy-protected) document."""
    fake = hashlib.sha256(b"synthetic distribution body").digest() * 8
    return build_cfb({
        ("FileHeader",): file_header(True, distribution=True),
        ("DocInfo",): deflate_raw(_docinfo([10.0])),
        ("ViewText", "Section0"): fake,
    })


def write_bomb_hwp5(megabytes: int) -> bytes:
    """A tiny file whose BodyText section inflates to ``megabytes`` MB (compression-bomb test input)."""
    c = zlib.compressobj(1, zlib.DEFLATED, -15)
    parts = [c.compress(b"\0" * (1024 * 1024)) for _ in range(megabytes)]
    parts.append(c.flush())
    return build_cfb({
        ("FileHeader",): file_header(True),
        ("DocInfo",): deflate_raw(_docinfo([10.0])),
        ("BodyText", "Section0"): b"".join(parts),
    })
