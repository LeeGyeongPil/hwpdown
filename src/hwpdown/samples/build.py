"""Sample documents (invented content) and the question set, generated entirely by code."""
from __future__ import annotations

import json
from pathlib import Path

from .hwp5_writer import write_distribution_hwp5, write_hwp5
from .hwpx_writer import write_hwpx
from .spec import C, NUM0, NUM1, Note, P, SampleDoc, T, TB

NOTE1 = "금액 단위는 백만 원이다."
NOTE2 = "수치는 모두 가상의 값이다."


def report_doc() -> SampleDoc:
    """Title by size only, numbered list, 4x4 merged table, two footnotes."""
    table = T(4, 4, [
        C(0, 0, [P("구분")], rs=2), C(0, 1, [P("2025년")], cs=2), C(0, 3, [P("비고")], rs=2),
        C(1, 1, [P("상반기")]), C(1, 2, [P("하반기")]),
        C(2, 0, [P("매출")]), C(2, 1, [P("100")]), C(2, 2, [P("120")]), C(2, 3, [P("증가")]),
        C(3, 0, [P("합계")], cs=3), C(3, 3, [P("220")]),
    ])
    return SampleDoc([
        P("사업 현황 보고", size=16.0),
        P("본 문서는 구조 보존 비교용 가상 샘플이다.", notes=[Note([P(NOTE1)])]),
        P("현황 요약", size=12.0),
        P("첫째 항목", shape=NUM0),
        P("세부 사항 하나", shape=NUM1),
        P("세부 사항 둘", shape=NUM1),
        P("둘째 항목", shape=NUM0),
        table,
        P("표의 값은 분기별 합계이다.", notes=[Note([P(NOTE2)])]),
    ])


def budget_doc() -> SampleDoc:
    """A plain table, then a text box and a footnote (their LIST_HEADERs must not become cells), then a merged table."""
    plain = T(3, 3, [C(r, c, [P(f"{'ABC'[r]}{c + 1}")]) for r in range(3) for c in range(3)])
    merged = T(2, 2, [C(0, 0, [P("분류")], cs=2), C(1, 0, [P("예산")]), C(1, 1, [P("50")])])
    return SampleDoc([
        P("예산 안내", size=16.0),
        plain,
        TB([P("글상자 안내 문단 하나"), P("글상자 안내 문단 둘")]),
        P("각주가 있는 문단이다.", notes=[Note([P("예산 각주 내용")])]),
        merged,
    ])


# Ground truth. "tables" lists the expected rows/cols/cell count/merged-cell count per table, in order.
_REPORT_Q = [
    {"id": "cell-h1", "type": "cell", "question": "2025년 상반기 매출은?", "row": ["매출"], "col": ["2025년", "상반기"], "answer": "100"},
    {"id": "cell-h2", "type": "cell", "question": "2025년 하반기 매출은?", "row": ["매출"], "col": ["2025년", "하반기"], "answer": "120"},
    {"id": "cell-total", "type": "cell", "question": "합계 행의 비고 열 값은?", "row": ["합계"], "col": ["비고"], "answer": "220"},
    {"id": "note-1", "type": "footnote", "question": "각주 1의 내용은?", "number": 1, "answer": NOTE1},
    {"id": "note-2", "type": "footnote", "question": "각주 2의 내용은?", "number": 2, "answer": NOTE2},
    {"id": "num-2", "type": "number", "question": "'둘째 항목'의 번호는?", "text": "둘째 항목", "answer": "2."},
    {"id": "num-sub", "type": "number", "question": "'세부 사항 둘'의 번호는?", "text": "세부 사항 둘", "answer": "나."},
    {"id": "head-2", "type": "heading", "question": "'현황 요약'은 몇 단계 제목인가?", "text": "현황 요약", "answer": "2"},
]
_REPORT_TABLES = [{"rows": 4, "cols": 4, "cells": 11, "merged": 4}]
QUESTIONS = {
    "documents": {
        "report.hwp": {"questions": _REPORT_Q, "tables": _REPORT_TABLES},
        "report.hwpx": {"questions": _REPORT_Q, "tables": _REPORT_TABLES},
        "budget.hwp": {
            "questions": [],
            "tables": [{"rows": 3, "cols": 3, "cells": 9, "merged": 0},
                       {"rows": 2, "cols": 2, "cells": 3, "merged": 1}],
            "textbox": ["글상자 안내 문단 하나", "글상자 안내 문단 둘"],
        },
    }
}


def build_samples() -> dict[str, bytes]:
    """Return ``{file name: bytes}`` for every committed sample (deterministic)."""
    report = report_doc()
    hwp5 = write_hwp5(report)
    return {
        "report.hwp": hwp5,
        "report.hwpx": write_hwpx(report),
        "budget.hwp": write_hwp5(budget_doc()),
        "disguised.hwpx": hwp5,  # extension says hwpx, content is HWP 5.0
        "distribution.hwp": write_distribution_hwp5(),
        "questions.json": (json.dumps(QUESTIONS, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    }


def write_samples(out_dir: "str | Path") -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, data in build_samples().items():
        p = out / name
        p.write_bytes(data)
        paths.append(p)
    return paths
