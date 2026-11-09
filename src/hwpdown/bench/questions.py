"""Question-set loading and validation (``questions.json`` next to the documents)."""
from __future__ import annotations

import json
from pathlib import Path

from ..errors import HwpdownError

TYPES = {"cell", "footnote", "number", "heading"}


class BenchError(HwpdownError):
    """Bad question file or unusable answerer configuration."""

    exit_code = 2


def load_questions(corpus_dir: "str | Path") -> dict[str, list[dict]]:
    """Return ``{document file name: [question, ...]}``; documents without questions are dropped."""
    path = Path(corpus_dir) / "questions.json"
    if not path.is_file():
        raise BenchError(
            f"{path} not found. Put documents and a questions.json in the folder "
            "(see samples/questions.json for the format)."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        docs = data["documents"]
    except (ValueError, KeyError, TypeError) as exc:
        raise BenchError(f"{path}: expected an object with a 'documents' key ({exc}).") from exc
    out: dict[str, list[dict]] = {}
    for name, spec in docs.items():
        qs = spec.get("questions", []) if isinstance(spec, dict) else []
        for q in qs:
            missing = [k for k in ("id", "type", "question", "answer") if k not in q]
            if missing or q["type"] not in TYPES:
                raise BenchError(
                    f"{path}: question {q.get('id', '?')} in {name} needs id/type/question/answer "
                    f"and type in {sorted(TYPES)} (problem: {missing or q['type']})."
                )
        if qs:
            if not (Path(corpus_dir) / name).is_file():
                raise BenchError(f"{path} refers to {name}, but that file is not in {corpus_dir}.")
            out[name] = qs
    if not out:
        raise BenchError(f"{path} has no questions.")
    return out
