#!/usr/bin/env python3
"""Export full prompts (system + user) as snapshot files for static analysis."""

import argparse
import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
BACKEND = EVAL_DIR.parent
sys.path.insert(0, str(BACKEND))

from prompts import (
    SCRIPT_SYSTEM_PROMPT,
    YOUTUBE_ASSETS_SYSTEM_PROMPT,
    build_script_user_prompt,
    build_youtube_assets_user_prompt,
    render_full_prompt,
)

SNAPSHOTS = {
    "script_short_honest_review": {
        "system": SCRIPT_SYSTEM_PROMPT,
        "builder": lambda: build_script_user_prompt(
            _product(), "curiosity", "honest_review", "short_form"
        ),
    },
    "script_long_honest_review": {
        "system": SCRIPT_SYSTEM_PROMPT,
        "builder": lambda: build_script_user_prompt(
            _product(), "data_bomb", "honest_review", "long_form"
        ),
    },
    "script_short_vs_battle": {
        "system": SCRIPT_SYSTEM_PROMPT,
        "builder": lambda: build_script_user_prompt(
            _product(), "comparison_trap", "vs_battle", "short_form"
        ),
    },
    "youtube_assets_long": {
        "system": YOUTUBE_ASSETS_SYSTEM_PROMPT,
        "builder": lambda: build_youtube_assets_user_prompt(
            _product(),
            _mock_script("hr_long"),
            "long_form",
            script_context="Hook | Pros | Cons | Verdict | Check the link",
            cons_lines="Fit issues for small ears",
            cta_lines="Check the link for current price",
            verdict_lines="Worth it for commuters",
        ),
    },
}


def _product() -> dict:
    path = EVAL_DIR / "fixtures" / "products" / "soundcore_a40.json"
    data = json.loads(path.read_text())
    data["content_style"] = "honest_review"
    return data


def _mock_script(key: str) -> dict:
    scripts = json.loads((EVAL_DIR / "fixtures" / "mock_scripts.json").read_text())
    return scripts[key]


def export_all(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, spec in SNAPSHOTS.items():
        user = spec["builder"]()
        full = render_full_prompt(spec["system"], user)
        path = out_dir / f"{name}.txt"
        path.write_text(full, encoding="utf-8")
        written.append(path)
    return written


def main():
    parser = argparse.ArgumentParser(description="Export prompt snapshots")
    parser.add_argument(
        "--output-dir",
        default=str(EVAL_DIR / "snapshots"),
        help="Directory for snapshot .txt files",
    )
    args = parser.parse_args()
    paths = export_all(Path(args.output_dir))
    for p in paths:
        print(p)


if __name__ == "__main__":
    main()
