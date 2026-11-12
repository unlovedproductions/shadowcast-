#!/usr/bin/env python3
"""Capture load-test baselines for ShadowCast health and status endpoints."""

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
BASELINE_PATH = BASE / "baselines" / "load_baseline.json"
DEFAULT_BASE = "http://127.0.0.1:8000"


def _run_load(
    url: str,
    *,
    concurrency: int,
    duration: int,
    method: str = "GET",
    body: str = "",
) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
        out_path = Path(handle.name)
    cmd = [
        sys.executable,
        str(BASE / "api_load_tester.py"),
        url,
        "--concurrency",
        str(concurrency),
        "--duration",
        str(duration),
        "--method",
        method,
        "--json",
        "--output",
        str(out_path),
    ]
    if body:
        cmd.extend(["--body", body])
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    try:
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"load test failed for {url}")
        return json.loads(out_path.read_text(encoding="utf-8"))
    finally:
        out_path.unlink(missing_ok=True)


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE
    base = base.rstrip("/")
    targets = [
        {
            "name": "health",
            "url": f"{base}/api/health",
            "concurrency": 20,
            "duration": 10,
        },
        {
            "name": "status_missing",
            "url": f"{base}/api/status/loadtest-missing",
            "concurrency": 10,
            "duration": 8,
        },
        {
            "name": "generate_validation",
            "url": f"{base}/api/generate",
            "method": "POST",
            "body": '{"product_info":{"product_name":""}}',
            "concurrency": 8,
            "duration": 6,
        },
    ]
    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base,
        "targets": {},
    }
    for target in targets:
        payload["targets"][target["name"]] = _run_load(
            target["url"],
            concurrency=target["concurrency"],
            duration=target["duration"],
            method=target.get("method", "GET"),
            body=target.get("body", ""),
        )
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(BASELINE_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
