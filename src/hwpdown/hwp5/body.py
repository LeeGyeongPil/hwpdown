"""BodyText records -> IR: paragraphs, tables, text boxes, footnotes."""
from __future__ import annotations

import bisect
import struct

from ..errors import LimitExceededError
from ..ir import Block, Cell, Footnote, NoteRef, Paragraph, Run, Table, TextBox
from ..limits import Limits
from .docinfo import DocInfo
from .records import (CTRL_HEADER, LIST_HEADER, PARA_CHAR_SHAPE, PARA_HEADER, PARA_TEXT, TABLE, Record)

# Control ids are stored as little-endian UINT32 of the 4-character ASCII code.
CTRL_TABLE = 0x74626C20  # 'tbl '
CTRL_GSO = 0x67736F20  # 'gso '
CTRL_FOOTNOTE = 0x666E2020  # 'fn  '
CTRL_ENDNOTE = 0x656E2020  # 'en  '

# WCHAR control codes that occupy a single character; every other code < 32 occupies 8 WCHARs.
SINGLE_CHAR_CODES = {0, 10, 13} | set(range(24, 32))
# 8-WCHAR codes that are backed by a CTRL_HEADER record (extended controls).
EXTENDED_CODES = {1, 2, 3, 11, 12, 14, 15, 16, 17, 18, 21, 22, 23}


class BodyReader:
    def __init__(self, info: DocInfo, limits: Limits, warnings: list[str]) -> None:
        self.info = info
        self.limits = limits
        self.warnings = warnings
        self.cell_count = 0

    def read_blocks(self, roots: list[Record]) -> list[Block]:
        blocks: list[Block] = []
        for node in roots:
            if node.tag == PARA_HEADER:
                blocks.extend(self.read_paragraph(node))
        return blocks

    # -- paragraphs -------------------------------------------------------------------------
    def _size_at(self, shapes: list[tuple[int, int]], starts: list[int], pos: int) -> tuple[float | None, bool, bool]:
        if not shapes:
            return None, False, False
        i = max(bisect.bisect_right(starts, pos) - 1, 0)
        csid = shapes[i][1]
        if csid < len(self.info.char_sizes):
            flags = self.info.char_flags[csid]
            return self.info.char_sizes[csid], bool(flags & 2), bool(flags & 1)
        return None, False, False

    def read_paragraph(self, node: Record) -> list[Block]:
        shape_id = struct.unpack_from("<H", node.data, 8)[0] if len(node.data) >= 10 else None
        text_rec = next((c for c in node.children if c.tag == PARA_TEXT), None)
        cs_rec = next((c for c in node.children if c.tag == PARA_CHAR_SHAPE), None)
        ctrls = [c for c in node.children if c.tag == CTRL_HEADER]
        shapes: list[tuple[int, int]] = []
        if cs_rec is not None:
            n = len(cs_rec.data) // 8
            shapes = sorted(struct.unpack_from("<II", cs_rec.data, 8 * i) for i in range(n))
        starts = [s[0] for s in shapes]

        para = Paragraph(para_shape_id=shape_id)
        extra: list[Block] = []
        if text_rec is not None:
            data = text_rec.data
            ws = struct.unpack_from(f"<{len(data) // 2}H", data, 0)
            buf: list[str] = []
            cur_key: tuple | None = None

            def flush() -> None:
                nonlocal buf
                if buf:
                    size, bold, italic = cur_key  # type: ignore[misc]
                    para.runs.append(Run("".join(buf), size, bold, italic))
                    buf = []

            i, k = 0, 0
            while i < len(ws):
                c = ws[i]
                if c < 32:
                    if c in SINGLE_CHAR_CODES:
                        if c == 10:
                            buf.append("\n")
                        i += 1
                        continue
                    ctrl = None
                    if c in EXTENDED_CODES:
                        if k < len(ctrls):
                            ctrl = ctrls[k]
                        k += 1
                    elif c == 9:
                        key = self._size_at(shapes, starts, i)
                        if key != cur_key:
                            flush()
                            cur_key = key
                        buf.append("\t")
                    i += 8
                    if ctrl is not None:
                        flush()
                        self._handle_control(ctrl, para, extra)
                    continue
                key = self._size_at(shapes, starts, i)
                if key != cur_key:
                    flush()
                    cur_key = key
                buf.append(chr(c))
                i += 1
            flush()
        out: list[Block] = []
        if para.runs:
            out.append(para)
        out.extend(extra)
        return out

    # -- controls ---------------------------------------------------------------------------
    def _handle_control(self, ctrl: Record, para: Paragraph, extra: list[Block]) -> None:
        if len(ctrl.data) < 4:
            return
        (cid,) = struct.unpack_from("<I", ctrl.data, 0)
        if cid == CTRL_TABLE:
            table = self.read_table(ctrl)
            if table is not None:
                extra.append(table)
        elif cid in (CTRL_FOOTNOTE, CTRL_ENDNOTE):
            note = Footnote(kind="footnote" if cid == CTRL_FOOTNOTE else "endnote")
            for group in self.list_groups(ctrl):
                note.blocks.extend(group)
            para.runs.append(NoteRef(note))
        elif cid == CTRL_GSO:
            for group in self.list_groups(ctrl):
                extra.append(TextBox(blocks=group))

    def list_groups(self, node: Record) -> list[list[Block]]:
        """Paragraph lists (LIST_HEADER + following paragraphs) below a shape/footnote control."""
        groups: list[list[Block]] = []
        current: list[Block] | None = None
        for ch in node.children:
            if ch.tag == LIST_HEADER:
                current = []
                groups.append(current)
                for p in ch.children:
                    if p.tag == PARA_HEADER:
                        current.extend(self.read_paragraph(p))
            elif ch.tag == PARA_HEADER:
                if current is not None:
                    current.extend(self.read_paragraph(ch))
            elif ch.tag != CTRL_HEADER:
                groups.extend(self.list_groups(ch))
        return [g for g in groups if g]

    def read_table(self, ctrl: Record) -> Table | None:
        """Only LIST_HEADERs that are direct children of this table control are cells."""
        trec = next((c for c in ctrl.children if c.tag == TABLE), None)
        if trec is None or len(trec.data) < 8:
            self.warnings.append("Table control without a TABLE record skipped.")
            return None
        rows, cols = struct.unpack_from("<HH", trec.data, 4)
        table = Table(rows=rows, cols=cols)
        current: Cell | None = None
        for ch in ctrl.children:
            if ch.tag == LIST_HEADER:
                if len(ch.data) < 16:
                    self.warnings.append("Short table-cell LIST_HEADER skipped.")
                    current = None
                    continue
                self.cell_count += 1
                if self.cell_count > self.limits.max_table_cells:
                    raise LimitExceededError(
                        f"More than {self.limits.max_table_cells} table cells. "
                        "Raise Limits(max_table_cells=...) if trusted."
                    )
                col, row, cs, rs = struct.unpack_from("<HHHH", ch.data, 8)
                current = Cell(row=row, col=col, row_span=max(rs, 1), col_span=max(cs, 1))
                table.cells.append(current)
                for p in ch.children:
                    if p.tag == PARA_HEADER:
                        current.blocks.extend(self.read_paragraph(p))
            elif ch.tag == PARA_HEADER and current is not None:
                current.blocks.extend(self.read_paragraph(ch))
        return table
