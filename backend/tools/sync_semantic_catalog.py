"""
Validate semantic_catalog.yaml against the live warehouse.

Prefer:  python tools/semantic_catalog_tool.py validate
        python tools/semantic_catalog_tool.py refresh --write

This module delegates to semantic_catalog_tool for backward compatibility.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate semantic catalog vs warehouse")
    parser.add_argument("--json", metavar="PATH", help="Write JSON report to file")
    args = parser.parse_args()

    tool = Path(__file__).resolve().parent / "semantic_catalog_tool.py"
    cmd = [sys.executable, str(tool), "validate"]
    if args.json:
        cmd.extend(["--json", args.json])
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
