"""File validation utilities for drone log files."""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

SUPPORTED_EXTENSIONS = {'.tlog', '.bin', '.log', '.tlv'}
MAX_SIZE_MB = 500
MIN_SIZE_BYTES = 16  # any real log has at least a header


def validate_file(file_obj, filename: str) -> Tuple[bool, str]:
    """
    Validate an uploaded drone log file.

    Returns (is_valid, message). On success, message is the detected extension.
    On failure, message describes the problem in user-friendly terms.
    """
    if file_obj is None:
        return False, "No file provided."
    if not filename or not isinstance(filename, str):
        return False, "Filename is missing or invalid."

    try:
        ext = Path(filename).suffix.lower()
    except Exception:
        return False, "Could not determine file extension."

    if not ext:
        return False, (
            "File has no extension. Expected one of: "
            f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if ext not in SUPPORTED_EXTENSIONS:
        return False, (
            f"Unsupported file extension '{ext}'. Supported: "
            f"{', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    size = getattr(file_obj, 'size', None)
    if size is not None:
        try:
            size = int(size)
        except (TypeError, ValueError):
            size = None

    if size is not None:
        if size < MIN_SIZE_BYTES:
            return False, f"File is too small ({size} bytes) to be a valid log."
        if size > MAX_SIZE_MB * 1024 * 1024:
            return False, (
                f"File too large ({size / 1024 / 1024:.1f} MB). "
                f"Limit is {MAX_SIZE_MB} MB."
            )

    # Magic-byte sniff (best-effort; never block on this)
    warning = None
    try:
        if hasattr(file_obj, 'getvalue'):
            head = file_obj.getvalue()[:32]
            if ext == '.bin' and len(head) >= 2:
                # ArduPilot DataFlash logs begin with 0xA3 0x95 (FMT header)
                if head[0] != 0xA3 or head[1] != 0x95:
                    warning = (
                        "warning: file does not start with the usual ArduPilot "
                        "DataFlash header (0xA3 0x95). Will attempt to parse anyway."
                    )
    except Exception:
        # Magic-byte sniffing is best-effort and should never break validation
        pass

    return True, warning if warning else ext


def format_size(num_bytes) -> str:
    """Human-readable file size. Never raises."""
    try:
        n = float(num_bytes)
    except (TypeError, ValueError):
        return "unknown"
    if n < 0:
        return "unknown"
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
