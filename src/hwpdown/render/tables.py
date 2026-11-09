"""Table layout and the HTML / GFM / naive-GFM / plain renderers."""
from __future__ import annotations

from typing import Callable

from ..ir import Cell, Table

CellText = Callable[[Cell], str]


def dims(table: Table) -> tuple[int, int]:
    rows = max([table.rows] + [c.row + c.row_span for c in table.cells])
    cols = max([table.cols] + [c.col + c.col_span for c in table.cells])
    return rows, cols


def has_merges(table: Table) -> bool:
    return any(c.row_span > 1 or c.col_span > 1 for c in table.cells)


def header_rows(table: Table) -> int:
    """Rows 0..n-1 are headers, n = largest rowspan among first-row cells."""
    first = [c.row_span for c in table.cells if c.row == 0]
    return max(first) if first else 1


def _layout(table: Table):
    rows, cols = dims(table)
    origin: dict[tuple[int, int], Cell] = {}
    covered: set[tuple[int, int]] = set()
    for c in table.cells:
        origin[(c.row, c.col)] = c
        for dr in range(c.row_span):
            for dc in range(c.col_span):
                if dr or dc:
                    covered.add((c.row + dr, c.col + dc))
    return rows, cols, origin, covered


def to_html(table: Table, text: CellText) -> str:
    rows, cols, origin, covered = _layout(table)
    hdr = header_rows(table)
    lines = ["<table>"]
    for r in range(rows):
        tag = "th" if r < hdr else "td"
        parts = []
        for c in range(cols):
            if (r, c) in covered:
                continue
            cell = origin.get((r, c))
            if cell is None:
                parts.append(f"<{tag}></{tag}>")
                continue
            attrs = ""
            if cell.row_span > 1:
                attrs += f' rowspan="{cell.row_span}"'
            if cell.col_span > 1:
                attrs += f' colspan="{cell.col_span}"'
            parts.append(f"<{tag}{attrs}>{text(cell)}</{tag}>")
        lines.append("<tr>" + "".join(parts) + "</tr>")
    lines.append("</table>")
    return "\n".join(lines)


def _gfm(rows_text: list[list[str]]) -> str:
    width = max((len(r) for r in rows_text), default=0)
    rows_text = [r + [""] * (width - len(r)) for r in rows_text]
    out = ["| " + " | ".join(rows_text[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    out += ["| " + " | ".join(r) + " |" for r in rows_text[1:]]
    return "\n".join(out)


def to_gfm(table: Table, text: CellText) -> str:
    """GFM grid; merged cells keep their text in the origin cell and leave the rest empty."""
    rows, cols, origin, _ = _layout(table)
    grid = [[text(origin[(r, c)]) if (r, c) in origin else "" for c in range(cols)] for r in range(rows)]
    return _gfm(grid)


def to_gfm_naive(table: Table, text: CellText) -> str:
    """Baseline that ignores spans: cells are laid out in reading order (reproduces column drift)."""
    rows, cols, _, _ = _layout(table)
    by_row: list[list[str]] = [[] for _ in range(rows)]
    for c in sorted(table.cells, key=lambda c: (c.row, c.col)):
        by_row[c.row].append(text(c))
    return _gfm([r + [""] * (cols - len(r)) for r in by_row])


def to_plain(table: Table, text: CellText) -> str:
    rows, _, _, _ = _layout(table)
    by_row: list[list[str]] = [[] for _ in range(rows)]
    for c in sorted(table.cells, key=lambda c: (c.row, c.col)):
        t = text(c)
        if t:
            by_row[c.row].append(t)
    return "\n".join(" ".join(r) for r in by_row if r)
