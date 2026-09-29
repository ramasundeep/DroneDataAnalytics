r"""Quick smoke test for the VBAT TLV parser.

Usage:
    python debug_tlv.py <path-to-tlv>

Prints progress at every step so it's obvious where things fail or stall.
"""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def log(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    log("== debug_tlv.py starting ==")
    log(f"Python:   {sys.version.split()[0]}")
    log(f"Argv:     {sys.argv}")

    if len(sys.argv) < 2:
        log("ERROR: missing path argument.")
        log('Usage: python debug_tlv.py "C:\\path\\to\\file.tlv"')
        return 2

    path = sys.argv[1]
    log(f"Path:     {path}")

    if not os.path.isfile(path):
        log(f"ERROR: file not found: {path}")
        return 3

    log(f"Size:     {os.path.getsize(path):,} bytes")

    # First-bytes sanity check.
    with open(path, 'rb') as f:
        head = f.read(8)
    log(f"Head:     {head!r}  (expected first 4 bytes b'SESS')")

    log("Importing parsers...")
    try:
        import pandas as pd
        from parsers import DroneLogParser
    except Exception as e:
        log(f"ERROR importing: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 4

    log("Parsing (this may take a few seconds for large files)...")
    parser = DroneLogParser(path)
    try:
        data = parser.parse()
    except Exception as e:
        log(f"PARSE FAILED: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 5

    meta = data.get('_meta', {}) or {}
    log("\n== Parse result ==")
    log(f"Format:        {meta.get('format')}")
    log(f"Total records: {meta.get('total_messages'):,}")
    log(f"Capped:        {meta.get('capped')}")
    log(f"Parser errors: {len(parser.errors)}")
    for err in parser.errors[:5]:
        log(f"  • {err}")
    if len(parser.errors) > 5:
        log(f"  … and {len(parser.errors) - 5} more")

    msg_types = meta.get('message_types') or {}
    if msg_types:
        log("\nTop 15 track frequencies:")
        for tag, count in sorted(msg_types.items(), key=lambda x: -x[1])[:15]:
            log(f"  {tag:<6} {count:>10,}")

    log("\nCommon-schema frames:")
    for key in ('position', 'attitude', 'vfr_hud', 'gps_raw', 'battery'):
        df = data.get(key)
        if isinstance(df, pd.DataFrame) and not df.empty:
            log(f"  {key:<10} rows={len(df):>8,}  cols={list(df.columns)}")
        else:
            log(f"  {key:<10} (empty)")

    pos = data.get('position')
    if isinstance(pos, pd.DataFrame) and not pos.empty:
        log("\nposition.head(3):")
        with pd.option_context('display.max_columns', None, 'display.width', 160):
            log(str(pos.head(3)))

    att = data.get('attitude')
    if isinstance(att, pd.DataFrame) and not att.empty:
        log("\nattitude.head(3) (radians):")
        with pd.option_context('display.max_columns', None, 'display.width', 160):
            log(str(att.head(3)))

    log("\n== Done ==")
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        log(f"UNCAUGHT: {type(e).__name__}: {e}")
        traceback.print_exc()
        sys.exit(99)
