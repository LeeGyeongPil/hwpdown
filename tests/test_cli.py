import json

from hwpdown.cli import main


def test_convert_and_help(samples, capsys, tmp_path):
    assert main(["convert", str(samples / "report.hwp")]) == 0
    out = capsys.readouterr().out
    assert out.startswith("> 읽는 법:")
    assert "<table>" in out

    assert main(["convert", str(samples / "report.hwp"), "--no-legend"]) == 0
    assert "읽는 법" not in capsys.readouterr().out

    target = tmp_path / "out.md"
    assert main(["convert", str(samples / "report.hwpx"), "-o", str(target)]) == 0
    assert "<table>" in target.read_text(encoding="utf-8")

    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    help_text = capsys.readouterr().out
    assert "한글과컴퓨터의 한/글 문서 파일(.hwp) 공개 문서를 참고하여 개발하였습니다" in help_text


def test_convert_json_and_style(samples, capsys):
    assert main(["convert", str(samples / "report.hwp"), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["format"] == "hwp5" and data["sections"]
    assert main(["convert", str(samples / "report.hwp"), "--style", "plain"]) == 0
    assert "<table>" not in capsys.readouterr().out


def test_samples_build_and_unsupported_exit(tmp_path, capsys):
    assert main(["samples", "build", str(tmp_path / "s")]) == 0
    assert (tmp_path / "s" / "report.hwp").is_file()
    junk = tmp_path / "junk.hwp"
    junk.write_bytes(b"hello")
    assert main(["convert", str(junk)]) == 2


def test_directory_argument_gives_friendly_error(samples, capsys):
    assert main(["convert", str(samples)]) == 2
    err = capsys.readouterr().err
    assert "is a directory" in err and "Traceback" not in err


def test_batch_output_dir_converts_and_names_files(samples, tmp_path, capsys):
    out = tmp_path / "new" / "out"
    files = [str(samples / "report.hwp"), str(samples / "budget.hwp")]
    assert main(["convert", *files, "-d", str(out), "--no-legend"]) == 0
    err = capsys.readouterr().err
    assert "converted 2, skipped 0" in err and "wrote" in err
    assert sorted(p.name for p in out.iterdir()) == ["budget.md", "report.md"]
    assert "읽는 법" not in (out / "report.md").read_text(encoding="utf-8")
    assert main(["convert", files[0], "-d", str(out), "--json"]) == 0
    assert json.loads((out / "report.json").read_text(encoding="utf-8"))["format"] == "hwp5"


def test_batch_skips_failures_and_returns_1(samples, tmp_path, capsys):
    out = tmp_path / "o"
    args = ["convert", str(samples / "distribution.hwp"), str(tmp_path / "missing.hwp"),
            str(tmp_path), str(samples / "report.hwpx"), "-d", str(out)]
    assert main(args) == 1
    err = capsys.readouterr().err
    assert err.count("skipped ") >= 3 and "converted 1, skipped 3" in err
    assert (out / "report.md").is_file()


def test_batch_argument_errors_and_collision(samples, tmp_path, capsys):
    two = [str(samples / "report.hwp"), str(samples / "budget.hwp")]
    for extra in ([], ["-o", str(tmp_path / "x.md")]):
        try:
            main(["convert", *two, *extra])
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError("expected argparse error")
    try:
        main(["convert", two[0], "-o", str(tmp_path / "x.md"), "-d", str(tmp_path)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("expected argparse error")
    capsys.readouterr()
    out = tmp_path / "c"
    assert main(["convert", str(samples / "report.hwp"), str(samples / "report.hwpx"), "-d", str(out)]) == 1
    assert "converted 1, skipped 1" in capsys.readouterr().err
    assert [p.name for p in out.iterdir()] == ["report.md"]


def test_single_file_path_unchanged(samples, capsys):
    assert main(["convert", str(samples / "distribution.hwp")]) == 3
    assert capsys.readouterr().out == ""
