"""Minimal use of hwpdown as a library: read a document and print LLM-friendly Markdown."""
import sys

import hwpdown
from hwpdown import RenderOptions

path = sys.argv[1] if len(sys.argv) > 1 else "samples/report.hwp"
doc = hwpdown.read(path)  # format is detected by magic bytes, not by extension
print(hwpdown.render(doc, RenderOptions(legend=True)))
