import struct

import pytest

import hwpdown
from hwpdown.errors import CorruptDocumentError, LimitExceededError
from hwpdown.hwp5.records import build_tree, iter_records
from hwpdown.ir import Paragraph, Table, TextBox
from hwpdown.limits import Limits
from hwpdown.samples.cfb import build_cfb
from hwpdown.samples.hwp5_writer import file_header, rec, write_hwp5
from hwpdown.samples.spec import P, SampleDoc


def _blocks(doc):
    return [b for s in doc.sections for b in s.blocks]


def test_textbox_list_header_not_counted_as_cell(samples, truth):
    doc = hwpdown.read(samples / "budget.hwp")
    tables = [b for b in _blocks(doc) if isinstance(b, Table)]
    expected = truth["budget.hwp"]["tables"]
    got = [{"rows": t.rows, "cols": t.cols, "cells": len(t.cells),
            "merged": sum(1 for c in t.cells if c.row_span > 1 or c.col_span > 1)} for t in tables]
    assert got == expected
    boxes = [b for b in _blocks(doc) if isinstance(b, TextBox)]
    assert len(boxes) == 1
    assert [p.text for p in boxes[0].blocks if isinstance(p, Paragraph)] == truth["budget.hwp"]["textbox"]


def test_report_merges_and_footnotes(samples):
    doc = hwpdown.read(samples / "report.hwp")
    table = next(b for b in _blocks(doc) if isinstance(b, Table))
    merged = sorted((c.row, c.col, c.row_span, c.col_span) for c in table.cells if c.row_span > 1 or c.col_span > 1)
    assert merged == [(0, 0, 2, 1), (0, 1, 1, 2), (0, 3, 2, 1), (3, 0, 1, 3)]
    assert doc.version == "5.0.3.0"


def test_extended_record_size_over_4095_bytes():
    long_text = "가" * 3000  # 6000 bytes of PARA_TEXT -> needs the 0xFFF extended size field
    doc = hwpdown.read(write_hwp5(SampleDoc([P(long_text)])))
    assert any(isinstance(b, Paragraph) and b.text == long_text for b in _blocks(doc))


def test_uncompressed_document_reads():
    doc = hwpdown.read(write_hwp5(SampleDoc([P("압축 없음")]), compress=False))
    assert [b.text for b in _blocks(doc) if isinstance(b, Paragraph)] == ["압축 없음"]


def test_record_header_roundtrip_and_tree():
    data = rec(0x20, 0, b"a") + rec(0x21, 1, b"b" * 5000) + rec(0x22, 1, b"") + rec(0x23, 0, b"")
    got = list(iter_records(data, Limits()))
    assert [(t, lv, len(p)) for t, lv, p in got] == [(0x20, 0, 1), (0x21, 1, 5000), (0x22, 1, 0), (0x23, 0, 0)]
    roots = build_tree(data, Limits())
    assert [len(r.children) for r in roots] == [2, 0]


def test_corrupt_inputs_raise_clear_errors():
    with pytest.raises(CorruptDocumentError):
        list(iter_records(b"\x01\x00", Limits()))
    with pytest.raises(CorruptDocumentError):
        list(iter_records(struct.pack("<I", (10 << 20) | 0x20) + b"abc", Limits()))
    with pytest.raises(CorruptDocumentError, match="FileHeader"):
        hwpdown.read(build_cfb({("Other",): b"x" * 10}))
    with pytest.raises(CorruptDocumentError, match="signature"):
        hwpdown.read(build_cfb({("FileHeader",): b"\0" * 256}))
    with pytest.raises(CorruptDocumentError, match="BodyText"):
        hwpdown.read(build_cfb({("FileHeader",): file_header(False)}))


def test_record_and_depth_limits():
    flat = b"".join(rec(0x20, 0, b"") for _ in range(10))
    with pytest.raises(LimitExceededError, match="max_records"):
        list(iter_records(flat, Limits(max_records=5)))
    deep = b"".join(rec(0x20, i, b"") for i in range(10))
    with pytest.raises(LimitExceededError, match="max_depth"):
        build_tree(deep, Limits(max_depth=4))


def test_table_cell_limit(samples):
    with pytest.raises(LimitExceededError, match="max_table_cells"):
        hwpdown.read(samples / "report.hwp", limits=Limits(max_table_cells=3))
