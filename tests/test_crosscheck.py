"""Cross-checks against a third-party implementation (python-hwpx, dev dependency only)."""
import warnings

import pytest

hwpx = pytest.importorskip("hwpx", reason="python-hwpx is a dev-only dependency (uv sync installs it)")

import hwpdown  # noqa: E402
from hwpdown.ir import Table  # noqa: E402


def _truth_doc(path):
    from hwpx import HwpxDocument

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # python-hwpx 6.x warns about APIs removed in 7.0
        doc = HwpxDocument.new()
        t = doc.add_table(4, 4)
        for (r, c), v in {(0, 0): "구분", (0, 1): "2025년", (0, 3): "비고", (1, 1): "상반기", (1, 2): "하반기",
                          (2, 0): "매출", (2, 1): "100", (2, 2): "120", (2, 3): "증가",
                          (3, 0): "합계", (3, 3): "220"}.items():
            t.set_cell_text(r, c, v)
        for rng in ("A1:A2", "B1:C1", "D1:D2", "A4:C4"):
            doc.merge_table_cells(t, rng)
        doc.save_to_path(str(path))


def test_reads_python_hwpx_generated_merges(tmp_path):
    p = tmp_path / "third_party.hwpx"
    _truth_doc(p)
    doc = hwpdown.read(p)
    table = next(b for s in doc.sections for b in s.blocks if isinstance(b, Table))
    merged = sorted((c.row, c.col, c.row_span, c.col_span) for c in table.cells if c.row_span > 1 or c.col_span > 1)
    assert merged == [(0, 0, 2, 1), (0, 1, 1, 2), (0, 3, 2, 1), (3, 0, 1, 3)]
    md = hwpdown.to_markdown(p)
    assert 'colspan="3"' in md and "220" in md.split('colspan="3"')[1]


def test_python_hwpx_opens_our_hwp5(samples):
    from hwpx import HwpxDocument

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        text = HwpxDocument.open(str(samples / "report.hwp")).export_rich_markdown()
    for word in ("구분", "2025년", "합계", "220"):
        assert word in text
