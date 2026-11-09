import pytest

import hwpdown
from hwpdown import RenderOptions


@pytest.mark.parametrize("name", ["report.hwp", "report.hwpx"])
def test_heading_by_font_size_ratio(samples, name):
    md = hwpdown.to_markdown(samples / name, options=RenderOptions(legend=False))
    lines = md.splitlines()
    assert "# 사업 현황 보고" in lines  # 16 pt over a 10 pt body
    assert "## 현황 요약" in lines  # 12 pt
    assert "본 문서는 구조 보존 비교용 가상 샘플이다.[^1]" in lines  # body stays body


def test_headings_off_for_plain_style(samples):
    md = hwpdown.to_markdown(samples / "report.hwp", options=RenderOptions(style="plain", legend=False))
    assert "# 사업 현황 보고" not in md


def test_high_ratio_disables_promotion(samples):
    md = hwpdown.to_markdown(samples / "report.hwp", options=RenderOptions(legend=False, heading_ratio=5.0))
    assert not any(line.startswith("#") for line in md.splitlines())
