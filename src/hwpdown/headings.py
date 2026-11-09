"""Promote paragraphs to headings by font size relative to the most common body size."""
from __future__ import annotations

from collections import Counter

from .ir import Document, Paragraph


def _dominant_size(p: Paragraph) -> float | None:
    weights: Counter[float] = Counter()
    for r in p.runs:
        size = getattr(r, "size_pt", None)
        if size:
            weights[round(size, 1)] += len(getattr(r, "text", ""))
    return weights.most_common(1)[0][0] if weights else None


def compute_levels(doc: Document, ratio: float) -> dict[int, int]:
    """Return ``{id(paragraph): heading level}`` (1 = largest) for top-level paragraphs."""
    candidates: list[tuple[Paragraph, float]] = []
    body: Counter[float] = Counter()
    for sec in doc.sections:
        for b in sec.blocks:
            if not isinstance(b, Paragraph):
                continue
            size = _dominant_size(b)
            if size is None:
                continue
            shape = doc.para_shapes.get(b.para_shape_id) if b.para_shape_id is not None else None
            if shape is not None and shape.head_type in (2, 3):
                continue
            body[size] += len(b.text)
            candidates.append((b, size))
    if not body:
        return {}
    base = body.most_common(1)[0][0]
    big = {s for _, s in candidates if s / base >= ratio}
    rank = {s: i + 1 for i, s in enumerate(sorted(big, reverse=True))}
    out: dict[int, int] = {}
    for p, s in candidates:
        text = p.text.strip()
        if s in rank and text and "\n" not in text and len(text) <= 100:
            out[id(p)] = min(rank[s], 6)
    return out
