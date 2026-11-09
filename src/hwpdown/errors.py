"""Exception hierarchy. Every error carries a message that says how to fix or avoid it."""
from __future__ import annotations


class HwpdownError(Exception):
    """Base class for all hwpdown errors."""

    exit_code = 2


class UnsupportedFormatError(HwpdownError):
    """The input is neither an HWP 5.0 (OLE) nor an HWPX (zip + mimetype) file."""

    exit_code = 2


class CorruptDocumentError(HwpdownError):
    """The container looks like HWP/HWPX but its content cannot be parsed."""

    exit_code = 2


class DistributionDocumentError(HwpdownError):
    """Distribution (copy-protected) or password-protected document; hwpdown does not decrypt."""

    exit_code = 3


class LimitExceededError(HwpdownError):
    """A safety limit (decompressed bytes, records, depth, table cells) was exceeded."""

    exit_code = 4
