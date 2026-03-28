"""Development path bootstrap for local venv execution.

Python automatically imports ``sitecustomize`` at interpreter startup if this
file is on ``sys.path`` (for example when running from the repository root).
This keeps ``src/`` importable without requiring manual PYTHONPATH exports.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent / "src"
if SRC_DIR.is_dir():
    src_str = str(SRC_DIR)
    if src_str not in sys.path:
        sys.path.insert(0, src_str)
