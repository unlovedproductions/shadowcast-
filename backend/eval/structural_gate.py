#!/usr/bin/env python3
"""Structural prompt/eval gate for CI — dry-run eval + snapshot clarity floors."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent
BACKEND = EVAL.parent
BASELINES = EVAL / "baselines"
SNAPSHOTS = EVAL / "snapshots"
FIXTURES = EVAL / "fixtures"

MIN_CLARITY = {
    "script_short_honest_review.txt": 60,
    "script_long_honest_review.txt": 55,
    "youtube_assets_long.txt": 60,
}


def _run(cmd: list[str], *, cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "command failed")


def _eval_set_ids() -> list[str]:
    data = json.loads((FIXTURES / "eval_set.json").read_text(encoding="utf-8"))
    return [case["id"] for case in data.get("cases", [])]


def _ensure_live_baseline(ids: list[str]) -> None:
    live_baseline = BASELINES / "eval_live_baseline.json"
    if live_baseline.exists():
        baseline = json.loads(live_baseline.read_text(encoding="utf-8"))
    else:
        baseline = {"live": True, "results": []}

    existing = {row["id"]: row for row in baseline.get("results", []) if isinstance(row, dict)}
    merged_results = []
    for case_id in ids:
        if case_id in existing:
            merged_results.append(existing[case_id])
        else:
            merged_results.append(
                {
                    "id": case_id,
                    "passed": None,
                    "pending_live": True,
                    "note": "Run with LLM_EVAL=1 and --live to populate",
                }
            )

    baseline["required_pass_ids"] = ids
    baseline["total"] = len(ids)
    baseline["results"] = merged_results
    baseline["passed"] = sum(1 for row in merged_results if row.get("passed") is True)
    baseline["failed"] = sum(1 for row in merged_results if row.get("passed") is False)
    baseline["pending_live"] = sum(1 for row in merged_results if row.get("pending_live"))
    live_baseline.write_text(json.dumps(baseline, indent=2), encoding="utf-8")


def main() -> int:
    BASELINES.mkdir(parents=True, exist_ok=True)
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)

    eval_ids = _eval_set_ids()
    _ensure_live_baseline(eval_ids)

    _run([sys.executable, str(EVAL / "export_snapshots.py")], cwd=BACKEND)
    _run(
        [
            sys.executable,
            str(EVAL / "eval_runner.py"),
            "--output",
            str(BASELINES / "eval_baseline.json"),
        ],
        cwd=BACKEND,
    )

    baseline_path = BASELINES / "eval_baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if baseline.get("failed", 0) > 0:
        print(f"Dry-run eval failed: {baseline['failed']} cases", file=sys.stderr)
        return 1

    live_baseline = json.loads((BASELINES / "eval_live_baseline.json").read_text(encoding="utf-8"))
    required = live_baseline.get("required_pass_ids") or []
    if set(required) != set(eval_ids):
        print("Live baseline missing eval_set case IDs", file=sys.stderr)
        return 1

    issues: list[str] = []
    for snapshot_name, min_clarity in MIN_CLARITY.items():
        snapshot_path = SNAPSHOTS / snapshot_name
        if not snapshot_path.exists():
            issues.append(f"missing snapshot: {snapshot_name}")
            continue
        out_path = BASELINES / f"{snapshot_name}.analysis.json"
        _run(
            [
                sys.executable,
                str(EVAL / "prompt_optimizer.py"),
                str(snapshot_path),
                "--analyze",
                "--json",
                "--model",
                "qwen2.5",
                "--output",
                str(out_path),
            ],
            cwd=BACKEND,
        )
        analysis = json.loads(out_path.read_text(encoding="utf-8"))
        clarity = int(analysis.get("clarity_score", 0))
        if clarity < min_clarity:
            issues.append(f"{snapshot_name}: clarity {clarity} < {min_clarity}")

    if issues:
        for issue in issues:
            print(f"STRUCTURAL GATE FAIL: {issue}", file=sys.stderr)
        return 1

    pending = live_baseline.get("pending_live", 0)
    if pending:
        print(f"Structural gate passed (dry-run); {pending} live eval cases pending LLM_EVAL=1")
    else:
        print("Structural gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
