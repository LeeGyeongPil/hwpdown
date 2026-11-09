"""Render the IR as Markdown in three styles: ``llm`` (default), ``plain`` and ``gfm-naive``."""
from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Literal, Optional

from ..headings import compute_levels
from ..ir import Block, Cell, Document, Footnote, NoteRef, Paragraph, Run, Table, TextBox
from ..numbering import compute_labels
from . import tables
from .legend import LEGEND


@dataclass(frozen=True)
class RenderOptions:
    """Rendering switches. ``style='llm'`` is the structure-preserving default."""

    style: Literal["llm", "plain", "gfm-naive"] = "llm"
    legend: bool = True
    table_mode: Literal["auto", "html", "gfm"] = "auto"  # auto: HTML when the table has merged cells
    numbering: bool = True
    heading_ratio: float = 1.15  # heading when size / most-common body size >= this
    section_marker: bool = True


def render(doc: Document, options: Optional[RenderOptions] = None) -> str:
    """Render ``doc`` to a Markdown string."""
    opt = options or RenderOptions()
    if opt.style not in ("llm", "plain", "gfm-naive"):
        raise ValueError(f"Unknown style {opt.style!r}; choose 'llm', 'plain' or 'gfm-naive'.")
    return _Renderer(doc, opt).run()


class _Renderer:
    def __init__(self, doc: Document, opt: RenderOptions) -> None:
        self.doc, self.opt = doc, opt
        structured = opt.style != "plain"
        self.labels = compute_labels(doc) if (opt.numbering and structured) else {}
        self.heads = compute_levels(doc, opt.heading_ratio) if structured else {}
        self.defs: list[str] = []  # footnote definitions in global order
        self.pending_plain: list[str] = []  # plain style: footnote text placed after its paragraph

    # -- entry --------------------------------------------------------------------------------
    def run(self) -> str:
        parts: list[str] = []
        for i, sec in enumerate(self.doc.sections):
            if i and self.opt.section_marker and self.opt.style == "llm":
                parts.append("---")
            parts.extend(self.blocks(sec.blocks))
        if self.defs:
            parts.append("\n".join(self.defs))
        body = "\n\n".join(p for p in parts if p)
        if self.opt.legend and self.opt.style == "llm":
            return LEGEND + "\n\n" + body + "\n"
        return body + "\n"

    def blocks(self, blocks: list[Block]) -> list[str]:
        out: list[str] = []
        prev_item = False  # consecutive list items stay in one Markdown list (single newline)
        for b in blocks:
            is_item = isinstance(b, Paragraph) and id(b) in self.labels
            if isinstance(b, Paragraph):
                s = self.paragraph(b)
                if s and is_item and prev_item and out:
                    out[-1] += "\n" + s
                elif s:
                    out.append(s)
                prev_item = is_item and bool(s)
                out.extend(self.pending_plain)
                self.pending_plain = []
            elif isinstance(b, Table):
                out.append(self.table(b))
                prev_item = False
            elif isinstance(b, TextBox):
                out.append(self.textbox(b))
                prev_item = False
        return out

    # -- paragraphs ---------------------------------------------------------------------------
    def inline(self, p: Paragraph) -> str:
        parts: list[str] = []
        for r in p.runs:
            if isinstance(r, Run):
                parts.append(r.text)
            else:
                parts.append(self.note_ref(r))
        return "".join(parts)

    def note_ref(self, ref: NoteRef) -> str:
        text = " ".join(self.flat_text(ref.note.blocks).split())
        if self.opt.style == "plain":
            self.pending_plain.append(text)
            return ""
        n = len(self.defs) + 1
        self.defs.append(f"[^{n}]: {text}")
        return f"[^{n}]"

    def flat_text(self, blocks: list[Block]) -> str:
        out: list[str] = []
        for b in blocks:
            if isinstance(b, Paragraph):
                out.append(b.text)
            elif isinstance(b, TextBox):
                out.append(self.flat_text(b.blocks))
            elif isinstance(b, Table):
                out.extend(self.flat_text(c.blocks) for c in sorted(b.cells, key=lambda c: (c.row, c.col)))
        return " ".join(t for t in out if t)

    def paragraph(self, p: Paragraph) -> str:
        text = self.inline(p).strip()
        if not text:
            return ""
        lvl = self.heads.get(id(p))
        if lvl:
            return "#" * lvl + " " + text
        label = self.labels.get(id(p))
        return f"{label} {text}" if label else text

    def textbox(self, tb: TextBox) -> str:
        texts = [self.paragraph(b) for b in tb.blocks if isinstance(b, Paragraph)]
        texts = [t for t in texts if t]
        if self.opt.style != "llm":
            return "\n\n".join(texts)
        lines = [("> [글상자] " if i == 0 else "> ") + t for i, t in enumerate(texts)]
        return "\n".join(lines)

    # -- tables -------------------------------------------------------------------------------
    def cell_text(self, cell: Cell, html_mode: bool) -> str:
        sep = "<br>" if (html_mode or self.opt.style == "llm") else " "
        parts: list[str] = []
        for b in cell.blocks:
            if isinstance(b, Paragraph):
                t = self.paragraph(b).strip()
                if t:
                    parts.append(t)
            elif isinstance(b, TextBox):
                t = self.flat_text(b.blocks)
                if t:
                    parts.append(t)
            elif isinstance(b, Table):
                parts.append(self.table(b, nested=True))
        raw = []
        for p in parts:
            if p.startswith("<table>"):
                raw.append(p)
            else:
                esc = html.escape(p, quote=False) if html_mode else p.replace("|", "\\|")
                raw.append(esc.replace("\n", "<br>" if (html_mode or self.opt.style == "llm") else " "))
        return sep.join(raw)

    def table(self, t: Table, nested: bool = False) -> str:
        style = self.opt.style
        if style == "plain":
            return tables.to_plain(t, lambda c: self.cell_text(c, False))
        if style == "gfm-naive":
            return tables.to_gfm_naive(t, lambda c: self.cell_text(c, False))
        mode = self.opt.table_mode
        use_html = mode == "html" or (mode == "auto" and (tables.has_merges(t) or nested))
        if use_html:
            return tables.to_html(t, lambda c: self.cell_text(c, True))
        return tables.to_gfm(t, lambda c: self.cell_text(c, False))
