"""Safety limits and bounded readers.

Raw-deflate streams inside an HWP 5.0 file carry no declared size, so the only safe cap is the
number of bytes that *actually* come out of the decompressor.
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass

from .errors import CorruptDocumentError, LimitExceededError


@dataclass(frozen=True)
class Limits:
    """Upper bounds applied while reading untrusted documents."""

    max_stream_bytes: int = 64 * 1024 * 1024
    max_total_bytes: int = 256 * 1024 * 1024
    max_records: int = 2_000_000
    max_depth: int = 64
    max_table_cells: int = 100_000


class ByteBudget:
    """Tracks the total number of decompressed bytes handed out for one document."""

    def __init__(self, limits: Limits) -> None:
        self.limits = limits
        self.used = 0

    def room(self) -> int:
        """Largest stream size still allowed (per-stream cap and remaining total)."""
        return min(self.limits.max_stream_bytes, self.limits.max_total_bytes - self.used)

    def take(self, n: int, what: str) -> None:
        self.used += n
        if self.used > self.limits.max_total_bytes:
            raise LimitExceededError(
                f"{what}: total decompressed size exceeds {self.limits.max_total_bytes} bytes. "
                "Pass a larger Limits(max_total_bytes=...) only if you trust the file."
            )


_CHUNK = 1024 * 1024


def _too_big(what: str, cap: int) -> LimitExceededError:
    return LimitExceededError(
        f"{what}: decompressed size exceeds {cap} bytes (possible compression bomb). "
        "Pass a larger Limits(max_stream_bytes=...) only if you trust the file."
    )


def inflate_raw(data: bytes, cap: int, what: str) -> bytes:
    """Raw-deflate decompress ``data``, refusing to produce more than ``cap`` bytes.

    Works in 1 MiB steps and stops at the first byte over the cap, so memory stays near the cap.
    """
    d = zlib.decompressobj(-15)
    parts: list[bytes] = []
    total = 0
    pending = data
    try:
        while pending and not d.eof:
            piece = d.decompress(pending, _CHUNK)
            pending = d.unconsumed_tail
            total += len(piece)
            if total > cap:
                raise _too_big(what, cap)
            parts.append(piece)
        tail = d.flush()
    except zlib.error as exc:
        raise CorruptDocumentError(f"{what}: invalid compressed data ({exc}).") from exc
    total += len(tail)
    if total > cap:
        raise _too_big(what, cap)
    parts.append(tail)
    return b"".join(parts)


def read_capped(f, cap: int, what: str) -> bytes:
    """Read a file-like object in chunks, raising LimitExceededError past ``cap`` real bytes."""
    parts: list[bytes] = []
    total = 0
    while True:
        piece = f.read(_CHUNK)
        if not piece:
            break
        total += len(piece)
        if total > cap:
            raise _too_big(what, cap)
        parts.append(piece)
    return b"".join(parts)
