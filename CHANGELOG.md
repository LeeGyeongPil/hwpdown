# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] - 2026-11-26

### Added
- `convert` accepts several files with `-d/--output-dir DIR`: writes `DIR/<name>.md` (or `.json`), skips files that fail or whose output name collides, prints `converted N, skipped M` and exits 1 if any were skipped. Single-file output and exit codes are unchanged.

## [0.1.1] - 2026-11-10

### Changed
- README: comparison table replaced by a short when-to-use section.

## [0.1.0]

### Added
- HWP 5.0 (OLE/CFB, raw deflate records) and HWPX (OWPML zip) readers in pure Python.
- Markdown renderer: merged-cell HTML tables, global footnote renumbering, automatic numbering restoration, size-based heading promotion, "읽는 법" legend.
- Safety limits: real decompressed-byte caps, record/depth/cell caps, distribution and password documents rejected.
- CLI: `detect`, `convert`, `samples build`, `bench` (mock rule-based reader and OpenAI-compatible reader).
- Synthetic sample corpus with ground-truth questions.
