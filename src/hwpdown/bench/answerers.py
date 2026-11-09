"""Answerers: a rule-based practice reader (mock, not an LLM) and an OpenAI-compatible reader."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser

from .questions import BenchError

MOCK_BANNER = "mode: mock — 연습용 규칙 판독기(LLM 아님)"


class _TableParser(HTMLParser):
    """Collect <table> rows as (tag, rowspan, colspan, text) cells."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[tuple[str, int, int, str]]]] = []
        self._depth = 0
        self._cell: list | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self._depth += 1
            if self._depth == 1:
                self.tables.append([])
        elif self._depth == 1 and tag == "tr":
            self.tables[-1].append([])
        elif self._depth == 1 and tag in ("td", "th"):
            self._cell = [tag, int(a.get("rowspan") or 1), int(a.get("colspan") or 1), ""]
        elif tag == "br" and self._cell is not None:
            self._cell[3] += " "

    def handle_endtag(self, tag):
        if tag == "table":
            self._depth -= 1
        elif tag in ("td", "th") and self._cell is not None and self.tables and self.tables[-1]:
            c = self._cell
            self.tables[-1][-1].append((c[0], c[1], c[2], " ".join(c[3].split())))
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell[3] += data


def _expand(rows):
    """Expand rowspan/colspan into a rectangular grid of (tag, text)."""
    grid: dict[tuple[int, int], tuple[str, str]] = {}
    for r, row in enumerate(rows):
        c = 0
        for tag, rs, cs, text in row:
            while (r, c) in grid:
                c += 1
            for dr in range(rs):
                for dc in range(cs):
                    grid[(r + dr, c + dc)] = (tag, text)
            c += cs
    nrows = max((k[0] for k in grid), default=-1) + 1
    ncols = max((k[1] for k in grid), default=-1) + 1
    return [[grid.get((r, c), ("td", "")) for c in range(ncols)] for r in range(nrows)]


def _cell_from_html(text: str, row: list[str], col: list[str]) -> str | None:
    p = _TableParser()
    p.feed(text)
    for rows in p.tables:
        grid = _expand(rows)
        hdr = 0
        while hdr < len(grid) and all(t == "th" for t, _ in grid[hdr]):
            hdr += 1
        for ci in range(len(grid[0]) if grid else 0):
            path = [grid[r][ci][1] for r in range(hdr)]
            if all(part in path for part in col):
                for r in range(hdr, len(grid)):
                    if grid[r][0][1] == row[0]:
                        return grid[r][ci][1]
    return None


def _cell_from_gfm(text: str, row: list[str], col: list[str]) -> str | None:
    lines = [ln for ln in text.splitlines() if ln.startswith("|")]
    table = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in lines
             if not re.fullmatch(r"\|[\s\-|:]+\|", ln.strip())]
    if len(table) < 2:
        return None
    header = table[0]
    idx = [i for i, h in enumerate(header) if h == col[-1]]
    if not idx:
        return ""  # column cannot be located: the reader has nothing to answer
    for r in table[1:]:
        if r and r[0] == row[0]:
            return r[idx[0]] if idx[0] < len(r) else ""
    return ""


def _cell_from_text(text: str, row: list[str]) -> str:
    """Common keyword-proximity reading: the first number after the row name."""
    for line in text.splitlines():
        if row[0] in line:
            nums = re.findall(r"\d+(?:\.\d+)?", line.split(row[0], 1)[1])
            return nums[0] if nums else ""
    return ""


def mock_answer(text: str, q: dict) -> str:
    """Rule-based practice reader. It only looks at the rendered text, like an LLM would."""
    kind = q["type"]
    if kind == "cell":
        row, col = q["row"], q["col"]
        if "<table>" in text:
            got = _cell_from_html(text, row, col)
            if got is not None:
                return got
        if "| --- |" in text:
            got = _cell_from_gfm(text, row, col)
            if got is not None:
                return got
        return _cell_from_text(text, row)
    if kind == "footnote":
        m = re.search(rf"^\[\^{q['number']}\]:\s*(.+)$", text, re.M)
        return m.group(1).strip() if m else ""
    if kind == "number":
        m = re.search(rf"^(\S+)\s+{re.escape(q['text'])}\s*$", text, re.M)
        return m.group(1) if m else ""
    if kind == "heading":
        m = re.search(rf"^(#{{1,6}})\s+{re.escape(q['text'])}\s*$", text, re.M)
        return str(len(m.group(1))) if m else "0"
    return ""


def load_dotenv(path: str = ".env") -> None:
    """Read KEY=VALUE lines from ``path`` into os.environ (never overrides variables already set)."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return  # no .env file is fine
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and value and key not in os.environ:  # empty values (as in .env.example) stay unset
            os.environ[key] = value


class LLMAnswerer:
    """OpenAI-compatible chat endpoint (local Ollama by default). Slow is fine: the timeout is generous."""

    def __init__(self) -> None:
        load_dotenv()  # `cp .env.example .env` works without extra dependencies
        self.base = os.environ.get("HWPDOWN_LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")
        self.model = os.environ.get("HWPDOWN_LLM_MODEL", "")
        self.key = os.environ.get("HWPDOWN_LLM_API_KEY", "")
        if not self.model:
            raise BenchError(
                "HWPDOWN_LLM_MODEL is not set. For the real mode set a model name, e.g. "
                "`HWPDOWN_LLM_MODEL=<model you pulled in Ollama>`, or use the default mock answerer."
            )
        self.timeout = 900  # a shared local model can be slow; slowness is not an error

    def banner(self) -> str:
        return f"mode: llm — {self.model} @ {self.base}"

    def __call__(self, text: str, q: dict) -> str:
        prompt = ("아래 문서만 보고 질문에 답하세요. 답만 짧게 쓰세요(숫자·낱말·번호만).\n\n"
                  f"[문서]\n{text}\n\n[질문]\n{q['question']}\n[답]")
        body = json.dumps({"model": self.model, "temperature": 0,
                           "messages": [{"role": "user", "content": prompt}]}).encode()
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        req = urllib.request.Request(f"{self.base}/chat/completions", data=body, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()
        except (urllib.error.URLError, OSError) as exc:
            raise BenchError(
                f"Cannot reach {self.base} ({exc}). Start the server (for Ollama: `ollama serve`) "
                "or set HWPDOWN_LLM_BASE_URL; finished answers are already saved in --out."
            ) from exc
        except (KeyError, ValueError, IndexError) as exc:
            raise BenchError(f"Unexpected reply from {self.base}: {exc}") from exc
