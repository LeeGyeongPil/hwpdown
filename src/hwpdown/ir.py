"""Format-independent document model (intermediate representation)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union


@dataclass
class Run:
    text: str
    size_pt: Optional[float] = None
    bold: bool = False
    italic: bool = False


@dataclass
class NoteRef:
    """Inline reference to a footnote/endnote; numbered globally at render time."""

    note: "Footnote"


@dataclass
class Paragraph:
    runs: list[Union[Run, NoteRef]] = field(default_factory=list)
    para_shape_id: Optional[int] = None

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs if isinstance(r, Run))


@dataclass
class Cell:
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1
    blocks: list["Block"] = field(default_factory=list)


@dataclass
class Table:
    rows: int
    cols: int
    cells: list[Cell] = field(default_factory=list)


@dataclass
class TextBox:
    blocks: list["Block"] = field(default_factory=list)


@dataclass
class Footnote:
    blocks: list["Block"] = field(default_factory=list)
    kind: str = "footnote"


Block = Union[Paragraph, Table, TextBox]


@dataclass
class Section:
    blocks: list[Block] = field(default_factory=list)


@dataclass
class ParaShape:
    """Paragraph shape: head_type 0 none, 1 outline, 2 number, 3 bullet; level is 0-based."""

    head_type: int = 0
    level: int = 0
    numbering_id: int = 0


@dataclass
class NumLevel:
    fmt: str = ""  # e.g. "^1." ; ^n is the counter of level n
    shape: int = 0  # number shape code (0 -> 1,2,3 ; 8 -> 가,나,다 ...)
    start: int = 1


@dataclass
class Numbering:
    levels: list[NumLevel] = field(default_factory=list)


@dataclass
class Document:
    format: str
    version: str = ""
    sections: list[Section] = field(default_factory=list)
    para_shapes: dict[int, ParaShape] = field(default_factory=dict)
    numberings: dict[int, Numbering] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
