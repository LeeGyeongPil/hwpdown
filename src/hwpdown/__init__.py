"""hwpdown: pure-Python HWP 5.0 / HWPX reader that renders LLM-friendly Markdown.

본 제품은 한글과컴퓨터의 한/글 문서 파일(.hwp) 공개 문서를 참고하여 개발하였습니다.
(This product was developed with reference to the public file-format documents of Hancom's Hangul (.hwp).)
"""
from __future__ import annotations

from typing import Optional

from .detect import Source, detect_format, load_source
from .errors import (CorruptDocumentError, DistributionDocumentError, HwpdownError, LimitExceededError,
                     UnsupportedFormatError)
from .hwp5 import read_hwp5
from .hwpx import read_hwpx
from .ir import Document
from .limits import Limits
from .render import RenderOptions, render

__version__ = "0.1.1"
CREDIT = "본 제품은 한글과컴퓨터의 한/글 문서 파일(.hwp) 공개 문서를 참고하여 개발하였습니다."

__all__ = [
    "CREDIT", "CorruptDocumentError", "DistributionDocumentError", "Document", "HwpdownError", "LimitExceededError",
    "Limits", "RenderOptions", "UnsupportedFormatError", "detect_format", "read", "render", "to_markdown",
]


def read(source: Source, *, limits: Optional[Limits] = None) -> Document:
    """Detect the format by magic bytes and read the document into the IR."""
    data = load_source(source)
    fmt = detect_format(data)
    return read_hwp5(data, limits) if fmt == "hwp5" else read_hwpx(data, limits)


def to_markdown(source: Source, *, options: Optional[RenderOptions] = None, limits: Optional[Limits] = None) -> str:
    """Read ``source`` (path or bytes) and render Markdown."""
    return render(read(source, limits=limits), options)
