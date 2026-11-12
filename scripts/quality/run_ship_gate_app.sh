#!/usr/bin/env python3
"""Run ship-gate against application code only (excludes vendored quality scripts)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNER = ROOT / "scripts" / "quality" / "ship_gate_scanner.py"


def main() -> int:
    if not SCANNER.exists():
        print(f"Missing scanner: {SCANNER}", file=sys.stderr)
        return 2

    targets = [ROOT / "backend", ROOT / "frontend", ROOT / "docs"]
    worst = 0
    for target in targets:
        if not target.exists():
            continue
        proc = subprocess.run(
            [sys.executable, str(SCANNER), str(target), "--json", "--no-interactive"],
            capture_output=True,
            text=True,
        )
        print(proc.stdout or proc.stderr)
        worst = max(worst, proc.returncode)
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
