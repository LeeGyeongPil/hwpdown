"""Format detection by magic bytes (never by file extension)."""
from __future__ import annotations

import io
import os
import zipfile
from typing import Literal, Union

from .errors import UnsupportedFormatError

OLE_MAGIC = bytes.fromhex("d0cf11e0a1b11ae1")
ZIP_MAGIC = b"PK\x03\x04"
HWPX_MIMETYPE = b"application/hwp+zip"

Source = Union[str, "os.PathLike[str]", bytes, bytearray]
Format = Literal["hwp5", "hwpx"]


def load_source(source: Source) -> bytes:
    """Return the raw bytes of a path or bytes-like input."""
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    with open(source, "rb") as f:
        return f.read()


def detect_format(source: Source) -> Format:
    """Return ``"hwp5"`` (OLE) or ``"hwpx"`` (zip with an HWP mimetype entry).

    Raises ``UnsupportedFormatError`` for anything else.
    """
    return detect_bytes(load_source(source))


def detect_bytes(data: bytes) -> Format:
    head = data[:8]
    if head == OLE_MAGIC:
        return "hwp5"
    if head[:4] == ZIP_MAGIC:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                with z.open("mimetype") as f:
                    mimetype = f.read(64).strip()
        except (zipfile.BadZipFile, KeyError) as exc:
            raise UnsupportedFormatError(
                "ZIP file without a readable 'mimetype' entry; not an HWPX document."
            ) from exc
        if mimetype == HWPX_MIMETYPE:
            return "hwpx"
        raise UnsupportedFormatError(
            f"ZIP mimetype is {mimetype!r}, expected {HWPX_MIMETYPE!r}. Only HWPX zips are supported."
        )
    raise UnsupportedFormatError(
        "Unknown file signature. hwpdown reads HWP 5.0 (OLE) and HWPX (zip) documents; "
        "HWP 3.0 and other formats are not supported."
    )
