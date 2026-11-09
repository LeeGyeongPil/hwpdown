import io
import zipfile

import pytest

from hwpdown import UnsupportedFormatError, detect_format
from hwpdown.cli import main


def test_detect_by_magic_not_extension(samples, capsys):
    # the file is named .hwpx but its bytes are an OLE (HWP 5.0) container
    assert detect_format(samples / "disguised.hwpx") == "hwp5"
    assert detect_format(samples / "report.hwpx") == "hwpx"
    assert detect_format((samples / "report.hwp").read_bytes()) == "hwp5"
    assert main(["detect", str(samples / "disguised.hwpx")]) == 0
    assert capsys.readouterr().out.strip() == "hwp5"


def test_random_bytes_rejected(tmp_path, capsys):
    with pytest.raises(UnsupportedFormatError):
        detect_format(b"not a hwp file at all")
    junk = tmp_path / "x.hwp"
    junk.write_bytes(b"\x00\x01\x02garbage")
    assert main(["detect", str(junk)]) == 2
    assert "hwpdown:" in capsys.readouterr().err


def test_zip_without_hwp_mimetype_rejected():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
    with pytest.raises(UnsupportedFormatError, match="mimetype"):
        detect_format(buf.getvalue())
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("other.txt", "x")
    with pytest.raises(UnsupportedFormatError):
        detect_format(buf.getvalue())


def test_missing_file_exit_code(tmp_path):
    assert main(["detect", str(tmp_path / "nope.hwp")]) == 2
