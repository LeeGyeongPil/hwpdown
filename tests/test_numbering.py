import pytest

import hwpdown
from hwpdown import RenderOptions
from hwpdown.numbering import format_number


@pytest.mark.parametrize("name", ["report.hwp", "report.hwpx"])
def test_numbering_restored_both_formats(samples, name):
    md = hwpdown.to_markdown(samples / name, options=RenderOptions(legend=False))
    assert "1. 첫째 항목" in md
    assert "2. 둘째 항목" in md
    assert "가. 세부 사항 하나" in md
    assert "나. 세부 사항 둘" in md


def test_numbering_can_be_turned_off(samples):
    md = hwpdown.to_markdown(samples / "report.hwp", options=RenderOptions(legend=False, numbering=False))
    assert "첫째 항목" in md and "1. 첫째 항목" not in md


@pytest.mark.parametrize("shape,expected", [(0, "1"), (8, "가"), (10, "ㄱ"), (13, "一"), (15, "갑")])
def test_number_shape_codes(shape, expected):
    assert format_number(shape, 1) == expected


def test_number_shape_progression():
    assert format_number(8, 2) == "나"
    assert format_number(2, 4) == "IV"
    assert format_number(1, 3) == "③"
