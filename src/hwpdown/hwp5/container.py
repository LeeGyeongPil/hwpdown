"""Open the OLE container, check FileHeader flags, inflate sections with real-byte caps."""
from __future__ import annotations

import io
import struct

import olefile

from ..detect import Source, load_source
from ..errors import CorruptDocumentError, DistributionDocumentError, LimitExceededError
from ..ir import Document, Section
from ..limits import ByteBudget, Limits, inflate_raw
from .body import BodyReader
from .docinfo import DocInfo, read_docinfo
from .records import build_tree

SIGNATURE = b"HWP Document File"


def read_hwp5(source: Source, limits: Limits | None = None) -> Document:
    """Read an HWP 5.0 document into the IR."""
    limits = limits or Limits()
    data = load_source(source)
    try:
        ole = olefile.OleFileIO(io.BytesIO(data))
    except (OSError, ValueError, struct.error) as exc:
        raise CorruptDocumentError(f"Cannot open OLE container: {exc}") from exc
    try:
        return _read(ole, limits)
    finally:
        ole.close()


def _read_stream(ole: olefile.OleFileIO, path: list[str], compressed: bool, budget: ByteBudget) -> bytes:
    name = "/".join(path)
    size = ole.get_size(path)
    if size > budget.room() and not compressed:
        raise LimitExceededError(f"{name}: stream is {size} bytes, above the configured limit.")
    raw = ole.openstream(path).read()
    if compressed:
        out = inflate_raw(raw, budget.room(), name)
    else:
        out = raw
    budget.take(len(out), name)
    return out


def _read(ole: olefile.OleFileIO, limits: Limits) -> Document:
    if not ole.exists("FileHeader"):
        raise CorruptDocumentError("OLE file has no FileHeader stream; not an HWP 5.0 document.")
    fh = ole.openstream("FileHeader").read(256)
    if len(fh) < 40 or not fh.startswith(SIGNATURE):
        raise CorruptDocumentError("FileHeader signature is not 'HWP Document File'.")
    ver = struct.unpack_from("<4B", fh, 32)
    version = ".".join(str(b) for b in reversed(ver))
    (props,) = struct.unpack_from("<I", fh, 36)
    compressed, encrypted, distribution = bool(props & 1), bool(props & 2), bool(props & 4)
    entries = ole.listdir()
    if distribution or (any(e[0] == "ViewText" for e in entries) and not any(e[0] == "BodyText" for e in entries)):
        raise DistributionDocumentError(
            "배포용(복제 방지) 문서라 본문을 읽지 않습니다. 원본 작성자에게 일반 .hwp 파일을 요청하세요."
        )
    if encrypted:
        raise DistributionDocumentError(
            "암호가 걸린 문서라 본문을 읽지 않습니다. 암호를 해제한 파일을 사용하세요."
        )
    budget = ByteBudget(limits)
    doc = Document(format="hwp5", version=version)
    info = DocInfo()
    if ole.exists("DocInfo"):
        info = read_docinfo(_read_stream(ole, ["DocInfo"], compressed, budget), limits)
    doc.para_shapes = info.para_shapes
    doc.numberings = info.numberings
    sections = sorted(
        (e for e in entries if len(e) == 2 and e[0] == "BodyText" and e[1].startswith("Section")),
        key=lambda e: int(e[1][7:] or 0) if e[1][7:].isdigit() else 0,
    )
    if not sections:
        raise CorruptDocumentError("No BodyText/Section streams found.")
    for entry in sections:
        buf = _read_stream(ole, list(entry), compressed, budget)
        roots = build_tree(buf, limits)
        reader = BodyReader(info, limits, doc.warnings)
        doc.sections.append(Section(blocks=reader.read_blocks(roots)))
    return doc
