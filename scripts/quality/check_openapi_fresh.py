#!/usr/bin/env python3
"""Export OpenAPI and verify it matches committed docs/openapi.json."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SPEC = ROOT / "docs" / "openapi.json"
VENV_PY = BACKEND / ".venv" / "bin" / "python"


def main() -> int:
    python = VENV_PY if VENV_PY.exists() else sys.executable
    export = subprocess.run(
        [str(python), str(BACKEND / "export_openapi.py"), "-o", str(SPEC)],
        cwd=str(BACKEND),
        capture_output=True,
        text=True,
    )
    if export.returncode != 0:
        print(export.stderr or export.stdout, file=sys.stderr)
        return export.returncode

    diff = subprocess.run(["git", "diff", "--quiet", str(SPEC)], cwd=str(ROOT))
    if diff.returncode != 0:
        print("docs/openapi.json is stale. Run: cd backend && python export_openapi.py", file=sys.stderr)
        return 1
    print("OpenAPI spec is up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
