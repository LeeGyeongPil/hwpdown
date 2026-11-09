"""HWP 5.0 record stream: 32-bit header (tag 10 bits, level 10 bits, size 12 bits) + payload."""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from ..errors import CorruptDocumentError, LimitExceededError
from ..limits import Limits

TAG_BEGIN = 0x10
# DocInfo
CHAR_SHAPE = TAG_BEGIN + 5
NUMBERING = TAG_BEGIN + 7
PARA_SHAPE = TAG_BEGIN + 9
# BodyText
PARA_HEADER = TAG_BEGIN + 50
PARA_TEXT = TAG_BEGIN + 51
PARA_CHAR_SHAPE = TAG_BEGIN + 52
CTRL_HEADER = TAG_BEGIN + 55
LIST_HEADER = TAG_BEGIN + 56
SHAPE_COMPONENT = TAG_BEGIN + 60
TABLE = TAG_BEGIN + 61


@dataclass
class Record:
    tag: int
    level: int
    data: bytes
    children: list["Record"] = field(default_factory=list)


def iter_records(buf: bytes, limits: Limits):
    """Yield (tag, level, payload) for every record; the 0xFFF size escape reads a 4-byte size."""
    pos, n, count = 0, len(buf), 0
    while pos < n:
        if pos + 4 > n:
            raise CorruptDocumentError("Truncated record header in stream.")
        (h,) = struct.unpack_from("<I", buf, pos)
        pos += 4
        tag, level, size = h & 0x3FF, (h >> 10) & 0x3FF, h >> 20
        if size == 0xFFF:
            if pos + 4 > n:
                raise CorruptDocumentError("Truncated extended record size.")
            (size,) = struct.unpack_from("<I", buf, pos)
            pos += 4
        if pos + size > n:
            raise CorruptDocumentError("Record payload runs past the end of the stream.")
        count += 1
        if count > limits.max_records:
            raise LimitExceededError(
                f"More than {limits.max_records} records in one stream. Raise Limits(max_records=...) if trusted."
            )
        yield tag, level, buf[pos:pos + size]
        pos += size


def build_tree(buf: bytes, limits: Limits) -> list[Record]:
    """Rebuild parent/child structure from record levels."""
    roots: list[Record] = []
    stack: list[Record] = []
    for tag, level, data in iter_records(buf, limits):
        rec = Record(tag, level, data)
        while stack and stack[-1].level >= level:
            stack.pop()
        if stack:
            stack[-1].children.append(rec)
        else:
            roots.append(rec)
        stack.append(rec)
        if len(stack) > limits.max_depth:
            raise LimitExceededError(
                f"Record nesting deeper than {limits.max_depth}. Raise Limits(max_depth=...) if trusted."
            )
    return roots
