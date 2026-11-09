# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

## [0.1.0]

### Added
- HWP 5.0 (OLE/CFB, raw deflate records) and HWPX (OWPML zip) readers in pure Python.
- Markdown renderer: merged-cell HTML tables, global footnote renumbering, automatic numbering restoration, size-based heading promotion, "읽는 법" legend.
- Safety limits: real decompressed-byte caps, record/depth/cell caps, distribution and password documents rejected.
- CLI: `detect`, `convert`, `samples build`, `bench` (mock rule-based reader and OpenAI-compatible reader).
- Synthetic sample corpus with ground-truth questions.
