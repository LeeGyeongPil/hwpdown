"""Create tiny compression-bomb files in a temp folder and show hwpdown refusing them.

Run: uv run python examples/make_bomb.py
Nothing is written into the repository; the files live in a temporary directory.
Expected: both conversions stop with exit code 4 and a message telling how to raise the limit.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

from hwpdown.samples.hwp5_writer import write_bomb_hwp5
from hwpdown.samples.hwpx_writer import write_bomb_hwpx

with tempfile.TemporaryDirectory() as tmp:
    for name, data in (("bomb.hwp", write_bomb_hwp5(80)), ("bomb.hwpx", write_bomb_hwpx(80))):
        path = Path(tmp) / name
        path.write_bytes(data)
        print(f"{name}: {len(data):,} bytes on disk, 80 MiB when inflated")
        done = subprocess.run(
            [sys.executable, "-c", "import sys; from hwpdown.cli import main; sys.exit(main(sys.argv[1:]))",
             "convert", str(path)],
            capture_output=True, text=True)
        print(f"  exit code: {done.returncode}\n  stderr: {done.stderr.strip()}")
