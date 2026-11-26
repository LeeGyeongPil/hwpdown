"""Command line interface: detect / convert / samples build / bench.

Exit codes: 0 ok, 2 unsupported or corrupt input, 3 distribution or password document, 4 limit exceeded.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

from . import CREDIT, __version__, detect_format, read, render
from .errors import HwpdownError
from .render import RenderOptions

EPILOG = (
    f"{CREDIT}\n"
    "Specs: Hancom HWP 5.0 file format (public document), KS X 6101 (OWPML), Microsoft [MS-CFB].\n"
    "Exit codes: 0 ok, 2 unsupported/corrupt, 3 distribution/password document, 4 limit exceeded."
)


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hwpdown",
        description="Convert HWP 5.0 / HWPX documents to LLM-friendly Markdown (pure Python).",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--version", action="version", version=f"hwpdown {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("detect", help="print the real format (hwp5 / hwpx), judged by magic bytes")
    d.add_argument("file")

    c = sub.add_parser("convert", help="convert a document to Markdown")
    c.add_argument("file", nargs="+", help="document(s) to convert; several files need -d")
    c.add_argument("-o", "--output", help="write to this file instead of stdout (single file only)")
    c.add_argument("-d", "--output-dir", metavar="DIR",
                   help="batch mode: write DIR/<name>.md (or .json) per input; failures are skipped, exit 1")
    c.add_argument("--style", choices=["llm", "plain", "gfm-naive"], default="llm",
                   help="llm (default) keeps structure; plain and gfm-naive are comparison baselines")
    c.add_argument("--no-legend", action="store_true", help="omit the '읽는 법' legend")
    c.add_argument("--json", action="store_true", help="print the intermediate representation as JSON")

    s = sub.add_parser("samples", help="synthetic sample documents")
    ssub = s.add_subparsers(dest="samples_cmd", required=True)
    sb = ssub.add_parser("build", help="(re)generate the sample documents into DIR")
    sb.add_argument("dir")

    b = sub.add_parser("bench", help="compare rendering styles on a folder of documents + questions.json")
    b.add_argument("dir")
    b.add_argument("--answerer", choices=["mock", "llm"], default="mock",
                   help="mock: rule-based practice reader (not an LLM); llm: OpenAI-compatible endpoint")
    b.add_argument("--out", help="append per-question results to this JSONL file (resumable)")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.cmd == "convert":
        if args.output and args.output_dir:
            parser.error("convert: -o/--output and -d/--output-dir cannot be used together")
        if len(args.file) > 1 and not args.output_dir:
            parser.error("convert: several files need -d/--output-dir DIR (stdout and -o take one file)")
    try:
        return _run(args)
    except HwpdownError as exc:
        print(f"hwpdown: {exc}", file=sys.stderr)
        return exc.exit_code
    except FileNotFoundError as exc:
        print(f"hwpdown: file not found: {exc.filename}", file=sys.stderr)
        return 2
    except IsADirectoryError as exc:
        print(f"hwpdown: {exc.filename} is a directory - pass a .hwp/.hwpx file", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"hwpdown: cannot read {exc.filename}: {exc.strerror}", file=sys.stderr)
        return 2


def _convert_one(args: argparse.Namespace, path: str):
    """Read one document and return (rendered text, warnings)."""
    doc = read(path)
    if args.json:
        text = json.dumps(dataclasses.asdict(doc), ensure_ascii=False, indent=2)
    else:
        text = render(doc, RenderOptions(style=args.style, legend=not args.no_legend))
    return text, doc.warnings


def _convert_batch(args: argparse.Namespace) -> int:
    """Convert every file into the output directory; skip failures, report a summary."""
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".json" if args.json else ".md"
    converted = skipped = 0
    claimed: set = set()
    for name in args.file:
        target = out_dir / (Path(name).stem + suffix)
        if target in claimed:
            print(f"warning: skipped {name}: output {target} already written by another input", file=sys.stderr)
            skipped += 1
            continue
        try:
            text, warnings = _convert_one(args, name)
            target.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        except (HwpdownError, OSError) as exc:
            reason = exc.strerror if isinstance(exc, OSError) and exc.strerror else str(exc)
            print(f"warning: skipped {name}: {reason}", file=sys.stderr)
            skipped += 1
            continue
        claimed.add(target)
        converted += 1
        print(f"wrote {target}", file=sys.stderr)
        for w in warnings:
            print(f"warning: {name}: {w}", file=sys.stderr)
    print(f"converted {converted}, skipped {skipped}", file=sys.stderr)
    return 1 if skipped else 0


def _run(args: argparse.Namespace) -> int:
    if args.cmd == "detect":
        print(detect_format(args.file))
        return 0
    if args.cmd == "convert":
        if args.output_dir:
            return _convert_batch(args)
        doc = _convert_one(args, args.file[0])
        text, warnings = doc
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            print(f"wrote {args.output}", file=sys.stderr)
        else:
            sys.stdout.write(text if text.endswith("\n") else text + "\n")
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        return 0
    if args.cmd == "samples":
        from .samples.build import write_samples

        for path in write_samples(args.dir):
            print(path)
        return 0
    if args.cmd == "bench":
        from .bench import run

        report = run(args.dir, answerer=args.answerer, out=args.out)
        print(report.format())
        return 0
    return 2
