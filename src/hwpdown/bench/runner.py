"""Run style x document x question, append results to JSONL (resumable), print a summary table."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .. import read, render
from ..render import RenderOptions
from .answerers import MOCK_BANNER, LLMAnswerer, mock_answer
from .questions import BenchError, load_questions

STYLES = ("plain", "gfm-naive", "llm")


def _norm(s: str) -> str:
    return " ".join(s.split())


@dataclass
class BenchReport:
    banner: str
    results: list[dict] = field(default_factory=list)

    def accuracy(self, style: str) -> float:
        rows = [r for r in self.results if r["style"] == style]
        return sum(r["correct"] for r in rows) / len(rows) if rows else 0.0

    def format(self) -> str:
        lines = [self.banner]
        styles = [s for s in STYLES if any(r["style"] == s for r in self.results)]
        total = len([r for r in self.results if styles and r["style"] == styles[0]])
        lines += [f"questions per style: {total}", "", f"{'style':<11}{'correct':>8}{'total':>7}{'accuracy':>10}"]
        for s in styles:
            rows = [r for r in self.results if r["style"] == s]
            ok = sum(r["correct"] for r in rows)
            lines.append(f"{s:<11}{ok:>8}{len(rows):>7}{self.accuracy(s):>10.2f}")
        wrong = [r for r in self.results if not r["correct"]]
        if wrong:
            lines += ["", "wrong answers:"]
            for r in wrong:
                lines.append(f"  [{r['style']}] {r['doc']} {r['id']}: expected {r['expected']!r}, got {r['got']!r}")
        return "\n".join(lines)


def _load_done(out: Path | None) -> dict[tuple, dict]:
    done: dict[tuple, dict] = {}
    if out and out.is_file():
        for line in out.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                done[(r["mode"], r["doc"], r["style"], r["id"])] = r
    return done


def run(corpus_dir: "str | Path", styles: Iterable[str] = STYLES, answerer: str = "mock",
        out: "str | Path | None" = None, on_result: Callable[[dict], None] | None = None) -> BenchReport:
    """Run the bench over ``corpus_dir`` (documents + questions.json)."""
    corpus = Path(corpus_dir)
    questions = load_questions(corpus)
    if answerer == "mock":
        fn, banner, mode = mock_answer, MOCK_BANNER, "mock"
    elif answerer == "llm":
        llm = LLMAnswerer()
        fn, banner, mode = llm, llm.banner(), "llm"
    else:
        raise BenchError(f"Unknown answerer {answerer!r}; use 'mock' or 'llm'.")
    out_path = Path(out) if out else None
    done = _load_done(out_path)
    report = BenchReport(banner)
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(out_path, "a", encoding="utf-8") if out_path else None
    try:
        for name, qs in questions.items():
            doc = read(corpus / name)
            for style in styles:
                text = render(doc, RenderOptions(style=style, legend=False))  # type: ignore[arg-type]
                for q in qs:
                    key = (mode, name, style, q["id"])
                    if key in done:  # resume: skip what an earlier run already finished
                        report.results.append(done[key])
                        continue
                    got = fn(text, q)
                    rec = {"mode": mode, "doc": name, "style": style, "id": q["id"], "type": q["type"],
                           "question": q["question"], "expected": q["answer"], "got": got,
                           "correct": _norm(got) == _norm(q["answer"])}
                    report.results.append(rec)
                    if fh:
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        fh.flush()
                    if on_result:
                        on_result(rec)
    finally:
        if fh:
            fh.close()
    return report
