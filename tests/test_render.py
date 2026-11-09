import re

import hwpdown
from hwpdown import RenderOptions


def _table_html(path, **kw):
    md = hwpdown.to_markdown(path, options=RenderOptions(legend=False, **kw))
    return re.search(r"<table>.*?</table>", md, re.S).group(0)


def test_merged_table_html_same_for_hwp_and_hwpx(samples):
    a = _table_html(samples / "report.hwp")
    b = _table_html(samples / "report.hwpx")
    assert a == b
    assert a.count('rowspan="2"') == 2
    assert a.count('colspan="2"') == 1
    assert a.count('colspan="3"') == 1
    row = next(r for r in a.splitlines() if "합계" in r)
    assert 'colspan="3"' in row and "220" in row  # same <tr>
    assert a.count("<th") == 5 and "<th>상반기</th>" in a  # two header rows are <th>


def test_footnotes_global_numbering(samples):
    for name in ("report.hwp", "report.hwpx"):
        md = hwpdown.to_markdown(samples / name)
        assert "구조 보존 비교용 가상 샘플이다.[^1]" in md
        assert "표의 값은 분기별 합계이다.[^2]" in md
        assert "[^1]: 금액 단위는 백만 원이다." in md
        assert "[^2]: 수치는 모두 가상의 값이다." in md
        assert md.rstrip().endswith("수치는 모두 가상의 값이다.")  # definitions come at the end


def test_footnote_numbering_continues_across_text_box_and_cells(samples):
    md = hwpdown.to_markdown(samples / "budget.hwp")
    assert "각주가 있는 문단이다.[^1]" in md and "[^1]: 예산 각주 내용" in md


def test_plain_table_without_merges_is_gfm(samples):
    md = hwpdown.to_markdown(samples / "budget.hwp", options=RenderOptions(legend=False))
    assert "| A1 | A2 | A3 |\n| --- | --- | --- |" in md
    assert md.count("<table>") == 1  # only the merged table needs HTML
    assert "> [글상자] 글상자 안내 문단 하나\n> 글상자 안내 문단 둘" in md


def test_table_mode_override(samples):
    md = hwpdown.to_markdown(samples / "budget.hwp", options=RenderOptions(legend=False, table_mode="html"))
    assert md.count("<table>") == 2


def test_gfm_naive_reproduces_column_drift(samples):
    md = hwpdown.to_markdown(samples / "report.hwp", options=RenderOptions(style="gfm-naive", legend=False))
    assert "| 합계 | 220 |  |  |" in md  # 220 landed under the wrong column


def test_plain_style_has_no_markup(samples):
    md = hwpdown.to_markdown(samples / "report.hwp", options=RenderOptions(style="plain"))
    assert "<table>" not in md and "[^" not in md and "#" not in md
    assert "읽는 법" not in md


def test_unknown_style_message(samples):
    import pytest

    with pytest.raises(ValueError, match="Unknown style"):
        hwpdown.to_markdown(samples / "report.hwp", options=RenderOptions(style="x"))  # type: ignore[arg-type]
