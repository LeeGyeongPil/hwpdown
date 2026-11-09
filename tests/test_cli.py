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
