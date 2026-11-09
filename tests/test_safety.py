import time
import tracemalloc

import pytest

import hwpdown
from hwpdown import DistributionDocumentError, LimitExceededError
from hwpdown.cli import main
from hwpdown.limits import Limits
from hwpdown.samples.cfb import build_cfb
from hwpdown.samples.hwp5_writer import file_header, write_bomb_hwp5
from hwpdown.samples.hwpx_writer import write_bomb_hwpx


@pytest.mark.parametrize("maker", [write_bomb_hwp5, write_bomb_hwpx], ids=["hwp5", "hwpx"])
def test_bomb_rejected_fast(maker):
    data = maker(300)  # about 300 MB once inflated, a few hundred KB on disk
    assert len(data) < 5_000_000
    limits = Limits()
    tracemalloc.start()
    t0 = time.perf_counter()
    with pytest.raises(LimitExceededError):
        hwpdown.read(data, limits=limits)
    elapsed = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert elapsed < 2.0
    assert peak < limits.max_stream_bytes + 48 * 1024 * 1024


def test_bomb_cli_exit_code_and_message(tmp_path, capsys):
    p = tmp_path / "bomb.hwp"
    p.write_bytes(write_bomb_hwp5(80))
    assert main(["convert", str(p)]) == 4
    assert "Limits(" in capsys.readouterr().err  # tells the user how to raise the limit


def test_custom_limit_is_honoured():
    data = write_bomb_hwp5(4)
    with pytest.raises(LimitExceededError):
        hwpdown.read(data, limits=Limits(max_stream_bytes=1024 * 1024))


def test_distribution_detected(samples, capsys):
    with pytest.raises(DistributionDocumentError, match="배포용"):
        hwpdown.read(samples / "distribution.hwp")
    assert main(["convert", str(samples / "distribution.hwp")]) == 3
    assert "배포용" in capsys.readouterr().err


def test_password_document_detected():
    data = build_cfb({("FileHeader",): file_header(True, encrypted=True)})
    with pytest.raises(DistributionDocumentError, match="암호"):
        hwpdown.read(data)
