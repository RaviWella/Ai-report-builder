#!/usr/bin/env python3
"""Generate MintHRM enterprise data dictionary under docs/."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data_dictionary.generator import main

if __name__ == "__main__":
    raise SystemExit(main())
