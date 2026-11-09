"""Tiny format-neutral description of a sample document; both writers consume it."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

# paragraph shapes: 0 plain, 1 numbered level 0 ("1."), 2 numbered level 1 ("가.")
PLAIN, NUM0, NUM1 = 0, 1, 2


@dataclass
class P:
    text: str
    size: float = 10.0
    shape: int = PLAIN
    notes: list["Note"] = field(default_factory=list)  # footnotes referenced at the end of the text


@dataclass
class Note:
    paras: list[P]


@dataclass
class C:
    row: int
    col: int
    paras: list[P]
    rs: int = 1
    cs: int = 1


@dataclass
class T:
    rows: int
    cols: int
    cells: list[C]


@dataclass
class TB:
    paras: list[P]


@dataclass
class SampleDoc:
    blocks: list[Union[P, T, TB]]
