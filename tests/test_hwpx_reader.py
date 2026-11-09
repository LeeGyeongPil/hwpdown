import io
import zipfile

import pytest

import hwpdown
from hwpdown.errors import CorruptDocumentError, LimitExceededError
from hwpdown.ir import Paragraph, Table, TextBox
from hwpdown.limits import Limits
from hwpdown.samples.build import budget_doc
from hwpdown.samples.hwpx_writer import write_hwpx


def _blocks(doc):
    return [b for s in doc.sections for b in s.blocks]


def test_hwpx_budget_tables_textbox_and_footnote(truth):
    doc = hwpdown.read(write_hwpx(budget_doc()))
    tables = [b for b in _blocks(doc) if isinstance(b, Table)]
    got = [{"rows": t.rows, "cols": t.cols, "cells": len(t.cells),
            "merged": sum(1 for c in t.cells if c.row_span > 1 or c.col_span > 1)} for t in tables]
    assert got == truth["budget.hwp"]["tables"]
    boxes = [b for b in _blocks(doc) if isinstance(b, TextBox)]
    assert [p.text for p in boxes[0].blocks if isinstance(p, Paragraph)] == truth["budget.hwp"]["textbox"]
    assert "예산 각주 내용" in hwpdown.to_markdown(write_hwpx(budget_doc()))


def test_hwpx_report_sizes_and_numbering_definitions(samples):
    doc = hwpdown.read(samples / "report.hwpx")
    sizes = {r.size_pt for b in _blocks(doc) if isinstance(b, Paragraph) for r in b.runs if hasattr(r, "size_pt")}
    assert sizes == {10.0, 12.0, 16.0}
    assert doc.numberings[1].levels[1].shape == 8


def _hwpx_with(section_xml: bytes, extra: dict[str, bytes] | None = None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", b"application/hwp+zip")
        z.writestr("Contents/section0.xml", section_xml)
        for k, v in (extra or {}).items():
            z.writestr(k, v)
    return buf.getvalue()


def test_doctype_entities_rejected():
    xml = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><hs:sec xmlns:hs="urn:x">&a;</hs:sec>'
    with pytest.raises(CorruptDocumentError, match="DOCTYPE"):
        hwpdown.read(_hwpx_with(xml))


def test_invalid_xml_and_missing_sections():
    with pytest.raises(CorruptDocumentError, match="invalid XML"):
        hwpdown.read(_hwpx_with(b"<not-closed"))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", b"application/hwp+zip")
    with pytest.raises(CorruptDocumentError, match="section"):
        hwpdown.read(buf.getvalue())


def test_hwpx_total_limit(samples):
    with pytest.raises(LimitExceededError):
        hwpdown.read(samples / "report.hwpx", limits=Limits(max_total_bytes=100))
