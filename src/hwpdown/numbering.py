"""Automatic numbering: the numbers are not stored in the file, they have to be counted."""
from __future__ import annotations

from .ir import Block, Document, Paragraph, Table, TextBox

_HANGUL = "가나다라마바사아자차카타파하"
_JAMO = "ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ"
_IDEO = "一二三四五六七八九十"
_STEM = "갑을병정무기경신임계"
_ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
          (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def _roman(n: int) -> str:
    out = ""
    for v, s in _ROMAN:
        while n >= v:
            out += s
            n -= v
    return out


def _from(chars: str, n: int) -> str:
    return chars[(n - 1) % len(chars)] if n >= 1 else ""


def format_number(shape: int, n: int) -> str:
    """Convert counter ``n`` (1-based) into text for HWP number shape code ``shape``."""
    if shape == 0:
        return str(n)
    if shape == 1:
        return chr(0x2460 + n - 1) if 1 <= n <= 20 else str(n)
    if shape == 2:
        return _roman(n)
    if shape == 3:
        return _roman(n).lower()
    if shape == 4:
        return chr(ord("A") + (n - 1) % 26)
    if shape == 5:
        return chr(ord("a") + (n - 1) % 26)
    if shape == 6:
        return chr(0x24B6 + (n - 1) % 26)
    if shape == 7:
        return chr(0x24D0 + (n - 1) % 26)
    if shape == 8:
        return _from(_HANGUL, n)
    if shape == 9:
        return chr(0x326E + (n - 1) % 14)
    if shape == 10:
        return _from(_JAMO, n)
    if shape == 11:
        return chr(0x3260 + (n - 1) % 14)
    if shape == 13:
        return _from(_IDEO, n)
    if shape == 14:
        return chr(0x3280 + (n - 1) % 10)
    if shape == 15:
        return _from(_STEM, n)
    return str(n)


def _walk(blocks: list[Block]):
    for b in blocks:
        if isinstance(b, Paragraph):
            yield b
        elif isinstance(b, Table):
            for c in sorted(b.cells, key=lambda c: (c.row, c.col)):
                yield from _walk(c.blocks)
        elif isinstance(b, TextBox):
            yield from _walk(b.blocks)


def compute_labels(doc: Document) -> dict[int, str]:
    """Return ``{id(paragraph): label}`` such as ``"1."`` or ``"가."`` in document order."""
    counters: dict[int, list[int]] = {}
    labels: dict[int, str] = {}
    for sec in doc.sections:
        for para in _walk(sec.blocks):
            shape = doc.para_shapes.get(para.para_shape_id) if para.para_shape_id is not None else None
            if shape is None:
                continue
            if shape.head_type == 3:
                labels[id(para)] = "-"
                continue
            if shape.head_type != 2:
                continue
            numbering = doc.numberings.get(shape.numbering_id)
            if numbering is None or not numbering.levels:
                continue
            lvl = min(shape.level, len(numbering.levels) - 1)
            cnt = counters.setdefault(shape.numbering_id, [0] * 7)
            cnt[lvl] = cnt[lvl] + 1 if cnt[lvl] else numbering.levels[lvl].start
            for deeper in range(lvl + 1, 7):
                cnt[deeper] = 0
            fmt = numbering.levels[lvl].fmt
            label = ""
            i = 0
            while i < len(fmt):
                if fmt[i] == "^" and i + 1 < len(fmt) and fmt[i + 1] in "1234567":
                    k = int(fmt[i + 1]) - 1
                    value = cnt[k] or (numbering.levels[k].start if k < len(numbering.levels) else 1)
                    label += format_number(numbering.levels[k].shape if k < len(numbering.levels) else 0, value)
                    i += 2
                else:
                    label += fmt[i]
                    i += 1
            if label:
                labels[id(para)] = label
    return labels
