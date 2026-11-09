"""DocInfo stream: character sizes, paragraph shapes, numbering definitions."""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from ..ir import NumLevel, Numbering, ParaShape
from ..limits import Limits
from .records import CHAR_SHAPE, NUMBERING, PARA_SHAPE, iter_records


@dataclass
class DocInfo:
    char_sizes: list[float] = field(default_factory=list)  # index = char shape id, points
    char_flags: list[int] = field(default_factory=list)  # bit0 italic, bit1 bold
    para_shapes: dict[int, ParaShape] = field(default_factory=dict)
    numberings: dict[int, Numbering] = field(default_factory=dict)


def read_docinfo(buf: bytes, limits: Limits) -> DocInfo:
    info = DocInfo()
    for tag, _level, p in iter_records(buf, limits):
        if tag == CHAR_SHAPE and len(p) >= 50:
            (height,) = struct.unpack_from("<i", p, 42)  # 1/100 pt
            (attr,) = struct.unpack_from("<I", p, 46)
            info.char_sizes.append(height / 100.0)
            info.char_flags.append(attr)
        elif tag == PARA_SHAPE and len(p) >= 28:
            (attr1,) = struct.unpack_from("<I", p, 0)
            (num_id,) = struct.unpack_from("<H", p, 26)
            info.para_shapes[len(info.para_shapes)] = ParaShape(
                head_type=(attr1 >> 23) & 0x3, level=(attr1 >> 25) & 0x7, numbering_id=num_id
            )
        elif tag == NUMBERING:
            info.numberings[len(info.numberings) + 1] = _parse_numbering(p)
    return info


def _parse_numbering(p: bytes) -> Numbering:
    levels: list[NumLevel] = []
    pos = 0
    for _ in range(7):
        if pos + 14 > len(p):
            break
        (attr,) = struct.unpack_from("<I", p, pos)
        pos += 12  # attr, width adjust, text distance, char shape id
        (n,) = struct.unpack_from("<H", p, pos)
        pos += 2
        fmt = p[pos:pos + 2 * n].decode("utf-16-le", "replace")
        pos += 2 * n
        levels.append(NumLevel(fmt=fmt, shape=(attr >> 5) & 0x1F))
    if pos + 2 <= len(p):
        (start,) = struct.unpack_from("<H", p, pos)
        for lv in levels:
            lv.start = start or 1
    return Numbering(levels)
