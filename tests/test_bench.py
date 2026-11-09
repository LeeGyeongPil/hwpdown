import json

import pytest

from hwpdown.bench import run
from hwpdown.bench.questions import BenchError
from hwpdown.cli import main


def test_mock_bench_shows_structure_gain(samples, tmp_path, capsys):
    out = tmp_path / "res.jsonl"
    assert main(["bench", str(samples), "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert text.splitlines()[0] == "mode: mock — 연습용 규칙 판독기(LLM 아님)"

    report = run(samples, answerer="mock")
    assert report.accuracy("llm") == 1.0
    assert report.accuracy("plain") < 1.0
    assert report.accuracy("gfm-naive") < 1.0
    plain_h2 = [r for r in report.results if r["style"] == "plain" and r["id"] == "cell-h2"]
    assert plain_h2 and all(r["got"] == "100" and not r["correct"] for r in plain_h2)

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert rows and {"doc", "style", "id", "expected", "got", "correct"} <= set(rows[0])


def test_bench_jsonl_resumes_without_duplicates(samples, tmp_path):
    out = tmp_path / "res.jsonl"
    run(samples, answerer="mock", out=out)
    n = len(out.read_text(encoding="utf-8").splitlines())
    run(samples, answerer="mock", out=out)
    assert len(out.read_text(encoding="utf-8").splitlines()) == n


def test_llm_answerer_without_model_explains(samples, monkeypatch):
    monkeypatch.delenv("HWPDOWN_LLM_MODEL", raising=False)
    with pytest.raises(BenchError) as exc:
        run(samples, answerer="llm")
    assert "HWPDOWN_LLM_MODEL" in str(exc.value)


def test_dotenv_model_is_read_and_env_wins(samples, tmp_path, monkeypatch):
    import os

    (tmp_path / ".env").write_text(
        "# comment\nHWPDOWN_LLM_MODEL=foo\nHWPDOWN_LLM_BASE_URL=http://example.invalid/v1\n"
        "HWPDOWN_LLM_API_KEY=\n")
    monkeypatch.chdir(tmp_path)
    for k in ("HWPDOWN_LLM_MODEL", "HWPDOWN_LLM_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("HWPDOWN_LLM_BASE_URL", "http://127.0.0.1:9/v1")  # already set: must not be overridden
    with pytest.raises(BenchError, match="Cannot reach"):  # got past "MODEL is not set" to the connection step
        run(str(samples), answerer="llm")
    assert os.environ["HWPDOWN_LLM_MODEL"] == "foo"
    assert os.environ["HWPDOWN_LLM_BASE_URL"] == "http://127.0.0.1:9/v1"
    monkeypatch.delenv("HWPDOWN_LLM_MODEL")
