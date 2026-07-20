#!/usr/bin/env python3
"""Export FastAPI OpenAPI schema to JSON/YAML."""

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Export ShadowCast OpenAPI schema")
    parser.add_argument(
        "--output",
        "-o",
        default=str(Path(__file__).resolve().parents[1] / "docs" / "openapi.json"),
    )
    args = parser.parse_args()

    from app import app

    schema = app.openapi()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
