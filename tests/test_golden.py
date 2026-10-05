"""Golden-output regression: a fresh build must match site/golden/ exactly.

Thin wrapper over `python _build/regress.py check` (see that script for how
the build is sandboxed and how to approve a deliberate re-baseline).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_build_output_matches_golden() -> None:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "_build" / "regress.py"), "check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
