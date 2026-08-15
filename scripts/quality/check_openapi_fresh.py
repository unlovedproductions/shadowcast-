#!/usr/bin/env python3
"""Export OpenAPI and verify it matches committed docs/openapi.json."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
SPEC = ROOT / "docs" / "openapi.json"


def _resolve_python() -> str:
    """Prefer repo-root .venv (has full deps); fall back to backend/.venv, then sys."""
    candidates = (
        ROOT / ".venv" / "bin" / "python",
        BACKEND / ".venv" / "bin" / "python",
    )
    for path in candidates:
        if path.is_file() or path.is_symlink():
            return str(path)
    return sys.executable


def main() -> int:
    python = _resolve_python()
    export = subprocess.run(
        [python, str(BACKEND / "export_openapi.py"), "-o", str(SPEC)],
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
