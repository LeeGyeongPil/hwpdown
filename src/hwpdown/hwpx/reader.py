"""HWPX: zipfile + ElementTree with real-byte caps on every member."""
from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree as ET

from ..detect import Source, load_source
from ..errors import CorruptDocumentError, LimitExceededError
from ..ir import (Cell, Document, Footnote, NoteRef, NumLevel, Numbering, ParaShape, Paragraph, Run, Section, Table,
                  TextBox, Block)
from ..limits import ByteBudget, Limits, read_capped

NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
NS_HH = "http://www.hancom.co.kr/hwpml/2011/head"

# OWPML numFormat name -> number shape code (same codes as the HWP 5.0 numbering definition).
NUM_FORMATS = [
    "DIGIT", "CIRCLED_DIGIT", "ROMAN_CAPITAL", "ROMAN_SMALL", "LATIN_CAPITAL", "LATIN_SMALL",
    "CIRCLED_LATIN_CAPITAL", "CIRCLED_LATIN_SMALL", "HANGUL_SYLLABLE", "CIRCLED_HANGUL_SYLLABLE",
    "HANGUL_JAMO", "CIRCLED_HANGUL_JAMO", "HANGUL_PHONETIC", "IDEOGRAPH", "CIRCLED_IDEOGRAPH",
    "HEAVENLY_STEM",
]


def _local(el: ET.Element) -> str:
    return el.tag.rsplit("}", 1)[-1]


def _read_member(z: zipfile.ZipFile, name: str, budget: ByteBudget) -> bytes:
    cap = budget.room()
    try:
        with z.open(name) as f:  # read with a real-bytes cap; the declared size is never trusted
            data = read_capped(f, cap, name)
    except zipfile.BadZipFile as exc:
        raise CorruptDocumentError(f"{name}: corrupt zip member ({exc}).") from exc
    budget.take(len(data), name)
    return data


def _parse_xml(data: bytes, name: str) -> ET.Element:
    if b"<!DOCTYPE" in data[:4096] or b"<!ENTITY" in data[:4096]:
        raise CorruptDocumentError(f"{name}: DOCTYPE/ENTITY declarations are not allowed in HWPX parts.")
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise CorruptDocumentError(f"{name}: invalid XML ({exc}).") from exc


def read_hwpx(source: Source, limits: Limits | None = None) -> Document:
    """Read an HWPX document into the IR."""
    limits = limits or Limits()
    data = load_source(source)
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise CorruptDocumentError(f"Cannot open HWPX zip: {exc}") from exc
    budget = ByteBudget(limits)
    doc = Document(format="hwpx")
    with z:
        names = z.namelist()
        if len(names) > limits.max_records:
            raise LimitExceededError("Too many zip members.")
        reader = _Reader(doc, limits)
        if "Contents/header.xml" in names:
            reader.read_header(_parse_xml(_read_member(z, "Contents/header.xml", budget), "header.xml"))
        sections = sorted(
            (n for n in names if re.fullmatch(r"Contents/section\d+\.xml", n)),
            key=lambda n: int(re.findall(r"\d+", n)[0]),
        )
        if not sections:
            raise CorruptDocumentError("No Contents/section*.xml found; not a valid HWPX document.")
        for name in sections:
            root = _parse_xml(_read_member(z, name, budget), name)
            doc.sections.append(Section(blocks=reader.read_section(root)))
    return doc


class _Reader:
    def __init__(self, doc: Document, limits: Limits) -> None:
        self.doc = doc
        self.limits = limits
        self.char_sizes: dict[str, float] = {}
        self.char_flags: dict[str, tuple[bool, bool]] = {}
        self.cell_count = 0
        self.depth = 0

    # -- header.xml: character sizes, paragraph shapes, numbering ----------------------------
    def read_header(self, root: ET.Element) -> None:
        for el in root.iter(f"{{{NS_HH}}}charPr"):
            h = el.get("height")
            if h and el.get("id") is not None:
                self.char_sizes[el.get("id")] = int(h) / 100.0  # type: ignore[index]
                self.char_flags[el.get("id")] = (  # type: ignore[index]
                    el.find(f"{{{NS_HH}}}bold") is not None, el.find(f"{{{NS_HH}}}italic") is not None)
        for el in root.iter(f"{{{NS_HH}}}numbering"):
            levels = []
            for ph in sorted(el.findall(f"{{{NS_HH}}}paraHead"), key=lambda e: int(e.get("level", "1"))):
                fmt = (ph.text or "")
                name = ph.get("numFormat", "DIGIT")
                levels.append(NumLevel(fmt=fmt, shape=NUM_FORMATS.index(name) if name in NUM_FORMATS else 0,
                                       start=int(ph.get("start", "1"))))
            self.doc.numberings[int(el.get("id", "0"))] = Numbering(levels)
        for el in root.iter(f"{{{NS_HH}}}paraPr"):
            pid = el.get("id")
            if pid is None:
                continue
            ps = ParaShape()
            heading = el.find(f"{{{NS_HH}}}heading")
            if heading is not None:
                kind = heading.get("type", "NONE")
                ps.head_type = {"NONE": 0, "OUTLINE": 1, "NUMBER": 2, "BULLET": 3}.get(kind, 0)
                ps.level = int(heading.get("level", "0"))
                ps.numbering_id = int(heading.get("idRef", "0"))
            self.doc.para_shapes[int(pid)] = ps

    # -- section.xml ------------------------------------------------------------------------
    def read_section(self, root: ET.Element) -> list[Block]:
        blocks: list[Block] = []
        for p in root.findall(f"{{{NS_HP}}}p"):
            blocks.extend(self.read_p(p))
        return blocks

    def _text_of(self, t: ET.Element) -> str:
        out = [t.text or ""]
        for ch in t:
            name = _local(ch)
            if name == "tab":
                out.append("\t")
            elif name in ("lineBreak",):
                out.append("\n")
            out.append(ch.tail or "")
        return "".join(out)

    def read_p(self, p: ET.Element) -> list[Block]:
        self.depth += 1
        if self.depth > self.limits.max_depth:
            raise LimitExceededError(f"Nesting deeper than {self.limits.max_depth}. Raise Limits(max_depth=...).")
        try:
            shape = p.get("paraPrIDRef")
            para = Paragraph(para_shape_id=int(shape) if shape is not None and shape.isdigit() else None)
            extra: list[Block] = []
            for run in p.findall(f"{{{NS_HP}}}run"):
                csid = run.get("charPrIDRef")
                size = self.char_sizes.get(csid) if csid is not None else None
                bold, italic = self.char_flags.get(csid, (False, False)) if csid is not None else (False, False)
                for ch in run:
                    name = _local(ch)
                    if name == "t":
                        text = self._text_of(ch)
                        if text:
                            para.runs.append(Run(text, size, bold, italic))
                    elif name == "tbl":
                        extra.append(self.read_tbl(ch))
                    else:
                        self._read_other(ch, para, extra)
            out: list[Block] = []
            if para.runs:
                out.append(para)
            out.extend(extra)
            return out
        finally:
            self.depth -= 1

    def _sub_blocks(self, el: ET.Element) -> list[Block]:
        blocks: list[Block] = []
        sub = el.find(f"{{{NS_HP}}}subList")
        if sub is not None:
            for p in sub.findall(f"{{{NS_HP}}}p"):
                blocks.extend(self.read_p(p))
        return blocks

    def _read_other(self, el: ET.Element, para: Paragraph, extra: list[Block]) -> None:
        name = _local(el)
        if name in ("footNote", "endNote"):
            note = Footnote(blocks=self._sub_blocks(el), kind="footnote" if name == "footNote" else "endnote")
            para.runs.append(NoteRef(note))
        elif name == "ctrl":
            for ch in el:
                self._read_other(ch, para, extra)
        elif name == "tbl":
            extra.append(self.read_tbl(el))
        else:
            # shapes (rect, container, ...) that carry a text box
            for dt in el.iter(f"{{{NS_HP}}}drawText"):
                blocks = self._sub_blocks(dt)
                if blocks:
                    extra.append(TextBox(blocks=blocks))

    def read_tbl(self, tbl: ET.Element) -> Table:
        table = Table(rows=int(tbl.get("rowCnt", "0")), cols=int(tbl.get("colCnt", "0")))
        # direct tr/tc children only: nested tables live inside a cell's subList
        for tr in tbl.findall(f"{{{NS_HP}}}tr"):
            for tc in tr.findall(f"{{{NS_HP}}}tc"):
                self.cell_count += 1
                if self.cell_count > self.limits.max_table_cells:
                    raise LimitExceededError(
                        f"More than {self.limits.max_table_cells} table cells. Raise Limits(max_table_cells=...)."
                    )
                addr = tc.find(f"{{{NS_HP}}}cellAddr")
                span = tc.find(f"{{{NS_HP}}}cellSpan")
                cell = Cell(
                    row=int(addr.get("rowAddr", "0")) if addr is not None else 0,
                    col=int(addr.get("colAddr", "0")) if addr is not None else 0,
                    row_span=int(span.get("rowSpan", "1")) if span is not None else 1,
                    col_span=int(span.get("colSpan", "1")) if span is not None else 1,
                    blocks=self._sub_blocks(tc),
                )
                table.cells.append(cell)
        return table
